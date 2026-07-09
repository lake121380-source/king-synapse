use crate::phase3_lesson_promotion::{LessonPromotionTrace, Phase3LessonPromotionEvaluator};
use anyhow::Result;
use chrono::Utc;
use serde::Serialize;

const EVALUATION_VERSION: &str = "phase3.4-future-influence-experiment";
const BASELINE_VERSION: &str = "phase3.3-controlled-lesson-promotion";

pub struct Phase3FutureInfluenceEvaluator;

impl Phase3FutureInfluenceEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase3FutureInfluenceReport> {
        let promotion_report =
            Phase3LessonPromotionEvaluator::evaluate("phase3-future-influence-promotion-source")?;
        Ok(evaluate_future_influence(
            tag.into(),
            &promotion_report.traces,
        ))
    }
}

fn evaluate_future_influence(
    tag: String,
    promoted_lessons: &[LessonPromotionTrace],
) -> Phase3FutureInfluenceReport {
    let scenarios = influence_scenarios();
    let traces = scenarios
        .iter()
        .map(|scenario| evaluate_scenario(scenario, promoted_lessons))
        .collect::<Vec<FutureInfluenceTrace>>();

    let helpful_lessons = traces
        .iter()
        .filter(|trace| trace.result_kind == "HelpfulLesson")
        .count();
    let neutral_lessons = traces
        .iter()
        .filter(|trace| trace.result_kind == "NeutralLesson")
        .count();
    let rejected_influence = traces
        .iter()
        .filter(|trace| trace.result_kind == "RejectedInfluence")
        .count();

    let safety = FutureInfluenceSafetyReport {
        memory_written: false,
        lesson_persisted: false,
        playbook_created: false,
        future_influence_changed: false,
    };
    let no_write_safe = traces.iter().all(|trace| {
        trace.influence_safe
            && !trace.memory_written
            && !trace.lesson_persisted
            && !trace.playbook_created
            && !trace.future_influence_changed
    }) && !safety.memory_written
        && !safety.lesson_persisted
        && !safety.playbook_created
        && !safety.future_influence_changed;

    let metrics = Phase3FutureInfluenceMetrics {
        influence_gain_score: mean_score(&traces, |trace| trace.improvement.max(0.0)),
        decision_improvement_score: safe_div(
            traces
                .iter()
                .filter(|trace| trace.influenced_score > trace.baseline_score)
                .count() as f32,
            traces.len() as f32,
        ),
        failure_reduction_score: safe_div(
            traces
                .iter()
                .filter(|trace| trace.baseline_failure && !trace.influenced_failure)
                .count() as f32,
            traces.iter().filter(|trace| trace.baseline_failure).count() as f32,
        ),
        lesson_usefulness_score: safe_div(
            traces.iter().filter(|trace| trace.lesson_useful).count() as f32,
            traces.len() as f32,
        ),
        no_write_safety: f32::from(no_write_safe),
    };

    let pass = traces.len() == scenarios.len()
        && helpful_lessons == 1
        && neutral_lessons == 1
        && rejected_influence == 1
        && metrics.influence_gain_score > 0.0
        && metrics.decision_improvement_score > 0.0
        && metrics.failure_reduction_score > 0.0
        && metrics.lesson_usefulness_score >= 0.66
        && metrics.no_write_safety >= 1.0;

    Phase3FutureInfluenceReport {
        tag,
        phase: "3.4".to_string(),
        mode: "evaluation_only".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        scenarios: traces.len(),
        promoted_lesson_source_count: promoted_lessons
            .iter()
            .filter(|trace| trace.status != "NotPromoted")
            .count(),
        mechanism_changed: false,
        schema_changed: false,
        retrieval_changed: false,
        activation_changed: false,
        temporal_lifecycle_changed: false,
        governance_changed: false,
        results: FutureInfluenceResultsReport {
            helpful_lessons,
            neutral_lessons,
            rejected_influence,
        },
        metrics,
        safety,
        pass,
        status: "future_influence_evaluated".to_string(),
        traces,
    }
}

