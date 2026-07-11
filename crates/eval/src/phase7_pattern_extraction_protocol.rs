use crate::phase7_cognitive_architecture_contract::{
    validate_pattern_candidate, PatternCandidate, PatternContractValidation, PatternStatus,
};
use anyhow::{Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

const DATASET_JSON: &str =
    include_str!("../datasets/pattern_extraction/phase7_2_pattern_extraction_design.json");
const EVALUATION_VERSION: &str = "phase7.2-pattern-extraction-protocol-v1";
const MAX_PROPOSED_CONFIDENCE: f64 = 0.75;

pub trait PatternExtractionProvider {
    fn provider_id(&self) -> &str;
    fn extract(&self, input: &PatternExtractionInput) -> Result<Vec<PatternCandidate>>;
}

pub struct Phase7PatternExtractionProtocolEvaluator;

impl Phase7PatternExtractionProtocolEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase7PatternExtractionReport> {
        evaluate(tag.into())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct PatternExtractionDataset {
    pub schema_version: u32,
    pub dataset_id: String,
    pub source_protocol: String,
    pub description: String,
    pub cases: Vec<PatternExtractionCase>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct PatternExtractionCase {
    pub id: String,
    pub source_transfer_scenario_id: String,
    pub input: PatternExtractionInput,
    pub reference_candidate: PatternCandidate,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PatternExtractionInput {
    pub case_id: String,
    pub source_domain: String,
    pub objective: String,
    pub experiences: Vec<ExtractionExperience>,
    pub supplied_counterexample_ids: Vec<String>,
    pub max_pattern_candidates: usize,
    pub prohibited_inputs: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExtractionExperience {
    pub memory_id: String,
    pub experience_id: String,
    pub domain: String,
    pub context: String,
    pub action_or_observation: String,
    pub outcome: String,
    pub constraints: Vec<String>,
    pub counterexample: bool,
    pub outcome_observed: bool,
    pub independent_source: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PatternExtractionMetricDefinition {
    pub name: String,
    pub direction: String,
    pub definition: String,
    pub requires_model_output: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PatternExtractionSubmissionValidation {
    pub candidate_id: String,
    pub valid: bool,
    pub base_contract: PatternContractValidation,
    pub violations: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PatternExtractionBatchValidation {
    pub case_id: String,
    pub valid: bool,
    pub candidate_validations: Vec<PatternExtractionSubmissionValidation>,
    pub violations: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PatternExtractionNegativeCase {
    pub name: String,
    pub rejected: bool,
    pub expected_violation: String,
    pub observed_violations: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct PatternExtractionDatasetSummary {
    pub case_count: usize,
    pub distinct_source_scenarios: usize,
    pub source_domain_count: usize,
    pub supporting_experience_count: usize,
    pub counterexample_count: usize,
    pub reference_candidates_valid: usize,
    pub held_out_references: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PatternExtractionProtocolGuards {
    pub eval_only: bool,
    pub design_cases_only: bool,
    pub target_problem_excluded: bool,
    pub expected_transfer_excluded: bool,
    pub held_out_cases_untouched: bool,
    pub max_one_candidate_per_case: bool,
    pub proposed_status_required: bool,
    pub proposed_confidence_capped: bool,
    pub extraction_algorithm_implemented: bool,
    pub model_evaluation_completed: bool,
    pub pattern_persistence_authorized: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
    pub autonomous_promotion_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Phase7PatternExtractionDecision {
    ProtocolFrozenExtractionAlgorithmBlocked,
    ProtocolInvalid,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7PatternExtractionReport {
    pub schema_version: u32,
    pub evaluation_version: String,
    pub tag: String,
    pub generated_at: String,
    pub phase: String,
    pub dataset: PatternExtractionDatasetSummary,
    pub metrics: Vec<PatternExtractionMetricDefinition>,
    pub reference_validations: Vec<PatternExtractionBatchValidation>,
    pub negative_cases: Vec<PatternExtractionNegativeCase>,
    pub all_reference_candidates_valid: bool,
    pub all_negative_cases_rejected: bool,
    pub guards: PatternExtractionProtocolGuards,
    pub decision: Phase7PatternExtractionDecision,
    pub conclusion: String,
}

pub fn load_phase7_pattern_extraction_design() -> Result<PatternExtractionDataset> {
    serde_json::from_str(DATASET_JSON).context("parse Phase 7.2 pattern extraction design dataset")
}

pub fn validate_pattern_extraction_submission(
    input: &PatternExtractionInput,
    candidate: &PatternCandidate,
) -> PatternExtractionSubmissionValidation {
    let base_contract = validate_pattern_candidate(candidate);
    let mut violations = base_contract.violations.clone();
    let authoritative = input
        .experiences
        .iter()
        .map(|experience| (experience.memory_id.as_str(), experience))
        .collect::<BTreeMap<_, _>>();
    let supplied_counterexamples = input
        .supplied_counterexample_ids
        .iter()
        .map(|id| id.as_str())
        .collect::<BTreeSet<_>>();

    if candidate.status != PatternStatus::Proposed {
        violations.push("extraction_output_must_remain_proposed".to_string());
    }
    if candidate.confidence > MAX_PROPOSED_CONFIDENCE {
        violations.push("proposed_confidence_exceeds_phase7_2_cap".to_string());
    }
    if !candidate.validation_outcome_ids.is_empty() {
        violations.push("extraction_cannot_claim_validation_outcomes".to_string());
    }
    if !candidate.counterexample_search_performed {
        violations.push("counterexample_search_must_be_recorded".to_string());
    }
    if candidate.counterexamples.is_empty() {
        violations.push("supplied_counterexample_must_be_considered".to_string());
    }

    for evidence in candidate
        .supporting_evidence
        .iter()
        .chain(candidate.counterexamples.iter())
    {
        match authoritative.get(evidence.memory_id.as_str()) {
            None => violations.push("evidence_reference_not_in_extraction_input".to_string()),
            Some(source)
                if source.experience_id != evidence.experience_id
                    || source.domain != evidence.domain
                    || source.independent_source != evidence.independent_source
                    || source.outcome_observed != evidence.observed_outcome =>
            {
                violations.push("evidence_provenance_mismatch".to_string());
            }
            Some(_) => {}
        }
    }

    if candidate
        .counterexamples
        .iter()
        .any(|evidence| !supplied_counterexamples.contains(evidence.memory_id.as_str()))
    {
        violations.push("counterexample_not_from_supplied_counterevidence".to_string());
    }
    if supplied_counterexamples.iter().any(|id| {
        !candidate
            .counterexamples
            .iter()
            .any(|item| item.memory_id == *id)
    }) {
        violations.push("supplied_counterexample_omitted".to_string());
    }

    let input_domains = input
        .experiences
        .iter()
        .map(|experience| experience.domain.as_str())
        .collect::<BTreeSet<_>>();
    if candidate
        .source_domains
        .iter()
        .any(|domain| !input_domains.contains(domain.as_str()))
    {
        violations.push("source_domain_not_grounded_in_input".to_string());
    }

    violations.sort();
    violations.dedup();
    PatternExtractionSubmissionValidation {
        candidate_id: candidate.id.clone(),
        valid: violations.is_empty(),
        base_contract,
        violations,
    }
}

pub fn validate_pattern_extraction_batch(
    input: &PatternExtractionInput,
    candidates: &[PatternCandidate],
) -> PatternExtractionBatchValidation {
    let mut violations = Vec::new();
    if candidates.is_empty() {
        violations.push("at_least_one_pattern_candidate_required".to_string());
    }
    if candidates.len() > input.max_pattern_candidates {
        violations.push("pattern_candidate_limit_exceeded".to_string());
    }
    let candidate_validations = candidates
        .iter()
        .map(|candidate| validate_pattern_extraction_submission(input, candidate))
        .collect::<Vec<_>>();
    let valid = violations.is_empty() && candidate_validations.iter().all(|item| item.valid);
    PatternExtractionBatchValidation {
        case_id: input.case_id.clone(),
        valid,
        candidate_validations,
        violations,
    }
}

fn evaluate(tag: String) -> Result<Phase7PatternExtractionReport> {
    let dataset = load_phase7_pattern_extraction_design()?;
    let reference_validations = dataset
        .cases
        .iter()
        .map(|case| {
            validate_pattern_extraction_batch(
                &case.input,
                std::slice::from_ref(&case.reference_candidate),
            )
        })
        .collect::<Vec<_>>();
    let all_reference_candidates_valid = reference_validations.iter().all(|item| item.valid);
    let negative_cases = negative_contract_cases(&dataset.cases[0]);
    let all_negative_cases_rejected = negative_cases.iter().all(|item| item.rejected);
    let dataset_summary = summarize(&dataset, &reference_validations);
    let metrics = metric_definitions();

    let prohibited_inputs_present = dataset.cases.iter().all(|case| {
        [
            "target_problem",
            "expected_transfer",
            "held_out_cases",
            "runtime_state",
        ]
        .iter()
        .all(|field| {
            case.input
                .prohibited_inputs
                .iter()
                .any(|item| item == field)
        })
    });
    let design_ids = phase7_1_design_scenario_ids();
    let design_only = dataset
        .cases
        .iter()
        .all(|case| design_ids.contains(case.source_transfer_scenario_id.as_str()));
    let protocol_valid = dataset.schema_version == 1
        && dataset.cases.len() == 10
        && design_only
        && prohibited_inputs_present
        && all_reference_candidates_valid
        && all_negative_cases_rejected
        && metrics.len() >= 10;

    let guards = PatternExtractionProtocolGuards {
        eval_only: true,
        design_cases_only: design_only,
        target_problem_excluded: prohibited_inputs_present,
        expected_transfer_excluded: prohibited_inputs_present,
        held_out_cases_untouched: dataset_summary.held_out_references == 0,
        max_one_candidate_per_case: dataset
            .cases
            .iter()
            .all(|case| case.input.max_pattern_candidates == 1),
        proposed_status_required: true,
        proposed_confidence_capped: true,
        extraction_algorithm_implemented: false,
        model_evaluation_completed: false,
        pattern_persistence_authorized: false,
        runtime_authorized: false,
        hermes_authorized: false,
        autonomous_promotion_authorized: false,
    };
    let decision = if protocol_valid {
        Phase7PatternExtractionDecision::ProtocolFrozenExtractionAlgorithmBlocked
    } else {
        Phase7PatternExtractionDecision::ProtocolInvalid
    };

    Ok(Phase7PatternExtractionReport {
        schema_version: 1,
        evaluation_version: EVALUATION_VERSION.to_string(),
        tag,
        generated_at: Utc::now().to_rfc3339(),
        phase: "Phase 7.2 Evidence-Grounded Pattern Extraction Protocol".to_string(),
        dataset: dataset_summary,
        metrics,
        reference_validations,
        negative_cases,
        all_reference_candidates_valid,
        all_negative_cases_rejected,
        guards,
        decision,
        conclusion: "The design-only extraction input, PatternCandidate output boundary, automatic grounding checks, metrics, and rejection cases are frozen. No extraction algorithm or transfer performance is implemented or claimed.".to_string(),
    })
}

fn summarize(
    dataset: &PatternExtractionDataset,
    validations: &[PatternExtractionBatchValidation],
) -> PatternExtractionDatasetSummary {
    let source_scenarios = dataset
        .cases
        .iter()
        .map(|case| case.source_transfer_scenario_id.as_str())
        .collect::<BTreeSet<_>>();
    let source_domains = dataset
        .cases
        .iter()
        .map(|case| case.input.source_domain.as_str())
        .collect::<BTreeSet<_>>();
    let supporting_experience_count = dataset
        .cases
        .iter()
        .flat_map(|case| &case.input.experiences)
        .filter(|experience| !experience.counterexample)
        .count();
    let counterexample_count = dataset
        .cases
        .iter()
        .flat_map(|case| &case.input.experiences)
        .filter(|experience| experience.counterexample)
        .count();
    let design_ids = phase7_1_design_scenario_ids();
    let held_out_references = dataset
        .cases
        .iter()
        .filter(|case| !design_ids.contains(case.source_transfer_scenario_id.as_str()))
        .count();
    PatternExtractionDatasetSummary {
        case_count: dataset.cases.len(),
        distinct_source_scenarios: source_scenarios.len(),
        source_domain_count: source_domains.len(),
        supporting_experience_count,
        counterexample_count,
        reference_candidates_valid: validations.iter().filter(|item| item.valid).count(),
        held_out_references,
    }
}

fn phase7_1_design_scenario_ids() -> BTreeSet<&'static str> {
    [
        "transfer_001_direct_software_release",
        "transfer_002_direct_support_triage",
        "transfer_003_direct_experiment_design",
        "transfer_004_direct_database_incident",
        "transfer_005_direct_content_research",
        "transfer_006_cross_batch_to_startup",
        "transfer_007_cross_incident_to_campaign",
        "transfer_008_cross_medical_to_security",
        "transfer_009_cross_research_to_hiring",
        "transfer_010_cross_supply_to_compute",
    ]
    .into_iter()
    .collect()
}
fn metric_definitions() -> Vec<PatternExtractionMetricDefinition> {
    vec![
        metric("contract_validity", "higher", "Fraction of outputs satisfying the Phase 7 PatternCandidate contract.", false),
        metric("evidence_grounding", "higher", "Fraction of cited evidence that exactly matches authoritative input provenance.", true),
        metric("evidence_coverage", "higher", "Coverage of independent supporting experiences relevant to the proposition.", true),
        metric("scope_preservation", "higher", "Retention of material applicability constraints from the experiences.", true),
        metric("counterexample_handling", "higher", "Coverage and correct use of supplied limiting evidence.", true),
        metric("abstraction_specificity", "higher_with_boundary", "The proposition is reusable but not a vague truism or literal event copy.", true),
        metric("compression_ratio", "higher_with_fidelity", "Input evidence size divided by Pattern package size, interpreted with grounding and scope.", true),
        metric("unsupported_claim_rate", "lower", "Unsupported proposition, scope, prediction, or causal claims per output.", true),
        metric("evidence_id_hallucination_rate", "lower", "Citations not present in the extraction input divided by all citations.", false),
        metric("boundary_loss_rate", "lower", "Material exclusions or conditions omitted from the Pattern Candidate.", true),
        metric("falsifiability_rate", "higher", "Fraction of outputs with an observable prediction and falsification condition.", false),
    ]
}

fn metric(
    name: &str,
    direction: &str,
    definition: &str,
    requires_model_output: bool,
) -> PatternExtractionMetricDefinition {
    PatternExtractionMetricDefinition {
        name: name.to_string(),
        direction: direction.to_string(),
        definition: definition.to_string(),
        requires_model_output,
    }
}

fn negative_contract_cases(case: &PatternExtractionCase) -> Vec<PatternExtractionNegativeCase> {
    let mut cases = Vec::new();

    let mut hallucinated = case.reference_candidate.clone();
    hallucinated.supporting_evidence[0].memory_id = "invented_memory".to_string();
    cases.push(negative(
        "hallucinated_evidence_id",
        "evidence_reference_not_in_extraction_input",
        validate_pattern_extraction_submission(&case.input, &hallucinated).violations,
    ));

    let mut provenance = case.reference_candidate.clone();
    provenance.supporting_evidence[0].domain = "invented_domain".to_string();
    cases.push(negative(
        "provenance_mismatch",
        "evidence_provenance_mismatch",
        validate_pattern_extraction_submission(&case.input, &provenance).violations,
    ));

    let mut no_counterexample = case.reference_candidate.clone();
    no_counterexample.counterexamples.clear();
    cases.push(negative(
        "counterexample_omitted",
        "supplied_counterexample_omitted",
        validate_pattern_extraction_submission(&case.input, &no_counterexample).violations,
    ));

    let mut active = case.reference_candidate.clone();
    active.status = PatternStatus::Active;
    cases.push(negative(
        "premature_active_status",
        "extraction_output_must_remain_proposed",
        validate_pattern_extraction_submission(&case.input, &active).violations,
    ));

    let mut overconfident = case.reference_candidate.clone();
    overconfident.confidence = 0.95;
    cases.push(negative(
        "premature_confidence",
        "proposed_confidence_exceeds_phase7_2_cap",
        validate_pattern_extraction_submission(&case.input, &overconfident).violations,
    ));

    let mut fake_outcome = case.reference_candidate.clone();
    fake_outcome
        .validation_outcome_ids
        .push("unobserved_validation".to_string());
    cases.push(negative(
        "fabricated_validation_outcome",
        "extraction_cannot_claim_validation_outcomes",
        validate_pattern_extraction_submission(&case.input, &fake_outcome).violations,
    ));

    let too_many = vec![
        case.reference_candidate.clone(),
        case.reference_candidate.clone(),
    ];
    let batch = validate_pattern_extraction_batch(&case.input, &too_many);
    cases.push(negative(
        "candidate_limit_exceeded",
        "pattern_candidate_limit_exceeded",
        batch.violations,
    ));

    cases
}

fn negative(
    name: &str,
    expected_violation: &str,
    observed_violations: Vec<String>,
) -> PatternExtractionNegativeCase {
    PatternExtractionNegativeCase {
        name: name.to_string(),
        rejected: observed_violations
            .iter()
            .any(|violation| violation == expected_violation),
        expected_violation: expected_violation.to_string(),
        observed_violations,
    }
}
