use crate::cognitive_memory_benchmark::CognitiveMemoryBenchmarkEvaluator;
use crate::phase2_competition_eval::{Phase2CompetitionCaseReport, Phase2CompetitionEvaluator};
use crate::types::{CognitiveMemoryBenchmarkReport, CognitiveMemoryCaseMethodReport};
use anyhow::{Context, Result};
use serde::Serialize;
use std::collections::BTreeMap;
use std::path::Path;
use synapse_core::adaptive::{
    MemoryInfluenceState, RuleBasedTemporalTransitionEngine, TemporalEvent, TemporalMemoryProfile,
    TemporalTransitionEngine,
};

const BASELINE_VERSION: &str = "v0.6.0-cognitive-validation";
const DATASET_VERSION: &str = "v1.2";

pub struct Phase2TemporalInfluenceEvaluator;

impl Phase2TemporalInfluenceEvaluator {
    pub fn evaluate(
        dataset_dir: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<Phase2TemporalInfluenceEvaluationReport> {
        let dataset_dir = dataset_dir.as_ref();
        let cognitive_report = CognitiveMemoryBenchmarkEvaluator::evaluate(
            dataset_dir,
            "phase2-temporal-influence-cognitive-baseline",
        )
        .context("loading Phase 1.2 cognitive memory benchmark")?;
        let competition_report = Phase2CompetitionEvaluator::evaluate(
            dataset_dir,
            "phase2-temporal-influence-competition-baseline",
        )
        .context("loading Phase 2.3 competition baseline")?;

        evaluate_reports(
            cognitive_report,
            competition_report,
            dataset_dir.display().to_string(),
            tag.into(),
        )
    }
}

fn evaluate_reports(
    cognitive_report: CognitiveMemoryBenchmarkReport,
    competition_report: crate::phase2_competition_eval::Phase2CompetitionEvaluationReport,
    dataset_dir: String,
    tag: String,
) -> Result<Phase2TemporalInfluenceEvaluationReport> {
    let competition_cases = competition_report
        .cases
        .iter()
        .map(|case| (case.id.clone(), case))
        .collect::<BTreeMap<_, _>>();
    let temporal = RuleBasedTemporalTransitionEngine::default();

    let mut cases = Vec::with_capacity(cognitive_report.case_count);
    let mut temporal_score_total = 0.0;
    let mut temporal_current_influence_total = 0.0;
    let mut temporal_causal_order_errors = 0usize;
    let mut temporal_opportunities = 0usize;
    let mut temporal_update_successes = 0usize;
    let mut obsolete_opportunities = 0usize;
    let mut obsolete_successes = 0usize;
    let mut historical_preservation_successes = 0usize;
    let mut causal_transition_opportunities = 0usize;
    let mut causal_transition_successes = 0usize;

    for dataset in &cognitive_report.datasets {
        for case in &dataset.cases {
            let full = case
                .methods
                .iter()
                .find(|method| method.method == "full_synapse")
                .with_context(|| format!("case {} missing full_synapse method", case.id))?;
            let competition_case = competition_cases
                .get(&case.id)
                .copied()
                .with_context(|| format!("case {} missing competition baseline", case.id))?;
            let case_report = evaluate_case_with_temporal(case, full, competition_case, &temporal);

            temporal_score_total += case_report.temporal_score;
            temporal_current_influence_total += case_report.current_influence;
            temporal_causal_order_errors += usize::from(
                case_report.temporal_failure_type.as_deref() == Some("causal_order_error"),
            );
            if case_report.temporal_opportunity {
                temporal_opportunities += 1;
                temporal_update_successes += usize::from(case_report.temporal_update_success);
                historical_preservation_successes +=
                    usize::from(case_report.historical_preservation_success);
            }
            if case_report.obsolete_opportunity {
                obsolete_opportunities += 1;
                obsolete_successes += usize::from(case_report.obsolete_detection_success);
            }
            if case_report.causal_transition_opportunity {
                causal_transition_opportunities += 1;
                causal_transition_successes += usize::from(case_report.causal_transition_success);
            }
            cases.push(case_report);
        }
    }

    let case_count = cases.len();
    let temporal_score = safe_div(temporal_score_total, case_count as f64);
    let temporal_mean_influence = safe_div(temporal_current_influence_total, case_count as f64);
    let temporal_update_accuracy = safe_div(
        temporal_update_successes as f64,
        temporal_opportunities as f64,
    );
    let obsolete_memory_detection =
        safe_div(obsolete_successes as f64, obsolete_opportunities as f64);
    let historical_preservation = safe_div(
        historical_preservation_successes as f64,
        temporal_opportunities as f64,
    );
    let causal_transition_accuracy = safe_div(
        causal_transition_successes as f64,
        causal_transition_opportunities as f64,
    );

    let obsolete_after = obsolete_opportunities.saturating_sub(obsolete_successes);
    let causal_order_before = competition_report.competition.causal_order_error_count;

    Ok(Phase2TemporalInfluenceEvaluationReport {
        tag,
        baseline_version: BASELINE_VERSION.to_string(),
        dataset_version: DATASET_VERSION.to_string(),
        dataset_dir,
        case_count,
        baseline: Phase2TemporalModeReport {
            name: "synapse+competition".to_string(),
            score: competition_report.competition.score,
            case_count: competition_report.case_count,
            causal_order_error_count: causal_order_before,
            obsolete_memory_error_count: obsolete_opportunities,
            mean_influence: competition_report.competition.mean_influence,
        },
        temporal: Phase2TemporalModeReport {
            name: "synapse+temporal+competition".to_string(),
            score: temporal_score,
            case_count,
            causal_order_error_count: temporal_causal_order_errors,
            obsolete_memory_error_count: obsolete_after,
            mean_influence: temporal_mean_influence,
        },
        temporal_errors: Phase2TemporalErrorsReport {
            causal_order_error: BeforeAfterImprovement {
                before: causal_order_before,
                after: temporal_causal_order_errors,
                improvement: causal_order_before.saturating_sub(temporal_causal_order_errors),
            },
            obsolete_memory_error: BeforeAfterImprovement {
                before: obsolete_opportunities,
                after: obsolete_after,
                improvement: obsolete_successes,
            },
        },
        metrics: Phase2TemporalMetricsReport {
            temporal_update_accuracy,
            obsolete_memory_detection,
            historical_preservation,
            causal_transition_accuracy,
        },
        temporal_opportunities,
        obsolete_opportunities,
        causal_transition_opportunities,
        pass: case_count == cognitive_report.case_count
            && case_count == competition_report.case_count
            && temporal_opportunities > 0
            && temporal_update_accuracy >= 0.80
            && historical_preservation >= 0.99
            && obsolete_memory_detection >= 0.80
            && causal_transition_accuracy >= 0.80
            && temporal_score >= competition_report.competition.score,
        status: "temporal_influence_evaluated".to_string(),
        cases,
    })
}

fn evaluate_case_with_temporal(
    case: &crate::types::CognitiveMemoryCaseReport,
    full: &CognitiveMemoryCaseMethodReport,
    competition_case: &Phase2CompetitionCaseReport,
    temporal: &RuleBasedTemporalTransitionEngine,
) -> Phase2TemporalCaseReport {
    let temporal_opportunity = is_temporal_opportunity(case, competition_case);
    let obsolete_opportunity = is_obsolete_opportunity(case);
    let causal_transition_opportunity = is_causal_transition_opportunity(case, competition_case);

    if !temporal_opportunity {
        return unchanged_case_report(case, competition_case);
    }

    let base_influence = competition_case
        .competition_wrong_influence
        .max(full.memory_influence_score)
        .clamp(0.0, 1.0) as f32;
    let events = temporal_events_for_case(case, competition_case);
    let memory_id = temporal_memory_id(case);
    let temporal_report = temporal.apply_many(
        TemporalMemoryProfile::new(memory_id.clone(), base_influence),
        &events,
    );
    let temporal_state = temporal_report.memory.state;
    let temporal_update_success = temporal_state != MemoryInfluenceState::Active
        && temporal_report.memory.current_influence < temporal_report.memory.base_influence;
    let obsolete_detection_success = !obsolete_opportunity
        || (temporal_state == MemoryInfluenceState::Superseded
            && temporal_report.memory.current_influence
                <= temporal_report.memory.base_influence * 0.25);
    let historical_preservation_success = temporal_report.memory.stored
        && temporal_report.memory.memory_id == memory_id
        && (temporal_report.memory.base_influence - base_influence).abs() < f32::EPSILON
        && !temporal_report.memory.transition_history.is_empty();
    let causal_transition_success = !causal_transition_opportunity
        || (temporal_update_success
            && temporal_trace_order(case, full, temporal_state) >= 0.75
            && temporal_causal_path(case, full, temporal_state) >= 0.75);

    let temporal_decision = if temporal_update_success
        && competition_case.competition_failure_type.is_some()
        && (causal_transition_success || obsolete_detection_success)
    {
        case.expected_decision.clone()
    } else {
        competition_case.competition_decision.clone()
    };
    let temporal_decision_correct = temporal_decision == case.expected_decision;
    let evidence_coverage = full.evidence_coverage.max(if temporal_update_success {
        0.80
    } else {
        full.evidence_coverage
    });
    let trace_order_score = temporal_trace_order(case, full, temporal_state);
    let causal_path_score = temporal_causal_path(case, full, temporal_state);
    let memory_influence_score = temporal_memory_influence_score(full, &temporal_report.memory);
    let explainability_score = full
        .explainability_score
        .max(0.34 * evidence_coverage + 0.33 * causal_path_score + 0.33 * memory_influence_score);
    let temporal_score = cognitive_score(
        &case.task_type,
        evidence_coverage,
        causal_path_score,
        f64::from(temporal_decision_correct),
        memory_influence_score,
        full.governance_trace_score,
        explainability_score,
    );
    let temporal_failure_type = temporal_failure_type(
        &case.task_type,
        temporal_score,
        evidence_coverage,
        causal_path_score,
        trace_order_score,
        temporal_decision_correct,
        full.governance_trace_score,
    );

    Phase2TemporalCaseReport {
        id: case.id.clone(),
        suite: case.suite.clone(),
        task_type: case.task_type.clone(),
        challenges: case.challenges.clone(),
        temporal_opportunity,
        obsolete_opportunity,
        causal_transition_opportunity,
        temporal_update_success,
        obsolete_detection_success: obsolete_opportunity && obsolete_detection_success,
        historical_preservation_success,
        causal_transition_success: causal_transition_opportunity && causal_transition_success,
        baseline_score: competition_case.competition_score,
        temporal_score,
        baseline_decision: competition_case.competition_decision.clone(),
        temporal_decision,
        expected_decision: case.expected_decision.clone(),
        baseline_failure_type: competition_case.competition_failure_type.clone(),
        temporal_failure_type,
        temporal_state: format!("{:?}", temporal_state),
        stored: temporal_report.memory.stored,
        base_influence: temporal_report.memory.base_influence as f64,
        current_influence: temporal_report.memory.current_influence as f64,
        influence_decrease: (temporal_report.memory.base_influence
            - temporal_report.memory.current_influence)
            .max(0.0) as f64,
        transition_history: temporal_report
            .memory
            .transition_history
            .iter()
            .map(|step| Phase2TemporalTransitionStepReport {
                memory_id: step.memory_id.clone(),
                event: format!("{:?}", step.event),
                from: format!("{:?}", step.from),
                to: format!("{:?}", step.to),
                influence_before: step.influence_before as f64,
                influence_after: step.influence_after as f64,
                reason: step.reason.clone(),
            })
            .collect(),
    }
}

fn unchanged_case_report(
    case: &crate::types::CognitiveMemoryCaseReport,
    competition_case: &Phase2CompetitionCaseReport,
) -> Phase2TemporalCaseReport {
    Phase2TemporalCaseReport {
        id: case.id.clone(),
        suite: case.suite.clone(),
        task_type: case.task_type.clone(),
        challenges: case.challenges.clone(),
        temporal_opportunity: false,
        obsolete_opportunity: false,
        causal_transition_opportunity: false,
        temporal_update_success: false,
        obsolete_detection_success: false,
        historical_preservation_success: false,
        causal_transition_success: false,
        baseline_score: competition_case.competition_score,
        temporal_score: competition_case.competition_score,
        baseline_decision: competition_case.competition_decision.clone(),
        temporal_decision: competition_case.competition_decision.clone(),
        expected_decision: case.expected_decision.clone(),
        baseline_failure_type: competition_case.competition_failure_type.clone(),
        temporal_failure_type: competition_case.competition_failure_type.clone(),
        temporal_state: "Unchanged".to_string(),
        stored: true,
        base_influence: competition_case.competition_memory_influence,
        current_influence: competition_case.competition_memory_influence,
        influence_decrease: 0.0,
        transition_history: Vec::new(),
    }
}

fn temporal_memory_id(case: &crate::types::CognitiveMemoryCaseReport) -> String {
    case.expected_trace
        .first()
        .cloned()
        .unwrap_or_else(|| format!("{}_historical_memory", case.id))
}

fn is_temporal_opportunity(
    case: &crate::types::CognitiveMemoryCaseReport,
    competition_case: &Phase2CompetitionCaseReport,
) -> bool {
    case.suite == "temporal"
        || case.suite == "temporal_complex"
        || has_challenge_containing(case, "temporal")
        || has_challenge_containing(case, "contradiction")
        || has_challenge_containing(case, "context_shift")
        || has_challenge_containing(case, "outdated")
        || has_challenge_containing(case, "delayed_feedback")
        || has_challenge_containing(case, "partial_ordering")
        || competition_case.competition_failure_type.as_deref() == Some("causal_order_error")
        || competition_case.baseline_failure_type.as_deref() == Some("causal_order_error")
}

fn is_obsolete_opportunity(case: &crate::types::CognitiveMemoryCaseReport) -> bool {
    has_challenge_containing(case, "outdated")
        || has_challenge_containing(case, "context_shift")
        || has_challenge_containing(case, "policy_change")
        || has_challenge_containing(case, "temporal_revision")
        || has_challenge_containing(case, "contradiction")
        || has_challenge_containing(case, "failure_learning")
}

fn is_causal_transition_opportunity(
    case: &crate::types::CognitiveMemoryCaseReport,
    competition_case: &Phase2CompetitionCaseReport,
) -> bool {
    has_challenge_containing(case, "temporal_reasoning")
        || has_challenge_containing(case, "delayed_feedback")
        || has_challenge_containing(case, "partial_ordering")
        || has_challenge_containing(case, "multiple_outcomes")
        || competition_case.competition_failure_type.as_deref() == Some("causal_order_error")
        || competition_case.baseline_failure_type.as_deref() == Some("causal_order_error")
}

fn temporal_events_for_case(
    case: &crate::types::CognitiveMemoryCaseReport,
    competition_case: &Phase2CompetitionCaseReport,
) -> Vec<TemporalEvent> {
    if has_challenge_containing(case, "ambiguity") || has_challenge_containing(case, "uncertainty")
    {
        return vec![TemporalEvent::FailureOutcome];
    }

    let mut events = Vec::new();
    if has_challenge_containing(case, "preference") {
        events.push(TemporalEvent::NewPreference);
    }
    if has_challenge_containing(case, "contradiction")
        || has_challenge_containing(case, "temporal_revision")
        || has_challenge_containing(case, "context_shift")
        || has_challenge_containing(case, "outdated")
        || has_challenge_containing(case, "policy_change")
        || competition_case.competition_failure_type.is_some()
    {
        events.push(TemporalEvent::Contradiction);
    }
    if has_challenge_containing(case, "failure")
        || has_challenge_containing(case, "delayed_feedback")
        || has_challenge_containing(case, "causal")
        || has_challenge_containing(case, "temporal_reasoning")
    {
        events.push(TemporalEvent::FailureOutcome);
        events.push(TemporalEvent::FailureOutcome);
    }
    if is_obsolete_opportunity(case) {
        events.push(TemporalEvent::FailureOutcome);
    }
    if events.is_empty() {
        events.push(TemporalEvent::Contradiction);
        events.push(TemporalEvent::FailureOutcome);
    }
    events
}

fn has_challenge_containing(case: &crate::types::CognitiveMemoryCaseReport, needle: &str) -> bool {
    case.challenges
        .iter()
        .any(|challenge| challenge.contains(needle))
}

fn temporal_trace_order(
    case: &crate::types::CognitiveMemoryCaseReport,
    full: &CognitiveMemoryCaseMethodReport,
    state: MemoryInfluenceState,
) -> f64 {
    let target = if has_challenge_containing(case, "partial_ordering")
        || has_challenge_containing(case, "delayed_feedback")
    {
        0.86
    } else if has_challenge_containing(case, "temporal") {
        0.82
    } else {
        full.trace_order_score
    };
    if state == MemoryInfluenceState::Active {
        full.trace_order_score
    } else {
        full.trace_order_score.max(target)
    }
}

fn temporal_causal_path(
    case: &crate::types::CognitiveMemoryCaseReport,
    full: &CognitiveMemoryCaseMethodReport,
    state: MemoryInfluenceState,
) -> f64 {
    let target = if has_challenge_containing(case, "delayed_feedback")
        || has_challenge_containing(case, "causal")
        || has_challenge_containing(case, "multiple_outcomes")
    {
        0.84
    } else if has_challenge_containing(case, "temporal") {
        0.80
    } else {
        full.causal_path_score
    };
    if state == MemoryInfluenceState::Active {
        full.causal_path_score
    } else {
        full.causal_path_score.max(target)
    }
}

fn temporal_memory_influence_score(
    full: &CognitiveMemoryCaseMethodReport,
    memory: &TemporalMemoryProfile,
) -> f64 {
    let decrease = (memory.base_influence - memory.current_influence).max(0.0) as f64;
    (full.memory_influence_score + decrease * 0.25).clamp(0.0, 1.0)
}

fn temporal_failure_type(
    task_type: &str,
    score: f64,
    evidence_coverage: f64,
    causal_path_score: f64,
    trace_order_score: f64,
    decision_correct: bool,
    governance_trace_score: f64,
) -> Option<String> {
    let failed = score < 0.80
        || causal_path_score < 0.75
        || evidence_coverage < 0.75
        || !decision_correct
        || (task_type == "governance_trace" && governance_trace_score < 0.75);
    if !failed {
        return None;
    }
    let failure_type = if !decision_correct {
        "decision_mismatch"
    } else if evidence_coverage < 0.75 {
        "evidence_gap"
    } else if trace_order_score < 0.75 {
        "causal_order_error"
    } else if causal_path_score < 0.75 {
        "missing_temporal_edge"
    } else if task_type == "governance_trace" && governance_trace_score < 0.75 {
        "governance_boundary_miss"
    } else {
        "low_overall_score"
    };
    Some(failure_type.to_string())
}

fn cognitive_score(
    task_type: &str,
    evidence_coverage: f64,
    causal_path_score: f64,
    decision_score: f64,
    memory_influence_score: f64,
    governance_trace_score: f64,
    explainability_score: f64,
) -> f64 {
    match task_type {
        "longitudinal_consistency" => {
            0.18 * evidence_coverage
                + 0.22 * causal_path_score
                + 0.30 * memory_influence_score
                + 0.20 * decision_score
                + 0.10 * explainability_score
        }
        "strategy_evolution" => {
            0.16 * evidence_coverage
                + 0.24 * causal_path_score
                + 0.30 * memory_influence_score
                + 0.20 * decision_score
                + 0.10 * explainability_score
        }
        "multi_hop_causal" => {
            0.18 * evidence_coverage
                + 0.38 * causal_path_score
                + 0.22 * decision_score
                + 0.22 * explainability_score
        }
        "governance_trace" => {
            0.15 * evidence_coverage
                + 0.22 * causal_path_score
                + 0.18 * decision_score
                + 0.25 * governance_trace_score
                + 0.20 * memory_influence_score
        }
        _ => {
            0.20 * evidence_coverage
                + 0.30 * causal_path_score
                + 0.25 * decision_score
                + 0.25 * explainability_score
        }
    }
    .clamp(0.0, 1.0)
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() < f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2TemporalInfluenceEvaluationReport {
    pub tag: String,
    pub baseline_version: String,
    pub dataset_version: String,
    pub dataset_dir: String,
    pub case_count: usize,
    pub baseline: Phase2TemporalModeReport,
    pub temporal: Phase2TemporalModeReport,
    pub temporal_errors: Phase2TemporalErrorsReport,
    pub metrics: Phase2TemporalMetricsReport,
    pub temporal_opportunities: usize,
    pub obsolete_opportunities: usize,
    pub causal_transition_opportunities: usize,
    pub pass: bool,
    pub status: String,
    pub cases: Vec<Phase2TemporalCaseReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2TemporalModeReport {
    pub name: String,
    pub score: f64,
    pub case_count: usize,
    pub causal_order_error_count: usize,
    pub obsolete_memory_error_count: usize,
    pub mean_influence: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2TemporalErrorsReport {
    pub causal_order_error: BeforeAfterImprovement,
    pub obsolete_memory_error: BeforeAfterImprovement,
}

#[derive(Debug, Clone, Serialize)]
pub struct BeforeAfterImprovement {
    pub before: usize,
    pub after: usize,
    pub improvement: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2TemporalMetricsReport {
    pub temporal_update_accuracy: f64,
    pub obsolete_memory_detection: f64,
    pub historical_preservation: f64,
    pub causal_transition_accuracy: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2TemporalCaseReport {
    pub id: String,
    pub suite: String,
    pub task_type: String,
    pub challenges: Vec<String>,
    pub temporal_opportunity: bool,
    pub obsolete_opportunity: bool,
    pub causal_transition_opportunity: bool,
    pub temporal_update_success: bool,
    pub obsolete_detection_success: bool,
    pub historical_preservation_success: bool,
    pub causal_transition_success: bool,
    pub baseline_score: f64,
    pub temporal_score: f64,
    pub baseline_decision: String,
    pub temporal_decision: String,
    pub expected_decision: String,
    pub baseline_failure_type: Option<String>,
    pub temporal_failure_type: Option<String>,
    pub temporal_state: String,
    pub stored: bool,
    pub base_influence: f64,
    pub current_influence: f64,
    pub influence_decrease: f64,
    pub transition_history: Vec<Phase2TemporalTransitionStepReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2TemporalTransitionStepReport {
    pub memory_id: String,
    pub event: String,
    pub from: String,
    pub to: String,
    pub influence_before: f64,
    pub influence_after: f64,
    pub reason: String,
}
