use anyhow::{ensure, Context, Result};
use chrono::Utc;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::{
    cmp::Ordering,
    collections::{BTreeMap, BTreeSet, HashMap},
    fs,
    path::{Path, PathBuf},
    str::FromStr,
};
use synapse_core::{
    CognitiveBooster, CognitiveBoosterConfig, CognitiveBoosterInput, CognitiveCompetitionTrace,
    CognitiveFactorType, CognitiveTraceEvaluator, DeterministicCognitiveBoosterV0, MemoryKind,
    RecallEngine, RecallHit, RecallProfile, RecallQuery, Scope, Source, Store, WriteInput,
    MAX_COGNITIVE_BOOSTER_BONUS,
};

use crate::{
    metrics::{ndcg_at_k, recall_at_k, reciprocal_rank},
    phase6_memory_intelligence_benchmark::{
        load_phase6_memory_intelligence_benchmark, MemoryIntelligenceMemorySpec,
        MemoryIntelligenceScenarioSpec,
    },
};

const SCHEMA_VERSION: u32 = 1;
const EVALUATION_VERSION: &str = "phase6.1-cognitive-baseline-comparison-v1";
const DATASET_PATH: &str = "crates/eval/datasets/memory_intelligence/agent_memory_benchmark.toml";
const RETRIEVAL_MODE: &str = "real_recall_engine_fts_entity_no_vectors_no_reranker";
const DEFAULT_K: usize = 5;
const POLICY_ALPHA: f64 = 0.20;
const MARGIN_THRESHOLD: f64 = 0.08;
const EXPECTED_SCENARIOS: usize = 320;
const EXPECTED_MEMORIES: usize = 1920;
const EPSILON: f64 = 1e-12;
const SCORE_DETERMINISM_EPSILON: f64 = 1e-6;

pub struct Phase6CognitiveBaselineComparisonEvaluator;

impl Phase6CognitiveBaselineComparisonEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase6CognitiveBaselineComparisonReport> {
        evaluate(tag.into())
    }
}

fn evaluate(tag: String) -> Result<Phase6CognitiveBaselineComparisonReport> {
    let specs = load_phase6_memory_intelligence_benchmark()?;
    ensure!(specs.len() == EXPECTED_SCENARIOS);
    let mut fixtures = Vec::with_capacity(specs.len());
    for spec in specs {
        fixtures.push(build_fixture(spec)?);
    }

    let policies = PolicySpec::all()
        .into_iter()
        .map(|policy| evaluate_policy(policy, &fixtures))
        .collect::<Result<Vec<_>>>()?;
    let factor_ablations = AblationSpec::all()
        .into_iter()
        .map(|ablation| evaluate_ablation(ablation, &fixtures))
        .collect::<Result<Vec<_>>>()?;
    let decision = build_decision(&policies, &factor_ablations)?;

    let all_hits_unchanged = fixtures.iter().all(Fixture::hits_unchanged);
    let all_stores_unchanged = fixtures.iter().all(Fixture::store_unchanged);
    let all_retrieval_deterministic = fixtures
        .iter()
        .all(|fixture| fixture.retrieval_deterministic);
    let all_policy_deterministic = policies
        .iter()
        .all(|policy| (policy.metrics.determinism - 1.0).abs() <= EPSILON);
    let all_ablation_deterministic = factor_ablations
        .iter()
        .all(|ablation| (ablation.metrics.determinism - 1.0).abs() <= EPSILON);
    let all_candidate_pools_preserved = policies
        .iter()
        .all(|policy| policy.candidate_pool_preserved)
        && factor_ablations
            .iter()
            .all(|ablation| ablation.candidate_pool_preserved);
    let all_expected_retrieved = fixtures.iter().all(Fixture::expected_retrieved);

    let guards = CognitiveBaselineComparisonGuards {
        eval_only: true,
        shadow_only: true,
        baseline_authoritative: true,
        real_recall_engine_used: true,
        artificial_baseline_scores_used: false,
        recall_engine_modified: false,
        candidate_generation_modified: false,
        retrieval_scores_mutated: !all_hits_unchanged,
        candidate_pool_changed: !all_candidate_pools_preserved,
        policy_memory_written: false,
        memory_mutated: !all_stores_unchanged,
        memory_schema_changed: false,
        runtime_applied: false,
        runtime_booster_registered: false,
        runtime_authorization: false,
        production_claim_authorized: false,
    };

    let pass = fixtures.len() == EXPECTED_SCENARIOS
        && fixtures
            .iter()
            .map(|fixture| fixture.spec.memory.len())
            .sum::<usize>()
            == EXPECTED_MEMORIES
        && policies.len() == 6
        && factor_ablations.len() == 6
        && all_expected_retrieved
        && all_retrieval_deterministic
        && all_policy_deterministic
        && all_ablation_deterministic
        && !guards.artificial_baseline_scores_used
        && !guards.recall_engine_modified
        && !guards.candidate_generation_modified
        && !guards.retrieval_scores_mutated
        && !guards.candidate_pool_changed
        && !guards.policy_memory_written
        && !guards.memory_mutated
        && !guards.memory_schema_changed
        && !guards.runtime_applied
        && !guards.runtime_booster_registered
        && !guards.runtime_authorization
        && !guards.production_claim_authorized;

    Ok(Phase6CognitiveBaselineComparisonReport {
        schema_version: SCHEMA_VERSION,
        tag,
        phase: "Phase 6.1 Cognitive vs Simple Baseline Evaluation".to_string(),
        mode: "eval_only_shadow_only_algorithm_attribution".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        protocol: CognitiveBaselineComparisonProtocol {
            dataset_path: DATASET_PATH.to_string(),
            dataset_sha256: hash_file(&repo_path(DATASET_PATH))?,
            retrieval_mode: RETRIEVAL_MODE.to_string(),
            candidate_limit: DEFAULT_K,
            policy_alpha: POLICY_ALPHA,
            margin_threshold: MARGIN_THRESHOLD,
            simple_combined_formula:
                "(normalized_confidence + recency + failure) / 3".to_string(),
            cognitive_signal:
                "unchanged deterministic_cognitive_booster_v0 bounded_bonus / 0.10".to_string(),
            ablation_method:
                "clone trace, remove exactly one factor type, run unchanged booster".to_string(),
            quality_gate_semantics:
                "PASS validates comparison integrity, determinism, and safety; it does not require positive cognitive gain"
                    .to_string(),
        },
        dataset: summarize_dataset(&fixtures),
        policies,
        factor_ablations,
        decision,
        guards,
        pass,
        status: if pass { "PASS" } else { "FAIL" }.to_string(),
        conclusion: "Phase 6.1 compares fixed Margin-Guarded Cognitive ranking against retrieval and simple metadata heuristics on the frozen Phase 6.0 workload. Runtime remains unauthorized."
            .to_string(),
    })
}

