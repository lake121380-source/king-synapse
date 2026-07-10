use anyhow::{ensure, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
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
    RecallEngine, RecallHit, RecallQuery, Scope, Source, Store, WriteInput,
    MAX_COGNITIVE_BOOSTER_BONUS,
};

const SCHEMA_VERSION: u32 = 1;
const EVALUATION_VERSION: &str = "phase5.3.3-cognitive-ranking-policy-study-v1";
const BASELINE_VERSION: &str = "phase5.3.2-deterministic-cognitive-booster-v0";
const METRIC_CUTOFF: usize = 3;
const MIN_SCENARIOS: usize = 30;
const MAX_SCENARIOS: usize = 50;
const WEIGHTED_ALPHAS: [f64; 3] = [0.05, 0.10, 0.20];
const MARGIN_GUARD_ALPHA: f64 = 0.20;
const MARGIN_GUARD_THRESHOLD: f64 = 0.08;
const EPSILON: f64 = 1e-12;

const REQUIRED_CATEGORIES: [&str; 6] = [
    "temporal_update",
    "failure_override",
    "reliability_conflict",
    "semantic_trap",
    "preference_evolution",
    "no_intervention",
];

pub struct Phase5CognitivePolicyEvaluator;

impl Phase5CognitivePolicyEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase5CognitivePolicyReport> {
        evaluate_policy_study(tag.into())
    }
}

pub fn load_cognitive_policy_benchmark() -> Result<Vec<CognitivePolicyScenarioSpec>> {
    load_benchmark_from(&benchmark_dir())
}

fn evaluate_policy_study(tag: String) -> Result<Phase5CognitivePolicyReport> {
    let specs = load_cognitive_policy_benchmark()?;
    ensure!(
        (MIN_SCENARIOS..=MAX_SCENARIOS).contains(&specs.len()),
        "cognitive policy benchmark must contain {MIN_SCENARIOS}-{MAX_SCENARIOS} scenarios"
    );
    ensure_required_categories(&specs)?;

    let mut fixtures = Vec::with_capacity(specs.len());
    for spec in specs {
        fixtures.push(build_fixture(spec)?);
    }

    let mut policy_reports = Vec::new();
    for policy in policy_specs() {
        policy_reports.push(evaluate_policy(&policy, &fixtures, None)?);
    }

    let selected_policy = PolicySpec::MarginGuard {
        alpha: MARGIN_GUARD_ALPHA,
        threshold: MARGIN_GUARD_THRESHOLD,
    };
    let ablations = ablation_specs()
        .into_iter()
        .map(|ablation| evaluate_ablation(&selected_policy, &fixtures, ablation))
        .collect::<Result<Vec<_>>>()?;

    let categories = category_counts(&fixtures);
    let label_mapping_stable = fixtures.iter().all(Fixture::label_mapping_is_bijective);
    let baseline_unchanged = fixtures.iter().all(Fixture::hits_unchanged);
    let store_unchanged = fixtures.iter().all(Fixture::store_unchanged);
    let all_deterministic = policy_reports
        .iter()
        .all(|policy| (policy.metrics.determinism - 1.0).abs() <= EPSILON);
    let all_bounded = policy_reports
        .iter()
        .all(|policy| (policy.metrics.bounded_rate - 1.0).abs() <= EPSILON);
    let candidate_pool_preserved = policy_reports.iter().all(|policy| {
        policy
            .scenario_reports
            .iter()
            .all(|scenario| scenario.candidate_pool_preserved)
    });

    let guards = CognitivePolicySafetyGuards {
        eval_only: true,
        shadow_only: true,
        baseline_authoritative: true,
        runtime_applied: false,
        fixture_setup_writes: true,
        policy_memory_written: false,
        memory_mutated: !store_unchanged,
        ranking_mutated: !baseline_unchanged,
        scores_mutated: !baseline_unchanged,
        activation_changed: !baseline_unchanged,
        candidate_pool_changed: !candidate_pool_preserved,
        recall_engine_integrated: false,
        production_claim_authorized: false,
    };

    let pass = (MIN_SCENARIOS..=MAX_SCENARIOS).contains(&fixtures.len())
        && REQUIRED_CATEGORIES
            .iter()
            .all(|category| categories.contains_key(*category))
        && label_mapping_stable
        && all_deterministic
        && all_bounded
        && !guards.runtime_applied
        && !guards.policy_memory_written
        && !guards.memory_mutated
        && !guards.ranking_mutated
        && !guards.scores_mutated
        && !guards.activation_changed
        && !guards.candidate_pool_changed
        && !guards.recall_engine_integrated
        && !guards.production_claim_authorized;

    Ok(Phase5CognitivePolicyReport {
        schema_version: SCHEMA_VERSION,
        tag,
        phase: "Phase 5.3.3 Cognitive Ranking Policy Study".to_string(),
        mode: "offline_shadow_policy_evaluation".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        benchmark: CognitivePolicyBenchmarkSummary {
            dataset_path: "crates/eval/datasets/cognitive_policy".to_string(),
            scenarios: fixtures.len(),
            candidates: fixtures.iter().map(|fixture| fixture.hits.len()).sum(),
            categories,
            required_categories: REQUIRED_CATEGORIES.iter().map(|value| (*value).to_string()).collect(),
            intervention_required_scenarios: fixtures.iter().filter(|fixture| fixture.spec.intervention_required).count(),
            no_intervention_scenarios: fixtures.iter().filter(|fixture| !fixture.spec.intervention_required).count(),
            label_mapping_stable,
        },
        normalization: PolicyNormalizationReport {
            baseline: "baseline_score / scenario_max_baseline_score".to_string(),
            cognitive: format!("bounded_bonus / MAX_COGNITIVE_BOOSTER_BONUS ({MAX_COGNITIVE_BOOSTER_BONUS:.2})"),
            weighted_fusion: "baseline_normalized * (1 - alpha) + cognitive_normalized * alpha".to_string(),
            margin_guard: format!("only candidates within normalized top-score margin <= {MARGIN_GUARD_THRESHOLD:.2} may be reordered; guarded band uses alpha {MARGIN_GUARD_ALPHA:.2}"),
        },
        policies: policy_reports,
        ablation_policy: selected_policy.name(),
        ablations,
        guards,
        pass,
        status: if pass { "PASS" } else { "FAIL" }.to_string(),
        conclusion: "Policy authority is evaluated offline only. Positive retrieval value and runtime authorization are not required by this safety gate.".to_string(),
    })
}

