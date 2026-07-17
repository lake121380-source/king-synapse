use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::path::PathBuf;
use synapse_eval::{
    construct_shadow_overlay, validate_serialized_shadow_overlay_integrity,
    ConfidenceCalibrationStatus, ExistingMemoryKind, FrozenMemorySnapshot, ProspectiveAtomicUnit,
    ReconstructionInput, ReconstructionStatus, SourceLocator, SupportState,
};

const ALGORITHM_ID: &str = "phase7.4-query-blind-sentence-segmentation-v1";

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
    let mut segmented_cases = Vec::with_capacity(projection.cases.len());
    for case in projection.cases {
        let mut overlays = Vec::with_capacity(case.candidate_memories.len());
        for memory in case.candidate_memories {
            let _pool_ordinal = memory.pool_ordinal;
            let memory_kind = ExistingMemoryKind::parse(&memory.source_memory_kind)
                .map_err(|error| format!("memory_kind_failure:{error}"))?;
            let spans = sentence_spans(&memory.source_memory_content)?;
            if spans.len() != 2 {
                return Err(format!(
                    "expected_two_units:{}:{}",
                    memory.source_memory_id,
                    spans.len()
                ));
            }
            let snapshot = FrozenMemorySnapshot::from_claimed(
                memory.source_memory_id.clone(),
                memory_kind,
                memory.source_memory_content.clone(),
                memory.source_memory_sha256,
                memory.source_memory_content_sha256,
                memory.source_evidence_ids.clone(),
                memory.source_event_ids.clone(),
            );
            let units: Vec<ProspectiveAtomicUnit> = spans
                .iter()
                .enumerate()
                .map(|(ordinal, (start, end))| ProspectiveAtomicUnit {
                    ordinal,
                    claim_text: exact_span(&memory.source_memory_content, *start, *end),
                    source_locator: SourceLocator::SourceMemoryTextSpan {
                        start_char: *start,
                        end_char: *end,
                    },
                    support_state: SupportState::NotAssessable,
                    source_evidence_provenance: memory.source_evidence_ids.clone(),
                    source_event_provenance: memory.source_event_ids.clone(),
                    extraction_confidence: 1.0,
                    support_confidence: 0.0,
                    confidence_calibration_status: ConfidenceCalibrationStatus::NotAssessable,
                    contradiction_links: Vec::new(),
                })
                .collect();
            let overlay = construct_shadow_overlay(
                &snapshot,
                &units,
                &ReconstructionInput {
                    status: ReconstructionStatus::Complete,
                    unresolved_gap_count: 0,
                },
            )
            .map_err(|error| format!("overlay_construction_failure:{error}"))?;
            let canonical = overlay
                .canonical_json()
                .map_err(|error| format!("overlay_serialization_failure:{error}"))?;
            validate_serialized_shadow_overlay_integrity(&canonical)
                .map_err(|error| format!("overlay_integrity_failure:{error}"))?;
            overlays.push(
                serde_json::from_str(&canonical)
                    .map_err(|error| format!("canonical_overlay_json_failure:{error}"))?,
            );
            memory_count += 1;
            atomic_unit_count += units.len();
        }
        segmented_cases.push(SegmentedCase {
            case_id: case.case_id,
            stratum: case.stratum,
            overlays,
        });
    }

    Ok(SegmentationExecution {
        schema_version: 1,
        execution_id: "phase7.4-query-blind-atomic-segmentation-execution-v1",
        status: "PASS_query_blind_atomic_overlays_constructed",
        segmentation_algorithm_id: ALGORITHM_ID,
        overlay_constructor_contract_version: "phase7.4-atomic-evidence-shadow-prototype-v1",
        input_projection_id: projection.projection_id,
        input_projection_sha256: sha256_hex(input_bytes),
        case_count: segmented_cases.len(),
        memory_count,
        atomic_unit_count,
        cases: segmented_cases,
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
        return Err("usage: phase7_4_atomic_segmentation_v1 --input <projection.json>".to_string());
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
        let bytes = fs::read(&path).map_err(|error| format!("input_read_failure:{error}"))?;
        let execution = build_execution(&bytes)?;
        let output = serde_json::to_string(&execution)
            .map_err(|error| format!("execution_serialization_failure:{error}"))?;
        println!("{output}");
        Ok(())
    })();
    if let Err(error) = result {
        eprintln!("{error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::sentence_spans;

    #[test]
    fn sentence_spans_include_terminator_and_following_space() {
        assert_eq!(
            sentence_spans("Alpha. Beta.").unwrap(),
            vec![(0, 7), (7, 12)]
        );
    }

    #[test]
    fn sentence_spans_cover_unicode_scalars() {
        assert_eq!(sentence_spans("甲. Beta.").unwrap(), vec![(0, 3), (3, 8)]);
    }

    #[test]
    fn terminal_question_and_exclamation_are_boundaries() {
        assert_eq!(
            sentence_spans("Ready? Yes!").unwrap(),
            vec![(0, 7), (7, 11)]
        );
    }
}
