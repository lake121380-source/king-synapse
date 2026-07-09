use crate::phase3_lesson_candidate_eval::{LessonCandidateReport, Phase3LessonCandidateEvaluator};
use anyhow::Result;
use chrono::Utc;
use serde::Serialize;

const EVALUATION_VERSION: &str = "phase3.3-controlled-lesson-promotion";
const BASELINE_VERSION: &str = "phase3.2-lesson-candidate-evaluation";

pub struct Phase3LessonPromotionEvaluator;

impl Phase3LessonPromotionEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase3LessonPromotionReport> {
        let candidate_report =
            Phase3LessonCandidateEvaluator::evaluate("phase3-lesson-promotion-candidate-source")?;
        Ok(evaluate_promotions(
            tag.into(),
            &candidate_report.candidates,
        ))
    }
}

fn evaluate_promotions(
    tag: String,
    candidates: &[LessonCandidateReport],
) -> Phase3LessonPromotionReport {
    let traces = candidates
        .iter()
        .map(evaluate_candidate)
        .collect::<Vec<LessonPromotionTrace>>();
    let proposed_lessons = traces
        .iter()
        .filter(|trace| trace.status == "ProposedLesson")
        .count();
    let playbook_candidates = traces
        .iter()
        .filter(|trace| trace.status == "PlaybookCandidate")
        .count();
    let not_promoted = traces
        .iter()
        .filter(|trace| trace.status == "NotPromoted")
        .count();
    let promoted = traces
        .iter()
        .filter(|trace| trace.status != "NotPromoted")
        .collect::<Vec<_>>();
    let safety = PromotionSafetyReport {
        memory_written: false,
        lesson_persisted: false,
        playbook_created: false,
        future_influence_changed: false,
    };
    let side_effect_safe = traces.iter().all(|trace| {
        !trace.memory_written
            && !trace.lesson_persisted
            && !trace.playbook_created
            && !trace.future_influence_changed
    }) && !safety.memory_written
        && !safety.lesson_persisted
        && !safety.playbook_created
        && !safety.future_influence_changed;

    let metrics = Phase3LessonPromotionMetrics {
        promotion_precision: safe_div(
            promoted
                .iter()
                .filter(|trace| trace.expected_status != "NotPromoted")
                .count() as f64,
            promoted.len() as f64,
        ),
        promotion_readiness_score: mean_promoted(&promoted, |trace| {
            trace.promotion_readiness_score
        }),
        evidence_sufficiency_score: mean_promoted(&promoted, |trace| trace.evidence_score),
        scope_stability_score: mean_promoted(&promoted, |trace| trace.scope_score),
        contradiction_safety_score: safe_div(
            traces
                .iter()
                .filter(|trace| trace.contradiction_score >= 1.0 || trace.status == "NotPromoted")
                .count() as f64,
            traces.len() as f64,
        ),
        promotion_decision_agreement: safe_div(
            traces
                .iter()
                .filter(|trace| trace.status == trace.expected_status)
                .count() as f64,
            traces.len() as f64,
        ),
        promotion_safety: f64::from(side_effect_safe),
    };

    let pass = traces.len() == candidates.len()
        && proposed_lessons == 2
        && playbook_candidates == 1
        && not_promoted == 3
        && metrics.promotion_precision >= 0.80
        && metrics.promotion_readiness_score >= 0.80
        && metrics.evidence_sufficiency_score >= 0.80
        && metrics.scope_stability_score >= 0.80
        && metrics.contradiction_safety_score >= 1.0
        && metrics.promotion_decision_agreement >= 0.80
        && metrics.promotion_safety >= 1.0;

    Phase3LessonPromotionReport {
        tag,
        phase: "3.3".to_string(),
        mode: "evaluation_only".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        baseline_version: BASELINE_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        input_candidates: candidates.len(),
        mechanism_changed: false,
        schema_changed: false,
        retrieval_changed: false,
        activation_changed: false,
        temporal_lifecycle_changed: false,
        governance_changed: false,
        promotion: PromotionSummaryReport {
            proposed_lessons,
            playbook_candidates,
            not_promoted,
        },
        safety,
        metrics,
        pass,
        status: "controlled_lesson_promotion_evaluated".to_string(),
        traces,
    }
}

