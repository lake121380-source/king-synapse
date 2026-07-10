use anyhow::{ensure, Context, Result};
use chrono::Utc;
use serde::Serialize;
use std::collections::BTreeMap;

use crate::{
    metrics::percentile,
    phase6_memory_intelligence_benchmark::{
        MemoryIntelligenceDatasetSummary, MemoryIntelligenceScenarioReport,
        Phase6MemoryIntelligenceBenchmarkEvaluator,
    },
};

const SCHEMA_VERSION: u32 = 1;
const EVALUATION_VERSION: &str = "phase6.2-recall-score-distribution-v1";
const EXPECTED_SCENARIOS: usize = 320;
const LOCKED_MARGIN_THRESHOLD: f64 = 0.08;
const LOCKED_POLICY_ALPHA: f64 = 0.20;
const ANALYZED_THRESHOLDS: [f64; 7] = [0.01, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20];
const EPSILON: f64 = 1e-12;

pub struct Phase6RecallScoreDistributionEvaluator;

impl Phase6RecallScoreDistributionEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase6RecallScoreDistributionReport> {
        evaluate(tag.into())
    }
}

fn evaluate(tag: String) -> Result<Phase6RecallScoreDistributionReport> {
    let source = Phase6MemoryIntelligenceBenchmarkEvaluator::evaluate(
        "phase6.2-recall-score-distribution-source",
    )?;
    ensure!(source.pass, "Phase 6.0 source benchmark did not pass");
    ensure!(source.scenarios.len() == EXPECTED_SCENARIOS);

    let scenarios = source
        .scenarios
        .iter()
        .map(build_scenario_distribution)
        .collect::<Result<Vec<_>>>()?;
    let candidate_count = summarize_candidate_counts(&scenarios);
    let score_distribution = summarize_scores(&source.scenarios);
    let adjacent_gaps = summarize_adjacent_gaps(&source.scenarios);
    let margin_coverage = ANALYZED_THRESHOLDS
        .iter()
        .copied()
        .map(|threshold| summarize_margin_coverage(threshold, &source.scenarios))
        .collect::<Vec<_>>();
    let locked_margin = margin_coverage
        .iter()
        .find(|coverage| approx_eq(coverage.threshold, LOCKED_MARGIN_THRESHOLD))
        .cloned()
        .context("locked 0.08 threshold missing from coverage study")?;
    let category_locked_margin =
        grouped_locked_margin(&scenarios, "category", |scenario| scenario.category.clone());
    let split_locked_margin =
        grouped_locked_margin(&scenarios, "split", |scenario| scenario.split.clone());

    let top1_top2 = adjacent_gaps
        .iter()
        .find(|gap| gap.left_rank == 1 && gap.right_rank == 2)
        .context("top1-top2 gap distribution missing")?;
    let coverage_monotonic = margin_coverage
        .windows(2)
        .all(|window| window[0].eligible_scenarios <= window[1].eligible_scenarios);
    let all_scores_ordered = scenarios.iter().all(|scenario| scenario.score_order_valid);
    let all_retrieval_deterministic = scenarios
        .iter()
        .all(|scenario| scenario.retrieval_deterministic);
    let all_scenarios_have_candidates = scenarios
        .iter()
        .all(|scenario| scenario.candidate_count > 0);
    let score_count_consistent = score_distribution.all_candidates.count
        == scenarios
            .iter()
            .map(|scenario| scenario.candidate_count)
            .sum::<usize>();
    let current_coverage_consistent = scenarios
        .iter()
        .filter(|scenario| scenario.locked_margin_triggered)
        .count()
        == locked_margin.eligible_scenarios;

    let guards = RecallScoreDistributionGuards {
        eval_only: true,
        distribution_study_only: true,
        real_recall_engine_used: source.guards.real_recall_engine_used,
        source_phase6_benchmark_passed: source.pass,
        recall_engine_modified: false,
        cognitive_booster_modified: false,
        cognitive_algorithm_executed: false,
        threshold_modified: false,
        alpha_modified: false,
        threshold_selected_from_results: false,
        ranking_modified: false,
        retrieval_scores_mutated: false,
        candidate_generation_modified: false,
        candidate_pool_changed: false,
        memory_written: false,
        memory_mutated: source.guards.memory_mutated_during_retrieval,
        memory_schema_changed: false,
        runtime_applied: false,
        hermes_integration_performed: false,
        runtime_authorization: false,
        production_claim_authorized: false,
    };

    let pass = source.dataset.scenarios == EXPECTED_SCENARIOS
        && scenarios.len() == EXPECTED_SCENARIOS
        && all_scenarios_have_candidates
        && all_scores_ordered
        && all_retrieval_deterministic
        && score_count_consistent
        && coverage_monotonic
        && current_coverage_consistent
        && margin_coverage.len() == ANALYZED_THRESHOLDS.len()
        && !guards.recall_engine_modified
        && !guards.cognitive_booster_modified
        && !guards.cognitive_algorithm_executed
        && !guards.threshold_modified
        && !guards.alpha_modified
        && !guards.threshold_selected_from_results
        && !guards.ranking_modified
        && !guards.retrieval_scores_mutated
        && !guards.candidate_generation_modified
        && !guards.candidate_pool_changed
        && !guards.memory_written
        && !guards.memory_mutated
        && !guards.memory_schema_changed
        && !guards.runtime_applied
        && !guards.hermes_integration_performed
        && !guards.runtime_authorization
        && !guards.production_claim_authorized;

    let current_margin_has_authority = locked_margin.eligible_scenarios > 0;
    let observed_min_gap = top1_top2.top_relative_gap.min;
    let decision = RecallScoreDistributionDecision {
        score_distribution_baseline_established: pass,
        locked_margin_threshold: LOCKED_MARGIN_THRESHOLD,
        observed_minimum_top1_top2_normalized_gap: observed_min_gap,
        locked_margin_eligible_scenarios: locked_margin.eligible_scenarios,
        locked_margin_eligible_rate: locked_margin.eligible_rate,
        current_margin_has_authority,
        current_margin_below_observed_minimum_gap: LOCKED_MARGIN_THRESHOLD + EPSILON
            < observed_min_gap,
        threshold_selection_performed: false,
        margin_redesign_authorized: false,
        cognitive_value_evaluated: false,
        cognitive_failure_inferred: false,
        hermes_shadow_integration_recommended: false,
        hermes_recommendation: if current_margin_has_authority {
            "Do not enter Hermes yet: first pre-register how observed score-gap coverage will be used in a separate shadow authority study."
                .to_string()
        } else {
            "Do not enter Hermes: the locked 0.08 Margin Guard has zero natural authority on the frozen workload; use this distribution baseline to design a separately pre-registered authority study."
                .to_string()
        },
        runtime_authorization: false,
        production_claim_authorized: false,
    };

    Ok(Phase6RecallScoreDistributionReport {
        schema_version: SCHEMA_VERSION,
        tag,
        phase: "Phase 6.2 Recall Score Distribution Study".to_string(),
        mode: "eval_only_real_recall_score_observation".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        protocol: RecallScoreDistributionProtocol {
            dataset_path: source.protocol.dataset_path.clone(),
            dataset_sha256: source.protocol.dataset_sha256.clone(),
            source_evaluation_version: source.evaluation_version.clone(),
            retrieval_mode: source.protocol.retrieval_mode.clone(),
            score_provenance: source.protocol.score_provenance.clone(),
            candidate_limit: source.protocol.candidate_limit,
            locked_margin_threshold: LOCKED_MARGIN_THRESHOLD,
            locked_policy_alpha: LOCKED_POLICY_ALPHA,
            analyzed_thresholds: ANALYZED_THRESHOLDS.to_vec(),
            raw_gap_definition: "score(rank_i) - score(rank_i+1)".to_string(),
            adjacent_normalized_gap_definition:
                "1 - score(rank_i+1) / score(rank_i)".to_string(),
            top_relative_gap_definition: "1 - score(candidate) / score(top1); this is the existing Margin Guard scale"
                .to_string(),
            threshold_policy: "descriptive_only_no_threshold_selection_or_tuning".to_string(),
            quality_gate_semantics: "PASS validates reproducible distribution statistics and safety isolation; it does not validate Cognitive value or authorize a new threshold"
                .to_string(),
        },
        dataset: source.dataset,
        candidate_count,
        score_distribution,
        adjacent_gaps,
        margin_coverage,
        category_locked_margin,
        split_locked_margin,
        scenarios,
        decision,
        guards,
        pass,
        status: if pass { "PASS" } else { "FAIL" }.to_string(),
        conclusion: "Phase 6.2 establishes a descriptive RecallEngine score-distribution baseline. No ranking, Cognitive algorithm, threshold, runtime, or Hermes integration was changed."
            .to_string(),
    })
}

