use crate::metrics::{ndcg_at_k, percentile, recall_at_k, reciprocal_rank};
use crate::types::{
    BenchOptions, Dataset, HypothesisMetrics, QueryResult, RecallProfileMeanMs, Report,
    ReturnedHitDiagnostic, SemanticAuditSample, SemanticConfidenceBucket,
    SemanticEdgeLifecycleRecord, SemanticGovernanceReport, SemanticJudgeKind,
    SemanticPolicyEvaluation, SemanticPolicySearchReport, SemanticSurvivalReport,
    SemanticUtilityReport, TimingReport,
};
use anyhow::{Context, Result};
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::time::Instant;
use synapse_core::{
    BoosterContext, GraphActivationBooster, MemoryEdge, MemoryKind, RecallBooster, RecallEngine,
    RecallHit, RecallProfile, RecallQuery, Scope, Source, Store, WriteInput,
};
use synapse_core::{
    CachedSemanticJudge, DeepSeekSemanticJudge, EdgeHypothesis, EdgeHypothesisGenerator,
    EdgeSemanticJudge, HeuristicSemanticJudge, HypothesisStore, JudgedEdgeGenerator,
    JudgedEdgeHypothesis, RetrievalContext, RuleBasedEdgeGenerator, SemanticEdgeMode,
};

pub fn default_dataset_path() -> PathBuf {
    let here = Path::new(env!("CARGO_MANIFEST_DIR"));
    here.join("datasets").join("coding_mem.toml")
}

const SEMANTIC_AUDIT_LIMIT_PER_DECISION: usize = 12;
const EDGE_ATTRIBUTION_LIMIT_PER_QUERY: usize = 20;
const ATTRIBUTION_EPSILON: f64 = 1e-9;
const GOVERNANCE_MIN_ATTRIBUTIONS: usize = 3;
const GOVERNANCE_MIN_STRONG_ATTRIBUTIONS: usize = 5;
const GOVERNANCE_POSITIVE_MRR: f64 = 0.005;
const GOVERNANCE_NEGATIVE_MRR: f64 = -0.005;
const GOVERNANCE_STRONG_NEGATIVE_MRR: f64 = -0.02;

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
        let count = store
            .link_shared_entity_edges()
            .context("linking shared-entity edges")?;
        eprintln!(
            "graph_activation: created {} entity edges in {:.1}ms",
            count,
            elapsed_ms(edge_start)
        );
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
    let mut semantic_cache_path = None;
    let mut semantic_cache_stats_handle = None;
    let semantic_generator =
        if opts.hypothesis_generation && opts.semantic_edge_mode != SemanticEdgeMode::Off {
            let judge: Box<dyn EdgeSemanticJudge> = match opts.semantic_judge {
                SemanticJudgeKind::Heuristic => Box::new(HeuristicSemanticJudge::default()),
                SemanticJudgeKind::DeepSeek => {
                    let deepseek = DeepSeekSemanticJudge::from_env()?;
                    if let Some(path) = opts.semantic_judge_cache_path.as_ref() {
                        let namespace = deepseek.cache_namespace();
                        let cached = CachedSemanticJudge::open(deepseek, path, namespace)?;
                        semantic_cache_path = Some(path.display().to_string());
                        semantic_cache_stats_handle = Some(cached.stats_handle());
                        Box::new(cached)
                    } else {
                        Box::new(deepseek)
                    }
                }
            };
            Some(
                JudgedEdgeGenerator::new(RuleBasedEdgeGenerator::new(), judge)
                    .with_mode(opts.semantic_edge_mode),
            )
        } else {
            None
        };
    let mut semantic_judged = 0usize;
    let mut semantic_accepted = 0usize;
    let mut semantic_rejected = 0usize;
    let mut semantic_accepted_samples = 0usize;
    let mut semantic_rejected_samples = 0usize;
    let mut semantic_audit_samples = Vec::new();
    let mut semantic_lifecycle: HashMap<String, SemanticEdgeLifecycleRecord> = HashMap::new();
    let mut semantic_utility_evaluated_queries = 0usize;
    let mut semantic_utility_affected_queries = 0usize;
    let mut governance_evaluated_queries = 0usize;
    let mut governance_changed_queries = 0usize;
    let mut governance_rank_delta_sum = 0.0f64;
    let mut governance_mrr_delta_sum = 0.0f64;
    let mut policy_totals: Vec<PolicyProbeTotals> = candidate_governance_policies()
        .into_iter()
        .map(PolicyProbeTotals::new)
        .collect();

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
        record_semantic_activations(&mut semantic_lifecycle, &hits);
        let relevant_ids: Vec<String> = q
            .relevant
            .iter()
            .filter_map(|key| key_to_id.get(key).cloned())
            .collect();
        if opts.graph_activation && has_graduated_semantic_edge(&semantic_lifecycle) {
            let baseline_hits = {
                let mut engine = RecallEngine::new(&mut store);
                if let Some(e) = embedder.as_mut() {
                    engine = engine.with_embedder(e);
                }
                if let Some(rr) = reranker.as_mut() {
                    engine = engine.with_reranker(rr, opts.rerank_pool);
                }
                engine = engine
                    .with_rrf_k(rrf_k)
                    .with_rrf_weights(rrf_weights)
                    .with_access_recording(false);
                engine.recall_profiled(&rq)?.hits
            };
            semantic_utility_evaluated_queries += 1;
            if record_semantic_edge_utility(
                &mut semantic_lifecycle,
                &baseline_hits,
                &hits,
                &relevant_ids,
                opts.k,
            ) {
                semantic_utility_affected_queries += 1;
            }
            if let Some(ref booster) = graph_booster {
                if let Some(delta) = evaluate_governance_probe(
                    &semantic_lifecycle,
                    &mut store,
                    embedder.as_mut(),
                    reranker.as_mut(),
                    &rq,
                    &hits,
                    &relevant_ids,
                    opts.k,
                    rrf_k,
                    rrf_weights,
                    opts.rerank_pool,
                    booster,
                )? {
                    governance_evaluated_queries += 1;
                    governance_rank_delta_sum += delta.rank_delta;
                    governance_mrr_delta_sum += delta.mrr_delta;
                    if delta.changed {
                        governance_changed_queries += 1;
                    }
                }
                evaluate_policy_search_probes(
                    &semantic_lifecycle,
                    &mut policy_totals,
                    &mut store,
                    embedder.as_mut(),
                    reranker.as_mut(),
                    &rq,
                    &hits,
                    &relevant_ids,
                    opts.k,
                    rrf_k,
                    rrf_weights,
                    opts.rerank_pool,
                    booster,
                )?;
            }
            if let Some(ref booster) = graph_booster {
                record_semantic_edge_attribution(
                    &mut semantic_lifecycle,
                    &mut store,
                    embedder.as_mut(),
                    reranker.as_mut(),
                    &rq,
                    &hits,
                    &relevant_ids,
                    opts.k,
                    rrf_k,
                    rrf_weights,
                    opts.rerank_pool,
                    booster,
                )?;
            }
        }
        // Edge Hypothesis Pool: generate and upsert hypotheses after retrieval
        if opts.hypothesis_generation {
            let hit_ids: Vec<String> = hits.iter().map(|h| h.memory.id.clone()).collect();
            let hit_scores: Vec<f32> = hits
                .iter()
                .map(|h| h.rerank_score.unwrap_or(h.rrf_score))
                .collect();
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
            if let Some(ref semantic) = semantic_generator {
                let generated = semantic.generate(&store, &ctx)?;
                semantic_judged += generated.accepted.len() + generated.rejected.len();
                semantic_accepted += generated.accepted.len();
                semantic_rejected += generated.rejected.len();
                for judged in &generated.accepted {
                    if semantic_accepted_samples < SEMANTIC_AUDIT_LIMIT_PER_DECISION {
                        semantic_audit_samples.push(semantic_audit_sample(
                            &store,
                            &id_to_key,
                            &q.query,
                            "accept",
                            &judged.hypothesis.source,
                            &judged.hypothesis.target,
                            judged.hypothesis.relation.as_str(),
                            judged.judgement.relation.map(|r| r.as_str()),
                            judged.judgement.confidence,
                            judged.judgement.reason_category.as_str(),
                            &judged.judgement.reason,
                        ));
                        semantic_accepted_samples += 1;
                    }
                    let reason = judged.evidence_reason(semantic.judge_name());
                    let updated = store.upsert_hypothesis(
                        &judged.hypothesis,
                        &context_hash,
                        &context_tag,
                        &hit_ids,
                        &reason,
                    )?;
                    record_semantic_acceptance(
                        &mut semantic_lifecycle,
                        judged,
                        &updated,
                        &id_to_key,
                        &q.query,
                        &context_tag,
                        qi,
                    );
                }
                for rejected in &generated.rejected {
                    if semantic_rejected_samples >= SEMANTIC_AUDIT_LIMIT_PER_DECISION {
                        break;
                    }
                    semantic_audit_samples.push(semantic_audit_sample(
                        &store,
                        &id_to_key,
                        &q.query,
                        "reject",
                        &rejected.candidate.source,
                        &rejected.candidate.target,
                        rejected.candidate.relation.as_str(),
                        rejected.judgement.relation.map(|r| r.as_str()),
                        rejected.judgement.confidence,
                        rejected.judgement.reason_category.as_str(),
                        &rejected.judgement.reason,
                    ));
                    semantic_rejected_samples += 1;
                }
            } else if let Some(ref gen) = hyp_generator {
                let hyps = gen.generate(&ctx);
                for hyp in &hyps {
                    let _ = store.upsert_hypothesis(
                        hyp,
                        &context_hash,
                        &context_tag,
                        &hit_ids,
                        "co-retrieval",
                    );
                }
            }

            // Periodic graduation: every 10 queries
            if opts.hypothesis_graduation && qi > 0 && qi % 10 == 0 {
                let _ = store.graduate_confirmed();
                mark_semantic_graduations(&mut semantic_lifecycle, qi);
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
            mark_semantic_graduations(&mut semantic_lifecycle, dataset.queries.len());
        }
        let status_counts = store.count_hypotheses_by_status().unwrap_or_default();
        let total: usize = status_counts.iter().map(|(_, c)| c).sum();
        let get = |s: &str| -> usize {
            status_counts
                .iter()
                .find(|(st, _)| st == s)
                .map(|(_, c)| *c)
                .unwrap_or(0)
        };
        let edge_count = store.count_memory_edges().unwrap_or(0);
        let max_edges = dataset.memories.len() * (dataset.memories.len().saturating_sub(1));
        let density = if max_edges > 0 {
            edge_count as f64 / max_edges as f64 * 100.0
        } else {
            0.0
        };
        let edge_types = store.count_edges_by_type().unwrap_or_default();
        let max_edge_out_degree = store.max_memory_edge_out_degree().unwrap_or(0);
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
            max_edge_out_degree,
            edge_types,
            mean_confidence: 0.0,
            mean_observations: 0.0,
            mean_distinct_contexts: 0.0,
            semantic_judged,
            semantic_accepted,
            semantic_rejected,
            semantic_acceptance_rate: if semantic_judged > 0 {
                semantic_accepted as f64 / semantic_judged as f64
            } else {
                0.0
            },
        })
    } else {
        None
    };
    let semantic_survival =
        if opts.hypothesis_generation && opts.semantic_edge_mode != SemanticEdgeMode::Off {
            Some(build_semantic_survival_report(
                &semantic_lifecycle,
                semantic_judged,
                semantic_accepted,
                semantic_rejected,
                semantic_utility_evaluated_queries,
                semantic_utility_affected_queries,
                GovernanceProbeTotals {
                    evaluated_queries: governance_evaluated_queries,
                    changed_queries: governance_changed_queries,
                    rank_delta_sum: governance_rank_delta_sum,
                    mrr_delta_sum: governance_mrr_delta_sum,
                },
                policy_totals,
            ))
        } else {
            None
        };

    let total_ms = bench_start.elapsed().as_secs_f64() * 1000.0;
    let semantic_cache_stats = semantic_cache_stats_handle
        .as_ref()
        .map(|handle| handle.stats())
        .transpose()?
        .unwrap_or_default();
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
        semantic_edge_mode: opts.semantic_edge_mode,
        semantic_judge: opts.semantic_judge,
        semantic_judge_cache_path: semantic_cache_path,
        semantic_cache_hits: semantic_cache_stats.hits,
        semantic_cache_misses: semantic_cache_stats.misses,
        semantic_cache_writes: semantic_cache_stats.writes,
        semantic_audit_samples,
        semantic_survival,
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

