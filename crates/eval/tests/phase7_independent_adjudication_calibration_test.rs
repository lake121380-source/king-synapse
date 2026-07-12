use synapse_eval::phase7_independent_adjudication_calibration::{
    aggregate_candidate_scope_expansion, aggregate_candidate_support_label,
    build_phase7_blind_review_packet, compute_confusion_matrix, compute_scope_confusion_matrix,
    compute_support_agreement, load_phase7_adjudication_measurement_protocol,
    load_phase7_adjudication_template, load_phase7_reviewer_a_template,
    load_phase7_reviewer_b_template, BinaryCalibrationView, CandidateJudgeCalibrationRow,
    HumanSupportLabel, MeasurementObjectKind, Phase7AdjudicationCalibrationDecision,
    Phase7AdjudicationCalibrationEvaluator, ScopeAssessment, ScopeJudgeCalibrationRow,
};

fn close(actual: Option<f64>, expected: f64) {
    let actual = actual.expect("metric should be defined");
    assert!((actual - expected).abs() < 1e-12, "{actual} != {expected}");
}

#[test]
fn measurement_objects_are_explicitly_separated_and_frozen() {
    let protocol = load_phase7_adjudication_measurement_protocol().expect("protocol");
    assert_eq!(protocol.measurement_objects.len(), 8);
    for item in protocol.measurement_objects {
        let expected_studied = matches!(
            item.object,
            MeasurementObjectKind::Candidate | MeasurementObjectKind::FrozenJudge
        );
        assert_eq!(item.studied, expected_studied);
        assert!(!item.modified);
    }
    assert!(!protocol.calibration_policy.threshold_change_allowed);
    assert!(!protocol.calibration_policy.prompt_change_allowed);
    assert!(!protocol.calibration_policy.rule_change_allowed);
    assert!(!protocol.calibration_policy.same_data_optimization_allowed);
}

#[test]
fn claim_origin_definitions_separate_synthesis_from_unsupportedness() {
    let protocol = load_phase7_adjudication_measurement_protocol().expect("protocol");
    let definitions = protocol
        .claim_origin_definitions
        .as_object()
        .expect("origin definitions");
    assert!(definitions.contains_key("explicit"));
    assert!(definitions.contains_key("inferred"));
    let synthesized = definitions["synthesized"].as_str().expect("synthesized");
    assert!(synthesized.contains("does not automatically mean unsupported"));
}

#[test]
fn frozen_outputs_produce_stable_claim_source_anchors_without_claiming_segmentation() {
    let report = Phase7AdjudicationCalibrationEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(report.claim_source_anchors.len(), 65);
    assert!(report
        .claim_source_anchors
        .iter()
        .all(|anchor| anchor.requires_independent_atomic_segmentation));
    assert_eq!(
        report
            .claim_source_anchors
            .iter()
            .map(|anchor| anchor.anchor_id.as_str())
            .collect::<std::collections::BTreeSet<_>>()
            .len(),
        65
    );
    assert!(report
        .claim_source_anchors
        .iter()
        .all(|anchor| !anchor.source_text.trim().is_empty()
            && anchor.response_sha256.len() == 64
            && anchor.source_text_sha256.len() == 64));
}

#[test]
fn reviewer_submissions_and_model_adjudication_are_completed_without_gold_claim() {
    for (submission, expected_claims) in [
        (load_phase7_reviewer_a_template().expect("reviewer a"), 74),
        (load_phase7_reviewer_b_template().expect("reviewer b"), 77),
    ] {
        assert!(submission.completed);
        assert_eq!(submission.claims.len(), expected_claims);
        assert!(submission.blind_to_other_reviewer);
        assert!(submission.blind_to_frozen_judge);
        assert!(submission.blind_to_phase7_3_aggregates);
        assert!(!submission.held_out_accessed);
    }
    let adjudication = load_phase7_adjudication_template().expect("adjudication");
    assert!(adjudication.completed);
    assert_eq!(adjudication.claims.len(), 77);
    assert!(adjudication.lineage.is_some());
    assert!(adjudication.disagreements_preserved);
    assert!(!adjudication.held_out_accessed);
}

