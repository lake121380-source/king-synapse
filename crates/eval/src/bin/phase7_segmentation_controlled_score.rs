use anyhow::{bail, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};
use synapse_eval::phase7_atomic_claim_diagnostics::{
    analyze_predictions, AtomicClaimPrediction, AtomicControlPrediction, AtomicDiagnosticsResult,
};
use synapse_eval::phase7_atomic_claim_measurement::{AtomicControlDataset, SourceSpan};
use synapse_eval::phase7_independent_adjudication_calibration::HumanSupportLabel;
use synapse_eval::phase7_segmentation_controlled_classification::ControlledJudgeOutput;

#[derive(Debug, Deserialize)]
struct ExecutionRow {
    case_id: String,
    status: String,
    output: Option<ControlledJudgeOutput>,
}

#[derive(Debug, Deserialize)]
struct ExecutionReport {
    execution_manifest_sha256: String,
    valid_output_count: usize,
    invalid_output_count: usize,
    resolved_model: Option<String>,
    results: Vec<ExecutionRow>,
}

#[derive(Debug, Serialize)]
struct GateDecision {
    valid_output_count_required: usize,
    valid_output_count_observed: usize,
    all_outputs_valid: bool,
    candidate_macro_recall_strictly_above: f64,
    candidate_macro_recall_observed: Option<f64>,
    candidate_macro_recall_passed: bool,
    candidate_single_class_prediction_rate_strictly_below: f64,
    candidate_single_class_prediction_rate_observed: Option<f64>,
    candidate_single_class_prediction_rate_passed: bool,
    all_four_candidate_labels_must_be_predicted: bool,
    predicted_candidate_labels: Vec<String>,
    all_four_candidate_labels_predicted: bool,
    overall_passed: bool,
}

#[derive(Debug, Serialize)]
struct CandidateDistribution {
    counts: BTreeMap<String, usize>,
    prediction_entropy_bits: Option<f64>,
    single_class_prediction_rate: Option<f64>,
}

#[derive(Debug, Serialize)]
struct ScoreReport {
    schema_version: u32,
    report_id: String,
    phase: String,
    generated_at: String,
    status: String,
    decision: String,
    execution_manifest_sha256: String,
    execution_report_sha256: String,
    resolved_model: Option<String>,
    valid_output_count: usize,
    invalid_output_count: usize,
    original_candidate_gate_diagnostics: Option<AtomicDiagnosticsResult>,
    combined_local_claim_diagnostics: Option<AtomicDiagnosticsResult>,
    candidate_prediction_distribution: CandidateDistribution,
    entry_gate: GateDecision,
    interpretation: Vec<String>,
    guards: BTreeMap<String, bool>,
}

fn sha256(path: &Path) -> Result<String> {
    let bytes = fs::read(path).with_context(|| format!("read {}", path.display()))?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
}

fn label_name(label: HumanSupportLabel) -> &'static str {
    match label {
        HumanSupportLabel::Supported => "supported",
        HumanSupportLabel::PartiallySupported => "partially_supported",
        HumanSupportLabel::Unsupported => "unsupported",
        HumanSupportLabel::NotAssessable => "not_assessable",
    }
}

fn predictions_for(
    dataset: &AtomicControlDataset,
    outputs: &BTreeMap<String, ControlledJudgeOutput>,
) -> Result<Vec<AtomicControlPrediction>> {
    dataset
        .control_cases
        .iter()
        .map(|case| {
            let output = outputs
                .get(&case.control_id)
                .with_context(|| format!("missing valid output for {}", case.control_id))?;
            if output.claim_judgments.len() != case.claims.len() {
                bail!("claim count mismatch for {}", case.control_id);
            }
            let claims = case
                .claims
                .iter()
                .zip(&output.claim_judgments)
                .map(|(gold, predicted)| {
                    if gold.claim_id != predicted.claim_id {
                        bail!("claim id/order mismatch for {}", gold.claim_id);
                    }
                    Ok(AtomicClaimPrediction {
                        claim_id: gold.claim_id.clone(),
                        source_span: SourceSpan {
                            start: gold.source_span.start,
                            end: gold.source_span.end,
                        },
                        support_label: predicted.support_label,
                    })
                })
                .collect::<Result<Vec<_>>>()?;
            Ok(AtomicControlPrediction {
                control_id: case.control_id.clone(),
                claims,
            })
        })
        .collect()
}