fn build_scenario_distribution(
    source: &MemoryIntelligenceScenarioReport,
) -> Result<RecallScoreScenarioReport> {
    ensure!(!source.scores.is_empty(), "{} has no scores", source.id);
    ensure!(
        source.ranking.len() == source.scores.len(),
        "{} ranking/score length mismatch",
        source.id
    );
    let score_order_valid = source
        .scores
        .windows(2)
        .all(|window| window[0] + EPSILON >= window[1]);
    ensure!(score_order_valid, "{} scores are not descending", source.id);

    let raw_adjacent_gaps = source
        .scores
        .windows(2)
        .map(|window| window[0] - window[1])
        .collect::<Vec<_>>();
    let adjacent_normalized_gaps = source
        .scores
        .windows(2)
        .map(|window| relative_gap(window[0], window[1]))
        .collect::<Vec<_>>();
    let top = source.scores[0];
    let top_relative_gaps = source
        .scores
        .iter()
        .map(|score| relative_gap(top, *score))
        .collect::<Vec<_>>();
    let locked_margin_eligible_candidates = top_relative_gaps
        .iter()
        .filter(|gap| **gap <= LOCKED_MARGIN_THRESHOLD + EPSILON)
        .count();

    Ok(RecallScoreScenarioReport {
        id: source.id.clone(),
        split: source.split.clone(),
        category: source.category.clone(),
        ranking: source.ranking.clone(),
        scores: source.scores.clone(),
        candidate_count: source.scores.len(),
        raw_adjacent_gaps,
        adjacent_normalized_gaps,
        top_relative_gaps,
        top1_top2_raw_gap: source.scores.get(1).map(|score| top - score),
        top1_top2_normalized_gap: source.scores.get(1).map(|score| relative_gap(top, *score)),
        locked_margin_eligible_candidates,
        locked_margin_triggered: locked_margin_eligible_candidates > 1,
        retrieval_deterministic: source.deterministic,
        score_order_valid,
        ranking_modified: false,
        runtime_applied: false,
    })
}