#[test]
fn support_agreement_distinguishes_boundary_and_fundamental_disagreement() {
    use HumanSupportLabel::{NotAssessable, PartiallySupported, Supported, Unsupported};
    let metrics = compute_support_agreement(&[
        (Supported, Supported),
        (PartiallySupported, Unsupported),
        (Supported, Unsupported),
        (NotAssessable, Supported),
    ]);
    assert_eq!(metrics.aligned_claim_count, 3);
    assert_eq!(metrics.excluded_not_assessable_count, 1);
    close(metrics.raw_agreement, 1.0 / 3.0);
    assert!(metrics.linear_weighted_kappa.is_some());
    assert_eq!(metrics.boundary_disagreement_count, 1);
    assert_eq!(metrics.fundamental_disagreement_count, 1);
}

#[test]
fn frozen_judge_calibration_uses_unsupported_as_the_positive_class() {
    use HumanSupportLabel::{NotAssessable, PartiallySupported, Supported, Unsupported};
    let rows = [
        CandidateJudgeCalibrationRow {
            case_id: "a".into(),
            silver_support_label: Supported,
            frozen_judge_unsupported_warning: false,
        },
        CandidateJudgeCalibrationRow {
            case_id: "b".into(),
            silver_support_label: Supported,
            frozen_judge_unsupported_warning: true,
        },
        CandidateJudgeCalibrationRow {
            case_id: "c".into(),
            silver_support_label: PartiallySupported,
            frozen_judge_unsupported_warning: true,
        },
        CandidateJudgeCalibrationRow {
            case_id: "d".into(),
            silver_support_label: Unsupported,
            frozen_judge_unsupported_warning: false,
        },
        CandidateJudgeCalibrationRow {
            case_id: "e".into(),
            silver_support_label: NotAssessable,
            frozen_judge_unsupported_warning: true,
        },
    ];
    let strict = compute_confusion_matrix(&rows, BinaryCalibrationView::StrictSafety);
    assert_eq!(strict.true_positive, 1);
    assert_eq!(strict.false_positive, 1);
    assert_eq!(strict.false_negative, 1);
    assert_eq!(strict.true_negative, 1);
    assert_eq!(strict.excluded, 1);
    close(strict.precision, 0.5);
    close(strict.recall_sensitivity, 0.5);
    close(strict.specificity, 0.5);
    close(strict.balanced_accuracy, 0.5);
    close(strict.matthews_correlation_coefficient, 0.0);
    for interval in [
        strict.precision_wilson_95.as_ref(),
        strict.recall_sensitivity_wilson_95.as_ref(),
        strict.specificity_wilson_95.as_ref(),
        strict.false_positive_rate_wilson_95.as_ref(),
        strict.false_negative_rate_wilson_95.as_ref(),
    ] {
        let interval = interval.expect("Wilson interval");
        assert!(0.0 <= interval.lower && interval.lower <= interval.upper);
        assert!(interval.upper <= 1.0);
    }

    let strong = compute_confusion_matrix(&rows, BinaryCalibrationView::StrongError);
    assert_eq!(strong.excluded, 2);
    assert_eq!(strong.true_positive, 0);
    assert_eq!(strong.false_negative, 1);
    assert_eq!(strong.false_positive, 1);
    assert_eq!(strong.true_negative, 1);
}

