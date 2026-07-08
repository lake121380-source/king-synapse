//! Memory Competition prototype (Phase 2.2).
//!
//! This module is algorithm-local. It consumes already-activated memory
//! candidates and produces an auditable dominant / suppressed / rejected
//! decision path. It does not read Store, change Recall, mutate memories, or
//! update governance state.

use serde::{Deserialize, Serialize};

const DEFAULT_DOMINANT_THRESHOLD: f32 = 0.20;
const DEFAULT_REJECTION_THRESHOLD: f32 = 0.08;

/// Competitive state assigned after influence regulation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[non_exhaustive]
pub enum MemoryCompetitionState {
    Dominant,
    Suppressed,
    Rejected,
}

/// A memory influence candidate entering the competition layer.
///
/// Scores are normalized to `0.0 ..= 1.0`. `final_influence` and `state` are
/// recomputed by [`MemoryCompetition`]; callers may leave them at their
/// constructor defaults.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct MemoryCandidate {
    pub memory_id: String,
    pub activation_score: f32,
    pub confidence: f32,
    pub temporal_score: f32,
    pub contradiction_score: f32,
    pub final_influence: f32,
    pub state: MemoryCompetitionState,
}

impl MemoryCandidate {
    pub fn new(
        memory_id: impl Into<String>,
        activation_score: f32,
        confidence: f32,
        temporal_score: f32,
        contradiction_score: f32,
    ) -> Self {
        Self {
            memory_id: memory_id.into(),
            activation_score: sanitize_factor(activation_score),
            confidence: sanitize_factor(confidence),
            temporal_score: sanitize_factor(temporal_score),
            contradiction_score: sanitize_factor(contradiction_score),
            final_influence: 0.0,
            state: MemoryCompetitionState::Suppressed,
        }
    }

    pub fn consistency_factor(&self) -> f32 {
        (1.0 - sanitize_factor(self.contradiction_score)).clamp(0.0, 1.0)
    }
}

/// One line in the auditable competition path.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct MemoryCompetitionTraceStep {
    pub memory_id: String,
    pub state: MemoryCompetitionState,
    pub final_influence: f32,
    pub reason: String,
}

/// Result of memory competition.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct MemoryCompetitionReport {
    pub candidates: Vec<MemoryCandidate>,
    pub dominant: Option<String>,
    pub suppressed: Vec<String>,
    pub rejected: Vec<String>,
    pub decision_path: Vec<MemoryCompetitionTraceStep>,
}

impl MemoryCompetitionReport {
    pub fn dominant_candidate(&self) -> Option<&MemoryCandidate> {
        let dominant = self.dominant.as_ref()?;
        self.candidates
            .iter()
            .find(|candidate| &candidate.memory_id == dominant)
    }
}

pub trait MemoryCompetition {
    fn compete(&self, candidates: &[MemoryCandidate]) -> MemoryCompetitionReport;
}

/// Minimal deterministic competition rule for Phase 2.2.
///
/// ```text
/// final_influence =
///   activation_score * confidence * temporal_factor * consistency_factor
/// ```
#[derive(Debug, Clone, Copy)]
pub struct RuleBasedMemoryCompetition {
    dominant_threshold: f32,
    rejection_threshold: f32,
}

impl RuleBasedMemoryCompetition {
    pub fn new(dominant_threshold: f32, rejection_threshold: f32) -> Self {
        let dominant_threshold = sanitize_threshold(dominant_threshold, DEFAULT_DOMINANT_THRESHOLD);
        let mut rejection_threshold =
            sanitize_threshold(rejection_threshold, DEFAULT_REJECTION_THRESHOLD);
        if rejection_threshold >= dominant_threshold {
            rejection_threshold = dominant_threshold * 0.5;
        }
        Self {
            dominant_threshold,
            rejection_threshold,
        }
    }

    pub fn dominant_threshold(&self) -> f32 {
        self.dominant_threshold
    }

    pub fn rejection_threshold(&self) -> f32 {
        self.rejection_threshold
    }
}

impl Default for RuleBasedMemoryCompetition {
    fn default() -> Self {
        Self::new(DEFAULT_DOMINANT_THRESHOLD, DEFAULT_REJECTION_THRESHOLD)
    }
}

