use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

pub const LABELS: [&str; 4] = [
    "supported",
    "partially_supported",
    "unsupported",
    "not_assessable",
];
pub const CONFIDENCE_LEVELS: [&str; 3] = ["low", "medium", "high"];

#[derive(Clone, Debug)]
pub struct SupportAgreementPaths {
    pub protocol: PathBuf,
    pub reviewer_a: PathBuf,
    pub reviewer_b: PathBuf,
    pub support_packet: PathBuf,
    pub boundary_gold: PathBuf,
    pub execution_outcome: PathBuf,
    pub analyzer_source: PathBuf,
    pub binary_source: PathBuf,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ArtifactRef {
    path: String,
    sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ProtocolGuards {
    raw_independent_submissions_only: bool,
    adjudication_used: bool,
    support_gold_visible: bool,
    held_out_accessed: bool,
    support_gold_freeze_allowed: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct SupportAgreementProtocol {
    schema_version: u64,
    protocol_id: String,
    phase: String,
    status: String,
    purpose: String,
    expected_claim_count: usize,
    label_order: Vec<String>,
    confidence_order: Vec<String>,
    artifact_lineage: BTreeMap<String, ArtifactRef>,
    reviewer_b_packet_sha256: String,
    severity_policy: Value,
    diagnostic_policy: Value,
    worklist_policy: Value,
    guards: ProtocolGuards,
}

#[derive(Clone, Debug)]
pub struct SupportAgreementArtifacts {
    pub report: Value,
    pub worklist: Value,
}

fn read_json(path: &Path) -> Result<Value> {
    let bytes = fs::read(path).with_context(|| format!("read {}", path.display()))?;
    serde_json::from_slice(&bytes).with_context(|| format!("parse {}", path.display()))
}

pub fn sha256_file(path: &Path) -> Result<String> {
    let bytes = fs::read(path).with_context(|| format!("read {}", path.display()))?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
}

fn array<'a>(value: &'a Value, field: &str) -> Result<&'a Vec<Value>> {
    value
        .get(field)
        .and_then(Value::as_array)
        .with_context(|| format!("missing_or_invalid_array:{field}"))
}

fn string<'a>(value: &'a Value, field: &str) -> Result<&'a str> {
    value
        .get(field)
        .and_then(Value::as_str)
        .with_context(|| format!("missing_or_invalid_string:{field}"))
}

fn boolean(value: &Value, field: &str) -> Result<bool> {
    value
        .get(field)
        .and_then(Value::as_bool)
        .with_context(|| format!("missing_or_invalid_bool:{field}"))
}

fn string_set(value: &Value, field: &str) -> Result<BTreeSet<String>> {
    let values = array(value, field)?;
    let mut out = BTreeSet::new();
    for item in values {
        let text = item
            .as_str()
            .with_context(|| format!("non_string_item:{field}"))?;
        if !out.insert(text.to_string()) {
            bail!("duplicate_item:{field}:{text}");
        }
    }
    Ok(out)
}

fn jaccard(left: &BTreeSet<String>, right: &BTreeSet<String>) -> f64 {
    if left.is_empty() && right.is_empty() {
        return 1.0;
    }
    let intersection = left.intersection(right).count() as f64;
    let union = left.union(right).count() as f64;
    intersection / union
}

pub fn disagreement_severity(left: &str, right: &str) -> Result<u64> {
    if left == right {
        return Ok(0);
    }
    if !LABELS.contains(&left) || !LABELS.contains(&right) {
        bail!("unknown_support_label:{left}:{right}");
    }
    if left == "not_assessable" || right == "not_assessable" {
        return Ok(3);
    }
    let pair = BTreeSet::from([left, right]);
    if pair == BTreeSet::from(["supported", "unsupported"]) {
        Ok(2)
    } else {
        Ok(1)
    }
}

fn cohen_kappa(
    left_counts: &BTreeMap<String, usize>,
    right_counts: &BTreeMap<String, usize>,
    agreement_count: usize,
    total: usize,
    categories: &[&str],
) -> Option<(f64, f64, f64)> {
    if total == 0 {
        return None;
    }
    let n = total as f64;
    let observed = agreement_count as f64 / n;
    let expected = categories
        .iter()
        .map(|label| {
            *left_counts.get(*label).unwrap_or(&0) as f64
                * *right_counts.get(*label).unwrap_or(&0) as f64
                / (n * n)
        })
        .sum::<f64>();
    if (1.0 - expected).abs() < f64::EPSILON {
        None
    } else {
        Some((observed, expected, (observed - expected) / (1.0 - expected)))
    }
}

