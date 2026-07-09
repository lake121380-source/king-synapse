use std::collections::BTreeSet;
use synapse_eval::{Phase3LessonCandidateEvaluator, Phase3LessonPromotionEvaluator};

#[test]
fn phase3_lesson_promotion_loads_candidate_baseline_with_same_case_count() {
    let candidates = Phase3LessonCandidateEvaluator::evaluate("phase3-promotion-candidate-count")
        .expect("phase3 lesson candidate baseline should run");
    let promotion = Phase3LessonPromotionEvaluator::evaluate("phase3-promotion-count")
        .expect("phase3 lesson promotion should run");

    assert_eq!(
        promotion.evaluation_version,
        "phase3.3-controlled-lesson-promotion"
    );
    assert_eq!(
        promotion.baseline_version,
        "phase3.2-lesson-candidate-evaluation"
    );
    assert_eq!(promotion.phase, "3.3");
    assert_eq!(promotion.mode, "evaluation_only");
    assert_eq!(promotion.input_candidates, candidates.candidate_count);
    assert_eq!(promotion.traces.len(), candidates.candidate_count);
    assert!(promotion.pass);
}

#[test]
fn phase3_lesson_promotion_produces_expected_status_mix() {
    let report = Phase3LessonPromotionEvaluator::evaluate("phase3-promotion-status-mix")
        .expect("phase3 lesson promotion should run");
    let statuses = report
        .traces
        .iter()
        .map(|trace| trace.status.as_str())
        .collect::<BTreeSet<_>>();

    assert_eq!(report.promotion.proposed_lessons, 2);
    assert_eq!(report.promotion.playbook_candidates, 1);
    assert_eq!(report.promotion.not_promoted, 3);
    assert!(statuses.contains("ProposedLesson"));
    assert!(statuses.contains("PlaybookCandidate"));
    assert!(statuses.contains("NotPromoted"));
    assert_eq!(report.metrics.promotion_precision, 1.0);
    assert_eq!(report.metrics.promotion_decision_agreement, 1.0);
}

#[test]
fn phase3_lesson_promotion_report_schema_is_valid() {
    let report = Phase3LessonPromotionEvaluator::evaluate("phase3-promotion-schema")
        .expect("phase3 lesson promotion should run");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "phase",
        "mode",
        "evaluation_version",
        "baseline_version",
        "input_candidates",
        "promotion",
        "safety",
        "metrics",
        "pass",
        "status",
        "traces",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    assert!(value["promotion"].get("proposed_lessons").is_some());
    assert!(value["promotion"].get("playbook_candidates").is_some());
    assert!(value["promotion"].get("not_promoted").is_some());
    assert!(value["safety"].get("memory_written").is_some());
    assert!(value["safety"].get("lesson_persisted").is_some());
    assert!(value["safety"].get("playbook_created").is_some());
    assert!(value["safety"].get("future_influence_changed").is_some());
    assert!(value["metrics"].get("promotion_precision").is_some());
    assert!(value["metrics"].get("promotion_readiness_score").is_some());
    assert!(value["metrics"].get("evidence_sufficiency_score").is_some());
    assert!(value["metrics"].get("scope_stability_score").is_some());
    assert!(value["metrics"].get("contradiction_safety_score").is_some());
    assert!(value["metrics"]
        .get("promotion_decision_agreement")
        .is_some());
    assert!(value["metrics"].get("promotion_safety").is_some());
}

#[test]
fn phase3_lesson_promotion_is_evaluation_only_and_side_effect_safe() {
    let report = Phase3LessonPromotionEvaluator::evaluate("phase3-promotion-safety")
        .expect("phase3 lesson promotion should run");

    assert!(!report.mechanism_changed);
    assert!(!report.schema_changed);
    assert!(!report.retrieval_changed);
    assert!(!report.activation_changed);
    assert!(!report.temporal_lifecycle_changed);
    assert!(!report.governance_changed);
    assert!(!report.safety.memory_written);
    assert!(!report.safety.lesson_persisted);
    assert!(!report.safety.playbook_created);
    assert!(!report.safety.future_influence_changed);
    assert_eq!(report.metrics.promotion_safety, 1.0);
    assert!(report.traces.iter().all(|trace| {
        !trace.memory_written
            && !trace.lesson_persisted
            && !trace.playbook_created
            && !trace.future_influence_changed
    }));
}

#[test]
fn phase3_lesson_promotion_keeps_playbook_candidate_report_only() {
    let report = Phase3LessonPromotionEvaluator::evaluate("phase3-promotion-playbook-report-only")
        .expect("phase3 lesson promotion should run");
    let playbook_trace = report
        .traces
        .iter()
        .find(|trace| trace.status == "PlaybookCandidate")
        .expect("one procedural lesson should be marked as a playbook candidate");

    assert_eq!(
        playbook_trace.candidate_id,
        "reflection_obs_004_repeated_permission_failure"
    );
    assert!(!playbook_trace.memory_written);
    assert!(!playbook_trace.lesson_persisted);
    assert!(!playbook_trace.playbook_created);
    assert!(!playbook_trace.future_influence_changed);
}
