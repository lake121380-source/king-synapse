use anyhow::{ensure, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
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

const SCHEMA_VERSION: u32 = 1;
const EVALUATION_VERSION: &str = "phase5.4-independent-end-to-end-cognitive-validation-v1";
const RETRIEVAL_MODE: &str = "real_recall_engine_fts_entity_no_vectors_no_reranker";
const DEFAULT_K: usize = 5;
const POLICY_ALPHA: f64 = 0.20;
const MARGIN_THRESHOLD: f64 = 0.08;
const EPSILON: f64 = 1e-12;
const MIN_SCENARIOS: usize = 18;

pub struct Phase5EndToEndCognitiveEvaluator;

impl Phase5EndToEndCognitiveEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase5EndToEndReport> {
        evaluate(tag.into())
    }
}

pub fn load_phase5_end_to_end_workload() -> Result<Vec<EndToEndScenarioSpec>> {
    let path = dataset_path();
    let source = fs::read_to_string(&path)
        .with_context(|| format!("reading Phase 5.4 workload {}", path.display()))?;
    let dataset: EndToEndDatasetFile = toml::from_str(&source)
        .with_context(|| format!("parsing Phase 5.4 workload {}", path.display()))?;
    ensure!(
        dataset.schema_version == SCHEMA_VERSION,
        "unsupported Phase 5.4 workload schema"
    );
    validate_scenarios(&dataset.scenario)?;
    Ok(dataset.scenario)
}

fn evaluate(tag: String) -> Result<Phase5EndToEndReport> {
    let specs = load_phase5_end_to_end_workload()?;
    ensure!(
        specs.len() >= MIN_SCENARIOS,
        "Phase 5.4 workload needs at least {MIN_SCENARIOS} scenarios"
    );

    let mut fixtures = Vec::with_capacity(specs.len());
    for spec in specs {
        fixtures.push(build_fixture(spec)?);
    }

    let policies = policy_specs()
        .into_iter()
        .map(|policy| evaluate_policy(policy, &fixtures))
        .collect::<Result<Vec<_>>>()?;
    let decision = build_decision(&policies)?;

    let all_hits_unchanged = fixtures.iter().all(EndToEndFixture::hits_unchanged);
    let all_stores_unchanged = fixtures.iter().all(EndToEndFixture::store_unchanged);
    let all_candidate_pools_preserved = policies
        .iter()
        .all(|policy| policy.candidate_pool_preserved);
    let all_deterministic = policies
        .iter()
        .all(|policy| (policy.metrics.determinism - 1.0).abs() <= EPSILON);

    let expected_candidate_retrieval_rate = safe_div(
        fixtures
            .iter()
            .filter(|fixture| fixture.expected_retrieved())
            .count() as f64,
        fixtures.len() as f64,
    );

    let guards = EndToEndSafetyGuards {
        eval_only: true,
        shadow_only: true,
        baseline_authoritative: true,
        real_recall_engine_used: true,
        artificial_baseline_scores_used: false,
        vectors_enabled: false,
        reranker_enabled: false,
        runtime_applied: false,
        fixture_setup_writes: true,
        policy_memory_written: false,
        memory_mutated: !all_stores_unchanged,
        ranking_mutated: !all_hits_unchanged,
        scores_mutated: !all_hits_unchanged,
        activation_changed: !all_hits_unchanged,
        candidate_pool_changed: !all_candidate_pools_preserved,
        recall_engine_integrated: false,
        runtime_booster_registered: false,
        production_claim_authorized: false,
        runtime_authorization: false,
    };

    let pass = fixtures.len() >= MIN_SCENARIOS
        && (expected_candidate_retrieval_rate - 1.0).abs() <= EPSILON
        && all_deterministic
        && !guards.artificial_baseline_scores_used
        && !guards.runtime_applied
        && !guards.policy_memory_written
        && !guards.memory_mutated
        && !guards.ranking_mutated
        && !guards.scores_mutated
        && !guards.activation_changed
        && !guards.candidate_pool_changed
        && !guards.recall_engine_integrated
        && !guards.runtime_booster_registered
        && !guards.production_claim_authorized
        && !guards.runtime_authorization;

    Ok(Phase5EndToEndReport {
        schema_version: SCHEMA_VERSION,
        tag,
        phase: "Phase 5.4 Independent End-to-End Cognitive Validation".to_string(),
        mode: "offline_real_recall_shadow_reranking".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        protocol: EndToEndProtocol {
            retrieval_mode: RETRIEVAL_MODE.to_string(),
            candidate_limit: DEFAULT_K,
            policy_alpha: POLICY_ALPHA,
            margin_threshold: MARGIN_THRESHOLD,
            baseline_score_source: "RecallEngine RecallHit.score only".to_string(),
            cognitive_source: "CognitiveTraceEvaluator over real RecallHit[]".to_string(),
            control_policy: "All non-baseline signals share the same locked margin guard and weighted-fusion authority envelope.".to_string(),
            external_dataset_status: "DMR and LongMemEval raw fixtures are not vendored; a deterministic Agent workload keeps lifecycle metadata and ground truth auditable while retrieval scores come exclusively from RecallEngine.".to_string(),
        },
        dataset: EndToEndDatasetSummary {
            path: relative_dataset_path(),
            sha256: hash_file(&dataset_path())?,
            scenarios: fixtures.len(),
            memories: fixtures.iter().map(|fixture| fixture.spec.memory.len()).sum(),
            retrieved_candidates: fixtures.iter().map(|fixture| fixture.hits.len()).sum(),
            categories: category_counts(&fixtures),
            intervention_required_scenarios: fixtures.iter().filter(|fixture| fixture.spec.intervention_required).count(),
            no_intervention_scenarios: fixtures.iter().filter(|fixture| !fixture.spec.intervention_required).count(),
            expected_candidate_retrieval_rate,
        },
        policies,
        decision,
        guards,
        pass,
        status: if pass { "PASS" } else { "FAIL" }.to_string(),
        conclusion: "This gate validates an end-to-end shadow experiment over real RecallEngine output. PASS means protocol and safety integrity, not runtime authorization or production improvement.".to_string(),
    })
}