#[test]
fn candidate_aggregation_and_scope_calibration_are_predeclared_before_real_labels() {
    use HumanSupportLabel::{PartiallySupported, Supported, Unsupported};
    assert_eq!(
        aggregate_candidate_support_label([Supported, PartiallySupported]),
        PartiallySupported
    );
    assert_eq!(
        aggregate_candidate_support_label([Supported, Unsupported]),
        Unsupported
    );
    assert_eq!(
        aggregate_candidate_scope_expansion([
            ScopeAssessment::Preserved,
            ScopeAssessment::Expanded,
        ]),
        Some(true)
    );

    let scope = compute_scope_confusion_matrix(&[
        ScopeJudgeCalibrationRow {
            case_id: "a".into(),
            adjudicated_scope_expanded: Some(true),
            frozen_judge_scope_warning: true,
        },
        ScopeJudgeCalibrationRow {
            case_id: "b".into(),
            adjudicated_scope_expanded: Some(false),
            frozen_judge_scope_warning: true,
        },
        ScopeJudgeCalibrationRow {
            case_id: "c".into(),
            adjudicated_scope_expanded: None,
            frozen_judge_scope_warning: false,
        },
    ]);
    assert_eq!(scope.true_positive, 1);
    assert_eq!(scope.false_positive, 1);
    assert_eq!(scope.excluded, 1);
}

#[test]
fn frozen_judge_is_diagnostically_calibrated_against_model_silver() {
    let report = Phase7AdjudicationCalibrationEvaluator::evaluate("test").expect("evaluate");
    assert_eq!(
        report.decision,
        Phase7AdjudicationCalibrationDecision::FrozenJudgeDiagnosticCalibrationComplete
    );
    assert!(report.agreement.is_none());
    assert_eq!(report.candidate_calibration_rows.len(), 10);
    let strict = report
        .strict_safety_calibration
        .expect("strict safety calibration");
    assert_eq!(
        (
            strict.true_positive,
            strict.false_positive,
            strict.false_negative,
            strict.true_negative,
            strict.excluded
        ),
        (9, 1, 0, 0, 0)
    );
    close(strict.precision, 0.9);
    close(strict.recall_sensitivity, 1.0);
    close(strict.specificity, 0.0);
    close(strict.balanced_accuracy, 0.5);
    assert!(strict.matthews_correlation_coefficient.is_none());
    let strong = report
        .strong_error_calibration
        .expect("strong error calibration");
    assert_eq!(
        (
            strong.true_positive,
            strong.false_positive,
            strong.false_negative,
            strong.true_negative,
            strong.excluded
        ),
        (2, 1, 0, 0, 7)
    );
    close(strong.precision, 2.0 / 3.0);
    close(strong.recall_sensitivity, 1.0);
    close(strong.specificity, 0.0);
    close(strong.balanced_accuracy, 0.5);
    assert!(strong.matthews_correlation_coefficient.is_none());
    assert!(report.scope_calibration.is_none());
    assert!(report.guards.reviewer_a_completed);
    assert!(report.guards.reviewer_b_completed);
    assert!(report.guards.independent_adjudication_completed);
    assert!(report.guards.silver_labels_frozen);
    assert!(report.silver_labels_sha256.is_some());
    assert_eq!(
        report.silver_label_status.as_deref(),
        Some("model_adjudicated_silver_not_human_gold")
    );
    assert!(report.guards.scorer_calibration_completed);
}

#[test]
fn phase7_3_1_preserves_extractor_judge_held_out_and_runtime_boundaries() {
    let report = Phase7AdjudicationCalibrationEvaluator::evaluate("test").expect("evaluate");
    let guards = report.guards;
    assert!(guards.frozen_phase7_2_3_outputs_reused);
    assert!(guards.evidence_bundle_frozen);
    assert!(!guards.candidate_modified);
    assert!(!guards.frozen_judge_modified);
    assert!(!guards.prompt_modified);
    assert!(!guards.provider_modified);
    assert!(!guards.parser_modified);
    assert!(!guards.repair_policy_modified);
    assert!(!guards.extraction_algorithm_modified);
    assert!(!guards.provider_calls_made);
    assert!(guards.held_out_cases_untouched);
    assert!(!guards.runtime_authorized);
    assert!(!guards.hermes_authorized);
    assert!(!guards.candidate_learning_authorized);
    assert!(!guards.knowledge_promotion_authorized);
}

