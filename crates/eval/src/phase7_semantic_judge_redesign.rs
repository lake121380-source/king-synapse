use crate::phase7_candidate_error_analysis::Phase7CandidateErrorAnalysisEvaluator;
use crate::phase7_independent_adjudication_calibration::{
    compute_confusion_matrix, BinaryCalibrationView, CandidateJudgeCalibrationRow, ConfusionMatrix,
    HumanSupportLabel,
};
use crate::phase7_model_adjudicated_silver_freeze::Phase7ModelAdjudicatedSilverFreeze;
use crate::phase7_pattern_provider_comparison::ModelProviderExecutionArtifact;
use anyhow::{bail, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;

const PROTOCOL_BYTES: &[u8] = include_bytes!(
    "../datasets/pattern_extraction/phase7_3_2_semantic_judge_redesign_protocol.json"
);
const PROMPT_BYTES: &[u8] = include_bytes!("../config/phase7_3_2_semantic_judge_prompt_v1.md");
const DESIGN_BYTES: &[u8] =
    include_bytes!("../datasets/pattern_extraction/phase7_2_pattern_extraction_design.json");
const CANDIDATE_EXECUTION_BYTES: &[u8] =
    include_bytes!("../reports/phase7_2_3_real_provider_execution.json");
const EVALUATION_VERSION: &str = "phase7.3.2-semantic-judge-redesign-v1";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SemanticJudgeDecision {
    pub case_id: String,
    pub candidate_response_sha256: String,
    pub support_label: HumanSupportLabel,
    pub unsupported_warning: bool,
    pub cited_evidence_ids: Vec<String>,
    pub reason_codes: Vec<String>,
    pub rationale: String,
    pub confidence: String,
    pub abstained: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SemanticJudgeExecutionArtifact {
    pub schema_version: u32,
    pub execution_id: String,
    pub phase: String,
    pub status: String,
    pub provider_name: String,
    pub model_requested: String,
    pub resolved_model: Option<String>,
    pub prompt_version: String,
    pub prompt_sha256: String,
    pub protocol_sha256: String,
    pub design_dataset_sha256: String,
    pub candidate_execution_sha256: String,
    pub adapter_sha256: String,
    pub temperature: f64,
    pub top_p: f64,
    pub strict_parser: bool,
    pub automatic_repair: bool,
    pub selective_retry: bool,
    pub case_isolation: bool,
    pub silver_labels_visible: bool,
    pub reviewer_annotations_visible: bool,
    pub adjudication_visible: bool,
    pub old_judge_visible: bool,
    pub reference_candidates_visible: bool,
    pub held_out_accessed: bool,
    pub api_key_recorded: bool,
    pub raw_provider_responses_stored: bool,
    pub design_case_count: usize,
    pub completed_case_count: usize,
    pub decisions: Vec<SemanticJudgeDecision>,
    pub protocol_id: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OrdinalComparisonRow {
    pub case_id: String,
    pub silver_support_label: HumanSupportLabel,
    pub semantic_judge_support_label: HumanSupportLabel,
    pub exact_match: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct OrdinalAgreement {
    pub case_count: usize,
    pub exact_match_count: usize,
    pub exact_agreement: Option<f64>,
    pub confusion: BTreeMap<String, BTreeMap<String, usize>>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct JudgeCalibrationSummary {
    pub strict_safety: ConfusionMatrix,
    pub strong_error: ConfusionMatrix,
    pub coverage: f64,
    pub abstention_rate: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SemanticJudgeDelta {
    pub strict_specificity_delta: Option<f64>,
    pub strict_false_positive_rate_delta: Option<f64>,
    pub strict_balanced_accuracy_delta: Option<f64>,
    pub strict_recall_delta: Option<f64>,
    pub strong_specificity_delta: Option<f64>,
    pub strong_false_positive_rate_delta: Option<f64>,
    pub strong_balanced_accuracy_delta: Option<f64>,
    pub strong_recall_delta: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SemanticJudgeArtifactHashes {
    pub protocol_sha256: String,
    pub prompt_sha256: String,
    pub design_dataset_sha256: String,
    pub candidate_execution_sha256: String,
    pub silver_freeze_sha256: String,
    pub old_judge_report_sha256: String,
    pub semantic_judge_execution_sha256: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SemanticJudgeGuards {
    pub evidence_bundle_frozen: bool,
    pub design_candidates_frozen: bool,
    pub model_adjudicated_silver_frozen: bool,
    pub human_gold_claimed: bool,
    pub extractor_modified: bool,
    pub provider_modified: bool,
    pub old_frozen_judge_modified: bool,
    pub semantic_judge_only_experimental_variable: bool,
    pub silver_labels_visible_to_semantic_judge: bool,
    pub reviewer_annotations_visible_to_semantic_judge: bool,
    pub old_judge_visible_to_semantic_judge: bool,
    pub reference_candidates_visible_to_semantic_judge: bool,
    pub held_out_cases_untouched: bool,
    pub memory_write_authorized: bool,
    pub pattern_promotion_authorized: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
    pub generalized_performance_claimed: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Phase7SemanticJudgeRedesignDecision {
    ExecutionBlocked,
    DiagnosticDiscriminationImproved,
    DiagnosticDiscriminationNotImproved,
    ExperimentInvalid,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7SemanticJudgeRedesignReport {
    pub schema_version: u32,
    pub evaluation_version: String,
    pub tag: String,
    pub generated_at: String,
    pub phase: String,
    pub purpose: String,
    pub reference_status: String,
    pub artifact_hashes: SemanticJudgeArtifactHashes,
    pub execution_status: String,
    pub semantic_judge_provider: Option<String>,
    pub semantic_judge_model: Option<String>,
    pub ordinal_rows: Vec<OrdinalComparisonRow>,
    pub ordinal_agreement: Option<OrdinalAgreement>,
    pub old_frozen_judge: JudgeCalibrationSummary,
    pub redesigned_semantic_judge: Option<JudgeCalibrationSummary>,
    pub delta_vs_old_frozen_judge: Option<SemanticJudgeDelta>,
    pub scope_calibration: Option<ConfusionMatrix>,
    pub guards: SemanticJudgeGuards,
    pub decision: Phase7SemanticJudgeRedesignDecision,
    pub conclusion: String,
}

pub struct Phase7SemanticJudgeRedesignEvaluator;

impl Phase7SemanticJudgeRedesignEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase7SemanticJudgeRedesignReport> {
        evaluate(tag.into())
    }
}

pub fn semantic_judge_execution_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports")
        .join("phase7_3_2_semantic_judge_execution.json")
}

pub fn load_phase7_semantic_judge_execution() -> Result<Option<SemanticJudgeExecutionArtifact>> {
    let path = semantic_judge_execution_path();
    if !path.exists() {
        return Ok(None);
    }
    let bytes = std::fs::read(&path).with_context(|| format!("read {}", path.display()))?;
    let artifact =
        serde_json::from_slice(&bytes).with_context(|| format!("parse {}", path.display()))?;
    Ok(Some(artifact))
}

fn evaluate(tag: String) -> Result<Phase7SemanticJudgeRedesignReport> {
    let protocol: serde_json::Value =
        serde_json::from_slice(PROTOCOL_BYTES).context("parse Phase 7.3.2 protocol")?;
    if protocol["protocol_id"] != "phase7.3.2-semantic-judge-redesign-v1" {
        bail!("phase7_3_2_protocol_id_invalid");
    }

    let silver = Phase7ModelAdjudicatedSilverFreeze::build()?;
    let old_report = Phase7CandidateErrorAnalysisEvaluator::evaluate("phase7.3.2-old-judge")?;
    let candidate_execution: ModelProviderExecutionArtifact =
        serde_json::from_slice(CANDIDATE_EXECUTION_BYTES)
            .context("parse frozen Phase 7.2.3 candidate execution")?;
    let old_warnings = old_report
        .cases
        .iter()
        .map(|case| (case.case_id.as_str(), case.unsupported_warning))
        .collect::<BTreeMap<_, _>>();
    let old_rows = silver
        .candidates
        .iter()
        .map(|candidate| CandidateJudgeCalibrationRow {
            case_id: candidate.case_id.clone(),
            silver_support_label: candidate.aggregate_support_label,
            frozen_judge_unsupported_warning: *old_warnings
                .get(candidate.case_id.as_str())
                .unwrap_or(&false),
        })
        .collect::<Vec<_>>();
    let old_summary = calibration_summary(&old_rows, &old_rows, 0);

    let execution = load_phase7_semantic_judge_execution()?;
    let execution_sha256 = semantic_judge_execution_path()
        .exists()
        .then(|| std::fs::read(semantic_judge_execution_path()))
        .transpose()?
        .map(|bytes| sha256(&bytes));
    let silver_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("datasets/pattern_extraction/phase7_3_1_model_adjudicated_silver_labels.json");
    let old_report_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports/phase7_candidate_error_analysis.json");
    let artifact_hashes = SemanticJudgeArtifactHashes {
        protocol_sha256: sha256(PROTOCOL_BYTES),
        prompt_sha256: sha256(PROMPT_BYTES),
        design_dataset_sha256: sha256(DESIGN_BYTES),
        candidate_execution_sha256: sha256(CANDIDATE_EXECUTION_BYTES),
        silver_freeze_sha256: sha256(&std::fs::read(&silver_path)?),
        old_judge_report_sha256: sha256(&std::fs::read(&old_report_path)?),
        semantic_judge_execution_sha256: execution_sha256,
    };

    let base_guards = SemanticJudgeGuards {
        evidence_bundle_frozen: true,
        design_candidates_frozen: true,
        model_adjudicated_silver_frozen: true,
        human_gold_claimed: false,
        extractor_modified: false,
        provider_modified: false,
        old_frozen_judge_modified: false,
        semantic_judge_only_experimental_variable: true,
        silver_labels_visible_to_semantic_judge: false,
        reviewer_annotations_visible_to_semantic_judge: false,
        old_judge_visible_to_semantic_judge: false,
        reference_candidates_visible_to_semantic_judge: false,
        held_out_cases_untouched: true,
        memory_write_authorized: false,
        pattern_promotion_authorized: false,
        runtime_authorized: false,
        hermes_authorized: false,
        generalized_performance_claimed: false,
    };

    let Some(execution) = execution else {
        return Ok(Phase7SemanticJudgeRedesignReport {
            schema_version: 1,
            evaluation_version: EVALUATION_VERSION.to_string(),
            tag,
            generated_at: Utc::now().to_rfc3339(),
            phase: "Phase 7.3.2 Semantic Judge Redesign".to_string(),
            purpose: protocol["purpose"].as_str().unwrap_or_default().to_string(),
            reference_status: silver.label_status,
            artifact_hashes,
            execution_status: "blocked_missing_semantic_judge_execution".to_string(),
            semantic_judge_provider: None,
            semantic_judge_model: None,
            ordinal_rows: Vec::new(),
            ordinal_agreement: None,
            old_frozen_judge: old_summary,
            redesigned_semantic_judge: None,
            delta_vs_old_frozen_judge: None,
            scope_calibration: None,
            guards: base_guards,
            decision: Phase7SemanticJudgeRedesignDecision::ExecutionBlocked,
            conclusion: "The redesign protocol and evaluator are frozen, but no semantic-Judge execution artifact exists. No replacement metrics are fabricated; held-out, runtime, memory writes, Hermes, and Pattern promotion remain blocked.".to_string(),
        });
    };

    validate_execution(&execution, &candidate_execution, &artifact_hashes)?;
    let silver_by_case = silver
        .candidates
        .iter()
        .map(|candidate| {
            (
                candidate.case_id.as_str(),
                candidate.aggregate_support_label,
            )
        })
        .collect::<BTreeMap<_, _>>();
    let mut strict_rows = Vec::new();
    let mut strong_rows = Vec::new();
    let mut ordinal_rows = Vec::new();
    for decision in &execution.decisions {
        let silver_label = *silver_by_case
            .get(decision.case_id.as_str())
            .context("semantic Judge case absent from frozen Silver")?;
        strict_rows.push(CandidateJudgeCalibrationRow {
            case_id: decision.case_id.clone(),
            silver_support_label: silver_label,
            frozen_judge_unsupported_warning: decision.unsupported_warning,
        });
        strong_rows.push(CandidateJudgeCalibrationRow {
            case_id: decision.case_id.clone(),
            silver_support_label: silver_label,
            frozen_judge_unsupported_warning: matches!(
                decision.support_label,
                HumanSupportLabel::Unsupported
            ),
        });
        ordinal_rows.push(OrdinalComparisonRow {
            case_id: decision.case_id.clone(),
            silver_support_label: silver_label,
            semantic_judge_support_label: decision.support_label,
            exact_match: silver_label == decision.support_label,
        });
    }
    ordinal_rows.sort_by(|a, b| a.case_id.cmp(&b.case_id));
    let abstentions = execution
        .decisions
        .iter()
        .filter(|row| row.abstained)
        .count();
    let redesigned = calibration_summary(&strict_rows, &strong_rows, abstentions);
    let ordinal = ordinal_agreement(&ordinal_rows);
    let delta = calibration_delta(&old_summary, &redesigned);
    let improved = metric_gt(
        redesigned.strict_safety.specificity,
        old_summary.strict_safety.specificity,
    ) && metric_lt(
        redesigned.strict_safety.false_positive_rate,
        old_summary.strict_safety.false_positive_rate,
    ) && metric_gt(
        redesigned.strict_safety.balanced_accuracy,
        old_summary.strict_safety.balanced_accuracy,
    );
    let decision = if improved {
        Phase7SemanticJudgeRedesignDecision::DiagnosticDiscriminationImproved
    } else {
        Phase7SemanticJudgeRedesignDecision::DiagnosticDiscriminationNotImproved
    };
    let conclusion = if improved {
        "On the ten frozen design Candidates, the redesigned semantic Judge improves diagnostic discrimination over the always-positive lexical proxy. This is same-design-set evidence against model-adjudicated Silver, not human Gold and not a held-out generalization claim. Scope calibration remains unavailable.".to_string()
    } else {
        "On the ten frozen design Candidates, the redesigned semantic Judge does not satisfy the frozen discrimination criteria against the always-positive lexical proxy. This negative result authorizes no tuning on held-out data and no runtime, memory, Hermes, or Pattern-promotion integration.".to_string()
    };

    Ok(Phase7SemanticJudgeRedesignReport {
        schema_version: 1,
        evaluation_version: EVALUATION_VERSION.to_string(),
        tag,
        generated_at: Utc::now().to_rfc3339(),
        phase: "Phase 7.3.2 Semantic Judge Redesign".to_string(),
        purpose: protocol["purpose"].as_str().unwrap_or_default().to_string(),
        reference_status: silver.label_status,
        artifact_hashes,
        execution_status: execution.status,
        semantic_judge_provider: Some(execution.provider_name),
        semantic_judge_model: execution.resolved_model.or(Some(execution.model_requested)),
        ordinal_rows,
        ordinal_agreement: Some(ordinal),
        old_frozen_judge: old_summary,
        redesigned_semantic_judge: Some(redesigned),
        delta_vs_old_frozen_judge: Some(delta),
        scope_calibration: None,
        guards: base_guards,
        decision,
        conclusion,
    })
}

fn validate_execution(
    execution: &SemanticJudgeExecutionArtifact,
    candidate_execution: &ModelProviderExecutionArtifact,
    hashes: &SemanticJudgeArtifactHashes,
) -> Result<()> {
    if execution.schema_version != 1
        || execution.execution_id != "phase7.3.2-semantic-judge-design-execution-v1"
        || execution.status != "completed"
        || execution.prompt_version != "PatternSemanticJudgePrompt-v1"
        || execution.protocol_id != "phase7.3.2-semantic-judge-redesign-v1"
        || execution.design_case_count != 10
        || execution.completed_case_count != 10
        || execution.decisions.len() != 10
        || execution.temperature != 0.0
        || execution.top_p != 1.0
        || !execution.strict_parser
        || execution.automatic_repair
        || execution.selective_retry
        || !execution.case_isolation
        || execution.silver_labels_visible
        || execution.reviewer_annotations_visible
        || execution.adjudication_visible
        || execution.old_judge_visible
        || execution.reference_candidates_visible
        || execution.held_out_accessed
        || execution.api_key_recorded
        || execution.raw_provider_responses_stored
    {
        bail!("phase7_3_2_semantic_judge_execution_boundary_invalid");
    }
    if execution.prompt_sha256 != hashes.prompt_sha256
        || execution.protocol_sha256 != hashes.protocol_sha256
        || execution.design_dataset_sha256 != hashes.design_dataset_sha256
        || execution.candidate_execution_sha256 != hashes.candidate_execution_sha256
    {
        bail!("phase7_3_2_semantic_judge_execution_lineage_invalid");
    }
    let expected = candidate_execution
        .outputs
        .iter()
        .map(|output| (output.case_id.as_str(), output.response_sha256.as_str()))
        .collect::<BTreeMap<_, _>>();
    let ids = execution
        .decisions
        .iter()
        .map(|decision| decision.case_id.as_str())
        .collect::<BTreeSet<_>>();
    if ids.len() != 10 || ids != expected.keys().copied().collect() {
        bail!("phase7_3_2_semantic_judge_case_set_invalid");
    }
    for decision in &execution.decisions {
        if expected.get(decision.case_id.as_str()).copied()
            != Some(decision.candidate_response_sha256.as_str())
            || decision.unsupported_warning
                != matches!(
                    decision.support_label,
                    HumanSupportLabel::PartiallySupported | HumanSupportLabel::Unsupported
                )
            || decision.abstained
                != matches!(decision.support_label, HumanSupportLabel::NotAssessable)
            || decision.rationale.trim().is_empty()
        {
            bail!("phase7_3_2_semantic_judge_decision_invalid");
        }
    }
    Ok(())
}

fn calibration_summary(
    strict_rows: &[CandidateJudgeCalibrationRow],
    strong_rows: &[CandidateJudgeCalibrationRow],
    abstentions: usize,
) -> JudgeCalibrationSummary {
    let count = strict_rows.len();
    JudgeCalibrationSummary {
        strict_safety: compute_confusion_matrix(strict_rows, BinaryCalibrationView::StrictSafety),
        strong_error: compute_confusion_matrix(strong_rows, BinaryCalibrationView::StrongError),
        coverage: if count == 0 {
            0.0
        } else {
            (count - abstentions) as f64 / count as f64
        },
        abstention_rate: if count == 0 {
            0.0
        } else {
            abstentions as f64 / count as f64
        },
    }
}

fn ordinal_agreement(rows: &[OrdinalComparisonRow]) -> OrdinalAgreement {
    let mut confusion = BTreeMap::<String, BTreeMap<String, usize>>::new();
    for row in rows {
        *confusion
            .entry(label_name(row.silver_support_label).to_string())
            .or_default()
            .entry(label_name(row.semantic_judge_support_label).to_string())
            .or_default() += 1;
    }
    let exact = rows.iter().filter(|row| row.exact_match).count();
    OrdinalAgreement {
        case_count: rows.len(),
        exact_match_count: exact,
        exact_agreement: (!rows.is_empty()).then_some(exact as f64 / rows.len() as f64),
        confusion,
    }
}

fn label_name(label: HumanSupportLabel) -> &'static str {
    match label {
        HumanSupportLabel::Supported => "supported",
        HumanSupportLabel::PartiallySupported => "partially_supported",
        HumanSupportLabel::Unsupported => "unsupported",
        HumanSupportLabel::NotAssessable => "not_assessable",
    }
}

fn calibration_delta(
    old: &JudgeCalibrationSummary,
    new: &JudgeCalibrationSummary,
) -> SemanticJudgeDelta {
    SemanticJudgeDelta {
        strict_specificity_delta: subtract(
            new.strict_safety.specificity,
            old.strict_safety.specificity,
        ),
        strict_false_positive_rate_delta: subtract(
            new.strict_safety.false_positive_rate,
            old.strict_safety.false_positive_rate,
        ),
        strict_balanced_accuracy_delta: subtract(
            new.strict_safety.balanced_accuracy,
            old.strict_safety.balanced_accuracy,
        ),
        strict_recall_delta: subtract(
            new.strict_safety.recall_sensitivity,
            old.strict_safety.recall_sensitivity,
        ),
        strong_specificity_delta: subtract(
            new.strong_error.specificity,
            old.strong_error.specificity,
        ),
        strong_false_positive_rate_delta: subtract(
            new.strong_error.false_positive_rate,
            old.strong_error.false_positive_rate,
        ),
        strong_balanced_accuracy_delta: subtract(
            new.strong_error.balanced_accuracy,
            old.strong_error.balanced_accuracy,
        ),
        strong_recall_delta: subtract(
            new.strong_error.recall_sensitivity,
            old.strong_error.recall_sensitivity,
        ),
    }
}

fn subtract(left: Option<f64>, right: Option<f64>) -> Option<f64> {
    Some(left? - right?)
}

fn metric_gt(left: Option<f64>, right: Option<f64>) -> bool {
    matches!((left, right), (Some(left), Some(right)) if left > right)
}

fn metric_lt(left: Option<f64>, right: Option<f64>) -> bool {
    matches!((left, right), (Some(left), Some(right)) if left < right)
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