fn dataset_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("datasets")
        .join("cognitive_end_to_end")
        .join("agent_workload.toml")
}

fn relative_dataset_path() -> String {
    "crates/eval/datasets/cognitive_end_to_end/agent_workload.toml".to_string()
}

fn hash_file(path: &Path) -> Result<String> {
    let mut hasher = Sha256::new();
    hasher.update(fs::read(path)?);
    Ok(format!("{:x}", hasher.finalize()))
}

fn validate_scenarios(scenarios: &[EndToEndScenarioSpec]) -> Result<()> {
    let mut ids = BTreeSet::new();
    for scenario in scenarios {
        ensure!(
            ids.insert(scenario.id.clone()),
            "duplicate scenario id {}",
            scenario.id
        );
        ensure!(
            !scenario.query.trim().is_empty(),
            "empty query in {}",
            scenario.id
        );
        ensure!(
            scenario.memory.len() >= DEFAULT_K,
            "scenario {} needs at least {DEFAULT_K} memories",
            scenario.id
        );
        ensure!(
            scenario
                .memory
                .iter()
                .any(|memory| memory.label == scenario.expected_top),
            "scenario {} expected_top is missing",
            scenario.id
        );
        ensure!(
            scenario
                .memory
                .iter()
                .find(|memory| memory.label == scenario.expected_top)
                .is_some_and(|memory| memory.relevant),
            "scenario {} expected_top must be relevant",
            scenario.id
        );
        let mut labels = BTreeSet::new();
        for memory in &scenario.memory {
            ensure!(
                labels.insert(memory.label.clone()),
                "duplicate label in {}",
                scenario.id
            );
            ensure!((0.0..=1.0).contains(&memory.confidence));
            ensure!((0.0..=1.0).contains(&memory.importance));
            MemoryKind::from_str(&memory.kind)
                .with_context(|| format!("invalid memory kind in {}", scenario.id))?;
        }
    }
    Ok(())
}