fn priority(left: &str, right: &str) -> Result<(u64, &'static str)> {
    let pair = BTreeSet::from([left, right]);
    if left != right && pair.contains("not_assessable") {
        Ok((1, "not_assessable_mismatch"))
    } else if pair == BTreeSet::from(["supported", "unsupported"]) {
        Ok((2, "supported_vs_unsupported"))
    } else if pair == BTreeSet::from(["partially_supported", "unsupported"]) {
        Ok((3, "partially_supported_vs_unsupported"))
    } else if pair == BTreeSet::from(["supported", "partially_supported"]) {
        Ok((4, "supported_vs_partially_supported"))
    } else {
        bail!("unsupported_priority_pair:{left}:{right}")
    }
}

fn verify_artifact(protocol: &SupportAgreementProtocol, key: &str, path: &Path) -> Result<String> {
    let reference = protocol
        .artifact_lineage
        .get(key)
        .with_context(|| format!("protocol_missing_artifact:{key}"))?;
    let actual = sha256_file(path)?;
    if actual != reference.sha256 {
        bail!(
            "artifact_hash_mismatch:{key}:expected={}:actual={actual}",
            reference.sha256
        );
    }
    Ok(actual)
}

fn validate_protocol(protocol: &SupportAgreementProtocol) -> Result<()> {
    if protocol.schema_version != 1
        || protocol.status != "frozen_before_agreement_computation"
        || protocol.expected_claim_count != 118
        || protocol.label_order != LABELS.map(str::to_string)
        || protocol.confidence_order != CONFIDENCE_LEVELS.map(str::to_string)
        || !protocol.guards.raw_independent_submissions_only
        || protocol.guards.adjudication_used
        || protocol.guards.support_gold_visible
        || protocol.guards.held_out_accessed
        || protocol.guards.support_gold_freeze_allowed
    {
        bail!("support_agreement_protocol_invalid");
    }
    for key in [
        "reviewer_a_submission",
        "reviewer_b_submission",
        "support_packet",
        "boundary_gold",
        "support_execution_outcome",
        "analyzer_source",
        "binary_source",
    ] {
        if !protocol.artifact_lineage.contains_key(key) {
            bail!("support_agreement_protocol_missing_artifact:{key}");
        }
    }
    Ok(())
}

fn validate_submission(
    submission: &Value,
    expected_reviewer: &str,
    expected_claim_count: usize,
) -> Result<Vec<String>> {
    if string(submission, "reviewer_id")? != expected_reviewer
        || !boolean(submission, "completed")?
        || string(submission, "status")? != "completed_independent_support_review"
        || !boolean(submission, "blind_to_other_reviewer")?
        || !boolean(submission, "blind_to_candidate_gold_or_silver")?
        || boolean(submission, "held_out_accessed")?
    {
        bail!("submission_contract_invalid:{expected_reviewer}");
    }
    let claims = array(submission, "claims")?;
    if claims.len() != expected_claim_count {
        bail!(
            "submission_claim_count_mismatch:{expected_reviewer}:{}",
            claims.len()
        );
    }
    let mut ids = Vec::with_capacity(claims.len());
    let mut unique = BTreeSet::new();
    for claim in claims {
        let id = string(claim, "boundary_claim_id")?.to_string();
        if !unique.insert(id.clone()) {
            bail!("duplicate_boundary_claim_id:{expected_reviewer}:{id}");
        }
        let label = string(claim, "support_label")?;
        if !LABELS.contains(&label) {
            bail!("invalid_support_label:{expected_reviewer}:{id}:{label}");
        }
        let confidence = string(claim, "annotation_confidence")?;
        if !CONFIDENCE_LEVELS.contains(&confidence) {
            bail!("invalid_annotation_confidence:{expected_reviewer}:{id}:{confidence}");
        }
        string_set(claim, "cited_evidence_ids")?;
        string_set(claim, "reason_codes")?;
        string(claim, "support_rationale")?;
        ids.push(id);
    }
    Ok(ids)
}

fn claim_metadata(boundary_claim: &Value) -> Value {
    let keys = [
        "boundary_claim_id",
        "case_id",
        "response_sha256",
        "anchor_id",
        "source_field",
        "source_index",
        "source_text_sha256",
        "source_span",
        "source_occurrence_index",
        "claim_text",
        "claim_type",
        "claim_role",
        "anchor_group",
        "material",
        "claim_origin",
    ];
    let mut output = Map::new();
    for key in keys {
        if let Some(value) = boundary_claim.get(key) {
            output.insert(key.to_string(), value.clone());
        }
    }
    Value::Object(output)
}

