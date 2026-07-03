use crate::metrics::{ndcg_at_k, percentile, recall_at_k, reciprocal_rank};
use crate::types::{
    BenchOptions, Dataset, QueryResult, RecallProfileMeanMs, Report, ReturnedHitDiagnostic,
    TimingReport,
};
use anyhow::{Context, Result};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::time::Instant;
use synapse_core::{
    MemoryKind, RecallEngine, RecallHit, RecallProfile, RecallQuery, Scope, Source, Store,
    WriteInput,
};

pub fn default_dataset_path() -> PathBuf {
    let here = Path::new(env!("CARGO_MANIFEST_DIR"));
    here.join("datasets").join("coding_mem.toml")
}

pub fn run(opts: BenchOptions) -> Result<Report> {
    let dataset_start = Instant::now();
    let raw = std::fs::read_to_string(&opts.dataset_path)
        .with_context(|| format!("reading dataset {}", opts.dataset_path.display()))?;
    let dataset: Dataset = toml::from_str(&raw).context("parsing dataset TOML")?;
    let dataset_load_ms = elapsed_ms(dataset_start);

    let mut store = Store::open_in_memory().context("opening in-memory store")?;
    let mut key_to_id: HashMap<String, String> = HashMap::new();
    let store_write_start = Instant::now();
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
    let store_write_ms = elapsed_ms(store_write_start);

    let mut embedder_load_ms = None;
    let mut corpus_embedding_ms = None;
    let mut embedding_write_ms = None;
    let mut embedder = if opts.vectors {
        eprintln!("loading embedder (first run downloads the model)...");
        let embedder_load_start = Instant::now();
        let mut e = synapse_core::Embedder::new().context("loading embedder")?;
        embedder_load_ms = Some(elapsed_ms(embedder_load_start));
        let pending = store.pending_embeddings(dataset.memories.len())?;
        let texts: Vec<&str> = pending.iter().map(|(_, c)| c.as_str()).collect();
        let corpus_embedding_start = Instant::now();
        let vecs = e.embed_documents(&texts).context("embedding corpus")?;
        corpus_embedding_ms = Some(elapsed_ms(corpus_embedding_start));
        let embedding_write_start = Instant::now();
        for ((id, _), v) in pending.iter().zip(vecs.iter()) {
            store.put_embedding(id, e.model_name(), v)?;
        }
        embedding_write_ms = Some(elapsed_ms(embedding_write_start));
        eprintln!("embedded {} memories", pending.len());
        Some(e)
    } else {
        None
    };

    let mut reranker_load_ms = None;
    let mut reranker = if opts.rerank {
        eprintln!("loading reranker (first run downloads the model)...");
        let reranker_load_start = Instant::now();
        let reranker = synapse_core::FastEmbedReranker::new().context("loading reranker")?;
        reranker_load_ms = Some(elapsed_ms(reranker_load_start));
        Some(reranker)
    } else {
        None
    };

    let rrf_k = if opts.rrf_k.is_finite() && opts.rrf_k >= 0.0 {
        opts.rrf_k
    } else {
        synapse_core::DEFAULT_RRF_K
    };
    let rrf_weights = opts.rrf_weights.sanitized();

    let id_to_key: HashMap<String, String> = key_to_id
        .iter()
        .map(|(k, v)| (v.clone(), k.clone()))
        .collect();

    let mut per_query = Vec::with_capacity(dataset.queries.len());
    let mut latencies = Vec::with_capacity(dataset.queries.len());
    let bench_start = Instant::now();
    let mut profile_totals = RecallProfile::default();

    for q in &dataset.queries {
        let rq = RecallQuery {
            query: q.query.clone(),
            k: Some(opts.k),
            scope_filter: None,
            kind_filter: None,
        };
        let t0 = Instant::now();
        let profiled = {
            let mut engine = RecallEngine::new(&mut store);
            if let Some(e) = embedder.as_mut() {
                engine = engine.with_embedder(e);
            }
            if let Some(rr) = reranker.as_mut() {
                engine = engine.with_reranker(rr, opts.rerank_pool);
            }
            engine = engine.with_rrf_k(rrf_k).with_rrf_weights(rrf_weights);
            engine.recall_profiled(&rq)?
        };
        let hits = profiled.hits;
        let elapsed_ms = t0.elapsed().as_secs_f64() * 1000.0;
        latencies.push(elapsed_ms);
        add_profile(&mut profile_totals, &profiled.profile);

        let returned: Vec<String> = hits
            .iter()
            .map(|h: &RecallHit| hit_key(h, &id_to_key))
            .collect();
        let returned_hit_diagnostics: Vec<ReturnedHitDiagnostic> = hits
            .iter()
            .enumerate()
            .map(|(index, h)| ReturnedHitDiagnostic {
                key: hit_key(h, &id_to_key),
                rank: index + 1,
                score: h.score,
                rrf_score: h.rrf_score,
                rerank_score: h.rerank_score,
                activation_bonus: h.activation_bonus,
                fts_rank: h.fts_rank,
                entity_rank: h.entity_rank,
                vector_rank: h.vector_rank,
                entity_hits: h.entity_hits,
                sources: h.sources.iter().map(|source| source.to_string()).collect(),
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
            returned_hit_diagnostics,
            recall_at_5: recall_5,
            recall_at_10: recall_10,
            rr,
            ndcg_at_10: ndcg,
            latency_ms: elapsed_ms,
            profile: profiled.profile,
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
        rrf_k,
        rrf_weights,
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
        timing: TimingReport {
            dataset_load_ms,
            store_write_ms,
            embedder_load_ms,
            corpus_embedding_ms,
            embedding_write_ms,
            reranker_load_ms,
            query_wall_ms: total_ms,
            recall_profile_mean_ms: mean_profile_ms(&profile_totals, per_query.len()),
            recall_profile_totals: profile_totals,
        },
        per_query,
    })
}

fn elapsed_ms(start: Instant) -> f64 {
    start.elapsed().as_secs_f64() * 1000.0
}

fn hit_key(h: &RecallHit, id_to_key: &HashMap<String, String>) -> String {
    id_to_key
        .get(&h.memory.id)
        .cloned()
        .unwrap_or_else(|| h.memory.id.clone())
}

fn add_profile(total: &mut RecallProfile, profile: &RecallProfile) {
    total.total_ms += profile.total_ms;
    total.fts_ms += profile.fts_ms;
    total.entity_ms += profile.entity_ms;
    total.query_embedding_ms += profile.query_embedding_ms;
    total.vector_search_ms += profile.vector_search_ms;
    total.memory_hydration_ms += profile.memory_hydration_ms;
    total.rrf_fusion_ms += profile.rrf_fusion_ms;
    total.hit_build_ms += profile.hit_build_ms;
    total.reranker_ms += profile.reranker_ms;
    total.booster_ms += profile.booster_ms;
    total.final_score_ms += profile.final_score_ms;
    total.record_access_ms += profile.record_access_ms;
    total.fts_candidates += profile.fts_candidates;
    total.entity_candidates += profile.entity_candidates;
    total.vector_candidates += profile.vector_candidates;
    total.hydrated_memories += profile.hydrated_memories;
    total.fused_candidates += profile.fused_candidates;
    total.rerank_candidates += profile.rerank_candidates;
    total.returned_hits += profile.returned_hits;
}

fn mean_profile_ms(total: &RecallProfile, count: usize) -> RecallProfileMeanMs {
    if count == 0 {
        return RecallProfileMeanMs::default();
    }
    let n = count as f64;
    RecallProfileMeanMs {
        total_ms: total.total_ms / n,
        fts_ms: total.fts_ms / n,
        entity_ms: total.entity_ms / n,
        query_embedding_ms: total.query_embedding_ms / n,
        vector_search_ms: total.vector_search_ms / n,
        memory_hydration_ms: total.memory_hydration_ms / n,
        rrf_fusion_ms: total.rrf_fusion_ms / n,
        hit_build_ms: total.hit_build_ms / n,
        reranker_ms: total.reranker_ms / n,
        booster_ms: total.booster_ms / n,
        final_score_ms: total.final_score_ms / n,
        record_access_ms: total.record_access_ms / n,
    }
}