fn evaluate_scenario(
    scenario: &FutureInfluenceScenario,
    promoted_lessons: &[LessonPromotionTrace],
) -> FutureInfluenceTrace {
    let promoted_lesson = promoted_lessons
        .iter()
        .find(|lesson| lesson.candidate_id == scenario.promoted_lesson_id);
    let promoted_lesson_available = promoted_lesson
        .map(|lesson| lesson.status != "NotPromoted")
        .unwrap_or(false);
    let lesson_used = promoted_lesson_available && scenario.influence_action == "use_lesson";
    let influence_rejected =
        promoted_lesson_available && scenario.influence_action == "reject_outdated";
    let influenced_score = if promoted_lesson_available {
        scenario.influenced_score
    } else {
        scenario.baseline_score
    };
    let influenced_decision = if promoted_lesson_available {
        scenario.influenced_decision
    } else {
        scenario.baseline_decision
    };
    let influenced_failure = if promoted_lesson_available {
        scenario.influenced_failure
    } else {
        scenario.baseline_failure
    };
    let improvement = influenced_score - scenario.baseline_score;
    let influence_safe = promoted_lesson_available
        && improvement >= 0.0
        && (lesson_used || !scenario.expect_lesson_use)
        && (!scenario.expect_rejection || influence_rejected);

    FutureInfluenceTrace {
        scenario_id: scenario.id.to_string(),
        query: scenario.query.to_string(),
        existing_context: scenario.existing_context.to_string(),
        baseline_decision: scenario.baseline_decision.to_string(),
        influenced_decision: influenced_decision.to_string(),
        promoted_lesson_id: scenario.promoted_lesson_id.to_string(),
        promoted_lesson_status: promoted_lesson
            .map(|lesson| lesson.status.clone())
            .unwrap_or_else(|| "Missing".to_string()),
        lesson_text: promoted_lesson.and_then(|lesson| lesson.lesson.clone()),
        lesson_used,
        baseline_score: scenario.baseline_score,
        influenced_score,
        improvement,
        baseline_failure: scenario.baseline_failure,
        influenced_failure,
        failure_reduced: scenario.baseline_failure && !influenced_failure,
        lesson_useful: influence_safe
            && (improvement > 0.0 || scenario.result_kind == "NeutralLesson")
            && promoted_lesson_available,
        influence_action: scenario.influence_action.to_string(),
        result_kind: scenario.result_kind.to_string(),
        influence_safe,
        memory_written: false,
        lesson_persisted: false,
        playbook_created: false,
        future_influence_changed: false,
        trace_notes: trace_notes(scenario, promoted_lesson_available, influence_rejected),
    }
}

fn trace_notes(
    scenario: &FutureInfluenceScenario,
    promoted_lesson_available: bool,
    influence_rejected: bool,
) -> Vec<String> {
    let mut notes = vec![
        "evaluation only: no memory write".to_string(),
        "evaluation only: no playbook creation".to_string(),
        "evaluation only: no runtime future influence mutation".to_string(),
    ];
    if promoted_lesson_available {
        notes.push("promoted lesson candidate loaded from Phase 3.3 report state".to_string());
    } else {
        notes.push("promoted lesson candidate was unavailable in Phase 3.3 source".to_string());
    }
    if influence_rejected {
        notes.push("outdated lesson influence rejected by scenario evidence".to_string());
    }
    notes.push(format!("scenario kind: {}", scenario.result_kind));
    notes
}

