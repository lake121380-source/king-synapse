use std::collections::BTreeSet;
use synapse_eval::Phase3LessonCandidateEvaluator;

#[test]
fn phase3_lesson_candidate_eval_produces_expected_decision_mix() {
    let report = Phase3LessonCandidateEvaluator::evaluate("phase3-lesson-candidate-eval-test")
        .expect("phase3 lesson candidate evaluation should run");
    let decisions = report
        .candidates
        .iter()
        .map(|candidate| candidate.evaluation_decision.as_str())
        .collect::<BTreeSet<_>>();

    assert_eq!(
        report.evaluation_version,
        "phase3.2-lesson-candidate-evaluation"
    );
    assert_eq!(report.baseline_version, "phase3.1-reflection-observation");
    assert_eq!(report.implementation_status, "evaluation_only");
    assert_eq!(report.source_trace_count, 6);
    assert_eq!(report.candidate_count, 6);
    assert!(report.accepted > 0);
    assert!(report.observe_more > 0);
    assert!(report.rejected > 0);
    assert!(decisions.contains("AcceptCandidate"));
    assert!(decisions.contains("ObserveMore"));
    assert!(decisions.contains("RejectCandidate"));
    assert!(report.pass);
}

#[test]
fn phase3_lesson_candidate_eval_is_promotion_safe() {
    let report = Phase3LessonCandidateEvaluator::evaluate("phase3-lesson-candidate-safety-test")
        .expect("phase3 lesson candidate evaluation should run");

    assert!(!report.mechanism_changed);
    assert!(!report.schema_changed);
    assert!(!report.retrieval_changed);
    assert!(!report.activation_changed);
    assert!(!report.temporal_lifecycle_changed);
    assert!(!report.governance_changed);
    assert!(!report.lesson_persisted);
    assert!(!report.playbook_created);
    assert!(!report.future_influence_changed);
    assert_eq!(report.metrics.promotion_safety, 1.0);
    assert!(report.candidates.iter().all(|candidate| {
        candidate.promotion_status == "not_promoted"
            && !candidate.lesson_persisted
            && !candidate.playbook_created
            && !candidate.future_influence_changed
    }));
}

#[test]
fn phase3_lesson_candidate_eval_report_schema_is_valid() {
    let report = Phase3LessonCandidateEvaluator::evaluate("phase3-lesson-candidate-schema-test")
        .expect("phase3 lesson candidate evaluation should run");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "evaluation_version",
        "baseline_version",
        "source_trace_count",
        "candidate_count",
        "metrics",
        "lesson_persisted",
        "playbook_created",
        "future_influence_changed",
        "implementation_status",
        "status",
        "candidates",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    assert!(value["metrics"].get("lesson_grounding_score").is_some());
    assert!(value["metrics"].get("lesson_scope_score").is_some());
    assert!(value["metrics"]
        .get("contradiction_resistance_score")
        .is_some());
    assert!(value["metrics"]
        .get("overgeneralization_guard_score")
        .is_some());
    assert!(value["metrics"].get("candidate_accept_precision").is_some());
    assert!(value["metrics"]
        .get("candidate_decision_agreement")
        .is_some());
    assert!(value["metrics"].get("promotion_safety").is_some());
    assert_eq!(report.status, "lesson_candidates_evaluated");
}