fn confusion_matrix(
    pairs: &[(String, String)],
    categories: &[&str],
) -> (
    Value,
    BTreeMap<String, usize>,
    BTreeMap<String, usize>,
    usize,
) {
    let mut rows: BTreeMap<String, BTreeMap<String, usize>> = categories
        .iter()
        .map(|label| {
            (
                (*label).to_string(),
                categories
                    .iter()
                    .map(|column| ((*column).to_string(), 0usize))
                    .collect(),
            )
        })
        .collect();
    let mut left_counts = BTreeMap::new();
    let mut right_counts = BTreeMap::new();
    let mut agreement = 0usize;
    for (left, right) in pairs {
        *rows.get_mut(left).unwrap().get_mut(right).unwrap() += 1;
        *left_counts.entry(left.clone()).or_insert(0) += 1;
        *right_counts.entry(right.clone()).or_insert(0) += 1;
        agreement += usize::from(left == right);
    }
    for category in categories {
        left_counts.entry((*category).to_string()).or_insert(0);
        right_counts.entry((*category).to_string()).or_insert(0);
    }
    let matrix = categories
        .iter()
        .map(|label| {
            json!({
                "reviewer_a_label": label,
                "reviewer_b_counts": rows.get(*label).unwrap(),
                "row_total": left_counts.get(*label).unwrap(),
            })
        })
        .collect::<Vec<_>>();
    (Value::Array(matrix), left_counts, right_counts, agreement)
}

fn per_token_diagnostics(
    left_sets: &[BTreeSet<String>],
    right_sets: &[BTreeSet<String>],
    token_name: &str,
) -> Value {
    let tokens: BTreeSet<String> = left_sets
        .iter()
        .chain(right_sets.iter())
        .flat_map(|set| set.iter().cloned())
        .collect();
    let rows = tokens
        .into_iter()
        .map(|token| {
            let left_count = left_sets.iter().filter(|set| set.contains(&token)).count();
            let right_count = right_sets.iter().filter(|set| set.contains(&token)).count();
            let both_count = left_sets
                .iter()
                .zip(right_sets.iter())
                .filter(|(left, right)| left.contains(&token) && right.contains(&token))
                .count();
            let union_count = left_count + right_count - both_count;
            let mut row = Map::new();
            row.insert(token_name.to_string(), json!(token));
            row.insert("reviewer_a_count".to_string(), json!(left_count));
            row.insert("reviewer_b_count".to_string(), json!(right_count));
            row.insert("both_count".to_string(), json!(both_count));
            row.insert(
                "presence_jaccard".to_string(),
                json!(if union_count == 0 {
                    1.0
                } else {
                    both_count as f64 / union_count as f64
                }),
            );
            Value::Object(row)
        })
        .collect::<Vec<_>>();
    Value::Array(rows)
}

fn set_agreement_metrics(
    left_sets: &[BTreeSet<String>],
    right_sets: &[BTreeSet<String>],
    labels_equal: &[bool],
    token_name: &str,
) -> Value {
    let total = left_sets.len();
    let exact_count = left_sets
        .iter()
        .zip(right_sets.iter())
        .filter(|(left, right)| left == right)
        .count();
    let mean_jaccard = left_sets
        .iter()
        .zip(right_sets.iter())
        .map(|(left, right)| jaccard(left, right))
        .sum::<f64>()
        / total as f64;
    let same_label_indices = labels_equal
        .iter()
        .enumerate()
        .filter_map(|(index, equal)| equal.then_some(index))
        .collect::<Vec<_>>();
    let conditional_count = same_label_indices.len();
    let conditional_exact = same_label_indices
        .iter()
        .filter(|index| left_sets[**index] == right_sets[**index])
        .count();
    let conditional_jaccard = if conditional_count == 0 {
        None
    } else {
        Some(
            same_label_indices
                .iter()
                .map(|index| jaccard(&left_sets[*index], &right_sets[*index]))
                .sum::<f64>()
                / conditional_count as f64,
        )
    };
    json!({
        "exact_set_agreement_count": exact_count,
        "exact_set_agreement_rate": exact_count as f64 / total as f64,
        "mean_set_jaccard": mean_jaccard,
        "conditional_on_label_agreement": {
            "claim_count": conditional_count,
            "exact_set_agreement_count": conditional_exact,
            "exact_set_agreement_rate": if conditional_count == 0 { Value::Null } else { json!(conditional_exact as f64 / conditional_count as f64) },
            "mean_set_jaccard": conditional_jaccard,
        },
        "per_token_diagnostics": per_token_diagnostics(left_sets, right_sets, token_name),
    })
}