fn build_fixture(spec: MemoryIntelligenceScenarioSpec) -> Result<Fixture> {
    let mut store = Store::open_in_memory()?;
    let mut label_to_id = BTreeMap::new();
    let mut id_to_memory = HashMap::new();
    let mut recently_accessed = Vec::new();
    let mut access_timestamp = 0_i64;
    let mut ordered = spec.memory.iter().collect::<Vec<_>>();
    ordered.sort_by_key(|memory| memory.turn);

    for memory in ordered {
        let stored = store.write(WriteInput {
            content: memory.content.clone(),
            kind: MemoryKind::from_str(&memory.kind)?,
            scope: Scope::User,
            source: Source::ExplicitUser,
            confidence: Some(memory.confidence as f32),
            importance: Some(memory.importance as f32),
        })?;
        access_timestamp = access_timestamp.max(stored.valid_from + 1);
        if memory.recently_accessed {
            recently_accessed.push(stored.id.clone());
        }
        label_to_id.insert(memory.label.clone(), stored.id.clone());
        id_to_memory.insert(stored.id, memory.clone());
    }
    if !recently_accessed.is_empty() {
        let ids = recently_accessed
            .iter()
            .map(String::as_str)
            .collect::<Vec<_>>();
        store.record_access(&ids, access_timestamp)?;
    }

    let store_snapshot = snapshot_store(&store, label_to_id.values())?;
    let query = RecallQuery {
        query: spec.query.clone(),
        k: Some(DEFAULT_K),
        scope_filter: Some(Scope::User),
        kind_filter: None,
    };
    let first = RecallEngine::new(&mut store)
        .with_access_recording(false)
        .recall_profiled(&query)?;
    let second = RecallEngine::new(&mut store)
        .with_access_recording(false)
        .recall_profiled(&query)?;
    ensure!(
        !first.hits.is_empty(),
        "scenario {} returned no RecallHit",
        spec.id
    );
    let retrieval_deterministic = same_hits(&first.hits, &second.hits);
    ensure!(
        retrieval_deterministic,
        "scenario {} retrieval changed",
        spec.id
    );
    ensure!(store_snapshot == snapshot_store(&store, label_to_id.values())?);

    let hits = first.hits;
    let hit_snapshot = serde_json::to_string(&hits)?;
    let trace = CognitiveTraceEvaluator::evaluate(&spec.query, &hits);
    let cognitive_signal = booster_signal(&hits, &trace)?;

    Ok(Fixture {
        spec,
        store,
        hits,
        profile: first.profile,
        trace,
        label_to_id,
        id_to_memory,
        cognitive_signal,
        hit_snapshot,
        store_snapshot,
        retrieval_deterministic,
    })
}

fn booster_signal(
    hits: &[RecallHit],
    trace: &CognitiveCompetitionTrace,
) -> Result<HashMap<String, f64>> {
    let config = CognitiveBoosterConfig::shadow(MAX_COGNITIVE_BOOSTER_BONUS, hits.len())?;
    let output =
        DeterministicCognitiveBoosterV0.boost(CognitiveBoosterInput::new(hits, trace, &config));
    ensure!(output.bounded());
    ensure!(!output.runtime_applied());
    ensure!(!output.memory_mutated());
    Ok(output
        .adjusted_scores()
        .iter()
        .map(|candidate| {
            (
                candidate.candidate_id.clone(),
                normalize(candidate.bounded_bonus / MAX_COGNITIVE_BOOSTER_BONUS),
            )
        })
        .collect())
}

