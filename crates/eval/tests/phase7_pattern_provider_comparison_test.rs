use synapse_eval::{
    load_phase7_model_execution, load_phase7_pattern_extraction_design,
    load_phase7_provider_manifests, strict_parse_pattern_candidate_json,
    DeterministicBoundedPatternExtractionProvider, PatternExtractionProvider,
    Phase7ProviderComparisonDecision, Phase7ProviderComparisonEvaluator,
};

fn valid_candidate_json() -> String {
    let dataset = load_phase7_pattern_extraction_design().expect("dataset");
    let provider = DeterministicBoundedPatternExtractionProvider::new();
    let candidate = provider
        .extract(&dataset.cases[0].input)
        .expect("extract")
        .remove(0);
    serde_json::to_string(&candidate).expect("serialize")
}

#[test]
fn frozen_artifact_hashes_match_the_manifest() {
    let report = Phase7ProviderComparisonEvaluator::evaluate("test").expect("evaluate");
    assert!(report.artifact_hashes.all_match_manifest);
    assert!(report.guards.canonical_prompt_frozen);
    assert!(report.guards.provider_manifests_frozen);
    assert!(report.guards.parser_policy_frozen);
    assert!(report.guards.scorer_policy_frozen);
}

#[test]
fn capability_matrix_contains_exactly_the_two_frozen_providers() {
    let report = Phase7ProviderComparisonEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.provider_manifests.len(), 2);
    assert_eq!(report.capability_matrix.len(), 2);
    assert_eq!(
        report.capability_matrix[0].provider_name,
        "deterministic_bounded_pattern_extractor_v0"
    );
    assert_eq!(
        report.capability_matrix[1].provider_name,
        "deepseek_pattern_extractor_v1"
    );
}

#[test]
fn weak_baseline_is_completed_with_measured_diagnostics() {
    let report = Phase7ProviderComparisonEvaluator::evaluate("test").expect("evaluate");
    let row = &report.capability_matrix[0];
    assert_eq!(row.execution_status, "completed");
    assert_eq!(row.design_cases_attempted, 10);
    assert_eq!(row.design_cases_completed, 10);
    assert_eq!(row.contract_validity, Some(1.0));
    assert!(row.evidence_attribution_accuracy.is_some());
    assert!(row.scope_preservation.is_some());
    assert!(row.counterexample_retention.is_some());
    assert!(row.unsupported_claim_rate.is_some());
    assert!(row.blocker.is_none());
}

#[test]
fn blocked_model_row_contains_no_fabricated_results() {
    let report = Phase7ProviderComparisonEvaluator::evaluate("test").expect("evaluate");
    let row = &report.capability_matrix[1];
    assert_eq!(row.execution_status, "blocked_authorization");
    assert_eq!(row.design_cases_attempted, 0);
    assert_eq!(row.design_cases_completed, 0);
    assert!(row.contract_validity.is_none());
    assert!(row.evidence_attribution_accuracy.is_none());
    assert!(row.scope_preservation.is_none());
    assert!(row.counterexample_retention.is_none());
    assert!(row.unsupported_claim_rate.is_none());
    assert!(row.abstraction_distance.is_none());
    assert!(row.design_reference_token_recall.is_none());
    assert!(row.cases_with_quality_diagnostics.is_none());
    assert_eq!(
        row.blocker.as_ref().and_then(|item| item.http_status),
        Some(401)
    );

    let execution = load_phase7_model_execution().expect("execution");
    assert!(execution.outputs.is_empty());
    assert!(!execution.api_key_recorded);
    assert!(!execution.raw_response_text_recorded);
}

#[test]
fn canonical_prompt_and_provider_parameters_are_frozen() {
    let manifests = load_phase7_provider_manifests().expect("manifests");
    assert_eq!(
        manifests.canonical_prompt_version,
        "PatternExtractorPrompt-v1"
    );
    let model = &manifests.providers[1];
    assert_eq!(
        model.prompt_version.as_deref(),
        Some("PatternExtractorPrompt-v1")
    );
    assert_eq!(model.temperature, Some(0.0));
    assert_eq!(model.top_p, Some(1.0));
    assert_eq!(model.repair_policy, "reject_only_no_automatic_repair");
}

#[test]
fn strict_parser_accepts_one_exact_candidate_object() {
    strict_parse_pattern_candidate_json(&valid_candidate_json()).expect("strict parse");
}

#[test]
fn strict_parser_rejects_fences_commentary_and_unknown_fields_without_repair() {
    let valid = valid_candidate_json();
    assert!(strict_parse_pattern_candidate_json(&format!("```json\n{valid}\n```")).is_err());
    assert!(strict_parse_pattern_candidate_json(&format!("{valid}\nexplanation")).is_err());

    let mut value: serde_json::Value = serde_json::from_str(&valid).expect("json");
    value
        .as_object_mut()
        .expect("object")
        .insert("eloquence_score".to_string(), serde_json::json!(1.0));
    assert!(strict_parse_pattern_candidate_json(&value.to_string()).is_err());
}

#[test]
fn scorer_never_rewards_fluency_or_style() {
    let report = Phase7ProviderComparisonEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(
        report.scorer_policy.principle,
        "never_reward_linguistic_sophistication"
    );
    assert_eq!(
        report.scorer_policy.primary_safety_metric,
        "unsupported_claim_rate"
    );
    assert!(report.scorer_policy.fluency_metric.is_none());
    assert!(report.scorer_policy.style_metric.is_none());
    assert!(!report.scorer_policy.held_out_threshold_selection);
    assert!(!report.guards.linguistic_sophistication_rewarded);
}

#[test]
fn phase_boundaries_remain_closed_when_model_authorization_is_blocked() {
    let report = Phase7ProviderComparisonEvaluator::evaluate("test").expect("evaluate");
    assert!(report.guards.design_cases_only);
    assert!(report.guards.held_out_cases_untouched);
    assert!(!report.guards.model_execution_completed);
    assert!(!report.guards.pattern_persistence_authorized);
    assert!(!report.guards.knowledge_promotion_authorized);
    assert!(!report.guards.transfer_value_claimed);
    assert!(!report.guards.runtime_authorized);
    assert!(!report.guards.hermes_authorized);
    assert_eq!(
        report.decision,
        Phase7ProviderComparisonDecision::ComparisonProtocolFrozenModelExecutionBlocked
    );
}