fn record_semantic_acceptance(
    records: &mut HashMap<String, SemanticEdgeLifecycleRecord>,
    judged: &JudgedEdgeHypothesis,
    updated: &EdgeHypothesis,
    id_to_key: &HashMap<String, String>,
    query: &str,
    context_tag: &str,
    query_index: usize,
) {
    let incoming_confidence = judged.judgement.confidence;
    let judged_relation = judged
        .judgement
        .relation
        .unwrap_or(judged.hypothesis.relation)
        .as_str()
        .to_string();
    let source_key = id_to_key
        .get(&updated.source)
        .cloned()
        .unwrap_or_else(|| updated.source.clone());
    let target_key = id_to_key
        .get(&updated.target)
        .cloned()
        .unwrap_or_else(|| updated.target.clone());
    let accepted_context = format!("{}: {}", context_tag, query);
    let entry = records
        .entry(updated.id.clone())
        .or_insert_with(|| SemanticEdgeLifecycleRecord {
            edge_id: updated.id.clone(),
            source_id: updated.source.clone(),
            target_id: updated.target.clone(),
            source_key,
            target_key,
            relation: judged_relation.clone(),
            judge_confidence: incoming_confidence,
            reason_category: judged.judgement.reason_category.as_str().to_string(),
            reason: judged.judgement.reason.clone(),
            created_at: updated.first_seen,
            accepted_at_query: query_index,
            accepted_context,
            observation_count: updated.observations,
            distinct_context_count: updated.distinct_contexts,
            hypothesis_confidence: updated.confidence,
            hypothesis_status: updated.status.as_str().to_string(),
            confirmed: is_confirmed_status(updated.status.as_str()),
            graduated: false,
            graduation_step: None,
            activation_hits: 0,
            activation_bonus_mean: 0.0,
            utility_queries: 0,
            useful_queries: 0,
            harmful_queries: 0,
            neutral_queries: 0,
            mean_rank_delta: 0.0,
            mean_mrr_delta: 0.0,
            correct_rank_improvements: 0,
            wrong_rank_promotions: 0,
            attribution_queries: 0,
            causal_useful_queries: 0,
            causal_harmful_queries: 0,
            causal_neutral_queries: 0,
            mean_causal_rank_delta: 0.0,
            mean_causal_mrr_delta: 0.0,
            causal_mrr_delta_variance: 0.0,
            causal_consistency: 0.0,
            useful_ratio: 0.0,
            harmful_ratio: 0.0,
            governance_state: "candidate".to_string(),
            governance_weight: 0.0,
            rank_delta: None,
        });

    if incoming_confidence >= entry.judge_confidence {
        entry.relation = judged_relation;
        entry.reason_category = judged.judgement.reason_category.as_str().to_string();
        entry.reason = judged.judgement.reason.clone();
    }
    entry.judge_confidence = entry.judge_confidence.max(incoming_confidence);
    entry.observation_count = updated.observations;
    entry.distinct_context_count = updated.distinct_contexts;
    entry.hypothesis_confidence = updated.confidence;
    entry.hypothesis_status = updated.status.as_str().to_string();
    entry.confirmed = is_confirmed_status(updated.status.as_str());
}