fn same_hits(left: &[RecallHit], right: &[RecallHit]) -> bool {
    left.len() == right.len()
        && left.iter().zip(right).all(|(left, right)| {
            left.memory.id == right.memory.id
                && (f64::from(left.score) - f64::from(right.score)).abs()
                    <= SCORE_DETERMINISM_EPSILON
        })
}

fn snapshot_store<'a>(store: &Store, ids: impl Iterator<Item = &'a String>) -> Result<String> {
    let mut memories = ids
        .map(|id| store.get(id))
        .collect::<std::result::Result<Vec<_>, _>>()?;
    memories.sort_by(|left, right| {
        left.as_ref()
            .map(|memory| &memory.id)
            .cmp(&right.as_ref().map(|memory| &memory.id))
    });
    Ok(serde_json::to_string(&memories)?)
}

fn evaluate_policy(policy: PolicySpec, fixtures: &[Fixture]) -> Result<PolicyResult> {
    let mut scenarios = Vec::with_capacity(fixtures.len());
    for fixture in fixtures {
        let first = apply_policy(policy, fixture, None)?;
        let replay = apply_policy(policy, fixture, None)?;
        let deterministic = first == replay;
        ensure!(
            deterministic,
            "policy {} is not deterministic",
            policy.name()
        );
        scenarios.push(build_scenario_report(
            policy.name(),
            fixture,
            first,
            deterministic,
        ));
    }
    let metrics = aggregate_metrics(&scenarios);
    Ok(PolicyResult {
        policy: policy.name().to_string(),
        family: policy.family().to_string(),
        alpha: policy.alpha(),
        margin_threshold: policy.threshold(),
        candidate_pool_preserved: scenarios
            .iter()
            .all(|scenario| scenario.candidate_pool_preserved),
        runtime_applied: false,
        metrics,
        scenarios,
    })
}

fn evaluate_ablation(ablation: AblationSpec, fixtures: &[Fixture]) -> Result<AblationResult> {
    let mut scenarios = Vec::with_capacity(fixtures.len());
    for fixture in fixtures {
        let first = apply_policy(
            PolicySpec::MarginGuardCognitive,
            fixture,
            ablation.excluded(),
        )?;
        let replay = apply_policy(
            PolicySpec::MarginGuardCognitive,
            fixture,
            ablation.excluded(),
        )?;
        let deterministic = first == replay;
        ensure!(
            deterministic,
            "ablation {} is not deterministic",
            ablation.name()
        );
        scenarios.push(build_scenario_report(
            ablation.name(),
            fixture,
            first,
            deterministic,
        ));
    }
    let metrics = aggregate_metrics(&scenarios);
    Ok(AblationResult {
        ablation: ablation.name().to_string(),
        excluded_factor: ablation.excluded().map(factor_name).map(str::to_string),
        alpha: POLICY_ALPHA,
        margin_threshold: MARGIN_THRESHOLD,
        candidate_pool_preserved: scenarios
            .iter()
            .all(|scenario| scenario.candidate_pool_preserved),
        runtime_applied: false,
        metrics,
    })
}

fn apply_policy(
    policy: PolicySpec,
    fixture: &Fixture,
    excluded_factor: Option<CognitiveFactorType>,
) -> Result<Vec<RankedCandidate>> {
    let max_baseline = fixture
        .hits
        .iter()
        .map(|hit| f64::from(hit.score))
        .fold(EPSILON, f64::max);
    let cognitive_signal = if matches!(policy, PolicySpec::MarginGuardCognitive) {
        if let Some(excluded) = excluded_factor {
            let mut trace = fixture.trace.clone();
            trace
                .factors
                .retain(|factor| factor.factor_type != excluded);
            booster_signal(&fixture.hits, &trace)?
        } else {
            fixture.cognitive_signal.clone()
        }
    } else {
        HashMap::new()
    };

    let mut candidates = fixture
        .hits
        .iter()
        .enumerate()
        .map(|(index, hit)| {
            let baseline_score = f64::from(hit.score);
            let baseline_normalized = normalize(baseline_score / max_baseline);
            let signal = match policy {
                PolicySpec::RetrievalBaseline => baseline_normalized,
                PolicySpec::ConfidenceOnly => normalize(f64::from(hit.memory.confidence)),
                PolicySpec::RecencyOnly => recency_signal(hit),
                PolicySpec::FailureOnly => failure_signal(&fixture.spec.query, hit),
                PolicySpec::SimpleCombined => {
                    (normalize(f64::from(hit.memory.confidence))
                        + recency_signal(hit)
                        + failure_signal(&fixture.spec.query, hit))
                        / 3.0
                }
                PolicySpec::MarginGuardCognitive => {
                    cognitive_signal.get(&hit.memory.id).copied().unwrap_or(0.0)
                }
            };
            let policy_score = if matches!(policy, PolicySpec::RetrievalBaseline) {
                baseline_normalized
            } else {
                baseline_normalized * (1.0 - POLICY_ALPHA) + signal * POLICY_ALPHA
            };
            RankedCandidate {
                candidate_id: hit.memory.id.clone(),
                baseline_rank: index + 1,
                baseline_score,
                baseline_normalized,
                signal,
                policy_score,
            }
        })
        .collect::<Vec<_>>();

    if matches!(policy, PolicySpec::RetrievalBaseline) {
        return Ok(candidates);
    }
    let mut guarded = candidates
        .iter()
        .filter(|candidate| 1.0 - candidate.baseline_normalized <= MARGIN_THRESHOLD + EPSILON)
        .cloned()
        .collect::<Vec<_>>();
    let mut preserved = candidates
        .iter()
        .filter(|candidate| 1.0 - candidate.baseline_normalized > MARGIN_THRESHOLD + EPSILON)
        .cloned()
        .collect::<Vec<_>>();
    guarded.sort_by(compare_ranked_candidate);
    preserved.sort_by_key(|candidate| candidate.baseline_rank);
    guarded.extend(preserved);
    candidates = guarded;
    Ok(candidates)
}

