use synapse_eval::phase7_pattern_provider_comparison::{
    Phase7ProviderComparisonDecision, Phase7ProviderComparisonEvaluator,
};
use synapse_eval::phase7_real_provider_readiness::{
    load_phase7_real_provider_execution, Phase7RealProviderReadinessDecision,
    Phase7RealProviderReadinessEvaluator,
};

fn close(left: f64, right: f64) {
    assert!((left - right).abs() < 1e-9, "left={left} right={right}");
}

#[test]
fn real_provider_completed_all_frozen_design_requests() {
    let report = Phase7RealProviderReadinessEvaluator::evaluate("test").expect("evaluate");
    assert!(report.guards.authenticated_preflight_completed);
    assert!(report.guards.all_design_requests_attempted_once);
    assert!(report.guards.all_design_outputs_strictly_parsed);
    assert!(report.guards.all_candidates_contract_valid);
    assert!(report.guards.provider_ready);
    assert_eq!(report.summary.design_case_count, 10);
    assert_eq!(report.summary.attempted_design_cases, 10);
    assert_eq!(report.summary.completed_design_cases, 10);
    close(report.summary.strict_parser_acceptance_rate, 1.0);
    close(report.summary.contract_validity, 1.0);
}

#[test]
fn real_provider_reuses_the_frozen_phase7_2_2_protocol() {
    let report = Phase7RealProviderReadinessEvaluator::evaluate("test").expect("evaluate");
    assert!(report.artifact_hashes.frozen_protocol_matches_manifest);
    assert!(report.artifact_hashes.execution_matches_frozen_protocol);
    assert!(report.guards.frozen_prompt_reused);
    assert!(report.guards.frozen_parser_reused);
    assert!(report.guards.frozen_scorer_reused);
    assert!(report.guards.frozen_design_dataset_reused);
    assert_eq!(
        report.scorer_policy.primary_safety_metric,
        "unsupported_claim_rate"
    );
    assert!(report.scorer_policy.fluency_metric.is_none());
    assert!(report.scorer_policy.style_metric.is_none());
}

#[test]
fn provider_artifact_records_no_key_or_raw_response() {
    let execution = load_phase7_real_provider_execution().expect("execution");
    assert_eq!(execution.status, "completed");
    assert_eq!(execution.outputs.len(), 10);
    assert!(!execution.api_key_recorded);
    assert!(!execution.raw_response_text_recorded);
    assert!(execution.blocker.is_none());
    assert!(execution
        .outputs
        .iter()
        .all(|output| output.response_sha256.len() == 64));
}

#[test]
fn no_repair_retry_or_selective_rerun_was_used() {
    let report = Phase7RealProviderReadinessEvaluator::evaluate("test").expect("evaluate");
    assert!(!report.parser_policy.automatic_repair);
    assert!(!report.parser_policy.retry_on_parse_error);
    assert!(!report.guards.automatic_output_repair);
    assert!(!report.guards.selective_retry);
    assert_eq!(
        report.summary.attempted_design_cases,
        report.summary.design_case_count
    );
}

#[test]
fn unsupported_abstraction_is_preserved_as_a_primary_safety_result() {
    let report = Phase7RealProviderReadinessEvaluator::evaluate("test").expect("evaluate");
    close(report.summary.evidence_attribution_accuracy, 1.0);
    close(report.summary.scope_preservation, 0.7);
    close(report.summary.counterexample_retention, 1.0);
    close(report.summary.unsupported_claim_rate, 0.5128640676484479);
    close(report.summary.abstraction_distance, 0.6158211828129112);
    close(
        report.summary.design_reference_token_recall,
        0.26041847041847044,
    );
    assert!(report.summary.unsupported_claim_requires_review);
    assert_eq!(report.summary.cases_with_quality_diagnostics, 10);
    assert_eq!(
        report.decision,
        Phase7RealProviderReadinessDecision::ProviderReadyCandidatesRequireQualityReview
    );
}

#[test]
fn format_readiness_does_not_authorize_learning_or_runtime() {
    let report = Phase7RealProviderReadinessEvaluator::evaluate("test").expect("evaluate");
    assert!(report.guards.provider_ready);
    assert!(!report.guards.candidate_learning_authorized);
    assert!(!report.guards.pattern_persistence_authorized);
    assert!(!report.guards.knowledge_promotion_authorized);
    assert!(!report.guards.transfer_value_claimed);
    assert!(!report.guards.runtime_authorized);
    assert!(!report.guards.hermes_authorized);
}

#[test]
fn held_out_cases_remain_untouched() {
    let report = Phase7RealProviderReadinessEvaluator::evaluate("test").expect("evaluate");
    assert!(report.guards.design_cases_only);
    assert!(report.guards.held_out_cases_untouched);
    assert!(!report.preflight.held_out_cases_accessed);
    assert_eq!(report.cases.len(), 10);
    assert!(report
        .cases
        .iter()
        .all(|case| case.case_id.starts_with("extract_")));
}

#[test]
fn phase7_2_2_historical_blocked_state_is_not_overwritten() {
    let report = Phase7ProviderComparisonEvaluator::evaluate("historical").expect("evaluate");
    let model = &report.capability_matrix[1];
    assert_eq!(model.execution_status, "blocked_authorization");
    assert_eq!(model.design_cases_attempted, 0);
    assert_eq!(model.design_cases_completed, 0);
    assert!(!report.guards.model_execution_completed);
    assert_eq!(
        report.decision,
        Phase7ProviderComparisonDecision::ComparisonProtocolFrozenModelExecutionBlocked
    );
}