fn record_semantic_activations(
    records: &mut HashMap<String, SemanticEdgeLifecycleRecord>,
    hits: &[RecallHit],
) {
    if records.is_empty() || hits.len() < 2 {
        return;
    }
    let bonus_by_id: HashMap<&str, f32> = hits
        .iter()
        .map(|hit| (hit.memory.id.as_str(), hit.activation_bonus))
        .collect();
    for record in records.values_mut() {
        if !record.graduated {
            continue;
        }
        let Some(source_bonus) = bonus_by_id.get(record.source_id.as_str()).copied() else {
            continue;
        };
        let Some(target_bonus) = bonus_by_id.get(record.target_id.as_str()).copied() else {
            continue;
        };
        let bonus = source_bonus.max(target_bonus);
        if bonus <= 0.0 {
            continue;
        }
        let previous_hits = record.activation_hits as f32;
        record.activation_bonus_mean =
            ((record.activation_bonus_mean * previous_hits) + bonus) / (previous_hits + 1.0);
        record.activation_hits += 1;
    }
}

fn record_semantic_edge_utility(
    records: &mut HashMap<String, SemanticEdgeLifecycleRecord>,
    baseline_hits: &[RecallHit],
    graph_hits: &[RecallHit],
    relevant_ids: &[String],
    k: usize,
) -> bool {
    if records.is_empty() || baseline_hits.is_empty() || graph_hits.is_empty() {
        return false;
    }
    let missing_rank = k.max(baseline_hits.len()).max(graph_hits.len()) + 1;
    let baseline_ranks = rank_map_by_id(baseline_hits);
    let graph_ranks = rank_map_by_id(graph_hits);
    let bonus_by_id: HashMap<&str, f32> = graph_hits
        .iter()
        .map(|hit| (hit.memory.id.as_str(), hit.activation_bonus))
        .collect();
    let relevant: HashSet<&str> = relevant_ids.iter().map(String::as_str).collect();
    let mrr_delta =
        reciprocal_rank_ids(graph_hits, &relevant) - reciprocal_rank_ids(baseline_hits, &relevant);
    let mut affected = false;

    for record in records.values_mut() {
        if !record.graduated {
            continue;
        }
        let endpoints = [record.source_id.as_str(), record.target_id.as_str()];
        let mut deltas = Vec::new();
        let mut correct_improvements = 0usize;
        let mut wrong_promotions = 0usize;

        for endpoint in endpoints {
            let bonus = bonus_by_id.get(endpoint).copied().unwrap_or(0.0);
            if bonus <= 0.0 {
                continue;
            }
            let before = baseline_ranks
                .get(endpoint)
                .copied()
                .unwrap_or(missing_rank);
            let after = graph_ranks.get(endpoint).copied().unwrap_or(missing_rank);
            let rank_delta = before as f64 - after as f64;
            deltas.push(rank_delta);
            if rank_delta > 0.0 {
                if relevant.contains(endpoint) {
                    correct_improvements += 1;
                } else {
                    wrong_promotions += 1;
                }
            }
        }

        if deltas.is_empty() {
            continue;
        }

        let mean_rank_delta = deltas.iter().sum::<f64>() / deltas.len() as f64;
        update_edge_utility_record(
            record,
            mean_rank_delta,
            mrr_delta,
            correct_improvements,
            wrong_promotions,
        );
        affected = true;
    }
    affected
}

fn record_semantic_edge_attribution(
    records: &mut HashMap<String, SemanticEdgeLifecycleRecord>,
    store: &mut Store,
    mut embedder: Option<&mut synapse_core::Embedder>,
    mut reranker: Option<&mut synapse_core::FastEmbedReranker>,
    query: &RecallQuery,
    graph_hits: &[RecallHit],
    relevant_ids: &[String],
    k: usize,
    rrf_k: f64,
    rrf_weights: synapse_core::RrfBranchWeights,
    rerank_pool: usize,
    graph_booster: &GraphActivationBooster,
) -> Result<()> {
    let relevant: HashSet<&str> = relevant_ids.iter().map(String::as_str).collect();
    let missing_rank = k.max(graph_hits.len()) + 1;
    let graph_best_rank = best_relevant_rank(graph_hits, &relevant, missing_rank);
    let graph_mrr = reciprocal_rank_ids(graph_hits, &relevant);
    let candidates =
        top_attribution_candidates(records, graph_hits, EDGE_ATTRIBUTION_LIMIT_PER_QUERY);

    for candidate in candidates {
        let ablation_booster = EdgeAblationBooster::new(
            graph_booster.scale(),
            graph_booster.cap(),
            graph_booster.decay(),
            graph_booster.steps(),
            candidate.key.clone(),
        );
        let ablated_hits = {
            let mut engine = RecallEngine::new(store);
            if let Some(e) = embedder.as_deref_mut() {
                engine = engine.with_embedder(e);
            }
            if let Some(rr) = reranker.as_deref_mut() {
                engine = engine.with_reranker(rr, rerank_pool);
            }
            engine = engine
                .with_rrf_k(rrf_k)
                .with_rrf_weights(rrf_weights)
                .with_booster(&ablation_booster)
                .with_access_recording(false);
            engine.recall_profiled(query)?.hits
        };
        let ablated_missing_rank = k.max(ablated_hits.len()).max(graph_hits.len()) + 1;
        let ablated_best_rank = best_relevant_rank(&ablated_hits, &relevant, ablated_missing_rank);
        let causal_rank_delta = ablated_best_rank as f64 - graph_best_rank as f64;
        let causal_mrr_delta = graph_mrr - reciprocal_rank_ids(&ablated_hits, &relevant);
        if let Some(record) = records.get_mut(&candidate.edge_id) {
            update_edge_attribution_record(record, causal_rank_delta, causal_mrr_delta);
        }
    }
    Ok(())
}

#[derive(Debug, Clone, Copy)]
struct GovernanceProbeDelta {
    rank_delta: f64,
    mrr_delta: f64,
    changed: bool,
}