fn summarize_candidate_counts(
    scenarios: &[RecallScoreScenarioReport],
) -> CandidateCountDistribution {
    let values = scenarios
        .iter()
        .map(|scenario| scenario.candidate_count as f64)
        .collect::<Vec<_>>();
    let mut histogram = BTreeMap::new();
    for scenario in scenarios {
        *histogram.entry(scenario.candidate_count).or_insert(0) += 1;
    }
    CandidateCountDistribution {
        scenarios: scenarios.len(),
        histogram,
        summary: summarize(&values),
    }
}

fn summarize_scores(scenarios: &[MemoryIntelligenceScenarioReport]) -> ScoreDistributionReport {
    let all = scenarios
        .iter()
        .flat_map(|scenario| scenario.scores.iter().copied())
        .collect::<Vec<_>>();
    let max_rank = scenarios
        .iter()
        .map(|scenario| scenario.scores.len())
        .max()
        .unwrap_or(0);
    let by_rank = (0..max_rank)
        .map(|index| {
            let values = scenarios
                .iter()
                .filter_map(|scenario| scenario.scores.get(index).copied())
                .collect::<Vec<_>>();
            RankScoreDistribution {
                rank: index + 1,
                summary: summarize(&values),
            }
        })
        .collect();
    ScoreDistributionReport {
        all_candidates: summarize(&all),
        by_rank,
    }
}

fn summarize_adjacent_gaps(
    scenarios: &[MemoryIntelligenceScenarioReport],
) -> Vec<AdjacentGapDistribution> {
    let max_rank = scenarios
        .iter()
        .map(|scenario| scenario.scores.len())
        .max()
        .unwrap_or(0);
    (0..max_rank.saturating_sub(1))
        .map(|index| {
            let pairs = scenarios
                .iter()
                .filter_map(|scenario| {
                    let left = scenario.scores.get(index).copied()?;
                    let right = scenario.scores.get(index + 1).copied()?;
                    Some((left, right, scenario.scores[0]))
                })
                .collect::<Vec<_>>();
            let raw = pairs
                .iter()
                .map(|(left, right, _)| left - right)
                .collect::<Vec<_>>();
            let adjacent_normalized = pairs
                .iter()
                .map(|(left, right, _)| relative_gap(*left, *right))
                .collect::<Vec<_>>();
            let top_relative = pairs
                .iter()
                .map(|(_, right, top)| relative_gap(*top, *right))
                .collect::<Vec<_>>();
            AdjacentGapDistribution {
                left_rank: index + 1,
                right_rank: index + 2,
                raw_gap: summarize(&raw),
                adjacent_normalized_gap: summarize(&adjacent_normalized),
                top_relative_gap: summarize(&top_relative),
            }
        })
        .collect()
}

