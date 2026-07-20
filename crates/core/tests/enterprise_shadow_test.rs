use serde::Deserialize;
use std::path::PathBuf;
use synapse_core::{EnterpriseExcludedEntry, EnterpriseShadowEngine};

#[derive(Debug, Deserialize)]
struct RegressionSuite {
    case_count: usize,
    cases: Vec<RegressionCase>,
}

#[derive(Debug, Deserialize)]
struct RegressionCase {
    case_id: String,
    query: String,
    expected_candidate_entry_ids: Vec<String>,
    expected_selected_entry_ids: Vec<String>,
    expected_excluded_entries: Vec<EnterpriseExcludedEntry>,
    expected_guards: Vec<String>,
    expected_answer_mode: String,
}

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../eval/datasets/phase8")
        .join(name)
}

fn engine() -> EnterpriseShadowEngine {
    EnterpriseShadowEngine::from_path(fixture(
        "phase8_lcn_v0_1_private_work_task_company_introduction_retrieval_packet_v1.json",
    ))
    .unwrap()
}

#[test]
fn rust_runtime_matches_all_twenty_frozen_governance_traces() {
    let suite: RegressionSuite = serde_json::from_slice(
        &std::fs::read(fixture(
            "phase8_lcn_v0_1_governance_regression_cases_v1.json",
        ))
        .unwrap(),
    )
    .unwrap();
    assert_eq!(suite.case_count, 20);
    assert_eq!(suite.cases.len(), 20);

    let engine = engine();
    for case in suite.cases {
        let response = engine.execute(&case.query).unwrap();
        let trace = response.trace;
        let candidate_ids = trace
            .candidate_entries
            .iter()
            .map(|entry| entry.entry_id.clone())
            .collect::<Vec<_>>();
        assert_eq!(
            candidate_ids, case.expected_candidate_entry_ids,
            "{} candidate entries",
            case.case_id
        );
        assert_eq!(
            trace.selected_entries, case.expected_selected_entry_ids,
            "{} selected entries",
            case.case_id
        );
        assert_eq!(
            trace.excluded_entries, case.expected_excluded_entries,
            "{} excluded entries",
            case.case_id
        );
        assert_eq!(
            trace.applied_guards, case.expected_guards,
            "{} guards",
            case.case_id
        );
        assert_eq!(
            trace.answer_mode, case.expected_answer_mode,
            "{} answer mode",
            case.case_id
        );
        assert_eq!(
            trace.evidence_basis.len(),
            trace.selected_entries.len(),
            "{} evidence basis",
            case.case_id
        );
        assert!(!trace.runtime_write, "{} runtime write", case.case_id);
        assert!(
            !trace.source_document_filesystem_read_during_generation,
            "{} source read",
            case.case_id
        );
        assert!(
            !trace.external_provider_called,
            "{} provider call",
            case.case_id
        );
        assert!(
            !trace.candidate_or_network_modified,
            "{} network mutation",
            case.case_id
        );
    }
}

#[test]
fn enterprise_shadow_is_deterministic_and_read_only() {
    let engine = engine();
    let first = engine.execute("公司套餐多少钱？").unwrap();
    let second = engine.execute("公司套餐多少钱？").unwrap();
    assert_eq!(first, second);
    assert!(!first.trace.runtime_write);
    assert_eq!(first.trace.answer_mode, "shadow_draft");
    assert!(first.answer.contains("1,980元/月"));
    assert!(first.answer.contains("人工确认"));
}

#[test]
fn enterprise_shadow_rejects_packets_with_source_documents() {
    let packet_path =
        fixture("phase8_lcn_v0_1_private_work_task_company_introduction_retrieval_packet_v1.json");
    let mut packet: serde_json::Value =
        serde_json::from_slice(&std::fs::read(packet_path).unwrap()).unwrap();
    packet["source_documents_in_packet"] = serde_json::json!(["private-source.md"]);
    let body = serde_json::to_vec(&packet).unwrap();
    let error = EnterpriseShadowEngine::from_slice(&body).unwrap_err();
    assert!(error
        .to_string()
        .contains("must not contain source documents"));
}

#[test]
fn enterprise_shadow_rejects_empty_questions() {
    let error = engine().execute("  ").unwrap_err();
    assert!(error.to_string().contains("must not be empty"));
}