fn evaluate_governance_probe(
    records: &HashMap<String, SemanticEdgeLifecycleRecord>,
    store: &mut Store,
    mut embedder: Option<&mut synapse_core::Embedder>,
    mut reranker: Option<&mut synapse_core::FastEmbedReranker>,
    query: &RecallQuery,
    full_graph_hits: &[RecallHit],
    relevant_ids: &[String],
    k: usize,
    rrf_k: f64,
    rrf_weights: synapse_core::RrfBranchWeights,
    rerank_pool: usize,
    graph_booster: &GraphActivationBooster,
) -> Result<Option<GovernanceProbeDelta>> {
    let governance_weights = governance_weight_map(records);
    if governance_weights.is_empty() {
        return Ok(None);
    }
    let booster = GovernanceGraphBooster::new(
        graph_booster.scale(),
        graph_booster.cap(),
        graph_booster.decay(),
        graph_booster.steps(),
        governance_weights,
    );
    let governed_hits = {
        let mut engine = RecallEngine::new(store);
        if let Some(e) = embedder.as_deref_mut() {
            engine = engine.with_embedder(e);
        }
        if let Some(rr) = reranker.as_deref_mut() {
            engine = engine.with_reranker(rr, rerank_pool);
        }
        engine = engine
            .with_rrf_k(rrf_k)
            .with_rrf_weights(rrf_weights)
            .with_booster(&booster)
            .with_access_recording(false);
        engine.recall_profiled(query)?.hits
    };
    let relevant: HashSet<&str> = relevant_ids.iter().map(String::as_str).collect();
    let missing_rank = k.max(full_graph_hits.len()).max(governed_hits.len()) + 1;
    let full_rank = best_relevant_rank(full_graph_hits, &relevant, missing_rank);
    let governed_rank = best_relevant_rank(&governed_hits, &relevant, missing_rank);
    let full_mrr = reciprocal_rank_ids(full_graph_hits, &relevant);
    let governed_mrr = reciprocal_rank_ids(&governed_hits, &relevant);
    Ok(Some(GovernanceProbeDelta {
        rank_delta: full_rank as f64 - governed_rank as f64,
        mrr_delta: governed_mrr - full_mrr,
        changed: ranked_ids(full_graph_hits) != ranked_ids(&governed_hits),
    }))
}

#[derive(Debug, Clone, Copy)]
enum GovernancePolicyKind {
    CurrentRule,
    ConservativeConsistency,
    VarianceGuard,
    ShadowStrongNegative,
    SoftUtility,
}

#[derive(Debug, Clone, Copy)]
struct GovernancePolicySpec {
    name: &'static str,
    description: &'static str,
    kind: GovernancePolicyKind,
}

#[derive(Debug, Clone)]
struct PolicyProbeTotals {
    spec: GovernancePolicySpec,
    evaluated_queries: usize,
    changed_queries: usize,
    improved_queries: usize,
    harmed_queries: usize,
    neutral_queries: usize,
    rank_delta_sum: f64,
    mrr_delta_sum: f64,
    edge_weight_sum: f64,
}

impl PolicyProbeTotals {
    fn new(spec: GovernancePolicySpec) -> Self {
        Self {
            spec,
            evaluated_queries: 0,
            changed_queries: 0,
            improved_queries: 0,
            harmed_queries: 0,
            neutral_queries: 0,
            rank_delta_sum: 0.0,
            mrr_delta_sum: 0.0,
            edge_weight_sum: 0.0,
        }
    }

    fn record(&mut self, delta: GovernanceProbeDelta, mean_edge_weight: f64) {
        self.evaluated_queries += 1;
        self.rank_delta_sum += delta.rank_delta;
        self.mrr_delta_sum += delta.mrr_delta;
        self.edge_weight_sum += mean_edge_weight;
        if delta.changed {
            self.changed_queries += 1;
        }
        if delta.mrr_delta > ATTRIBUTION_EPSILON
            || (delta.mrr_delta.abs() <= ATTRIBUTION_EPSILON
                && delta.rank_delta > ATTRIBUTION_EPSILON)
        {
            self.improved_queries += 1;
        } else if delta.mrr_delta < -ATTRIBUTION_EPSILON
            || (delta.mrr_delta.abs() <= ATTRIBUTION_EPSILON
                && delta.rank_delta < -ATTRIBUTION_EPSILON)
        {
            self.harmed_queries += 1;
        } else {
            self.neutral_queries += 1;
        }
    }
}

fn candidate_governance_policies() -> Vec<GovernancePolicySpec> {
    vec![
        GovernancePolicySpec {
            name: "current_rule",
            description: "Phase 1c-5 hand-written state machine weights.",
            kind: GovernancePolicyKind::CurrentRule,
        },
        GovernancePolicySpec {
            name: "conservative_consistency",
            description: "Only downweights stable, repeatedly harmful edges.",
            kind: GovernancePolicyKind::ConservativeConsistency,
        },
        GovernancePolicySpec {
            name: "variance_guard",
            description: "Keeps high-variance edges active and downweights low-variance harm.",
            kind: GovernancePolicyKind::VarianceGuard,
        },
        GovernancePolicySpec {
            name: "shadow_strong_negative",
            description:
                "Only shadows strongly negative, consistent edges; otherwise keeps full graph.",
            kind: GovernancePolicyKind::ShadowStrongNegative,
        },
        GovernancePolicySpec {
            name: "soft_utility",
            description: "Maps utility features continuously to activation weights.",
            kind: GovernancePolicyKind::SoftUtility,
        },
    ]
}

fn evaluate_policy_search_probes(
    records: &HashMap<String, SemanticEdgeLifecycleRecord>,
    totals: &mut [PolicyProbeTotals],
    store: &mut Store,
    mut embedder: Option<&mut synapse_core::Embedder>,
    mut reranker: Option<&mut synapse_core::FastEmbedReranker>,
    query: &RecallQuery,
    full_graph_hits: &[RecallHit],
    relevant_ids: &[String],
    k: usize,
    rrf_k: f64,
    rrf_weights: synapse_core::RrfBranchWeights,
    rerank_pool: usize,
    graph_booster: &GraphActivationBooster,
) -> Result<()> {
    if records.values().all(|record| !record.graduated) {
        return Ok(());
    }
    for total in totals {
        let (edge_weights, mean_edge_weight) = policy_weight_map(records, total.spec.kind);
        let delta = if edge_weights.is_empty() {
            GovernanceProbeDelta {
                rank_delta: 0.0,
                mrr_delta: 0.0,
                changed: false,
            }
        } else {
            let booster = GovernanceGraphBooster::new(
                graph_booster.scale(),
                graph_booster.cap(),
                graph_booster.decay(),
                graph_booster.steps(),
                edge_weights,
            );
            let governed_hits = {
                let mut engine = RecallEngine::new(store);
                if let Some(e) = embedder.as_deref_mut() {
                    engine = engine.with_embedder(e);
                }
                if let Some(rr) = reranker.as_deref_mut() {
                    engine = engine.with_reranker(rr, rerank_pool);
                }
                engine = engine
                    .with_rrf_k(rrf_k)
                    .with_rrf_weights(rrf_weights)
                    .with_booster(&booster)
                    .with_access_recording(false);
                engine.recall_profiled(query)?.hits
            };
            governance_delta(full_graph_hits, &governed_hits, relevant_ids, k)
        };
        total.record(delta, mean_edge_weight);
    }
    Ok(())
}

fn governance_delta(
    full_graph_hits: &[RecallHit],
    governed_hits: &[RecallHit],
    relevant_ids: &[String],
    k: usize,
) -> GovernanceProbeDelta {
    let relevant: HashSet<&str> = relevant_ids.iter().map(String::as_str).collect();
    let missing_rank = k.max(full_graph_hits.len()).max(governed_hits.len()) + 1;
    let full_rank = best_relevant_rank(full_graph_hits, &relevant, missing_rank);
    let governed_rank = best_relevant_rank(governed_hits, &relevant, missing_rank);
    let full_mrr = reciprocal_rank_ids(full_graph_hits, &relevant);
    let governed_mrr = reciprocal_rank_ids(governed_hits, &relevant);
    GovernanceProbeDelta {
        rank_delta: full_rank as f64 - governed_rank as f64,
        mrr_delta: governed_mrr - full_mrr,
        changed: ranked_ids(full_graph_hits) != ranked_ids(governed_hits),
    }
}

