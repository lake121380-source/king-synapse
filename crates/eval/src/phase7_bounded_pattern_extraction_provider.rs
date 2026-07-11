use crate::phase7_cognitive_architecture_contract::{
    EvidenceReference, FalsificationCondition, PatternCandidate, PatternCondition,
    PatternPrediction, PatternStatus,
};
use crate::phase7_pattern_extraction_protocol::{
    load_phase7_pattern_extraction_design, validate_pattern_extraction_batch,
    PatternExtractionBatchValidation, PatternExtractionInput, PatternExtractionProvider,
};
use anyhow::{bail, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

const EVALUATION_VERSION: &str = "phase7.2.1-bounded-pattern-extraction-provider-v1";
const PROVIDER_ID: &str = "deterministic_bounded_pattern_extractor_v0";
const PROMPT_OR_RULESET_ID: &str = "deterministic_ruleset_v0_no_model_prompt";
const OUTPUT_REPAIR_POLICY: &str = "reject_only_no_automatic_repair";
const MAX_CONFIDENCE: f64 = 0.60;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct BoundedPatternExtractionProviderConfig {
    pub provider_id: String,
    pub provider_kind: String,
    pub model_id: Option<String>,
    pub prompt_or_ruleset_id: String,
    pub design_cases_only: bool,
    pub max_candidates_per_case: usize,
    pub max_confidence: f64,
    pub output_repair_policy: String,
    pub deterministic: bool,
    pub held_out_access: bool,
    pub persistence_authorized: bool,
    pub runtime_authorized: bool,
}

impl BoundedPatternExtractionProviderConfig {
    pub fn frozen_v0() -> Self {
        Self {
            provider_id: PROVIDER_ID.to_string(),
            provider_kind: "deterministic_transparent_weak_baseline".to_string(),
            model_id: None,
            prompt_or_ruleset_id: PROMPT_OR_RULESET_ID.to_string(),
            design_cases_only: true,
            max_candidates_per_case: 1,
            max_confidence: MAX_CONFIDENCE,
            output_repair_policy: OUTPUT_REPAIR_POLICY.to_string(),
            deterministic: true,
            held_out_access: false,
            persistence_authorized: false,
            runtime_authorized: false,
        }
    }
}

#[derive(Clone, Debug)]
pub struct DeterministicBoundedPatternExtractionProvider {
    config: BoundedPatternExtractionProviderConfig,
}

impl Default for DeterministicBoundedPatternExtractionProvider {
    fn default() -> Self {
        Self::new()
    }
}

impl DeterministicBoundedPatternExtractionProvider {
    pub fn new() -> Self {
        Self {
            config: BoundedPatternExtractionProviderConfig::frozen_v0(),
        }
    }

    pub fn config(&self) -> &BoundedPatternExtractionProviderConfig {
        &self.config
    }
}

impl PatternExtractionProvider for DeterministicBoundedPatternExtractionProvider {
    fn provider_id(&self) -> &str {
        &self.config.provider_id
    }

    fn extract(&self, input: &PatternExtractionInput) -> Result<Vec<PatternCandidate>> {
        if input.max_pattern_candidates != self.config.max_candidates_per_case {
            bail!("provider_requires_exactly_one_candidate_slot");
        }

        let supporting = input
            .experiences
            .iter()
            .filter(|experience| !experience.counterexample)
            .collect::<Vec<_>>();
        let counterexamples = input
            .experiences
            .iter()
            .filter(|experience| experience.counterexample)
            .collect::<Vec<_>>();
        if supporting.len() < 2 {
            bail!("provider_requires_two_supporting_experiences");
        }
        if counterexamples.is_empty() {
            bail!("provider_requires_supplied_counterexample");
        }

        let recurring_terms = recurring_grounded_terms(input, 4);
        let proposition = format!(
            "Within {}, recurring evidence involving {} is associated with observed outcomes; the supplied counterexample bounds the claim.",
            input.source_domain,
            recurring_terms.join(", ")
        );

        let supporting_evidence = supporting
            .iter()
            .map(|experience| evidence_reference(experience))
            .collect::<Vec<_>>();
        let counterexample_evidence = counterexamples
            .iter()
            .map(|experience| evidence_reference(experience))
            .collect::<Vec<_>>();

        let applicability_conditions = vec![
            PatternCondition {
                field: "source_domain".to_string(),
                operator: "equals".to_string(),
                value: input.source_domain.clone(),
            },
            PatternCondition {
                field: "independent_supporting_experiences".to_string(),
                operator: "greater_than_or_equal".to_string(),
                value: supporting.len().to_string(),
            },
            PatternCondition {
                field: "outcomes".to_string(),
                operator: "requires".to_string(),
                value: "observable".to_string(),
            },
        ];
        let exclusion_conditions = counterexamples
            .iter()
            .map(|experience| PatternCondition {
                field: format!("counterexample.{}", experience.memory_id),
                operator: "excludes".to_string(),
                value: format!(
                    "{} Outcome: {}",
                    experience.action_or_observation, experience.outcome
                ),
            })
            .collect::<Vec<_>>();

        let first_support = supporting[0];
        let first_counterexample = counterexamples[0];
        let candidate = PatternCandidate {
            id: format!("pattern_candidate.{}.deterministic_v0", input.case_id),
            proposition,
            supporting_evidence,
            counterexamples: counterexample_evidence,
            counterexample_search_performed: true,
            applicability_conditions,
            exclusion_conditions,
            source_domains: vec![input.source_domain.clone()],
            predictions: vec![PatternPrediction {
                statement: format!(
                    "For a future in-scope {} case, the bounded pattern predicts an outcome consistent with the supplied evidence.",
                    input.source_domain
                ),
                observable: first_support.outcome.clone(),
                success_criterion: "observed outcome is more consistent with supporting evidence than the supplied counterexample".to_string(),
            }],
            falsification_conditions: vec![FalsificationCondition {
                statement: "Reject or narrow the candidate when repeated comparable outcomes match the supplied counterexample rather than the supporting evidence.".to_string(),
                observable: first_counterexample.outcome.clone(),
            }],
            validation_outcome_ids: Vec::new(),
            confidence: MAX_CONFIDENCE,
            status: PatternStatus::Proposed,
        };
        Ok(vec![candidate])
    }
}

fn evidence_reference(
    experience: &crate::phase7_pattern_extraction_protocol::ExtractionExperience,
) -> EvidenceReference {
    EvidenceReference {
        memory_id: experience.memory_id.clone(),
        experience_id: experience.experience_id.clone(),
        domain: experience.domain.clone(),
        independent_source: experience.independent_source,
        observed_outcome: experience.outcome_observed,
    }
}

fn recurring_grounded_terms(input: &PatternExtractionInput, limit: usize) -> Vec<String> {
    let stopwords = stopwords();
    let mut counts = BTreeMap::<String, usize>::new();
    for experience in input
        .experiences
        .iter()
        .filter(|experience| !experience.counterexample)
    {
        let text = format!(
            "{} {} {}",
            experience.context, experience.action_or_observation, experience.outcome
        );
        for token in tokenize(&text) {
            if token.len() >= 5 && !stopwords.contains(token.as_str()) {
                *counts.entry(token).or_default() += 1;
            }
        }
    }
    let mut ranked = counts.into_iter().collect::<Vec<_>>();
    ranked.sort_by(|(left_token, left_count), (right_token, right_count)| {
        right_count
            .cmp(left_count)
            .then_with(|| left_token.cmp(right_token))
    });
    let mut terms = ranked
        .into_iter()
        .take(limit)
        .map(|(token, _)| token)
        .collect::<Vec<_>>();
    if terms.is_empty() {
        terms.push(input.source_domain.replace('_', " "));
    }
    terms
}

fn stopwords() -> BTreeSet<&'static str> {
    [
        "about",
        "after",
        "again",
        "against",
        "before",
        "being",
        "between",
        "could",
        "during",
        "their",
        "there",
        "these",
        "those",
        "through",
        "under",
        "until",
        "where",
        "which",
        "while",
        "would",
        "without",
        "added",
        "found",
        "remained",
        "result",
        "outcome",
        "observed",
        "evidence",
        "supporting",
        "future",
    ]
    .into_iter()
    .collect()
}