fn influence_scenarios() -> Vec<FutureInfluenceScenario> {
    vec![
        FutureInfluenceScenario {
            id: "future_influence_001_helpful_gpu_lesson",
            query: "Deploy a large model on a GPU-constrained workstation.",
            existing_context: "The rollout is urgent, but prior deployment context is incomplete.",
            promoted_lesson_id: "reflection_obs_001_gpu_deployment_failure",
            baseline_decision: "Deploy with default batch size and react if runtime fails.",
            influenced_decision: "Check GPU memory footprint, lower batch size, then deploy.",
            baseline_score: 0.45,
            influenced_score: 0.90,
            baseline_failure: true,
            influenced_failure: false,
            influence_action: "use_lesson",
            result_kind: "HelpfulLesson",
            expect_lesson_use: true,
            expect_rejection: false,
        },
        FutureInfluenceScenario {
            id: "future_influence_002_irrelevant_gpu_lesson",
            query: "Diagnose a database write permission failure.",
            existing_context: "The runtime user cannot write to the database.",
            promoted_lesson_id: "reflection_obs_001_gpu_deployment_failure",
            baseline_decision: "Inspect database grants for the runtime user.",
            influenced_decision: "Inspect database grants for the runtime user.",
            baseline_score: 0.78,
            influenced_score: 0.78,
            baseline_failure: false,
            influenced_failure: false,
            influence_action: "ignore_irrelevant",
            result_kind: "NeutralLesson",
            expect_lesson_use: false,
            expect_rejection: false,
        },
        FutureInfluenceScenario {
            id: "future_influence_003_outdated_docker_lesson",
            query: "Repair Docker build failures after moving to a remote builder.",
            existing_context: "Old local disk cleanup did not fix the issue; remote cache auth fixed the next build.",
            promoted_lesson_id: "reflection_obs_005_local_docker_disk_scope",
            baseline_decision: "Repeat the old local disk cleanup before checking the remote builder.",
            influenced_decision: "Reduce the old local disk lesson and inspect remote builder cache auth.",
            baseline_score: 0.40,
            influenced_score: 0.82,
            baseline_failure: true,
            influenced_failure: false,
            influence_action: "reject_outdated",
            result_kind: "RejectedInfluence",
            expect_lesson_use: false,
            expect_rejection: true,
        },
    ]
}

fn mean_score<F>(traces: &[FutureInfluenceTrace], score: F) -> f32
where
    F: Fn(&FutureInfluenceTrace) -> f32,
{
    safe_div(traces.iter().map(score).sum::<f32>(), traces.len() as f32)
}

fn safe_div(numerator: f32, denominator: f32) -> f32 {
    if denominator.abs() < f32::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone)]
struct FutureInfluenceScenario {
    id: &'static str,
    query: &'static str,
    existing_context: &'static str,
    promoted_lesson_id: &'static str,
    baseline_decision: &'static str,
    influenced_decision: &'static str,
    baseline_score: f32,
    influenced_score: f32,
    baseline_failure: bool,
    influenced_failure: bool,
    influence_action: &'static str,
    result_kind: &'static str,
    expect_lesson_use: bool,
    expect_rejection: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase3FutureInfluenceReport {
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub scenarios: usize,
    pub promoted_lesson_source_count: usize,
    pub mechanism_changed: bool,
    pub schema_changed: bool,
    pub retrieval_changed: bool,
    pub activation_changed: bool,
    pub temporal_lifecycle_changed: bool,
    pub governance_changed: bool,
    pub results: FutureInfluenceResultsReport,
    pub metrics: Phase3FutureInfluenceMetrics,
    pub safety: FutureInfluenceSafetyReport,
    pub pass: bool,
    pub status: String,
    pub traces: Vec<FutureInfluenceTrace>,
}

#[derive(Debug, Clone, Serialize)]
pub struct FutureInfluenceResultsReport {
    pub helpful_lessons: usize,
    pub neutral_lessons: usize,
    pub rejected_influence: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase3FutureInfluenceMetrics {
    pub influence_gain_score: f32,
    pub decision_improvement_score: f32,
    pub failure_reduction_score: f32,
    pub lesson_usefulness_score: f32,
    pub no_write_safety: f32,
}

#[derive(Debug, Clone, Serialize)]
pub struct FutureInfluenceSafetyReport {
    pub memory_written: bool,
    pub lesson_persisted: bool,
    pub playbook_created: bool,
    pub future_influence_changed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct FutureInfluenceTrace {
    pub scenario_id: String,
    pub query: String,
    pub existing_context: String,
    pub baseline_decision: String,
    pub influenced_decision: String,
    pub promoted_lesson_id: String,
    pub promoted_lesson_status: String,
    pub lesson_text: Option<String>,
    pub lesson_used: bool,
    pub baseline_score: f32,
    pub influenced_score: f32,
    pub improvement: f32,
    pub baseline_failure: bool,
    pub influenced_failure: bool,
    pub failure_reduced: bool,
    pub lesson_useful: bool,
    pub influence_action: String,
    pub result_kind: String,
    pub influence_safe: bool,
    pub memory_written: bool,
    pub lesson_persisted: bool,
    pub playbook_created: bool,
    pub future_influence_changed: bool,
    pub trace_notes: Vec<String>,
}