fn update_edge_utility_record(
    record: &mut SemanticEdgeLifecycleRecord,
    rank_delta: f64,
    mrr_delta: f64,
    correct_improvements: usize,
    wrong_promotions: usize,
) {
    let previous = record.utility_queries as f64;
    record.mean_rank_delta = ((record.mean_rank_delta * previous) + rank_delta) / (previous + 1.0);
    record.mean_mrr_delta = ((record.mean_mrr_delta * previous) + mrr_delta) / (previous + 1.0);
    record.rank_delta = Some(record.mean_rank_delta);
    record.utility_queries += 1;
    record.correct_rank_improvements += correct_improvements;
    record.wrong_rank_promotions += wrong_promotions;
    if correct_improvements > 0 {
        record.useful_queries += 1;
    }
    if wrong_promotions > 0 {
        record.harmful_queries += 1;
    }
    if correct_improvements == 0 && wrong_promotions == 0 {
        record.neutral_queries += 1;
    }
}

fn update_edge_attribution_record(
    record: &mut SemanticEdgeLifecycleRecord,
    causal_rank_delta: f64,
    causal_mrr_delta: f64,
) {
    let previous = record.attribution_queries as f64;
    let previous_mean_mrr = record.mean_causal_mrr_delta;
    let previous_variance = record.causal_mrr_delta_variance;
    record.mean_causal_rank_delta =
        ((record.mean_causal_rank_delta * previous) + causal_rank_delta) / (previous + 1.0);
    record.mean_causal_mrr_delta =
        ((record.mean_causal_mrr_delta * previous) + causal_mrr_delta) / (previous + 1.0);
    record.attribution_queries += 1;
    let new_count = record.attribution_queries as f64;
    let previous_m2 = previous_variance * previous;
    let m2 = if previous == 0.0 {
        0.0
    } else {
        previous_m2
            + (causal_mrr_delta - previous_mean_mrr)
                * (causal_mrr_delta - record.mean_causal_mrr_delta)
    };
    record.causal_mrr_delta_variance = if new_count > 0.0 { m2 / new_count } else { 0.0 };

    if causal_mrr_delta > ATTRIBUTION_EPSILON
        || (causal_mrr_delta.abs() <= ATTRIBUTION_EPSILON
            && causal_rank_delta > ATTRIBUTION_EPSILON)
    {
        record.causal_useful_queries += 1;
    } else if causal_mrr_delta < -ATTRIBUTION_EPSILON
        || (causal_mrr_delta.abs() <= ATTRIBUTION_EPSILON
            && causal_rank_delta < -ATTRIBUTION_EPSILON)
    {
        record.causal_harmful_queries += 1;
    } else {
        record.causal_neutral_queries += 1;
    }
    refresh_edge_governance(record);
}

fn refresh_edge_governance(record: &mut SemanticEdgeLifecycleRecord) {
    let total = record.attribution_queries.max(1) as f64;
    record.useful_ratio = record.causal_useful_queries as f64 / total;
    record.harmful_ratio = record.causal_harmful_queries as f64 / total;
    record.causal_consistency = if record.attribution_queries == 0 {
        0.0
    } else {
        (record.causal_useful_queries as f64 - record.causal_harmful_queries as f64).abs() / total
    };

    let (state, weight) = edge_governance_decision(record);
    record.governance_state = state.to_string();
    record.governance_weight = weight;
}

fn edge_governance_decision(record: &SemanticEdgeLifecycleRecord) -> (&'static str, f32) {
    if !record.graduated {
        return ("candidate", 0.0);
    }
    if record.attribution_queries < GOVERNANCE_MIN_ATTRIBUTIONS {
        return ("graduated", 0.75);
    }
    if record.attribution_queries >= GOVERNANCE_MIN_STRONG_ATTRIBUTIONS
        && record.mean_causal_mrr_delta <= GOVERNANCE_STRONG_NEGATIVE_MRR
        && record.harmful_ratio >= 0.40
        && record.causal_consistency >= 0.30
    {
        return ("dormant", 0.0);
    }
    if record.mean_causal_mrr_delta <= GOVERNANCE_NEGATIVE_MRR || record.harmful_ratio >= 0.25 {
        return ("suspect", 0.25);
    }
    if record.mean_causal_mrr_delta >= GOVERNANCE_POSITIVE_MRR
        && record.useful_ratio >= 0.25
        && record.harmful_ratio <= 0.15
    {
        return ("trusted", 1.0);
    }
    ("graduated", 0.75)
}

fn has_graduated_semantic_edge(records: &HashMap<String, SemanticEdgeLifecycleRecord>) -> bool {
    records.values().any(|record| record.graduated)
}

#[derive(Debug, Clone)]
struct EdgeAttributionCandidate {
    edge_id: String,
    key: EdgeAttributionKey,
    activation_bonus: f32,
}

#[derive(Debug, Clone)]
struct EdgeAttributionKey {
    source_id: String,
    target_id: String,
    relation: String,
}

impl EdgeAttributionKey {
    fn matches(&self, edge: &MemoryEdge) -> bool {
        edge.edge == self.relation
            && ((edge.source == self.source_id && edge.target == self.target_id)
                || (edge.source == self.target_id && edge.target == self.source_id))
    }
}

fn top_attribution_candidates(
    records: &HashMap<String, SemanticEdgeLifecycleRecord>,
    graph_hits: &[RecallHit],
    limit: usize,
) -> Vec<EdgeAttributionCandidate> {
    let bonus_by_id: HashMap<&str, f32> = graph_hits
        .iter()
        .map(|hit| (hit.memory.id.as_str(), hit.activation_bonus))
        .collect();
    let mut candidates: Vec<EdgeAttributionCandidate> = records
        .values()
        .filter(|record| record.graduated)
        .filter_map(|record| {
            let source_bonus = bonus_by_id.get(record.source_id.as_str()).copied();
            let target_bonus = bonus_by_id.get(record.target_id.as_str()).copied();
            let activation_bonus = source_bonus.unwrap_or(0.0).max(target_bonus.unwrap_or(0.0));
            if activation_bonus <= 0.0 || (source_bonus.is_none() && target_bonus.is_none()) {
                return None;
            }
            Some(EdgeAttributionCandidate {
                edge_id: record.edge_id.clone(),
                key: EdgeAttributionKey {
                    source_id: record.source_id.clone(),
                    target_id: record.target_id.clone(),
                    relation: record.relation.clone(),
                },
                activation_bonus,
            })
        })
        .collect();
    candidates.sort_by(|a, b| {
        b.activation_bonus
            .partial_cmp(&a.activation_bonus)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.edge_id.cmp(&b.edge_id))
    });
    candidates.truncate(limit);
    candidates
}

struct EdgeAblationBooster {
    scale: f32,
    cap: f32,
    decay: f32,
    steps: usize,
    excluded: EdgeAttributionKey,
}

impl EdgeAblationBooster {
    fn new(scale: f32, cap: f32, decay: f32, steps: usize, excluded: EdgeAttributionKey) -> Self {
        Self {
            scale,
            cap,
            decay,
            steps: steps.max(1),
            excluded,
        }
    }
}