fn benchmark_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("datasets")
        .join("cognitive_policy")
}

pub(crate) fn load_benchmark_from(dir: &Path) -> Result<Vec<CognitivePolicyScenarioSpec>> {
    let mut paths = fs::read_dir(dir)
        .with_context(|| {
            format!(
                "reading cognitive policy dataset directory {}",
                dir.display()
            )
        })?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.extension().and_then(|value| value.to_str()) == Some("toml"))
        .collect::<Vec<_>>();
    paths.sort();

    let mut scenarios = Vec::new();
    let mut ids = BTreeSet::new();
    for path in paths {
        let source = fs::read_to_string(&path)
            .with_context(|| format!("reading cognitive policy dataset {}", path.display()))?;
        let file: CognitivePolicyDatasetFile = toml::from_str(&source)
            .with_context(|| format!("parsing cognitive policy dataset {}", path.display()))?;
        ensure!(
            file.schema_version == SCHEMA_VERSION,
            "unsupported schema in {}",
            path.display()
        );
        for scenario in file.scenario {
            ensure!(
                ids.insert(scenario.id.clone()),
                "duplicate scenario id {}",
                scenario.id
            );
            validate_scenario(&scenario)?;
            scenarios.push(scenario);
        }
    }
    scenarios.sort_by(|left, right| left.id.cmp(&right.id));
    Ok(scenarios)
}

fn validate_scenario(scenario: &CognitivePolicyScenarioSpec) -> Result<()> {
    ensure!(
        scenario.memory.len() >= 2,
        "scenario {} needs at least two candidates",
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
        ensure!(memory.baseline_score.is_finite() && memory.baseline_score >= 0.0);
        ensure!((0.0..=1.0).contains(&memory.confidence));
        ensure!((0.0..=1.0).contains(&memory.importance));
        MemoryKind::from_str(&memory.kind)
            .with_context(|| format!("invalid memory kind in {}", scenario.id))?;
        ensure!(
            matches!(
                memory.temporal_state.as_str(),
                "active" | "superseded" | "accessed"
            ),
            "invalid temporal_state in {}",
            scenario.id
        );
    }
    Ok(())
}

fn ensure_required_categories(specs: &[CognitivePolicyScenarioSpec]) -> Result<()> {
    let categories = specs
        .iter()
        .map(|scenario| scenario.category.as_str())
        .collect::<BTreeSet<_>>();
    for required in REQUIRED_CATEGORIES {
        ensure!(
            categories.contains(required),
            "missing required category {required}"
        );
    }
    Ok(())
}