pub fn analyze_support_agreement(
    paths: &SupportAgreementPaths,
) -> Result<SupportAgreementArtifacts> {
    let protocol_value = read_json(&paths.protocol)?;
    let protocol: SupportAgreementProtocol = serde_json::from_value(protocol_value.clone())
        .context("parse support agreement protocol")?;
    validate_protocol(&protocol)?;

    let artifact_hashes = BTreeMap::from([
        ("protocol".to_string(), sha256_file(&paths.protocol)?),
        (
            "reviewer_a_submission".to_string(),
            verify_artifact(&protocol, "reviewer_a_submission", &paths.reviewer_a)?,
        ),
        (
            "reviewer_b_submission".to_string(),
            verify_artifact(&protocol, "reviewer_b_submission", &paths.reviewer_b)?,
        ),
        (
            "support_packet".to_string(),
            verify_artifact(&protocol, "support_packet", &paths.support_packet)?,
        ),
        (
            "boundary_gold".to_string(),
            verify_artifact(&protocol, "boundary_gold", &paths.boundary_gold)?,
        ),
        (
            "support_execution_outcome".to_string(),
            verify_artifact(
                &protocol,
                "support_execution_outcome",
                &paths.execution_outcome,
            )?,
        ),
        (
            "analyzer_source".to_string(),
            verify_artifact(&protocol, "analyzer_source", &paths.analyzer_source)?,
        ),
        (
            "binary_source".to_string(),
            verify_artifact(&protocol, "binary_source", &paths.binary_source)?,
        ),
    ]);

    let reviewer_a = read_json(&paths.reviewer_a)?;
    let reviewer_b = read_json(&paths.reviewer_b)?;
    let packet = read_json(&paths.support_packet)?;
    let boundary_gold = read_json(&paths.boundary_gold)?;
    let execution_outcome = read_json(&paths.execution_outcome)?;

    let a_ids = validate_submission(&reviewer_a, "reviewer_a", protocol.expected_claim_count)?;
    let b_ids = validate_submission(&reviewer_b, "reviewer_b", protocol.expected_claim_count)?;
    if a_ids != b_ids {
        bail!("reviewer_claim_id_or_order_mismatch");
    }
    if string(&reviewer_a, "packet_sha256")? != protocol.artifact_lineage["support_packet"].sha256
        || string(&reviewer_b, "packet_sha256")? != protocol.reviewer_b_packet_sha256
    {
        bail!("submission_packet_hash_mismatch");
    }
    if string(&reviewer_a, "reviewer_id")? == string(&reviewer_b, "reviewer_id")? {
        bail!("reviewers_not_independent");
    }
    if !boolean(&execution_outcome, "two_completed_support_submissions")?
        || !boolean(&execution_outcome, "support_agreement_allowed")?
        || boolean(&execution_outcome, "support_agreement_computed")?
        || boolean(&execution_outcome, "support_gold_frozen")?
        || boolean(&execution_outcome, "held_out_accessed")?
    {
        bail!("support_execution_outcome_not_authorized_for_agreement");
    }
    if boolean(&packet, "held_out_accessed")? {
        bail!("support_packet_held_out_accessed");
    }

    let gold_claims = array(&boundary_gold, "claims")?;
    if gold_claims.len() != protocol.expected_claim_count {
        bail!("boundary_gold_claim_count_mismatch:{}", gold_claims.len());
    }
    let gold_ids = gold_claims
        .iter()
        .map(|claim| string(claim, "boundary_claim_id").map(str::to_string))
        .collect::<Result<Vec<_>>>()?;
    if gold_ids != a_ids {
        bail!("boundary_gold_claim_id_or_order_mismatch");
    }

    let packet_cases = array(&packet, "cases")?;
    let mut cases_by_id = BTreeMap::new();
    let mut packet_claim_ids = Vec::new();
    for case in packet_cases {
        let case_id = string(case, "case_id")?.to_string();
        let valid_evidence = array(case, "valid_evidence_ids")?
            .iter()
            .map(|item| {
                item.as_str()
                    .context("non_string_valid_evidence_id")
                    .map(str::to_string)
            })
            .collect::<Result<BTreeSet<_>>>()?;
        for claim in array(case, "boundary_claims")? {
            packet_claim_ids.push(string(claim, "boundary_claim_id")?.to_string());
        }
        cases_by_id.insert(case_id, (case.clone(), valid_evidence));
    }
    if packet_claim_ids != a_ids {
        bail!("support_packet_claim_id_or_order_mismatch");
    }

    let a_claims = array(&reviewer_a, "claims")?;
    let b_claims = array(&reviewer_b, "claims")?;
    let mut label_pairs = Vec::with_capacity(protocol.expected_claim_count);
    let mut labels_equal = Vec::with_capacity(protocol.expected_claim_count);
    let mut reason_a = Vec::with_capacity(protocol.expected_claim_count);
    let mut reason_b = Vec::with_capacity(protocol.expected_claim_count);
    let mut citation_a = Vec::with_capacity(protocol.expected_claim_count);
    let mut citation_b = Vec::with_capacity(protocol.expected_claim_count);
    let mut confidence_pairs = Vec::with_capacity(protocol.expected_claim_count);
    let mut severity_sum = 0u64;
    let mut label_disagreement_indices = Vec::new();
    let mut diagnostic_followup_indices = Vec::new();

    for index in 0..protocol.expected_claim_count {
        let a = &a_claims[index];
        let b = &b_claims[index];
        let gold = &gold_claims[index];
        let case_id = string(gold, "case_id")?;
        let valid_evidence = &cases_by_id
            .get(case_id)
            .with_context(|| format!("missing_packet_case:{case_id}"))?
            .1;
        let a_citations = string_set(a, "cited_evidence_ids")?;
        let b_citations = string_set(b, "cited_evidence_ids")?;
        if !a_citations.is_subset(valid_evidence) || !b_citations.is_subset(valid_evidence) {
            bail!("invalid_citation_for_case:{}", a_ids[index]);
        }
        let a_reasons = string_set(a, "reason_codes")?;
        let b_reasons = string_set(b, "reason_codes")?;
        let a_label = string(a, "support_label")?.to_string();
        let b_label = string(b, "support_label")?.to_string();
        let label_equal = a_label == b_label;
        let diagnostics_equal = a_reasons == b_reasons
            && a_citations == b_citations
            && string(a, "annotation_confidence")? == string(b, "annotation_confidence")?;
        severity_sum += disagreement_severity(&a_label, &b_label)?;
        if !label_equal {
            label_disagreement_indices.push(index);
        } else if !diagnostics_equal {
            diagnostic_followup_indices.push(index);
        }
        label_pairs.push((a_label, b_label));
        labels_equal.push(label_equal);
        reason_a.push(a_reasons);
        reason_b.push(b_reasons);
        citation_a.push(a_citations);
        citation_b.push(b_citations);
        confidence_pairs.push((
            string(a, "annotation_confidence")?.to_string(),
            string(b, "annotation_confidence")?.to_string(),
        ));
    }

    let (label_matrix, label_a_counts, label_b_counts, label_agreement_count) =
        confusion_matrix(&label_pairs, &LABELS);
    let (observed, expected, kappa) = cohen_kappa(
        &label_a_counts,
        &label_b_counts,
        label_agreement_count,
        protocol.expected_claim_count,
        &LABELS,
    )
    .context("label_kappa_undefined")?;
    let non_na_indices = label_pairs
        .iter()
        .enumerate()
        .filter_map(|(index, (left, right))| {
            (left != "not_assessable" && right != "not_assessable").then_some(index)
        })
        .collect::<Vec<_>>();
    let conditional_pairs = non_na_indices
        .iter()
        .map(|index| label_pairs[*index].clone())
        .collect::<Vec<_>>();
    let (_, conditional_a_counts, conditional_b_counts, conditional_agreement) =
        confusion_matrix(&conditional_pairs, &LABELS[..3]);
    let conditional_kappa = cohen_kappa(
        &conditional_a_counts,
        &conditional_b_counts,
        conditional_agreement,
        conditional_pairs.len(),
        &LABELS[..3],
    );

    let (confidence_matrix, confidence_a_counts, confidence_b_counts, confidence_agreement) =
        confusion_matrix(&confidence_pairs, &CONFIDENCE_LEVELS);
    let confidence_kappa = cohen_kappa(
        &confidence_a_counts,
        &confidence_b_counts,
        confidence_agreement,
        protocol.expected_claim_count,
        &CONFIDENCE_LEVELS,
    );
    let confidence_distance_sum = confidence_pairs
        .iter()
        .map(|(left, right)| {
            let left_index = CONFIDENCE_LEVELS
                .iter()
                .position(|value| value == left)
                .unwrap();
            let right_index = CONFIDENCE_LEVELS
                .iter()
                .position(|value| value == right)
                .unwrap();
            left_index.abs_diff(right_index) as u64
        })
        .sum::<u64>();
    let confidence_disagreement_count = protocol.expected_claim_count - confidence_agreement;

    let mut by_case: BTreeMap<String, (usize, usize, u64)> = BTreeMap::new();
    let mut by_type: BTreeMap<String, (usize, usize, u64)> = BTreeMap::new();
    for (index, gold) in gold_claims.iter().enumerate() {
        let case_id = string(gold, "case_id")?.to_string();
        let claim_type = string(gold, "claim_type")?.to_string();
        let severity = disagreement_severity(&label_pairs[index].0, &label_pairs[index].1)?;
        let case_entry = by_case.entry(case_id).or_insert((0, 0, 0));
        case_entry.0 += 1;
        case_entry.1 += usize::from(!labels_equal[index]);
        case_entry.2 += severity;
        let type_entry = by_type.entry(claim_type).or_insert((0, 0, 0));
        type_entry.0 += 1;
        type_entry.1 += usize::from(!labels_equal[index]);
        type_entry.2 += severity;
    }
    let concentration_rows = |values: BTreeMap<String, (usize, usize, u64)>, key: &str| {
        Value::Array(
            values
                .into_iter()
                .map(|(name, (claim_count, disagreement_count, severity))| {
                    let mut row = Map::new();
                    row.insert(key.to_string(), json!(name));
                    row.insert("claim_count".to_string(), json!(claim_count));
                    row.insert(
                        "label_disagreement_count".to_string(),
                        json!(disagreement_count),
                    );
                    row.insert(
                        "label_disagreement_rate".to_string(),
                        json!(disagreement_count as f64 / claim_count as f64),
                    );
                    row.insert("severity_sum".to_string(), json!(severity));
                    Value::Object(row)
                })
                .collect(),
        )
    };

    let diagnostic_diff = |index: usize| -> Value {
        json!({
            "reason_codes_equal": reason_a[index] == reason_b[index],
            "reason_codes_jaccard": jaccard(&reason_a[index], &reason_b[index]),
            "citations_equal": citation_a[index] == citation_b[index],
            "citations_jaccard": jaccard(&citation_a[index], &citation_b[index]),
            "confidence_equal": confidence_pairs[index].0 == confidence_pairs[index].1,
            "confidence_pair": {
                "reviewer_a": confidence_pairs[index].0,
                "reviewer_b": confidence_pairs[index].1,
            }
        })
    };

    let mut label_items_seed = label_disagreement_indices
        .iter()
        .map(|index| {
            let (rank, reason) = priority(&label_pairs[*index].0, &label_pairs[*index].1)?;
            Ok((rank, a_ids[*index].clone(), *index, reason))
        })
        .collect::<Result<Vec<_>>>()?;
    label_items_seed.sort_by(|left, right| (left.0, &left.1).cmp(&(right.0, &right.1)));
    let mut label_items = Vec::new();
    for (position, (rank, _, index, reason)) in label_items_seed.into_iter().enumerate() {
        let gold = &gold_claims[index];
        let case_id = string(gold, "case_id")?;
        let evidence_bundle = cases_by_id.get(case_id).unwrap().0["evidence_bundle"].clone();
        label_items.push(json!({
            "worklist_item_id": format!("support-label-adjudication-{:03}", position + 1),
            "boundary_claim_id": a_ids[index],
            "case_id": case_id,
            "priority_rank": rank,
            "priority_reason": reason,
            "disagreement_severity": disagreement_severity(&label_pairs[index].0, &label_pairs[index].1)?,
            "label_pair": {"reviewer_a": label_pairs[index].0, "reviewer_b": label_pairs[index].1},
            "immutable_claim_metadata": claim_metadata(gold),
            "same_case_evidence_bundle": evidence_bundle,
            "reviewer_a_decision": a_claims[index],
            "reviewer_b_decision": b_claims[index],
            "diagnostic_differences": diagnostic_diff(index),
            "support_label_adjudication_required": true,
            "adjudication_status": "pending",
        }));
    }

    let mut diagnostic_items = Vec::new();
    for (position, index) in diagnostic_followup_indices.iter().enumerate() {
        let gold = &gold_claims[*index];
        let case_id = string(gold, "case_id")?;
        let evidence_bundle = cases_by_id.get(case_id).unwrap().0["evidence_bundle"].clone();
        diagnostic_items.push(json!({
            "worklist_item_id": format!("support-diagnostic-followup-{:03}", position + 1),
            "boundary_claim_id": a_ids[*index],
            "case_id": case_id,
            "agreed_support_label": label_pairs[*index].0,
            "immutable_claim_metadata": claim_metadata(gold),
            "same_case_evidence_bundle": evidence_bundle,
            "reviewer_a_decision": a_claims[*index],
            "reviewer_b_decision": b_claims[*index],
            "diagnostic_differences": diagnostic_diff(*index),
            "support_label_adjudication_required": false,
            "label_change_authorized": false,
            "followup_status": "pending_optional_diagnostic_reconciliation",
        }));
    }

    let disagreement_count = protocol.expected_claim_count - label_agreement_count;
    let severity_max = protocol.expected_claim_count as u64 * 3;
    let reason_metrics = set_agreement_metrics(&reason_a, &reason_b, &labels_equal, "reason_code");
    let citation_metrics =
        set_agreement_metrics(&citation_a, &citation_b, &labels_equal, "evidence_id");

    let report = json!({
        "schema_version": 1,
        "report_id": "phase7.3.3-d2-support-agreement-report-v1",
        "protocol_id": protocol.protocol_id,
        "phase": protocol.phase,
        "status": "completed_support_agreement_analysis",
        "object_of_study": "agreement_between_two_raw_independent_support_reviews",
        "claim_count": protocol.expected_claim_count,
        "artifact_lineage": artifact_hashes,
        "input_validation": {
            "protocol_frozen_before_computation": true,
            "artifact_hashes_match": true,
            "both_submissions_completed": true,
            "reviewer_ids_independent": true,
            "claim_count_each": protocol.expected_claim_count,
            "claim_ids_and_order_exact": true,
            "boundary_gold_ids_and_order_exact": true,
            "citations_within_same_case_evidence_bundle": true,
            "duplicate_claim_ids_citations_or_reasons": false,
            "held_out_accessed": false,
        },
        "label_agreement": {
            "label_order": LABELS,
            "confusion_matrix": label_matrix,
            "reviewer_a_marginals": label_a_counts,
            "reviewer_b_marginals": label_b_counts,
            "exact_agreement_count": label_agreement_count,
            "exact_agreement_rate": observed,
            "disagreement_count": disagreement_count,
            "chance_expected_agreement": expected,
            "cohen_kappa_unweighted": kappa,
            "conditional_excluding_not_assessable": {
                "interpretation": "conditional_secondary_metric_only",
                "claim_count": conditional_pairs.len(),
                "exact_agreement_count": conditional_agreement,
                "exact_agreement_rate": if conditional_pairs.is_empty() { Value::Null } else { json!(conditional_agreement as f64 / conditional_pairs.len() as f64) },
                "chance_expected_agreement": conditional_kappa.map(|value| value.1),
                "cohen_kappa_unweighted": conditional_kappa.map(|value| value.2),
            }
        },
        "severity_aware_disagreement": {
            "severity_policy": protocol.severity_policy,
            "severity_sum": severity_sum,
            "maximum_possible_severity_sum": severity_max,
            "normalized_weighted_disagreement": severity_sum as f64 / severity_max as f64,
            "weighted_agreement_complement": 1.0 - severity_sum as f64 / severity_max as f64,
            "mean_severity_among_disagreements": if disagreement_count == 0 { Value::Null } else { json!(severity_sum as f64 / disagreement_count as f64) },
        },
        "reason_code_agreement": reason_metrics,
        "citation_agreement": citation_metrics,
        "confidence_agreement": {
            "confidence_order": CONFIDENCE_LEVELS,
            "confusion_matrix": confidence_matrix,
            "reviewer_a_marginals": confidence_a_counts,
            "reviewer_b_marginals": confidence_b_counts,
            "exact_agreement_count": confidence_agreement,
            "exact_agreement_rate": confidence_agreement as f64 / protocol.expected_claim_count as f64,
            "chance_expected_agreement": confidence_kappa.map(|value| value.1),
            "cohen_kappa_unweighted": confidence_kappa.map(|value| value.2),
            "ordinal_distance_sum": confidence_distance_sum,
            "maximum_possible_ordinal_distance_sum": protocol.expected_claim_count * 2,
            "normalized_ordinal_disagreement": confidence_distance_sum as f64 / (protocol.expected_claim_count * 2) as f64,
            "mean_ordinal_distance_among_disagreements": if confidence_disagreement_count == 0 { Value::Null } else { json!(confidence_distance_sum as f64 / confidence_disagreement_count as f64) },
        },
        "disagreement_concentration": {
            "by_case": concentration_rows(by_case, "case_id"),
            "by_claim_type": concentration_rows(by_type, "claim_type"),
        },
        "adjudication_candidates": {
            "label_adjudication_count": label_items.len(),
            "diagnostic_followup_count": diagnostic_items.len(),
            "label_adjudication_worklist_required": !label_items.is_empty(),
        },
        "interpretation_guard": "Reviewer label distributions are descriptive marginals only and do not establish that either reviewer is stricter, more accurate, or closer to future Support Gold.",
        "guards": {
            "raw_independent_submissions_only": true,
            "adjudication_used": false,
            "support_gold_visible": false,
            "support_gold_generated": false,
            "held_out_accessed": false,
        },
        "next_authorized_stage": if label_items.is_empty() { "support_gold_freeze_requires_explicit_no_disagreement_gate" } else { "freeze_support_adjudication_protocol_v1" },
    });

    let worklist = json!({
        "schema_version": 1,
        "worklist_id": "phase7.3.3-d2-support-disagreement-worklist-v1",
        "protocol_id": protocol.protocol_id,
        "status": "frozen_agreement_output_pending_adjudication",
        "claim_count_analyzed": protocol.expected_claim_count,
        "label_adjudication_items": label_items,
        "diagnostic_followup_items": diagnostic_items,
        "summary": {
            "label_adjudication_count": disagreement_count,
            "diagnostic_followup_count": diagnostic_followup_indices.len(),
            "same_label_no_diagnostic_difference_count": label_agreement_count - diagnostic_followup_indices.len(),
        },
        "worklist_guards": {
            "boundary_mutation_allowed": false,
            "new_claim_creation_allowed": false,
            "claim_deletion_allowed": false,
            "support_gold_freeze_allowed": false,
            "held_out_accessed": false,
            "diagnostic_followup_authorizes_label_change": false,
        },
        "adjudication_status": "not_started",
    });

    Ok(SupportAgreementArtifacts { report, worklist })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn severity_matrix_is_frozen() {
        assert_eq!(disagreement_severity("supported", "supported").unwrap(), 0);
        assert_eq!(
            disagreement_severity("supported", "partially_supported").unwrap(),
            1
        );
        assert_eq!(
            disagreement_severity("partially_supported", "unsupported").unwrap(),
            1
        );
        assert_eq!(
            disagreement_severity("supported", "unsupported").unwrap(),
            2
        );
        assert_eq!(
            disagreement_severity("not_assessable", "supported").unwrap(),
            3
        );
    }

    #[test]
    fn cohen_kappa_matches_known_example() {
        let left = BTreeMap::from([("yes".to_string(), 50), ("no".to_string(), 50)]);
        let right = BTreeMap::from([("yes".to_string(), 60), ("no".to_string(), 40)]);
        let (_, expected, kappa) = cohen_kappa(&left, &right, 80, 100, &["yes", "no"]).unwrap();
        assert!((expected - 0.5).abs() < 1e-12);
        assert!((kappa - 0.6).abs() < 1e-12);
    }

    #[test]
    fn empty_set_jaccard_is_one() {
        assert_eq!(jaccard(&BTreeSet::new(), &BTreeSet::new()), 1.0);
    }

    #[test]
    fn nonempty_vs_empty_jaccard_is_zero() {
        assert_eq!(
            jaccard(&BTreeSet::from(["x".to_string()]), &BTreeSet::new()),
            0.0
        );
    }

    #[test]
    fn priority_order_is_frozen() {
        assert_eq!(priority("supported", "not_assessable").unwrap().0, 1);
        assert_eq!(priority("supported", "unsupported").unwrap().0, 2);
        assert_eq!(priority("partially_supported", "unsupported").unwrap().0, 3);
        assert_eq!(priority("supported", "partially_supported").unwrap().0, 4);
    }
}