impl RecallBooster for EdgeAblationBooster {
    fn name(&self) -> &'static str {
        "edge_ablation"
    }

    fn apply(&self, ctx: &BoosterContext<'_>, hits: &mut [RecallHit]) -> synapse_core::Result<()> {
        if hits.len() < 2 || self.scale == 0.0 || self.cap == 0.0 || self.decay == 0.0 {
            return Ok(());
        }

        let ids: Vec<&str> = hits.iter().map(|hit| hit.memory.id.as_str()).collect();
        let edges = ctx.store.memory_edges_between(&ids, &ids)?;
        if edges.is_empty() {
            return Ok(());
        }

        let adjacency = typed_adjacency_without(edges, &self.excluded);
        let mut frontier = initial_activation(hits);
        let mut bonuses: HashMap<String, f32> = HashMap::new();

        for step in 0..self.steps {
            let attenuation = self.decay.powi(step as i32);
            let mut next_frontier = HashMap::new();

            for (source, source_activation) in &frontier {
                let Some(targets) = adjacency.get(source) else {
                    continue;
                };
                for (target, weight) in targets {
                    let propagated = source_activation * weight * self.scale * attenuation;
                    if propagated <= 0.0 || !propagated.is_finite() {
                        continue;
                    }
                    *bonuses.entry(target.clone()).or_insert(0.0) += propagated;
                    *next_frontier.entry(target.clone()).or_insert(0.0) += propagated;
                }
            }

            if next_frontier.is_empty() {
                break;
            }
            frontier = next_frontier;
        }

        for hit in hits {
            if let Some(bonus) = bonuses.get(&hit.memory.id) {
                let raw = hit.activation_bonus + bonus;
                let sigmoid_factor = 1.0 / (1.0 + (-raw * 4.0 / self.cap).exp());
                hit.activation_bonus = self.cap * sigmoid_factor;
            }
        }
        Ok(())
    }
}

struct GovernanceGraphBooster {
    scale: f32,
    cap: f32,
    decay: f32,
    steps: usize,
    edge_weights: HashMap<String, f32>,
}

impl GovernanceGraphBooster {
    fn new(
        scale: f32,
        cap: f32,
        decay: f32,
        steps: usize,
        edge_weights: HashMap<String, f32>,
    ) -> Self {
        Self {
            scale,
            cap,
            decay,
            steps: steps.max(1),
            edge_weights,
        }
    }
}

impl RecallBooster for GovernanceGraphBooster {
    fn name(&self) -> &'static str {
        "governance_graph_activation"
    }

    fn apply(&self, ctx: &BoosterContext<'_>, hits: &mut [RecallHit]) -> synapse_core::Result<()> {
        if hits.len() < 2 || self.scale == 0.0 || self.cap == 0.0 || self.decay == 0.0 {
            return Ok(());
        }

        let ids: Vec<&str> = hits.iter().map(|hit| hit.memory.id.as_str()).collect();
        let edges = ctx.store.memory_edges_between(&ids, &ids)?;
        if edges.is_empty() {
            return Ok(());
        }

        let adjacency = typed_adjacency_with_governance(edges, &self.edge_weights);
        let mut frontier = initial_activation(hits);
        let mut bonuses: HashMap<String, f32> = HashMap::new();

        for step in 0..self.steps {
            let attenuation = self.decay.powi(step as i32);
            let mut next_frontier = HashMap::new();

            for (source, source_activation) in &frontier {
                let Some(targets) = adjacency.get(source) else {
                    continue;
                };
                for (target, weight) in targets {
                    let propagated = source_activation * weight * self.scale * attenuation;
                    if propagated <= 0.0 || !propagated.is_finite() {
                        continue;
                    }
                    *bonuses.entry(target.clone()).or_insert(0.0) += propagated;
                    *next_frontier.entry(target.clone()).or_insert(0.0) += propagated;
                }
            }

            if next_frontier.is_empty() {
                break;
            }
            frontier = next_frontier;
        }

        for hit in hits {
            if let Some(bonus) = bonuses.get(&hit.memory.id) {
                let raw = hit.activation_bonus + bonus;
                let sigmoid_factor = 1.0 / (1.0 + (-raw * 4.0 / self.cap).exp());
                hit.activation_bonus = self.cap * sigmoid_factor;
            }
        }
        Ok(())
    }
}

fn typed_adjacency_without(
    edges: Vec<MemoryEdge>,
    excluded: &EdgeAttributionKey,
) -> HashMap<String, Vec<(String, f32)>> {
    let mut adjacency: HashMap<String, Vec<(String, f32)>> = HashMap::new();
    for edge in edges {
        if excluded.matches(&edge) || edge.weight <= 0.0 || !edge.weight.is_finite() {
            continue;
        }
        adjacency
            .entry(edge.source)
            .or_default()
            .push((edge.target, edge.weight));
    }
    adjacency
}

fn typed_adjacency_with_governance(
    edges: Vec<MemoryEdge>,
    edge_weights: &HashMap<String, f32>,
) -> HashMap<String, Vec<(String, f32)>> {
    let mut adjacency: HashMap<String, Vec<(String, f32)>> = HashMap::new();
    for edge in edges {
        if edge.weight <= 0.0 || !edge.weight.is_finite() {
            continue;
        }
        let governance_weight = edge_weights
            .get(&normalized_edge_key(&edge.source, &edge.target, &edge.edge))
            .copied()
            .unwrap_or(1.0);
        let weight = edge.weight * governance_weight;
        if weight <= 0.0 || !weight.is_finite() {
            continue;
        }
        adjacency
            .entry(edge.source)
            .or_default()
            .push((edge.target, weight));
    }
    adjacency
}

fn governance_weight_map(
    records: &HashMap<String, SemanticEdgeLifecycleRecord>,
) -> HashMap<String, f32> {
    records
        .values()
        .filter(|record| record.graduated)
        .filter_map(|record| {
            let (_, weight) = edge_governance_decision(record);
            if (weight - 1.0).abs() <= f32::EPSILON {
                return None;
            }
            Some((
                normalized_edge_key(&record.source_id, &record.target_id, &record.relation),
                weight,
            ))
        })
        .collect()
}

fn policy_weight_map(
    records: &HashMap<String, SemanticEdgeLifecycleRecord>,
    policy: GovernancePolicyKind,
) -> (HashMap<String, f32>, f64) {
    let mut changed = HashMap::new();
    let mut total_weight = 0.0;
    let mut total_edges = 0usize;
    for record in records.values().filter(|record| record.graduated) {
        let weight = policy_edge_weight(record, policy);
        total_weight += weight as f64;
        total_edges += 1;
        if (weight - 1.0).abs() > f32::EPSILON {
            changed.insert(
                normalized_edge_key(&record.source_id, &record.target_id, &record.relation),
                weight,
            );
        }
    }
    let mean_weight = if total_edges > 0 {
        total_weight / total_edges as f64
    } else {
        0.0
    };
    (changed, mean_weight)
}