fn evaluate_candidate(candidate: &LessonCandidateReport) -> LessonPromotionTrace {
    let evidence_score = evidence_score(candidate);
    let scope_score = scope_stability_score(candidate);
    let contradiction_score = contradiction_score(candidate);
    let procedural_score = procedural_score(candidate.lesson.as_deref());
    let promotion_readiness_score =
        promotion_readiness_score(candidate, evidence_score, scope_score, contradiction_score);
    let status = promotion_status(
        candidate,
        evidence_score,
        scope_score,
        contradiction_score,
        procedural_score,
        promotion_readiness_score,
    );
    let expected_status = expected_status(candidate);

    LessonPromotionTrace {
        candidate_id: candidate.source_experience_id.clone(),
        source_decision: candidate.evaluation_decision.clone(),
        status: status.as_str().to_string(),
        expected_status: expected_status.to_string(),
        lesson: candidate.lesson.clone(),
        evidence_count: candidate.evidence_count,
        supporting_events: candidate.supporting_events.clone(),
        contradicting_events: candidate.contradicting_events.clone(),
        evidence_score,
        scope_score,
        contradiction_score,
        procedural_score,
        promotion_readiness_score,
        promotion_reason: promotion_reason(candidate, status, evidence_score, procedural_score),
        memory_written: false,
        lesson_persisted: false,
        playbook_created: false,
        future_influence_changed: false,
        trace_notes: vec![
            "evaluation only: promotion does not write memory".to_string(),
            "evaluation only: playbook candidate is report-only".to_string(),
            "evaluation only: future influence remains unchanged".to_string(),
        ],
    }
}

fn evidence_score(candidate: &LessonCandidateReport) -> f64 {
    (candidate.evidence_count as f64 / 3.0).min(1.0)
}

fn scope_stability_score(candidate: &LessonCandidateReport) -> f64 {
    if candidate.scope == "global" || candidate.scope == "none" {
        return 0.0;
    }
    candidate.scope_score
}

fn contradiction_score(candidate: &LessonCandidateReport) -> f64 {
    if candidate.contradicting_events.is_empty() {
        1.0
    } else {
        0.0
    }
}

fn procedural_score(lesson: Option<&str>) -> f64 {
    let Some(lesson) = lesson else {
        return 0.0;
    };
    let lower = lesson.to_ascii_lowercase();
    let has_action = ["verify", "check", "validate"]
        .iter()
        .any(|keyword| lower.contains(keyword));

    if lower.starts_with("before ") && has_action {
        1.0
    } else if lower.contains("before") && has_action {
        0.95
    } else if has_action {
        0.80
    } else {
        0.55
    }
}

fn promotion_readiness_score(
    candidate: &LessonCandidateReport,
    evidence: f64,
    scope: f64,
    contradiction: f64,
) -> f64 {
    (0.35 * candidate.confidence + 0.30 * evidence + 0.20 * scope + 0.15 * contradiction)
        .clamp(0.0, 1.0)
}

fn promotion_status(
    candidate: &LessonCandidateReport,
    evidence: f64,
    scope: f64,
    contradiction: f64,
    procedural: f64,
    readiness: f64,
) -> PromotionStatus {
    if candidate.evaluation_decision != "AcceptCandidate"
        || !candidate.has_lesson_candidate
        || contradiction < 1.0
    {
        return PromotionStatus::NotPromoted;
    }

    if evidence >= 1.0 && procedural >= 1.0 && readiness >= 0.90 {
        PromotionStatus::PlaybookCandidate
    } else if evidence >= 0.60 && scope >= 0.75 && readiness >= 0.75 {
        PromotionStatus::ProposedLesson
    } else {
        PromotionStatus::NotPromoted
    }
}

