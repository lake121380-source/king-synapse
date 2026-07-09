use crate::phase3_reflection_observation::{
    Phase3ReflectionObservationEvaluator, ReflectionTraceReport,
};
use anyhow::Result;
use chrono::Utc;
use serde::Serialize;

const EVALUATION_VERSION: &str = "phase3.2-lesson-candidate-evaluation";
const BASELINE_VERSION: &str = "phase3.1-reflection-observation";

pub struct Phase3LessonCandidateEvaluator;

impl Phase3LessonCandidateEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase3LessonCandidateEvaluationReport> {
        let observation = Phase3ReflectionObservationEvaluator::evaluate(
            "phase3-lesson-candidate-observation-source",
        )?;
        Ok(evaluate_candidates(tag.into(), &observation.traces))
    }
}

fn evaluate_candidates(
    tag: String,
    traces: &[ReflectionTraceReport],
) -> Phase3LessonCandidateEvaluationReport {
    let candidates = traces
        .iter()
        .map(evaluate_trace)
        .collect::<Vec<LessonCandidateReport>>();
    let accepted = candidates
        .iter()
        .filter(|candidate| candidate.evaluation_decision == "AcceptCandidate")
        .count();
    let observe_more = candidates
        .iter()
        .filter(|candidate| candidate.evaluation_decision == "ObserveMore")
        .count();
    let rejected = candidates
        .iter()
        .filter(|candidate| candidate.evaluation_decision == "RejectCandidate")
        .count();
    let accepted_candidates = candidates
        .iter()
        .filter(|candidate| candidate.evaluation_decision == "AcceptCandidate")
        .collect::<Vec<_>>();
    let candidate_opportunities = candidates
        .iter()
        .filter(|candidate| candidate.has_lesson_candidate)
        .count();
    let safe = candidates.iter().all(|candidate| {
        !candidate.lesson_persisted
            && !candidate.playbook_created
            && !candidate.future_influence_changed
            && candidate.promotion_status == "not_promoted"
    });

    let metrics = Phase3LessonCandidateMetrics {
        lesson_grounding_score: mean_score(&candidates, |candidate| candidate.grounding_score),
        lesson_scope_score: mean_score(&candidates, |candidate| candidate.scope_score),
        contradiction_resistance_score: mean_score(&candidates, |candidate| {
            candidate.contradiction_resistance_score
        }),
        overgeneralization_guard_score: mean_score(&candidates, |candidate| {
            f64::from(candidate.overgeneralization_guard)
        }),
        candidate_accept_precision: safe_div(
            accepted_candidates
                .iter()
                .filter(|candidate| candidate.expected_decision == "AcceptCandidate")
                .count() as f64,
            accepted_candidates.len() as f64,
        ),
        candidate_decision_agreement: safe_div(
            candidates
                .iter()
                .filter(|candidate| candidate.evaluation_decision == candidate.expected_decision)
                .count() as f64,
            candidates.len() as f64,
        ),
        promotion_safety: f64::from(safe),
    };

    let pass = candidates.len() == traces.len()
        && candidate_opportunities > 0
        && metrics.lesson_grounding_score >= 0.80
        && metrics.lesson_scope_score >= 0.80
        && metrics.contradiction_resistance_score >= 0.80
        && metrics.overgeneralization_guard_score >= 0.80
        && metrics.candidate_accept_precision >= 0.80
        && metrics.candidate_decision_agreement >= 0.80
        && metrics.promotion_safety >= 1.0;

    Phase3LessonCandidateEvaluationReport {
        tag,
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        source_trace_count: traces.len(),
        candidate_count: candidates.len(),
        candidate_opportunities,
        accepted,
        observe_more,
        rejected,
        mechanism_changed: false,
        schema_changed: false,
        retrieval_changed: false,
        activation_changed: false,
        temporal_lifecycle_changed: false,
        governance_changed: false,
        lesson_persisted: false,
        playbook_created: false,
        future_influence_changed: false,
        implementation_status: "evaluation_only".to_string(),
        metrics,
        pass,
        status: "lesson_candidates_evaluated".to_string(),
        candidates,
    }
}

