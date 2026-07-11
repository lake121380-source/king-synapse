use std::collections::BTreeSet;
use synapse_eval::{
    load_phase7_pattern_extraction_design, load_phase7_transfer_benchmark,
    validate_pattern_extraction_batch, validate_pattern_extraction_submission, PatternStatus,
    Phase7PatternExtractionDecision, Phase7PatternExtractionProtocolEvaluator, TransferSplit,
};

#[test]
fn extraction_dataset_uses_only_the_ten_phase7_1_design_cases() {
    let dataset = load_phase7_pattern_extraction_design().expect("dataset loads");
    assert_eq!(dataset.cases.len(), 10);
    let report = Phase7PatternExtractionProtocolEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.dataset.case_count, 10);
    assert_eq!(report.dataset.distinct_source_scenarios, 10);
    assert_eq!(report.dataset.held_out_references, 0);
    assert!(report.guards.design_cases_only);
    assert!(report.guards.held_out_cases_untouched);
}

#[test]
fn extraction_source_ids_exactly_match_phase7_1_design_split() {
    let extraction = load_phase7_pattern_extraction_design().expect("extraction dataset loads");
    let transfer = load_phase7_transfer_benchmark().expect("transfer dataset loads");
    let extraction_ids = extraction
        .cases
        .iter()
        .map(|case| case.source_transfer_scenario_id.as_str())
        .collect::<BTreeSet<_>>();
    let design_ids = transfer
        .scenarios
        .iter()
        .filter(|scenario| scenario.split == TransferSplit::Design)
        .map(|scenario| scenario.id.as_str())
        .collect::<BTreeSet<_>>();
    assert_eq!(extraction_ids, design_ids);
}
#[test]
fn extractor_input_excludes_target_answers_runtime_and_held_out_content() {
    let dataset = load_phase7_pattern_extraction_design().expect("dataset loads");
    for case in dataset.cases {
        for prohibited in [
            "target_problem",
            "expected_transfer",
            "held_out_cases",
            "runtime_state",
        ] {
            assert!(case
                .input
                .prohibited_inputs
                .iter()
                .any(|field| field == prohibited));
        }
        assert_eq!(case.input.max_pattern_candidates, 1);
    }
}

#[test]
fn reference_candidates_satisfy_phase7_and_extraction_contracts() {
    let dataset = load_phase7_pattern_extraction_design().expect("dataset loads");
    for case in dataset.cases {
        let validation =
            validate_pattern_extraction_submission(&case.input, &case.reference_candidate);
        assert!(
            validation.valid,
            "{}: {:#?}",
            case.id, validation.violations
        );
        assert_eq!(case.reference_candidate.status, PatternStatus::Proposed);
        assert!(case.reference_candidate.confidence <= 0.75);
        assert!(case.reference_candidate.validation_outcome_ids.is_empty());
    }
}

#[test]
fn evidence_ids_and_provenance_must_come_from_authoritative_input() {
    let dataset = load_phase7_pattern_extraction_design().expect("dataset loads");
    let case = &dataset.cases[0];

    let mut hallucinated = case.reference_candidate.clone();
    hallucinated.supporting_evidence[0].memory_id = "invented_memory".to_string();
    let validation = validate_pattern_extraction_submission(&case.input, &hallucinated);
    assert!(!validation.valid);
    assert!(validation
        .violations
        .contains(&"evidence_reference_not_in_extraction_input".to_string()));

    let mut mismatched = case.reference_candidate.clone();
    mismatched.supporting_evidence[0].domain = "invented_domain".to_string();
    let validation = validate_pattern_extraction_submission(&case.input, &mismatched);
    assert!(!validation.valid);
    assert!(validation
        .violations
        .contains(&"evidence_provenance_mismatch".to_string()));
}

#[test]
fn supplied_counterexamples_cannot_be_silently_dropped() {
    let dataset = load_phase7_pattern_extraction_design().expect("dataset loads");
    let case = &dataset.cases[0];
    let mut candidate = case.reference_candidate.clone();
    candidate.counterexamples.clear();

    let validation = validate_pattern_extraction_submission(&case.input, &candidate);
    assert!(!validation.valid);
    assert!(validation
        .violations
        .contains(&"supplied_counterexample_omitted".to_string()));
    assert!(validation
        .violations
        .contains(&"supplied_counterexample_must_be_considered".to_string()));
}

#[test]
fn extraction_cannot_promote_validate_or_overstate_confidence() {
    let dataset = load_phase7_pattern_extraction_design().expect("dataset loads");
    let case = &dataset.cases[0];
    let mut candidate = case.reference_candidate.clone();
    candidate.status = PatternStatus::Active;
    candidate.confidence = 0.95;
    candidate
        .validation_outcome_ids
        .push("not_observed".to_string());

    let validation = validate_pattern_extraction_submission(&case.input, &candidate);
    for required in [
        "extraction_output_must_remain_proposed",
        "proposed_confidence_exceeds_phase7_2_cap",
        "extraction_cannot_claim_validation_outcomes",
    ] {
        assert!(validation.violations.iter().any(|item| item == required));
    }
}

#[test]
fn batch_contract_rejects_zero_or_multiple_candidates() {
    let dataset = load_phase7_pattern_extraction_design().expect("dataset loads");
    let case = &dataset.cases[0];

    let empty = validate_pattern_extraction_batch(&case.input, &[]);
    assert!(!empty.valid);
    assert!(empty
        .violations
        .contains(&"at_least_one_pattern_candidate_required".to_string()));

    let multiple = validate_pattern_extraction_batch(
        &case.input,
        &[
            case.reference_candidate.clone(),
            case.reference_candidate.clone(),
        ],
    );
    assert!(!multiple.valid);
    assert!(multiple
        .violations
        .contains(&"pattern_candidate_limit_exceeded".to_string()));
}

#[test]
fn protocol_freezes_extraction_metrics_without_claiming_model_results() {
    let report = Phase7PatternExtractionProtocolEvaluator::evaluate("test").expect("evaluate");
    let metrics = report
        .metrics
        .iter()
        .map(|metric| metric.name.as_str())
        .collect::<Vec<_>>();
    for required in [
        "contract_validity",
        "evidence_grounding",
        "evidence_coverage",
        "scope_preservation",
        "counterexample_handling",
        "abstraction_specificity",
        "compression_ratio",
        "unsupported_claim_rate",
        "evidence_id_hallucination_rate",
        "boundary_loss_rate",
        "falsifiability_rate",
    ] {
        assert!(metrics.contains(&required), "missing metric {required}");
    }
    assert!(!report.guards.extraction_algorithm_implemented);
    assert!(!report.guards.model_evaluation_completed);
}

#[test]
fn phase7_2_keeps_persistence_runtime_hermes_and_autonomy_blocked() {
    let report = Phase7PatternExtractionProtocolEvaluator::evaluate("test").expect("evaluate");
    assert!(report.all_reference_candidates_valid);
    assert!(report.all_negative_cases_rejected);
    assert_eq!(
        report.decision,
        Phase7PatternExtractionDecision::ProtocolFrozenExtractionAlgorithmBlocked
    );
    assert!(report.guards.eval_only);
    assert!(!report.guards.pattern_persistence_authorized);
    assert!(!report.guards.runtime_authorized);
    assert!(!report.guards.hermes_authorized);
    assert!(!report.guards.autonomous_promotion_authorized);
}