fn recency_signal(hit: &RecallHit) -> f64 {
    if hit.memory.last_accessed_at.is_some() {
        1.0
    } else {
        0.0
    }
}

fn failure_signal(query: &str, hit: &RecallHit) -> f64 {
    if hit.memory.kind != MemoryKind::Failure {
        return 0.0;
    }
    0.5 + lexical_overlap(query, &hit.memory.content) * 0.5
}

fn lexical_overlap(query: &str, content: &str) -> f64 {
    let query_tokens = tokens(query);
    if query_tokens.is_empty() {
        return 0.0;
    }
    let content_tokens = tokens(content);
    safe_div(
        query_tokens.intersection(&content_tokens).count() as f64,
        query_tokens.len() as f64,
    )
}

fn tokens(value: &str) -> BTreeSet<String> {
    value
        .split(|character: char| !character.is_alphanumeric())
        .filter(|token| !token.is_empty())
        .map(str::to_lowercase)
        .collect()
}

fn compare_ranked_candidate(left: &RankedCandidate, right: &RankedCandidate) -> Ordering {
    right
        .policy_score
        .partial_cmp(&left.policy_score)
        .unwrap_or(Ordering::Equal)
        .then_with(|| left.baseline_rank.cmp(&right.baseline_rank))
}

fn build_scenario_report(
    policy: &str,
    fixture: &Fixture,
    ranking: Vec<RankedCandidate>,
    deterministic: bool,
) -> ScenarioPolicyReport {
    let baseline_ids = fixture
        .hits
        .iter()
        .map(|hit| hit.memory.id.clone())
        .collect::<Vec<_>>();
    let policy_ids = ranking
        .iter()
        .map(|candidate| candidate.candidate_id.clone())
        .collect::<Vec<_>>();
    let expected_id = fixture
        .label_to_id
        .get(&fixture.spec.expected_top)
        .expect("validated expected label");
    let relevant_ids = vec![expected_id.clone()];
    let baseline_top_expected = baseline_ids.first() == Some(expected_id);
    let policy_top_expected = policy_ids.first() == Some(expected_id);
    let top1_changed = baseline_ids.first() != policy_ids.first();
    let successful_intervention =
        fixture.spec.intervention_required && top1_changed && policy_top_expected;
    let unnecessary_intervention = !fixture.spec.intervention_required && top1_changed;
    let catastrophic_regression = baseline_top_expected && !policy_top_expected;
    let candidate_pool_preserved = same_pool(&baseline_ids, &policy_ids);
    let competition_eligible = ranking
        .iter()
        .filter(|candidate| 1.0 - candidate.baseline_normalized <= MARGIN_THRESHOLD + EPSILON)
        .count()
        > 1;

    ScenarioPolicyReport {
        id: fixture.spec.id.clone(),
        split: fixture.spec.split.clone(),
        category: fixture.spec.category.clone(),
        policy: policy.to_string(),
        intervention_required: fixture.spec.intervention_required,
        expected_top: fixture.spec.expected_top.clone(),
        expected_retrieved: policy_ids.iter().any(|id| id == expected_id),
        baseline_ranking: baseline_ids
            .iter()
            .map(|id| fixture.label_for_id(id).to_string())
            .collect(),
        policy_ranking: policy_ids
            .iter()
            .map(|id| fixture.label_for_id(id).to_string())
            .collect(),
        recall_at_1: recall_at_k(&policy_ids, &relevant_ids, 1),
        recall_at_3: recall_at_k(&policy_ids, &relevant_ids, 3),
        mrr_at_5: reciprocal_rank(&policy_ids, &relevant_ids),
        ndcg_at_5: ndcg_at_k(&policy_ids, &relevant_ids, 5),
        baseline_top_expected,
        policy_top_expected,
        top1_changed,
        successful_intervention,
        unnecessary_intervention,
        catastrophic_regression,
        competition_eligible,
        deterministic,
        candidate_pool_preserved,
        runtime_applied: false,
        retrieval_profile: fixture.profile.clone(),
        candidates: ranking
            .into_iter()
            .enumerate()
            .map(|(index, candidate)| CandidatePolicyReport {
                label: fixture.label_for_id(&candidate.candidate_id).to_string(),
                baseline_rank: candidate.baseline_rank,
                policy_rank: index + 1,
                baseline_score: candidate.baseline_score,
                baseline_normalized: candidate.baseline_normalized,
                policy_signal: candidate.signal,
                policy_score: candidate.policy_score,
            })
            .collect(),
    }
}