fn evaluate_trace(trace: &ReflectionTraceReport) -> LessonCandidateReport {
    let has_lesson_candidate = trace.lesson_candidate.is_some();
    let grounding_score = grounding_score(trace);
    let scope_score = scope_score(trace);
    let contradiction_resistance_score = contradiction_resistance_score(trace);
    let confidence = candidate_confidence(trace, grounding_score, scope_score);
    let evaluation_decision = evaluation_decision(
        trace,
        grounding_score,
        scope_score,
        contradiction_resistance_score,
        confidence,
    );
    let expected_decision = expected_decision(trace);

    LessonCandidateReport {
        source_experience_id: trace.experience_id.clone(),
        source_action: trace.observed_action.clone(),
        has_lesson_candidate,
        lesson: trace.lesson_candidate.clone(),
        evidence_count: trace.supporting_events.len(),
        supporting_events: trace.supporting_events.clone(),
        contradicting_events: trace.contradicting_events.clone(),
        confidence,
        scope: trace.lesson_scope.clone(),
        grounding_score,
        scope_score,
        contradiction_resistance_score,
        overgeneralization_guard: trace.overgeneralization_guard && trace.lesson_scope != "global",
        evaluation_decision: evaluation_decision.to_string(),
        expected_decision: expected_decision.to_string(),
        promotion_status: "not_promoted".to_string(),
        lesson_persisted: false,
        playbook_created: false,
        future_influence_changed: false,
        evaluation_notes: evaluation_notes(trace, evaluation_decision),
    }
}

fn grounding_score(trace: &ReflectionTraceReport) -> f64 {
    if trace.lesson_candidate.is_none() {
        return if trace.observed_action == "Ignore" {
            1.0
        } else {
            0.70
        };
    }
    let evidence = trace.supporting_events.len() as f64;
    let has_failure_pattern = trace.failure_pattern.is_some();
    let grounded = trace.grounding_status == "grounded";
    (0.35 * f64::from(grounded)
        + 0.35 * (evidence / 3.0).min(1.0)
        + 0.30 * f64::from(has_failure_pattern))
    .clamp(0.0, 1.0)
}

fn scope_score(trace: &ReflectionTraceReport) -> f64 {
    if trace.lesson_candidate.is_none() {
        return if trace.observed_action == "Ignore" {
            1.0
        } else {
            0.75
        };
    }
    let scoped = trace.lesson_scope != "global" && trace.lesson_scope != "none";
    let specific_scope = trace.lesson_scope.contains('_') || trace.lesson_scope.len() >= 12;
    (0.55 * f64::from(scoped)
        + 0.25 * f64::from(specific_scope)
        + 0.20 * f64::from(trace.overgeneralization_guard))
    .clamp(0.0, 1.0)
}

fn contradiction_resistance_score(trace: &ReflectionTraceReport) -> f64 {
    if trace.contradicting_events.is_empty() {
        return 1.0;
    }
    if trace.lesson_candidate.is_none() && trace.observed_action == "Observe" {
        1.0
    } else {
        0.40
    }
}

fn candidate_confidence(trace: &ReflectionTraceReport, grounding: f64, scope: f64) -> f64 {
    let contradiction_penalty = if trace.contradicting_events.is_empty() {
        0.0
    } else {
        0.25
    };
    (0.45 * trace.confidence + 0.30 * grounding + 0.25 * scope - contradiction_penalty)
        .clamp(0.0, 1.0)
}

