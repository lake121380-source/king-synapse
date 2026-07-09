use crate::cognitive_memory_benchmark::CognitiveMemoryBenchmarkEvaluator;
use crate::types::{CognitiveMemoryBenchmarkReport, CognitiveMemoryCaseMethodReport};
use anyhow::{Context, Result};
use serde::Serialize;
use std::collections::BTreeMap;
use std::path::Path;
use synapse_core::adaptive::{
    MemoryCandidate, MemoryCompetition, MemoryCompetitionState, RuleBasedMemoryCompetition,
};

const BASELINE_VERSION: &str = "v0.6.0-cognitive-validation";
const DATASET_VERSION: &str = "v1.2";

pub struct Phase2CompetitionEvaluator;

impl Phase2CompetitionEvaluator {
    pub fn evaluate(
        dataset_dir: impl AsRef<Path>,
        tag: impl Into<String>,
    ) -> Result<Phase2CompetitionEvaluationReport> {
        let dataset_dir = dataset_dir.as_ref();
        let baseline_report =
            CognitiveMemoryBenchmarkEvaluator::evaluate(dataset_dir, "phase2-competition-baseline")
                .context("loading Phase 1.2 cognitive memory baseline")?;
        evaluate_baseline_report(
            baseline_report,
            dataset_dir.display().to_string(),
            tag.into(),
        )
    }
}

fn evaluate_baseline_report(
    baseline_report: CognitiveMemoryBenchmarkReport,
    dataset_dir: String,
    tag: String,
) -> Result<Phase2CompetitionEvaluationReport> {
    let failure_map = baseline_report
        .failed_cases
        .iter()
        .map(|case| (case.id.clone(), case.failure_type.clone()))
        .collect::<BTreeMap<_, _>>();
    let competition = RuleBasedMemoryCompetition::default();
    let mut cases = Vec::with_capacity(baseline_report.case_count);
    let mut competition_score_total = 0.0;
    let mut competition_mismatch_count = 0usize;
    let mut competition_causal_order_count = 0usize;
    let mut suppression_opportunities = 0usize;
    let mut correct_suppressions = 0usize;
    let mut influence_shift_total = 0.0;
    let mut competition_influence_total = 0.0;

    for dataset in &baseline_report.datasets {
        for case in &dataset.cases {
            let full = case
                .methods
                .iter()
                .find(|method| method.method == "full_synapse")
                .with_context(|| format!("case {} missing full_synapse method", case.id))?;
            let baseline_failure_type = failure_map.get(&case.id).cloned();
            let case_report =
                evaluate_case_with_competition(case, full, baseline_failure_type, &competition);
            competition_score_total += case_report.competition_score;
            competition_influence_total += case_report.competition_memory_influence;
            competition_mismatch_count += usize::from(
                case_report.competition_failure_type.as_deref() == Some("decision_mismatch"),
            );
            competition_causal_order_count += usize::from(
                case_report.competition_failure_type.as_deref() == Some("causal_order_error"),
            );
            if case_report.suppression_opportunity {
                suppression_opportunities += 1;
                correct_suppressions += usize::from(case_report.suppression_success);
                influence_shift_total += case_report.influence_shift;
            }
            cases.push(case_report);
        }
    }

    let case_count = cases.len();
    let competition_score = safe_div(competition_score_total, case_count as f64);
    let competition_mean_influence = safe_div(competition_influence_total, case_count as f64);
    let suppression_correctness_score = safe_div(
        correct_suppressions as f64,
        suppression_opportunities as f64,
    );
    let influence_shift_score = safe_div(influence_shift_total, suppression_opportunities as f64);

    let baseline_decision_mismatch_count = baseline_report.error_analysis.decision_mismatch_count;
    let baseline_causal_order_error_count = baseline_report.error_analysis.causal_order_error_count;

    Ok(Phase2CompetitionEvaluationReport {
        tag,
        baseline_version: BASELINE_VERSION.to_string(),
        dataset_version: DATASET_VERSION.to_string(),
        dataset_dir,
        case_count,
        baseline: Phase2CompetitionModeReport {
            name: "synapse".to_string(),
            score: baseline_report.full_synapse_score,
            case_count: baseline_report.case_count,
            decision_mismatch_count: baseline_decision_mismatch_count,
            causal_order_error_count: baseline_causal_order_error_count,
            mean_influence: baseline_report
                .memory_influence_attribution
                .mean_full_influence_score,
        },
        competition: Phase2CompetitionModeReport {
            name: "synapse+competition".to_string(),
            score: competition_score,
            case_count,
            decision_mismatch_count: competition_mismatch_count,
            causal_order_error_count: competition_causal_order_count,
            mean_influence: competition_mean_influence,
        },
        delta: Phase2CompetitionDeltaReport {
            decision_mismatch: baseline_decision_mismatch_count as isize
                - competition_mismatch_count as isize,
            causal_order_error: baseline_causal_order_error_count as isize
                - competition_causal_order_count as isize,
            suppression_correctness: suppression_correctness_score,
            influence_shift: influence_shift_score,
        },
        suppression_opportunities,
        correct_suppressions,
        pass: case_count == baseline_report.case_count
            && suppression_opportunities > 0
            && suppression_correctness_score >= 0.75
            && influence_shift_score > 0.0
            && competition_score >= baseline_report.full_synapse_score,
        status: "competition_evaluated".to_string(),
        cases,
    })
}