fn aggregate_metrics(scenarios: &[ScenarioPolicyReport]) -> ComparisonMetrics {
    let count = scenarios.len() as f64;
    let changed = scenarios
        .iter()
        .filter(|scenario| scenario.top1_changed)
        .count();
    let successful = scenarios
        .iter()
        .filter(|scenario| scenario.successful_intervention)
        .count();
    let required = scenarios
        .iter()
        .filter(|scenario| scenario.intervention_required)
        .count();
    let unnecessary_base = scenarios
        .iter()
        .filter(|scenario| !scenario.intervention_required)
        .count();
    let baseline_correct = scenarios
        .iter()
        .filter(|scenario| scenario.baseline_top_expected)
        .count();

    ComparisonMetrics {
        scenarios: scenarios.len(),
        expected_candidate_retrieval_rate: safe_div(
            scenarios
                .iter()
                .filter(|scenario| scenario.expected_retrieved)
                .count() as f64,
            count,
        ),
        recall_at_1: mean(scenarios, |scenario| scenario.recall_at_1),
        recall_at_3: mean(scenarios, |scenario| scenario.recall_at_3),
        mrr_at_5: mean(scenarios, |scenario| scenario.mrr_at_5),
        ndcg_at_5: mean(scenarios, |scenario| scenario.ndcg_at_5),
        intervention_precision: safe_div(successful as f64, changed as f64),
        intervention_recall: safe_div(
            scenarios
                .iter()
                .filter(|scenario| scenario.intervention_required && scenario.policy_top_expected)
                .count() as f64,
            required as f64,
        ),
        unnecessary_intervention_rate: safe_div(
            scenarios
                .iter()
                .filter(|scenario| scenario.unnecessary_intervention)
                .count() as f64,
            unnecessary_base as f64,
        ),
        catastrophic_regression_rate: safe_div(
            scenarios
                .iter()
                .filter(|scenario| scenario.catastrophic_regression)
                .count() as f64,
            baseline_correct as f64,
        ),
        top1_change_rate: safe_div(changed as f64, count),
        competition_eligible_rate: safe_div(
            scenarios
                .iter()
                .filter(|scenario| scenario.competition_eligible)
                .count() as f64,
            count,
        ),
        determinism: safe_div(
            scenarios
                .iter()
                .filter(|scenario| scenario.deterministic)
                .count() as f64,
            count,
        ),
    }
}

