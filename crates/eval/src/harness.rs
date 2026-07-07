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
    GraphActivationBooster, MemoryKind, RecallEngine, RecallHit, RecallProfile, RecallQuery, Scope, Source, Store,
    WriteInput,
};
use synapse_core::{
    EdgeHypothesisGenerator, HypothesisStore, RetrievalContext, RuleBasedEdgeGenerator,
};
use crate::types::HypothesisMetrics;

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

    let edge_count = if opts.graph_activation && !opts.hypothesis_generation {
        // Only use entity-shared edges when hypothesis pool is NOT active.
        // When hypothesis generation is on, edges come solely from graduation.
        let edge_start = Instant::now();
        let count = store.link_shared_entity_edges()
            .context("linking shared-entity edges")?;
        eprintln!("graph_activation: created {} entity edges in {:.1}ms", count, elapsed_ms(edge_start));
        count
    } else {
        0
    };

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

    let graph_booster = if opts.graph_activation {
        Some(GraphActivationBooster::default())
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

    let hyp_generator = if opts.hypothesis_generation {
        Some(RuleBasedEdgeGenerator::new())
    } else {
        None
    };

    for (qi, q) in dataset.queries.iter().enumerate() {
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
            if let Some(ref booster) = graph_booster {
                engine = engine.with_booster(booster);
            }
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
        // Edge Hypothesis Pool: generate and upsert hypotheses after retrieval
        if let Some(ref gen) = hyp_generator {
            let hit_ids: Vec<String> = hits.iter().map(|h| h.memory.id.clone()).collect();
            let hit_scores: Vec<f32> = hits.iter().map(|h| h.rerank_score.unwrap_or(h.rrf_score)).collect();
            // Semantic context hash: extract topic keywords from query.
            // Queries about the same topic (e.g., "pets", "music", "jobs")
            // share the same context hash, so diversity filtering works
            // on semantic diversity, not just query index diversity.
            let topic = extract_query_topic(&q.query);
            let context_hash = format!("topic_{}", topic);
            let context_tag = topic.clone();
            let now = chrono::Utc::now().timestamp();
            let ctx = RetrievalContext {
                query: &q.query,
                query_context_hash: &context_hash,
                query_context_tag: &context_tag,
                hit_memory_ids: &hit_ids,
                hit_scores: &hit_scores,
                timestamp: now,
            };
            let hyps = gen.generate(&ctx);
            for hyp in &hyps {
                let _ = store.upsert_hypothesis(hyp, &context_hash, &context_tag, &hit_ids, "co-retrieval");
            }

            // Periodic graduation: every 10 queries
            if opts.hypothesis_graduation && qi > 0 && qi % 10 == 0 {
                let _ = store.graduate_confirmed();
            }
        }

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

    // Final graduation and hypothesis metrics
    let hypothesis_metrics = if opts.hypothesis_generation {
        if opts.hypothesis_graduation {
            let _ = store.graduate_confirmed();
        }
        let status_counts = store.count_hypotheses_by_status().unwrap_or_default();
        let total: usize = status_counts.iter().map(|(_, c)| c).sum();
        let get = |s: &str| -> usize {
            status_counts.iter().find(|(st, _)| st == s).map(|(_, c)| *c).unwrap_or(0)
        };
        let edge_count = store.count_memory_edges().unwrap_or(0);
        let max_edges = dataset.memories.len() * (dataset.memories.len().saturating_sub(1));
        let density = if max_edges > 0 {
            edge_count as f64 / max_edges as f64 * 100.0
        } else {
            0.0
        };
        let edge_types = store.count_edges_by_type().unwrap_or_default();
        Some(HypothesisMetrics {
            total_hypotheses: total,
            candidates: get("candidate"),
            observed: get("observed"),
            confirmed: get("confirmed"),
            strengthened: get("strengthened"),
            disputed: get("disputed"),
            forgotten: get("forgotten"),
            graduated_edges: edge_count,
            edge_density_pct: density,
            edge_types,
            mean_confidence: 0.0,
            mean_observations: 0.0,
            mean_distinct_contexts: 0.0,
        })
    } else {
        None
    };

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
        graph_activation: opts.graph_activation,
        edge_count,
        hypothesis_generation: opts.hypothesis_generation,
        hypothesis_graduation: opts.hypothesis_graduation,
        hypothesis_metrics,
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


/// Extract a topic keyword from a DMR-style query for semantic context hashing.
fn extract_query_topic(query: &str) -> String {
    let lower = query.to_lowercase();
    let prefixes = [
        "we talked about ",
        "we discussed ",
        "we chatted about ",
        "about your ",
        "about my ",
        "about the ",
    ];
    for prefix in &prefixes {
        if let Some(pos) = lower.find(prefix) {
            let after = &query[pos + prefix.len()..];
            let end = after.find(|c: char| c == '?' || c == '.' || c == '!')
                .unwrap_or(after.len());
            let topic = after[..end].trim();
            let words: Vec<&str> = topic.split_whitespace().take(2).collect();
            if !words.is_empty() {
                return words.join("_");
            }
        }
    }
    // Fallback: first 3 words
    query
        .split_whitespace()
        .take(3)
        .collect::<Vec<_>>()
        .join("_")
}
