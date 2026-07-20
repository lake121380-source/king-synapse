use serde::Deserialize;
use serde_json::{json, Value};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

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
    expected_excluded_entries: Vec<Value>,
    expected_guards: Vec<String>,
    expected_answer_mode: String,
}

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../eval/datasets/phase8")
        .join(name)
}

fn temporary_db_path() -> PathBuf {
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    std::env::temp_dir().join(format!(
        "king-synapse-agent-read-only-{}-{nonce}.sqlite",
        std::process::id()
    ))
}

fn cleanup_db(path: &Path) {
    for suffix in ["", "-wal", "-shm"] {
        let candidate = PathBuf::from(format!("{}{suffix}", path.display()));
        let _ = std::fs::remove_file(candidate);
    }
}

#[test]
fn agent_read_only_stdio_enforces_policy_across_twenty_frozen_cases() {
    let packet =
        fixture("phase8_lcn_v0_1_private_work_task_company_introduction_retrieval_packet_v1.json");
    let suite: RegressionSuite = serde_json::from_slice(
        &std::fs::read(fixture(
            "phase8_lcn_v0_1_governance_regression_cases_v1.json",
        ))
        .unwrap(),
    )
    .unwrap();
    assert_eq!(suite.case_count, 20);
    assert_eq!(suite.cases.len(), 20);

    let db_path = temporary_db_path();
    let mut child = Command::new(env!("CARGO_BIN_EXE_synapse-mcp"))
        .env("KING_SYNAPSE_MCP_TOOL_PROFILE", "agent_read_only")
        .env("KING_SYNAPSE_ENTERPRISE_PACKET", &packet)
        .env("KING_SYNAPSE_DB", &db_path)
        .env("RUST_LOG", "off")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();

    let mut stdin = child.stdin.take().unwrap();
    writeln!(
        stdin,
        "{}",
        json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{}})
    )
    .unwrap();
    writeln!(
        stdin,
        "{}",
        json!({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
    )
    .unwrap();
    for (index, case) in suite.cases.iter().enumerate() {
        writeln!(
            stdin,
            "{}",
            json!({
                "jsonrpc": "2.0",
                "id": 100 + index,
                "method": "tools/call",
                "params": {
                    "name": "synapse_enterprise_shadow",
                    "arguments": {"question": case.query}
                }
            })
        )
        .unwrap();
    }
    writeln!(
        stdin,
        "{}",
        json!({
            "jsonrpc": "2.0",
            "id": 999,
            "method": "tools/call",
            "params": {
                "name": "synapse_write",
                "arguments": {"content": "must not persist"}
            }
        })
    )
    .unwrap();
    drop(stdin);

    let output = child.wait_with_output().unwrap();
    cleanup_db(&db_path);
    assert!(output.status.success());
    let responses = String::from_utf8(output.stdout)
        .unwrap()
        .lines()
        .map(|line| serde_json::from_str::<Value>(line).unwrap())
        .collect::<Vec<_>>();

    let tools = responses
        .iter()
        .find(|response| response["id"] == 2)
        .unwrap()["result"]["tools"]
        .as_array()
        .unwrap()
        .iter()
        .map(|descriptor| descriptor["name"].as_str().unwrap())
        .collect::<Vec<_>>();
    assert_eq!(
        tools,
        vec![
            "synapse_recall",
            "synapse_trace",
            "synapse_enterprise_shadow"
        ]
    );

    for (index, case) in suite.cases.iter().enumerate() {
        let response = responses
            .iter()
            .find(|response| response["id"] == 100 + index)
            .unwrap();
        let trace = &response["result"]["structuredContent"]["trace"];
        let candidate_ids = trace["candidate_entries"]
            .as_array()
            .unwrap()
            .iter()
            .map(|candidate| candidate["entry_id"].as_str().unwrap().to_string())
            .collect::<Vec<_>>();
        assert_eq!(
            candidate_ids, case.expected_candidate_entry_ids,
            "{} candidate entries",
            case.case_id
        );
        assert_eq!(
            trace["selected_entries"],
            json!(case.expected_selected_entry_ids),
            "{} selected entries",
            case.case_id
        );
        assert_eq!(
            trace["excluded_entries"],
            json!(case.expected_excluded_entries),
            "{} excluded entries",
            case.case_id
        );
        assert_eq!(
            trace["applied_guards"],
            json!(case.expected_guards),
            "{} guards",
            case.case_id
        );
        assert_eq!(
            trace["answer_mode"], case.expected_answer_mode,
            "{} answer mode",
            case.case_id
        );
        assert_eq!(trace["runtime_write"], false, "{} write", case.case_id);
        assert_eq!(
            trace["external_provider_called"], false,
            "{} provider",
            case.case_id
        );
        assert_eq!(
            trace["candidate_or_network_modified"], false,
            "{} mutation",
            case.case_id
        );
    }

    let write_error = responses
        .iter()
        .find(|response| response["id"] == 999)
        .unwrap()["error"]["message"]
        .as_str()
        .unwrap();
    assert!(write_error.contains("not permitted"));
}