pub(crate) fn build_fixture(spec: CognitivePolicyScenarioSpec) -> Result<Fixture> {
    let mut store = Store::open_in_memory()?;
    let mut id_to_spec = HashMap::new();
    let mut label_to_id = BTreeMap::new();

    for memory in &spec.memory {
        let stored = store.write(WriteInput {
            content: memory.content.clone(),
            kind: MemoryKind::from_str(&memory.kind)?,
            scope: Scope::User,
            source: Source::ExplicitUser,
            confidence: Some(memory.confidence as f32),
            importance: Some(memory.importance as f32),
        })?;
        label_to_id.insert(memory.label.clone(), stored.id.clone());
        id_to_spec.insert(stored.id, memory.clone());
    }

    let query = RecallQuery {
        query: spec.query.clone(),
        k: Some(spec.memory.len()),
        scope_filter: Some(Scope::User),
        kind_filter: None,
    };
    let mut hits = RecallEngine::new(&mut store)
        .with_access_recording(false)
        .recall(&query)?;
    ensure!(
        hits.len() == spec.memory.len(),
        "scenario {} retrieved {}/{} fixture memories",
        spec.id,
        hits.len(),
        spec.memory.len()
    );

    for hit in &mut hits {
        let memory_spec = id_to_spec
            .get(&hit.memory.id)
            .with_context(|| format!("unmapped recall id in {}", spec.id))?;
        hit.score = memory_spec.baseline_score as f32;
        hit.rrf_score = memory_spec.baseline_score as f32;
        match memory_spec.temporal_state.as_str() {
            "superseded" => {
                hit.memory.valid_to = Some(hit.memory.valid_from + 1);
                hit.memory.superseded_by = Some(format!("{}-successor", memory_spec.label));
            }
            "accessed" => hit.memory.last_accessed_at = Some(hit.memory.valid_from + 1),
            _ => {}
        }
    }
    hits.sort_by(|left, right| {
        right
            .score
            .partial_cmp(&left.score)
            .unwrap_or(Ordering::Equal)
            .then_with(|| {
                label_for_id(&id_to_spec, &left.memory.id)
                    .cmp(label_for_id(&id_to_spec, &right.memory.id))
            })
    });

    let hit_snapshot = serde_json::to_string(&hits)?;
    let store_snapshot = store_snapshot(&store, label_to_id.values())?;
    let trace = CognitiveTraceEvaluator::evaluate(&spec.query, &hits);
    let config = CognitiveBoosterConfig::shadow(MAX_COGNITIVE_BOOSTER_BONUS, hits.len())?;
    let booster = DeterministicCognitiveBoosterV0;
    let output = booster.boost(CognitiveBoosterInput::new(&hits, &trace, &config));
    ensure!(output.bounded());
    ensure!(!output.runtime_applied());
    ensure!(!output.memory_mutated());
    let full_bonuses = output
        .adjusted_scores()
        .iter()
        .map(|score| (score.candidate_id.clone(), score.bounded_bonus))
        .collect();

    Ok(Fixture {
        spec,
        store,
        hits,
        trace,
        label_to_id,
        id_to_spec,
        full_bonuses,
        hit_snapshot,
        store_snapshot,
    })
}

