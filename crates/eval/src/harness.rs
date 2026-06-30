use crate::metrics::{ndcg_at_k, percentile, recall_at_k, reciprocal_rank};
use crate::types::{BenchOptions, Dataset, QueryResult, Report};
use anyhow::{Context, Result};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::time::Instant;
use synapse_core::{
    MemoryKind, RecallEngine, RecallHit, RecallQuery, Scope, Source, Store, WriteInput,
};

pub fn default_dataset_path() -> PathBuf {
    let here = Path::new(env!("CARGO_MANIFEST_DIR"));
    here.join("datasets").join("coding_mem.toml")
}

pub fn run(opts: BenchOptions) -> Result<Report> {
    let raw = std::fs::read_to_string(&opts.dataset_path)
        .with_context(|| format!("reading dataset {}", opts.dataset_path.display()))?;
    let dataset: Dataset = toml::from_str(&raw).context("parsing dataset TOML")?;

    let mut store = Store::open_in_memory().context("opening in-memory store")?;
    let mut key_to_id: HashMap<String, String> = HashMap::new();
    for m in &dataset.memories {
        let kind: MemoryKind = m.kind.parse().context("memory.kind")?;
        let scope: Scope = m.scope.parse().context("memory.scope")?;
        let written = store.write(WriteInput {
            content: m.content.clone(),
            kind,
            scope,
            source: Source::ExplicitUser,
            confidence: m.confidence,
            importance: m.importance,
        })?;
        key_to_id.insert(m.key.clone(), written.id);
    }

    let mut embedder = if opts.vectors {
        eprintln!("loading embedder (first run downloads the model)...");
        let mut e = synapse_core::Embedder::new().context("loading embedder")?;
        let pending = store.pending_embeddings(dataset.memories.len())?;
        let texts: Vec<&str> = pending.iter().map(|(_, c)| c.as_str()).collect();
        let vecs = e.embed_documents(&texts).context("embedding corpus")?;
        for ((id, _), v) in pending.iter().zip(vecs.iter()) {
            store.put_embedding(id, e.model_name(), v)?;
        }
        eprintln!("embedded {} memories", pending.len());
        Some(e)
    } else {
        None
    };

    let mut reranker = if opts.rerank {
        eprintln!("loading reranker (first run downloads the model)...");
        Some(synapse_core::FastEmbedReranker::new().context("loading reranker")?)
    } else {
        None
    };

    let id_to_key: HashMap<String, String> = key_to_id
        .iter()
        .map(|(k, v)| (v.clone(), k.clone()))
        .collect();

    let mut per_query = Vec::with_capacity(dataset.queries.len());
    let mut latencies = Vec::with_capacity(dataset.queries.len());
    let bench_start = Instant::now();

    for q in &dataset.queries {
        let rq = RecallQuery {
            query: q.query.clone(),
            k: Some(opts.k),
            scope_filter: None,
            kind_filter: None,
        };
        let t0 = Instant::now();
        let hits = {
            let mut engine = RecallEngine::new(&mut store);
            if let Some(e) = embedder.as_mut() {
                engine = engine.with_embedder(e);
            }
            if let Some(rr) = reranker.as_mut() {
                engine = engine.with_reranker(rr, opts.rerank_pool);
            }
            engine.recall(&rq)?
        };
        let elapsed_ms = t0.elapsed().as_secs_f64() * 1000.0;
        latencies.push(elapsed_ms);

        let returned: Vec<String> = hits
            .iter()
            .map(|h: &RecallHit| {
                id_to_key
                    .get(&h.memory.id)
                    .cloned()
                    .unwrap_or_else(|| h.memory.id.clone())
            })
            .collect();
        let relevant: Vec<String> = q.relevant.clone();
        let recall_5 = recall_at_k(&returned, &relevant, 5);
        let recall_10 = recall_at_k(&returned, &relevant, 10);
        let rr = reciprocal_rank(&returned, &relevant);
        let ndcg = ndcg_at_k(&returned, &relevant, 10);
        per_query.push(QueryResult {
            query: q.query.clone(),
            relevant,
            returned,
            recall_at_5: recall_5,
            recall_at_10: recall_10,
            rr,
            ndcg_at_10: ndcg,
            latency_ms: elapsed_ms,
        });
    }

    let total_ms = bench_start.elapsed().as_secs_f64() * 1000.0;
    let n = per_query.len() as f64;
    let mean = |f: fn(&QueryResult) -> f64| {
        if n == 0.0 {
            0.0
        } else {
            per_query.iter().map(f).sum::<f64>() / n
        }
    };
    Ok(Report {
        tag: opts.tag,
        dataset: opts.dataset_path.display().to_string(),
        vectors_enabled: opts.vectors,
        rerank_enabled: opts.rerank,
        rerank_pool: opts.rerank_pool,
        k: opts.k,
        n_memories: dataset.memories.len(),
        n_queries: dataset.queries.len(),
        recall_at_5: mean(|q| q.recall_at_5),
        recall_at_10: mean(|q| q.recall_at_10),
        mrr_at_10: mean(|q| q.rr),
        ndcg_at_10: mean(|q| q.ndcg_at_10),
        p50_latency_ms: percentile(&mut latencies.clone(), 50.0),
        p95_latency_ms: percentile(&mut latencies.clone(), 95.0),
        total_ms,
        per_query,
    })
}
