use std::collections::BTreeSet;
use synapse_eval::{Phase3FutureInfluenceEvaluator, Phase3LessonPromotionEvaluator};

#[test]
fn phase3_future_influence_loads_promotion_source() {
    let promotion = Phase3LessonPromotionEvaluator::evaluate("phase3-future-source")
        .expect("Phase 3.3 promotion source should run");
    let report = Phase3FutureInfluenceEvaluator::evaluate("phase3-future-load")
        .expect("Phase 3.4 future influence should run");

    assert_eq!(report.phase, "3.4");
    assert_eq!(report.mode, "evaluation_only");
    assert_eq!(
        report.evaluation_version,
        "phase3.4-future-influence-experiment"
    );
    assert_eq!(
        report.baseline_version,
        "phase3.3-controlled-lesson-promotion"
    );
    assert_eq!(report.scenarios, 3);
    assert_eq!(
        report.promoted_lesson_source_count,
        promotion
            .traces
            .iter()
            .filter(|trace| trace.status != "NotPromoted")
            .count()
    );
    assert!(report.pass);
}

#[test]
fn phase3_future_influence_covers_helpful_neutral_and_rejected_cases() {
    let report = Phase3FutureInfluenceEvaluator::evaluate("phase3-future-result-mix")
        .expect("Phase 3.4 future influence should run");
    let kinds = report
        .traces
        .iter()
        .map(|trace| trace.result_kind.as_str())
        .collect::<BTreeSet<_>>();

    assert_eq!(report.results.helpful_lessons, 1);
    assert_eq!(report.results.neutral_lessons, 1);
    assert_eq!(report.results.rejected_influence, 1);
    assert!(kinds.contains("HelpfulLesson"));
    assert!(kinds.contains("NeutralLesson"));
    assert!(kinds.contains("RejectedInfluence"));
}

#[test]
fn phase3_future_influence_proves_promoted_lesson_can_change_decision() {
    let report = Phase3FutureInfluenceEvaluator::evaluate("phase3-future-helpful")
        .expect("Phase 3.4 future influence should run");
    let helpful = report
        .traces
        .iter()
        .find(|trace| trace.result_kind == "HelpfulLesson")
        .expect("helpful lesson scenario should exist");

    assert!(helpful.lesson_used);
    assert!(helpful.influenced_score > helpful.baseline_score);
    assert!(helpful.improvement > 0.0);
    assert!(helpful.failure_reduced);
    assert!(helpful.influence_safe);
}

#[test]
fn phase3_future_influence_does_not_apply_irrelevant_lesson() {
    let report = Phase3FutureInfluenceEvaluator::evaluate("phase3-future-neutral")
        .expect("Phase 3.4 future influence should run");
    let neutral = report
        .traces
        .iter()
        .find(|trace| trace.result_kind == "NeutralLesson")
        .expect("neutral lesson scenario should exist");

    assert!(!neutral.lesson_used);
    assert_eq!(neutral.baseline_score, neutral.influenced_score);
    assert_eq!(neutral.baseline_decision, neutral.influenced_decision);
    assert!(neutral.influence_safe);
}

#[test]
fn phase3_future_influence_reduces_outdated_lesson_influence() {
    let report = Phase3FutureInfluenceEvaluator::evaluate("phase3-future-outdated")
        .expect("Phase 3.4 future influence should run");
    let rejected = report
        .traces
        .iter()
        .find(|trace| trace.result_kind == "RejectedInfluence")
        .expect("rejected influence scenario should exist");

    assert!(!rejected.lesson_used);
    assert_eq!(rejected.influence_action, "reject_outdated");
    assert!(rejected.influenced_score > rejected.baseline_score);
    assert!(rejected.failure_reduced);
    assert!(rejected.influence_safe);
}

#[test]
fn phase3_future_influence_report_schema_is_valid() {
    let report = Phase3FutureInfluenceEvaluator::evaluate("phase3-future-schema")
        .expect("Phase 3.4 future influence should run");
    let value = serde_json::to_value(&report).expect("report should serialize");

    for key in [
        "phase",
        "mode",
        "evaluation_version",
        "baseline_version",
        "scenarios",
        "results",
        "metrics",
        "safety",
        "pass",
        "traces",
    ] {
        assert!(value.get(key).is_some(), "missing schema field {key}");
    }

    assert!(value["results"].get("helpful_lessons").is_some());
    assert!(value["results"].get("neutral_lessons").is_some());
    assert!(value["results"].get("rejected_influence").is_some());
    assert!(value["metrics"].get("influence_gain_score").is_some());
    assert!(value["metrics"].get("decision_improvement_score").is_some());
    assert!(value["metrics"].get("failure_reduction_score").is_some());
    assert!(value["metrics"].get("lesson_usefulness_score").is_some());
    assert!(value["metrics"].get("no_write_safety").is_some());
}

#[test]
fn phase3_future_influence_is_eval_only_and_side_effect_safe() {
    let report = Phase3FutureInfluenceEvaluator::evaluate("phase3-future-safety")
        .expect("Phase 3.4 future influence should run");

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
    assert_eq!(report.metrics.no_write_safety, 1.0);
    assert!(report.traces.iter().all(|trace| {
        trace.influence_safe
            && !trace.memory_written
            && !trace.lesson_persisted
            && !trace.playbook_created
            && !trace.future_influence_changed
    }));
}