fn tokenize(text: &str) -> Vec<String> {
    text.split(|character: char| !character.is_alphanumeric())
        .filter(|token| !token.is_empty())
        .map(|token| token.to_ascii_lowercase())
        .collect()
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct PatternExtractionQualityMetrics {
    pub pattern_completeness: f64,
    pub evidence_attribution_accuracy: f64,
    pub evidence_coverage: f64,
    pub scope_retention: f64,
    pub counterexample_handling: f64,
    pub abstraction_distance_score: f64,
    pub design_reference_token_recall: f64,
    pub unsupported_claim_rate: f64,
    pub compression_ratio: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ProviderOutputDisposition {
    AcceptedContractOnly,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct PatternExtractionProviderCaseReport {
    pub case_id: String,
    pub source_transfer_scenario_id: String,
    pub provider_id: String,
    pub candidate_count: usize,
    pub validation: PatternExtractionBatchValidation,
    pub disposition: ProviderOutputDisposition,
    pub quality_metrics: Option<PatternExtractionQualityMetrics>,
    pub diagnostics: Vec<String>,
    pub candidates: Vec<PatternCandidate>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderFaultInjectionReport {
    pub name: String,
    pub rejected: bool,
    pub observed_violations: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct PatternExtractionProviderSummary {
    pub design_case_count: usize,
    pub provider_executions: usize,
    pub candidates_produced: usize,
    pub contract_accepted_cases: usize,
    pub contract_rejected_cases: usize,
    pub cases_with_quality_diagnostics: usize,
    pub mean_pattern_completeness: f64,
    pub mean_evidence_attribution_accuracy: f64,
    pub mean_scope_retention: f64,
    pub mean_counterexample_handling: f64,
    pub mean_abstraction_distance_score: f64,
    pub mean_design_reference_token_recall: f64,
    pub mean_unsupported_claim_rate: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BoundedPatternExtractionGuards {
    pub eval_only: bool,
    pub design_cases_only: bool,
    pub held_out_cases_untouched: bool,
    pub provider_config_frozen: bool,
    pub deterministic_provider: bool,
    pub automatic_output_repair: bool,
    pub pattern_persistence_authorized: bool,
    pub knowledge_promotion_authorized: bool,
    pub transfer_value_claimed: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Phase7BoundedPatternExtractionDecision {
    ProviderFrozenDesignEvaluationOnly,
    ProviderProtocolInvalid,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7BoundedPatternExtractionReport {
    pub schema_version: u32,
    pub evaluation_version: String,
    pub tag: String,
    pub generated_at: String,
    pub phase: String,
    pub provider_config: BoundedPatternExtractionProviderConfig,
    pub summary: PatternExtractionProviderSummary,
    pub cases: Vec<PatternExtractionProviderCaseReport>,
    pub fault_injections: Vec<ProviderFaultInjectionReport>,
    pub guards: BoundedPatternExtractionGuards,
    pub decision: Phase7BoundedPatternExtractionDecision,
    pub conclusion: String,
}

pub struct Phase7BoundedPatternExtractionEvaluator;

impl Phase7BoundedPatternExtractionEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase7BoundedPatternExtractionReport> {
        let provider = DeterministicBoundedPatternExtractionProvider::new();
        evaluate_provider(tag.into(), &provider, provider.config().clone())
    }
}

pub fn evaluate_provider(
    tag: String,
    provider: &dyn PatternExtractionProvider,
    provider_config: BoundedPatternExtractionProviderConfig,
) -> Result<Phase7BoundedPatternExtractionReport> {
    if provider.provider_id() != provider_config.provider_id {
        bail!("provider_id_does_not_match_frozen_configuration");
    }
    let dataset = load_phase7_pattern_extraction_design()?;
    let mut cases = Vec::new();
    for case in &dataset.cases {
        let candidates = provider.extract(&case.input)?;
        let validation = validate_pattern_extraction_batch(&case.input, &candidates);
        let quality_metrics = candidates
            .first()
            .map(|candidate| quality_metrics(&case.input, candidate, &case.reference_candidate));
        let diagnostics = quality_metrics
            .as_ref()
            .map(quality_diagnostics)
            .unwrap_or_else(|| vec!["provider_returned_no_candidate".to_string()]);
        let disposition = if validation.valid {
            ProviderOutputDisposition::AcceptedContractOnly
        } else {
            ProviderOutputDisposition::Rejected
        };
        cases.push(PatternExtractionProviderCaseReport {
            case_id: case.id.clone(),
            source_transfer_scenario_id: case.source_transfer_scenario_id.clone(),
            provider_id: provider.provider_id().to_string(),
            candidate_count: candidates.len(),
            validation,
            disposition,
            quality_metrics,
            diagnostics,
            candidates,
        });
    }

    let fault_injections =
        fault_injection_reports(&dataset.cases[0].input, &cases[0].candidates[0]);
    let summary = summarize_provider_cases(&cases);
    let guards = BoundedPatternExtractionGuards {
        eval_only: true,
        design_cases_only: true,
        held_out_cases_untouched: true,
        provider_config_frozen: true,
        deterministic_provider: true,
        automatic_output_repair: false,
        pattern_persistence_authorized: false,
        knowledge_promotion_authorized: false,
        transfer_value_claimed: false,
        runtime_authorized: false,
        hermes_authorized: false,
    };
    let valid = summary.provider_executions == 10
        && summary.candidates_produced == 10
        && summary.contract_accepted_cases == 10
        && fault_injections.iter().all(|fault| fault.rejected)
        && guards.held_out_cases_untouched
        && !guards.pattern_persistence_authorized
        && !guards.runtime_authorized;
    let decision = if valid {
        Phase7BoundedPatternExtractionDecision::ProviderFrozenDesignEvaluationOnly
    } else {
        Phase7BoundedPatternExtractionDecision::ProviderProtocolInvalid
    };

    Ok(Phase7BoundedPatternExtractionReport {
        schema_version: 1,
        evaluation_version: EVALUATION_VERSION.to_string(),
        tag,
        generated_at: Utc::now().to_rfc3339(),
        phase: "Phase 7.2.1 Bounded Pattern Extraction Provider".to_string(),
        provider_config,
        summary,
        cases,
        fault_injections,
        guards,
        decision,
        conclusion: "The frozen deterministic weak-baseline provider can produce structurally bounded Pattern Candidates from the ten design inputs, and invalid provider outputs receive explicit rejection reasons. Contract acceptance is not semantic validation, transfer evidence, knowledge promotion, persistence, or runtime authority.".to_string(),
    })
}

fn quality_metrics(
    input: &PatternExtractionInput,
    candidate: &PatternCandidate,
    reference: &PatternCandidate,
) -> PatternExtractionQualityMetrics {
    let completeness_checks = [
        !candidate.id.trim().is_empty(),
        !candidate.proposition.trim().is_empty(),
        !candidate.supporting_evidence.is_empty(),
        !candidate.counterexamples.is_empty(),
        candidate.counterexample_search_performed,
        !candidate.applicability_conditions.is_empty(),
        !candidate.exclusion_conditions.is_empty(),
        !candidate.source_domains.is_empty(),
        !candidate.predictions.is_empty(),
        !candidate.falsification_conditions.is_empty(),
        candidate.validation_outcome_ids.is_empty(),
        candidate.status == PatternStatus::Proposed,
    ];
    let pattern_completeness = fraction(
        completeness_checks.iter().filter(|value| **value).count(),
        completeness_checks.len(),
    );

    let authoritative = input
        .experiences
        .iter()
        .map(|experience| (experience.memory_id.as_str(), experience))
        .collect::<BTreeMap<_, _>>();
    let cited = candidate
        .supporting_evidence
        .iter()
        .chain(candidate.counterexamples.iter())
        .collect::<Vec<_>>();
    let accurate = cited
        .iter()
        .filter(|evidence| {
            authoritative
                .get(evidence.memory_id.as_str())
                .is_some_and(|source| {
                    source.experience_id == evidence.experience_id
                        && source.domain == evidence.domain
                        && source.independent_source == evidence.independent_source
                        && source.outcome_observed == evidence.observed_outcome
                })
        })
        .count();
    let evidence_attribution_accuracy = fraction(accurate, cited.len());

    let support_ids = input
        .experiences
        .iter()
        .filter(|experience| !experience.counterexample)
        .map(|experience| experience.memory_id.as_str())
        .collect::<BTreeSet<_>>();
    let cited_support = candidate
        .supporting_evidence
        .iter()
        .filter(|evidence| support_ids.contains(evidence.memory_id.as_str()))
        .count();
    let evidence_coverage = fraction(cited_support, support_ids.len());

    let domain_retained = candidate.applicability_conditions.iter().any(|condition| {
        condition.value == input.source_domain || condition.value.contains(&input.source_domain)
    });
    let exclusions_retained =
        candidate.exclusion_conditions.len() >= input.supplied_counterexample_ids.len();
    let scope_retention = fraction(domain_retained as usize + exclusions_retained as usize, 2);

    let counterexample_ids = candidate
        .counterexamples
        .iter()
        .map(|evidence| evidence.memory_id.as_str())
        .collect::<BTreeSet<_>>();
    let handled = input
        .supplied_counterexample_ids
        .iter()
        .filter(|id| counterexample_ids.contains(id.as_str()))
        .count();
    let counterexample_handling = fraction(handled, input.supplied_counterexample_ids.len());

    let proposition_tokens = content_tokens(&candidate.proposition);
    let individual_copy_overlap = input
        .experiences
        .iter()
        .map(|experience| {
            let source = format!(
                "{} {} {}",
                experience.context, experience.action_or_observation, experience.outcome
            );
            jaccard(&proposition_tokens, &content_tokens(&source))
        })
        .fold(0.0_f64, f64::max);
    let abstraction_distance_score =
        (1.0 - ((individual_copy_overlap - 0.35).abs() / 0.35)).clamp(0.0, 1.0);

    let reference_tokens = content_tokens(&reference.proposition);
    let design_reference_token_recall = fraction(
        proposition_tokens.intersection(&reference_tokens).count(),
        reference_tokens.len(),
    );

    let input_text = input
        .experiences
        .iter()
        .map(|experience| {
            format!(
                "{} {} {} {}",
                experience.domain,
                experience.context,
                experience.action_or_observation,
                experience.outcome
            )
        })
        .collect::<Vec<_>>()
        .join(" ");
    let input_tokens = content_tokens(&input_text);
    let provider_scaffolding = content_tokens(
        "within recurring evidence involving associated observed outcomes supplied counterexample bounds claim",
    );
    let unsupported = proposition_tokens
        .iter()
        .filter(|token| !input_tokens.contains(*token) && !provider_scaffolding.contains(*token))
        .count();
    let unsupported_claim_rate = fraction(unsupported, proposition_tokens.len());

    let input_word_count = tokenize(&input_text).len();
    let candidate_word_count =
        tokenize(&serde_json::to_string(candidate).unwrap_or_default()).len();
    let compression_ratio = if candidate_word_count == 0 {
        0.0
    } else {
        input_word_count as f64 / candidate_word_count as f64
    };

    PatternExtractionQualityMetrics {
        pattern_completeness,
        evidence_attribution_accuracy,
        evidence_coverage,
        scope_retention,
        counterexample_handling,
        abstraction_distance_score,
        design_reference_token_recall,
        unsupported_claim_rate,
        compression_ratio,
    }
}

fn quality_diagnostics(metrics: &PatternExtractionQualityMetrics) -> Vec<String> {
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
    if metrics.unsupported_claim_rate > 0.20 {
        diagnostics.push("unsupported_language_requires_review".to_string());
    }
    if diagnostics.is_empty() {
        diagnostics.push("no_deterministic_quality_warning".to_string());
    }
    diagnostics
}

fn fault_injection_reports(
    input: &PatternExtractionInput,
    valid: &PatternCandidate,
) -> Vec<ProviderFaultInjectionReport> {
    let mut hallucinated = valid.clone();
    hallucinated.supporting_evidence[0].memory_id = "fabricated_memory".to_string();

    let mut omitted_counterexample = valid.clone();
    omitted_counterexample.counterexamples.clear();

    let mut premature_active = valid.clone();
    premature_active.status = PatternStatus::Active;

    let mut fabricated_validation = valid.clone();
    fabricated_validation
        .validation_outcome_ids
        .push("fabricated_outcome".to_string());

    let cases = vec![
        ("hallucinated_evidence", vec![hallucinated]),
        ("omitted_counterexample", vec![omitted_counterexample]),
        ("premature_active", vec![premature_active]),
        ("fabricated_validation", vec![fabricated_validation]),
        (
            "candidate_limit_exceeded",
            vec![valid.clone(), valid.clone()],
        ),
        ("empty_provider_output", Vec::new()),
    ];
    cases
        .into_iter()
        .map(|(name, candidates)| {
            let validation = validate_pattern_extraction_batch(input, &candidates);
            let mut observed_violations = validation.violations;
            for candidate in validation.candidate_validations {
                observed_violations.extend(candidate.violations);
            }
            observed_violations.sort();
            observed_violations.dedup();
            ProviderFaultInjectionReport {
                name: name.to_string(),
                rejected: !validation.valid,
                observed_violations,
            }
        })
        .collect()
}

fn summarize_provider_cases(
    cases: &[PatternExtractionProviderCaseReport],
) -> PatternExtractionProviderSummary {
    let metrics = cases
        .iter()
        .filter_map(|case| case.quality_metrics.as_ref())
        .collect::<Vec<_>>();
    PatternExtractionProviderSummary {
        design_case_count: cases.len(),
        provider_executions: cases.len(),
        candidates_produced: cases.iter().map(|case| case.candidate_count).sum(),
        contract_accepted_cases: cases.iter().filter(|case| case.validation.valid).count(),
        contract_rejected_cases: cases.iter().filter(|case| !case.validation.valid).count(),
        cases_with_quality_diagnostics: cases
            .iter()
            .filter(|case| {
                case.diagnostics
                    .iter()
                    .any(|diagnostic| diagnostic != "no_deterministic_quality_warning")
            })
            .count(),
        mean_pattern_completeness: mean(metrics.iter().map(|item| item.pattern_completeness)),
        mean_evidence_attribution_accuracy: mean(
            metrics
                .iter()
                .map(|item| item.evidence_attribution_accuracy),
        ),
        mean_scope_retention: mean(metrics.iter().map(|item| item.scope_retention)),
        mean_counterexample_handling: mean(metrics.iter().map(|item| item.counterexample_handling)),
        mean_abstraction_distance_score: mean(
            metrics.iter().map(|item| item.abstraction_distance_score),
        ),
        mean_design_reference_token_recall: mean(
            metrics
                .iter()
                .map(|item| item.design_reference_token_recall),
        ),
        mean_unsupported_claim_rate: mean(metrics.iter().map(|item| item.unsupported_claim_rate)),
    }
}

fn content_tokens(text: &str) -> BTreeSet<String> {
    let stopwords = stopwords();
    tokenize(text)
        .into_iter()
        .filter(|token| token.len() >= 4 && !stopwords.contains(token.as_str()))
        .collect()
}

fn jaccard(left: &BTreeSet<String>, right: &BTreeSet<String>) -> f64 {
    let union = left.union(right).count();
    fraction(left.intersection(right).count(), union)
}

fn fraction(numerator: usize, denominator: usize) -> f64 {
    if denominator == 0 {
        1.0
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
