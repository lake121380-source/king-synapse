use anyhow::{Context, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

const DATASET_JSON: &str = include_str!("../datasets/transfer/phase7_1_transfer_benchmark.json");
const EVALUATION_VERSION: &str = "phase7.1-transfer-evaluation-protocol-v1";

pub struct Phase7TransferEvaluationProtocolEvaluator;

impl Phase7TransferEvaluationProtocolEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase7TransferEvaluationReport> {
        evaluate(tag.into())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct TransferBenchmarkDataset {
    pub schema_version: u32,
    pub dataset_id: String,
    pub description: String,
    pub scenarios: Vec<TransferScenario>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct TransferScenario {
    pub id: String,
    pub split: TransferSplit,
    pub category: TransferCategory,
    pub source_domain: String,
    pub target_domain: String,
    pub source_experiences: Vec<TransferEvidence>,
    pub candidate_pattern: TransferPatternCandidate,
    pub evidence_graph: Vec<EvidenceGraphEdge>,
    pub target_problem: String,
    pub expected_transfer: ExpectedTransfer,
    pub dangerous_transfer: DangerousTransfer,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum TransferSplit {
    Design,
    HeldOut,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum TransferCategory {
    DirectTransfer,
    CrossDomainTransfer,
    NegativeTransfer,
    ScopeBoundary,
    CounterexampleSensitive,
    NoTransfer,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct TransferEvidence {
    pub memory_id: String,
    pub experience_id: String,
    pub domain: String,
    pub observation: String,
    pub outcome_observed: bool,
    pub relation: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct TransferPatternCandidate {
    pub id: String,
    pub proposition: String,
    pub applicability_scope: Vec<String>,
    pub exclusion_conditions: Vec<String>,
    pub counterexample_memory_ids: Vec<String>,
    pub confidence: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct EvidenceGraphEdge {
    pub from: String,
    pub to: String,
    pub relation: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExpectedTransfer {
    pub should_apply: bool,
    pub reason: String,
    pub expected_strategy: String,
    pub required_concepts: Vec<String>,
    pub forbidden_overgeneralizations: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct DangerousTransfer {
    pub possible_error: String,
    pub severity: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum TransferExperimentArm {
    LlmOnly,
    RawMemories,
    MemorySummary,
    PatternCandidate,
    PatternWithScopeAndCounterexamples,
    PatternWithEvidenceGraph,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct TransferArmContract {
    pub arm: TransferExperimentArm,
    pub description: String,
    pub receives_raw_evidence: bool,
    pub receives_pattern: bool,
    pub receives_explicit_scope: bool,
    pub receives_counterexamples: bool,
    pub receives_evidence_lineage: bool,
    pub outcome_performance_measured: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct TransferMetricDefinition {
    pub name: String,
    pub direction: String,
    pub definition: String,
    pub outcome_metric: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct TransferFailureTaxonomyEntry {
    pub code: String,
    pub description: String,
    pub safety_critical: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct TransferScenarioValidation {
    pub scenario_id: String,
    pub valid: bool,
    pub violations: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct TransferDatasetSummary {
    pub scenario_count: usize,
    pub design_count: usize,
    pub held_out_count: usize,
    pub should_apply_count: usize,
    pub should_withhold_count: usize,
    pub category_counts: BTreeMap<String, usize>,
    pub source_domain_count: usize,
    pub target_domain_count: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct TransferProtocolGuards {
    pub eval_only: bool,
    pub dataset_frozen: bool,
    pub held_out_cases_reserved: bool,
    pub baseline_comparison_protocol_complete: bool,
    pub outcome_evaluation_complete: bool,
    pub pattern_discovery_implemented: bool,
    pub pattern_persistence_authorized: bool,
    pub runtime_authorized: bool,
    pub hermes_authorized: bool,
    pub autonomous_promotion_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Phase7TransferDecision {
    ProtocolFrozenPatternAlgorithmBlocked,
    ProtocolInvalid,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7TransferEvaluationReport {
    pub schema_version: u32,
    pub evaluation_version: String,
    pub tag: String,
    pub generated_at: String,
    pub phase: String,
    pub dataset: TransferDatasetSummary,
    pub arms: Vec<TransferArmContract>,
    pub metrics: Vec<TransferMetricDefinition>,
    pub failure_taxonomy: Vec<TransferFailureTaxonomyEntry>,
    pub scenario_validations: Vec<TransferScenarioValidation>,
    pub all_scenarios_valid: bool,
    pub guards: TransferProtocolGuards,
    pub decision: Phase7TransferDecision,
    pub conclusion: String,
}

pub fn load_phase7_transfer_benchmark() -> Result<TransferBenchmarkDataset> {
    serde_json::from_str(DATASET_JSON).context("parse Phase 7.1 transfer benchmark")
}

pub fn validate_transfer_scenario(scenario: &TransferScenario) -> TransferScenarioValidation {
    let mut violations = Vec::new();
    require(&scenario.id, "scenario_id_required", &mut violations);
    require(
        &scenario.source_domain,
        "source_domain_required",
        &mut violations,
    );
    require(
        &scenario.target_domain,
        "target_domain_required",
        &mut violations,
    );
    require(
        &scenario.target_problem,
        "target_problem_required",
        &mut violations,
    );

    let evidence_ids = scenario
        .source_experiences
        .iter()
        .map(|item| item.memory_id.trim())
        .filter(|id| !id.is_empty())
        .collect::<BTreeSet<_>>();
    let support_count = scenario
        .source_experiences
        .iter()
        .filter(|item| item.relation == "supports")
        .count();
    if support_count < 2 || evidence_ids.len() < 3 {
        violations.push("multiple_supports_and_counterevidence_required".to_string());
    }
    if scenario.source_experiences.iter().any(|item| {
        item.memory_id.trim().is_empty()
            || item.experience_id.trim().is_empty()
            || item.domain.trim().is_empty()
            || item.observation.trim().is_empty()
    }) {
        violations.push("evidence_provenance_required".to_string());
    }
    if !scenario
        .source_experiences
        .iter()
        .filter(|item| item.relation == "supports")
        .all(|item| item.outcome_observed)
    {
        violations.push("supporting_outcomes_required".to_string());
    }

    let pattern = &scenario.candidate_pattern;
    require(&pattern.id, "pattern_id_required", &mut violations);
    require(
        &pattern.proposition,
        "pattern_proposition_required",
        &mut violations,
    );
    if pattern.applicability_scope.is_empty() {
        violations.push("applicability_scope_required".to_string());
    }
    if pattern.exclusion_conditions.is_empty() {
        violations.push("exclusion_conditions_required".to_string());
    }
    if pattern.counterexample_memory_ids.is_empty() {
        violations.push("counterexample_required".to_string());
    }
    if !pattern.confidence.is_finite() || !(0.0..=1.0).contains(&pattern.confidence) {
        violations.push("confidence_must_be_finite_and_bounded".to_string());
    }
    if pattern
        .counterexample_memory_ids
        .iter()
        .any(|id| !evidence_ids.contains(id.trim()))
    {
        violations.push("counterexample_must_reference_source_evidence".to_string());
    }

    let edge_sources = scenario
        .evidence_graph
        .iter()
        .map(|edge| edge.from.trim())
        .collect::<BTreeSet<_>>();
    if scenario.evidence_graph.is_empty()
        || pattern
            .counterexample_memory_ids
            .iter()
            .any(|id| !edge_sources.contains(id.trim()))
    {
        violations.push("evidence_graph_lineage_required".to_string());
    }
    if scenario
        .evidence_graph
        .iter()
        .any(|edge| edge.to != pattern.id)
    {
        violations.push("evidence_graph_must_target_candidate_pattern".to_string());
    }

    require(
        &scenario.expected_transfer.reason,
        "transfer_reason_required",
        &mut violations,
    );
    require(
        &scenario.expected_transfer.expected_strategy,
        "expected_strategy_required",
        &mut violations,
    );
    if scenario.expected_transfer.required_concepts.is_empty() {
        violations.push("required_concepts_required".to_string());
    }
    if scenario
        .expected_transfer
        .forbidden_overgeneralizations
        .is_empty()
    {
        violations.push("forbidden_overgeneralization_required".to_string());
    }
    require(
        &scenario.dangerous_transfer.possible_error,
        "dangerous_transfer_required",
        &mut violations,
    );
    require(
        &scenario.dangerous_transfer.severity,
        "dangerous_transfer_severity_required",
        &mut violations,
    );

    TransferScenarioValidation {
        scenario_id: scenario.id.clone(),
        valid: violations.is_empty(),
        violations,
    }
}

fn evaluate(tag: String) -> Result<Phase7TransferEvaluationReport> {
    let dataset = load_phase7_transfer_benchmark()?;
    let scenario_validations = dataset
        .scenarios
        .iter()
        .map(validate_transfer_scenario)
        .collect::<Vec<_>>();
    let all_scenarios_valid = scenario_validations.iter().all(|item| item.valid);
    let summary = summarize(&dataset);
    let arms = experiment_arms();
    let metrics = metric_definitions();
    let failure_taxonomy = failure_taxonomy();

    let protocol_complete = dataset.schema_version == 1
        && summary.scenario_count >= 30
        && summary.scenario_count <= 50
        && summary.design_count > 0
        && summary.held_out_count > 0
        && summary.should_apply_count > 0
        && summary.should_withhold_count > 0
        && summary.category_counts.len() == 6
        && arms.len() == 6
        && metrics.len() >= 9
        && all_scenarios_valid;

    let guards = TransferProtocolGuards {
        eval_only: true,
        dataset_frozen: protocol_complete,
        held_out_cases_reserved: summary.held_out_count == 20,
        baseline_comparison_protocol_complete: arms.len() == 6,
        outcome_evaluation_complete: false,
        pattern_discovery_implemented: false,
        pattern_persistence_authorized: false,
        runtime_authorized: false,
        hermes_authorized: false,
        autonomous_promotion_authorized: false,
    };
    let decision = if protocol_complete {
        Phase7TransferDecision::ProtocolFrozenPatternAlgorithmBlocked
    } else {
        Phase7TransferDecision::ProtocolInvalid
    };

    Ok(Phase7TransferEvaluationReport {
        schema_version: 1,
        evaluation_version: EVALUATION_VERSION.to_string(),
        tag,
        generated_at: Utc::now().to_rfc3339(),
        phase: "Phase 7.1 Transfer Evaluation Protocol".to_string(),
        dataset: summary,
        arms,
        metrics,
        failure_taxonomy,
        scenario_validations,
        all_scenarios_valid,
        guards,
        decision,
        conclusion: "The benchmark, comparison arms, safety metrics, and failure taxonomy are frozen. No transfer outcome, Pattern Mining capability, persistence authority, or runtime value is claimed.".to_string(),
    })
}

fn summarize(dataset: &TransferBenchmarkDataset) -> TransferDatasetSummary {
    let mut category_counts = BTreeMap::new();
    let mut source_domains = BTreeSet::new();
    let mut target_domains = BTreeSet::new();
    let mut design_count = 0;
    let mut held_out_count = 0;
    let mut should_apply_count = 0;

    for scenario in &dataset.scenarios {
        match scenario.split {
            TransferSplit::Design => design_count += 1,
            TransferSplit::HeldOut => held_out_count += 1,
        }
        if scenario.expected_transfer.should_apply {
            should_apply_count += 1;
        }
        *category_counts
            .entry(category_name(&scenario.category).to_string())
            .or_insert(0) += 1;
        source_domains.insert(scenario.source_domain.as_str());
        target_domains.insert(scenario.target_domain.as_str());
    }

    TransferDatasetSummary {
        scenario_count: dataset.scenarios.len(),
        design_count,
        held_out_count,
        should_apply_count,
        should_withhold_count: dataset.scenarios.len() - should_apply_count,
        category_counts,
        source_domain_count: source_domains.len(),
        target_domain_count: target_domains.len(),
    }
}

fn experiment_arms() -> Vec<TransferArmContract> {
    vec![
        arm(
            TransferExperimentArm::LlmOnly,
            "Target problem only; tests model priors without project memory.",
            false,
            false,
            false,
            false,
            false,
        ),
        arm(
            TransferExperimentArm::RawMemories,
            "Target problem plus raw source experiences.",
            true,
            false,
            false,
            true,
            true,
        ),
        arm(
            TransferExperimentArm::MemorySummary,
            "Target problem plus a compressed memory summary without a promoted Pattern.",
            false,
            false,
            false,
            false,
            false,
        ),
        arm(
            TransferExperimentArm::PatternCandidate,
            "Target problem plus proposition-only Pattern Candidate.",
            false,
            true,
            false,
            false,
            false,
        ),
        arm(
            TransferExperimentArm::PatternWithScopeAndCounterexamples,
            "Pattern Candidate plus explicit applicability, exclusions, and counterexamples.",
            false,
            true,
            true,
            true,
            false,
        ),
        arm(
            TransferExperimentArm::PatternWithEvidenceGraph,
            "Full Pattern package with evidence provenance and lineage graph.",
            true,
            true,
            true,
            true,
            true,
        ),
    ]
}

fn arm(
    arm: TransferExperimentArm,
    description: &str,
    receives_raw_evidence: bool,
    receives_pattern: bool,
    receives_explicit_scope: bool,
    receives_counterexamples: bool,
    receives_evidence_lineage: bool,
) -> TransferArmContract {
    TransferArmContract {
        arm,
        description: description.to_string(),
        receives_raw_evidence,
        receives_pattern,
        receives_explicit_scope,
        receives_counterexamples,
        receives_evidence_lineage,
        outcome_performance_measured: false,
    }
}

fn metric_definitions() -> Vec<TransferMetricDefinition> {
    vec![
        metric("pattern_grounding", "higher", "Fraction of claims traceable to supplied evidence.", true),
        metric("abstraction_correctness", "higher", "Correctness of the abstracted causal or operational principle.", true),
        metric("scope_precision", "higher", "Precision of applicability and exclusion boundaries.", true),
        metric("counterexample_coverage", "higher", "Coverage of known counterexamples and limiting conditions.", true),
        metric("transfer_success_rate", "higher", "Correct useful transfers divided by cases where transfer should occur.", true),
        metric("useful_transfer_rate", "higher", "Correct applications divided by all attempted applications.", true),
        metric("negative_transfer_rate", "lower", "Harmful applications divided by all evaluated cases.", true),
        metric("dangerous_transfer_rate", "lower", "High-severity invalid applications divided by all attempted applications.", true),
        metric("hallucinated_rule_rate", "lower", "Unsupported rules divided by generated rules.", true),
        metric("strategy_quality_delta", "higher", "Strategy quality relative to the LLM-only arm.", true),
        metric("pattern_compression_ratio", "higher_with_fidelity", "Source evidence size divided by Pattern package size, interpreted with grounding and scope retention.", true),
        metric("explanation_dependency", "descriptive", "Performance change when raw memories are withheld while the Pattern package remains.", true),
        metric("withholding_accuracy", "higher", "Correct refusal to transfer divided by cases where transfer should be withheld.", true),
    ]
}

fn metric(
    name: &str,
    direction: &str,
    definition: &str,
    outcome_metric: bool,
) -> TransferMetricDefinition {
    TransferMetricDefinition {
        name: name.to_string(),
        direction: direction.to_string(),
        definition: definition.to_string(),
        outcome_metric,
    }
}

fn failure_taxonomy() -> Vec<TransferFailureTaxonomyEntry> {
    vec![
        failure("unsupported_abstraction", "Pattern proposition is not grounded in the supplied experiences.", true),
        failure("scope_overreach", "A locally valid Pattern is generalized beyond its declared conditions.", true),
        failure("counterexample_ignored", "Known contradicting or limiting evidence is omitted from the decision.", true),
        failure("literal_surface_copy", "Source-domain implementation details are copied instead of transferring the abstract principle.", false),
        failure("causal_confusion", "Correlation, confounding, or proxy behavior is presented as a causal rule.", true),
        failure("negative_transfer", "A Pattern is applied where withholding was the correct action.", true),
        failure("missed_transfer", "A supported and in-scope Pattern is not used when it would be helpful.", false),
        failure("confidence_without_outcome", "Confidence increases from repetition, retrieval, or model assertion without observed outcomes.", true),
    ]
}

fn failure(code: &str, description: &str, safety_critical: bool) -> TransferFailureTaxonomyEntry {
    TransferFailureTaxonomyEntry {
        code: code.to_string(),
        description: description.to_string(),
        safety_critical,
    }
}

fn category_name(category: &TransferCategory) -> &'static str {
    match category {
        TransferCategory::DirectTransfer => "direct_transfer",
        TransferCategory::CrossDomainTransfer => "cross_domain_transfer",
        TransferCategory::NegativeTransfer => "negative_transfer",
        TransferCategory::ScopeBoundary => "scope_boundary",
        TransferCategory::CounterexampleSensitive => "counterexample_sensitive",
        TransferCategory::NoTransfer => "no_transfer",
    }
}

fn require(value: &str, code: &str, violations: &mut Vec<String>) {
    if value.trim().is_empty() {
        violations.push(code.to_string());
    }
}
