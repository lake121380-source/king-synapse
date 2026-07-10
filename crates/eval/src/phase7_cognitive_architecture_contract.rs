use anyhow::Result;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

const SCHEMA_VERSION: u32 = 1;
const EVALUATION_VERSION: &str = "phase7.0-cognitive-architecture-contract-v1";

pub struct Phase7CognitiveArchitectureContractEvaluator;

impl Phase7CognitiveArchitectureContractEvaluator {
    pub fn evaluate(tag: impl Into<String>) -> Result<Phase7CognitiveArchitectureContractReport> {
        Ok(evaluate(tag.into()))
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PatternStatus {
    Proposed,
    Supported,
    Active,
    Challenged,
    Refined,
    Superseded,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct EvidenceReference {
    pub memory_id: String,
    pub experience_id: String,
    pub domain: String,
    pub independent_source: bool,
    pub observed_outcome: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PatternCondition {
    pub field: String,
    pub operator: String,
    pub value: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PatternPrediction {
    pub statement: String,
    pub observable: String,
    pub success_criterion: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct FalsificationCondition {
    pub statement: String,
    pub observable: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct PatternCandidate {
    pub id: String,
    pub proposition: String,
    pub supporting_evidence: Vec<EvidenceReference>,
    pub counterexamples: Vec<EvidenceReference>,
    pub counterexample_search_performed: bool,
    pub applicability_conditions: Vec<PatternCondition>,
    pub exclusion_conditions: Vec<PatternCondition>,
    pub source_domains: Vec<String>,
    pub predictions: Vec<PatternPrediction>,
    pub falsification_conditions: Vec<FalsificationCondition>,
    pub validation_outcome_ids: Vec<String>,
    pub confidence: f64,
    pub status: PatternStatus,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PatternContractValidation {
    pub valid: bool,
    pub violations: Vec<String>,
}

pub fn validate_pattern_candidate(candidate: &PatternCandidate) -> PatternContractValidation {
    let mut violations = Vec::new();

    require_non_empty(&candidate.id, "pattern_id_required", &mut violations);
    require_non_empty(
        &candidate.proposition,
        "pattern_proposition_required",
        &mut violations,
    );

    let supporting_ids = candidate
        .supporting_evidence
        .iter()
        .map(|evidence| evidence.memory_id.trim())
        .filter(|id| !id.is_empty())
        .collect::<BTreeSet<_>>();
    if supporting_ids.len() < 2 {
        violations.push("at_least_two_distinct_supporting_memories_required".to_string());
    }

    if candidate.supporting_evidence.iter().any(|evidence| {
        evidence.experience_id.trim().is_empty() || evidence.domain.trim().is_empty()
    }) {
        violations.push("supporting_evidence_provenance_required".to_string());
    }

    let counterexample_ids = candidate
        .counterexamples
        .iter()
        .map(|evidence| evidence.memory_id.trim())
        .filter(|id| !id.is_empty())
        .collect::<BTreeSet<_>>();
    if candidate.counterexamples.iter().any(|evidence| {
        evidence.experience_id.trim().is_empty() || evidence.domain.trim().is_empty()
    }) {
        violations.push("counterexample_provenance_required".to_string());
    }
    if !supporting_ids.is_disjoint(&counterexample_ids) {
        violations.push("support_and_counterexample_evidence_must_be_disjoint".to_string());
    }
    if !candidate.counterexample_search_performed {
        violations.push("counterexample_search_required".to_string());
    }
    if candidate.applicability_conditions.is_empty() {
        violations.push("applicability_conditions_required".to_string());
    }
    if candidate.source_domains.is_empty()
        || candidate
            .source_domains
            .iter()
            .any(|domain| domain.trim().is_empty())
    {
        violations.push("source_domain_required".to_string());
    }
    if candidate.predictions.is_empty() {
        violations.push("testable_prediction_required".to_string());
    }
    if candidate.falsification_conditions.is_empty() {
        violations.push("falsification_condition_required".to_string());
    }
    if !candidate.confidence.is_finite() || !(0.0..=1.0).contains(&candidate.confidence) {
        violations.push("confidence_must_be_finite_and_bounded".to_string());
    }
    if matches!(
        candidate.status,
        PatternStatus::Supported
            | PatternStatus::Active
            | PatternStatus::Challenged
            | PatternStatus::Refined
            | PatternStatus::Superseded
    ) && candidate.validation_outcome_ids.is_empty()
    {
        violations.push("non_proposed_status_requires_validation_outcome".to_string());
    }

    PatternContractValidation {
        valid: violations.is_empty(),
        violations,
    }
}

fn require_non_empty(value: &str, violation: &str, violations: &mut Vec<String>) {
    if value.trim().is_empty() {
        violations.push(violation.to_string());
    }
}

fn canonical_candidate() -> PatternCandidate {
    PatternCandidate {
        id: "pattern.service-diagnosis.observability-first.v0".to_string(),
        proposition: "For an unavailable long-running service, establish observability before applying remediation.".to_string(),
        supporting_evidence: vec![
            EvidenceReference {
                memory_id: "memory.redis-outage-001".to_string(),
                experience_id: "experience.redis-outage-001".to_string(),
                domain: "redis".to_string(),
                independent_source: true,
                observed_outcome: true,
            },
            EvidenceReference {
                memory_id: "memory.postgresql-outage-004".to_string(),
                experience_id: "experience.postgresql-outage-004".to_string(),
                domain: "postgresql".to_string(),
                independent_source: true,
                observed_outcome: true,
            },
        ],
        counterexamples: vec![EvidenceReference {
            memory_id: "memory.managed-service-incident-002".to_string(),
            experience_id: "experience.managed-service-incident-002".to_string(),
            domain: "managed_service".to_string(),
            independent_source: true,
            observed_outcome: true,
        }],
        counterexample_search_performed: true,
        applicability_conditions: vec![PatternCondition {
            field: "system.kind".to_string(),
            operator: "equals".to_string(),
            value: "long_running_service".to_string(),
        }],
        exclusion_conditions: vec![PatternCondition {
            field: "operator.host_access".to_string(),
            operator: "equals".to_string(),
            value: "unavailable".to_string(),
        }],
        source_domains: vec!["redis".to_string(), "postgresql".to_string()],
        predictions: vec![PatternPrediction {
            statement: "Observability-first diagnosis reduces unsupported remediation attempts."
                .to_string(),
            observable: "unsupported_remediation_attempt_count".to_string(),
            success_criterion: "lower_than_direct_remediation_baseline".to_string(),
        }],
        falsification_conditions: vec![FalsificationCondition {
            statement: "Reject or narrow the pattern if observability-first diagnosis does not reduce unsupported remediation across independent service incidents.".to_string(),
            observable: "independent_incident_outcomes".to_string(),
        }],
        validation_outcome_ids: Vec::new(),
        confidence: 0.55,
        status: PatternStatus::Proposed,
    }
}

fn invalid_cases(valid: &PatternCandidate) -> Vec<PatternContractCase> {
    let mut missing_support = valid.clone();
    missing_support.supporting_evidence.truncate(1);

    let mut missing_scope = valid.clone();
    missing_scope.applicability_conditions.clear();

    let mut missing_falsification = valid.clone();
    missing_falsification.falsification_conditions.clear();

    let mut no_counterexample_search = valid.clone();
    no_counterexample_search.counterexample_search_performed = false;

    let mut invalid_confidence = valid.clone();
    invalid_confidence.confidence = 1.5;

    let mut premature_active = valid.clone();
    premature_active.status = PatternStatus::Active;
    premature_active.validation_outcome_ids.clear();

    vec![
        contract_case("missing_supporting_evidence", missing_support, false),
        contract_case("missing_applicability_scope", missing_scope, false),
        contract_case(
            "missing_falsification_condition",
            missing_falsification,
            false,
        ),
        contract_case(
            "counterexample_search_not_performed",
            no_counterexample_search,
            false,
        ),
        contract_case("invalid_confidence", invalid_confidence, false),
        contract_case("premature_active_status", premature_active, false),
    ]
}

fn contract_case(
    name: impl Into<String>,
    candidate: PatternCandidate,
    expected_valid: bool,
) -> PatternContractCase {
    let validation = validate_pattern_candidate(&candidate);
    PatternContractCase {
        name: name.into(),
        expected_valid,
        observed_valid: validation.valid,
        violations: validation.violations,
        expectation_met: validation.valid == expected_valid,
    }
}

fn evaluate(tag: String) -> Phase7CognitiveArchitectureContractReport {
    let candidate = canonical_candidate();
    let canonical_validation = validate_pattern_candidate(&candidate);
    let invalid_cases = invalid_cases(&candidate);
    let artifact_ladder = artifact_ladder();
    let lifecycle = lifecycle_contract();
    let confidence_update_policy = ConfidenceUpdatePolicy {
        allowed_sources: vec![
            "new_independent_supporting_evidence".to_string(),
            "new_counterexample".to_string(),
            "observed_transfer_outcome".to_string(),
            "explicit_human_or_evaluator_review".to_string(),
        ],
        prohibited_sources: vec![
            "retrieval_count".to_string(),
            "usage_count_without_outcome".to_string(),
            "model_self_assertion".to_string(),
            "generated_explanation_without_evidence".to_string(),
        ],
    };
    let guards = Phase7ArchitectureGuards {
        eval_only: true,
        contract_only: true,
        recall_engine_modified: false,
        cognitive_booster_modified: false,
        memory_schema_changed: false,
        memory_written: false,
        pattern_persisted: false,
        pattern_algorithm_implemented: false,
        autonomous_pattern_promotion: false,
        strategy_execution_performed: false,
        runtime_applied: false,
        hermes_integration_performed: false,
        production_claim_authorized: false,
    };
    let pass = canonical_validation.valid
        && invalid_cases.iter().all(|case| case.expectation_met)
        && artifact_ladder
            .iter()
            .all(|artifact| !artifact.runtime_authority)
        && lifecycle.iter().all(|transition| !transition.autonomous)
        && confidence_update_policy
            .prohibited_sources
            .iter()
            .any(|source| source == "usage_count_without_outcome")
        && !guards.pattern_algorithm_implemented
        && !guards.autonomous_pattern_promotion
        && !guards.runtime_applied;

    Phase7CognitiveArchitectureContractReport {
        schema_version: SCHEMA_VERSION,
        tag,
        phase: "Phase 7.0 Cognitive Architecture Reorientation".to_string(),
        mode: "eval_only_contract".to_string(),
        evaluation_version: EVALUATION_VERSION.to_string(),
        generated_at: Utc::now().to_rfc3339(),
        north_star: NorthStarContract {
            statement: "Transform grounded experiences into scoped, falsifiable, transferable patterns; use outcomes to validate, refine, supersede, or reject them."
                .to_string(),
            mainline: vec![
                "experience".to_string(),
                "evidence".to_string(),
                "pattern_candidate".to_string(),
                "validated_pattern".to_string(),
                "strategy_candidate".to_string(),
                "transfer".to_string(),
                "outcome_feedback".to_string(),
                "knowledge_evolution".to_string(),
            ],
            memory_role: "evidence substrate, not the final cognitive product".to_string(),
            retrieval_booster_role: "bounded evidence-selection research, not the project mainline"
                .to_string(),
        },
        artifact_ladder,
        canonical_pattern_candidate: candidate,
        canonical_validation,
        invalid_contract_cases: invalid_cases,
        lifecycle,
        confidence_update_policy,
        decision: Phase7ArchitectureDecision {
            cognitive_architecture_north_star_frozen: true,
            experience_to_pattern_mainline_authorized: true,
            retrieval_booster_mainline_continued: false,
            pattern_contract_established: true,
            pattern_discovery_algorithm_authorized: false,
            phase7_1_transfer_benchmark_design_recommended: true,
            knowledge_graph_authorized: false,
            autonomous_self_improvement_authorized: false,
            runtime_authorization: false,
        },
        guards,
        pass,
        status: if pass { "PASS" } else { "FAIL" }.to_string(),
        conclusion: "Phase 7.0 defines the evidence-grounded Experience-to-Pattern contract only; it does not discover, persist, promote, execute, or deploy patterns."
            .to_string(),
    }
}

fn artifact_ladder() -> Vec<CognitiveArtifactContract> {
    vec![
        CognitiveArtifactContract {
            artifact: "experience".to_string(),
            purpose: "record an observed event and outcome".to_string(),
            required_grounding: "source and outcome provenance".to_string(),
            allowed_authority: "evidence only".to_string(),
            runtime_authority: false,
        },
        CognitiveArtifactContract {
            artifact: "pattern_candidate".to_string(),
            purpose:
                "express a scoped and falsifiable hypothesis induced from multiple experiences"
                    .to_string(),
            required_grounding:
                "supporting evidence, counterexample search, scope, prediction, falsification"
                    .to_string(),
            allowed_authority: "proposal and evaluation only".to_string(),
            runtime_authority: false,
        },
        CognitiveArtifactContract {
            artifact: "validated_pattern".to_string(),
            purpose: "represent a pattern supported by independent validation outcomes".to_string(),
            required_grounding: "independent evidence and observed transfer outcomes".to_string(),
            allowed_authority: "future shadow strategy input only".to_string(),
            runtime_authority: false,
        },
        CognitiveArtifactContract {
            artifact: "strategy_candidate".to_string(),
            purpose: "adapt one or more patterns to a new task".to_string(),
            required_grounding: "pattern provenance, task conditions, risk and expected outcome"
                .to_string(),
            allowed_authority: "proposal and shadow evaluation only".to_string(),
            runtime_authority: false,
        },
        CognitiveArtifactContract {
            artifact: "outcome".to_string(),
            purpose: "record what happened after an authorized experiment".to_string(),
            required_grounding: "action, environment, observation and attribution boundaries"
                .to_string(),
            allowed_authority: "future lifecycle evidence only".to_string(),
            runtime_authority: false,
        },
    ]
}

fn lifecycle_contract() -> Vec<PatternLifecycleTransition> {
    vec![
        transition(
            PatternStatus::Proposed,
            PatternStatus::Supported,
            "independent supporting evidence and evaluation gate",
        ),
        transition(
            PatternStatus::Supported,
            PatternStatus::Active,
            "successful held-out transfer validation and explicit authorization",
        ),
        transition(
            PatternStatus::Active,
            PatternStatus::Challenged,
            "material counterexample or failed transfer outcome",
        ),
        transition(
            PatternStatus::Challenged,
            PatternStatus::Refined,
            "scope or proposition revised with traceable evidence",
        ),
        transition(
            PatternStatus::Refined,
            PatternStatus::Active,
            "revalidation on held-out evidence",
        ),
        transition(
            PatternStatus::Active,
            PatternStatus::Superseded,
            "better supported replacement pattern",
        ),
        transition(
            PatternStatus::Proposed,
            PatternStatus::Rejected,
            "insufficient grounding or falsifying evidence",
        ),
    ]
}

fn transition(
    from: PatternStatus,
    to: PatternStatus,
    required_evidence: impl Into<String>,
) -> PatternLifecycleTransition {
    PatternLifecycleTransition {
        from,
        to,
        required_evidence: required_evidence.into(),
        autonomous: false,
        requires_explicit_evaluation_gate: true,
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct NorthStarContract {
    pub statement: String,
    pub mainline: Vec<String>,
    pub memory_role: String,
    pub retrieval_booster_role: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CognitiveArtifactContract {
    pub artifact: String,
    pub purpose: String,
    pub required_grounding: String,
    pub allowed_authority: String,
    pub runtime_authority: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PatternContractCase {
    pub name: String,
    pub expected_valid: bool,
    pub observed_valid: bool,
    pub violations: Vec<String>,
    pub expectation_met: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PatternLifecycleTransition {
    pub from: PatternStatus,
    pub to: PatternStatus,
    pub required_evidence: String,
    pub autonomous: bool,
    pub requires_explicit_evaluation_gate: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConfidenceUpdatePolicy {
    pub allowed_sources: Vec<String>,
    pub prohibited_sources: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Phase7ArchitectureDecision {
    pub cognitive_architecture_north_star_frozen: bool,
    pub experience_to_pattern_mainline_authorized: bool,
    pub retrieval_booster_mainline_continued: bool,
    pub pattern_contract_established: bool,
    pub pattern_discovery_algorithm_authorized: bool,
    pub phase7_1_transfer_benchmark_design_recommended: bool,
    pub knowledge_graph_authorized: bool,
    pub autonomous_self_improvement_authorized: bool,
    pub runtime_authorization: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Phase7ArchitectureGuards {
    pub eval_only: bool,
    pub contract_only: bool,
    pub recall_engine_modified: bool,
    pub cognitive_booster_modified: bool,
    pub memory_schema_changed: bool,
    pub memory_written: bool,
    pub pattern_persisted: bool,
    pub pattern_algorithm_implemented: bool,
    pub autonomous_pattern_promotion: bool,
    pub strategy_execution_performed: bool,
    pub runtime_applied: bool,
    pub hermes_integration_performed: bool,
    pub production_claim_authorized: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Phase7CognitiveArchitectureContractReport {
    pub schema_version: u32,
    pub tag: String,
    pub phase: String,
    pub mode: String,
    pub evaluation_version: String,
    pub generated_at: String,
    pub north_star: NorthStarContract,
    pub artifact_ladder: Vec<CognitiveArtifactContract>,
    pub canonical_pattern_candidate: PatternCandidate,
    pub canonical_validation: PatternContractValidation,
    pub invalid_contract_cases: Vec<PatternContractCase>,
    pub lifecycle: Vec<PatternLifecycleTransition>,
    pub confidence_update_policy: ConfidenceUpdatePolicy,
    pub decision: Phase7ArchitectureDecision,
    pub guards: Phase7ArchitectureGuards,
    pub pass: bool,
    pub status: String,
    pub conclusion: String,
}
