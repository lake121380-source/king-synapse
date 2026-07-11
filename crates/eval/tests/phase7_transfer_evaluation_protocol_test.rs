use synapse_eval::{
    load_phase7_transfer_benchmark, validate_transfer_scenario, Phase7TransferDecision,
    Phase7TransferEvaluationProtocolEvaluator, TransferExperimentArm,
};

#[test]
fn dataset_contains_frozen_design_and_held_out_transfer_cases() {
    let dataset = load_phase7_transfer_benchmark().expect("dataset loads");
    assert_eq!(dataset.scenarios.len(), 30);

    let report = Phase7TransferEvaluationProtocolEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.dataset.design_count, 10);
    assert_eq!(report.dataset.held_out_count, 20);
    assert_eq!(report.dataset.category_counts.len(), 6);
    assert!(report
        .dataset
        .category_counts
        .values()
        .all(|count| *count == 5));
    assert!(report.dataset.should_apply_count > 0);
    assert!(report.dataset.should_withhold_count > 0);
}

#[test]
fn every_transfer_scenario_satisfies_evidence_scope_and_safety_contract() {
    let dataset = load_phase7_transfer_benchmark().expect("dataset loads");
    let failures = dataset
        .scenarios
        .iter()
        .map(validate_transfer_scenario)
        .filter(|validation| !validation.valid)
        .collect::<Vec<_>>();
    assert!(failures.is_empty(), "invalid scenarios: {failures:#?}");
}

#[test]
fn comparison_protocol_contains_all_six_experimental_arms() {
    let report = Phase7TransferEvaluationProtocolEvaluator::evaluate("test").expect("evaluate");
    let arms = report
        .arms
        .iter()
        .map(|arm| arm.arm.clone())
        .collect::<Vec<_>>();
    assert_eq!(arms.len(), 6);
    assert!(arms.contains(&TransferExperimentArm::LlmOnly));
    assert!(arms.contains(&TransferExperimentArm::RawMemories));
    assert!(arms.contains(&TransferExperimentArm::MemorySummary));
    assert!(arms.contains(&TransferExperimentArm::PatternCandidate));
    assert!(arms.contains(&TransferExperimentArm::PatternWithScopeAndCounterexamples));
    assert!(arms.contains(&TransferExperimentArm::PatternWithEvidenceGraph));
    assert!(report
        .arms
        .iter()
        .all(|arm| !arm.outcome_performance_measured));
}

#[test]
fn full_pattern_arm_preserves_scope_counterexamples_and_evidence_lineage() {
    let report = Phase7TransferEvaluationProtocolEvaluator::evaluate("test").expect("evaluate");
    let full = report
        .arms
        .iter()
        .find(|arm| arm.arm == TransferExperimentArm::PatternWithEvidenceGraph)
        .expect("full arm");
    assert!(full.receives_raw_evidence);
    assert!(full.receives_pattern);
    assert!(full.receives_explicit_scope);
    assert!(full.receives_counterexamples);
    assert!(full.receives_evidence_lineage);

    let llm_only = report
        .arms
        .iter()
        .find(|arm| arm.arm == TransferExperimentArm::LlmOnly)
        .expect("llm-only arm");
    assert!(!llm_only.receives_raw_evidence);
    assert!(!llm_only.receives_pattern);
    assert!(!llm_only.receives_explicit_scope);
    assert!(!llm_only.receives_counterexamples);
    assert!(!llm_only.receives_evidence_lineage);
}

#[test]
fn transfer_metrics_include_quality_safety_compression_and_dependency() {
    let report = Phase7TransferEvaluationProtocolEvaluator::evaluate("test").expect("evaluate");
    let names = report
        .metrics
        .iter()
        .map(|metric| metric.name.as_str())
        .collect::<Vec<_>>();
    for required in [
        "pattern_grounding",
        "abstraction_correctness",
        "scope_precision",
        "counterexample_coverage",
        "transfer_success_rate",
        "useful_transfer_rate",
        "negative_transfer_rate",
        "dangerous_transfer_rate",
        "hallucinated_rule_rate",
        "strategy_quality_delta",
        "pattern_compression_ratio",
        "explanation_dependency",
        "withholding_accuracy",
    ] {
        assert!(names.contains(&required), "missing metric {required}");
    }
}

#[test]
fn failure_taxonomy_names_negative_transfer_and_epistemic_failures() {
    let report = Phase7TransferEvaluationProtocolEvaluator::evaluate("test").expect("evaluate");
    let codes = report
        .failure_taxonomy
        .iter()
        .map(|failure| failure.code.as_str())
        .collect::<Vec<_>>();
    for required in [
        "unsupported_abstraction",
        "scope_overreach",
        "counterexample_ignored",
        "literal_surface_copy",
        "causal_confusion",
        "negative_transfer",
        "missed_transfer",
        "confidence_without_outcome",
    ] {
        assert!(codes.contains(&required), "missing failure {required}");
    }
}

#[test]
fn missing_scope_counterexample_and_lineage_are_rejected() {
    let dataset = load_phase7_transfer_benchmark().expect("dataset loads");
    let mut scenario = dataset.scenarios[0].clone();
    scenario.candidate_pattern.applicability_scope.clear();
    scenario.candidate_pattern.counterexample_memory_ids.clear();
    scenario.evidence_graph.clear();

    let validation = validate_transfer_scenario(&scenario);
    assert!(!validation.valid);
    assert!(validation
        .violations
        .contains(&"applicability_scope_required".to_string()));
    assert!(validation
        .violations
        .contains(&"counterexample_required".to_string()));
    assert!(validation
        .violations
        .contains(&"evidence_graph_lineage_required".to_string()));
}

#[test]
fn unsupported_or_unbounded_pattern_candidates_are_rejected() {
    let dataset = load_phase7_transfer_benchmark().expect("dataset loads");
    let mut scenario = dataset.scenarios[0].clone();
    scenario
        .source_experiences
        .retain(|item| item.relation != "supports");
    scenario.candidate_pattern.confidence = 1.5;

    let validation = validate_transfer_scenario(&scenario);
    assert!(!validation.valid);
    assert!(validation
        .violations
        .contains(&"multiple_supports_and_counterevidence_required".to_string()));
    assert!(validation
        .violations
        .contains(&"confidence_must_be_finite_and_bounded".to_string()));
}

#[test]
fn phase7_1_freezes_protocol_without_claiming_transfer_performance() {
    let report = Phase7TransferEvaluationProtocolEvaluator::evaluate("test").expect("evaluate");
    assert!(report.all_scenarios_valid);
    assert_eq!(
        report.decision,
        Phase7TransferDecision::ProtocolFrozenPatternAlgorithmBlocked
    );
    assert!(report.guards.eval_only);
    assert!(report.guards.dataset_frozen);
    assert!(report.guards.held_out_cases_reserved);
    assert!(report.guards.baseline_comparison_protocol_complete);
    assert!(!report.guards.outcome_evaluation_complete);
    assert!(!report.guards.pattern_discovery_implemented);
    assert!(!report.guards.pattern_persistence_authorized);
    assert!(!report.guards.runtime_authorized);
    assert!(!report.guards.hermes_authorized);
    assert!(!report.guards.autonomous_promotion_authorized);
}
