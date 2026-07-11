use crate::phase7_bounded_pattern_extraction_provider::PatternExtractionQualityMetrics;
use crate::phase7_pattern_extraction_protocol::load_phase7_pattern_extraction_design;
use crate::phase7_real_provider_readiness::{
    load_phase7_real_provider_execution, Phase7RealProviderReadinessEvaluator,
};
use anyhow::{bail, Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

const ANNOTATIONS_JSON: &str =
    include_str!("../datasets/pattern_extraction/phase7_3_candidate_error_annotations.json");
const EXECUTION_JSON: &str = include_str!("../reports/phase7_2_3_real_provider_execution.json");
const EVALUATION_VERSION: &str = "phase7.3-failure-taxonomy-candidate-error-analysis-v1";
const UNSUPPORTED_WARNING_THRESHOLD: f64 = 0.20;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum CandidateFailureKind {
    UnsupportedGeneralization,
    ScopeExpansion,
    MissingEvidence,
    WeakEvidence,
    PredictionWithoutSupport,
    CausalLeap,
    OverAbstraction,
    CounterexampleIgnored,
    AmbiguousPattern,
    DuplicatePattern,
    Other,
}

impl CandidateFailureKind {
    fn all() -> [Self; 11] {
        [
            Self::UnsupportedGeneralization,
            Self::ScopeExpansion,
            Self::MissingEvidence,
            Self::WeakEvidence,
            Self::PredictionWithoutSupport,
            Self::CausalLeap,
            Self::OverAbstraction,
            Self::CounterexampleIgnored,
            Self::AmbiguousPattern,
            Self::DuplicatePattern,
            Self::Other,
        ]
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum CandidateComponent {
    Proposition,
    Evidence,
    ApplicabilityScope,
    ExclusionScope,
    Prediction,
    Falsification,
    Counterexample,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum FailureSeverity {
    Low,
    Medium,
    High,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum MetricConfoundKind {
    LexicalNoveltyConfound,
    ScopeFieldPlacementConfound,
}

impl MetricConfoundKind {
    fn all() -> [Self; 2] {
        [
            Self::LexicalNoveltyConfound,
            Self::ScopeFieldPlacementConfound,
        ]
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct CandidateFailureLabel {
    pub kind: CandidateFailureKind,
    pub severity: FailureSeverity,
    pub components: Vec<CandidateComponent>,
    pub rationale: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MetricConfoundAnnotation {
    pub kind: MetricConfoundKind,
    pub rationale: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct FalsifiabilitySeedAssessment {
    pub structural_fields_present: bool,
    pub directly_tests_in_scope_prediction: bool,
    pub semantic_validity_established: bool,
    pub rationale: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct CandidateErrorSeedCase {
    pub case_id: String,
    pub response_sha256: String,
    pub primary_failure: CandidateFailureLabel,
    pub secondary_failures: Vec<CandidateFailureLabel>,
    pub metric_confounds: Vec<MetricConfoundAnnotation>,
    pub falsifiability: FalsifiabilitySeedAssessment,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct CandidateErrorAnnotationDataset {
    pub schema_version: u32,
    pub dataset_id: String,
    pub source_execution_id: String,
    pub annotation_mode: String,
    pub reviewer_count: usize,
    pub independent_second_review: bool,
    pub inter_rater_agreement: Option<f64>,
    pub held_out_accessed: bool,
    pub cases: Vec<CandidateErrorSeedCase>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct FailureTaxonomyDefinition {
    pub kind: CandidateFailureKind,
    pub definition: String,
    pub evidence_required: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MetricConfoundDefinition {
    pub kind: MetricConfoundKind,
    pub definition: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct CandidateErrorCaseAnalysis {
    pub case_id: String,
    pub response_sha256: String,
    pub quality_metrics: PatternExtractionQualityMetrics,
    pub unsupported_warning: bool,
    pub scope_warning: bool,
    pub primary_failure: CandidateFailureLabel,
    pub secondary_failures: Vec<CandidateFailureLabel>,
    pub metric_confounds: Vec<MetricConfoundAnnotation>,
    pub falsifiability: FalsifiabilitySeedAssessment,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct FailureKindSummary {
    pub kind: CandidateFailureKind,
    pub primary_count: usize,
    pub any_label_count: usize,
    pub case_rate: f64,
    pub mean_unsupported_claim_rate: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct MetricConfoundSummary {
    pub kind: MetricConfoundKind,
    pub case_count: usize,
    pub case_rate: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct FalsifiabilitySummary {
    pub structural_fields_present_count: usize,
    pub structural_fields_present_rate: f64,
    pub direct_in_scope_test_count: usize,
    pub direct_in_scope_test_rate: f64,
    pub semantic_validity_established_count: usize,
    pub semantic_validity_established_rate: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct CandidateErrorAnalysisSummary {
    pub candidate_count: usize,
    pub candidates_with_failure_labels: usize,
    pub total_failure_labels: usize,
    pub unsupported_warning_count: usize,
    pub scope_warning_count: usize,
    pub scope_expansion_label_count: usize,
    pub scope_warning_confirmation_rate: f64,
    pub evidence_failure_case_count: usize,
    pub counterexample_failure_case_count: usize,
    pub primary_failure_distribution: Vec<FailureKindSummary>,
    pub metric_confound_distribution: Vec<MetricConfoundSummary>,
    pub falsifiability: FalsifiabilitySummary,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CandidateErrorAnalysisGuards {
    pub frozen_phase7_2_3_execution_reused: bool,
    pub provider_calls_made: bool,
    pub prompt_modified: bool,
    pub parser_modified: bool,
    pub scorer_modified: bool,
    pub extraction_algorithm_modified: bool,
    pub design_cases_only: bool,
    pub held_out_cases_untouched: bool,
    pub independent_second_review_completed: bool,
    pub candidate_learning_authorized: bool,
    pub pattern_persistence_authorized: bool,
    pub knowledge_promotion_authorized: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Phase7CandidateErrorAnalysisDecision {
    TaxonomySeededIndependentReviewRequired,
    TaxonomyIndependentlyAdjudicated,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7CandidateErrorAnalysisReport {
    pub schema_version: u32,
    pub evaluation_version: String,
    pub tag: String,
    pub generated_at: String,
    pub phase: String,
    pub purpose: String,
    pub source_execution_sha256: String,
    pub annotation_sha256: String,
    pub annotation_protocol: CandidateErrorAnnotationDataset,
    pub taxonomy: Vec<FailureTaxonomyDefinition>,
    pub metric_confound_taxonomy: Vec<MetricConfoundDefinition>,
    pub cases: Vec<CandidateErrorCaseAnalysis>,
    pub summary: CandidateErrorAnalysisSummary,
    pub guards: CandidateErrorAnalysisGuards,
    pub decision: Phase7CandidateErrorAnalysisDecision,
    pub conclusion: String,
}

pub struct Phase7CandidateErrorAnalysisEvaluator;

impl Phase7CandidateErrorAnalysisEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase7CandidateErrorAnalysisReport> {
        evaluate(tag.into())
    }
}

pub fn load_phase7_candidate_error_annotations() -> Result<CandidateErrorAnnotationDataset> {
    serde_json::from_str(ANNOTATIONS_JSON)
        .context("parse Phase 7.3 candidate error annotation dataset")
}

fn evaluate(tag: String) -> Result<Phase7CandidateErrorAnalysisReport> {
    let dataset = load_phase7_pattern_extraction_design()?;
    let execution = load_phase7_real_provider_execution()?;
    let readiness = Phase7RealProviderReadinessEvaluator::evaluate("phase7.3-source")?;
    let annotations = load_phase7_candidate_error_annotations()?;

    if annotations.source_execution_id != execution.execution_id {
        bail!("annotation_source_execution_id_mismatch");
    }
    if annotations.held_out_accessed {
        bail!("phase7_3_annotations_must_not_access_held_out_cases");
    }
    if annotations.reviewer_count == 0 {
        bail!("phase7_3_requires_at_least_one_seed_reviewer");
    }
    if annotations.independent_second_review && annotations.reviewer_count < 2 {
        bail!("independent_review_requires_two_reviewers");
    }
    if !annotations.independent_second_review && annotations.inter_rater_agreement.is_some() {
        bail!("inter_rater_agreement_requires_independent_second_review");
    }

    let expected_ids = dataset
        .cases
        .iter()
        .map(|case| case.id.as_str())
        .collect::<BTreeSet<_>>();
    let annotation_ids = annotations
        .cases
        .iter()
        .map(|case| case.case_id.as_str())
        .collect::<BTreeSet<_>>();
    if expected_ids != annotation_ids || annotations.cases.len() != dataset.cases.len() {
        bail!("phase7_3_annotations_must_cover_exactly_the_ten_design_cases");
    }

    let readiness_by_id = readiness
        .cases
        .iter()
        .map(|case| (case.case_id.as_str(), case))
        .collect::<BTreeMap<_, _>>();
    let output_by_id = execution
        .outputs
        .iter()
        .map(|output| (output.case_id.as_str(), output))
        .collect::<BTreeMap<_, _>>();
    let input_by_id = dataset
        .cases
        .iter()
        .map(|case| (case.id.as_str(), &case.input))
        .collect::<BTreeMap<_, _>>();

    let mut cases = Vec::with_capacity(annotations.cases.len());
    for annotation in &annotations.cases {
        let readiness_case = readiness_by_id
            .get(annotation.case_id.as_str())
            .with_context(|| format!("missing readiness case {}", annotation.case_id))?;
        let output = output_by_id
            .get(annotation.case_id.as_str())
            .with_context(|| format!("missing execution output {}", annotation.case_id))?;
        let input = input_by_id
            .get(annotation.case_id.as_str())
            .with_context(|| format!("missing design input {}", annotation.case_id))?;

        if annotation.response_sha256 != output.response_sha256 {
            bail!(
                "annotation_response_hash_mismatch_for_{}",
                annotation.case_id
            );
        }
        validate_failure_labels(annotation)?;
        validate_metric_confounds(annotation, readiness_case, output, input)?;
        validate_falsifiability(annotation, output)?;

        cases.push(CandidateErrorCaseAnalysis {
            case_id: annotation.case_id.clone(),
            response_sha256: annotation.response_sha256.clone(),
            quality_metrics: readiness_case.quality_metrics.clone(),
            unsupported_warning: readiness_case.quality_metrics.unsupported_claim_rate
                > UNSUPPORTED_WARNING_THRESHOLD,
            scope_warning: readiness_case.quality_metrics.scope_retention < 1.0,
            primary_failure: annotation.primary_failure.clone(),
            secondary_failures: annotation.secondary_failures.clone(),
            metric_confounds: annotation.metric_confounds.clone(),
            falsifiability: annotation.falsifiability.clone(),
        });
    }

    let summary = summarize(&cases);
    let guards = CandidateErrorAnalysisGuards {
        frozen_phase7_2_3_execution_reused: annotations.source_execution_id
            == execution.execution_id,
        provider_calls_made: false,
        prompt_modified: false,
        parser_modified: false,
        scorer_modified: false,
        extraction_algorithm_modified: false,
        design_cases_only: true,
        held_out_cases_untouched: !annotations.held_out_accessed,
        independent_second_review_completed: annotations.independent_second_review,
        candidate_learning_authorized: false,
        pattern_persistence_authorized: false,
        knowledge_promotion_authorized: false,
        runtime_authorized: false,
        hermes_authorized: false,
    };
    let decision = if annotations.independent_second_review {
        Phase7CandidateErrorAnalysisDecision::TaxonomyIndependentlyAdjudicated
    } else {
        Phase7CandidateErrorAnalysisDecision::TaxonomySeededIndependentReviewRequired
    };

    Ok(Phase7CandidateErrorAnalysisReport {
        schema_version: 1,
        evaluation_version: EVALUATION_VERSION.to_string(),
        tag,
        generated_at: Utc::now().to_rfc3339(),
        phase: "Phase 7.3 Failure Taxonomy & Candidate Error Analysis".to_string(),
        purpose: "Explain candidate-level failure mechanisms in the frozen ten-case real-provider design run without changing extraction, scoring, held-out data, persistence, or runtime behavior.".to_string(),
        source_execution_sha256: sha256(EXECUTION_JSON.as_bytes()),
        annotation_sha256: sha256(ANNOTATIONS_JSON.as_bytes()),
        annotation_protocol: annotations,
        taxonomy: failure_taxonomy(),
        metric_confound_taxonomy: metric_confound_taxonomy(),
        cases,
        summary,
        guards,
        decision,
        conclusion: "The seed review separates candidate errors from scorer confounds. Primary mechanisms are prediction overcommitment, unsupported generalization, causal certainty, and over-abstraction; evidence provenance and counterexample retention are not the observed bottlenecks. The frozen lexical unsupported-claim and scope proxies remain useful warnings but are not semantic ground truth, so extraction or admission changes remain blocked until independent adjudication.".to_string(),
    })
}

fn validate_failure_labels(annotation: &CandidateErrorSeedCase) -> Result<()> {
    let mut kinds = BTreeSet::new();
    let labels = std::iter::once(&annotation.primary_failure)
        .chain(annotation.secondary_failures.iter())
        .collect::<Vec<_>>();
    for label in labels {
        if label.components.is_empty() || label.rationale.trim().is_empty() {
            bail!("incomplete_failure_label_for_{}", annotation.case_id);
        }
        if !kinds.insert(label.kind) {
            bail!("duplicate_failure_kind_for_{}", annotation.case_id);
        }
    }
    Ok(())
}

fn validate_metric_confounds(
    annotation: &CandidateErrorSeedCase,
    readiness_case: &crate::phase7_real_provider_readiness::RealProviderCaseReadiness,
    output: &crate::phase7_pattern_provider_comparison::ModelProviderCaseOutput,
    input: &crate::phase7_pattern_extraction_protocol::PatternExtractionInput,
) -> Result<()> {
    let mut kinds = BTreeSet::new();
    for confound in &annotation.metric_confounds {
        if confound.rationale.trim().is_empty() || !kinds.insert(confound.kind) {
            bail!("invalid_metric_confound_for_{}", annotation.case_id);
        }
        match confound.kind {
            MetricConfoundKind::LexicalNoveltyConfound => {
                if readiness_case.quality_metrics.unsupported_claim_rate
                    <= UNSUPPORTED_WARNING_THRESHOLD
                {
                    bail!("lexical_confound_requires_unsupported_warning");
                }
            }
            MetricConfoundKind::ScopeFieldPlacementConfound => {
                if readiness_case.quality_metrics.scope_retention >= 1.0
                    || !output
                        .candidate
                        .source_domains
                        .iter()
                        .any(|domain| domain == &input.source_domain)
                {
                    bail!("scope_field_confound_requires_scope_warning_and_grounded_domain");
                }
            }
        }
    }
    Ok(())
}

fn validate_falsifiability(
    annotation: &CandidateErrorSeedCase,
    output: &crate::phase7_pattern_provider_comparison::ModelProviderCaseOutput,
) -> Result<()> {
    let structurally_present = !output.candidate.falsification_conditions.is_empty()
        && output
            .candidate
            .falsification_conditions
            .iter()
            .all(|item| !item.statement.trim().is_empty() && !item.observable.trim().is_empty());
    if annotation.falsifiability.structural_fields_present != structurally_present {
        bail!(
            "falsifiability_structure_mismatch_for_{}",
            annotation.case_id
        );
    }
    if annotation.falsifiability.semantic_validity_established {
        bail!("phase7_3_cannot_establish_falsification_semantic_validity");
    }
    if annotation.falsifiability.rationale.trim().is_empty() {
        bail!("falsifiability_rationale_required");
    }
    Ok(())
}

fn summarize(cases: &[CandidateErrorCaseAnalysis]) -> CandidateErrorAnalysisSummary {
    let candidate_count = cases.len();
    let total_failure_labels = cases
        .iter()
        .map(|case| 1 + case.secondary_failures.len())
        .sum();
    let unsupported_warning_count = cases.iter().filter(|case| case.unsupported_warning).count();
    let scope_warning_count = cases.iter().filter(|case| case.scope_warning).count();
    let scope_expansion_label_count = cases
        .iter()
        .filter(|case| case_has_kind(case, CandidateFailureKind::ScopeExpansion))
        .count();
    let evidence_failure_case_count = cases
        .iter()
        .filter(|case| {
            case_has_kind(case, CandidateFailureKind::MissingEvidence)
                || case_has_kind(case, CandidateFailureKind::WeakEvidence)
        })
        .count();
    let counterexample_failure_case_count = cases
        .iter()
        .filter(|case| case_has_kind(case, CandidateFailureKind::CounterexampleIgnored))
        .count();

    let primary_failure_distribution = CandidateFailureKind::all()
        .into_iter()
        .map(|kind| {
            let primary_count = cases
                .iter()
                .filter(|case| case.primary_failure.kind == kind)
                .count();
            let affected = cases
                .iter()
                .filter(|case| case_has_kind(case, kind))
                .collect::<Vec<_>>();
            FailureKindSummary {
                kind,
                primary_count,
                any_label_count: affected.len(),
                case_rate: fraction(affected.len(), candidate_count),
                mean_unsupported_claim_rate: if affected.is_empty() {
                    None
                } else {
                    Some(mean(
                        affected
                            .iter()
                            .map(|case| case.quality_metrics.unsupported_claim_rate),
                    ))
                },
            }
        })
        .collect();

    let metric_confound_distribution = MetricConfoundKind::all()
        .into_iter()
        .map(|kind| {
            let case_count = cases
                .iter()
                .filter(|case| {
                    case.metric_confounds
                        .iter()
                        .any(|confound| confound.kind == kind)
                })
                .count();
            MetricConfoundSummary {
                kind,
                case_count,
                case_rate: fraction(case_count, candidate_count),
            }
        })
        .collect();

    let structural_fields_present_count = cases
        .iter()
        .filter(|case| case.falsifiability.structural_fields_present)
        .count();
    let direct_in_scope_test_count = cases
        .iter()
        .filter(|case| case.falsifiability.directly_tests_in_scope_prediction)
        .count();
    let semantic_validity_established_count = cases
        .iter()
        .filter(|case| case.falsifiability.semantic_validity_established)
        .count();

    CandidateErrorAnalysisSummary {
        candidate_count,
        candidates_with_failure_labels: cases.len(),
        total_failure_labels,
        unsupported_warning_count,
        scope_warning_count,
        scope_expansion_label_count,
        scope_warning_confirmation_rate: fraction(
            cases
                .iter()
                .filter(|case| {
                    case.scope_warning && case_has_kind(case, CandidateFailureKind::ScopeExpansion)
                })
                .count(),
            scope_warning_count,
        ),
        evidence_failure_case_count,
        counterexample_failure_case_count,
        primary_failure_distribution,
        metric_confound_distribution,
        falsifiability: FalsifiabilitySummary {
            structural_fields_present_count,
            structural_fields_present_rate: fraction(
                structural_fields_present_count,
                candidate_count,
            ),
            direct_in_scope_test_count,
            direct_in_scope_test_rate: fraction(direct_in_scope_test_count, candidate_count),
            semantic_validity_established_count,
            semantic_validity_established_rate: fraction(
                semantic_validity_established_count,
                candidate_count,
            ),
        },
    }
}

fn case_has_kind(case: &CandidateErrorCaseAnalysis, kind: CandidateFailureKind) -> bool {
    case.primary_failure.kind == kind
        || case
            .secondary_failures
            .iter()
            .any(|failure| failure.kind == kind)
}

fn failure_taxonomy() -> Vec<FailureTaxonomyDefinition> {
    vec![
        definition(CandidateFailureKind::UnsupportedGeneralization, "The candidate extends beyond the number, domain, conditions, or outcome range supported by the supplied evidence.", "Identify the exact broader claim and the missing evidence needed to support it."),
        definition(CandidateFailureKind::ScopeExpansion, "The candidate drops or widens an applicability or exclusion boundary present in the evidence.", "Compare proposition, applicability conditions, exclusions, source domains, and counterexample semantics."),
        definition(CandidateFailureKind::MissingEvidence, "A claim cites absent, incorrect, or incomplete evidence lineage.", "Show a missing or provenance-invalid memory or experience reference."),
        definition(CandidateFailureKind::WeakEvidence, "The evidence is correctly cited but lacks independent, observed, or sufficient support for the claim strength.", "Show insufficient independent observations or missing outcomes relative to the claim."),
        definition(CandidateFailureKind::PredictionWithoutSupport, "The prediction introduces a guarantee, detail, or outcome not warranted by the observed evidence.", "Compare prediction strength with observed outcomes and proposition uncertainty."),
        definition(CandidateFailureKind::CausalLeap, "Observational or associational evidence is converted into causal or deterministic language.", "Identify causal-strength language and the missing intervention or alternative-explanation evidence."),
        definition(CandidateFailureKind::OverAbstraction, "Compression removes distinctions that are necessary for the Pattern to remain meaningful and bounded.", "Identify merged concepts or conditions whose differences matter to the outcome."),
        definition(CandidateFailureKind::CounterexampleIgnored, "A supplied counterexample is omitted or retained only by ID without preserving its limiting meaning.", "Compare counterexample evidence with exclusions and falsification conditions."),
        definition(CandidateFailureKind::AmbiguousPattern, "The Pattern cannot be applied or tested consistently because key terms or outcomes are underspecified.", "Identify undefined terms, unobservable outcomes, or incompatible interpretations."),
        definition(CandidateFailureKind::DuplicatePattern, "The candidate adds no distinct proposition, boundary, or prediction relative to another candidate.", "Show semantic equivalence and absence of new scope or evidence lineage."),
        definition(CandidateFailureKind::Other, "A candidate-level failure not captured by the frozen taxonomy.", "Provide a bounded rationale and evidence for taxonomy revision."),
    ]
}

fn metric_confound_taxonomy() -> Vec<MetricConfoundDefinition> {
    vec![
        MetricConfoundDefinition {
            kind: MetricConfoundKind::LexicalNoveltyConfound,
            definition: "The token-level unsupported-claim proxy counts grounded paraphrases or bridging terms as unsupported because it does not perform semantic entailment.".to_string(),
        },
        MetricConfoundDefinition {
            kind: MetricConfoundKind::ScopeFieldPlacementConfound,
            definition: "The frozen scope proxy requires the source domain inside applicability-condition values and can warn even when the domain is preserved in proposition and source_domains.".to_string(),
        },
    ]
}

fn definition(
    kind: CandidateFailureKind,
    definition: &str,
    evidence_required: &str,
) -> FailureTaxonomyDefinition {
    FailureTaxonomyDefinition {
        kind,
        definition: definition.to_string(),
        evidence_required: evidence_required.to_string(),
    }
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