fn build_decision(
    policies: &[PolicyResult],
    ablations: &[AblationResult],
) -> Result<CognitiveBaselineDecision> {
    let cognitive = find_policy(policies, "margin_guard_cognitive")?;
    let simple_names = [
        "confidence_only_margin_guarded",
        "recency_only_margin_guarded",
        "failure_only_margin_guarded",
        "simple_combined_margin_guarded",
    ];
    let best_simple = policies
        .iter()
        .filter(|policy| simple_names.contains(&policy.policy.as_str()))
        .max_by(|left, right| {
            left.metrics
                .mrr_at_5
                .partial_cmp(&right.metrics.mrr_at_5)
                .unwrap_or(Ordering::Equal)
                .then_with(|| {
                    left.metrics
                        .recall_at_1
                        .partial_cmp(&right.metrics.recall_at_1)
                        .unwrap_or(Ordering::Equal)
                })
        })
        .context("missing simple baselines")?;
    let mrr_gain = cognitive.metrics.mrr_at_5 - best_simple.metrics.mrr_at_5;
    let recall_gain = cognitive.metrics.recall_at_1 - best_simple.metrics.recall_at_1;
    let outcome = if mrr_gain > EPSILON
        && recall_gain >= -EPSILON
        && cognitive.metrics.catastrophic_regression_rate <= EPSILON
    {
        "A_cognitive_exceeds_best_simple"
    } else if mrr_gain.abs() <= EPSILON && recall_gain.abs() <= EPSILON {
        "B_cognitive_matches_best_simple"
    } else {
        "C_cognitive_below_best_simple"
    };

    let full = ablations
        .iter()
        .find(|ablation| ablation.ablation == "full_cognitive")
        .context("missing full cognitive ablation")?;
    let mut factor_deltas = Vec::new();
    for ablation in ablations
        .iter()
        .filter(|ablation| ablation.excluded_factor.is_some())
    {
        factor_deltas.push(FactorContribution {
            factor: ablation.excluded_factor.clone().unwrap_or_default(),
            mrr_at_5_delta_when_removed: ablation.metrics.mrr_at_5 - full.metrics.mrr_at_5,
            recall_at_1_delta_when_removed: ablation.metrics.recall_at_1 - full.metrics.recall_at_1,
            independently_contributing: ablation.metrics.mrr_at_5 + EPSILON < full.metrics.mrr_at_5
                || ablation.metrics.recall_at_1 + EPSILON < full.metrics.recall_at_1,
        });
    }
    let contributing_factors = factor_deltas
        .iter()
        .filter(|factor| factor.independently_contributing)
        .map(|factor| factor.factor.clone())
        .collect::<Vec<_>>();
    let zero_intervention_authority = cognitive.metrics.competition_eligible_rate <= EPSILON;
    let attribution_resolved = !zero_intervention_authority;
    let hermes_recommended = outcome == "A_cognitive_exceeds_best_simple" && attribution_resolved;

    Ok(CognitiveBaselineDecision {
        best_simple_baseline: best_simple.policy.clone(),
        best_simple_mrr_at_5: best_simple.metrics.mrr_at_5,
        best_simple_recall_at_1: best_simple.metrics.recall_at_1,
        cognitive_mrr_at_5: cognitive.metrics.mrr_at_5,
        cognitive_recall_at_1: cognitive.metrics.recall_at_1,
        cognitive_gain_vs_best_simple_baseline: mrr_gain,
        cognitive_recall_at_1_gain_vs_best_simple_baseline: recall_gain,
        outcome: outcome.to_string(),
        cognitive_exceeds_best_simple: outcome == "A_cognitive_exceeds_best_simple",
        cognitive_matches_best_simple: outcome == "B_cognitive_matches_best_simple",
        independent_value_supported: outcome == "A_cognitive_exceeds_best_simple",
        attribution_resolved,
        zero_intervention_authority,
        metadata_aggregation_only: outcome == "B_cognitive_matches_best_simple"
            && attribution_resolved,
        factor_deltas,
        contributing_factors,
        hermes_shadow_integration_recommended: hermes_recommended,
        hermes_recommendation: if hermes_recommended {
            "Eligible for a separate Hermes shadow-integration review; this report does not authorize runtime use."
        } else if zero_intervention_authority {
            "Do not enter Hermes integration: the locked 0.08 Margin Guard admitted no two-candidate competitions on this workload, so independent-value attribution is unresolved."
        } else if outcome == "B_cognitive_matches_best_simple" {
            "Do not enter Hermes integration yet; position Cognitive as observability plus conditional retrieval policy."
        } else {
            "Freeze the booster and retain the trace/evaluation framework; do not enter Hermes integration."
        }
        .to_string(),
        runtime_authorization: false,
        production_claim_authorized: false,
    })
}

fn find_policy<'a>(policies: &'a [PolicyResult], name: &str) -> Result<&'a PolicyResult> {
    policies
        .iter()
        .find(|policy| policy.policy == name)
        .with_context(|| format!("missing policy {name}"))
}

fn summarize_dataset(fixtures: &[Fixture]) -> CognitiveBaselineDatasetSummary {
    let mut split_counts = BTreeMap::new();
    let mut category_counts = BTreeMap::new();
    for fixture in fixtures {
        *split_counts.entry(fixture.spec.split.clone()).or_default() += 1;
        *category_counts
            .entry(fixture.spec.category.clone())
            .or_default() += 1;
    }
    CognitiveBaselineDatasetSummary {
        scenarios: fixtures.len(),
        memories: fixtures
            .iter()
            .map(|fixture| fixture.spec.memory.len())
            .sum(),
        categories: category_counts.len(),
        intervention_required: fixtures
            .iter()
            .filter(|fixture| fixture.spec.intervention_required)
            .count(),
        no_intervention: fixtures
            .iter()
            .filter(|fixture| !fixture.spec.intervention_required)
            .count(),
        split_counts,
        category_counts,
    }
}

fn same_pool(left: &[String], right: &[String]) -> bool {
    left.iter().cloned().collect::<BTreeSet<_>>() == right.iter().cloned().collect::<BTreeSet<_>>()
}

fn mean(scenarios: &[ScenarioPolicyReport], metric: impl Fn(&ScenarioPolicyReport) -> f64) -> f64 {
    safe_div(scenarios.iter().map(metric).sum(), scenarios.len() as f64)
}

fn normalize(value: f64) -> f64 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        0.0
    }
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() <= EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

fn factor_name(factor: CognitiveFactorType) -> &'static str {
    match factor {
        CognitiveFactorType::SemanticMatch => "semantic",
        CognitiveFactorType::TemporalConfidence => "temporal",
        CognitiveFactorType::Reliability => "reliability",
        CognitiveFactorType::PreferenceAlignment => "preference",
        CognitiveFactorType::FailureEvidence => "failure",
        CognitiveFactorType::ContextAlignment => "context",
    }
}

fn repo_path(relative: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join(relative)
}

fn hash_file(path: &Path) -> Result<String> {
    let mut hasher = Sha256::new();
    hasher.update(fs::read(path)?);
    Ok(format!("{:x}", hasher.finalize()))
}