fn store_snapshot<'a>(store: &Store, ids: impl Iterator<Item = &'a String>) -> Result<String> {
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

fn policy_specs() -> Vec<PolicySpec> {
    let mut policies = vec![PolicySpec::AbsoluteBonus];
    policies.extend(
        WEIGHTED_ALPHAS
            .into_iter()
            .map(|alpha| PolicySpec::WeightedFusion { alpha }),
    );
    policies.push(PolicySpec::MarginGuard {
        alpha: MARGIN_GUARD_ALPHA,
        threshold: MARGIN_GUARD_THRESHOLD,
    });
    policies
}

pub(crate) fn evaluate_policy(
    policy: &PolicySpec,
    fixtures: &[Fixture],
    omitted_factor: Option<CognitiveFactorType>,
) -> Result<CognitivePolicyResult> {
    let mut scenario_reports = Vec::with_capacity(fixtures.len());
    for fixture in fixtures {
        let bonuses = match omitted_factor {
            None => fixture.full_bonuses.clone(),
            Some(factor) => bonuses_with_factor_removed(fixture, factor)?,
        };
        let first = apply_policy(policy, fixture, &bonuses);
        let replay = apply_policy(policy, fixture, &bonuses);
        let deterministic = first == replay;
        ensure!(
            deterministic,
            "policy {} is not deterministic",
            policy.name()
        );
        scenario_reports.push(build_scenario_report(
            fixture,
            policy,
            &bonuses,
            first,
            deterministic,
        ));
    }
    let metrics = aggregate_metrics(&scenario_reports);
    Ok(CognitivePolicyResult {
        policy: policy.name(),
        family: policy.family().to_string(),
        alpha: policy.alpha(),
        margin_threshold: policy.threshold(),
        metrics,
        scenario_reports,
    })
}

pub(crate) fn evaluate_policy_with_included_factors(
    policy: &PolicySpec,
    fixtures: &[Fixture],
    included_factors: &[CognitiveFactorType],
) -> Result<CognitivePolicyResult> {
    let mut scenario_reports = Vec::with_capacity(fixtures.len());
    for fixture in fixtures {
        let bonuses = bonuses_with_included_factors(fixture, included_factors)?;
        let first = apply_policy(policy, fixture, &bonuses);
        let replay = apply_policy(policy, fixture, &bonuses);
        let deterministic = first == replay;
        ensure!(
            deterministic,
            "policy {} factor interaction is not deterministic",
            policy.name()
        );
        scenario_reports.push(build_scenario_report(
            fixture,
            policy,
            &bonuses,
            first,
            deterministic,
        ));
    }
    let metrics = aggregate_metrics(&scenario_reports);
    Ok(CognitivePolicyResult {
        policy: policy.name(),
        family: policy.family().to_string(),
        alpha: policy.alpha(),
        margin_threshold: policy.threshold(),
        metrics,
        scenario_reports,
    })
}

fn bonuses_with_included_factors(
    fixture: &Fixture,
    included_factors: &[CognitiveFactorType],
) -> Result<HashMap<String, f64>> {
    let mut trace = fixture.trace.clone();
    trace
        .factors
        .retain(|factor| included_factors.contains(&factor.factor_type));
    let config = CognitiveBoosterConfig::shadow(MAX_COGNITIVE_BOOSTER_BONUS, fixture.hits.len())?;
    let booster = DeterministicCognitiveBoosterV0;
    let output = booster.boost(CognitiveBoosterInput::new(&fixture.hits, &trace, &config));
    ensure!(output.bounded());
    ensure!(!output.runtime_applied());
    ensure!(!output.memory_mutated());
    Ok(output
        .adjusted_scores()
        .iter()
        .map(|score| (score.candidate_id.clone(), score.bounded_bonus))
        .collect())
}

fn bonuses_with_factor_removed(
    fixture: &Fixture,
    omitted_factor: CognitiveFactorType,
) -> Result<HashMap<String, f64>> {
    let mut trace = fixture.trace.clone();
    trace
        .factors
        .retain(|factor| factor.factor_type != omitted_factor);
    let config = CognitiveBoosterConfig::shadow(MAX_COGNITIVE_BOOSTER_BONUS, fixture.hits.len())?;
    let booster = DeterministicCognitiveBoosterV0;
    let output = booster.boost(CognitiveBoosterInput::new(&fixture.hits, &trace, &config));
    Ok(output
        .adjusted_scores()
        .iter()
        .map(|score| (score.candidate_id.clone(), score.bounded_bonus))
        .collect())
}

fn apply_policy(
    policy: &PolicySpec,
    fixture: &Fixture,
    bonuses: &HashMap<String, f64>,
) -> Vec<RankedCandidate> {
    let max_baseline = fixture
        .hits
        .iter()
        .map(|hit| f64::from(hit.score))
        .fold(EPSILON, f64::max);
    let mut candidates = fixture
        .hits
        .iter()
        .enumerate()
        .map(|(index, hit)| {
            let baseline = f64::from(hit.score);
            let baseline_normalized = (baseline / max_baseline).clamp(0.0, 1.0);
            let bonus = bonuses.get(&hit.memory.id).copied().unwrap_or(0.0);
            let cognitive_normalized = (bonus / MAX_COGNITIVE_BOOSTER_BONUS).clamp(0.0, 1.0);
            let memory_spec = fixture
                .id_to_spec
                .get(&hit.memory.id)
                .expect("fixture recall id must map to memory spec");
            let score = match policy {
                PolicySpec::Baseline => baseline_normalized,
                PolicySpec::MetadataConfidence { alpha } => {
                    baseline_normalized * (1.0 - alpha)
                        + memory_spec.confidence.clamp(0.0, 1.0) * alpha
                }
                PolicySpec::Recency { alpha } => {
                    let recency = match memory_spec.temporal_state.as_str() {
                        "superseded" => 0.20,
                        "accessed" => 0.90,
                        _ => 0.75,
                    };
                    baseline_normalized * (1.0 - alpha) + recency * alpha
                }
                PolicySpec::AbsoluteBonus => baseline + bonus,
                PolicySpec::WeightedFusion { alpha } | PolicySpec::MarginGuard { alpha, .. } => {
                    baseline_normalized * (1.0 - alpha) + cognitive_normalized * alpha
                }
            };
            RankedCandidate {
                candidate_id: hit.memory.id.clone(),
                baseline_rank: index + 1,
                baseline_score: baseline,
                baseline_normalized,
                cognitive_bonus: bonus,
                cognitive_normalized,
                policy_score: score,
            }
        })
        .collect::<Vec<_>>();

    match policy {
        PolicySpec::Baseline
        | PolicySpec::MetadataConfidence { .. }
        | PolicySpec::Recency { .. }
        | PolicySpec::AbsoluteBonus
        | PolicySpec::WeightedFusion { .. } => candidates.sort_by(compare_policy_candidate),
        PolicySpec::MarginGuard { threshold, .. } => {
            let mut guarded = candidates
                .iter()
                .filter(|candidate| 1.0 - candidate.baseline_normalized <= *threshold + EPSILON)
                .cloned()
                .collect::<Vec<_>>();
            let mut preserved = candidates
                .iter()
                .filter(|candidate| 1.0 - candidate.baseline_normalized > *threshold + EPSILON)
                .cloned()
                .collect::<Vec<_>>();
            guarded.sort_by(compare_policy_candidate);
            preserved.sort_by_key(|candidate| candidate.baseline_rank);
            guarded.extend(preserved);
            candidates = guarded;
        }
    }
    candidates
}

fn compare_policy_candidate(left: &RankedCandidate, right: &RankedCandidate) -> Ordering {
    right
        .policy_score
        .partial_cmp(&left.policy_score)
        .unwrap_or(Ordering::Equal)
        .then_with(|| left.baseline_rank.cmp(&right.baseline_rank))
}

fn build_scenario_report(
    fixture: &Fixture,
    policy: &PolicySpec,
    bonuses: &HashMap<String, f64>,
    ranking: Vec<RankedCandidate>,
    deterministic: bool,
) -> CognitivePolicyScenarioReport {
    let baseline_ranking = fixture
        .hits
        .iter()
        .map(|hit| label_for_id(&fixture.id_to_spec, &hit.memory.id).to_string())
        .collect::<Vec<_>>();
    let policy_ranking = ranking
        .iter()
        .map(|candidate| label_for_id(&fixture.id_to_spec, &candidate.candidate_id).to_string())
        .collect::<Vec<_>>();
    let expected = &fixture.spec.expected_top;
    let baseline_rank = rank_of(&baseline_ranking, expected);
    let policy_rank = rank_of(&policy_ranking, expected);
    let top1_changed = baseline_ranking.first() != policy_ranking.first();
    let successful_intervention = fixture.spec.intervention_required
        && policy_ranking
            .first()
            .is_some_and(|label| label == expected);
    let unnecessary_intervention = !fixture.spec.intervention_required && top1_changed;
    let catastrophic_regression = baseline_ranking
        .first()
        .is_some_and(|label| label == expected)
        && policy_ranking.first().map(String::as_str) != Some(expected.as_str());
    let policy_rank_by_id = ranking
        .iter()
        .enumerate()
        .map(|(index, candidate)| (candidate.candidate_id.as_str(), index + 1))
        .collect::<HashMap<_, _>>();
    let candidates = ranking
        .iter()
        .map(|candidate| {
            let policy_rank_value = policy_rank_by_id[&candidate.candidate_id.as_str()];
            CognitivePolicyCandidateReport {
                label: label_for_id(&fixture.id_to_spec, &candidate.candidate_id).to_string(),
                candidate_id: candidate.candidate_id.clone(),
                relevant: fixture
                    .id_to_spec
                    .get(&candidate.candidate_id)
                    .is_some_and(|memory| memory.relevant),
                baseline_rank: candidate.baseline_rank,
                policy_rank: policy_rank_value,
                position_delta: candidate.baseline_rank as isize - policy_rank_value as isize,
                baseline_score: candidate.baseline_score,
                baseline_normalized: candidate.baseline_normalized,
                cognitive_bonus: bonuses.get(&candidate.candidate_id).copied().unwrap_or(0.0),
                cognitive_normalized: candidate.cognitive_normalized,
                policy_score: candidate.policy_score,
                factors: factor_reports(fixture, &candidate.candidate_id),
            }
        })
        .collect::<Vec<_>>();

    CognitivePolicyScenarioReport {
        id: fixture.spec.id.clone(),
        category: fixture.spec.category.clone(),
        query: fixture.spec.query.clone(),
        policy: policy.name(),
        intervention_required: fixture.spec.intervention_required,
        expected_top: expected.clone(),
        label_to_candidate_id: fixture.label_to_id.clone(),
        baseline_ranking: baseline_ranking.clone(),
        policy_ranking: policy_ranking.clone(),
        baseline_expected_rank: baseline_rank,
        policy_expected_rank: policy_rank,
        baseline_recall_at_k: recall_at_k(&baseline_ranking, expected, METRIC_CUTOFF),
        policy_recall_at_k: recall_at_k(&policy_ranking, expected, METRIC_CUTOFF),
        baseline_reciprocal_rank: reciprocal_rank(baseline_rank),
        policy_reciprocal_rank: reciprocal_rank(policy_rank),
        top1_changed,
        successful_intervention,
        unnecessary_intervention,
        catastrophic_regression,
        deterministic,
        candidate_pool_preserved: same_pool(&baseline_ranking, &policy_ranking),
        runtime_applied: false,
        candidates,
    }
}

fn factor_reports(fixture: &Fixture, candidate_id: &str) -> Vec<CognitiveFactorContributionReport> {
    fixture
        .trace
        .factors
        .iter()
        .filter(|factor| factor.candidate_id == candidate_id)
        .map(|factor| CognitiveFactorContributionReport {
            factor: format!("{:?}", factor.factor_type),
            contribution: factor.contribution,
        })
        .collect()
}

pub(crate) fn aggregate_metrics(
    scenarios: &[CognitivePolicyScenarioReport],
) -> CognitivePolicyMetrics {
    let count = scenarios.len() as f64;
    let required = scenarios
        .iter()
        .filter(|scenario| scenario.intervention_required)
        .count();
    let no_intervention = scenarios.len() - required;
    let interventions = scenarios
        .iter()
        .filter(|scenario| scenario.top1_changed)
        .count();
    let successes = scenarios
        .iter()
        .filter(|scenario| scenario.successful_intervention)
        .count();
    let unnecessary = scenarios
        .iter()
        .filter(|scenario| scenario.unnecessary_intervention)
        .count();
    let baseline_correct = scenarios
        .iter()
        .filter(|scenario| scenario.baseline_expected_rank == 1)
        .count();
    let catastrophic = scenarios
        .iter()
        .filter(|scenario| scenario.catastrophic_regression)
        .count();
    let regressions = scenarios
        .iter()
        .filter(|scenario| scenario.policy_expected_rank > scenario.baseline_expected_rank)
        .count();
    let changed_positions = scenarios
        .iter()
        .flat_map(|scenario| &scenario.candidates)
        .filter(|candidate| candidate.position_delta != 0)
        .count();
    let total_candidates = scenarios
        .iter()
        .map(|scenario| scenario.candidates.len())
        .sum::<usize>();
    let total_movement = scenarios
        .iter()
        .flat_map(|scenario| &scenario.candidates)
        .map(|candidate| candidate.position_delta.unsigned_abs() as f64)
        .sum::<f64>();
    let max_movement = scenarios
        .iter()
        .flat_map(|scenario| &scenario.candidates)
        .map(|candidate| candidate.position_delta.unsigned_abs())
        .max()
        .unwrap_or(0);
    let bounded = scenarios
        .iter()
        .flat_map(|scenario| &scenario.candidates)
        .filter(|candidate| {
            candidate.cognitive_bonus >= 0.0
                && candidate.cognitive_bonus <= MAX_COGNITIVE_BOOSTER_BONUS + EPSILON
        })
        .count();
    let baseline_recall = scenarios
        .iter()
        .map(|scenario| scenario.baseline_recall_at_k)
        .sum::<f64>()
        / count;
    let policy_recall = scenarios
        .iter()
        .map(|scenario| scenario.policy_recall_at_k)
        .sum::<f64>()
        / count;
    let baseline_mrr = scenarios
        .iter()
        .map(|scenario| scenario.baseline_reciprocal_rank)
        .sum::<f64>()
        / count;
    let policy_mrr = scenarios
        .iter()
        .map(|scenario| scenario.policy_reciprocal_rank)
        .sum::<f64>()
        / count;

    CognitivePolicyMetrics {
        scenarios: scenarios.len(),
        top1_accuracy: safe_div(
            scenarios
                .iter()
                .filter(|scenario| scenario.policy_expected_rank == 1)
                .count() as f64,
            count,
        ),
        baseline_recall_at_k: baseline_recall,
        policy_recall_at_k: policy_recall,
        recall_at_k_delta: policy_recall - baseline_recall,
        baseline_mrr,
        policy_mrr,
        mrr_delta: policy_mrr - baseline_mrr,
        policy_interventions: interventions,
        successful_required_interventions: successes,
        intervention_precision: safe_div(successes as f64, interventions as f64),
        intervention_recall: safe_div(successes as f64, required as f64),
        unnecessary_interventions: unnecessary,
        unnecessary_intervention_rate: safe_div(unnecessary as f64, no_intervention as f64),
        catastrophic_regressions: catastrophic,
        catastrophic_regression_rate: safe_div(catastrophic as f64, baseline_correct as f64),
        regressions,
        regression_rate: safe_div(regressions as f64, count),
        changed_positions,
        avg_abs_rank_delta: safe_div(total_movement, total_candidates as f64),
        max_abs_rank_delta: max_movement,
        bounded_rate: safe_div(bounded as f64, total_candidates as f64),
        determinism: safe_div(
            scenarios
                .iter()
                .filter(|scenario| scenario.deterministic)
                .count() as f64,
            count,
        ),
    }
}

fn evaluate_ablation(
    policy: &PolicySpec,
    fixtures: &[Fixture],
    ablation: AblationSpec,
) -> Result<CognitivePolicyAblationReport> {
    let result = evaluate_policy(policy, fixtures, ablation.factor)?;
    let removed_factor_count = match ablation.factor {
        None => 0,
        Some(factor) => fixtures
            .iter()
            .flat_map(|fixture| &fixture.trace.factors)
            .filter(|candidate_factor| candidate_factor.factor_type == factor)
            .count(),
    };
    Ok(CognitivePolicyAblationReport {
        name: ablation.name.to_string(),
        omitted_factor: ablation.factor.map(|factor| format!("{:?}", factor)),
        removed_factor_count,
        metrics: result.metrics,
    })
}

fn ablation_specs() -> Vec<AblationSpec> {
    vec![
        AblationSpec {
            name: "full_cognitive",
            factor: None,
        },
        AblationSpec {
            name: "without_temporal",
            factor: Some(CognitiveFactorType::TemporalConfidence),
        },
        AblationSpec {
            name: "without_reliability",
            factor: Some(CognitiveFactorType::Reliability),
        },
        AblationSpec {
            name: "without_failure",
            factor: Some(CognitiveFactorType::FailureEvidence),
        },
        AblationSpec {
            name: "without_preference",
            factor: Some(CognitiveFactorType::PreferenceAlignment),
        },
        AblationSpec {
            name: "without_context",
            factor: Some(CognitiveFactorType::ContextAlignment),
        },
    ]
}

fn category_counts(fixtures: &[Fixture]) -> BTreeMap<String, usize> {
    let mut categories = BTreeMap::new();
    for fixture in fixtures {
        *categories.entry(fixture.spec.category.clone()).or_default() += 1;
    }
    categories
}

fn label_for_id<'a>(mapping: &'a HashMap<String, CognitivePolicyMemorySpec>, id: &str) -> &'a str {
    mapping
        .get(id)
        .map(|memory| memory.label.as_str())
        .unwrap_or("<unknown>")
}