impl MemoryCompetition for RuleBasedMemoryCompetition {
    fn compete(&self, candidates: &[MemoryCandidate]) -> MemoryCompetitionReport {
        let mut evaluated = candidates
            .iter()
            .cloned()
            .map(evaluate_candidate)
            .collect::<Vec<_>>();

        evaluated.sort_by(|left, right| {
            right
                .final_influence
                .total_cmp(&left.final_influence)
                .then_with(|| left.memory_id.cmp(&right.memory_id))
        });

        let dominant_index = evaluated
            .first()
            .filter(|candidate| {
                !candidate.memory_id.is_empty()
                    && candidate.final_influence >= self.dominant_threshold
            })
            .map(|_| 0usize);

        for (index, candidate) in evaluated.iter_mut().enumerate() {
            candidate.state = if Some(index) == dominant_index {
                MemoryCompetitionState::Dominant
            } else if dominant_index.is_some()
                && candidate.final_influence > self.rejection_threshold
            {
                MemoryCompetitionState::Suppressed
            } else {
                MemoryCompetitionState::Rejected
            };
        }

        let dominant = evaluated
            .iter()
            .find(|candidate| candidate.state == MemoryCompetitionState::Dominant)
            .map(|candidate| candidate.memory_id.clone());
        let suppressed = ids_with_state(&evaluated, MemoryCompetitionState::Suppressed);
        let rejected = ids_with_state(&evaluated, MemoryCompetitionState::Rejected);
        let decision_path = evaluated.iter().map(trace_step).collect();

        MemoryCompetitionReport {
            candidates: evaluated,
            dominant,
            suppressed,
            rejected,
            decision_path,
        }
    }
}

fn evaluate_candidate(mut candidate: MemoryCandidate) -> MemoryCandidate {
    candidate.activation_score = sanitize_factor(candidate.activation_score);
    candidate.confidence = sanitize_factor(candidate.confidence);
    candidate.temporal_score = sanitize_factor(candidate.temporal_score);
    candidate.contradiction_score = sanitize_factor(candidate.contradiction_score);
    candidate.final_influence = candidate.activation_score
        * candidate.confidence
        * candidate.temporal_score
        * candidate.consistency_factor();
    candidate
}

fn ids_with_state(candidates: &[MemoryCandidate], state: MemoryCompetitionState) -> Vec<String> {
    candidates
        .iter()
        .filter(|candidate| candidate.state == state)
        .map(|candidate| candidate.memory_id.clone())
        .collect()
}

fn trace_step(candidate: &MemoryCandidate) -> MemoryCompetitionTraceStep {
    MemoryCompetitionTraceStep {
        memory_id: candidate.memory_id.clone(),
        state: candidate.state,
        final_influence: candidate.final_influence,
        reason: competition_reason(candidate),
    }
}

fn competition_reason(candidate: &MemoryCandidate) -> String {
    match candidate.state {
        MemoryCompetitionState::Dominant => {
            "dominant: highest final influence above threshold".to_string()
        }
        MemoryCompetitionState::Suppressed => {
            if candidate.contradiction_score >= 0.50 {
                "suppressed: contradiction lowered influence".to_string()
            } else if candidate.temporal_score < 0.60 {
                "suppressed: older evidence reduced temporal factor".to_string()
            } else {
                "suppressed: lower final influence than dominant".to_string()
            }
        }
        MemoryCompetitionState::Rejected => {
            if candidate.memory_id.is_empty() {
                "rejected: empty memory id".to_string()
            } else if candidate.confidence < 0.40 {
                "rejected: confidence below competition threshold".to_string()
            } else if candidate.temporal_score < 0.35 {
                "rejected: temporal factor too weak".to_string()
            } else if candidate.contradiction_score > 0.75 {
                "rejected: contradiction pressure too high".to_string()
            } else {
                "rejected: final influence below dominant threshold".to_string()
            }
        }
    }
}

fn sanitize_factor(value: f32) -> f32 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        0.0
    }
}

fn sanitize_threshold(value: f32, fallback: f32) -> f32 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        fallback
    }
}
