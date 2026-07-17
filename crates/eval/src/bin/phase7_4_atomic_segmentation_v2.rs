use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::env;
use std::fs;
use std::path::PathBuf;

const ALGORITHM_ID: &str = "phase7.4-query-blind-sentence-segmentation-v1";
const CONTRACT_VERSION: &str = "phase7.4-query-blind-sentence-segmentation-overlay-v2";

#[derive(Debug, Deserialize)]
struct Projection {
    projection_id: String,
    cases: Vec<ProjectionCase>,
    query_fields_copied: bool,
    gold_or_reference_fields_copied: bool,
    atomic_or_arm_fields_copied: bool,
    phase7_3_3_d_content_loaded: bool,
    provider_called: bool,
    network_used: bool,
    runtime_accessed: bool,
    selected_effect_dataset_opened_for_arm_execution: bool,
}

#[derive(Debug, Deserialize)]
struct ProjectionCase {
    case_id: String,
    stratum: String,
    candidate_memories: Vec<ProjectionMemory>,
}

#[derive(Debug, Deserialize)]
struct ProjectionMemory {
    pool_ordinal: usize,
    source_memory_id: String,
    source_memory_kind: String,
    source_memory_content: String,
    source_memory_content_sha256: String,
    source_memory_sha256: String,
    source_evidence_ids: Vec<String>,
    source_event_ids: Vec<String>,
}

#[derive(Debug, Serialize)]
struct SegmentationExecution {
    schema_version: u8,
    execution_id: &'static str,
    status: &'static str,
    segmentation_algorithm_id: &'static str,
    overlay_constructor_contract_version: &'static str,
    input_projection_id: String,
    input_projection_sha256: String,
    case_count: usize,
    memory_count: usize,
    atomic_unit_count: usize,
    cases: Vec<SegmentedCase>,
    query_access_count: usize,
    gold_or_reference_access_count: usize,
    arm_output_access_count: usize,
    phase7_3_3_d_content_access_count: usize,
    provider_call_count: usize,
    network_access_count: usize,
    runtime_access_count: usize,
    store_write_count: usize,
    recall_engine_access_count: usize,
    selected_effect_dataset_opened_for_arm_execution: bool,
    runtime_integration_authorized: bool,
}

#[derive(Debug, Serialize)]
struct SegmentedCase {
    case_id: String,
    stratum: String,
    overlays: Vec<Value>,
}

fn sha256_hex(value: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(value);
    format!("{:x}", hasher.finalize())
}

fn canonical_json(value: &Value) -> String {
    match value {
        Value::Null => "null".to_string(),
        Value::Bool(value) => value.to_string(),
        Value::Number(value) => value.to_string(),
        Value::String(value) => serde_json::to_string(value).expect("string serialization"),
        Value::Array(values) => format!(
            "[{}]",
            values
                .iter()
                .map(canonical_json)
                .collect::<Vec<_>>()
                .join(",")
        ),
        Value::Object(values) => {
            let mut keys: Vec<&String> = values.keys().collect();
            keys.sort_unstable();
            let body = keys
                .into_iter()
                .map(|key| {
                    format!(
                        "{}:{}",
                        serde_json::to_string(key).expect("key serialization"),
                        canonical_json(&values[key])
                    )
                })
                .collect::<Vec<_>>()
                .join(",");
            format!("{{{body}}}")
        }
    }
}

fn authoring_memory_hash(memory: &ProjectionMemory) -> String {
    let mut evidence = memory.source_evidence_ids.clone();
    let mut events = memory.source_event_ids.clone();
    evidence.sort_unstable();
    events.sort_unstable();
    let material = json!({
        "source_memory_content_sha256": memory.source_memory_content_sha256,
        "source_memory_id": memory.source_memory_id,
        "source_memory_kind": memory.source_memory_kind,
        "source_evidence_ids_sorted": evidence,
        "source_event_ids_sorted": events,
    });
    sha256_hex(canonical_json(&material).as_bytes())
}

