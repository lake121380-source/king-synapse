use crate::phase7_independent_adjudication_calibration::{
    compute_support_agreement, load_phase7_adjudication_measurement_protocol,
    load_phase7_reviewer_a_template, load_phase7_reviewer_b_template,
    validate_phase7_reviewer_submission_against_frozen_inputs, AtomicClaimAnnotation,
    HumanSupportLabel, ReviewerAnnotationSubmission, SupportAgreementMetrics,
};
use anyhow::{bail, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

const PROTOCOL_JSON: &str = include_str!(
    "../datasets/pattern_extraction/phase7_3_1_inter_reviewer_agreement_protocol.json"
);
const EVALUATION_VERSION: &str = "phase7.3.1-inter-reviewer-agreement-gate-v1";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ClaimAlignmentPolicy {
    pub grouping_keys: Vec<String>,
    pub pair_score: String,
    pub matching: String,
    pub minimum_iou: f64,
    pub exact_boundary_requires_identical_start_and_end: bool,
    pub claim_text_similarity_used: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct InterReviewerAgreementProtocol {
    pub schema_version: u32,
    pub protocol_id: String,
    pub parent_protocol_id: String,
    pub phase: String,
    pub purpose: String,
    pub measurement_order: Vec<String>,
    pub source_span_unit: String,
    pub alignment_policy: ClaimAlignmentPolicy,
    pub segmentation_metrics: Vec<String>,
    pub claim_count_metrics: Vec<String>,
    pub semantic_metrics: Vec<String>,
    pub agreement_input: String,
    pub adjudicated_labels_allowed: bool,
    pub frozen_judge_visible: bool,
    pub phase7_3_seed_visible: bool,
    pub held_out_accessed: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ClaimAlignment {
    pub reviewer_a_claim_id: String,
    pub reviewer_b_claim_id: String,
    pub case_id: String,
    pub anchor_id: String,
    pub span_iou: f64,
    pub exact_boundary_match: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SegmentationAgreementMetrics {
    pub reviewer_a_claim_count: usize,
    pub reviewer_b_claim_count: usize,
    pub absolute_claim_count_difference: usize,
    pub aligned_claim_pair_count: usize,
    pub exact_boundary_match_count: usize,
    pub exact_boundary_agreement_rate: Option<f64>,
    pub matched_span_mean_iou: Option<f64>,
    pub overlap_alignment_rate: Option<f64>,
    pub unmatched_reviewer_a_claim_count: usize,
    pub unmatched_reviewer_b_claim_count: usize,
    pub unmatched_claim_rate: Option<f64>,
    pub split_disagreement_count: usize,
    pub merge_disagreement_count: usize,
    pub per_case_claim_count_pearson_correlation: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SemanticAgreementMetrics {
    pub support: SupportAgreementMetrics,
    pub support_krippendorff_alpha_ordinal: Option<f64>,
    pub provenance_agreement: Option<f64>,
    pub scope_agreement: Option<f64>,
    pub causal_strength_agreement: Option<f64>,
    pub prediction_support_agreement: Option<f64>,
    pub counterexample_handling_agreement: Option<f64>,
    pub falsifiability_agreement: Option<f64>,
    pub confidence_agreement: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct InterReviewerAgreementMetrics {
    pub alignments: Vec<ClaimAlignment>,
    pub segmentation: SegmentationAgreementMetrics,
    pub semantic: SemanticAgreementMetrics,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct InterReviewerAgreementGuards {
    pub raw_blind_submissions_only: bool,
    pub adjudicated_labels_used: bool,
    pub frozen_judge_visible: bool,
    pub phase7_3_seed_visible: bool,
    pub held_out_cases_untouched: bool,
    pub reviewer_a_completed: bool,
    pub reviewer_b_completed: bool,
    pub agreement_report_completed: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum InterReviewerAgreementDecision {
    WaitingForTwoIndependentSubmissions,
    AgreementReportReadyAdjudicationRequired,
    AgreementProtocolInvalid,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct InterReviewerAgreementReport {
    pub schema_version: u32,
    pub evaluation_version: String,
    pub tag: String,
    pub generated_at: String,
    pub phase: String,
    pub protocol: InterReviewerAgreementProtocol,
    pub metrics: Option<InterReviewerAgreementMetrics>,
    pub guards: InterReviewerAgreementGuards,
    pub decision: InterReviewerAgreementDecision,
    pub conclusion: String,
}

pub struct Phase7InterReviewerAgreementEvaluator;

impl Phase7InterReviewerAgreementEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<InterReviewerAgreementReport> {
        evaluate(tag.into())
    }
}

pub fn load_phase7_inter_reviewer_agreement_protocol() -> Result<InterReviewerAgreementProtocol> {
    serde_json::from_str(PROTOCOL_JSON).context("parse Phase 7.3.1 agreement protocol")
}

fn evaluate(tag: String) -> Result<InterReviewerAgreementReport> {
    let protocol = load_phase7_inter_reviewer_agreement_protocol()?;
    let reviewer_a = load_phase7_reviewer_a_template()?;
    let reviewer_b = load_phase7_reviewer_b_template()?;
    validate_protocol(&protocol)?;
    let parent_protocol = load_phase7_adjudication_measurement_protocol()?;
    if protocol.parent_protocol_id != parent_protocol.protocol_id {
        bail!("phase7_3_1_agreement_parent_protocol_mismatch");
    }
    validate_phase7_reviewer_submission_against_frozen_inputs(&reviewer_a)?;
    validate_phase7_reviewer_submission_against_frozen_inputs(&reviewer_b)?;

    let both_completed = reviewer_a.completed && reviewer_b.completed;
    let metrics = if both_completed {
        Some(compute_inter_reviewer_agreement(
            &reviewer_a,
            &reviewer_b,
            &protocol.alignment_policy,
        )?)
    } else {
        None
    };
    let guards = InterReviewerAgreementGuards {
        raw_blind_submissions_only: true,
        adjudicated_labels_used: false,
        frozen_judge_visible: false,
        phase7_3_seed_visible: false,
        held_out_cases_untouched: !reviewer_a.held_out_accessed && !reviewer_b.held_out_accessed,
        reviewer_a_completed: reviewer_a.completed,
        reviewer_b_completed: reviewer_b.completed,
        agreement_report_completed: metrics.is_some(),
        runtime_authorized: false,
        hermes_authorized: false,
    };
    let decision = if both_completed {
        InterReviewerAgreementDecision::AgreementReportReadyAdjudicationRequired
    } else {
        InterReviewerAgreementDecision::WaitingForTwoIndependentSubmissions
    };

    Ok(InterReviewerAgreementReport {
        schema_version: 1,
        evaluation_version: EVALUATION_VERSION.to_string(),
        tag,
        generated_at: Utc::now().to_rfc3339(),
        phase: protocol.phase.clone(),
        protocol,
        metrics,
        guards,
        decision,
        conclusion: if both_completed {
            "Agreement is measured only from the two raw blind submissions. Preserve the report and all disagreements before adjudication; frozen-Judge calibration remains blocked.".to_string()
        } else {
            "The Agreement Gate is frozen, but no agreement statistic is emitted until two genuinely independent completed submissions exist.".to_string()
        },
    })
}

fn validate_protocol(protocol: &InterReviewerAgreementProtocol) -> Result<()> {
    let expected_grouping_keys = vec!["case_id".to_string(), "anchor_id".to_string()];
    if protocol.schema_version != 1
        || protocol.source_span_unit != "unicode_scalar_index_half_open"
        || protocol.alignment_policy.grouping_keys != expected_grouping_keys
        || protocol.alignment_policy.pair_score != "character_span_intersection_over_union"
        || protocol.alignment_policy.matching
            != "deterministic_greedy_descending_iou_then_claim_ids"
        || protocol.alignment_policy.minimum_iou <= 0.0
        || protocol.alignment_policy.minimum_iou > 1.0
        || !protocol
            .alignment_policy
            .exact_boundary_requires_identical_start_and_end
        || protocol.alignment_policy.claim_text_similarity_used
        || protocol.adjudicated_labels_allowed
        || protocol.frozen_judge_visible
        || protocol.phase7_3_seed_visible
        || protocol.held_out_accessed
        || protocol.runtime_authorized
        || protocol.hermes_authorized
    {
        bail!("phase7_3_1_agreement_protocol_boundary_invalid");
    }
    Ok(())
}

pub fn compute_inter_reviewer_agreement(
    reviewer_a: &ReviewerAnnotationSubmission,
    reviewer_b: &ReviewerAnnotationSubmission,
    policy: &ClaimAlignmentPolicy,
) -> Result<InterReviewerAgreementMetrics> {
    if policy.grouping_keys != ["case_id", "anchor_id"]
        || policy.pair_score != "character_span_intersection_over_union"
        || policy.matching != "deterministic_greedy_descending_iou_then_claim_ids"
        || policy.minimum_iou <= 0.0
        || policy.minimum_iou > 1.0
        || !policy.exact_boundary_requires_identical_start_and_end
        || policy.claim_text_similarity_used
    {
        bail!("agreement_requires_frozen_alignment_policy");
    }
    if !reviewer_a.completed || !reviewer_b.completed {
        bail!("agreement_requires_two_completed_submissions");
    }
    if !reviewer_a.blind_to_other_reviewer
        || !reviewer_b.blind_to_other_reviewer
        || !reviewer_a.blind_to_frozen_judge
        || !reviewer_b.blind_to_frozen_judge
        || !reviewer_a.blind_to_phase7_3_aggregates
        || !reviewer_b.blind_to_phase7_3_aggregates
        || reviewer_a.held_out_accessed
        || reviewer_b.held_out_accessed
    {
        bail!("agreement_requires_blind_design_only_submissions");
    }

    let alignments = align_claims(&reviewer_a.claims, &reviewer_b.claims, policy.minimum_iou);
    let a_by_id = reviewer_a
        .claims
        .iter()
        .map(|claim| (claim.claim_id.as_str(), claim))
        .collect::<BTreeMap<_, _>>();
    let b_by_id = reviewer_b
        .claims
        .iter()
        .map(|claim| (claim.claim_id.as_str(), claim))
        .collect::<BTreeMap<_, _>>();
    let aligned_pairs = alignments
        .iter()
        .map(|alignment| {
            (
                *a_by_id
                    .get(alignment.reviewer_a_claim_id.as_str())
                    .expect("aligned A claim"),
                *b_by_id
                    .get(alignment.reviewer_b_claim_id.as_str())
                    .expect("aligned B claim"),
            )
        })
        .collect::<Vec<_>>();

    let support_labels = aligned_pairs
        .iter()
        .map(|(a, b)| (a.human_support_label, b.human_support_label))
        .collect::<Vec<_>>();
    let support = compute_support_agreement(&support_labels);
    let semantic = SemanticAgreementMetrics {
        support_krippendorff_alpha_ordinal: krippendorff_alpha_ordinal(&support_labels),
        provenance_agreement: exact_agreement(&aligned_pairs, |claim| claim.claim_origin),
        scope_agreement: exact_agreement(&aligned_pairs, |claim| claim.dimension_labels.scope),
        causal_strength_agreement: exact_agreement(&aligned_pairs, |claim| {
            claim.dimension_labels.causal_strength
        }),
        prediction_support_agreement: exact_agreement(&aligned_pairs, |claim| {
            claim.dimension_labels.prediction_support
        }),
        counterexample_handling_agreement: exact_agreement(&aligned_pairs, |claim| {
            claim.dimension_labels.counterexample_handling
        }),
        falsifiability_agreement: exact_agreement(&aligned_pairs, |claim| {
            claim.dimension_labels.falsifiability
        }),
        confidence_agreement: exact_agreement(&aligned_pairs, |claim| claim.annotation_confidence),
        support,
    };

    Ok(InterReviewerAgreementMetrics {
        segmentation: segmentation_metrics(&reviewer_a.claims, &reviewer_b.claims, &alignments),
        alignments,
        semantic,
    })
}

fn align_claims(
    reviewer_a: &[AtomicClaimAnnotation],
    reviewer_b: &[AtomicClaimAnnotation],
    minimum_iou: f64,
) -> Vec<ClaimAlignment> {
    let mut candidates = Vec::new();
    for a in reviewer_a {
        for b in reviewer_b {
            if a.case_id != b.case_id || a.anchor_id != b.anchor_id {
                continue;
            }
            let iou = span_iou(a, b);
            if iou >= minimum_iou {
                candidates.push((iou, a, b));
            }
        }
    }
    candidates.sort_by(|left, right| {
        right
            .0
            .total_cmp(&left.0)
            .then_with(|| left.1.claim_id.cmp(&right.1.claim_id))
            .then_with(|| left.2.claim_id.cmp(&right.2.claim_id))
    });

    let mut used_a = BTreeSet::new();
    let mut used_b = BTreeSet::new();
    let mut alignments = Vec::new();
    for (iou, a, b) in candidates {
        if used_a.contains(&a.claim_id) || used_b.contains(&b.claim_id) {
            continue;
        }
        used_a.insert(a.claim_id.clone());
        used_b.insert(b.claim_id.clone());
        alignments.push(ClaimAlignment {
            reviewer_a_claim_id: a.claim_id.clone(),
            reviewer_b_claim_id: b.claim_id.clone(),
            case_id: a.case_id.clone(),
            anchor_id: a.anchor_id.clone(),
            span_iou: iou,
            exact_boundary_match: a.source_span.start_char == b.source_span.start_char
                && a.source_span.end_char == b.source_span.end_char,
        });
    }
    alignments.sort_by(|a, b| {
        a.case_id
            .cmp(&b.case_id)
            .then_with(|| a.anchor_id.cmp(&b.anchor_id))
            .then_with(|| a.reviewer_a_claim_id.cmp(&b.reviewer_a_claim_id))
    });
    alignments
}

fn span_iou(a: &AtomicClaimAnnotation, b: &AtomicClaimAnnotation) -> f64 {
    let intersection_start = a.source_span.start_char.max(b.source_span.start_char);
    let intersection_end = a.source_span.end_char.min(b.source_span.end_char);
    let intersection = intersection_end.saturating_sub(intersection_start);
    let union_start = a.source_span.start_char.min(b.source_span.start_char);
    let union_end = a.source_span.end_char.max(b.source_span.end_char);
    let union = union_end.saturating_sub(union_start);
    if union == 0 {
        0.0
    } else {
        intersection as f64 / union as f64
    }
}

fn segmentation_metrics(
    reviewer_a: &[AtomicClaimAnnotation],
    reviewer_b: &[AtomicClaimAnnotation],
    alignments: &[ClaimAlignment],
) -> SegmentationAgreementMetrics {
    let aligned_a = alignments
        .iter()
        .map(|alignment| alignment.reviewer_a_claim_id.as_str())
        .collect::<BTreeSet<_>>();
    let aligned_b = alignments
        .iter()
        .map(|alignment| alignment.reviewer_b_claim_id.as_str())
        .collect::<BTreeSet<_>>();
    let exact = alignments
        .iter()
        .filter(|alignment| alignment.exact_boundary_match)
        .count();
    let denominator = reviewer_a.len().max(reviewer_b.len());
    let total_claims = reviewer_a.len() + reviewer_b.len();
    let unmatched_a = reviewer_a.len().saturating_sub(aligned_a.len());
    let unmatched_b = reviewer_b.len().saturating_sub(aligned_b.len());
    let split_disagreement_count = reviewer_a
        .iter()
        .filter(|a| {
            reviewer_b
                .iter()
                .filter(|b| same_anchor_overlap(a, b))
                .count()
                > 1
        })
        .count();
    let merge_disagreement_count = reviewer_b
        .iter()
        .filter(|b| {
            reviewer_a
                .iter()
                .filter(|a| same_anchor_overlap(a, b))
                .count()
                > 1
        })
        .count();

    SegmentationAgreementMetrics {
        reviewer_a_claim_count: reviewer_a.len(),
        reviewer_b_claim_count: reviewer_b.len(),
        absolute_claim_count_difference: reviewer_a.len().abs_diff(reviewer_b.len()),
        aligned_claim_pair_count: alignments.len(),
        exact_boundary_match_count: exact,
        exact_boundary_agreement_rate: ratio(exact, denominator),
        matched_span_mean_iou: mean(alignments.iter().map(|alignment| alignment.span_iou)),
        overlap_alignment_rate: ratio(alignments.len() * 2, total_claims),
        unmatched_reviewer_a_claim_count: unmatched_a,
        unmatched_reviewer_b_claim_count: unmatched_b,
        unmatched_claim_rate: ratio(unmatched_a + unmatched_b, total_claims),
        split_disagreement_count,
        merge_disagreement_count,
        per_case_claim_count_pearson_correlation: claim_count_correlation(reviewer_a, reviewer_b),
    }
}

fn same_anchor_overlap(a: &AtomicClaimAnnotation, b: &AtomicClaimAnnotation) -> bool {
    a.case_id == b.case_id && a.anchor_id == b.anchor_id && span_iou(a, b) > 0.0
}

fn claim_count_correlation(
    reviewer_a: &[AtomicClaimAnnotation],
    reviewer_b: &[AtomicClaimAnnotation],
) -> Option<f64> {
    let cases = reviewer_a
        .iter()
        .chain(reviewer_b.iter())
        .map(|claim| claim.case_id.as_str())
        .collect::<BTreeSet<_>>();
    if cases.len() < 2 {
        return None;
    }
    let pairs = cases
        .iter()
        .map(|case_id| {
            (
                reviewer_a
                    .iter()
                    .filter(|claim| claim.case_id == *case_id)
                    .count() as f64,
                reviewer_b
                    .iter()
                    .filter(|claim| claim.case_id == *case_id)
                    .count() as f64,
            )
        })
        .collect::<Vec<_>>();
    pearson(&pairs)
}

fn pearson(pairs: &[(f64, f64)]) -> Option<f64> {
    if pairs.len() < 2 {
        return None;
    }
    let mean_a = pairs.iter().map(|pair| pair.0).sum::<f64>() / pairs.len() as f64;
    let mean_b = pairs.iter().map(|pair| pair.1).sum::<f64>() / pairs.len() as f64;
    let covariance = pairs
        .iter()
        .map(|pair| (pair.0 - mean_a) * (pair.1 - mean_b))
        .sum::<f64>();
    let variance_a = pairs
        .iter()
        .map(|pair| (pair.0 - mean_a).powi(2))
        .sum::<f64>();
    let variance_b = pairs
        .iter()
        .map(|pair| (pair.1 - mean_b).powi(2))
        .sum::<f64>();
    let denominator = (variance_a * variance_b).sqrt();
    if denominator == 0.0 {
        None
    } else {
        Some(covariance / denominator)
    }
}

fn exact_agreement<T: Copy + Eq>(
    pairs: &[(&AtomicClaimAnnotation, &AtomicClaimAnnotation)],
    select: impl Fn(&AtomicClaimAnnotation) -> T,
) -> Option<f64> {
    ratio(
        pairs.iter().filter(|(a, b)| select(a) == select(b)).count(),
        pairs.len(),
    )
}

fn krippendorff_alpha_ordinal(labels: &[(HumanSupportLabel, HumanSupportLabel)]) -> Option<f64> {
    let usable = labels
        .iter()
        .filter_map(|(a, b)| Some((support_rank(*a)?, support_rank(*b)?)))
        .collect::<Vec<_>>();
    if usable.len() < 2 {
        return None;
    }
    let observed = usable
        .iter()
        .map(|(a, b)| (*a as f64 - *b as f64).powi(2))
        .sum::<f64>()
        / usable.len() as f64;
    let mut counts = [0usize; 3];
    for (a, b) in &usable {
        counts[*a] += 1;
        counts[*b] += 1;
    }
    let total = usable.len() * 2;
    let mut expected = 0.0;
    for i in 0..3 {
        for j in 0..3 {
            if i == j {
                continue;
            }
            expected += (counts[i] * counts[j]) as f64 * (i as f64 - j as f64).powi(2)
                / (total * (total - 1)) as f64;
        }
    }
    if expected == 0.0 {
        None
    } else {
        Some(1.0 - observed / expected)
    }
}

fn support_rank(label: HumanSupportLabel) -> Option<usize> {
    match label {
        HumanSupportLabel::Supported => Some(0),
        HumanSupportLabel::PartiallySupported => Some(1),
        HumanSupportLabel::Unsupported => Some(2),
        HumanSupportLabel::NotAssessable => None,
    }
}

fn ratio(numerator: usize, denominator: usize) -> Option<f64> {
    if denominator == 0 {
        None
    } else {
        Some(numerator as f64 / denominator as f64)
    }
}

fn mean(values: impl Iterator<Item = f64>) -> Option<f64> {
    let values = values.collect::<Vec<_>>();
    if values.is_empty() {
        None
    } else {
        Some(values.iter().sum::<f64>() / values.len() as f64)
    }
}
