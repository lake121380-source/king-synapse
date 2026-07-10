use super::types::{CognitiveBoosterInput, CognitiveBoosterOutput};

/// Produces bounded cognitive score proposals without mutating recall hits.
///
/// Phase 5.3.1 implementations are shadow-only. This trait is intentionally
/// not the runtime `RecallBooster` contract: it receives immutable candidates,
/// cannot access the store, cannot create candidates, and cannot apply scores.
pub trait CognitiveBooster {
    /// Stable diagnostic name for reports and A/B fixtures.
    fn name(&self) -> &'static str;

    /// Inspect the bounded input and return a shadow proposal.
    ///
    /// The returned output must keep `runtime_applied = false` and
    /// `memory_mutated = false` during Phase 5.3.1.
    fn boost(&self, input: CognitiveBoosterInput<'_>) -> CognitiveBoosterOutput;
}

/// Default inert implementation.
///
/// Supplying this implementation, even with an explicitly enabled shadow
/// configuration, produces no score proposals and changes no runtime state.
#[derive(Debug, Clone, Copy, Default)]
pub struct NoOpCognitiveBooster;

impl CognitiveBooster for NoOpCognitiveBooster {
    fn name(&self) -> &'static str {
        "cognitive_booster_noop"
    }

    fn boost(&self, input: CognitiveBoosterInput<'_>) -> CognitiveBoosterOutput {
        CognitiveBoosterOutput::disabled(input.candidate_count())
    }
}