fn rank_of(ranking: &[String], expected: &str) -> usize {
    ranking
        .iter()
        .position(|candidate| candidate == expected)
        .map(|index| index + 1)
        .unwrap_or(ranking.len() + 1)
}

fn recall_at_k(ranking: &[String], expected: &str, k: usize) -> f64 {
    if ranking
        .iter()
        .take(k)
        .any(|candidate| candidate == expected)
    {
        1.0
    } else {
        0.0
    }
}

fn reciprocal_rank(rank: usize) -> f64 {
    if rank == 0 {
        0.0
    } else {
        1.0 / rank as f64
    }
}

fn same_pool(left: &[String], right: &[String]) -> bool {
    let mut left = left.to_vec();
    let mut right = right.to_vec();
    left.sort();
    right.sort();
    left == right
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator <= EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone, Deserialize)]
struct CognitivePolicyDatasetFile {
    schema_version: u32,
    scenario: Vec<CognitivePolicyScenarioSpec>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct CognitivePolicyScenarioSpec {
    pub id: String,
    pub category: String,
    pub query: String,
    pub expected_top: String,
    pub intervention_required: bool,
    pub memory: Vec<CognitivePolicyMemorySpec>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct CognitivePolicyMemorySpec {
    pub label: String,
    pub content: String,
    pub kind: String,
    pub confidence: f64,
    pub importance: f64,
    pub baseline_score: f64,
    #[serde(default = "active_temporal_state")]
    pub temporal_state: String,
    pub relevant: bool,
}

fn active_temporal_state() -> String {
    "active".to_string()
}

pub(crate) struct Fixture {
    spec: CognitivePolicyScenarioSpec,
    store: Store,
    hits: Vec<RecallHit>,
    trace: CognitiveCompetitionTrace,
    label_to_id: BTreeMap<String, String>,
    id_to_spec: HashMap<String, CognitivePolicyMemorySpec>,
    full_bonuses: HashMap<String, f64>,
    hit_snapshot: String,
    store_snapshot: String,
}

impl Fixture {
    pub(crate) fn label_mapping_is_bijective(&self) -> bool {
        self.label_to_id.len() == self.spec.memory.len()
            && self.label_to_id.values().collect::<BTreeSet<_>>().len() == self.spec.memory.len()
    }
    pub(crate) fn hits_unchanged(&self) -> bool {
        serde_json::to_string(&self.hits).is_ok_and(|snapshot| snapshot == self.hit_snapshot)
    }
    pub(crate) fn store_unchanged(&self) -> bool {
        store_snapshot(&self.store, self.label_to_id.values())
            .is_ok_and(|snapshot| snapshot == self.store_snapshot)
    }
}

#[derive(Debug, Clone, Copy)]
pub(crate) enum PolicySpec {
    Baseline,
    MetadataConfidence { alpha: f64 },
    Recency { alpha: f64 },
    AbsoluteBonus,
    WeightedFusion { alpha: f64 },
    MarginGuard { alpha: f64, threshold: f64 },
}

impl PolicySpec {
    fn name(self) -> String {
        match self {
            Self::Baseline => "retrieval_baseline".to_string(),
            Self::MetadataConfidence { alpha } => {
                format!("metadata_confidence_alpha_{alpha:.2}")
            }
            Self::Recency { alpha } => format!("recency_boost_alpha_{alpha:.2}"),
            Self::AbsoluteBonus => "absolute_bonus".to_string(),
            Self::WeightedFusion { alpha } => format!("weighted_fusion_alpha_{alpha:.2}"),
            Self::MarginGuard { alpha, threshold } => {
                format!("margin_guard_threshold_{threshold:.2}_alpha_{alpha:.2}")
            }
        }
    }
    fn family(self) -> &'static str {
        match self {
            Self::Baseline => "retrieval_baseline",
            Self::MetadataConfidence { .. } => "metadata_confidence",
            Self::Recency { .. } => "recency_boost",
            Self::AbsoluteBonus => "absolute_bonus",
            Self::WeightedFusion { .. } => "weighted_fusion",
            Self::MarginGuard { .. } => "margin_guard",
        }
    }
    fn alpha(self) -> Option<f64> {
        match self {
            Self::Baseline | Self::AbsoluteBonus => None,
            Self::MetadataConfidence { alpha }
            | Self::Recency { alpha }
            | Self::WeightedFusion { alpha }
            | Self::MarginGuard { alpha, .. } => Some(alpha),
        }
    }
    fn threshold(self) -> Option<f64> {
        match self {
            Self::MarginGuard { threshold, .. } => Some(threshold),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub(crate) struct RankedCandidate {
    candidate_id: String,
    baseline_rank: usize,
    baseline_score: f64,
    baseline_normalized: f64,
    cognitive_bonus: f64,
    cognitive_normalized: f64,
    policy_score: f64,
}

#[derive(Debug, Clone, Copy)]
struct AblationSpec {
    name: &'static str,
    factor: Option<CognitiveFactorType>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitivePolicyBenchmarkSummary {
    pub dataset_path: String,
    pub scenarios: usize,
    pub candidates: usize,
    pub categories: BTreeMap<String, usize>,
    pub required_categories: Vec<String>,
    pub intervention_required_scenarios: usize,
    pub no_intervention_scenarios: usize,
    pub label_mapping_stable: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct PolicyNormalizationReport {
    pub baseline: String,
    pub cognitive: String,
    pub weighted_fusion: String,
    pub margin_guard: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitivePolicyResult {
    pub policy: String,
    pub family: String,
    pub alpha: Option<f64>,
    pub margin_threshold: Option<f64>,
    pub metrics: CognitivePolicyMetrics,
    pub scenario_reports: Vec<CognitivePolicyScenarioReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitivePolicyMetrics {
    pub scenarios: usize,
    pub top1_accuracy: f64,
    pub baseline_recall_at_k: f64,
    pub policy_recall_at_k: f64,
    pub recall_at_k_delta: f64,
    pub baseline_mrr: f64,
    pub policy_mrr: f64,
    pub mrr_delta: f64,
    pub policy_interventions: usize,
    pub successful_required_interventions: usize,
    pub intervention_precision: f64,
    pub intervention_recall: f64,
    pub unnecessary_interventions: usize,
    pub unnecessary_intervention_rate: f64,
    pub catastrophic_regressions: usize,
    pub catastrophic_regression_rate: f64,
    pub regressions: usize,
    pub regression_rate: f64,
    pub changed_positions: usize,
    pub avg_abs_rank_delta: f64,
    pub max_abs_rank_delta: usize,
    pub bounded_rate: f64,
    pub determinism: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitivePolicyScenarioReport {
    pub id: String,
    pub category: String,
    pub query: String,
    pub policy: String,
    pub intervention_required: bool,
    pub expected_top: String,
    pub label_to_candidate_id: BTreeMap<String, String>,
    pub baseline_ranking: Vec<String>,
    pub policy_ranking: Vec<String>,
    pub baseline_expected_rank: usize,
    pub policy_expected_rank: usize,
    pub baseline_recall_at_k: f64,
    pub policy_recall_at_k: f64,
    pub baseline_reciprocal_rank: f64,
    pub policy_reciprocal_rank: f64,
    pub top1_changed: bool,
    pub successful_intervention: bool,
    pub unnecessary_intervention: bool,
    pub catastrophic_regression: bool,
    pub deterministic: bool,
    pub candidate_pool_preserved: bool,
    pub runtime_applied: bool,
    pub candidates: Vec<CognitivePolicyCandidateReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitivePolicyCandidateReport {
    pub label: String,
    pub candidate_id: String,
    pub relevant: bool,
    pub baseline_rank: usize,
    pub policy_rank: usize,
    pub position_delta: isize,
    pub baseline_score: f64,
    pub baseline_normalized: f64,
    pub cognitive_bonus: f64,
    pub cognitive_normalized: f64,
    pub policy_score: f64,
    pub factors: Vec<CognitiveFactorContributionReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitiveFactorContributionReport {
    pub factor: String,
    pub contribution: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitivePolicyAblationReport {
    pub name: String,
    pub omitted_factor: Option<String>,
    pub removed_factor_count: usize,
    pub metrics: CognitivePolicyMetrics,
}

#[derive(Debug, Clone, Serialize)]
pub struct CognitivePolicySafetyGuards {
    pub eval_only: bool,
    pub shadow_only: bool,
    pub baseline_authoritative: bool,
    pub runtime_applied: bool,
    pub fixture_setup_writes: bool,
    pub policy_memory_written: bool,
    pub memory_mutated: bool,
    pub ranking_mutated: bool,
    pub scores_mutated: bool,
    pub activation_changed: bool,
    pub candidate_pool_changed: bool,
    pub recall_engine_integrated: bool,
    pub production_claim_authorized: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase5CognitivePolicyReport {
    pub schema_version: u32,
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub benchmark: CognitivePolicyBenchmarkSummary,
    pub normalization: PolicyNormalizationReport,
    pub policies: Vec<CognitivePolicyResult>,
    pub ablation_policy: String,
    pub ablations: Vec<CognitivePolicyAblationReport>,
    pub guards: CognitivePolicySafetyGuards,
    pub pass: bool,
    pub status: String,
    pub conclusion: String,
}