fn candidate_distribution(diagnostics: Option<&AtomicDiagnosticsResult>) -> CandidateDistribution {
    let mut counts = BTreeMap::<String, usize>::new();
    if let Some(value) = diagnostics {
        for row in &value.aggregation_error_attribution.rows {
            if let Some(label) = row.predicted_candidate_label {
                *counts.entry(label_name(label).to_string()).or_default() += 1;
            }
        }
    }
    let total = counts.values().sum::<usize>();
    if total == 0 {
        return CandidateDistribution {
            counts,
            prediction_entropy_bits: None,
            single_class_prediction_rate: None,
        };
    }
    let entropy = counts.values().fold(0.0, |sum, count| {
        let p = *count as f64 / total as f64;
        sum - p * p.log2()
    });
    let max_count = counts.values().copied().max().unwrap_or(0);
    CandidateDistribution {
        counts,
        prediction_entropy_bits: Some(entropy),
        single_class_prediction_rate: Some(max_count as f64 / total as f64),
    }
}

fn main() -> Result<()> {
    let crate_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let report_path =
        crate_dir.join("reports/phase7_3_3_c_atomic_claim_classifier_control_execution.json");
    let manifest_path = crate_dir.join("reports/phase7_3_3_c_execution_manifest_v1.json");
    let original_path =
        crate_dir.join("datasets/pattern_extraction/phase7_3_3_atomic_claim_controls.json");
    let supplement_path = crate_dir
        .join("datasets/pattern_extraction/phase7_3_3_a_partial_atomic_claim_supplement_v1.json");
    let output_path = crate_dir.join("reports/phase7_3_3_c_segmentation_controlled_score.json");

    let execution: ExecutionReport = serde_json::from_slice(&fs::read(&report_path)?)?;
    let manifest_hash = sha256(&manifest_path)?;
    if execution.execution_manifest_sha256 != manifest_hash {
        bail!("execution report manifest hash mismatch");
    }
    let original: AtomicControlDataset = serde_json::from_slice(&fs::read(original_path)?)?;
    let supplement: AtomicControlDataset = serde_json::from_slice(&fs::read(supplement_path)?)?;
    let mut outputs = BTreeMap::new();
    for row in execution.results {
        if row.status == "valid" {
            let output = row.output.context("valid row missing parsed output")?;
            if output.case_id != row.case_id {
                bail!("row/output case mismatch");
            }
            if outputs.insert(row.case_id, output).is_some() {
                bail!("duplicate execution row");
            }
        }
    }

    let all_valid = execution.valid_output_count == 20
        && execution.invalid_output_count == 0
        && outputs.len() == 20;
    let (original_diagnostics, combined_diagnostics) = if all_valid {
        let original_predictions = predictions_for(&original, &outputs)?;
        let mut combined = original.clone();
        combined
            .control_cases
            .extend(supplement.control_cases.clone());
        let combined_predictions = predictions_for(&combined, &outputs)?;
        (
            Some(analyze_predictions(
                "phase7_3_3_c_original_candidate_gate",
                &original,
                &original_predictions,
            )?),
            Some(analyze_predictions(
                "phase7_3_3_c_combined_local_claim_diagnostics",
                &combined,
                &combined_predictions,
            )?),
        )
    } else {
        (None, None)
    };

    let distribution = candidate_distribution(original_diagnostics.as_ref());
    let macro_recall = original_diagnostics.as_ref().and_then(|value| {
        value
            .aggregation_error_attribution
            .candidate_classification
            .macro_recall_over_observed_gold_labels
    });
    let predicted_labels = distribution.counts.keys().cloned().collect::<Vec<_>>();
    let all_labels = BTreeSet::from([
        "supported".to_string(),
        "partially_supported".to_string(),
        "unsupported".to_string(),
        "not_assessable".to_string(),
    ]);
    let predicted_set = predicted_labels.iter().cloned().collect::<BTreeSet<_>>();
    let macro_pass = macro_recall.is_some_and(|value| value > 0.25);
    let single_rate = distribution.single_class_prediction_rate;
    let single_pass = single_rate.is_some_and(|value| value < 1.0);
    let four_pass = predicted_set == all_labels;
    let overall = all_valid && macro_pass && single_pass && four_pass;
    let gate = GateDecision {
        valid_output_count_required: 20,
        valid_output_count_observed: execution.valid_output_count,
        all_outputs_valid: all_valid,
        candidate_macro_recall_strictly_above: 0.25,
        candidate_macro_recall_observed: macro_recall,
        candidate_macro_recall_passed: macro_pass,
        candidate_single_class_prediction_rate_strictly_below: 1.0,
        candidate_single_class_prediction_rate_observed: single_rate,
        candidate_single_class_prediction_rate_passed: single_pass,
        all_four_candidate_labels_must_be_predicted: true,
        predicted_candidate_labels: predicted_labels,
        all_four_candidate_labels_predicted: four_pass,
        overall_passed: overall,
    };
    let mut guards = BTreeMap::new();
    guards.insert("prompt_modified_after_execution".to_string(), false);
    guards.insert("parser_modified_after_execution".to_string(), false);
    guards.insert("aggregator_modified_after_execution".to_string(), false);
    guards.insert("design_cases_accessed".to_string(), false);
    guards.insert("held_out_accessed".to_string(), false);
    guards.insert("runtime_authorized".to_string(), false);
    guards.insert("memory_write_authorized".to_string(), false);

    let report = ScoreReport {
        schema_version: 1,
        report_id: "phase7.3.3-c-segmentation-controlled-score-v1".to_string(),
        phase: "Phase 7.3.3-C Segmentation-Controlled Atomic Claim Classification".to_string(),
        generated_at: Utc::now().to_rfc3339(),
        status: if overall { "control_entry_gate_passed" } else { "control_entry_gate_failed_negative_result" }.to_string(),
        decision: if overall {
            "segmentation_controlled_atomic_claim_classification_is_control_ready"
        } else {
            "record_negative_result_and_do_not_execute_design_cases"
        }.to_string(),
        execution_manifest_sha256: manifest_hash,
        execution_report_sha256: sha256(&report_path)?,
        resolved_model: execution.resolved_model,
        valid_output_count: execution.valid_output_count,
        invalid_output_count: execution.invalid_output_count,
        original_candidate_gate_diagnostics: original_diagnostics,
        combined_local_claim_diagnostics: combined_diagnostics,
        candidate_prediction_distribution: distribution,
        entry_gate: gate,
        interpretation: vec![
            "Segmentation and structural annotations were protocol-owned, so this run measures local support classification without the prior source-span confound.".to_string(),
            "The original sixteen balanced controls alone own the Candidate-level entry gate; the four Partial Claim supplements affect local diagnostics only.".to_string(),
            "Passing the control gate authorizes design-case preparation under the same frozen protocol; it does not establish design or held-out generalization.".to_string(),
        ],
        guards,
    };
    fs::write(&output_path, serde_json::to_vec_pretty(&report)?)?;
    println!("Status: {}", report.status);
    println!("Decision: {}", report.decision);
    println!("Valid outputs: {}/20", report.valid_output_count);
    println!(
        "Candidate distribution: {:?}",
        report.candidate_prediction_distribution.counts
    );
    println!(
        "Candidate macro recall: {:?}",
        report.entry_gate.candidate_macro_recall_observed
    );
    println!(
        "Single-class rate: {:?}",
        report
            .entry_gate
            .candidate_single_class_prediction_rate_observed
    );
    println!("Report: {}", output_path.display());
    Ok(())
}
