use synapse_eval::phase7_candidate_error_analysis::{
    load_phase7_candidate_error_annotations, CandidateFailureKind, MetricConfoundKind,
    Phase7CandidateErrorAnalysisDecision, Phase7CandidateErrorAnalysisEvaluator,
};

fn close(left: f64, right: f64) {
    assert!((left - right).abs() < 1e-12, "left={left} right={right}");
}

#[test]
fn taxonomy_analyzes_exactly_the_frozen_ten_design_candidates() {
    let report = Phase7CandidateErrorAnalysisEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.summary.candidate_count, 10);
    assert_eq!(report.summary.candidates_with_failure_labels, 10);
    assert_eq!(report.cases.len(), 10);
    assert!(report
        .cases
        .iter()
        .all(|case| case.case_id.starts_with("extract_")));
    assert!(report.guards.design_cases_only);
    assert!(report.guards.held_out_cases_untouched);
}

#[test]
fn annotation_protocol_is_a_seed_not_independent_ground_truth() {
    let annotations = load_phase7_candidate_error_annotations().expect("annotations");
    assert_eq!(
        annotations.annotation_mode,
        "single_reviewer_model_assisted_seed"
    );
    assert_eq!(annotations.reviewer_count, 1);
    assert!(!annotations.independent_second_review);
    assert!(annotations.inter_rater_agreement.is_none());
    assert!(!annotations.held_out_accessed);
}

#[test]
fn failure_taxonomy_preserves_zero_count_categories() {
    let report = Phase7CandidateErrorAnalysisEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.taxonomy.len(), 11);
    assert_eq!(report.summary.primary_failure_distribution.len(), 11);
    assert!(CandidateFailureKind::all_for_test()
        .iter()
        .all(|kind| report.taxonomy.iter().any(|item| item.kind == *kind)));
}

#[test]
fn primary_mechanisms_are_prediction_generalization_causality_and_abstraction() {
    let report = Phase7CandidateErrorAnalysisEvaluator::evaluate("test").expect("evaluate");
    let count = |kind| {
        report
            .summary
            .primary_failure_distribution
            .iter()
            .find(|item| item.kind == kind)
            .expect("kind")
            .primary_count
    };
    assert_eq!(count(CandidateFailureKind::PredictionWithoutSupport), 4);
    assert_eq!(count(CandidateFailureKind::UnsupportedGeneralization), 3);
    assert_eq!(count(CandidateFailureKind::CausalLeap), 2);
    assert_eq!(count(CandidateFailureKind::OverAbstraction), 1);
    assert_eq!(report.summary.total_failure_labels, 25);
}

#[test]
fn evidence_and_counterexample_lineage_are_not_the_observed_bottleneck() {
    let report = Phase7CandidateErrorAnalysisEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.summary.evidence_failure_case_count, 0);
    assert_eq!(report.summary.counterexample_failure_case_count, 0);
    assert!(report.cases.iter().all(|case| {
        case.quality_metrics.evidence_attribution_accuracy == 1.0
            && case.quality_metrics.evidence_coverage == 1.0
            && case.quality_metrics.counterexample_handling == 1.0
    }));
}

#[test]
fn scorer_warnings_are_not_treated_as_semantic_ground_truth() {
    let report = Phase7CandidateErrorAnalysisEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.summary.unsupported_warning_count, 10);
    assert_eq!(report.summary.scope_warning_count, 6);
    assert_eq!(report.summary.scope_expansion_label_count, 0);
    close(report.summary.scope_warning_confirmation_rate, 0.0);

    let confound_count = |kind| {
        report
            .summary
            .metric_confound_distribution
            .iter()
            .find(|item| item.kind == kind)
            .expect("confound")
            .case_count
    };
    assert_eq!(
        confound_count(MetricConfoundKind::LexicalNoveltyConfound),
        5
    );
    assert_eq!(
        confound_count(MetricConfoundKind::ScopeFieldPlacementConfound),
        6
    );
}

#[test]
fn falsifiability_structure_is_separated_from_semantic_validity() {
    let report = Phase7CandidateErrorAnalysisEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(
        report
            .summary
            .falsifiability
            .structural_fields_present_count,
        10
    );
    close(
        report.summary.falsifiability.structural_fields_present_rate,
        1.0,
    );
    assert_eq!(report.summary.falsifiability.direct_in_scope_test_count, 8);
    close(report.summary.falsifiability.direct_in_scope_test_rate, 0.8);
    assert_eq!(
        report
            .summary
            .falsifiability
            .semantic_validity_established_count,
        0
    );
}

#[test]
fn phase7_3_changes_no_extraction_or_runtime_authority() {
    let report = Phase7CandidateErrorAnalysisEvaluator::evaluate("test").expect("evaluate");
    assert!(report.guards.frozen_phase7_2_3_execution_reused);
    assert!(!report.guards.provider_calls_made);
    assert!(!report.guards.prompt_modified);
    assert!(!report.guards.parser_modified);
    assert!(!report.guards.scorer_modified);
    assert!(!report.guards.extraction_algorithm_modified);
    assert!(!report.guards.candidate_learning_authorized);
    assert!(!report.guards.pattern_persistence_authorized);
    assert!(!report.guards.knowledge_promotion_authorized);
    assert!(!report.guards.runtime_authorized);
    assert!(!report.guards.hermes_authorized);
}

#[test]
fn independent_review_remains_the_next_required_step() {
    let report = Phase7CandidateErrorAnalysisEvaluator::evaluate("test").expect("evaluate");
    assert!(!report.guards.independent_second_review_completed);
    assert_eq!(
        report.decision,
        Phase7CandidateErrorAnalysisDecision::TaxonomySeededIndependentReviewRequired
    );
}

trait CandidateFailureKindTestExt {
    fn all_for_test() -> [CandidateFailureKind; 11];
}

impl CandidateFailureKindTestExt for CandidateFailureKind {
    fn all_for_test() -> [CandidateFailureKind; 11] {
        [
            CandidateFailureKind::UnsupportedGeneralization,
            CandidateFailureKind::ScopeExpansion,
            CandidateFailureKind::MissingEvidence,
            CandidateFailureKind::WeakEvidence,
            CandidateFailureKind::PredictionWithoutSupport,
            CandidateFailureKind::CausalLeap,
            CandidateFailureKind::OverAbstraction,
            CandidateFailureKind::CounterexampleIgnored,
            CandidateFailureKind::AmbiguousPattern,
            CandidateFailureKind::DuplicatePattern,
            CandidateFailureKind::Other,
        ]
    }
}