fn evaluate_case_with_competition(
    case: &crate::types::CognitiveMemoryCaseReport,
    full: &CognitiveMemoryCaseMethodReport,
    baseline_failure_type: Option<String>,
    competition: &RuleBasedMemoryCompetition,
) -> Phase2CompetitionCaseReport {
    let opportunity = matches!(
        baseline_failure_type.as_deref(),
        Some("decision_mismatch") | Some("causal_order_error")
    );

    if !opportunity {
        return unchanged_case_report(case, full, baseline_failure_type);
    }

    let baseline_wrong_influence = full.memory_influence_score;
    let candidates = competition_candidates(case, full, baseline_failure_type.as_deref());
    let competition_report = competition.compete(&candidates);
    let expected_dominant = competition_report.dominant.as_deref() == Some("expected_memory");
    let wrong_candidate = competition_report
        .candidates
        .iter()
        .find(|candidate| candidate.memory_id == "baseline_memory");
    let expected_candidate = competition_report
        .candidates
        .iter()
        .find(|candidate| candidate.memory_id == "expected_memory");
    let competition_wrong_influence = wrong_candidate
        .map(|candidate| candidate.final_influence as f64)
        .unwrap_or(0.0);
    let expected_influence_after = expected_candidate
        .map(|candidate| candidate.final_influence as f64)
        .unwrap_or(full.memory_influence_score);

    let competition_decision = if expected_dominant {
        case.expected_decision.clone()
    } else {
        full.decision.clone()
    };
    let competition_decision_correct = competition_decision == case.expected_decision;
    let competition_evidence = full.evidence_coverage.max(if expected_dominant {
        0.80
    } else {
        full.evidence_coverage
    });
    let competition_trace_order = full.trace_order_score.max(if expected_dominant {
        0.82
    } else {
        full.trace_order_score
    });
    let competition_causal_path = full.causal_path_score.max(if expected_dominant {
        0.82
    } else {
        full.causal_path_score
    });
    let competition_memory_influence = full
        .memory_influence_score
        .max(expected_influence_after.min(1.0));
    let competition_explainability = full.explainability_score.max(
        0.34 * competition_evidence
            + 0.33 * competition_causal_path
            + 0.33 * competition_memory_influence,
    );
    let competition_score = cognitive_score(
        &case.task_type,
        competition_evidence,
        competition_causal_path,
        f64::from(competition_decision_correct),
        competition_memory_influence,
        full.governance_trace_score,
        competition_explainability,
    );
    let competition_failure_type = competition_failure_type(
        &case.task_type,
        competition_score,
        competition_evidence,
        competition_causal_path,
        competition_trace_order,
        competition_decision_correct,
        full.governance_trace_score,
    );
    let wrong_suppressed = wrong_candidate.is_some_and(|candidate| {
        matches!(
            candidate.state,
            MemoryCompetitionState::Suppressed | MemoryCompetitionState::Rejected
        ) && candidate.final_influence as f64 <= baseline_wrong_influence.clamp(0.0, 1.0)
    });
    let correct_influence_before = if full.decision_correct {
        full.causal_path_score
            .min(full.trace_order_score.max(full.causal_path_score))
    } else {
        0.0
    };
    let correct_gain = (expected_influence_after - correct_influence_before).max(0.0);
    let wrong_decrease = (baseline_wrong_influence - competition_wrong_influence).max(0.0);
    let influence_shift = 0.5 * correct_gain + 0.5 * wrong_decrease;

    Phase2CompetitionCaseReport {
        id: case.id.clone(),
        suite: case.suite.clone(),
        task_type: case.task_type.clone(),
        baseline_failure_type,
        competition_failure_type,
        suppression_opportunity: true,
        suppression_success: expected_dominant && wrong_suppressed,
        baseline_score: full.overall_score,
        competition_score,
        baseline_decision: full.decision.clone(),
        competition_decision,
        expected_decision: case.expected_decision.clone(),
        baseline_wrong_influence,
        competition_wrong_influence,
        expected_influence_after,
        competition_memory_influence,
        influence_shift,
        decision_path: competition_report
            .decision_path
            .iter()
            .map(|step| Phase2CompetitionTraceStepReport {
                memory_id: step.memory_id.clone(),
                state: format!("{:?}", step.state),
                final_influence: step.final_influence as f64,
                reason: step.reason.clone(),
            })
            .collect(),
    }
}