fn build_fixture(spec: EndToEndScenarioSpec) -> Result<EndToEndFixture> {
    let mut store = Store::open_in_memory()?;
    let mut label_to_id = BTreeMap::new();
    let mut id_to_memory = HashMap::new();
    let mut recently_accessed = Vec::new();
    let mut access_timestamp = 0_i64;

    for memory in &spec.memory {
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
    let profiled = RecallEngine::new(&mut store)
        .with_access_recording(false)
        .recall_profiled(&query)?;
    let hits = profiled.hits;
    ensure!(
        !hits.is_empty(),
        "scenario {} returned no RecallHit",
        spec.id
    );
    let hit_snapshot = serde_json::to_string(&hits)?;
    let post_recall_store_snapshot = snapshot_store(&store, label_to_id.values())?;
    ensure!(
        store_snapshot == post_recall_store_snapshot,
        "scenario {} RecallEngine mutated Store with access recording disabled",
        spec.id
    );

    let trace = CognitiveTraceEvaluator::evaluate(&spec.query, &hits);
    let config = CognitiveBoosterConfig::shadow(MAX_COGNITIVE_BOOSTER_BONUS, hits.len())?;
    let booster = DeterministicCognitiveBoosterV0;
    let output = booster.boost(CognitiveBoosterInput::new(&hits, &trace, &config));
    ensure!(
        output.bounded(),
        "scenario {} produced unbounded bonus",
        spec.id
    );
    ensure!(!output.runtime_applied());
    ensure!(!output.memory_mutated());
    let cognitive_signal = output
        .adjusted_scores()
        .iter()
        .map(|candidate| {
            (
                candidate.candidate_id.clone(),
                normalize(candidate.bounded_bonus / MAX_COGNITIVE_BOOSTER_BONUS),
            )
        })
        .collect::<HashMap<_, _>>();

    Ok(EndToEndFixture {
        spec,
        store,
        hits,
        profile: profiled.profile,
        trace,
        label_to_id,
        id_to_memory,
        cognitive_signal,
        hit_snapshot,
        store_snapshot,
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

fn policy_specs() -> [EndToEndPolicySpec; 5] {
    [
        EndToEndPolicySpec::RetrievalBaseline,
        EndToEndPolicySpec::ConfidenceBoost,
        EndToEndPolicySpec::RecencyBoost,
        EndToEndPolicySpec::FailureBoost,
        EndToEndPolicySpec::MarginGuardCognitive,
    ]
}

fn evaluate_policy(
    policy: EndToEndPolicySpec,
    fixtures: &[EndToEndFixture],
) -> Result<EndToEndPolicyResult> {
    let mut scenarios = Vec::with_capacity(fixtures.len());
    for fixture in fixtures {
        let first = apply_policy(policy, fixture);
        let replay = apply_policy(policy, fixture);
        let deterministic = first == replay;
        ensure!(
            deterministic,
            "policy {} is not deterministic",
            policy.name()
        );
        scenarios.push(build_scenario_report(policy, fixture, first, deterministic));
    }
    let metrics = aggregate_metrics(&scenarios);
    Ok(EndToEndPolicyResult {
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

fn apply_policy(
    policy: EndToEndPolicySpec,
    fixture: &EndToEndFixture,
) -> Vec<EndToEndRankedCandidate> {
    let max_baseline = fixture
        .hits
        .iter()
        .map(|hit| f64::from(hit.score))
        .fold(EPSILON, f64::max);
    let failure_by_id = factor_signal(&fixture.trace, CognitiveFactorType::FailureEvidence, 0.15);
    let mut candidates = fixture
        .hits
        .iter()
        .enumerate()
        .map(|(index, hit)| {
            let baseline_score = f64::from(hit.score);
            let baseline_normalized = normalize(baseline_score / max_baseline);
            let signal = match policy {
                EndToEndPolicySpec::RetrievalBaseline => baseline_normalized,
                EndToEndPolicySpec::ConfidenceBoost => normalize(f64::from(hit.memory.confidence)),
                EndToEndPolicySpec::RecencyBoost => {
                    if hit.memory.last_accessed_at.is_some() {
                        1.0
                    } else {
                        0.0
                    }
                }
                EndToEndPolicySpec::FailureBoost => {
                    failure_by_id.get(&hit.memory.id).copied().unwrap_or(0.0)
                }
                EndToEndPolicySpec::MarginGuardCognitive => fixture
                    .cognitive_signal
                    .get(&hit.memory.id)
                    .copied()
                    .unwrap_or(0.0),
            };
            let policy_score = if matches!(policy, EndToEndPolicySpec::RetrievalBaseline) {
                baseline_normalized
            } else {
                baseline_normalized * (1.0 - POLICY_ALPHA) + signal * POLICY_ALPHA
            };
            EndToEndRankedCandidate {
                candidate_id: hit.memory.id.clone(),
                baseline_rank: index + 1,
                baseline_score,
                baseline_normalized,
                signal,
                policy_score,
            }
        })
        .collect::<Vec<_>>();

    if matches!(policy, EndToEndPolicySpec::RetrievalBaseline) {
        return candidates;
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
    candidates
}

fn factor_signal(
    trace: &CognitiveCompetitionTrace,
    factor_type: CognitiveFactorType,
    max_contribution: f64,
) -> HashMap<String, f64> {
    trace
        .factors
        .iter()
        .filter(|factor| factor.factor_type == factor_type)
        .map(|factor| {
            (
                factor.candidate_id.clone(),
                normalize(factor.contribution / max_contribution),
            )
        })
        .collect()
}

fn compare_ranked_candidate(
    left: &EndToEndRankedCandidate,
    right: &EndToEndRankedCandidate,
) -> Ordering {
    right
        .policy_score
        .partial_cmp(&left.policy_score)
        .unwrap_or(Ordering::Equal)
        .then_with(|| left.baseline_rank.cmp(&right.baseline_rank))
}

fn build_scenario_report(
    policy: EndToEndPolicySpec,
    fixture: &EndToEndFixture,
    ranking: Vec<EndToEndRankedCandidate>,
    deterministic: bool,
) -> EndToEndScenarioReport {
    let baseline_ids = fixture
        .hits
        .iter()
        .map(|hit| hit.memory.id.clone())
        .collect::<Vec<_>>();
    let policy_ids = ranking
        .iter()
        .map(|candidate| candidate.candidate_id.clone())
        .collect::<Vec<_>>();
    let relevant_ids = fixture
        .spec
        .memory
        .iter()
        .filter(|memory| memory.relevant)
        .filter_map(|memory| fixture.label_to_id.get(&memory.label).cloned())
        .collect::<BTreeSet<_>>();
    let expected_id = fixture
        .label_to_id
        .get(&fixture.spec.expected_top)
        .expect("validated expected label");
    let baseline_top = baseline_ids.first();
    let policy_top = policy_ids.first();
    let baseline_top_relevant = baseline_top.is_some_and(|id| relevant_ids.contains(id));
    let policy_top_relevant = policy_top.is_some_and(|id| relevant_ids.contains(id));
    let baseline_top_expected = baseline_top == Some(expected_id);
    let policy_top_expected = policy_top == Some(expected_id);
    let top1_changed = baseline_top != policy_top;
    let successful_intervention =
        fixture.spec.intervention_required && top1_changed && policy_top_expected;
    let unnecessary_intervention = !fixture.spec.intervention_required && top1_changed;
    let top1_regression = baseline_top_relevant && !policy_top_relevant;
    let catastrophic_regression = baseline_top_expected && !policy_top_expected;

    let candidates = ranking
        .iter()
        .enumerate()
        .map(|(policy_index, candidate)| {
            let hit = fixture
                .hits
                .iter()
                .find(|hit| hit.memory.id == candidate.candidate_id)
                .expect("ranked candidate must be a RecallHit");
            EndToEndCandidateReport {
                label: fixture.label_for_id(&candidate.candidate_id).to_string(),
                candidate_id: candidate.candidate_id.clone(),
                relevant: relevant_ids.contains(&candidate.candidate_id),
                kind: hit.memory.kind.to_string(),
                confidence: f64::from(hit.memory.confidence),
                importance: f64::from(hit.memory.importance),
                recently_accessed: hit.memory.last_accessed_at.is_some(),
                baseline_rank: candidate.baseline_rank,
                policy_rank: policy_index + 1,
                position_delta: candidate.baseline_rank as isize - (policy_index + 1) as isize,
                baseline_score: candidate.baseline_score,
                baseline_normalized: candidate.baseline_normalized,
                policy_signal: candidate.signal,
                policy_score: candidate.policy_score,
                sources: hit.sources.iter().map(ToString::to_string).collect(),
            }
        })
        .collect::<Vec<_>>();

    EndToEndScenarioReport {
        id: fixture.spec.id.clone(),
        category: fixture.spec.category.clone(),
        query: fixture.spec.query.clone(),
        policy: policy.name().to_string(),
        intervention_required: fixture.spec.intervention_required,
        expected_top: fixture.spec.expected_top.clone(),
        expected_retrieved: baseline_ids.iter().any(|id| id == expected_id),
        baseline_ranking: baseline_ids
            .iter()
            .map(|id| fixture.label_for_id(id).to_string())
            .collect(),
        policy_ranking: policy_ids
            .iter()
            .map(|id| fixture.label_for_id(id).to_string())
            .collect(),
        baseline_recall_at_1: recall_at_k(&baseline_ids, &relevant_ids, 1),
        baseline_recall_at_3: recall_at_k(&baseline_ids, &relevant_ids, 3),
        baseline_recall_at_5: recall_at_k(&baseline_ids, &relevant_ids, 5),
        policy_recall_at_1: recall_at_k(&policy_ids, &relevant_ids, 1),
        policy_recall_at_3: recall_at_k(&policy_ids, &relevant_ids, 3),
        policy_recall_at_5: recall_at_k(&policy_ids, &relevant_ids, 5),
        baseline_mrr_at_5: reciprocal_rank_at_k(&baseline_ids, &relevant_ids, 5),
        policy_mrr_at_5: reciprocal_rank_at_k(&policy_ids, &relevant_ids, 5),
        baseline_ndcg_at_5: ndcg_at_k(&baseline_ids, &relevant_ids, 5),
        policy_ndcg_at_5: ndcg_at_k(&policy_ids, &relevant_ids, 5),
        baseline_top_relevant,
        policy_top_relevant,
        baseline_top_expected,
        policy_top_expected,
        top1_changed,
        successful_intervention,
        unnecessary_intervention,
        top1_regression,
        catastrophic_regression,
        silent_correctness: baseline_top_relevant && baseline_top == policy_top,
        deterministic,
        candidate_pool_preserved: same_pool(&baseline_ids, &policy_ids),
        runtime_applied: false,
        retrieval_profile: fixture.profile.clone(),
        candidates,
    }
}

fn aggregate_metrics(scenarios: &[EndToEndScenarioReport]) -> EndToEndMetrics {
    let count = scenarios.len() as f64;
    let interventions = scenarios
        .iter()
        .filter(|scenario| scenario.top1_changed)
        .count();
    let successes = scenarios
        .iter()
        .filter(|scenario| scenario.successful_intervention)
        .count();
    let required = scenarios
        .iter()
        .filter(|scenario| scenario.intervention_required)
        .count();
    let required_correct = scenarios
        .iter()
        .filter(|scenario| scenario.intervention_required && scenario.policy_top_expected)
        .count();
    let no_intervention = scenarios.len() - required;
    let unnecessary = scenarios
        .iter()
        .filter(|scenario| scenario.unnecessary_intervention)
        .count();
    let baseline_correct = scenarios
        .iter()
        .filter(|scenario| scenario.baseline_top_relevant)
        .count();
    let regressions = scenarios
        .iter()
        .filter(|scenario| scenario.top1_regression)
        .count();
    let catastrophic = scenarios
        .iter()
        .filter(|scenario| scenario.catastrophic_regression)
        .count();
    let silent = scenarios
        .iter()
        .filter(|scenario| scenario.silent_correctness)
        .count();
    let mut latencies = scenarios
        .iter()
        .map(|scenario| scenario.retrieval_profile.total_ms)
        .collect::<Vec<_>>();
    latencies.sort_by(|left, right| left.partial_cmp(right).unwrap_or(Ordering::Equal));

    EndToEndMetrics {
        scenarios: scenarios.len(),
        expected_candidate_retrieval_rate: mean(scenarios, |scenario| {
            if scenario.expected_retrieved {
                1.0
            } else {
                0.0
            }
        }),
        recall_at_1: mean(scenarios, |scenario| scenario.policy_recall_at_1),
        recall_at_3: mean(scenarios, |scenario| scenario.policy_recall_at_3),
        recall_at_5: mean(scenarios, |scenario| scenario.policy_recall_at_5),
        mrr_at_5: mean(scenarios, |scenario| scenario.policy_mrr_at_5),
        ndcg_at_5: mean(scenarios, |scenario| scenario.policy_ndcg_at_5),
        baseline_recall_at_1: mean(scenarios, |scenario| scenario.baseline_recall_at_1),
        baseline_recall_at_3: mean(scenarios, |scenario| scenario.baseline_recall_at_3),
        baseline_recall_at_5: mean(scenarios, |scenario| scenario.baseline_recall_at_5),
        baseline_mrr_at_5: mean(scenarios, |scenario| scenario.baseline_mrr_at_5),
        baseline_ndcg_at_5: mean(scenarios, |scenario| scenario.baseline_ndcg_at_5),
        recall_at_1_delta: mean(scenarios, |scenario| {
            scenario.policy_recall_at_1 - scenario.baseline_recall_at_1
        }),
        mrr_at_5_delta: mean(scenarios, |scenario| {
            scenario.policy_mrr_at_5 - scenario.baseline_mrr_at_5
        }),
        ndcg_at_5_delta: mean(scenarios, |scenario| {
            scenario.policy_ndcg_at_5 - scenario.baseline_ndcg_at_5
        }),
        cognitive_intervention_rate: safe_div(interventions as f64, count),
        successful_intervention_rate: safe_div(successes as f64, interventions as f64),
        intervention_recall: safe_div(required_correct as f64, required as f64),
        unnecessary_intervention_rate: safe_div(unnecessary as f64, no_intervention as f64),
        top1_regression_rate: safe_div(regressions as f64, baseline_correct as f64),
        catastrophic_regression_rate: safe_div(catastrophic as f64, baseline_correct as f64),
        silent_correctness_rate: safe_div(silent as f64, baseline_correct as f64),
        determinism: mean(
            scenarios,
            |scenario| if scenario.deterministic { 1.0 } else { 0.0 },
        ),
        retrieval_latency_p50_ms: percentile(&latencies, 0.50),
        retrieval_latency_p95_ms: percentile(&latencies, 0.95),
    }
}

fn mean(
    scenarios: &[EndToEndScenarioReport],
    value: impl Fn(&EndToEndScenarioReport) -> f64,
) -> f64 {
    safe_div(scenarios.iter().map(value).sum(), scenarios.len() as f64)
}

fn recall_at_k(ranking: &[String], relevant: &BTreeSet<String>, k: usize) -> f64 {
    if relevant.is_empty() {
        return 0.0;
    }
    let found = ranking
        .iter()
        .take(k)
        .filter(|candidate| relevant.contains(*candidate))
        .count();
    safe_div(found as f64, relevant.len() as f64)
}

fn reciprocal_rank_at_k(ranking: &[String], relevant: &BTreeSet<String>, k: usize) -> f64 {
    ranking
        .iter()
        .take(k)
        .position(|candidate| relevant.contains(candidate))
        .map(|index| 1.0 / (index + 1) as f64)
        .unwrap_or(0.0)
}

fn ndcg_at_k(ranking: &[String], relevant: &BTreeSet<String>, k: usize) -> f64 {
    if relevant.is_empty() {
        return 0.0;
    }
    let dcg = ranking
        .iter()
        .take(k)
        .enumerate()
        .filter(|(_, candidate)| relevant.contains(*candidate))
        .map(|(index, _)| 1.0 / ((index + 2) as f64).log2())
        .sum::<f64>();
    let ideal = (0..relevant.len().min(k))
        .map(|index| 1.0 / ((index + 2) as f64).log2())
        .sum::<f64>();
    safe_div(dcg, ideal)
}

fn percentile(sorted: &[f64], percentile: f64) -> f64 {
    if sorted.is_empty() {
        return 0.0;
    }
    let index = ((sorted.len() - 1) as f64 * percentile).ceil() as usize;
    sorted[index.min(sorted.len() - 1)]
}

fn same_pool(left: &[String], right: &[String]) -> bool {
    let mut left = left.to_vec();
    let mut right = right.to_vec();
    left.sort();
    right.sort();
    left == right
}

fn normalize(value: f64) -> f64 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        0.0
    }
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator <= EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

fn category_counts(fixtures: &[EndToEndFixture]) -> BTreeMap<String, usize> {
    let mut counts = BTreeMap::new();
    for fixture in fixtures {
        *counts.entry(fixture.spec.category.clone()).or_default() += 1;
    }
    counts
}

fn build_decision(policies: &[EndToEndPolicyResult]) -> Result<EndToEndDecision> {
    let baseline = find_policy(policies, "retrieval_baseline")?;
    let confidence = find_policy(policies, "confidence_boost")?;
    let recency = find_policy(policies, "recency_boost")?;
    let failure = find_policy(policies, "failure_boost")?;
    let cognitive = find_policy(policies, "margin_guard_cognitive")?;
    let beats_baseline = cognitive.metrics.mrr_at_5 > baseline.metrics.mrr_at_5 + EPSILON;
    let beats_confidence = cognitive.metrics.mrr_at_5 > confidence.metrics.mrr_at_5 + EPSILON;
    let beats_recency = cognitive.metrics.mrr_at_5 > recency.metrics.mrr_at_5 + EPSILON;
    let beats_failure = cognitive.metrics.mrr_at_5 > failure.metrics.mrr_at_5 + EPSILON;
    let best_simple_control_mrr_at_5 = confidence
        .metrics
        .mrr_at_5
        .max(recency.metrics.mrr_at_5)
        .max(failure.metrics.mrr_at_5);
    let cognitive_delta_vs_best_simple_control =
        cognitive.metrics.mrr_at_5 - best_simple_control_mrr_at_5;
    let cognitive_matches_best_simple_control =
        cognitive_delta_vs_best_simple_control.abs() <= EPSILON;
    let safety_preserved = cognitive.metrics.top1_regression_rate <= EPSILON
        && cognitive.metrics.catastrophic_regression_rate <= EPSILON;
    Ok(EndToEndDecision {
        baseline_mrr_at_5: baseline.metrics.mrr_at_5,
        confidence_mrr_at_5: confidence.metrics.mrr_at_5,
        recency_mrr_at_5: recency.metrics.mrr_at_5,
        failure_mrr_at_5: failure.metrics.mrr_at_5,
        cognitive_mrr_at_5: cognitive.metrics.mrr_at_5,
        best_simple_control_mrr_at_5,
        cognitive_delta_vs_best_simple_control,
        cognitive_matches_best_simple_control,
        cognitive_beats_baseline: beats_baseline,
        cognitive_beats_confidence: beats_confidence,
        cognitive_beats_recency: beats_recency,
        cognitive_beats_failure: beats_failure,
        safety_preserved,
        independent_end_to_end_value_supported: beats_baseline
            && beats_confidence
            && beats_recency
            && beats_failure
            && safety_preserved,
        runtime_authorization: false,
        production_claim_authorized: false,
    })
}

fn find_policy<'a>(
    policies: &'a [EndToEndPolicyResult],
    family: &str,
) -> Result<&'a EndToEndPolicyResult> {
    policies
        .iter()
        .find(|policy| policy.family == family)
        .with_context(|| format!("missing policy {family}"))
}

#[derive(Debug, Clone, Deserialize)]
struct EndToEndDatasetFile {
    schema_version: u32,
    scenario: Vec<EndToEndScenarioSpec>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct EndToEndScenarioSpec {
    pub id: String,
    pub category: String,
    pub query: String,
    pub expected_top: String,
    pub intervention_required: bool,
    pub memory: Vec<EndToEndMemorySpec>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct EndToEndMemorySpec {
    pub label: String,
    pub content: String,
    pub kind: String,
    pub confidence: f64,
    pub importance: f64,
    #[serde(default)]
    pub recently_accessed: bool,
    pub relevant: bool,
}

struct EndToEndFixture {
    spec: EndToEndScenarioSpec,
    store: Store,
    hits: Vec<RecallHit>,
    profile: RecallProfile,
    trace: CognitiveCompetitionTrace,
    label_to_id: BTreeMap<String, String>,
    id_to_memory: HashMap<String, EndToEndMemorySpec>,
    cognitive_signal: HashMap<String, f64>,
    hit_snapshot: String,
    store_snapshot: String,
}

impl EndToEndFixture {
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
enum EndToEndPolicySpec {
    RetrievalBaseline,
    ConfidenceBoost,
    RecencyBoost,
    FailureBoost,
    MarginGuardCognitive,
}

impl EndToEndPolicySpec {
    fn name(self) -> &'static str {
        match self {
            Self::RetrievalBaseline => "retrieval_baseline",
            Self::ConfidenceBoost => "confidence_boost_margin_guarded",
            Self::RecencyBoost => "recency_boost_margin_guarded",
            Self::FailureBoost => "failure_boost_margin_guarded",
            Self::MarginGuardCognitive => "margin_guard_cognitive",
        }
    }

    fn family(self) -> &'static str {
        match self {
            Self::RetrievalBaseline => "retrieval_baseline",
            Self::ConfidenceBoost => "confidence_boost",
            Self::RecencyBoost => "recency_boost",
            Self::FailureBoost => "failure_boost",
            Self::MarginGuardCognitive => "margin_guard_cognitive",
        }
    }

    fn alpha(self) -> Option<f64> {
        if matches!(self, Self::RetrievalBaseline) {
            None
        } else {
            Some(POLICY_ALPHA)
        }
    }

    fn threshold(self) -> Option<f64> {
        if matches!(self, Self::RetrievalBaseline) {
            None
        } else {
            Some(MARGIN_THRESHOLD)
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
struct EndToEndRankedCandidate {
    candidate_id: String,
    baseline_rank: usize,
    baseline_score: f64,
    baseline_normalized: f64,
    signal: f64,
    policy_score: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5EndToEndReport {
    pub schema_version: u32,
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub generated_at: String,
    pub protocol: EndToEndProtocol,
    pub dataset: EndToEndDatasetSummary,
    pub policies: Vec<EndToEndPolicyResult>,
    pub decision: EndToEndDecision,
    pub guards: EndToEndSafetyGuards,
    pub pass: bool,
    pub status: String,
    pub conclusion: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct EndToEndProtocol {
    pub retrieval_mode: String,
    pub candidate_limit: usize,
    pub policy_alpha: f64,
    pub margin_threshold: f64,
    pub baseline_score_source: String,
    pub cognitive_source: String,
    pub control_policy: String,
    pub external_dataset_status: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct EndToEndDatasetSummary {
    pub path: String,
    pub sha256: String,
    pub scenarios: usize,
    pub memories: usize,
    pub retrieved_candidates: usize,
    pub categories: BTreeMap<String, usize>,
    pub intervention_required_scenarios: usize,
    pub no_intervention_scenarios: usize,
    pub expected_candidate_retrieval_rate: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct EndToEndPolicyResult {
    pub policy: String,
    pub family: String,
    pub alpha: Option<f64>,
    pub margin_threshold: Option<f64>,
    pub candidate_pool_preserved: bool,
    pub runtime_applied: bool,
    pub metrics: EndToEndMetrics,
    pub scenarios: Vec<EndToEndScenarioReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct EndToEndMetrics {
    pub scenarios: usize,
    pub expected_candidate_retrieval_rate: f64,
    pub recall_at_1: f64,
    pub recall_at_3: f64,
    pub recall_at_5: f64,
    pub mrr_at_5: f64,
    pub ndcg_at_5: f64,
    pub baseline_recall_at_1: f64,
    pub baseline_recall_at_3: f64,
    pub baseline_recall_at_5: f64,
    pub baseline_mrr_at_5: f64,
    pub baseline_ndcg_at_5: f64,
    pub recall_at_1_delta: f64,
    pub mrr_at_5_delta: f64,
    pub ndcg_at_5_delta: f64,
    pub cognitive_intervention_rate: f64,
    pub successful_intervention_rate: f64,
    pub intervention_recall: f64,
    pub unnecessary_intervention_rate: f64,
    pub top1_regression_rate: f64,
    pub catastrophic_regression_rate: f64,
    pub silent_correctness_rate: f64,
    pub determinism: f64,
    pub retrieval_latency_p50_ms: f64,
    pub retrieval_latency_p95_ms: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct EndToEndScenarioReport {
    pub id: String,
    pub category: String,
    pub query: String,
    pub policy: String,
    pub intervention_required: bool,
    pub expected_top: String,
    pub expected_retrieved: bool,
    pub baseline_ranking: Vec<String>,
    pub policy_ranking: Vec<String>,
    pub baseline_recall_at_1: f64,
    pub baseline_recall_at_3: f64,
    pub baseline_recall_at_5: f64,
    pub policy_recall_at_1: f64,
    pub policy_recall_at_3: f64,
    pub policy_recall_at_5: f64,
    pub baseline_mrr_at_5: f64,
    pub policy_mrr_at_5: f64,
    pub baseline_ndcg_at_5: f64,
    pub policy_ndcg_at_5: f64,
    pub baseline_top_relevant: bool,
    pub policy_top_relevant: bool,
    pub baseline_top_expected: bool,
    pub policy_top_expected: bool,
    pub top1_changed: bool,
    pub successful_intervention: bool,
    pub unnecessary_intervention: bool,
    pub top1_regression: bool,
    pub catastrophic_regression: bool,
    pub silent_correctness: bool,
    pub deterministic: bool,
    pub candidate_pool_preserved: bool,
    pub runtime_applied: bool,
    pub retrieval_profile: RecallProfile,
    pub candidates: Vec<EndToEndCandidateReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct EndToEndCandidateReport {
    pub label: String,
    pub candidate_id: String,
    pub relevant: bool,
    pub kind: String,
    pub confidence: f64,
    pub importance: f64,
    pub recently_accessed: bool,
    pub baseline_rank: usize,
    pub policy_rank: usize,
    pub position_delta: isize,
    pub baseline_score: f64,
    pub baseline_normalized: f64,
    pub policy_signal: f64,
    pub policy_score: f64,
    pub sources: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct EndToEndDecision {
    pub baseline_mrr_at_5: f64,
    pub confidence_mrr_at_5: f64,
    pub recency_mrr_at_5: f64,
    pub failure_mrr_at_5: f64,
    pub cognitive_mrr_at_5: f64,
    pub best_simple_control_mrr_at_5: f64,
    pub cognitive_delta_vs_best_simple_control: f64,
    pub cognitive_matches_best_simple_control: bool,
    pub cognitive_beats_baseline: bool,
    pub cognitive_beats_confidence: bool,
    pub cognitive_beats_recency: bool,
    pub cognitive_beats_failure: bool,
    pub safety_preserved: bool,
    pub independent_end_to_end_value_supported: bool,
    pub runtime_authorization: bool,
    pub production_claim_authorized: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct EndToEndSafetyGuards {
    pub eval_only: bool,
    pub shadow_only: bool,
    pub baseline_authoritative: bool,
    pub real_recall_engine_used: bool,
    pub artificial_baseline_scores_used: bool,
    pub vectors_enabled: bool,
    pub reranker_enabled: bool,
    pub runtime_applied: bool,
    pub fixture_setup_writes: bool,
    pub policy_memory_written: bool,
    pub memory_mutated: bool,
    pub ranking_mutated: bool,
    pub scores_mutated: bool,
    pub activation_changed: bool,
    pub candidate_pool_changed: bool,
    pub recall_engine_integrated: bool,
    pub runtime_booster_registered: bool,
    pub production_claim_authorized: bool,
    pub runtime_authorization: bool,
}