fn expected_status(candidate: &LessonCandidateReport) -> &'static str {
    match candidate.source_experience_id.as_str() {
        "reflection_obs_004_repeated_permission_failure" => "PlaybookCandidate",
        "reflection_obs_001_gpu_deployment_failure"
        | "reflection_obs_005_local_docker_disk_scope" => "ProposedLesson",
        _ => "NotPromoted",
    }
}

fn promotion_reason(
    candidate: &LessonCandidateReport,
    status: PromotionStatus,
    evidence: f64,
    procedural: f64,
) -> String {
    match status {
        PromotionStatus::PlaybookCandidate => format!(
            "accepted candidate has sufficient evidence ({:.2}) and procedural form ({:.2})",
            evidence, procedural
        ),
        PromotionStatus::ProposedLesson => format!(
            "accepted candidate is grounded enough for proposed lesson review ({:.2})",
            evidence
        ),
        PromotionStatus::NotPromoted if candidate.evaluation_decision != "AcceptCandidate" => {
            format!(
                "Phase 3.2 decision was {}, so promotion is blocked",
                candidate.evaluation_decision
            )
        }
        PromotionStatus::NotPromoted if !candidate.contradicting_events.is_empty() => {
            "contradicting evidence blocks controlled promotion".to_string()
        }
        PromotionStatus::NotPromoted => {
            "candidate lacks sufficient readiness for controlled promotion".to_string()
        }
    }
}

fn mean_promoted<F>(promoted: &[&LessonPromotionTrace], score: F) -> f64
where
    F: Fn(&LessonPromotionTrace) -> f64,
{
    safe_div(
        promoted.iter().map(|trace| score(trace)).sum::<f64>(),
        promoted.len() as f64,
    )
}

fn safe_div(numerator: f64, denominator: f64) -> f64 {
    if denominator.abs() < f64::EPSILON {
        0.0
    } else {
        numerator / denominator
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum PromotionStatus {
    ProposedLesson,
    PlaybookCandidate,
    NotPromoted,
}

impl PromotionStatus {
    fn as_str(self) -> &'static str {
        match self {
            PromotionStatus::ProposedLesson => "ProposedLesson",
            PromotionStatus::PlaybookCandidate => "PlaybookCandidate",
            PromotionStatus::NotPromoted => "NotPromoted",
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase3LessonPromotionReport {
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub baseline_version: String,
    pub generated_at: String,
    pub input_candidates: usize,
    pub mechanism_changed: bool,
    pub schema_changed: bool,
    pub retrieval_changed: bool,
    pub activation_changed: bool,
    pub temporal_lifecycle_changed: bool,
    pub governance_changed: bool,
    pub promotion: PromotionSummaryReport,
    pub safety: PromotionSafetyReport,
    pub metrics: Phase3LessonPromotionMetrics,
    pub pass: bool,
    pub status: String,
    pub traces: Vec<LessonPromotionTrace>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PromotionSummaryReport {
    pub proposed_lessons: usize,
    pub playbook_candidates: usize,
    pub not_promoted: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct PromotionSafetyReport {
    pub memory_written: bool,
    pub lesson_persisted: bool,
    pub playbook_created: bool,
    pub future_influence_changed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Phase3LessonPromotionMetrics {
    pub promotion_precision: f64,
    pub promotion_readiness_score: f64,
    pub evidence_sufficiency_score: f64,
    pub scope_stability_score: f64,
    pub contradiction_safety_score: f64,
    pub promotion_decision_agreement: f64,
    pub promotion_safety: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct LessonPromotionTrace {
    pub candidate_id: String,
    pub source_decision: String,
    pub status: String,
    pub expected_status: String,
    pub lesson: Option<String>,
    pub evidence_count: usize,
    pub supporting_events: Vec<String>,
    pub contradicting_events: Vec<String>,
    pub evidence_score: f64,
    pub scope_score: f64,
    pub contradiction_score: f64,
    pub procedural_score: f64,
    pub promotion_readiness_score: f64,
    pub promotion_reason: String,
    pub memory_written: bool,
    pub lesson_persisted: bool,
    pub playbook_created: bool,
    pub future_influence_changed: bool,
    pub trace_notes: Vec<String>,
}