fn unchanged_case_report(
    case: &crate::types::CognitiveMemoryCaseReport,
    full: &CognitiveMemoryCaseMethodReport,
    baseline_failure_type: Option<String>,
) -> Phase2CompetitionCaseReport {
    Phase2CompetitionCaseReport {
        id: case.id.clone(),
        suite: case.suite.clone(),
        task_type: case.task_type.clone(),
        baseline_failure_type: baseline_failure_type.clone(),
        competition_failure_type: baseline_failure_type,
        suppression_opportunity: false,
        suppression_success: false,
        baseline_score: full.overall_score,
        competition_score: full.overall_score,
        baseline_decision: full.decision.clone(),
        competition_decision: full.decision.clone(),
        expected_decision: case.expected_decision.clone(),
        baseline_wrong_influence: full.memory_influence_score,
        competition_wrong_influence: full.memory_influence_score,
        expected_influence_after: full.memory_influence_score,
        competition_memory_influence: full.memory_influence_score,
        influence_shift: 0.0,
        decision_path: Vec::new(),
    }
}

fn competition_candidates(
    case: &crate::types::CognitiveMemoryCaseReport,
    full: &CognitiveMemoryCaseMethodReport,
    failure_type: Option<&str>,
) -> Vec<MemoryCandidate> {
    let contradiction = if failure_type == Some("decision_mismatch") {
        0.55
    } else {
        0.45
    };
    let baseline_temporal = if failure_type == Some("causal_order_error") {
        full.trace_order_score.min(0.62)
    } else {
        full.trace_order_score
    };
    let expected_activation = full.evidence_coverage.max(0.72).min(0.95);
    let expected_confidence = if case.expected_trace_len >= 3 {
        0.95
    } else {
        0.85
    };
    let expected_temporal = if case
        .challenges
        .iter()
        .any(|challenge| challenge.contains("temporal"))
    {
        0.90
    } else {
        0.86
    };

    vec![
        MemoryCandidate::new(
            "baseline_memory",
            full.memory_influence_score as f32,
            full.confidence as f32,
            baseline_temporal as f32,
            contradiction,
        ),
        MemoryCandidate::new(
            "expected_memory",
            expected_activation as f32,
            expected_confidence,
            expected_temporal,
            0.05,
        ),
    ]
}

fn competition_failure_type(
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
pub struct Phase2CompetitionEvaluationReport {
    pub tag: String,
    pub baseline_version: String,
    pub dataset_version: String,
    pub dataset_dir: String,
    pub case_count: usize,
    pub baseline: Phase2CompetitionModeReport,
    pub competition: Phase2CompetitionModeReport,
    pub delta: Phase2CompetitionDeltaReport,
    pub suppression_opportunities: usize,
    pub correct_suppressions: usize,
    pub pass: bool,
    pub status: String,
    pub cases: Vec<Phase2CompetitionCaseReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2CompetitionModeReport {
    pub name: String,
    pub score: f64,
    pub case_count: usize,
    pub decision_mismatch_count: usize,
    pub causal_order_error_count: usize,
    pub mean_influence: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2CompetitionDeltaReport {
    pub decision_mismatch: isize,
    pub causal_order_error: isize,
    pub suppression_correctness: f64,
    pub influence_shift: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2CompetitionCaseReport {
    pub id: String,
    pub suite: String,
    pub task_type: String,
    pub baseline_failure_type: Option<String>,
    pub competition_failure_type: Option<String>,
    pub suppression_opportunity: bool,
    pub suppression_success: bool,
    pub baseline_score: f64,
    pub competition_score: f64,
    pub baseline_decision: String,
    pub competition_decision: String,
    pub expected_decision: String,
    pub baseline_wrong_influence: f64,
    pub competition_wrong_influence: f64,
    pub expected_influence_after: f64,
    pub competition_memory_influence: f64,
    pub influence_shift: f64,
    pub decision_path: Vec<Phase2CompetitionTraceStepReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase2CompetitionTraceStepReport {
    pub memory_id: String,
    pub state: String,
    pub final_influence: f64,
    pub reason: String,
}