struct Fixture {
    spec: MemoryIntelligenceScenarioSpec,
    store: Store,
    hits: Vec<RecallHit>,
    profile: RecallProfile,
    trace: CognitiveCompetitionTrace,
    label_to_id: BTreeMap<String, String>,
    id_to_memory: HashMap<String, MemoryIntelligenceMemorySpec>,
    cognitive_signal: HashMap<String, f64>,
    hit_snapshot: String,
    store_snapshot: String,
    retrieval_deterministic: bool,
}

impl Fixture {
    fn label_for_id(&self, id: &str) -> &str {
        self.id_to_memory
            .get(id)
            .map(|memory| memory.label.as_str())
            .unwrap_or("<unknown>")
    }

    fn expected_retrieved(&self) -> bool {
        self.label_to_id
            .get(&self.spec.expected_top)
            .is_some_and(|expected| self.hits.iter().any(|hit| &hit.memory.id == expected))
    }

    fn hits_unchanged(&self) -> bool {
        serde_json::to_string(&self.hits).is_ok_and(|snapshot| snapshot == self.hit_snapshot)
    }

    fn store_unchanged(&self) -> bool {
        snapshot_store(&self.store, self.label_to_id.values())
            .is_ok_and(|snapshot| snapshot == self.store_snapshot)
    }
}

#[derive(Debug, Clone, Copy)]
enum PolicySpec {
    RetrievalBaseline,
    ConfidenceOnly,
    RecencyOnly,
    FailureOnly,
    SimpleCombined,
    MarginGuardCognitive,
}

impl PolicySpec {
    const fn all() -> [Self; 6] {
        [
            Self::RetrievalBaseline,
            Self::ConfidenceOnly,
            Self::RecencyOnly,
            Self::FailureOnly,
            Self::SimpleCombined,
            Self::MarginGuardCognitive,
        ]
    }

    const fn name(self) -> &'static str {
        match self {
            Self::RetrievalBaseline => "retrieval_baseline",
            Self::ConfidenceOnly => "confidence_only_margin_guarded",
            Self::RecencyOnly => "recency_only_margin_guarded",
            Self::FailureOnly => "failure_only_margin_guarded",
            Self::SimpleCombined => "simple_combined_margin_guarded",
            Self::MarginGuardCognitive => "margin_guard_cognitive",
        }
    }

    const fn family(self) -> &'static str {
        match self {
            Self::RetrievalBaseline => "retrieval",
            Self::ConfidenceOnly => "simple_confidence",
            Self::RecencyOnly => "simple_recency",
            Self::FailureOnly => "simple_failure",
            Self::SimpleCombined => "simple_combined",
            Self::MarginGuardCognitive => "cognitive",
        }
    }

    const fn alpha(self) -> Option<f64> {
        if matches!(self, Self::RetrievalBaseline) {
            None
        } else {
            Some(POLICY_ALPHA)
        }
    }

    const fn threshold(self) -> Option<f64> {
        if matches!(self, Self::RetrievalBaseline) {
            None
        } else {
            Some(MARGIN_THRESHOLD)
        }
    }
}

#[derive(Debug, Clone, Copy)]
enum AblationSpec {
    Full,
    WithoutTemporal,
    WithoutFailure,
    WithoutReliability,
    WithoutPreference,
    WithoutContext,
}

impl AblationSpec {
    const fn all() -> [Self; 6] {
        [
            Self::Full,
            Self::WithoutTemporal,
            Self::WithoutFailure,
            Self::WithoutReliability,
            Self::WithoutPreference,
            Self::WithoutContext,
        ]
    }