fn summarize_margin_coverage(
    threshold: f64,
    scenarios: &[MemoryIntelligenceScenarioReport],
) -> MarginCoverage {
    let eligible_counts = scenarios
        .iter()
        .map(|scenario| {
            let top = scenario.scores[0];
            scenario
                .scores
                .iter()
                .filter(|score| relative_gap(top, **score) <= threshold + EPSILON)
                .count()
        })
        .collect::<Vec<_>>();
    let triggered = eligible_counts.iter().filter(|count| **count > 1).count();
    let eligible_candidates = eligible_counts.iter().sum::<usize>();
    let triggered_counts = eligible_counts
        .iter()
        .filter(|count| **count > 1)
        .map(|count| *count as f64)
        .collect::<Vec<_>>();
    MarginCoverage {
        threshold,
        scenarios: scenarios.len(),
        eligible_scenarios: triggered,
        eligible_rate: safe_div(triggered as f64, scenarios.len() as f64),
        total_candidates_inside_margin: eligible_candidates,
        mean_candidates_inside_margin: safe_div(eligible_candidates as f64, scenarios.len() as f64),
        mean_candidates_when_triggered: if triggered_counts.is_empty() {
            0.0
        } else {
            summarize(&triggered_counts).mean
        },
        max_candidates_inside_margin: eligible_counts.into_iter().max().unwrap_or(0),
        is_locked_margin: approx_eq(threshold, LOCKED_MARGIN_THRESHOLD),
    }
}

fn grouped_locked_margin(
    scenarios: &[RecallScoreScenarioReport],
    group_type: &str,
    key: impl Fn(&RecallScoreScenarioReport) -> String,
) -> Vec<GroupMarginCoverage> {
    let mut groups = BTreeMap::<String, Vec<&RecallScoreScenarioReport>>::new();
    for scenario in scenarios {
        groups.entry(key(scenario)).or_default().push(scenario);
    }
    groups
        .into_iter()
        .map(|(group, members)| {
            let gaps = members
                .iter()
                .filter_map(|scenario| scenario.top1_top2_normalized_gap)
                .collect::<Vec<_>>();
            let eligible = members
                .iter()
                .filter(|scenario| scenario.locked_margin_triggered)
                .count();
            GroupMarginCoverage {
                group_type: group_type.to_string(),
                group,
                scenarios: members.len(),
                top1_top2_normalized_gap: summarize(&gaps),
                locked_margin_eligible_scenarios: eligible,
                locked_margin_eligible_rate: safe_div(eligible as f64, members.len() as f64),
            }
        })
        .collect()
}

fn summarize(values: &[f64]) -> DistributionSummary {
    if values.is_empty() {
        return DistributionSummary::default();
    }
    let mean = values.iter().sum::<f64>() / values.len() as f64;
    let variance = values
        .iter()
        .map(|value| {
            let delta = value - mean;
            delta * delta
        })
        .sum::<f64>()
        / values.len() as f64;
    DistributionSummary {
        count: values.len(),
        min: values.iter().copied().fold(f64::INFINITY, f64::min),
        max: values.iter().copied().fold(f64::NEG_INFINITY, f64::max),
        mean,
        median: quantile(values, 50.0),
        p50: quantile(values, 50.0),
        p90: quantile(values, 90.0),
        p95: quantile(values, 95.0),
        p99: quantile(values, 99.0),
        standard_deviation: variance.sqrt(),
    }
}

fn quantile(values: &[f64], percentile_value: f64) -> f64 {
    let mut copy = values.to_vec();
    percentile(&mut copy, percentile_value)
}