fn sentence_spans(source: &str) -> Result<Vec<(usize, usize)>, String> {
    let characters: Vec<char> = source.chars().collect();
    let mut spans = Vec::new();
    let mut start = 0;
    let mut cursor = 0;
    while cursor < characters.len() {
        let terminator = matches!(characters[cursor], '.' | '?' | '!');
        let followed_by_boundary = cursor + 1 == characters.len()
            || characters
                .get(cursor + 1)
                .is_some_and(|character| character.is_whitespace());
        if terminator && followed_by_boundary {
            let mut end = cursor + 1;
            while end < characters.len() && characters[end].is_whitespace() {
                end += 1;
            }
            if start >= end {
                return Err("empty_sentence_span".to_string());
            }
            spans.push((start, end));
            start = end;
            cursor = end;
        } else {
            cursor += 1;
        }
    }
    if start < characters.len() {
        spans.push((start, characters.len()));
    }
    if spans.is_empty() {
        return Err("zero_sentence_spans".to_string());
    }
    let mut expected_start = 0;
    for (span_start, span_end) in &spans {
        if *span_start != expected_start || span_start >= span_end || *span_end > characters.len() {
            return Err("sentence_span_coverage_failure".to_string());
        }
        expected_start = *span_end;
    }
    if expected_start != characters.len() {
        return Err("sentence_span_trailing_gap".to_string());
    }
    Ok(spans)
}

fn exact_span(source: &str, start: usize, end: usize) -> String {
    source.chars().skip(start).take(end - start).collect()
}

fn validate_unique_nonempty(values: &[String], field: &str) -> Result<(), String> {
    if values.is_empty() || values.iter().any(String::is_empty) {
        return Err(format!("empty_{field}"));
    }
    let unique: HashSet<&str> = values.iter().map(String::as_str).collect();
    if unique.len() != values.len() {
        return Err(format!("duplicate_{field}"));
    }
    Ok(())
}

fn construct_overlay(memory: &ProjectionMemory) -> Result<Value, String> {
    let _pool_ordinal = memory.pool_ordinal;
    if !matches!(
        memory.source_memory_kind.as_str(),
        "fact" | "preference" | "failure" | "playbook" | "state"
    ) {
        return Err("invalid_memory_kind".to_string());
    }
    if sha256_hex(memory.source_memory_content.as_bytes()) != memory.source_memory_content_sha256 {
        return Err("source_memory_content_hash_mismatch".to_string());
    }
    if authoring_memory_hash(memory) != memory.source_memory_sha256 {
        return Err("authoring_source_memory_hash_mismatch".to_string());
    }
    validate_unique_nonempty(&memory.source_evidence_ids, "source_evidence_ids")?;
    validate_unique_nonempty(&memory.source_event_ids, "source_event_ids")?;
    let spans = sentence_spans(&memory.source_memory_content)?;
    if spans.len() != 2 {
        return Err(format!(
            "expected_two_units:{}:{}",
            memory.source_memory_id,
            spans.len()
        ));
    }
    let overlay_id = format!(
        "aes-v1-{}",
        sha256_hex(
            format!(
                "phase7.4|{}|{}|{}",
                memory.source_memory_id, memory.source_memory_sha256, CONTRACT_VERSION
            )
            .as_bytes()
        )
    );
    let atomic_units: Vec<Value> = spans
        .iter()
        .enumerate()
        .map(|(ordinal, (start, end))| {
            let claim_text = exact_span(&memory.source_memory_content, *start, *end);
            let claim_text_sha256 = sha256_hex(claim_text.as_bytes());
            let atomic_claim_id = format!(
                "aes-claim-v1-{}",
                sha256_hex(format!("{overlay_id}|{ordinal}|{claim_text_sha256}").as_bytes())
            );
            json!({
                "atomic_claim_id": atomic_claim_id,
                "ordinal": ordinal,
                "claim_text": claim_text,
                "claim_text_sha256": claim_text_sha256,
                "source_locator": {
                    "locator_type": "source_memory_text_span",
                    "start_char": start,
                    "end_char": end,
                },
                "support_state": "not_assessable",
                "provenance": {
                    "source_memory_id": memory.source_memory_id,
                    "source_memory_sha256": memory.source_memory_sha256,
                    "source_evidence_ids": memory.source_evidence_ids,
                    "source_event_ids": memory.source_event_ids,
                },
                "confidence": {
                    "extraction_confidence": 1.0,
                    "support_confidence": 0.0,
                    "calibration_status": "not_assessable",
                },
                "contradiction_links": [],
            })
        })
        .collect();
    let ordered_atomic_claim_ids: Vec<&str> = atomic_units
        .iter()
        .map(|unit| {
            unit["atomic_claim_id"]
                .as_str()
                .expect("constructed claim ID is a string")
        })
        .collect();
    let overlay = json!({
        "schema_version": 2,
        "overlay_id": overlay_id,
        "status": "eval_only_formal_atomic_overlay",
        "source_memory_id": memory.source_memory_id,
        "source_memory_sha256": memory.source_memory_sha256,
        "source_memory_content_sha256": memory.source_memory_content_sha256,
        "source_memory_kind": memory.source_memory_kind,
        "segmentation_contract_version": CONTRACT_VERSION,
        "atomic_units": atomic_units,
        "reconstruction": {
            "source_memory_id": memory.source_memory_id,
            "ordered_atomic_claim_ids": ordered_atomic_claim_ids,
            "status": "complete",
            "deterministic": true,
            "overlap_characters": 0,
            "unresolved_gap_count": 0,
        },
        "authority": {
            "eval_only": true,
            "runtime_applied": false,
            "memory_mutated": false,
            "store_written": false,
            "recall_engine_mutated": false,
            "promotion_authorized": false,
        },
    });
    validate_overlay(&overlay, memory)?;
    Ok(overlay)
}