#[test]
fn checked_in_report_matches_diagnostic_calibration_boundary() {
    let checked: serde_json::Value = serde_json::from_str(include_str!(
        "../reports/phase7_independent_adjudication_calibration.json"
    ))
    .expect("checked report");
    assert_eq!(
        checked["decision"],
        "frozen_judge_diagnostic_calibration_complete"
    );
    assert_eq!(
        checked["claim_source_anchors"].as_array().unwrap().len(),
        65
    );
    assert!(checked["agreement"].is_null());
    assert_eq!(
        checked["candidate_calibration_rows"]
            .as_array()
            .unwrap()
            .len(),
        10
    );
    assert_eq!(checked["strict_safety_calibration"]["true_positive"], 9);
    assert_eq!(checked["strict_safety_calibration"]["false_positive"], 1);
    assert_eq!(checked["strict_safety_calibration"]["specificity"], 0.0);
    assert_eq!(checked["strong_error_calibration"]["true_positive"], 2);
    assert_eq!(checked["strong_error_calibration"]["excluded"], 7);
    assert!(checked["scope_calibration"].is_null());
    assert_eq!(checked["guards"]["held_out_cases_untouched"], true);
    assert_eq!(checked["guards"]["runtime_authorized"], false);
    assert_eq!(checked["guards"]["hermes_authorized"], false);
}

#[test]
fn repeated_evaluation_preserves_all_scientific_content() {
    let mut a = serde_json::to_value(
        Phase7AdjudicationCalibrationEvaluator::evaluate("a").expect("evaluate a"),
    )
    .unwrap();
    let mut b = serde_json::to_value(
        Phase7AdjudicationCalibrationEvaluator::evaluate("b").expect("evaluate b"),
    )
    .unwrap();
    a.as_object_mut().unwrap().remove("tag");
    a.as_object_mut().unwrap().remove("generated_at");
    b.as_object_mut().unwrap().remove("tag");
    b.as_object_mut().unwrap().remove("generated_at");
    assert_eq!(a, b);
}

#[test]
fn blind_review_packet_contains_only_frozen_evidence_candidates_and_anchors() {
    let packet = build_phase7_blind_review_packet().expect("blind review packet");
    assert_eq!(packet.cases.len(), 10);
    assert_eq!(
        packet
            .cases
            .iter()
            .map(|case| case.claim_source_anchors.len())
            .sum::<usize>(),
        65
    );
    assert!(packet.blind_to_other_reviewer);
    assert!(packet.blind_to_frozen_judge);
    assert!(packet.blind_to_phase7_3_aggregates);
    assert!(!packet.held_out_accessed);
    assert!(packet.cases.iter().all(|case| {
        case.case_id == case.evidence_input.case_id
            && case.claim_source_anchors.iter().all(|anchor| {
                anchor.case_id == case.case_id && anchor.response_sha256 == case.response_sha256
            })
    }));

    let value = serde_json::to_value(packet).expect("serialize packet");
    let forbidden_structural_keys = [
        "reference_candidate",
        "unsupported_claim_rate",
        "scope_retention",
        "scorer_policy",
        "capability_matrix",
        "judge_warning",
        "reviewer_a",
        "reviewer_b",
        "adjudication",
    ];
    fn assert_keys_are_blind(value: &serde_json::Value, forbidden: &[&str]) {
        match value {
            serde_json::Value::Object(map) => {
                for (key, child) in map {
                    assert!(
                        !forbidden.contains(&key.as_str()),
                        "forbidden blind-packet key: {key}"
                    );
                    assert_keys_are_blind(child, forbidden);
                }
            }
            serde_json::Value::Array(items) => {
                for item in items {
                    assert_keys_are_blind(item, forbidden);
                }
            }
            _ => {}
        }
    }
    assert_keys_are_blind(&value, &forbidden_structural_keys);
}
