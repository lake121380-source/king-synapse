use crate::{CognitiveCompetitionTrace, RecallHit};
use serde::{de, Deserialize, Deserializer, Serialize};
use thiserror::Error;

/// Absolute interface cap for the first bounded cognitive booster prototype.
///
/// This matches the current activation-booster cap budget. Phase 5.3.1 does
/// not apply the value to recall; it only constrains future shadow proposals.
pub const MAX_COGNITIVE_BOOSTER_BONUS: f64 = 0.10;

/// Configuration for a cognitive booster proposal run.
///
/// `Default` is strictly disabled: no candidate is eligible and the effective
/// maximum bonus is zero. Shadow mode must be requested explicitly through
/// [`CognitiveBoosterConfig::shadow`]. Deserialization preserves the same
/// invariants and rejects configurations that bypass those constructors.
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub struct CognitiveBoosterConfig {
    enabled: bool,
    max_bonus: f64,
    candidate_limit: usize,
}

impl CognitiveBoosterConfig {
    pub const fn disabled() -> Self {
        Self {
            enabled: false,
            max_bonus: 0.0,
            candidate_limit: 0,
        }
    }

    /// Construct an explicit shadow-only configuration.
    ///
    /// This does not connect the booster to recall. It only validates the
    /// limits made available to a [`crate::CognitiveBooster`] implementation.
    pub fn shadow(
        max_bonus: f64,
        candidate_limit: usize,
    ) -> Result<Self, CognitiveBoosterConfigError> {
        if !max_bonus.is_finite() || max_bonus <= 0.0 {
            return Err(CognitiveBoosterConfigError::InvalidMaxBonus);
        }
        if max_bonus > MAX_COGNITIVE_BOOSTER_BONUS {
            return Err(CognitiveBoosterConfigError::MaxBonusExceeded {
                requested: max_bonus,
                allowed: MAX_COGNITIVE_BOOSTER_BONUS,
            });
        }
        if candidate_limit == 0 {
            return Err(CognitiveBoosterConfigError::EmptyCandidateLimit);
        }
        Ok(Self {
            enabled: true,
            max_bonus,
            candidate_limit,
        })
    }

    pub const fn enabled(self) -> bool {
        self.enabled
    }

    pub const fn max_bonus(self) -> f64 {
        self.max_bonus
    }

    pub const fn candidate_limit(self) -> usize {
        self.candidate_limit
    }
}

impl Default for CognitiveBoosterConfig {
    fn default() -> Self {
        Self::disabled()
    }
}

impl<'de> Deserialize<'de> for CognitiveBoosterConfig {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        #[derive(Deserialize)]
        struct WireConfig {
            enabled: bool,
            max_bonus: f64,
            candidate_limit: usize,
        }

        let wire = WireConfig::deserialize(deserializer)?;
        if wire.enabled {
            Self::shadow(wire.max_bonus, wire.candidate_limit).map_err(de::Error::custom)
        } else if wire.max_bonus == 0.0 && wire.candidate_limit == 0 {
            Ok(Self::disabled())
        } else {
            Err(de::Error::custom(
                CognitiveBoosterConfigError::DisabledLimitsMustBeZero,
            ))
        }
    }
}

#[derive(Debug, Clone, PartialEq, Error)]
pub enum CognitiveBoosterConfigError {
    #[error("cognitive booster max_bonus must be finite and greater than zero")]
    InvalidMaxBonus,
    #[error("cognitive booster max_bonus {requested} exceeds interface cap {allowed}")]
    MaxBonusExceeded { requested: f64, allowed: f64 },
    #[error("cognitive booster candidate_limit must be greater than zero")]
    EmptyCandidateLimit,
    #[error("disabled cognitive booster limits must both be zero")]
    DisabledLimitsMustBeZero,
}

/// Read-only bounded input handed to [`crate::CognitiveBooster`].
///
/// No store handle, retriever, mutable hit slice, or memory writer is present.
#[derive(Debug, Clone, Copy)]
pub struct CognitiveBoosterInput<'a> {
    candidates: &'a [RecallHit],
    trace: &'a CognitiveCompetitionTrace,
    config: &'a CognitiveBoosterConfig,
}

impl<'a> CognitiveBoosterInput<'a> {
    pub const fn new(
        candidates: &'a [RecallHit],
        trace: &'a CognitiveCompetitionTrace,
        config: &'a CognitiveBoosterConfig,
    ) -> Self {
        Self {
            candidates,
            trace,
            config,
        }
    }

    /// All baseline candidates supplied by the shadow caller.
    ///
    /// Implementations may inspect this slice for comparison, but output
    /// construction accepts proposals only for [`Self::eligible_candidates`].
    pub const fn candidates(&self) -> &'a [RecallHit] {
        self.candidates
    }

    /// The prefix eligible for cognitive proposals under the configured cap.
    /// Disabled configurations always expose an empty eligible slice.
    pub fn eligible_candidates(&self) -> &'a [RecallHit] {
        if !self.config.enabled {
            return &self.candidates[..0];
        }
        let eligible = self.config.candidate_limit.min(self.candidates.len());
        &self.candidates[..eligible]
    }

    pub const fn trace(&self) -> &'a CognitiveCompetitionTrace {
        self.trace
    }

    pub const fn config(&self) -> &'a CognitiveBoosterConfig {
        self.config
    }

    pub const fn candidate_count(&self) -> usize {
        self.candidates.len()
    }
}

/// Execution mode recorded in shadow reports.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CognitiveBoosterMode {
    Disabled,
    Shadow,
}