fn validate_overlay(overlay: &Value, memory: &ProjectionMemory) -> Result<(), String> {
    if overlay["source_memory_sha256"].as_str() != Some(&memory.source_memory_sha256)
        || overlay["source_memory_id"].as_str() != Some(&memory.source_memory_id)
        || overlay["segmentation_contract_version"].as_str() != Some(CONTRACT_VERSION)
        || overlay["status"].as_str() != Some("eval_only_formal_atomic_overlay")
    {
        return Err("formal_overlay_root_mismatch".to_string());
    }
    let expected_overlay_id = format!(
        "aes-v1-{}",
        sha256_hex(
            format!(
                "phase7.4|{}|{}|{}",
                memory.source_memory_id, memory.source_memory_sha256, CONTRACT_VERSION
            )
            .as_bytes()
        )
    );
    if overlay["overlay_id"].as_str() != Some(&expected_overlay_id) {
        return Err("formal_overlay_id_mismatch".to_string());
    }
    let units = overlay["atomic_units"]
        .as_array()
        .ok_or_else(|| "formal_atomic_units_not_array".to_string())?;
    let mut cursor = 0;
    let mut ordered = Vec::new();
    for (ordinal, unit) in units.iter().enumerate() {
        let start = unit["source_locator"]["start_char"]
            .as_u64()
            .ok_or_else(|| "formal_start_missing".to_string())? as usize;
        let end = unit["source_locator"]["end_char"]
            .as_u64()
            .ok_or_else(|| "formal_end_missing".to_string())? as usize;
        if start != cursor || start >= end {
            return Err("formal_span_coverage_failure".to_string());
        }
        let claim_text = exact_span(&memory.source_memory_content, start, end);
        let claim_hash = sha256_hex(claim_text.as_bytes());
        let expected_claim_id = format!(
            "aes-claim-v1-{}",
            sha256_hex(format!("{expected_overlay_id}|{ordinal}|{claim_hash}").as_bytes())
        );
        if unit["ordinal"].as_u64() != Some(ordinal as u64)
            || unit["claim_text"].as_str() != Some(&claim_text)
            || unit["claim_text_sha256"].as_str() != Some(&claim_hash)
            || unit["atomic_claim_id"].as_str() != Some(&expected_claim_id)
            || unit["support_state"].as_str() != Some("not_assessable")
            || unit["provenance"]["source_evidence_ids"] != json!(memory.source_evidence_ids)
            || unit["provenance"]["source_event_ids"] != json!(memory.source_event_ids)
        {
            return Err("formal_atomic_unit_mismatch".to_string());
        }
        ordered.push(expected_claim_id);
        cursor = end;
    }
    if cursor != memory.source_memory_content.chars().count()
        || overlay["reconstruction"]["ordered_atomic_claim_ids"] != json!(ordered)
        || overlay["reconstruction"]["status"].as_str() != Some("complete")
        || overlay["reconstruction"]["unresolved_gap_count"].as_u64() != Some(0)
        || overlay["authority"]
            != json!({
                "eval_only": true,
                "runtime_applied": false,
                "memory_mutated": false,
                "store_written": false,
                "recall_engine_mutated": false,
                "promotion_authorized": false,
            })
    {
        return Err("formal_reconstruction_or_authority_mismatch".to_string());
    }
    Ok(())
}

