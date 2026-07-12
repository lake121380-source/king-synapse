use std::collections::BTreeSet;
use synapse_eval::phase7_independent_adjudication_calibration::HumanSupportLabel;
use synapse_eval::phase7_semantic_judge_redesign::{
    load_phase7_semantic_judge_execution, Phase7SemanticJudgeRedesignDecision,
    Phase7SemanticJudgeRedesignEvaluator,
};

#[test]
fn semantic_judge_execution_is_complete_blind_and_design_only() {
    let execution = load_phase7_semantic_judge_execution()
        .expect("load semantic Judge execution")
        .expect("completed semantic Judge execution must be checked in");
    assert_eq!(execution.status, "completed");
    assert_eq!(execution.design_case_count, 10);
    assert_eq!(execution.completed_case_count, 10);
    assert_eq!(execution.decisions.len(), 10);
    assert_eq!(execution.temperature, 0.0);
    assert_eq!(execution.top_p, 1.0);
    assert!(execution.strict_parser);
    assert!(!execution.automatic_repair);
    assert!(!execution.selective_retry);
    assert!(execution.case_isolation);
    assert!(!execution.silver_labels_visible);
    assert!(!execution.reviewer_annotations_visible);
    assert!(!execution.adjudication_visible);
    assert!(!execution.old_judge_visible);
    assert!(!execution.reference_candidates_visible);
    assert!(!execution.held_out_accessed);
    assert!(!execution.api_key_recorded);
    assert!(!execution.raw_provider_responses_stored);
    let ids = execution
        .decisions
        .iter()
        .map(|decision| decision.case_id.as_str())
        .collect::<BTreeSet<_>>();
    assert_eq!(ids.len(), 10);
    assert!(ids.iter().all(|id| id.starts_with("extract_")));
}

#[test]
fn semantic_judge_report_preserves_negative_result_without_fake_improvement() {
    let report = Phase7SemanticJudgeRedesignEvaluator::evaluate("phase7.3.2-test")
        .expect("evaluate semantic Judge redesign");
    assert_eq!(
        report.decision,
        Phase7SemanticJudgeRedesignDecision::DiagnosticDiscriminationNotImproved
    );
    assert_eq!(report.ordinal_rows.len(), 10);
    let ordinal = report.ordinal_agreement.expect("ordinal comparison");
    assert_eq!(ordinal.exact_match_count, 7);
    assert_eq!(ordinal.exact_agreement, Some(0.7));

    let old = report.old_frozen_judge;
    let redesigned = report
        .redesigned_semantic_judge
        .expect("redesigned calibration");
    assert_eq!(old.strict_safety.true_positive, 9);
    assert_eq!(old.strict_safety.false_positive, 1);
    assert_eq!(old.strict_safety.specificity, Some(0.0));
    assert_eq!(old.strict_safety.false_positive_rate, Some(1.0));
    assert_eq!(redesigned.strict_safety.true_positive, 9);
    assert_eq!(redesigned.strict_safety.false_positive, 1);
    assert_eq!(redesigned.strict_safety.specificity, Some(0.0));
    assert_eq!(redesigned.strict_safety.false_positive_rate, Some(1.0));
    assert_eq!(redesigned.strict_safety.balanced_accuracy, Some(0.5));
    assert_eq!(redesigned.strong_error.true_positive, 0);
    assert_eq!(redesigned.strong_error.false_negative, 2);
    assert_eq!(redesigned.strong_error.true_negative, 1);
    assert_eq!(redesigned.strong_error.specificity, Some(1.0));
    assert_eq!(redesigned.strong_error.recall_sensitivity, Some(0.0));
    assert_eq!(report.scope_calibration, None);
}

#[test]
fn semantic_judge_collapsed_to_partial_support_and_authorizes_nothing() {
    let execution = load_phase7_semantic_judge_execution()
        .expect("load execution")
        .expect("execution");
    assert!(execution.decisions.iter().all(|decision| {
        decision.support_label == HumanSupportLabel::PartiallySupported
            && decision.unsupported_warning
            && !decision.abstained
    }));

    let report = Phase7SemanticJudgeRedesignEvaluator::evaluate("phase7.3.2-guards")
        .expect("evaluate report");
    assert!(report.guards.evidence_bundle_frozen);
    assert!(report.guards.design_candidates_frozen);
    assert!(report.guards.model_adjudicated_silver_frozen);
    assert!(!report.guards.human_gold_claimed);
    assert!(!report.guards.extractor_modified);
    assert!(!report.guards.provider_modified);
    assert!(!report.guards.old_frozen_judge_modified);
    assert!(report.guards.semantic_judge_only_experimental_variable);
    assert!(!report.guards.silver_labels_visible_to_semantic_judge);
    assert!(!report.guards.reviewer_annotations_visible_to_semantic_judge);
    assert!(!report.guards.old_judge_visible_to_semantic_judge);
    assert!(!report.guards.reference_candidates_visible_to_semantic_judge);
    assert!(report.guards.held_out_cases_untouched);
    assert!(!report.guards.memory_write_authorized);
    assert!(!report.guards.pattern_promotion_authorized);
    assert!(!report.guards.runtime_authorized);
    assert!(!report.guards.hermes_authorized);
    assert!(!report.guards.generalized_performance_claimed);
}

#[test]
fn semantic_judge_adapter_never_loads_reference_or_label_artifacts() {
    let source = include_str!("../../../scripts/eval/phase7_semantic_judge_execution.py");
    for forbidden_path in [
        "phase7_3_1_model_adjudicated_silver_labels.json",
        "phase7_3_1_adjudication_template.json",
        "phase7_3_1_reviewer_a_template.json",
        "phase7_3_1_reviewer_b_template.json",
        "phase7_candidate_error_analysis.json",
    ] {
        assert!(
            !source.contains(forbidden_path),
            "adapter must not load {forbidden_path}"
        );
    }
    assert!(source.contains("phase7_2_pattern_extraction_design.json"));
    assert!(source.contains("phase7_2_3_real_provider_execution.json"));
    assert!(source.contains("raw_provider_responses_stored\": False"));
}