fn relative_gap(left: f64, right: f64) -> f64 {
    if left.abs() <= EPSILON {
        0.0
    } else {
        ((left - right) / left).max(0.0)
    }
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() <= EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

fn approx_eq(left: f64, right: f64) -> bool {
    (left - right).abs() <= EPSILON
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase6RecallScoreDistributionReport {
    pub schema_version: u32,
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub generated_at: String,
    pub protocol: RecallScoreDistributionProtocol,
    pub dataset: MemoryIntelligenceDatasetSummary,
    pub candidate_count: CandidateCountDistribution,
    pub score_distribution: ScoreDistributionReport,
    pub adjacent_gaps: Vec<AdjacentGapDistribution>,
    pub margin_coverage: Vec<MarginCoverage>,
    pub category_locked_margin: Vec<GroupMarginCoverage>,
    pub split_locked_margin: Vec<GroupMarginCoverage>,
    pub scenarios: Vec<RecallScoreScenarioReport>,
    pub decision: RecallScoreDistributionDecision,
    pub guards: RecallScoreDistributionGuards,
    pub pass: bool,
    pub status: String,
    pub conclusion: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct RecallScoreDistributionProtocol {
    pub dataset_path: String,
    pub dataset_sha256: String,
    pub source_evaluation_version: String,
    pub retrieval_mode: String,
    pub score_provenance: String,
    pub candidate_limit: usize,
    pub locked_margin_threshold: f64,
    pub locked_policy_alpha: f64,
    pub analyzed_thresholds: Vec<f64>,
    pub raw_gap_definition: String,
    pub adjacent_normalized_gap_definition: String,
    pub top_relative_gap_definition: String,
    pub threshold_policy: String,
    pub quality_gate_semantics: String,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct DistributionSummary {
    pub count: usize,
    pub min: f64,
    pub max: f64,
    pub mean: f64,
    pub median: f64,
    pub p50: f64,
    pub p90: f64,
    pub p95: f64,
    pub p99: f64,
    pub standard_deviation: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct CandidateCountDistribution {
    pub scenarios: usize,
    pub histogram: BTreeMap<usize, usize>,
    pub summary: DistributionSummary,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScoreDistributionReport {
    pub all_candidates: DistributionSummary,
    pub by_rank: Vec<RankScoreDistribution>,
}

#[derive(Debug, Clone, Serialize)]
pub struct RankScoreDistribution {
    pub rank: usize,
    pub summary: DistributionSummary,
}

#[derive(Debug, Clone, Serialize)]
pub struct AdjacentGapDistribution {
    pub left_rank: usize,
    pub right_rank: usize,
    pub raw_gap: DistributionSummary,
    pub adjacent_normalized_gap: DistributionSummary,
    pub top_relative_gap: DistributionSummary,
}

#[derive(Debug, Clone, Serialize)]
pub struct MarginCoverage {
    pub threshold: f64,
    pub scenarios: usize,
    pub eligible_scenarios: usize,
    pub eligible_rate: f64,
    pub total_candidates_inside_margin: usize,
    pub mean_candidates_inside_margin: f64,
    pub mean_candidates_when_triggered: f64,
    pub max_candidates_inside_margin: usize,
    pub is_locked_margin: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct GroupMarginCoverage {
    pub group_type: String,
    pub group: String,
    pub scenarios: usize,
    pub top1_top2_normalized_gap: DistributionSummary,
    pub locked_margin_eligible_scenarios: usize,
    pub locked_margin_eligible_rate: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct RecallScoreScenarioReport {
    pub id: String,
    pub split: String,
    pub category: String,
    pub ranking: Vec<String>,
    pub scores: Vec<f64>,
    pub candidate_count: usize,
    pub raw_adjacent_gaps: Vec<f64>,
    pub adjacent_normalized_gaps: Vec<f64>,
    pub top_relative_gaps: Vec<f64>,
    pub top1_top2_raw_gap: Option<f64>,
    pub top1_top2_normalized_gap: Option<f64>,
    pub locked_margin_eligible_candidates: usize,
    pub locked_margin_triggered: bool,
    pub retrieval_deterministic: bool,
    pub score_order_valid: bool,
    pub ranking_modified: bool,
    pub runtime_applied: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct RecallScoreDistributionDecision {
    pub score_distribution_baseline_established: bool,
    pub locked_margin_threshold: f64,
    pub observed_minimum_top1_top2_normalized_gap: f64,
    pub locked_margin_eligible_scenarios: usize,
    pub locked_margin_eligible_rate: f64,
    pub current_margin_has_authority: bool,
    pub current_margin_below_observed_minimum_gap: bool,
    pub threshold_selection_performed: bool,
    pub margin_redesign_authorized: bool,
    pub cognitive_value_evaluated: bool,
    pub cognitive_failure_inferred: bool,
    pub hermes_shadow_integration_recommended: bool,
    pub hermes_recommendation: String,
    pub runtime_authorization: bool,
    pub production_claim_authorized: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct RecallScoreDistributionGuards {
    pub eval_only: bool,
    pub distribution_study_only: bool,
    pub real_recall_engine_used: bool,
    pub source_phase6_benchmark_passed: bool,
    pub recall_engine_modified: bool,
    pub cognitive_booster_modified: bool,
    pub cognitive_algorithm_executed: bool,
    pub threshold_modified: bool,
    pub alpha_modified: bool,
    pub threshold_selected_from_results: bool,
    pub ranking_modified: bool,
    pub retrieval_scores_mutated: bool,
    pub candidate_generation_modified: bool,
    pub candidate_pool_changed: bool,
    pub memory_written: bool,
    pub memory_mutated: bool,
    pub memory_schema_changed: bool,
    pub runtime_applied: bool,
    pub hermes_integration_performed: bool,
    pub runtime_authorization: bool,
    pub production_claim_authorized: bool,
}