    const fn name(self) -> &'static str {
        match self {
            Self::Full => "full_cognitive",
            Self::WithoutTemporal => "without_temporal",
            Self::WithoutFailure => "without_failure",
            Self::WithoutReliability => "without_reliability",
            Self::WithoutPreference => "without_preference",
            Self::WithoutContext => "without_context",
        }
    }

    const fn excluded(self) -> Option<CognitiveFactorType> {
        match self {
            Self::Full => None,
            Self::WithoutTemporal => Some(CognitiveFactorType::TemporalConfidence),
            Self::WithoutFailure => Some(CognitiveFactorType::FailureEvidence),
            Self::WithoutReliability => Some(CognitiveFactorType::Reliability),
            Self::WithoutPreference => Some(CognitiveFactorType::PreferenceAlignment),
            Self::WithoutContext => Some(CognitiveFactorType::ContextAlignment),
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
struct RankedCandidate {
    candidate_id: String,
    baseline_rank: usize,
    baseline_score: f64,
    baseline_normalized: f64,
    signal: f64,
    policy_score: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase6CognitiveBaselineComparisonReport {
    pub schema_version: u32,
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub generated_at: String,
    pub protocol: CognitiveBaselineComparisonProtocol,
    pub dataset: CognitiveBaselineDatasetSummary,
    pub policies: Vec<PolicyResult>,
    pub factor_ablations: Vec<AblationResult>,
    pub decision: CognitiveBaselineDecision,
    pub guards: CognitiveBaselineComparisonGuards,
    pub pass: bool,
    pub status: String,
    pub conclusion: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveBaselineComparisonProtocol {
    pub dataset_path: String,
    pub dataset_sha256: String,
    pub retrieval_mode: String,
    pub candidate_limit: usize,
    pub policy_alpha: f64,
    pub margin_threshold: f64,
    pub simple_combined_formula: String,
    pub cognitive_signal: String,
    pub ablation_method: String,
    pub quality_gate_semantics: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveBaselineDatasetSummary {
    pub scenarios: usize,
    pub memories: usize,
    pub categories: usize,
    pub intervention_required: usize,
    pub no_intervention: usize,
    pub split_counts: BTreeMap<String, usize>,
    pub category_counts: BTreeMap<String, usize>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PolicyResult {
    pub policy: String,
    pub family: String,
    pub alpha: Option<f64>,
    pub margin_threshold: Option<f64>,
    pub candidate_pool_preserved: bool,
    pub runtime_applied: bool,
    pub metrics: ComparisonMetrics,
    pub scenarios: Vec<ScenarioPolicyReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct AblationResult {
    pub ablation: String,
    pub excluded_factor: Option<String>,
    pub alpha: f64,
    pub margin_threshold: f64,
    pub candidate_pool_preserved: bool,
    pub runtime_applied: bool,
    pub metrics: ComparisonMetrics,
}

#[derive(Debug, Clone, Serialize)]
pub struct ComparisonMetrics {
    pub scenarios: usize,
    pub expected_candidate_retrieval_rate: f64,
    pub recall_at_1: f64,
    pub recall_at_3: f64,
    pub mrr_at_5: f64,
    pub ndcg_at_5: f64,
    pub intervention_precision: f64,
    pub intervention_recall: f64,
    pub unnecessary_intervention_rate: f64,
    pub catastrophic_regression_rate: f64,
    pub top1_change_rate: f64,
    pub competition_eligible_rate: f64,
    pub determinism: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScenarioPolicyReport {
    pub id: String,
    pub split: String,
    pub category: String,
    pub policy: String,
    pub intervention_required: bool,
    pub expected_top: String,
    pub expected_retrieved: bool,
    pub baseline_ranking: Vec<String>,
    pub policy_ranking: Vec<String>,
    pub recall_at_1: f64,
    pub recall_at_3: f64,
    pub mrr_at_5: f64,
    pub ndcg_at_5: f64,
    pub baseline_top_expected: bool,
    pub policy_top_expected: bool,
    pub top1_changed: bool,
    pub successful_intervention: bool,
    pub unnecessary_intervention: bool,
    pub catastrophic_regression: bool,
    pub competition_eligible: bool,
    pub deterministic: bool,
    pub candidate_pool_preserved: bool,
    pub runtime_applied: bool,
    pub retrieval_profile: RecallProfile,
    pub candidates: Vec<CandidatePolicyReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CandidatePolicyReport {
    pub label: String,
    pub baseline_rank: usize,
    pub policy_rank: usize,
    pub baseline_score: f64,
    pub baseline_normalized: f64,
    pub policy_signal: f64,
    pub policy_score: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveBaselineDecision {
    pub best_simple_baseline: String,
    pub best_simple_mrr_at_5: f64,
    pub best_simple_recall_at_1: f64,
    pub cognitive_mrr_at_5: f64,
    pub cognitive_recall_at_1: f64,
    pub cognitive_gain_vs_best_simple_baseline: f64,
    pub cognitive_recall_at_1_gain_vs_best_simple_baseline: f64,
    pub outcome: String,
    pub cognitive_exceeds_best_simple: bool,
    pub cognitive_matches_best_simple: bool,
    pub independent_value_supported: bool,
    pub attribution_resolved: bool,
    pub zero_intervention_authority: bool,
    pub metadata_aggregation_only: bool,
    pub factor_deltas: Vec<FactorContribution>,
    pub contributing_factors: Vec<String>,
    pub hermes_shadow_integration_recommended: bool,
    pub hermes_recommendation: String,
    pub runtime_authorization: bool,
    pub production_claim_authorized: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct FactorContribution {
    pub factor: String,
    pub mrr_at_5_delta_when_removed: f64,
    pub recall_at_1_delta_when_removed: f64,
    pub independently_contributing: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveBaselineComparisonGuards {
    pub eval_only: bool,
    pub shadow_only: bool,
    pub baseline_authoritative: bool,
    pub real_recall_engine_used: bool,
    pub artificial_baseline_scores_used: bool,
    pub recall_engine_modified: bool,
    pub candidate_generation_modified: bool,
    pub retrieval_scores_mutated: bool,
    pub candidate_pool_changed: bool,
    pub policy_memory_written: bool,
    pub memory_mutated: bool,
    pub memory_schema_changed: bool,
    pub runtime_applied: bool,
    pub runtime_booster_registered: bool,
    pub runtime_authorization: bool,
    pub production_claim_authorized: bool,
}