fn policy_edge_weight(record: &SemanticEdgeLifecycleRecord, policy: GovernancePolicyKind) -> f32 {
    match policy {
        GovernancePolicyKind::CurrentRule => edge_governance_decision(record).1,
        GovernancePolicyKind::ConservativeConsistency => {
            if record.attribution_queries < GOVERNANCE_MIN_STRONG_ATTRIBUTIONS {
                1.0
            } else if record.mean_causal_mrr_delta <= GOVERNANCE_STRONG_NEGATIVE_MRR
                && record.harmful_ratio >= 0.30
                && record.causal_consistency >= 0.25
                && record.causal_mrr_delta_variance <= 0.01
            {
                0.25
            } else {
                1.0
            }
        }
        GovernancePolicyKind::VarianceGuard => {
            if record.attribution_queries < GOVERNANCE_MIN_ATTRIBUTIONS
                || record.causal_mrr_delta_variance > 0.005
            {
                1.0
            } else if record.mean_causal_mrr_delta <= GOVERNANCE_NEGATIVE_MRR
                || record.harmful_ratio >= 0.25
            {
                0.40
            } else if record.mean_causal_mrr_delta >= GOVERNANCE_POSITIVE_MRR
                && record.useful_ratio >= 0.20
            {
                1.15
            } else {
                1.0
            }
        }
        GovernancePolicyKind::ShadowStrongNegative => {
            if record.attribution_queries >= GOVERNANCE_MIN_STRONG_ATTRIBUTIONS
                && record.mean_causal_mrr_delta <= GOVERNANCE_STRONG_NEGATIVE_MRR
                && record.harmful_ratio >= 0.40
                && record.causal_consistency >= 0.30
            {
                0.0
            } else {
                1.0
            }
        }
        GovernancePolicyKind::SoftUtility => {
            if record.attribution_queries < GOVERNANCE_MIN_ATTRIBUTIONS {
                return 0.90;
            }
            let raw = 0.90
                + 3.0 * record.mean_causal_mrr_delta
                + 0.35 * (record.useful_ratio - record.harmful_ratio)
                - 0.25 * record.causal_mrr_delta_variance.min(0.25);
            raw.clamp(0.20, 1.20) as f32
        }
    }
}

fn normalized_edge_key(source: &str, target: &str, relation: &str) -> String {
    if source <= target {
        format!("{source}|{target}|{relation}")
    } else {
        format!("{target}|{source}|{relation}")
    }
}

fn initial_activation(hits: &[RecallHit]) -> HashMap<String, f32> {
    hits.iter()
        .map(|hit| (hit.memory.id.clone(), 1.0))
        .collect()
}

fn mark_semantic_graduations(
    records: &mut HashMap<String, SemanticEdgeLifecycleRecord>,
    graduation_step: usize,
) {
    for record in records.values_mut() {
        if record.graduated || !record.confirmed {
            continue;
        }
        record.graduated = true;
        record.graduation_step = Some(graduation_step);
    }
}

fn build_semantic_survival_report(
    records: &HashMap<String, SemanticEdgeLifecycleRecord>,
    candidate_count: usize,
    semantic_accepted_count: usize,
    semantic_rejected_count: usize,
    utility_evaluated_queries: usize,
    utility_affected_queries: usize,
    governance_probe: GovernanceProbeTotals,
    policy_totals: Vec<PolicyProbeTotals>,
) -> SemanticSurvivalReport {
    let mut records: Vec<SemanticEdgeLifecycleRecord> = records.values().cloned().collect();
    for record in &mut records {
        refresh_edge_governance(record);
    }
    records.sort_by(|a, b| {
        a.accepted_at_query
            .cmp(&b.accepted_at_query)
            .then_with(|| a.edge_id.cmp(&b.edge_id))
    });
    let confirmed_count = records.iter().filter(|record| record.confirmed).count();
    let graduated_count = records.iter().filter(|record| record.graduated).count();
    let activated_count = records
        .iter()
        .filter(|record| record.activation_hits > 0)
        .count();
    let confidence_buckets = build_confidence_buckets(&records);
    let utility = build_utility_report(
        &records,
        utility_evaluated_queries,
        utility_affected_queries,
    );
    let governance = build_governance_report(&records, governance_probe);
    let policy_search = build_policy_search_report(policy_totals);
    let unique_accepted_edges = records.len();
    SemanticSurvivalReport {
        candidate_count,
        semantic_accepted_count,
        semantic_rejected_count,
        unique_accepted_edges,
        confirmed_count,
        graduated_count,
        activated_count,
        utility,
        governance,
        policy_search,
        confidence_buckets,
        records,
    }
}

#[derive(Debug, Clone, Copy)]
struct GovernanceProbeTotals {
    evaluated_queries: usize,
    changed_queries: usize,
    rank_delta_sum: f64,
    mrr_delta_sum: f64,
}

fn build_governance_report(
    records: &[SemanticEdgeLifecycleRecord],
    probe: GovernanceProbeTotals,
) -> SemanticGovernanceReport {
    let candidate_edges = records
        .iter()
        .filter(|record| record.governance_state == "candidate")
        .count();
    let graduated_edges = records
        .iter()
        .filter(|record| record.governance_state == "graduated")
        .count();
    let trusted_edges = records
        .iter()
        .filter(|record| record.governance_state == "trusted")
        .count();
    let suspect_edges = records
        .iter()
        .filter(|record| record.governance_state == "suspect")
        .count();
    let dormant_edges = records
        .iter()
        .filter(|record| record.governance_state == "dormant")
        .count();
    let governed_edges = records.iter().filter(|record| record.graduated).count();
    let total_weight: f64 = records
        .iter()
        .filter(|record| record.graduated)
        .map(|record| record.governance_weight as f64)
        .sum();
    SemanticGovernanceReport {
        candidate_edges,
        graduated_edges,
        trusted_edges,
        suspect_edges,
        dormant_edges,
        mean_governance_weight: if governed_edges > 0 {
            total_weight / governed_edges as f64
        } else {
            0.0
        },
        evaluated_queries: probe.evaluated_queries,
        changed_queries: probe.changed_queries,
        mean_rank_delta_vs_full_graph: if probe.evaluated_queries > 0 {
            probe.rank_delta_sum / probe.evaluated_queries as f64
        } else {
            0.0
        },
        mean_mrr_delta_vs_full_graph: if probe.evaluated_queries > 0 {
            probe.mrr_delta_sum / probe.evaluated_queries as f64
        } else {
            0.0
        },
    }
}

