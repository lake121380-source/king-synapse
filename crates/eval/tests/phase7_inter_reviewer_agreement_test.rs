use synapse_eval::phase7_candidate_error_analysis::CandidateFailureKind;
use synapse_eval::phase7_independent_adjudication_calibration::{
    build_phase7_blind_review_packet, validate_phase7_reviewer_submission_against_frozen_inputs,
    AnnotationConfidence, AtomicClaimAnnotation, CausalStrengthAssessment, ClaimDimensionLabels,
    ClaimOrigin, ClaimSourceSpan, CounterexampleAssessment, FalsifiabilityAssessment,
    HumanSupportLabel, PredictionSupportAssessment, ReviewerAnnotationSubmission, ScopeAssessment,
};
use synapse_eval::phase7_inter_reviewer_agreement::{
    compute_inter_reviewer_agreement, load_phase7_inter_reviewer_agreement_protocol,
    InterReviewerAgreementDecision, Phase7InterReviewerAgreementEvaluator,
};

fn claim(
    id: &str,
    case_id: &str,
    anchor_id: &str,
    start: usize,
    end: usize,
    label: HumanSupportLabel,
) -> AtomicClaimAnnotation {
    AtomicClaimAnnotation {
        claim_id: id.to_string(),
        case_id: case_id.to_string(),
        response_sha256: "a".repeat(64),
        anchor_id: anchor_id.to_string(),
        source_span: ClaimSourceSpan {
            start_char: start,
            end_char: end,
            source_excerpt: "x".repeat(end - start),
        },
        claim_text: format!("claim {id}"),
        claim_origin: ClaimOrigin::Explicit,
        claimed_evidence_ids: vec!["evidence-1".to_string()],
        human_support_label: label,
        dimension_labels: ClaimDimensionLabels {
            scope: ScopeAssessment::Preserved,
            causal_strength: CausalStrengthAssessment::NotPresent,
            prediction_support: PredictionSupportAssessment::NotPresent,
            counterexample_handling: CounterexampleAssessment::NotPresent,
            falsifiability: FalsifiabilityAssessment::StructuralOnly,
        },
        failure_kinds: Vec::<CandidateFailureKind>::new(),
        reviewer_rationale: "synthetic agreement test".to_string(),
        annotation_confidence: AnnotationConfidence::High,
    }
}

fn submission(id: &str, claims: Vec<AtomicClaimAnnotation>) -> ReviewerAnnotationSubmission {
    ReviewerAnnotationSubmission {
        schema_version: 1,
        submission_id: id.to_string(),
        reviewer_id: id.to_string(),
        reviewer_role: "independent_semantic_reviewer".to_string(),
        source_execution_id: "phase7.2.3-deepseek-real-provider-readiness-v1".to_string(),
        protocol_id: "phase7.3.1-independent-adjudication-frozen-judge-calibration-v1".to_string(),
        completed: true,
        blind_to_other_reviewer: true,
        blind_to_frozen_judge: true,
        blind_to_phase7_3_aggregates: true,
        held_out_accessed: false,
        claims,
    }
}

#[test]
fn agreement_gate_reports_two_frozen_ai_submissions() {
    let report = Phase7InterReviewerAgreementEvaluator::evaluate("test").expect("report");
    assert_eq!(
        report.decision,
        InterReviewerAgreementDecision::AgreementReportReadyAdjudicationRequired
    );
    let metrics = report.metrics.expect("agreement metrics");
    assert_eq!(metrics.segmentation.reviewer_a_claim_count, 74);
    assert_eq!(metrics.segmentation.reviewer_b_claim_count, 77);
    assert!(
        metrics
            .semantic
            .support
            .raw_agreement
            .expect("raw agreement")
            > 0.0
    );
    assert!(report.guards.reviewer_a_completed);
    assert!(report.guards.reviewer_b_completed);
    assert!(report.guards.agreement_report_completed);
    assert!(report.guards.raw_blind_submissions_only);
    assert!(!report.guards.adjudicated_labels_used);
    assert!(!report.guards.frozen_judge_visible);
    assert!(!report.guards.phase7_3_seed_visible);
    assert!(report.guards.held_out_cases_untouched);
}

#[test]
fn agreement_protocol_freezes_span_alignment_before_annotations() {
    let protocol = load_phase7_inter_reviewer_agreement_protocol().expect("protocol");
    assert_eq!(protocol.source_span_unit, "unicode_scalar_index_half_open");
    assert_eq!(protocol.alignment_policy.minimum_iou, 0.5);
    assert!(!protocol.alignment_policy.claim_text_similarity_used);
    assert_eq!(
        protocol.agreement_input,
        "raw_blind_reviewer_submissions_only"
    );
    assert!(!protocol.adjudicated_labels_allowed);
    assert!(!protocol.frozen_judge_visible);
    assert!(!protocol.phase7_3_seed_visible);
    assert!(!protocol.held_out_accessed);
}