fn build_execution(input_bytes: &[u8]) -> Result<SegmentationExecution, String> {
    let projection: Projection = serde_json::from_slice(input_bytes)
        .map_err(|error| format!("projection_json_failure:{error}"))?;
    if projection.query_fields_copied
        || projection.gold_or_reference_fields_copied
        || projection.atomic_or_arm_fields_copied
        || projection.phase7_3_3_d_content_loaded
        || projection.provider_called
        || projection.network_used
        || projection.runtime_accessed
        || projection.selected_effect_dataset_opened_for_arm_execution
    {
        return Err("projection_authority_or_blindness_failure".to_string());
    }
    let mut memory_count = 0;
    let mut atomic_unit_count = 0;
    let mut cases = Vec::with_capacity(projection.cases.len());
    for case in projection.cases {
        let mut overlays = Vec::with_capacity(case.candidate_memories.len());
        for memory in case.candidate_memories {
            let overlay = construct_overlay(&memory)?;
            atomic_unit_count += overlay["atomic_units"]
                .as_array()
                .expect("constructed units")
                .len();
            memory_count += 1;
            overlays.push(overlay);
        }
        cases.push(SegmentedCase {
            case_id: case.case_id,
            stratum: case.stratum,
            overlays,
        });
    }
    Ok(SegmentationExecution {
        schema_version: 2,
        execution_id: "phase7.4-query-blind-atomic-segmentation-execution-v2",
        status: "PASS_query_blind_formal_atomic_overlays_constructed",
        segmentation_algorithm_id: ALGORITHM_ID,
        overlay_constructor_contract_version: CONTRACT_VERSION,
        input_projection_id: projection.projection_id,
        input_projection_sha256: sha256_hex(input_bytes),
        case_count: cases.len(),
        memory_count,
        atomic_unit_count,
        cases,
        query_access_count: 0,
        gold_or_reference_access_count: 0,
        arm_output_access_count: 0,
        phase7_3_3_d_content_access_count: 0,
        provider_call_count: 0,
        network_access_count: 0,
        runtime_access_count: 0,
        store_write_count: 0,
        recall_engine_access_count: 0,
        selected_effect_dataset_opened_for_arm_execution: false,
        runtime_integration_authorized: false,
    })
}

fn parse_input_path() -> Result<PathBuf, String> {
    let mut args = env::args_os().skip(1);
    if args.next().as_deref() != Some(std::ffi::OsStr::new("--input")) {
        return Err("usage: phase7_4_atomic_segmentation_v2 --input <projection.json>".to_string());
    }
    let path = args
        .next()
        .ok_or_else(|| "missing_input_path".to_string())?;
    if args.next().is_some() {
        return Err("unexpected_extra_arguments".to_string());
    }
    Ok(PathBuf::from(path))
}

fn main() {
    let result = (|| -> Result<(), String> {
        let path = parse_input_path()?;
        let bytes = fs::read(path).map_err(|error| format!("input_read_failure:{error}"))?;
        let execution = build_execution(&bytes)?;
        println!(
            "{}",
            serde_json::to_string(&execution)
                .map_err(|error| format!("execution_serialization_failure:{error}"))?
        );
        Ok(())
    })();
    if let Err(error) = result {
        eprintln!("{error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::{authoring_memory_hash, sentence_spans, ProjectionMemory};

    fn fixture_memory() -> ProjectionMemory {
        let mut memory = ProjectionMemory {
            pool_ordinal: 0,
            source_memory_id: "memory-1".to_string(),
            source_memory_kind: "fact".to_string(),
            source_memory_content: "Alpha. Beta.".to_string(),
            source_memory_content_sha256:
                "b1b9260eb57aa35238b1064ff3cf68a14b1e103115eb98a2cdb178f0ce5b85d7".to_string(),
            source_memory_sha256: String::new(),
            source_evidence_ids: vec!["evidence-2".to_string(), "evidence-1".to_string()],
            source_event_ids: vec!["event-2".to_string(), "event-1".to_string()],
        };
        memory.source_memory_sha256 = authoring_memory_hash(&memory);
        memory
    }

    #[test]
    fn sentence_spans_match_frozen_v1_algorithm() {
        assert_eq!(
            sentence_spans("Alpha. Beta.").unwrap(),
            vec![(0, 7), (7, 12)]
        );
        assert_eq!(sentence_spans("甲. Beta.").unwrap(), vec![(0, 3), (3, 8)]);
    }

    #[test]
    fn authoring_hash_sorts_evidence_and_event_values() {
        let first = fixture_memory();
        let mut second = fixture_memory();
        second.source_evidence_ids.reverse();
        second.source_event_ids.reverse();
        assert_eq!(
            authoring_memory_hash(&first),
            authoring_memory_hash(&second)
        );
    }

    #[test]
    fn authoring_hash_is_stable() {
        let memory = fixture_memory();
        assert_eq!(memory.source_memory_sha256, authoring_memory_hash(&memory));
    }
}