fn build_policy_search_report(totals: Vec<PolicyProbeTotals>) -> SemanticPolicySearchReport {
    let evaluated_queries = totals
        .iter()
        .map(|total| total.evaluated_queries)
        .max()
        .unwrap_or(0);
    let policies: Vec<SemanticPolicyEvaluation> = totals
        .into_iter()
        .map(|total| {
            let n = total.evaluated_queries as f64;
            SemanticPolicyEvaluation {
                name: total.spec.name.to_string(),
                description: total.spec.description.to_string(),
                evaluated_queries: total.evaluated_queries,
                changed_queries: total.changed_queries,
                improved_queries: total.improved_queries,
                harmed_queries: total.harmed_queries,
                neutral_queries: total.neutral_queries,
                mean_rank_delta_vs_full_graph: if n > 0.0 {
                    total.rank_delta_sum / n
                } else {
                    0.0
                },
                mean_mrr_delta_vs_full_graph: if n > 0.0 {
                    total.mrr_delta_sum / n
                } else {
                    0.0
                },
                mean_edge_weight: if n > 0.0 {
                    total.edge_weight_sum / n
                } else {
                    0.0
                },
            }
        })
        .collect();
    let best_policy_by_mrr = policies
        .iter()
        .max_by(|a, b| {
            a.mean_mrr_delta_vs_full_graph
                .partial_cmp(&b.mean_mrr_delta_vs_full_graph)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
        .map(|policy| policy.name.clone());
    SemanticPolicySearchReport {
        evaluated_queries,
        best_policy_by_mrr,
        policies,
    }
}

fn build_utility_report(
    records: &[SemanticEdgeLifecycleRecord],
    evaluated_queries: usize,
    affected_queries: usize,
) -> SemanticUtilityReport {
    let affected_edges = records
        .iter()
        .filter(|record| record.utility_queries > 0)
        .count();
    let useful_edges = records
        .iter()
        .filter(|record| record.correct_rank_improvements > 0)
        .count();
    let harmful_edges = records
        .iter()
        .filter(|record| record.wrong_rank_promotions > 0)
        .count();
    let neutral_edges = records
        .iter()
        .filter(|record| {
            record.utility_queries > 0
                && record.correct_rank_improvements == 0
                && record.wrong_rank_promotions == 0
        })
        .count();
    let utility_events: usize = records.iter().map(|record| record.utility_queries).sum();
    let correct_rank_improvements: usize = records
        .iter()
        .map(|record| record.correct_rank_improvements)
        .sum();
    let wrong_rank_promotions: usize = records
        .iter()
        .map(|record| record.wrong_rank_promotions)
        .sum();
    let total_rank_delta: f64 = records
        .iter()
        .map(|record| record.mean_rank_delta * record.utility_queries as f64)
        .sum();
    let total_mrr_delta: f64 = records
        .iter()
        .map(|record| record.mean_mrr_delta * record.utility_queries as f64)
        .sum();
    let attribution_evaluated_edges: usize = records
        .iter()
        .map(|record| record.attribution_queries)
        .sum();
    let attribution_affected_edges = records
        .iter()
        .filter(|record| record.attribution_queries > 0)
        .count();
    let causal_useful_edges = records
        .iter()
        .filter(|record| record.causal_useful_queries > 0)
        .count();
    let causal_harmful_edges = records
        .iter()
        .filter(|record| record.causal_harmful_queries > 0)
        .count();
    let causal_neutral_edges = records
        .iter()
        .filter(|record| {
            record.attribution_queries > 0
                && record.causal_useful_queries == 0
                && record.causal_harmful_queries == 0
        })
        .count();
    let total_causal_rank_delta: f64 = records
        .iter()
        .map(|record| record.mean_causal_rank_delta * record.attribution_queries as f64)
        .sum();
    let total_causal_mrr_delta: f64 = records
        .iter()
        .map(|record| record.mean_causal_mrr_delta * record.attribution_queries as f64)
        .sum();
    SemanticUtilityReport {
        evaluated_queries,
        affected_queries,
        utility_events,
        affected_edges,
        useful_edges,
        harmful_edges,
        neutral_edges,
        mean_rank_delta: if utility_events > 0 {
            total_rank_delta / utility_events as f64
        } else {
            0.0
        },
        mean_mrr_delta: if utility_events > 0 {
            total_mrr_delta / utility_events as f64
        } else {
            0.0
        },
        correct_rank_improvements,
        wrong_rank_promotions,
        attribution_evaluated_edges,
        attribution_affected_edges,
        causal_useful_edges,
        causal_harmful_edges,
        causal_neutral_edges,
        mean_causal_rank_delta: if attribution_evaluated_edges > 0 {
            total_causal_rank_delta / attribution_evaluated_edges as f64
        } else {
            0.0
        },
        mean_causal_mrr_delta: if attribution_evaluated_edges > 0 {
            total_causal_mrr_delta / attribution_evaluated_edges as f64
        } else {
            0.0
        },
    }
}

fn build_confidence_buckets(
    records: &[SemanticEdgeLifecycleRecord],
) -> Vec<SemanticConfidenceBucket> {
    const BUCKETS: [&str; 6] = [
        "0.0-0.5", "0.5-0.6", "0.6-0.7", "0.7-0.8", "0.8-0.9", "0.9-1.0",
    ];
    BUCKETS
        .iter()
        .map(|bucket| {
            let accepted_edges = records
                .iter()
                .filter(|record| confidence_bucket(record.judge_confidence) == *bucket)
                .count();
            let confirmed_edges = records
                .iter()
                .filter(|record| confidence_bucket(record.judge_confidence) == *bucket)
                .filter(|record| record.confirmed)
                .count();
            let graduated_edges = records
                .iter()
                .filter(|record| confidence_bucket(record.judge_confidence) == *bucket)
                .filter(|record| record.graduated)
                .count();
            let activated_edges = records
                .iter()
                .filter(|record| confidence_bucket(record.judge_confidence) == *bucket)
                .filter(|record| record.activation_hits > 0)
                .count();
            SemanticConfidenceBucket {
                bucket: (*bucket).to_string(),
                accepted_edges,
                confirmed_edges,
                graduated_edges,
                activated_edges,
                confirmation_rate: rate(confirmed_edges, accepted_edges),
                graduation_rate: rate(graduated_edges, accepted_edges),
                activation_rate: rate(activated_edges, accepted_edges),
            }
        })
        .collect()
}

fn confidence_bucket(confidence: f32) -> &'static str {
    let confidence = confidence.clamp(0.0, 1.0);
    if confidence < 0.5 {
        "0.0-0.5"
    } else if confidence < 0.6 {
        "0.5-0.6"
    } else if confidence < 0.7 {
        "0.6-0.7"
    } else if confidence < 0.8 {
        "0.7-0.8"
    } else if confidence < 0.9 {
        "0.8-0.9"
    } else {
        "0.9-1.0"
    }
}

fn rate(numerator: usize, denominator: usize) -> f64 {
    if denominator == 0 {
        0.0
    } else {
        numerator as f64 / denominator as f64
    }
}

fn is_confirmed_status(status: &str) -> bool {
    status == "confirmed" || status == "strengthened"
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

fn rank_map_by_id(hits: &[RecallHit]) -> HashMap<&str, usize> {
    hits.iter()
        .enumerate()
        .map(|(index, hit)| (hit.memory.id.as_str(), index + 1))
        .collect()
}

fn reciprocal_rank_ids(hits: &[RecallHit], relevant_ids: &HashSet<&str>) -> f64 {
    if relevant_ids.is_empty() {
        return 0.0;
    }
    hits.iter()
        .position(|hit| relevant_ids.contains(hit.memory.id.as_str()))
        .map(|index| 1.0 / (index as f64 + 1.0))
        .unwrap_or(0.0)
}

fn best_relevant_rank(
    hits: &[RecallHit],
    relevant_ids: &HashSet<&str>,
    missing_rank: usize,
) -> usize {
    if relevant_ids.is_empty() {
        return missing_rank;
    }
    hits.iter()
        .position(|hit| relevant_ids.contains(hit.memory.id.as_str()))
        .map(|index| index + 1)
        .unwrap_or(missing_rank)
}

fn ranked_ids(hits: &[RecallHit]) -> Vec<&str> {
    hits.iter().map(|hit| hit.memory.id.as_str()).collect()
}

fn semantic_audit_sample(
    store: &Store,
    id_to_key: &HashMap<String, String>,
    query: &str,
    decision: &str,
    source: &str,
    target: &str,
    edge_relation: &str,
    judged_relation: Option<&str>,
    confidence: f32,
    reason_category: &str,
    reason: &str,
) -> SemanticAuditSample {
    SemanticAuditSample {
        decision: decision.to_string(),
        query: query.to_string(),
        source_key: id_to_key
            .get(source)
            .cloned()
            .unwrap_or_else(|| source.to_string()),
        target_key: id_to_key
            .get(target)
            .cloned()
            .unwrap_or_else(|| target.to_string()),
        source_content: memory_content(store, source),
        target_content: memory_content(store, target),
        edge_relation: edge_relation.to_string(),
        judged_relation: judged_relation.map(str::to_string),
        confidence,
        reason_category: reason_category.to_string(),
        reason: reason.to_string(),
    }
}

fn memory_content(store: &Store, id: &str) -> String {
    store
        .get(id)
        .ok()
        .flatten()
        .map(|memory| memory.content)
        .unwrap_or_else(|| "<missing memory>".to_string())
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
            let end = after
                .find(|c: char| c == '?' || c == '.' || c == '!')
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