fn evaluation_decision(
    trace: &ReflectionTraceReport,
    grounding: f64,
    scope: f64,
    contradiction: f64,
    confidence: f64,
) -> &'static str {
    if trace.lesson_candidate.is_some()
        && trace.supporting_events.len() >= 2
        && trace.contradicting_events.is_empty()
        && grounding >= 0.75
        && scope >= 0.75
        && confidence >= 0.70
    {
        "AcceptCandidate"
    } else if trace.observed_action == "Ignore"
        || (trace.lesson_candidate.is_none() && trace.supporting_events.is_empty())
    {
        "RejectCandidate"
    } else if contradiction < 0.75 || trace.lesson_candidate.is_none() {
        "ObserveMore"
    } else {
        "ObserveMore"
    }
}

fn expected_decision(trace: &ReflectionTraceReport) -> &'static str {
    match trace.experience_id.as_str() {
        "reflection_obs_001_gpu_deployment_failure"
        | "reflection_obs_004_repeated_permission_failure"
        | "reflection_obs_005_local_docker_disk_scope" => "AcceptCandidate",
        "reflection_obs_002_routine_success" => "RejectCandidate",
        _ => "ObserveMore",
    }
}

fn evaluation_notes(trace: &ReflectionTraceReport, decision: &str) -> Vec<String> {
    let mut notes = vec![
        "evaluation only: lesson not persisted".to_string(),
        "evaluation only: playbook not created".to_string(),
        "evaluation only: future influence not changed".to_string(),
    ];
    match decision {
        "AcceptCandidate" => notes.push(format!(
            "candidate passed grounding and scope checks with {} supporting events",
            trace.supporting_events.len()
        )),
        "ObserveMore" => {
            notes.push("candidate needs more evidence before promotion".to_string());
            if !trace.contradicting_events.is_empty() {
                notes.push("contradicting evidence prevents acceptance".to_string());
            }
        }
        _ => notes.push("no useful lesson candidate accepted".to_string()),
    }
    notes
}

fn mean_score<F>(candidates: &[LessonCandidateReport], score: F) -> f64
where
    F: Fn(&LessonCandidateReport) -> f64,
{
    safe_div(
        candidates.iter().map(score).sum::<f64>(),
        candidates.len() as f64,
    )
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() < f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase3LessonCandidateEvaluationReport {
    pub tag: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub source_trace_count: usize,
    pub candidate_count: usize,
    pub candidate_opportunities: usize,
    pub accepted: usize,
    pub observe_more: usize,
    pub rejected: usize,
    pub mechanism_changed: bool,
    pub schema_changed: bool,
    pub retrieval_changed: bool,
    pub activation_changed: bool,
    pub temporal_lifecycle_changed: bool,
    pub governance_changed: bool,
    pub lesson_persisted: bool,
    pub playbook_created: bool,
    pub future_influence_changed: bool,
    pub implementation_status: String,
    pub metrics: Phase3LessonCandidateMetrics,
    pub pass: bool,
    pub status: String,
    pub candidates: Vec<LessonCandidateReport>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase3LessonCandidateMetrics {
    pub lesson_grounding_score: f64,
    pub lesson_scope_score: f64,
    pub contradiction_resistance_score: f64,
    pub overgeneralization_guard_score: f64,
    pub candidate_accept_precision: f64,
    pub candidate_decision_agreement: f64,
    pub promotion_safety: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct LessonCandidateReport {
    pub source_experience_id: String,
    pub source_action: String,
    pub has_lesson_candidate: bool,
    pub lesson: Option<String>,
    pub evidence_count: usize,
    pub supporting_events: Vec<String>,
    pub contradicting_events: Vec<String>,
    pub confidence: f64,
    pub scope: String,
    pub grounding_score: f64,
    pub scope_score: f64,
    pub contradiction_resistance_score: f64,
    pub overgeneralization_guard: bool,
    pub evaluation_decision: String,
    pub expected_decision: String,
    pub promotion_status: String,
    pub lesson_persisted: bool,
    pub playbook_created: bool,
    pub future_influence_changed: bool,
    pub evaluation_notes: Vec<String>,
}
