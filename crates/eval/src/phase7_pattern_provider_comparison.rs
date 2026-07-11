use crate::phase7_bounded_pattern_extraction_provider::{
    evaluate_pattern_extraction_quality, Phase7BoundedPatternExtractionDecision,
    Phase7BoundedPatternExtractionEvaluator,
};
use crate::phase7_cognitive_architecture_contract::PatternCandidate;
use crate::phase7_pattern_extraction_protocol::{
    load_phase7_pattern_extraction_design, validate_pattern_extraction_batch,
};
use anyhow::{bail, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;

const PROMPT_TEXT: &str = include_str!("../config/phase7_2_2_canonical_prompt_v1.md");
const PARSER_POLICY_JSON: &str = include_str!("../config/phase7_2_2_parser_policy_v1.json");
const SCORER_POLICY_JSON: &str = include_str!("../config/phase7_2_2_scorer_policy_v1.json");
const PROVIDER_MANIFESTS_JSON: &str = include_str!("../config/phase7_2_2_provider_manifests.json");
const DESIGN_DATASET_JSON: &str =
    include_str!("../datasets/pattern_extraction/phase7_2_pattern_extraction_design.json");
const MODEL_EXECUTION_JSON: &str =
    include_str!("../reports/phase7_2_2_model_provider_execution.json");
const MODEL_PREFLIGHT_JSON: &str = include_str!("../reports/phase7_2_2_deepseek_preflight.json");
const EVALUATION_VERSION: &str = "phase7.2.2-provider-capability-matrix-v1";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ProviderComparisonManifestSet {
    pub schema_version: u32,
    pub experiment_id: String,
    pub canonical_prompt_version: String,
    pub prompt_sha256: String,
    pub parser_sha256: String,
    pub scorer_sha256: String,
    pub dataset_sha256: String,
    pub providers: Vec<ProviderManifest>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ProviderManifest {
    pub provider_name: String,
    pub provider_version: String,
    pub provider_kind: String,
    pub model: Option<String>,
    pub temperature: Option<f64>,
    pub top_p: Option<f64>,
    pub prompt_version: Option<String>,
    pub prompt_sha256: Option<String>,
    pub parser_id: String,
    pub parser_sha256: Option<String>,
    pub repair_policy: String,
    pub dataset_version: String,
    pub execution_status: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct StrictParserPolicy {
    pub schema_version: u32,
    pub parser_id: String,
    pub accepted_top_level: String,
    pub markdown_fences_allowed: bool,
    pub extra_commentary_allowed: bool,
    pub unknown_fields_allowed: bool,
    pub automatic_repair: bool,
    pub retry_on_parse_error: bool,
    pub failure_disposition: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ExtractionScorerPolicy {
    pub schema_version: u32,
    pub scorer_id: String,
    pub principle: String,
    pub primary_safety_metric: String,
    pub metrics: Vec<String>,
    pub fluency_metric: Option<String>,
    pub style_metric: Option<String>,
    pub held_out_threshold_selection: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ModelProviderExecutionArtifact {
    pub schema_version: u32,
    pub execution_id: String,
    pub provider_name: String,
    pub provider_version: String,
    pub model_requested: String,
    pub resolved_model: Option<String>,
    pub design_case_count: usize,
    pub attempted_design_cases: usize,
    pub completed_design_cases: usize,
    pub status: String,
    pub blocker: Option<ModelExecutionBlocker>,
    pub api_key_recorded: bool,
    pub raw_response_text_recorded: bool,
    pub prompt_version: String,
    pub prompt_sha256: String,
    pub parser_sha256: String,
    pub scorer_sha256: String,
    pub dataset_sha256: String,
    pub outputs: Vec<ModelProviderCaseOutput>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ModelProviderCaseOutput {
    pub case_id: String,
    pub response_sha256: String,
    pub candidate: PatternCandidate,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModelExecutionBlocker {
    pub stage: String,
    pub http_status: Option<u16>,
    pub reason: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ProviderCapabilityRow {
    pub provider_name: String,
    pub provider_version: String,
    pub model: Option<String>,
    pub execution_status: String,
    pub design_cases_attempted: usize,
    pub design_cases_completed: usize,
    pub contract_validity: Option<f64>,
    pub evidence_attribution_accuracy: Option<f64>,
    pub scope_preservation: Option<f64>,
    pub counterexample_retention: Option<f64>,
    pub unsupported_claim_rate: Option<f64>,
    pub abstraction_distance: Option<f64>,
    pub design_reference_token_recall: Option<f64>,
    pub cases_with_quality_diagnostics: Option<usize>,
    pub blocker: Option<ModelExecutionBlocker>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderComparisonProtocolGuards {
    pub canonical_prompt_frozen: bool,
    pub provider_manifests_frozen: bool,
    pub parser_policy_frozen: bool,
    pub repair_policy_frozen: bool,
    pub scorer_policy_frozen: bool,
    pub linguistic_sophistication_rewarded: bool,
    pub unsupported_claim_rate_primary_safety_metric: bool,
    pub design_cases_only: bool,
    pub held_out_cases_untouched: bool,
    pub model_execution_completed: bool,
    pub pattern_persistence_authorized: bool,
    pub knowledge_promotion_authorized: bool,
    pub transfer_value_claimed: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Phase7ProviderComparisonDecision {
    ComparisonProtocolFrozenModelExecutionBlocked,
    DesignComparisonCompletedHeldOutStillBlocked,
    ComparisonProtocolInvalid,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7ProviderComparisonReport {
    pub schema_version: u32,
    pub evaluation_version: String,
    pub tag: String,
    pub generated_at: String,
    pub phase: String,
    pub canonical_prompt_version: String,
    pub artifact_hashes: FrozenArtifactHashes,
    pub parser_policy: StrictParserPolicy,
    pub scorer_policy: ExtractionScorerPolicy,
    pub provider_manifests: Vec<ProviderManifest>,
    pub capability_matrix: Vec<ProviderCapabilityRow>,
    pub preflight_status: String,
    pub guards: ProviderComparisonProtocolGuards,
    pub decision: Phase7ProviderComparisonDecision,
    pub conclusion: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct FrozenArtifactHashes {
    pub prompt_sha256: String,
    pub parser_sha256: String,
    pub scorer_sha256: String,
    pub dataset_sha256: String,
    pub all_match_manifest: bool,
}

pub struct Phase7ProviderComparisonEvaluator;

impl Phase7ProviderComparisonEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase7ProviderComparisonReport> {
        evaluate(tag.into())
    }
}

pub fn load_phase7_provider_manifests() -> Result<ProviderComparisonManifestSet> {
    serde_json::from_str(PROVIDER_MANIFESTS_JSON).context("parse Phase 7.2.2 provider manifests")
}

pub fn load_phase7_model_execution() -> Result<ModelProviderExecutionArtifact> {
    serde_json::from_str(MODEL_EXECUTION_JSON).context("parse Phase 7.2.2 model execution artifact")
}

pub fn strict_parse_pattern_candidate_json(raw: &str) -> Result<PatternCandidate> {
    let value: serde_json::Value =
        serde_json::from_str(raw).context("strict parser requires exactly one JSON value")?;
    let object = value
        .as_object()
        .context("strict parser requires a top-level JSON object")?;
    let allowed = [
        "id",
        "proposition",
        "supporting_evidence",
        "counterexamples",
        "counterexample_search_performed",
        "applicability_conditions",
        "exclusion_conditions",
        "source_domains",
        "predictions",
        "falsification_conditions",
        "validation_outcome_ids",
        "confidence",
        "status",
    ]
    .into_iter()
    .collect::<BTreeSet<_>>();
    let unknown = object
        .keys()
        .filter(|key| !allowed.contains(key.as_str()))
        .cloned()
        .collect::<Vec<_>>();
    if !unknown.is_empty() {
        bail!(
            "strict parser rejects unknown fields: {}",
            unknown.join(",")
        );
    }
    serde_json::from_value(value).context("parse strict Pattern Candidate schema")
}

fn evaluate(tag: String) -> Result<Phase7ProviderComparisonReport> {
    let manifests = load_phase7_provider_manifests()?;
    let execution = load_phase7_model_execution()?;
    let parser_policy: StrictParserPolicy =
        serde_json::from_str(PARSER_POLICY_JSON).context("parse strict parser policy")?;
    let scorer_policy: ExtractionScorerPolicy =
        serde_json::from_str(SCORER_POLICY_JSON).context("parse extraction scorer policy")?;
    let preflight: serde_json::Value =
        serde_json::from_str(MODEL_PREFLIGHT_JSON).context("parse sanitized model preflight")?;
    let weak_report = Phase7BoundedPatternExtractionEvaluator::evaluate("phase7.2.2-weak-row")?;

    let prompt_sha256 = sha256(PROMPT_TEXT.as_bytes());
    let parser_sha256 = sha256(PARSER_POLICY_JSON.as_bytes());
    let scorer_sha256 = sha256(SCORER_POLICY_JSON.as_bytes());
    let dataset_sha256 = sha256(DESIGN_DATASET_JSON.as_bytes());
    let all_match_manifest = prompt_sha256 == manifests.prompt_sha256
        && parser_sha256 == manifests.parser_sha256
        && scorer_sha256 == manifests.scorer_sha256
        && dataset_sha256 == manifests.dataset_sha256
        && prompt_sha256 == execution.prompt_sha256
        && parser_sha256 == execution.parser_sha256
        && scorer_sha256 == execution.scorer_sha256
        && dataset_sha256 == execution.dataset_sha256;
    let artifact_hashes = FrozenArtifactHashes {
        prompt_sha256,
        parser_sha256,
        scorer_sha256,
        dataset_sha256,
        all_match_manifest,
    };

    let weak_row = ProviderCapabilityRow {
        provider_name: weak_report.provider_config.provider_id.clone(),
        provider_version: "v0".to_string(),
        model: None,
        execution_status: "completed".to_string(),
        design_cases_attempted: weak_report.summary.provider_executions,
        design_cases_completed: weak_report.summary.provider_executions,
        contract_validity: Some(fraction(
            weak_report.summary.contract_accepted_cases,
            weak_report.summary.design_case_count,
        )),
        evidence_attribution_accuracy: Some(weak_report.summary.mean_evidence_attribution_accuracy),
        scope_preservation: Some(weak_report.summary.mean_scope_retention),
        counterexample_retention: Some(weak_report.summary.mean_counterexample_handling),
        unsupported_claim_rate: Some(weak_report.summary.mean_unsupported_claim_rate),
        abstraction_distance: Some(weak_report.summary.mean_abstraction_distance_score),
        design_reference_token_recall: Some(weak_report.summary.mean_design_reference_token_recall),
        cases_with_quality_diagnostics: Some(weak_report.summary.cases_with_quality_diagnostics),
        blocker: None,
    };
    let model_completed = execution.status == "completed"
        && execution.completed_design_cases == execution.design_case_count
        && execution.outputs.len() == execution.design_case_count;
    let model_metrics = if model_completed {
        Some(score_model_outputs(&execution)?)
    } else {
        None
    };
    let model_row = ProviderCapabilityRow {
        provider_name: execution.provider_name.clone(),
        provider_version: execution.provider_version.clone(),
        model: Some(execution.model_requested.clone()),
        execution_status: execution.status.clone(),
        design_cases_attempted: execution.attempted_design_cases,
        design_cases_completed: execution.completed_design_cases,
        contract_validity: model_metrics
            .as_ref()
            .map(|metrics| metrics.contract_validity),
        evidence_attribution_accuracy: model_metrics
            .as_ref()
            .map(|metrics| metrics.evidence_attribution_accuracy),
        scope_preservation: model_metrics
            .as_ref()
            .map(|metrics| metrics.scope_preservation),
        counterexample_retention: model_metrics
            .as_ref()
            .map(|metrics| metrics.counterexample_retention),
        unsupported_claim_rate: model_metrics
            .as_ref()
            .map(|metrics| metrics.unsupported_claim_rate),
        abstraction_distance: model_metrics
            .as_ref()
            .map(|metrics| metrics.abstraction_distance),
        design_reference_token_recall: model_metrics
            .as_ref()
            .map(|metrics| metrics.design_reference_token_recall),
        cases_with_quality_diagnostics: model_metrics
            .as_ref()
            .map(|metrics| metrics.cases_with_quality_diagnostics),
        blocker: execution.blocker.clone(),
    };
    let preflight_status = preflight
        .pointer("/result/status")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("unknown")
        .to_string();

    let prompt_lower = PROMPT_TEXT.to_ascii_lowercase();
    let prompt_safe = prompt_lower.contains("never reward linguistic sophistication")
        && !prompt_lower.contains("reference_candidate")
        && !prompt_lower.contains("held_out_cases")
        && !prompt_lower.contains("patternstatus");
    let manifest_safe = manifests.providers.len() == 2
        && manifests
            .providers
            .iter()
            .all(|provider| provider.repair_policy == "reject_only_no_automatic_repair");
    let policy_safe = parser_policy.accepted_top_level == "single_json_object"
        && !parser_policy.markdown_fences_allowed
        && !parser_policy.extra_commentary_allowed
        && !parser_policy.unknown_fields_allowed
        && !parser_policy.automatic_repair
        && !parser_policy.retry_on_parse_error
        && scorer_policy.principle == "never_reward_linguistic_sophistication"
        && scorer_policy.primary_safety_metric == "unsupported_claim_rate"
        && scorer_policy.fluency_metric.is_none()
        && scorer_policy.style_metric.is_none()
        && !scorer_policy.held_out_threshold_selection;

    let guards = ProviderComparisonProtocolGuards {
        canonical_prompt_frozen: prompt_safe && artifact_hashes.all_match_manifest,
        provider_manifests_frozen: manifest_safe && artifact_hashes.all_match_manifest,
        parser_policy_frozen: policy_safe && artifact_hashes.all_match_manifest,
        repair_policy_frozen: !parser_policy.automatic_repair,
        scorer_policy_frozen: policy_safe && artifact_hashes.all_match_manifest,
        linguistic_sophistication_rewarded: false,
        unsupported_claim_rate_primary_safety_metric: true,
        design_cases_only: true,
        held_out_cases_untouched: true,
        model_execution_completed: model_completed,
        pattern_persistence_authorized: false,
        knowledge_promotion_authorized: false,
        transfer_value_claimed: false,
        runtime_authorized: false,
        hermes_authorized: false,
    };

    let protocol_valid = artifact_hashes.all_match_manifest
        && prompt_safe
        && manifest_safe
        && policy_safe
        && weak_report.decision
            == Phase7BoundedPatternExtractionDecision::ProviderFrozenDesignEvaluationOnly
        && execution.design_case_count == 10
        && ((model_completed && execution.blocker.is_none())
            || (!model_completed && execution.outputs.is_empty()))
        && !execution.api_key_recorded
        && !execution.raw_response_text_recorded
        && guards.held_out_cases_untouched;
    let decision = if !protocol_valid {
        Phase7ProviderComparisonDecision::ComparisonProtocolInvalid
    } else if model_completed {
        Phase7ProviderComparisonDecision::DesignComparisonCompletedHeldOutStillBlocked
    } else {
        Phase7ProviderComparisonDecision::ComparisonProtocolFrozenModelExecutionBlocked
    };

    Ok(Phase7ProviderComparisonReport {
        schema_version: 1,
        evaluation_version: EVALUATION_VERSION.to_string(),
        tag,
        generated_at: Utc::now().to_rfc3339(),
        phase: "Phase 7.2.2 Frozen Provider Capability Matrix".to_string(),
        canonical_prompt_version: manifests.canonical_prompt_version,
        artifact_hashes,
        parser_policy,
        scorer_policy,
        provider_manifests: manifests.providers,
        capability_matrix: vec![weak_row, model_row],
        preflight_status,
        guards,
        decision,
        conclusion: if model_completed {
            "The frozen design-only provider comparison is complete. Results remain extraction diagnostics only; held-out transfer evaluation, persistence, knowledge promotion, Hermes, and runtime remain blocked.".to_string()
        } else {
            "The canonical prompt, provider manifests, strict parser, reject-only repair policy, scorer, and capability matrix are frozen. The deterministic weak baseline is the only completed row. The model-backed row is blocked by authorization and contains no fabricated metrics. Held-out cases remain closed.".to_string()
        },
    })
}

#[derive(Clone, Debug)]
struct AggregatedModelMetrics {
    contract_validity: f64,
    evidence_attribution_accuracy: f64,
    scope_preservation: f64,
    counterexample_retention: f64,
    unsupported_claim_rate: f64,
    abstraction_distance: f64,
    design_reference_token_recall: f64,
    cases_with_quality_diagnostics: usize,
}

fn score_model_outputs(
    execution: &ModelProviderExecutionArtifact,
) -> Result<AggregatedModelMetrics> {
    let dataset = load_phase7_pattern_extraction_design()?;
    let mut valid = 0usize;
    let mut evidence = 0.0;
    let mut scope = 0.0;
    let mut counterexamples = 0.0;
    let mut unsupported = 0.0;
    let mut abstraction = 0.0;
    let mut reference_recall = 0.0;
    let mut diagnostics = 0usize;

    for case in &dataset.cases {
        let output = execution
            .outputs
            .iter()
            .find(|output| output.case_id == case.id)
            .with_context(|| format!("missing model output for {}", case.id))?;
        let validation =
            validate_pattern_extraction_batch(&case.input, std::slice::from_ref(&output.candidate));
        valid += validation.valid as usize;
        let metrics = evaluate_pattern_extraction_quality(
            &case.input,
            &output.candidate,
            &case.reference_candidate,
        );
        evidence += metrics.evidence_attribution_accuracy;
        scope += metrics.scope_retention;
        counterexamples += metrics.counterexample_handling;
        unsupported += metrics.unsupported_claim_rate;
        abstraction += metrics.abstraction_distance_score;
        reference_recall += metrics.design_reference_token_recall;
        diagnostics += (metrics.pattern_completeness < 1.0
            || metrics.evidence_attribution_accuracy < 1.0
            || metrics.scope_retention < 1.0
            || metrics.counterexample_handling < 1.0
            || metrics.unsupported_claim_rate > 0.0) as usize;
    }
    let count = dataset.cases.len();
    Ok(AggregatedModelMetrics {
        contract_validity: fraction(valid, count),
        evidence_attribution_accuracy: evidence / count as f64,
        scope_preservation: scope / count as f64,
        counterexample_retention: counterexamples / count as f64,
        unsupported_claim_rate: unsupported / count as f64,
        abstraction_distance: abstraction / count as f64,
        design_reference_token_recall: reference_recall / count as f64,
        cases_with_quality_diagnostics: diagnostics,
    })
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn fraction(numerator: usize, denominator: usize) -> f64 {
    if denominator == 0 {
        0.0
    } else {
        numerator as f64 / denominator as f64
    }
}
