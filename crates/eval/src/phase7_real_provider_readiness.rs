use crate::phase7_bounded_pattern_extraction_provider::{
    evaluate_pattern_extraction_quality, PatternExtractionQualityMetrics,
};
use crate::phase7_pattern_extraction_protocol::{
    load_phase7_pattern_extraction_design, validate_pattern_extraction_batch,
};
use crate::phase7_pattern_provider_comparison::{
    load_phase7_provider_manifests, ExtractionScorerPolicy, ModelProviderExecutionArtifact,
    StrictParserPolicy,
};
use anyhow::{Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;

const PROMPT_TEXT: &str = include_str!("../config/phase7_2_2_canonical_prompt_v1.md");
const PARSER_POLICY_JSON: &str = include_str!("../config/phase7_2_2_parser_policy_v1.json");
const SCORER_POLICY_JSON: &str = include_str!("../config/phase7_2_2_scorer_policy_v1.json");
const DESIGN_DATASET_JSON: &str =
    include_str!("../datasets/pattern_extraction/phase7_2_pattern_extraction_design.json");
const EXECUTION_JSON: &str = include_str!("../reports/phase7_2_3_real_provider_execution.json");
const PREFLIGHT_JSON: &str =
    include_str!("../reports/phase7_2_3_deepseek_readiness_preflight.json");
const EVALUATION_VERSION: &str = "phase7.2.3-real-provider-readiness-v1";
const UNSUPPORTED_CLAIM_REVIEW_THRESHOLD: f64 = 0.20;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderReadinessPreflight {
    pub schema_version: u32,
    pub probe_id: String,
    pub provider_name: String,
    pub base_url: String,
    pub requested_model: String,
    pub models_endpoint_http_status: u16,
    pub chat_completion_http_status: u16,
    pub resolved_model: String,
    pub authentication_status: String,
    pub api_key_recorded: bool,
    pub raw_response_text_recorded: bool,
    pub held_out_cases_accessed: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReadinessArtifactHashes {
    pub prompt_sha256: String,
    pub parser_sha256: String,
    pub scorer_sha256: String,
    pub dataset_sha256: String,
    pub execution_sha256: String,
    pub frozen_protocol_matches_manifest: bool,
    pub execution_matches_frozen_protocol: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct RealProviderCaseReadiness {
    pub case_id: String,
    pub response_sha256: String,
    pub contract_valid: bool,
    pub quality_metrics: PatternExtractionQualityMetrics,
    pub diagnostics: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct RealProviderReadinessSummary {
    pub provider_name: String,
    pub provider_version: String,
    pub requested_model: String,
    pub resolved_model: String,
    pub design_case_count: usize,
    pub attempted_design_cases: usize,
    pub completed_design_cases: usize,
    pub strict_parser_acceptance_rate: f64,
    pub contract_validity: f64,
    pub evidence_attribution_accuracy: f64,
    pub scope_preservation: f64,
    pub counterexample_retention: f64,
    pub unsupported_claim_rate: f64,
    pub abstraction_distance: f64,
    pub design_reference_token_recall: f64,
    pub cases_with_quality_diagnostics: usize,
    pub unsupported_claim_review_threshold: f64,
    pub unsupported_claim_requires_review: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct RealProviderReadinessGuards {
    pub frozen_prompt_reused: bool,
    pub frozen_parser_reused: bool,
    pub frozen_scorer_reused: bool,
    pub frozen_design_dataset_reused: bool,
    pub authenticated_preflight_completed: bool,
    pub all_design_requests_attempted_once: bool,
    pub all_design_outputs_strictly_parsed: bool,
    pub all_candidates_contract_valid: bool,
    pub automatic_output_repair: bool,
    pub selective_retry: bool,
    pub api_key_recorded: bool,
    pub raw_response_text_recorded: bool,
    pub design_cases_only: bool,
    pub held_out_cases_untouched: bool,
    pub provider_ready: bool,
    pub candidate_learning_authorized: bool,
    pub pattern_persistence_authorized: bool,
    pub knowledge_promotion_authorized: bool,
    pub transfer_value_claimed: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Phase7RealProviderReadinessDecision {
    ProviderReadyCandidatesRequireQualityReview,
    ProviderReadyCandidatesRemainProposed,
    ProviderReadinessInvalid,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7RealProviderReadinessReport {
    pub schema_version: u32,
    pub evaluation_version: String,
    pub tag: String,
    pub generated_at: String,
    pub phase: String,
    pub purpose: String,
    pub preflight: ProviderReadinessPreflight,
    pub artifact_hashes: ReadinessArtifactHashes,
    pub parser_policy: StrictParserPolicy,
    pub scorer_policy: ExtractionScorerPolicy,
    pub summary: RealProviderReadinessSummary,
    pub cases: Vec<RealProviderCaseReadiness>,
    pub guards: RealProviderReadinessGuards,
    pub decision: Phase7RealProviderReadinessDecision,
    pub conclusion: String,
}

pub struct Phase7RealProviderReadinessEvaluator;

impl Phase7RealProviderReadinessEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase7RealProviderReadinessReport> {
        evaluate(tag.into())
    }
}

pub fn load_phase7_real_provider_execution() -> Result<ModelProviderExecutionArtifact> {
    serde_json::from_str(EXECUTION_JSON).context("parse Phase 7.2.3 real provider execution")
}

fn evaluate(tag: String) -> Result<Phase7RealProviderReadinessReport> {
    let execution = load_phase7_real_provider_execution()?;
    let preflight: ProviderReadinessPreflight =
        serde_json::from_str(PREFLIGHT_JSON).context("parse Phase 7.2.3 sanitized preflight")?;
    let parser_policy: StrictParserPolicy =
        serde_json::from_str(PARSER_POLICY_JSON).context("parse frozen strict parser policy")?;
    let scorer_policy: ExtractionScorerPolicy =
        serde_json::from_str(SCORER_POLICY_JSON).context("parse frozen scorer policy")?;
    let manifests = load_phase7_provider_manifests()?;
    let model_manifest = manifests
        .providers
        .iter()
        .find(|provider| provider.provider_name == execution.provider_name)
        .context("real provider is absent from frozen provider manifests")?;
    let dataset = load_phase7_pattern_extraction_design()?;

    let prompt_sha256 = sha256(PROMPT_TEXT.as_bytes());
    let parser_sha256 = sha256(PARSER_POLICY_JSON.as_bytes());
    let scorer_sha256 = sha256(SCORER_POLICY_JSON.as_bytes());
    let dataset_sha256 = sha256(DESIGN_DATASET_JSON.as_bytes());
    let execution_sha256 = sha256(EXECUTION_JSON.as_bytes());
    let frozen_protocol_matches_manifest = prompt_sha256 == manifests.prompt_sha256
        && parser_sha256 == manifests.parser_sha256
        && scorer_sha256 == manifests.scorer_sha256
        && dataset_sha256 == manifests.dataset_sha256;
    let execution_matches_frozen_protocol = prompt_sha256 == execution.prompt_sha256
        && parser_sha256 == execution.parser_sha256
        && scorer_sha256 == execution.scorer_sha256
        && dataset_sha256 == execution.dataset_sha256
        && model_manifest.model.as_deref() == Some(execution.model_requested.as_str())
        && model_manifest.prompt_sha256.as_deref() == Some(prompt_sha256.as_str())
        && model_manifest.parser_sha256.as_deref() == Some(parser_sha256.as_str());
    let artifact_hashes = ReadinessArtifactHashes {
        prompt_sha256,
        parser_sha256,
        scorer_sha256,
        dataset_sha256,
        execution_sha256,
        frozen_protocol_matches_manifest,
        execution_matches_frozen_protocol,
    };

    let expected_ids = dataset
        .cases
        .iter()
        .map(|case| case.id.as_str())
        .collect::<BTreeSet<_>>();
    let output_ids = execution
        .outputs
        .iter()
        .map(|output| output.case_id.as_str())
        .collect::<BTreeSet<_>>();

    let mut cases = Vec::with_capacity(dataset.cases.len());
    for case in &dataset.cases {
        let output = execution
            .outputs
            .iter()
            .find(|output| output.case_id == case.id)
            .with_context(|| format!("missing real provider output for {}", case.id))?;
        let validation =
            validate_pattern_extraction_batch(&case.input, std::slice::from_ref(&output.candidate));
        let metrics = evaluate_pattern_extraction_quality(
            &case.input,
            &output.candidate,
            &case.reference_candidate,
        );
        cases.push(RealProviderCaseReadiness {
            case_id: case.id.clone(),
            response_sha256: output.response_sha256.clone(),
            contract_valid: validation.valid,
            diagnostics: diagnostics(&metrics),
            quality_metrics: metrics,
        });
    }

    let count = cases.len();
    let contract_valid_count = cases.iter().filter(|case| case.contract_valid).count();
    let cases_with_quality_diagnostics = cases
        .iter()
        .filter(|case| {
            !case
                .diagnostics
                .iter()
                .any(|item| item == "no_deterministic_quality_warning")
        })
        .count();
    let unsupported_claim_rate = mean(
        cases
            .iter()
            .map(|case| case.quality_metrics.unsupported_claim_rate),
    );
    let scope_preservation = mean(
        cases
            .iter()
            .map(|case| case.quality_metrics.scope_retention),
    );
    let summary = RealProviderReadinessSummary {
        provider_name: execution.provider_name.clone(),
        provider_version: execution.provider_version.clone(),
        requested_model: execution.model_requested.clone(),
        resolved_model: execution.resolved_model.clone().unwrap_or_default(),
        design_case_count: execution.design_case_count,
        attempted_design_cases: execution.attempted_design_cases,
        completed_design_cases: execution.completed_design_cases,
        strict_parser_acceptance_rate: fraction(
            execution.outputs.len(),
            execution.design_case_count,
        ),
        contract_validity: fraction(contract_valid_count, count),
        evidence_attribution_accuracy: mean(
            cases
                .iter()
                .map(|case| case.quality_metrics.evidence_attribution_accuracy),
        ),
        scope_preservation,
        counterexample_retention: mean(
            cases
                .iter()
                .map(|case| case.quality_metrics.counterexample_handling),
        ),
        unsupported_claim_rate,
        abstraction_distance: mean(
            cases
                .iter()
                .map(|case| case.quality_metrics.abstraction_distance_score),
        ),
        design_reference_token_recall: mean(
            cases
                .iter()
                .map(|case| case.quality_metrics.design_reference_token_recall),
        ),
        cases_with_quality_diagnostics,
        unsupported_claim_review_threshold: UNSUPPORTED_CLAIM_REVIEW_THRESHOLD,
        unsupported_claim_requires_review: unsupported_claim_rate
            > UNSUPPORTED_CLAIM_REVIEW_THRESHOLD,
    };

    let authenticated_preflight_completed = preflight.models_endpoint_http_status == 200
        && preflight.chat_completion_http_status == 200
        && preflight.authentication_status == "authenticated"
        && preflight.resolved_model == execution.resolved_model.clone().unwrap_or_default()
        && !preflight.api_key_recorded
        && !preflight.raw_response_text_recorded;
    let all_design_requests_attempted_once = execution.attempted_design_cases == count
        && execution.completed_design_cases == count
        && execution.outputs.len() == count
        && execution.status == "completed"
        && execution.blocker.is_none();
    let all_design_outputs_strictly_parsed =
        execution.outputs.len() == count && expected_ids == output_ids && output_ids.len() == count;
    let all_candidates_contract_valid = contract_valid_count == count;
    let provider_ready = artifact_hashes.frozen_protocol_matches_manifest
        && artifact_hashes.execution_matches_frozen_protocol
        && authenticated_preflight_completed
        && all_design_requests_attempted_once
        && all_design_outputs_strictly_parsed
        && all_candidates_contract_valid
        && !parser_policy.automatic_repair
        && !parser_policy.retry_on_parse_error
        && !execution.api_key_recorded
        && !execution.raw_response_text_recorded
        && !preflight.held_out_cases_accessed;
    let guards = RealProviderReadinessGuards {
        frozen_prompt_reused: artifact_hashes.frozen_protocol_matches_manifest,
        frozen_parser_reused: artifact_hashes.frozen_protocol_matches_manifest,
        frozen_scorer_reused: artifact_hashes.frozen_protocol_matches_manifest,
        frozen_design_dataset_reused: artifact_hashes.frozen_protocol_matches_manifest,
        authenticated_preflight_completed,
        all_design_requests_attempted_once,
        all_design_outputs_strictly_parsed,
        all_candidates_contract_valid,
        automatic_output_repair: false,
        selective_retry: false,
        api_key_recorded: execution.api_key_recorded,
        raw_response_text_recorded: execution.raw_response_text_recorded,
        design_cases_only: true,
        held_out_cases_untouched: !preflight.held_out_cases_accessed && expected_ids == output_ids,
        provider_ready,
        candidate_learning_authorized: false,
        pattern_persistence_authorized: false,
        knowledge_promotion_authorized: false,
        transfer_value_claimed: false,
        runtime_authorized: false,
        hermes_authorized: false,
    };
    let decision = if !provider_ready {
        Phase7RealProviderReadinessDecision::ProviderReadinessInvalid
    } else if summary.unsupported_claim_requires_review || summary.scope_preservation < 1.0 {
        Phase7RealProviderReadinessDecision::ProviderReadyCandidatesRequireQualityReview
    } else {
        Phase7RealProviderReadinessDecision::ProviderReadyCandidatesRemainProposed
    };

    Ok(Phase7RealProviderReadinessReport {
        schema_version: 1,
        evaluation_version: EVALUATION_VERSION.to_string(),
        tag,
        generated_at: Utc::now().to_rfc3339(),
        phase: "Phase 7.2.3 Real Provider Readiness Validation".to_string(),
        purpose: "Determine whether one real provider can reliably produce evaluable Pattern Candidates under the frozen design-only protocol; do not establish knowledge or transfer value.".to_string(),
        preflight,
        artifact_hashes,
        parser_policy,
        scorer_policy,
        summary,
        cases,
        guards,
        decision,
        conclusion: "DeepSeek completed all ten frozen design-only extractions with strict parsing and contract validity, so provider readiness is established. Candidate learning remains unauthorized because extraction quality is diagnostic-only and unsupported abstraction requires review; held-out transfer evaluation, persistence, knowledge promotion, Hermes, and runtime remain closed.".to_string(),
    })
}

fn diagnostics(metrics: &PatternExtractionQualityMetrics) -> Vec<String> {
    let mut diagnostics = Vec::new();
    if metrics.pattern_completeness < 1.0 {
        diagnostics.push("pattern_incomplete".to_string());
    }
    if metrics.evidence_attribution_accuracy < 1.0 {
        diagnostics.push("evidence_attribution_error".to_string());
    }
    if metrics.scope_retention < 1.0 {
        diagnostics.push("scope_boundary_loss".to_string());
    }
    if metrics.counterexample_handling < 1.0 {
        diagnostics.push("counterexample_not_preserved".to_string());
    }
    if metrics.abstraction_distance_score < 0.35 {
        diagnostics.push("abstraction_distance_outside_preferred_band".to_string());
    }
    if metrics.design_reference_token_recall < 0.20 {
        diagnostics.push("low_design_reference_alignment_not_a_rejection_gate".to_string());
    }
    if metrics.unsupported_claim_rate > UNSUPPORTED_CLAIM_REVIEW_THRESHOLD {
        diagnostics.push("unsupported_language_requires_review".to_string());
    }
    if diagnostics.is_empty() {
        diagnostics.push("no_deterministic_quality_warning".to_string());
    }
    diagnostics
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

fn mean(values: impl Iterator<Item = f64>) -> f64 {
    let values = values.collect::<Vec<_>>();
    if values.is_empty() {
        0.0
    } else {
        values.iter().sum::<f64>() / values.len() as f64
    }
}
