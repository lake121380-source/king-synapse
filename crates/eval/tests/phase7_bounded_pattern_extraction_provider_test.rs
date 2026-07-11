use synapse_eval::{
    evaluate_provider, load_phase7_pattern_extraction_design, validate_pattern_extraction_batch,
    DeterministicBoundedPatternExtractionProvider, PatternExtractionProvider, PatternStatus,
    Phase7BoundedPatternExtractionDecision, Phase7BoundedPatternExtractionEvaluator,
    ProviderOutputDisposition,
};

#[test]
fn frozen_provider_runs_only_the_ten_design_inputs() {
    let report = Phase7BoundedPatternExtractionEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.summary.design_case_count, 10);
    assert_eq!(report.summary.provider_executions, 10);
    assert_eq!(report.summary.candidates_produced, 10);
    assert!(report.guards.design_cases_only);
    assert!(report.guards.held_out_cases_untouched);
}

#[test]
fn same_input_produces_the_same_candidate() {
    let dataset = load_phase7_pattern_extraction_design().expect("dataset");
    let provider = DeterministicBoundedPatternExtractionProvider::new();
    let first = provider.extract(&dataset.cases[0].input).expect("first");
    let second = provider.extract(&dataset.cases[0].input).expect("second");
    assert_eq!(first, second);
}

#[test]
fn provider_preserves_authoritative_evidence_and_counterexamples() {
    let dataset = load_phase7_pattern_extraction_design().expect("dataset");
    let provider = DeterministicBoundedPatternExtractionProvider::new();
    for case in dataset.cases {
        let candidates = provider.extract(&case.input).expect("extract");
        let validation = validate_pattern_extraction_batch(&case.input, &candidates);
        assert!(validation.valid, "{:?}", validation.violations);
        let candidate = &candidates[0];
        assert_eq!(candidate.status, PatternStatus::Proposed);
        assert!(candidate.validation_outcome_ids.is_empty());
        assert!(candidate.confidence <= provider.config().max_confidence);
        assert_eq!(
            candidate.counterexamples.len(),
            case.input.supplied_counterexample_ids.len()
        );
    }
}

#[test]
fn provider_configuration_is_frozen_and_default_safe() {
    let provider = DeterministicBoundedPatternExtractionProvider::new();
    let config = provider.config();
    assert!(config.design_cases_only);
    assert!(config.deterministic);
    assert!(!config.held_out_access);
    assert!(!config.persistence_authorized);
    assert!(!config.runtime_authorized);
    assert_eq!(
        config.output_repair_policy,
        "reject_only_no_automatic_repair"
    );
    assert!(config.model_id.is_none());
}

#[test]
fn contract_acceptance_is_not_reported_as_knowledge_validation() {
    let report = Phase7BoundedPatternExtractionEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.summary.contract_accepted_cases, 10);
    assert!(report
        .cases
        .iter()
        .all(|case| case.disposition == ProviderOutputDisposition::AcceptedContractOnly));
    assert!(!report.guards.knowledge_promotion_authorized);
    assert!(!report.guards.transfer_value_claimed);
}

#[test]
fn quality_metrics_are_reported_separately_from_contract_validation() {
    let report = Phase7BoundedPatternExtractionEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.summary.mean_pattern_completeness, 1.0);
    assert_eq!(report.summary.mean_evidence_attribution_accuracy, 1.0);
    assert_eq!(report.summary.mean_scope_retention, 1.0);
    assert_eq!(report.summary.mean_counterexample_handling, 1.0);
    assert!(report.summary.mean_design_reference_token_recall < 1.0);
    assert!(report
        .cases
        .iter()
        .all(|case| case.quality_metrics.is_some()));
}

#[test]
fn invalid_provider_outputs_receive_explicit_rejection_reasons() {
    let report = Phase7BoundedPatternExtractionEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.fault_injections.len(), 6);
    assert!(report.fault_injections.iter().all(|fault| fault.rejected));
    assert!(report
        .fault_injections
        .iter()
        .all(|fault| !fault.observed_violations.is_empty()));
}

#[test]
fn phase_decision_keeps_provider_in_design_evaluation_only() {
    let report = Phase7BoundedPatternExtractionEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(
        report.decision,
        Phase7BoundedPatternExtractionDecision::ProviderFrozenDesignEvaluationOnly
    );
    assert!(!report.guards.pattern_persistence_authorized);
    assert!(!report.guards.runtime_authorized);
    assert!(!report.guards.hermes_authorized);
}

#[test]
fn provider_rejects_inputs_without_the_frozen_candidate_slot() {
    let dataset = load_phase7_pattern_extraction_design().expect("dataset");
    let provider = DeterministicBoundedPatternExtractionProvider::new();
    let mut input = dataset.cases[0].input.clone();
    input.max_pattern_candidates = 2;
    assert!(provider.extract(&input).is_err());
}

#[test]
fn evaluator_rejects_provider_configuration_identity_mismatch() {
    let provider = DeterministicBoundedPatternExtractionProvider::new();
    let mut config = provider.config().clone();
    config.provider_id = "different_provider".to_string();
    assert!(evaluate_provider("test".to_string(), &provider, config).is_err());
}
