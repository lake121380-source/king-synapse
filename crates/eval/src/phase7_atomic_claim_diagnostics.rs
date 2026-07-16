use crate::phase7_atomic_claim_measurement::{
    aggregate_candidate_label, AtomicClaimType, AtomicControlCase, AtomicControlClaim,
    AtomicControlDataset, ClaimCentrality, SourceSpan,
};
use crate::phase7_independent_adjudication_calibration::HumanSupportLabel;
use anyhow::{bail, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

const DIAGNOSTICS_MANIFEST_BYTES: &[u8] =
    include_bytes!("../config/phase7_3_3_a_diagnostics_manifest_v1.json");
const CONTROL_BYTES: &[u8] =
    include_bytes!("../datasets/pattern_extraction/phase7_3_3_atomic_claim_controls.json");
const PARTIAL_SUPPLEMENT_BYTES: &[u8] = include_bytes!(
    "../datasets/pattern_extraction/phase7_3_3_a_partial_atomic_claim_supplement_v1.json"
);
const PARTIAL_SUPPLEMENT_MANIFEST_BYTES: &[u8] =
    include_bytes!("../config/phase7_3_3_a_partial_atomic_claim_supplement_manifest_v1.json");
const ATOMIC_PROTOCOL_BYTES: &[u8] = include_bytes!(
    "../datasets/pattern_extraction/phase7_3_3_atomic_claim_measurement_protocol.json"
);
const ATOMIC_PROMPT_BYTES: &[u8] =
    include_bytes!("../config/phase7_3_3_atomic_claim_judge_prompt_v1.md");
const EVALUATION_VERSION: &str = "phase7.3.3-a-diagnostics-v2";

#[derive(Clone, Debug, Deserialize)]
struct DiagnosticsManifest {
    manifest_id: String,
    changes_gate_decision: bool,
}

#[derive(Clone, Debug, Deserialize)]
struct PartialSupplementManifest {
    manifest_id: String,
    supplement_dataset_id: String,
    changes_gate_decision: bool,
    candidate_collapse_gate_uses_original_balanced_controls_only: bool,
    supplement_may_change_candidate_readiness_metrics: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AtomicClaimPrediction {
    pub claim_id: String,
    pub source_span: SourceSpan,
    pub support_label: HumanSupportLabel,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AtomicControlPrediction {
    pub control_id: String,
    pub claims: Vec<AtomicClaimPrediction>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct LabelDiagnosticSummary {
    pub item_count: usize,
    pub exact_match_count: usize,
    pub exact_accuracy: Option<f64>,
    pub observed_gold_labels: Vec<String>,
    pub absent_gold_labels: Vec<String>,
    pub macro_recall_over_observed_gold_labels: Option<f64>,
    pub confusion: BTreeMap<String, BTreeMap<String, usize>>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ClaimTypeDiagnostic {
    pub claim_type: AtomicClaimType,
    pub support_classification: LabelDiagnosticSummary,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct CentralityDiagnostics {
    pub central_claims: LabelDiagnosticSummary,
    pub non_central_material_claims: LabelDiagnosticSummary,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum CandidateErrorAttribution {
    Correct,
    MaskedClaimError,
    ClaimClassificationError,
    AggregationRuleError,
    MixedError,
    SegmentationFailure,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CandidateAttributionRow {
    pub control_id: String,
    pub expected_candidate_label: HumanSupportLabel,
    pub predicted_candidate_label: Option<HumanSupportLabel>,
    pub gold_claim_aggregation: Option<HumanSupportLabel>,
    pub all_claim_labels_correct: bool,
    pub attribution: CandidateErrorAttribution,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct AggregationAttributionDiagnostics {
    pub candidate_classification: LabelDiagnosticSummary,
    pub attribution_counts: BTreeMap<String, usize>,
    pub rows: Vec<CandidateAttributionRow>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct AtomicDiagnosticsResult {
    pub probe_id: String,
    pub segmentation_exact_span_precision: Option<f64>,
    pub segmentation_exact_span_recall: Option<f64>,
    pub overall_claim_support: LabelDiagnosticSummary,
    pub support_confusion_by_claim_type: Vec<ClaimTypeDiagnostic>,
    pub centrality_split: CentralityDiagnostics,
    pub aggregation_error_attribution: AggregationAttributionDiagnostics,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DiagnosticsArtifactHashes {
    pub diagnostics_manifest_sha256: String,
    pub partial_supplement_manifest_sha256: String,
    pub partial_supplement_dataset_sha256: String,
    pub frozen_atomic_protocol_sha256: String,
    pub frozen_atomic_prompt_sha256: String,
    pub frozen_balanced_controls_sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DiagnosticsReadinessGuards {
    pub atomic_protocol_modified: bool,
    pub atomic_prompt_modified: bool,
    pub balanced_controls_modified: bool,
    pub aggregation_policy_modified: bool,
    pub readiness_thresholds_modified: bool,
    pub diagnostic_supplement_changes_candidate_gate: bool,
    pub model_execution_completed: bool,
    pub held_out_accessed: bool,
    pub runtime_authorized: bool,
    pub memory_write_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7AtomicClaimDiagnosticsReadinessReport {
    pub schema_version: u32,
    pub report_id: String,
    pub phase: String,
    pub evaluation_version: String,
    pub generated_at: String,
    pub status: String,
    pub manifest_id: String,
    pub diagnostics_change_gate_decision: bool,
    pub partial_supplement_manifest_id: String,
    pub partial_supplement_dataset_id: String,
    pub partial_supplement_change_gate_decision: bool,
    pub candidate_collapse_gate_uses_original_balanced_controls_only: bool,
    pub original_gold_atomic_claim_label_counts: BTreeMap<String, usize>,
    pub supplement_gold_atomic_claim_label_counts: BTreeMap<String, usize>,
    pub combined_gold_atomic_claim_label_counts: BTreeMap<String, usize>,
    pub missing_gold_atomic_claim_labels: Vec<String>,
    pub four_label_local_claim_calibration_available: bool,
    pub perfect_probe: AtomicDiagnosticsResult,
    pub always_partial_probe: AtomicDiagnosticsResult,
    pub supplement_perfect_probe: AtomicDiagnosticsResult,
    pub real_model_diagnostics: Option<AtomicDiagnosticsResult>,
    pub real_model_supplement_diagnostics: Option<AtomicDiagnosticsResult>,
    pub decision: String,
    pub proof_gap: String,
    pub next_gate: Vec<String>,
    pub artifact_hashes: DiagnosticsArtifactHashes,
    pub guards: DiagnosticsReadinessGuards,
}

pub struct Phase7AtomicClaimDiagnosticsEvaluator;

impl Phase7AtomicClaimDiagnosticsEvaluator {
    pub fn evaluate(
        report_id: impl Into<String>,
    ) -> Result<Phase7AtomicClaimDiagnosticsReadinessReport> {
        let manifest: DiagnosticsManifest = serde_json::from_slice(DIAGNOSTICS_MANIFEST_BYTES)
            .context("parse Phase 7.3.3-A diagnostics manifest")?;
        let supplement_manifest: PartialSupplementManifest =
            serde_json::from_slice(PARTIAL_SUPPLEMENT_MANIFEST_BYTES)
                .context("parse Phase 7.3.3-A partial Claim supplement manifest")?;
        let controls: AtomicControlDataset =
            serde_json::from_slice(CONTROL_BYTES).context("parse frozen atomic controls")?;
        let supplement: AtomicControlDataset = serde_json::from_slice(PARTIAL_SUPPLEMENT_BYTES)
            .context("parse diagnostics-only partial Claim supplement")?;
        validate_partial_supplement(&supplement, &supplement_manifest)?;
        let perfect_predictions = synthetic_predictions(&controls, None);
        let collapsed_predictions =
            synthetic_predictions(&controls, Some(HumanSupportLabel::PartiallySupported));
        let perfect_probe = analyze_predictions("perfect_oracle", &controls, &perfect_predictions)?;
        let always_partial_probe = analyze_predictions(
            "always_partially_supported",
            &controls,
            &collapsed_predictions,
        )?;
        let supplement_perfect_predictions = synthetic_predictions(&supplement, None);
        let supplement_perfect_probe = analyze_predictions(
            "partial_claim_supplement_perfect_oracle",
            &supplement,
            &supplement_perfect_predictions,
        )?;

        let original_gold_atomic_claim_label_counts = claim_label_counts(&controls);
        let supplement_gold_atomic_claim_label_counts = claim_label_counts(&supplement);
        let combined_gold_atomic_claim_label_counts = merge_label_counts(
            &original_gold_atomic_claim_label_counts,
            &supplement_gold_atomic_claim_label_counts,
        );
        let missing_gold_atomic_claim_labels = all_labels()
            .into_iter()
            .filter(|label| {
                !combined_gold_atomic_claim_label_counts.contains_key(label_name(*label))
            })
            .map(|label| label_name(label).to_string())
            .collect::<Vec<_>>();
        let four_label_local_claim_calibration_available =
            missing_gold_atomic_claim_labels.is_empty();

        Ok(Phase7AtomicClaimDiagnosticsReadinessReport {
            schema_version: 1,
            report_id: report_id.into(),
            phase: "Phase 7.3.3-A Balanced Control Diagnostics Readiness".to_string(),
            evaluation_version: EVALUATION_VERSION.to_string(),
            generated_at: Utc::now().to_rfc3339(),
            status: "diagnostics_ready_four_label_controls_frozen_model_execution_pending".to_string(),
            manifest_id: manifest.manifest_id,
            diagnostics_change_gate_decision: manifest.changes_gate_decision,
            partial_supplement_manifest_id: supplement_manifest.manifest_id,
            partial_supplement_dataset_id: supplement.dataset_id.clone(),
            partial_supplement_change_gate_decision: supplement_manifest.changes_gate_decision,
            candidate_collapse_gate_uses_original_balanced_controls_only: supplement_manifest
                .candidate_collapse_gate_uses_original_balanced_controls_only,
            original_gold_atomic_claim_label_counts,
            supplement_gold_atomic_claim_label_counts,
            combined_gold_atomic_claim_label_counts,
            missing_gold_atomic_claim_labels,
            four_label_local_claim_calibration_available,
            perfect_probe,
            always_partial_probe,
            supplement_perfect_probe,
            real_model_diagnostics: None,
            real_model_supplement_diagnostics: None,
            decision: "diagnostics_ready_four_label_local_claim_controls_frozen".to_string(),
            proof_gap: "Resolved by a separately versioned diagnostics-only supplement: the original 16 balanced Candidate controls remain unchanged and continue to own Candidate collapse readiness, while four supplemental local Claims provide the previously absent partially_supported gold label. Real-model capability remains untested.".to_string(),
            next_gate: vec![
                "Do not modify the already frozen Phase 7.3.3 protocol, prompt, original controls, supplement, or aggregator after real-model execution starts.".to_string(),
                "Run the real Atomic Judge on the original balanced controls and the diagnostics-only supplement; use the supplement only for local Claim calibration, never for Candidate collapse readiness.".to_string(),
                "Emit Claim-Type-conditioned support confusion, central versus non-central metrics, and Candidate error attribution without changing readiness thresholds.".to_string(),
                "Keep the real ten design Candidates and held-out cases closed until the control-execution declaration is finalized.".to_string(),
            ],
            artifact_hashes: DiagnosticsArtifactHashes {
                diagnostics_manifest_sha256: sha256(DIAGNOSTICS_MANIFEST_BYTES),
                partial_supplement_manifest_sha256: sha256(PARTIAL_SUPPLEMENT_MANIFEST_BYTES),
                partial_supplement_dataset_sha256: sha256(PARTIAL_SUPPLEMENT_BYTES),
                frozen_atomic_protocol_sha256: sha256(ATOMIC_PROTOCOL_BYTES),
                frozen_atomic_prompt_sha256: sha256(ATOMIC_PROMPT_BYTES),
                frozen_balanced_controls_sha256: sha256(CONTROL_BYTES),
            },
            guards: DiagnosticsReadinessGuards {
                atomic_protocol_modified: false,
                atomic_prompt_modified: false,
                balanced_controls_modified: false,
                aggregation_policy_modified: false,
                readiness_thresholds_modified: false,
                diagnostic_supplement_changes_candidate_gate: supplement_manifest
                    .supplement_may_change_candidate_readiness_metrics,
                model_execution_completed: false,
                held_out_accessed: false,
                runtime_authorized: false,
                memory_write_authorized: false,
            },
        })
    }
}

fn validate_partial_supplement(
    supplement: &AtomicControlDataset,
    manifest: &PartialSupplementManifest,
) -> Result<()> {
    if supplement.dataset_id != manifest.supplement_dataset_id {
        bail!("partial Claim supplement dataset id does not match manifest");
    }
    if supplement.control_cases.is_empty() {
        bail!("partial Claim supplement must contain at least one control");
    }
    let mut control_ids = BTreeSet::new();
    let mut claim_ids = BTreeSet::new();
    for case in &supplement.control_cases {
        if !control_ids.insert(case.control_id.as_str()) {
            bail!("duplicate supplement control id {}", case.control_id);
        }
        if case.expected_candidate_label != HumanSupportLabel::PartiallySupported {
            bail!("supplement Candidate must be partially_supported");
        }
        if case
            .claims
            .iter()
            .filter(|claim| claim.centrality == ClaimCentrality::Central)
            .count()
            != 1
        {
            bail!("supplement control must contain exactly one central Claim");
        }
        let evidence_ids = case
            .evidence
            .iter()
            .map(|row| row.evidence_id.as_str())
            .collect::<BTreeSet<_>>();
        for claim in &case.claims {
            if !claim_ids.insert(claim.claim_id.as_str()) {
                bail!("duplicate supplement Claim id {}", claim.claim_id);
            }
            if claim.expected_support_label != HumanSupportLabel::PartiallySupported {
                bail!("every supplement Claim must be partially_supported");
            }
            let span = &claim.source_span;
            if span.start > span.end
                || span.end > case.candidate_text.len()
                || !case.candidate_text.is_char_boundary(span.start)
                || !case.candidate_text.is_char_boundary(span.end)
                || case.candidate_text[span.start..span.end] != claim.claim_text
            {
                bail!(
                    "invalid exact source span for supplement Claim {}",
                    claim.claim_id
                );
            }
            if claim.evidence_ids.is_empty()
                || !claim
                    .evidence_ids
                    .iter()
                    .all(|id| evidence_ids.contains(id.as_str()))
            {
                bail!(
                    "invalid evidence reference for supplement Claim {}",
                    claim.claim_id
                );
            }
        }
        if aggregate_candidate_label(&case.claims)? != case.expected_candidate_label {
            bail!("supplement gold Claims do not aggregate to expected Candidate label");
        }
    }
    Ok(())
}

fn merge_label_counts(
    left: &BTreeMap<String, usize>,
    right: &BTreeMap<String, usize>,
) -> BTreeMap<String, usize> {
    let mut merged = left.clone();
    for (label, count) in right {
        *merged.entry(label.clone()).or_default() += count;
    }
    merged
}

pub fn analyze_predictions(
    probe_id: impl Into<String>,
    controls: &AtomicControlDataset,
    predictions: &[AtomicControlPrediction],
) -> Result<AtomicDiagnosticsResult> {
    let prediction_by_case = predictions
        .iter()
        .map(|prediction| (prediction.control_id.as_str(), prediction))
        .collect::<BTreeMap<_, _>>();
    if prediction_by_case.len() != predictions.len() {
        bail!("duplicate control prediction id");
    }

    let mut all_pairs = Vec::<(HumanSupportLabel, HumanSupportLabel)>::new();
    let mut central_pairs = Vec::<(HumanSupportLabel, HumanSupportLabel)>::new();
    let mut non_central_pairs = Vec::<(HumanSupportLabel, HumanSupportLabel)>::new();
    let mut type_pairs =
        BTreeMap::<AtomicClaimType, Vec<(HumanSupportLabel, HumanSupportLabel)>>::new();
    let mut candidate_pairs = Vec::<(HumanSupportLabel, HumanSupportLabel)>::new();
    let mut rows = Vec::new();
    let mut attribution_counts = BTreeMap::<String, usize>::new();
    let mut predicted_span_count = 0usize;
    let mut matched_span_count = 0usize;
    let gold_span_count = controls
        .control_cases
        .iter()
        .map(|case| case.claims.len())
        .sum::<usize>();

    for case in &controls.control_cases {
        let Some(prediction) = prediction_by_case.get(case.control_id.as_str()) else {
            push_attribution(
                &mut rows,
                &mut attribution_counts,
                case,
                None,
                None,
                false,
                CandidateErrorAttribution::SegmentationFailure,
            );
            continue;
        };
        predicted_span_count += prediction.claims.len();
        let predicted_ids = prediction
            .claims
            .iter()
            .map(|claim| claim.claim_id.as_str())
            .collect::<BTreeSet<_>>();
        if predicted_ids.len() != prediction.claims.len() {
            bail!("duplicate predicted claim id for {}", case.control_id);
        }
        let prediction_by_span = prediction
            .claims
            .iter()
            .map(|claim| ((claim.source_span.start, claim.source_span.end), claim))
            .collect::<BTreeMap<_, _>>();
        if prediction_by_span.len() != prediction.claims.len() {
            bail!("duplicate predicted source span for {}", case.control_id);
        }

        let mut predicted_labels = BTreeMap::<String, HumanSupportLabel>::new();
        let mut segmentation_complete = prediction.claims.len() == case.claims.len();
        let mut all_claim_labels_correct = true;
        for gold in &case.claims {
            let Some(predicted) =
                prediction_by_span.get(&(gold.source_span.start, gold.source_span.end))
            else {
                segmentation_complete = false;
                all_claim_labels_correct = false;
                continue;
            };
            matched_span_count += 1;
            predicted_labels.insert(gold.claim_id.clone(), predicted.support_label);
            all_claim_labels_correct &= predicted.support_label == gold.expected_support_label;
            let pair = (gold.expected_support_label, predicted.support_label);
            all_pairs.push(pair);
            type_pairs.entry(gold.claim_type).or_default().push(pair);
            match gold.centrality {
                ClaimCentrality::Central => central_pairs.push(pair),
                ClaimCentrality::Material => non_central_pairs.push(pair),
            }
        }

        if !segmentation_complete {
            push_attribution(
                &mut rows,
                &mut attribution_counts,
                case,
                None,
                aggregate_candidate_label(&case.claims).ok(),
                false,
                CandidateErrorAttribution::SegmentationFailure,
            );
            continue;
        }

        let predicted_candidate = aggregate_with_predictions(&case.claims, &predicted_labels)?;
        let gold_aggregation = aggregate_candidate_label(&case.claims)?;
        candidate_pairs.push((case.expected_candidate_label, predicted_candidate));
        let attribution = if predicted_candidate == case.expected_candidate_label {
            if all_claim_labels_correct {
                CandidateErrorAttribution::Correct
            } else {
                CandidateErrorAttribution::MaskedClaimError
            }
        } else if all_claim_labels_correct {
            CandidateErrorAttribution::AggregationRuleError
        } else if gold_aggregation == case.expected_candidate_label {
            CandidateErrorAttribution::ClaimClassificationError
        } else {
            CandidateErrorAttribution::MixedError
        };
        push_attribution(
            &mut rows,
            &mut attribution_counts,
            case,
            Some(predicted_candidate),
            Some(gold_aggregation),
            all_claim_labels_correct,
            attribution,
        );
    }

    let support_confusion_by_claim_type = all_claim_types()
        .into_iter()
        .map(|claim_type| ClaimTypeDiagnostic {
            claim_type,
            support_classification: label_summary(
                type_pairs
                    .get(&claim_type)
                    .map(Vec::as_slice)
                    .unwrap_or(&[]),
                false,
            ),
        })
        .collect::<Vec<_>>();

    Ok(AtomicDiagnosticsResult {
        probe_id: probe_id.into(),
        segmentation_exact_span_precision: ratio(matched_span_count, predicted_span_count),
        segmentation_exact_span_recall: ratio(matched_span_count, gold_span_count),
        overall_claim_support: label_summary(&all_pairs, false),
        support_confusion_by_claim_type,
        centrality_split: CentralityDiagnostics {
            central_claims: label_summary(&central_pairs, false),
            non_central_material_claims: label_summary(&non_central_pairs, false),
        },
        aggregation_error_attribution: AggregationAttributionDiagnostics {
            candidate_classification: label_summary(&candidate_pairs, true),
            attribution_counts,
            rows,
        },
    })
}

fn aggregate_with_predictions(
    claims: &[AtomicControlClaim],
    predictions: &BTreeMap<String, HumanSupportLabel>,
) -> Result<HumanSupportLabel> {
    let central = claims
        .iter()
        .filter(|claim| claim.centrality == ClaimCentrality::Central)
        .collect::<Vec<_>>();
    if central.len() != 1 {
        bail!("exactly one central claim required");
    }
    let central_label = predictions
        .get(&central[0].claim_id)
        .copied()
        .context("missing central Claim prediction")?;
    match central_label {
        HumanSupportLabel::Unsupported => return Ok(HumanSupportLabel::Unsupported),
        HumanSupportLabel::NotAssessable => return Ok(HumanSupportLabel::NotAssessable),
        HumanSupportLabel::PartiallySupported => return Ok(HumanSupportLabel::PartiallySupported),
        HumanSupportLabel::Supported => {}
    }
    for claim in claims
        .iter()
        .filter(|claim| claim.material && claim.centrality == ClaimCentrality::Material)
    {
        let label = predictions
            .get(&claim.claim_id)
            .copied()
            .with_context(|| format!("missing prediction for {}", claim.claim_id))?;
        if label != HumanSupportLabel::Supported {
            return Ok(HumanSupportLabel::PartiallySupported);
        }
    }
    Ok(HumanSupportLabel::Supported)
}

fn synthetic_predictions(
    controls: &AtomicControlDataset,
    constant: Option<HumanSupportLabel>,
) -> Vec<AtomicControlPrediction> {
    controls
        .control_cases
        .iter()
        .map(|case| AtomicControlPrediction {
            control_id: case.control_id.clone(),
            claims: case
                .claims
                .iter()
                .map(|claim| AtomicClaimPrediction {
                    claim_id: claim.claim_id.clone(),
                    source_span: claim.source_span.clone(),
                    support_label: constant.unwrap_or(claim.expected_support_label),
                })
                .collect(),
        })
        .collect()
}

fn push_attribution(
    rows: &mut Vec<CandidateAttributionRow>,
    counts: &mut BTreeMap<String, usize>,
    case: &AtomicControlCase,
    predicted: Option<HumanSupportLabel>,
    gold_aggregation: Option<HumanSupportLabel>,
    all_claim_labels_correct: bool,
    attribution: CandidateErrorAttribution,
) {
    *counts
        .entry(attribution_name(attribution).to_string())
        .or_default() += 1;
    rows.push(CandidateAttributionRow {
        control_id: case.control_id.clone(),
        expected_candidate_label: case.expected_candidate_label,
        predicted_candidate_label: predicted,
        gold_claim_aggregation: gold_aggregation,
        all_claim_labels_correct,
        attribution,
    });
}

fn label_summary(
    pairs: &[(HumanSupportLabel, HumanSupportLabel)],
    force_all_gold_labels: bool,
) -> LabelDiagnosticSummary {
    let mut confusion = BTreeMap::<String, BTreeMap<String, usize>>::new();
    let mut observed = BTreeSet::<HumanSupportLabel>::new();
    let mut exact = 0usize;
    for (gold, predicted) in pairs {
        observed.insert(*gold);
        exact += usize::from(gold == predicted);
        *confusion
            .entry(label_name(*gold).to_string())
            .or_default()
            .entry(label_name(*predicted).to_string())
            .or_default() += 1;
    }
    if force_all_gold_labels {
        observed.extend(all_labels());
    }
    let recalls = observed
        .iter()
        .map(|gold| {
            let row = confusion.get(label_name(*gold));
            let total = row.map(|row| row.values().sum::<usize>()).unwrap_or(0);
            let correct = row
                .and_then(|row| row.get(label_name(*gold)))
                .copied()
                .unwrap_or(0);
            if total == 0 {
                0.0
            } else {
                correct as f64 / total as f64
            }
        })
        .collect::<Vec<_>>();
    let absent_gold_labels = all_labels()
        .into_iter()
        .filter(|label| !pairs.iter().any(|(gold, _)| gold == label))
        .map(|label| label_name(label).to_string())
        .collect::<Vec<_>>();
    LabelDiagnosticSummary {
        item_count: pairs.len(),
        exact_match_count: exact,
        exact_accuracy: ratio(exact, pairs.len()),
        observed_gold_labels: observed
            .into_iter()
            .map(|label| label_name(label).to_string())
            .collect(),
        absent_gold_labels,
        macro_recall_over_observed_gold_labels: if recalls.is_empty() {
            None
        } else {
            Some(recalls.iter().sum::<f64>() / recalls.len() as f64)
        },
        confusion,
    }
}

fn claim_label_counts(controls: &AtomicControlDataset) -> BTreeMap<String, usize> {
    let mut counts = BTreeMap::new();
    for claim in controls
        .control_cases
        .iter()
        .flat_map(|case| case.claims.iter())
    {
        *counts
            .entry(label_name(claim.expected_support_label).to_string())
            .or_default() += 1;
    }
    counts
}

fn ratio(numerator: usize, denominator: usize) -> Option<f64> {
    (denominator > 0).then_some(numerator as f64 / denominator as f64)
}

fn all_labels() -> [HumanSupportLabel; 4] {
    [
        HumanSupportLabel::Supported,
        HumanSupportLabel::PartiallySupported,
        HumanSupportLabel::Unsupported,
        HumanSupportLabel::NotAssessable,
    ]
}

fn all_claim_types() -> [AtomicClaimType; 7] {
    [
        AtomicClaimType::Proposition,
        AtomicClaimType::Scope,
        AtomicClaimType::Prediction,
        AtomicClaimType::Causal,
        AtomicClaimType::Counterexample,
        AtomicClaimType::Limitation,
        AtomicClaimType::Falsifiability,
    ]
}

fn label_name(label: HumanSupportLabel) -> &'static str {
    match label {
        HumanSupportLabel::Supported => "supported",
        HumanSupportLabel::PartiallySupported => "partially_supported",
        HumanSupportLabel::Unsupported => "unsupported",
        HumanSupportLabel::NotAssessable => "not_assessable",
    }
}

fn attribution_name(attribution: CandidateErrorAttribution) -> &'static str {
    match attribution {
        CandidateErrorAttribution::Correct => "correct",
        CandidateErrorAttribution::MaskedClaimError => "masked_claim_error",
        CandidateErrorAttribution::ClaimClassificationError => "claim_classification_error",
        CandidateErrorAttribution::AggregationRuleError => "aggregation_rule_error",
        CandidateErrorAttribution::MixedError => "mixed_error",
        CandidateErrorAttribution::SegmentationFailure => "segmentation_failure",
    }
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn controls() -> AtomicControlDataset {
        serde_json::from_slice(CONTROL_BYTES).expect("controls")
    }

    #[test]
    fn perfect_probe_has_no_diagnostic_errors() {
        let controls = controls();
        let predictions = synthetic_predictions(&controls, None);
        let result = analyze_predictions("perfect", &controls, &predictions).expect("diagnostics");
        assert_eq!(result.overall_claim_support.exact_accuracy, Some(1.0));
        assert_eq!(
            result
                .aggregation_error_attribution
                .candidate_classification
                .exact_accuracy,
            Some(1.0)
        );
        assert_eq!(
            result
                .aggregation_error_attribution
                .attribution_counts
                .get("correct"),
            Some(&16)
        );
    }

    #[test]
    fn always_partial_probe_exposes_collapse_and_attributes_claim_error() {
        let controls = controls();
        let predictions =
            synthetic_predictions(&controls, Some(HumanSupportLabel::PartiallySupported));
        let result = analyze_predictions("collapse", &controls, &predictions).expect("diagnostics");
        assert_eq!(result.overall_claim_support.exact_accuracy, Some(0.0));
        assert_eq!(
            result
                .aggregation_error_attribution
                .candidate_classification
                .exact_accuracy,
            Some(0.25)
        );
        assert_eq!(
            result
                .aggregation_error_attribution
                .attribution_counts
                .get("claim_classification_error"),
            Some(&12)
        );
        assert_eq!(
            result
                .aggregation_error_attribution
                .attribution_counts
                .get("masked_claim_error"),
            Some(&4)
        );
    }

    #[test]
    fn readiness_report_resolves_partial_atomic_gold_with_versioned_supplement() {
        let report = Phase7AtomicClaimDiagnosticsEvaluator::evaluate("test").expect("report");
        assert!(report.four_label_local_claim_calibration_available);
        assert!(report.missing_gold_atomic_claim_labels.is_empty());
        assert_eq!(
            report
                .supplement_gold_atomic_claim_label_counts
                .get("partially_supported"),
            Some(&4)
        );
        assert_eq!(
            report
                .combined_gold_atomic_claim_label_counts
                .get("partially_supported"),
            Some(&4)
        );
        assert!(report.real_model_diagnostics.is_none());
        assert!(report.real_model_supplement_diagnostics.is_none());
        assert!(!report.guards.diagnostic_supplement_changes_candidate_gate);
        assert!(!report.guards.held_out_accessed);
    }

    #[test]
    fn predictions_align_by_exact_source_span_not_provider_claim_id() {
        let controls = controls();
        let mut predictions = synthetic_predictions(&controls, None);
        for (case_index, prediction) in predictions.iter_mut().enumerate() {
            for (claim_index, claim) in prediction.claims.iter_mut().enumerate() {
                claim.claim_id = format!("provider_{case_index}_{claim_index}");
            }
        }
        let result = analyze_predictions("provider-ids", &controls, &predictions)
            .expect("source-span alignment");
        assert_eq!(result.segmentation_exact_span_precision, Some(1.0));
        assert_eq!(result.segmentation_exact_span_recall, Some(1.0));
        assert_eq!(result.overall_claim_support.exact_accuracy, Some(1.0));
    }

    #[test]
    fn aggregation_rule_error_is_separable_from_claim_error() {
        let mut controls = controls();
        let case = &mut controls.control_cases[0];
        case.expected_candidate_label = HumanSupportLabel::Unsupported;
        let predictions = synthetic_predictions(&controls, None);
        let result =
            analyze_predictions("inconsistent-gold", &controls, &predictions).expect("diagnostics");
        assert_eq!(
            result
                .aggregation_error_attribution
                .attribution_counts
                .get("aggregation_rule_error"),
            Some(&1)
        );
    }
}
