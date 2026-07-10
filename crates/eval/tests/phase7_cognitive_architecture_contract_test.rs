use serde_json::Value;
use std::{fs, path::PathBuf};
use synapse_eval::{
    validate_pattern_candidate, PatternStatus, Phase7CognitiveArchitectureContractEvaluator,
};

fn fresh_report() -> synapse_eval::Phase7CognitiveArchitectureContractReport {
    Phase7CognitiveArchitectureContractEvaluator::evaluate("phase7-contract-test")
        .expect("Phase 7.0 report")
}

fn checked_report_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("reports/phase7_cognitive_architecture_contract.json")
}

#[test]
fn phase7_north_star_moves_the_mainline_from_retrieval_to_experience_to_pattern() {
    let report = fresh_report();
    assert!(report.pass);
    assert!(report
        .north_star
        .mainline
        .starts_with(&["experience".to_string(), "evidence".to_string()]));
    assert!(report
        .north_star
        .mainline
        .contains(&"pattern_candidate".to_string()));
    assert!(report
        .north_star
        .mainline
        .contains(&"knowledge_evolution".to_string()));
    assert!(report.decision.experience_to_pattern_mainline_authorized);
    assert!(!report.decision.retrieval_booster_mainline_continued);
}

#[test]
fn canonical_pattern_candidate_is_grounded_scoped_and_falsifiable() {
    let report = fresh_report();
    let candidate = &report.canonical_pattern_candidate;
    assert_eq!(candidate.status, PatternStatus::Proposed);
    assert!(candidate.supporting_evidence.len() >= 2);
    assert!(candidate.counterexample_search_performed);
    assert!(!candidate.applicability_conditions.is_empty());
    assert!(!candidate.predictions.is_empty());
    assert!(!candidate.falsification_conditions.is_empty());
    assert!(validate_pattern_candidate(candidate).valid);
}

#[test]
fn contract_rejects_missing_grounding_scope_falsification_and_counterexample_search() {
    let report = fresh_report();
    let failed = report
        .invalid_contract_cases
        .iter()
        .map(|case| case.name.as_str())
        .collect::<Vec<_>>();
    assert!(failed.contains(&"missing_supporting_evidence"));
    assert!(failed.contains(&"missing_applicability_scope"));
    assert!(failed.contains(&"missing_falsification_condition"));
    assert!(failed.contains(&"counterexample_search_not_performed"));
    assert!(report
        .invalid_contract_cases
        .iter()
        .all(|case| case.expectation_met && !case.observed_valid));
}

#[test]
fn confidence_is_bounded_and_cannot_grow_from_usage_alone() {
    let report = fresh_report();
    assert!(report
        .invalid_contract_cases
        .iter()
        .any(|case| case.name == "invalid_confidence" && case.expectation_met));
    assert!(report
        .confidence_update_policy
        .prohibited_sources
        .contains(&"usage_count_without_outcome".to_string()));
    assert!(report
        .confidence_update_policy
        .prohibited_sources
        .contains(&"model_self_assertion".to_string()));
    assert!(report
        .confidence_update_policy
        .allowed_sources
        .contains(&"observed_transfer_outcome".to_string()));
}

#[test]
fn non_proposed_status_requires_validation_outcomes() {
    let report = fresh_report();
    let case = report
        .invalid_contract_cases
        .iter()
        .find(|case| case.name == "premature_active_status")
        .expect("premature active case");
    assert!(!case.observed_valid);
    assert!(case
        .violations
        .contains(&"non_proposed_status_requires_validation_outcome".to_string()));
}

#[test]
fn lifecycle_transitions_are_never_autonomous() {
    let report = fresh_report();
    assert_eq!(report.lifecycle.len(), 7);
    assert!(report
        .lifecycle
        .iter()
        .all(|transition| !transition.autonomous && transition.requires_explicit_evaluation_gate));
}

#[test]
fn no_cognitive_artifact_has_runtime_authority_in_phase7_0() {
    let report = fresh_report();
    assert!(report
        .artifact_ladder
        .iter()
        .all(|artifact| !artifact.runtime_authority));
    assert!(!report.decision.pattern_discovery_algorithm_authorized);
    assert!(!report.decision.knowledge_graph_authorized);
    assert!(!report.decision.autonomous_self_improvement_authorized);
    assert!(!report.decision.runtime_authorization);
}

#[test]
fn phase7_0_preserves_runtime_storage_and_hermes_boundaries() {
    let report = fresh_report();
    assert!(report.guards.eval_only);
    assert!(report.guards.contract_only);
    assert!(!report.guards.recall_engine_modified);
    assert!(!report.guards.cognitive_booster_modified);
    assert!(!report.guards.memory_schema_changed);
    assert!(!report.guards.memory_written);
    assert!(!report.guards.pattern_persisted);
    assert!(!report.guards.pattern_algorithm_implemented);
    assert!(!report.guards.autonomous_pattern_promotion);
    assert!(!report.guards.strategy_execution_performed);
    assert!(!report.guards.runtime_applied);
    assert!(!report.guards.hermes_integration_performed);
    assert!(!report.guards.production_claim_authorized);
}

#[test]
fn checked_report_preserves_phase7_claim_boundary() {
    let source = fs::read_to_string(checked_report_path()).expect("checked Phase 7.0 report");
    let value: Value = serde_json::from_str(&source).expect("valid Phase 7.0 JSON");
    assert_eq!(value["status"], "PASS");
    assert_eq!(value["mode"], "eval_only_contract");
    assert_eq!(
        value["decision"]["experience_to_pattern_mainline_authorized"],
        true
    );
    assert_eq!(
        value["decision"]["pattern_discovery_algorithm_authorized"],
        false
    );
    assert_eq!(value["guards"]["pattern_persisted"], false);
    assert_eq!(value["guards"]["runtime_applied"], false);
    assert_eq!(value["guards"]["production_claim_authorized"], false);
}