#[test]
fn independent_segmentation_is_aligned_before_semantic_agreement() {
    let protocol = load_phase7_inter_reviewer_agreement_protocol().expect("protocol");
    let reviewer_a = submission(
        "reviewer-a",
        vec![
            claim(
                "a1",
                "case-1",
                "anchor-1",
                0,
                5,
                HumanSupportLabel::Supported,
            ),
            claim(
                "a2",
                "case-1",
                "anchor-1",
                5,
                10,
                HumanSupportLabel::PartiallySupported,
            ),
            claim(
                "a3",
                "case-2",
                "anchor-2",
                0,
                10,
                HumanSupportLabel::Unsupported,
            ),
        ],
    );
    let reviewer_b = submission(
        "reviewer-b",
        vec![
            claim(
                "b1",
                "case-1",
                "anchor-1",
                0,
                5,
                HumanSupportLabel::Supported,
            ),
            claim(
                "b2",
                "case-1",
                "anchor-1",
                5,
                10,
                HumanSupportLabel::Unsupported,
            ),
            claim(
                "b3",
                "case-2",
                "anchor-2",
                0,
                5,
                HumanSupportLabel::Unsupported,
            ),
            claim(
                "b4",
                "case-2",
                "anchor-2",
                5,
                10,
                HumanSupportLabel::Unsupported,
            ),
        ],
    );
    let metrics =
        compute_inter_reviewer_agreement(&reviewer_a, &reviewer_b, &protocol.alignment_policy)
            .expect("agreement");

    assert_eq!(metrics.segmentation.reviewer_a_claim_count, 3);
    assert_eq!(metrics.segmentation.reviewer_b_claim_count, 4);
    assert_eq!(metrics.segmentation.aligned_claim_pair_count, 3);
    assert_eq!(metrics.segmentation.exact_boundary_match_count, 2);
    assert_eq!(metrics.segmentation.split_disagreement_count, 1);
    assert_eq!(metrics.segmentation.merge_disagreement_count, 0);
    assert_eq!(metrics.segmentation.unmatched_reviewer_b_claim_count, 1);
    assert_eq!(metrics.semantic.support.aligned_claim_count, 3);
    assert_eq!(metrics.semantic.support.boundary_disagreement_count, 1);
    assert!(metrics.semantic.support.linear_weighted_kappa.is_some());
    assert!(metrics
        .semantic
        .support_krippendorff_alpha_ordinal
        .is_some());
}

#[test]
fn agreement_rejects_non_blind_or_incomplete_submissions() {
    let protocol = load_phase7_inter_reviewer_agreement_protocol().expect("protocol");
    let mut reviewer_a = submission(
        "reviewer-a",
        vec![claim(
            "a1",
            "case-1",
            "anchor-1",
            0,
            5,
            HumanSupportLabel::Supported,
        )],
    );
    let reviewer_b = submission(
        "reviewer-b",
        vec![claim(
            "b1",
            "case-1",
            "anchor-1",
            0,
            5,
            HumanSupportLabel::Supported,
        )],
    );
    reviewer_a.blind_to_frozen_judge = false;
    assert!(
        compute_inter_reviewer_agreement(&reviewer_a, &reviewer_b, &protocol.alignment_policy)
            .is_err()
    );
    reviewer_a.blind_to_frozen_judge = true;
    reviewer_a.completed = false;
    assert!(
        compute_inter_reviewer_agreement(&reviewer_a, &reviewer_b, &protocol.alignment_policy)
            .is_err()
    );
}

#[test]
fn frozen_input_validation_rejects_a_mismatched_source_excerpt() {
    let packet = build_phase7_blind_review_packet().expect("blind packet");
    let case = packet.cases.first().expect("design case");
    let anchor = case
        .claim_source_anchors
        .iter()
        .find(|anchor| !anchor.source_text.is_empty())
        .expect("non-empty anchor");
    let end_char = 1;
    let mut annotation = claim(
        "reviewer-a-claim-1",
        &anchor.case_id,
        &anchor.anchor_id,
        0,
        end_char,
        HumanSupportLabel::Supported,
    );
    annotation.response_sha256 = anchor.response_sha256.clone();
    annotation.source_span.source_excerpt = "not-the-frozen-source".to_string();

    let reviewer = ReviewerAnnotationSubmission {
        schema_version: 1,
        submission_id: "reviewer-a-real-submission".to_string(),
        reviewer_id: "reviewer-a".to_string(),
        reviewer_role: "independent_semantic_reviewer".to_string(),
        source_execution_id: packet.source_execution_id,
        protocol_id: packet.protocol_id,
        completed: true,
        blind_to_other_reviewer: true,
        blind_to_frozen_judge: true,
        blind_to_phase7_3_aggregates: true,
        held_out_accessed: false,
        claims: vec![annotation],
    };

    let error = validate_phase7_reviewer_submission_against_frozen_inputs(&reviewer)
        .expect_err("mismatched excerpt must fail");
    assert!(error
        .to_string()
        .contains("reviewer_claim_source_excerpt_mismatch"));
}

#[test]
fn checked_in_agreement_report_requires_adjudication() {
    let report: serde_json::Value = serde_json::from_str(include_str!(
        "../reports/phase7_inter_reviewer_agreement.json"
    ))
    .expect("checked report");
    assert_eq!(
        report["decision"],
        "agreement_report_ready_adjudication_required"
    );
    assert_eq!(
        report["metrics"]["segmentation"]["reviewer_a_claim_count"],
        74
    );
    assert_eq!(
        report["metrics"]["segmentation"]["reviewer_b_claim_count"],
        77
    );
    assert_eq!(report["guards"]["adjudicated_labels_used"], false);
    assert_eq!(report["guards"]["frozen_judge_visible"], false);
    assert_eq!(report["guards"]["held_out_cases_untouched"], true);
}
