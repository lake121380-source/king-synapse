use crate::phase7_artifact_lineage_transition_gate::{
    exact_file_sha256, validate_silver_labels_artifact_lineage, SilverLabelsLineageReference,
};
use crate::phase7_independent_adjudication_calibration::{
    aggregate_candidate_support_label, load_phase7_adjudication_template,
    load_phase7_reviewer_a_template, load_phase7_reviewer_b_template, ClaimOrigin,
    DisagreementKind, HumanSupportLabel, JudgeFailureKind,
};
use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

const ADJUDICATION_BYTES: &[u8] =
    include_bytes!("../datasets/pattern_extraction/phase7_3_1_adjudication_template.json");

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModelAdjudicatedSilverClaim {
    pub silver_claim_id: String,
    pub adjudicated_claim_id: String,
    pub case_id: String,
    pub reviewer_a_claim_ids: Vec<String>,
    pub reviewer_b_claim_ids: Vec<String>,
    pub final_support_label: HumanSupportLabel,
    pub final_claim_origin: ClaimOrigin,
    pub disagreements: Vec<DisagreementKind>,
    pub judge_failures: Vec<JudgeFailureKind>,
    pub adjudication_rationale: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModelAdjudicatedSilverCandidateLabel {
    pub case_id: String,
    pub silver_claim_ids: Vec<String>,
    pub aggregate_support_label: HumanSupportLabel,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModelAdjudicatedSilverFreezeArtifact {
    pub schema_version: u32,
    pub freeze_id: String,
    pub phase: String,
    pub frozen: bool,
    pub label_status: String,
    pub human_gold: bool,
    pub held_out_accessed: bool,
    pub source_adjudication_id: String,
    pub lineage: SilverLabelsLineageReference,
    pub claim_count: usize,
    pub candidate_count: usize,
    pub claims: Vec<ModelAdjudicatedSilverClaim>,
    pub candidates: Vec<ModelAdjudicatedSilverCandidateLabel>,
    pub scope_labels_adjudicated: bool,
    pub scope_calibration_available: bool,
    pub conclusion: String,
}

pub struct Phase7ModelAdjudicatedSilverFreeze;

impl Phase7ModelAdjudicatedSilverFreeze {
    pub fn build() -> Result<ModelAdjudicatedSilverFreezeArtifact> {
        build()
    }
}

pub fn validate_model_adjudicated_silver_freeze(
    artifact: &ModelAdjudicatedSilverFreezeArtifact,
) -> Result<()> {
    if artifact.schema_version != 1
        || artifact.freeze_id != "phase7.3.1-model-adjudicated-silver-freeze-v1"
        || artifact.phase != "Phase 7.3.1-D Model-Adjudicated Silver Label Freeze"
        || !artifact.frozen
        || artifact.label_status != "model_adjudicated_silver_not_human_gold"
        || artifact.human_gold
        || artifact.held_out_accessed
        || artifact.scope_labels_adjudicated
        || artifact.scope_calibration_available
        || artifact.claim_count != 77
        || artifact.candidate_count != 10
        || artifact.claims.len() != artifact.claim_count
        || artifact.candidates.len() != artifact.candidate_count
    {
        bail!("phase7_3_1_model_adjudicated_silver_freeze_boundary_invalid");
    }
    validate_silver_labels_artifact_lineage(
        &artifact.lineage,
        &exact_file_sha256(ADJUDICATION_BYTES),
    )?;
    let claim_ids = artifact
        .claims
        .iter()
        .map(|claim| claim.silver_claim_id.as_str())
        .collect::<BTreeSet<_>>();
    if claim_ids.len() != artifact.claim_count {
        bail!("silver_claim_ids_must_be_unique");
    }
    let candidate_ids = artifact
        .candidates
        .iter()
        .map(|candidate| candidate.case_id.as_str())
        .collect::<BTreeSet<_>>();
    if candidate_ids.len() != artifact.candidate_count {
        bail!("silver_candidate_ids_must_be_unique");
    }
    for candidate in &artifact.candidates {
        if candidate.silver_claim_ids.is_empty()
            || candidate
                .silver_claim_ids
                .iter()
                .any(|claim_id| !claim_ids.contains(claim_id.as_str()))
        {
            bail!("silver_candidate_claim_lineage_invalid");
        }
    }
    Ok(())
}

fn build() -> Result<ModelAdjudicatedSilverFreezeArtifact> {
    let adjudication = load_phase7_adjudication_template()?;
    let reviewer_a = load_phase7_reviewer_a_template()?;
    let reviewer_b = load_phase7_reviewer_b_template()?;
    if !adjudication.completed || adjudication.claims.len() != 77 {
        bail!("silver_freeze_requires_completed_77_claim_adjudication");
    }

    let reviewer_a_cases = reviewer_a
        .claims
        .iter()
        .map(|claim| (claim.claim_id.as_str(), claim.case_id.as_str()))
        .collect::<BTreeMap<_, _>>();
    let reviewer_b_cases = reviewer_b
        .claims
        .iter()
        .map(|claim| (claim.claim_id.as_str(), claim.case_id.as_str()))
        .collect::<BTreeMap<_, _>>();

    let mut claims = Vec::with_capacity(adjudication.claims.len());
    for adjudicated in &adjudication.claims {
        let mut case_ids = BTreeSet::new();
        for claim_id in &adjudicated.reviewer_a_claim_ids {
            case_ids.insert(
                *reviewer_a_cases
                    .get(claim_id.as_str())
                    .with_context(|| format!("missing Reviewer A claim {claim_id}"))?,
            );
        }
        for claim_id in &adjudicated.reviewer_b_claim_ids {
            case_ids.insert(
                *reviewer_b_cases
                    .get(claim_id.as_str())
                    .with_context(|| format!("missing Reviewer B claim {claim_id}"))?,
            );
        }
        if case_ids.len() != 1 {
            bail!("adjudicated_claim_must_resolve_to_exactly_one_case");
        }
        let case_id = case_ids.into_iter().next().expect("one case").to_string();
        claims.push(ModelAdjudicatedSilverClaim {
            silver_claim_id: adjudicated.claim_id.clone(),
            adjudicated_claim_id: adjudicated.claim_id.clone(),
            case_id,
            reviewer_a_claim_ids: adjudicated.reviewer_a_claim_ids.clone(),
            reviewer_b_claim_ids: adjudicated.reviewer_b_claim_ids.clone(),
            final_support_label: adjudicated.final_support_label,
            final_claim_origin: adjudicated.final_claim_origin,
            disagreements: adjudicated.disagreements.clone(),
            judge_failures: adjudicated.judge_failures.clone(),
            adjudication_rationale: adjudicated.adjudication_rationale.clone(),
        });
    }
    claims.sort_by(|a, b| {
        a.case_id
            .cmp(&b.case_id)
            .then(a.silver_claim_id.cmp(&b.silver_claim_id))
    });

    let mut by_case: BTreeMap<String, Vec<&ModelAdjudicatedSilverClaim>> = BTreeMap::new();
    for claim in &claims {
        by_case
            .entry(claim.case_id.clone())
            .or_default()
            .push(claim);
    }
    let candidates = by_case
        .into_iter()
        .map(
            |(case_id, case_claims)| ModelAdjudicatedSilverCandidateLabel {
                case_id,
                silver_claim_ids: case_claims
                    .iter()
                    .map(|claim| claim.silver_claim_id.clone())
                    .collect(),
                aggregate_support_label: aggregate_candidate_support_label(
                    case_claims.iter().map(|claim| claim.final_support_label),
                ),
            },
        )
        .collect::<Vec<_>>();

    let artifact = ModelAdjudicatedSilverFreezeArtifact {
        schema_version: 1,
        freeze_id: "phase7.3.1-model-adjudicated-silver-freeze-v1".to_string(),
        phase: "Phase 7.3.1-D Model-Adjudicated Silver Label Freeze".to_string(),
        frozen: true,
        label_status: "model_adjudicated_silver_not_human_gold".to_string(),
        human_gold: false,
        held_out_accessed: false,
        source_adjudication_id: adjudication.adjudication_id,
        lineage: SilverLabelsLineageReference {
            adjudication_sha256: exact_file_sha256(ADJUDICATION_BYTES),
        },
        claim_count: claims.len(),
        candidate_count: candidates.len(),
        claims,
        candidates,
        scope_labels_adjudicated: false,
        scope_calibration_available: false,
        conclusion: "These immutable labels are third-model-adjudicated Silver references for diagnostic calibration only. They are not human Gold, do not establish semantic truth, and authorize no learning, memory write, held-out access, Hermes integration, or runtime behavior.".to_string(),
    };
    validate_model_adjudicated_silver_freeze(&artifact)?;
    Ok(artifact)
}