/// One bounded score proposal for an existing candidate.
///
/// `adjusted_score` is diagnostic only. It is not written back to `RecallHit`
/// by any Phase 5.3.1 code path. [`CognitiveBoosterOutput::shadow`] reconstructs
/// these values from the immutable input and does not trust caller-supplied
/// baseline fields.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CognitiveAdjustedScore {
    pub candidate_id: String,
    pub baseline_rank: usize,
    pub baseline_score: f64,
    pub requested_bonus: f64,
    pub bounded_bonus: f64,
    pub adjusted_score: f64,
    pub was_clamped: bool,
}

impl CognitiveAdjustedScore {
    pub fn bounded(
        candidate_id: impl Into<String>,
        baseline_rank: usize,
        baseline_score: f64,
        requested_bonus: f64,
        max_bonus: f64,
    ) -> Self {
        let effective_cap = finite_non_negative(max_bonus).min(MAX_COGNITIVE_BOOSTER_BONUS);
        let normalized_request = finite_non_negative(requested_bonus);
        let bounded_bonus = normalized_request.min(effective_cap);
        Self {
            candidate_id: candidate_id.into(),
            baseline_rank,
            baseline_score,
            requested_bonus,
            bounded_bonus,
            adjusted_score: baseline_score + bounded_bonus,
            was_clamped: !requested_bonus.is_finite()
                || (requested_bonus - bounded_bonus).abs() > f64::EPSILON,
        }
    }

    pub fn changed(&self) -> bool {
        self.bounded_bonus > f64::EPSILON
    }
}

/// Shadow-only result returned by a [`crate::CognitiveBooster`].
///
/// Fields are intentionally private so implementations cannot claim that a
/// proposal was applied to runtime or mutated memory. Reports remain
/// serializable through the stable field names below.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct CognitiveBoosterOutput {
    mode: CognitiveBoosterMode,
    candidate_count: usize,
    eligible_candidate_count: usize,
    adjusted_scores: Vec<CognitiveAdjustedScore>,
    confidence: f64,
    changed_candidates: Vec<String>,
    max_bonus: f64,
    bounded: bool,
    runtime_applied: bool,
    memory_mutated: bool,
}

impl CognitiveBoosterOutput {
    pub fn disabled(candidate_count: usize) -> Self {
        Self {
            mode: CognitiveBoosterMode::Disabled,
            candidate_count,
            eligible_candidate_count: 0,
            adjusted_scores: Vec::new(),
            confidence: 0.0,
            changed_candidates: Vec::new(),
            max_bonus: 0.0,
            bounded: true,
            runtime_applied: false,
            memory_mutated: false,
        }
    }

    /// Build a bounded shadow result without applying it to recall.
    ///
    /// Proposals outside the eligible candidate prefix are ignored. Baseline
    /// rank and score are reconstructed from the immutable input, requested
    /// bonuses are capped by the validated configuration, and duplicate
    /// proposals use the first proposal for deterministic behavior.
    pub fn shadow(
        input: &CognitiveBoosterInput<'_>,
        proposals: Vec<CognitiveAdjustedScore>,
        confidence: f64,
    ) -> Self {
        if !input.config.enabled {
            return Self::disabled(input.candidate_count());
        }

        let eligible_candidates = input.eligible_candidates();
        let adjusted_scores = eligible_candidates
            .iter()
            .enumerate()
            .filter_map(|(index, hit)| {
                proposals
                    .iter()
                    .find(|proposal| proposal.candidate_id == hit.memory.id)
                    .map(|proposal| {
                        CognitiveAdjustedScore::bounded(
                            hit.memory.id.clone(),
                            index + 1,
                            f64::from(hit.score),
                            proposal.requested_bonus,
                            input.config.max_bonus,
                        )
                    })
            })
            .collect::<Vec<_>>();
        let changed_candidates = adjusted_scores
            .iter()
            .filter(|score| score.changed())
            .map(|score| score.candidate_id.clone())
            .collect();

        Self {
            mode: CognitiveBoosterMode::Shadow,
            candidate_count: input.candidate_count(),
            eligible_candidate_count: eligible_candidates.len(),
            adjusted_scores,
            confidence: normalize(confidence),
            changed_candidates,
            max_bonus: input.config.max_bonus,
            bounded: true,
            runtime_applied: false,
            memory_mutated: false,
        }
    }

    pub const fn mode(&self) -> CognitiveBoosterMode {
        self.mode
    }

    pub const fn candidate_count(&self) -> usize {
        self.candidate_count
    }

    pub const fn eligible_candidate_count(&self) -> usize {
        self.eligible_candidate_count
    }

    pub fn adjusted_scores(&self) -> &[CognitiveAdjustedScore] {
        &self.adjusted_scores
    }

    pub const fn confidence(&self) -> f64 {
        self.confidence
    }

    pub fn changed_candidates(&self) -> &[String] {
        &self.changed_candidates
    }

    pub const fn max_bonus(&self) -> f64 {
        self.max_bonus
    }

    pub const fn bounded(&self) -> bool {
        self.bounded
    }

    pub const fn runtime_applied(&self) -> bool {
        self.runtime_applied
    }

    pub const fn memory_mutated(&self) -> bool {
        self.memory_mutated
    }
}

fn finite_non_negative(value: f64) -> f64 {
    if value.is_finite() {
        value.max(0.0)
    } else {
        0.0
    }
}

fn normalize(value: f64) -> f64 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        0.0
    }
}
