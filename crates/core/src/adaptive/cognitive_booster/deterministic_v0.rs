use super::{
    CognitiveAdjustedScore, CognitiveBooster, CognitiveBoosterInput, CognitiveBoosterOutput,
};
use crate::CognitiveFactorType;

const TEMPORAL_BUDGET: f64 = 0.02;
const RELIABILITY_BUDGET: f64 = 0.02;
const CONTEXT_BUDGET: f64 = 0.02;
const PREFERENCE_BUDGET: f64 = 0.01;
const FAILURE_BUDGET: f64 = 0.03;

const TEMPORAL_TRACE_MAX: f64 = 0.15;
const RELIABILITY_TRACE_MAX: f64 = 0.20;
const CONTEXT_TRACE_MAX: f64 = 0.15;
const PREFERENCE_TRACE_MAX: f64 = 0.10;
const FAILURE_TRACE_MAX: f64 = 0.15;

/// First deterministic cognitive booster used by the Phase 5.3.2 shadow experiment.
///
/// The algorithm deliberately excludes `SemanticMatch`: semantic relevance is
/// already represented by the baseline recall score, while this experiment is
/// intended to measure the additional value of temporal, reliability, context,
/// preference, and failure-evidence signals. The returned score proposals are
/// shadow-only and are bounded again by [`CognitiveBoosterOutput::shadow`].
#[derive(Debug, Clone, Copy, Default)]
pub struct DeterministicCognitiveBoosterV0;

impl CognitiveBooster for DeterministicCognitiveBoosterV0 {
    fn name(&self) -> &'static str {
        "deterministic_cognitive_booster_v0"
    }

    fn boost(&self, input: CognitiveBoosterInput<'_>) -> CognitiveBoosterOutput {
        if !input.config().enabled() {
            return CognitiveBoosterOutput::disabled(input.candidate_count());
        }

        let proposals = input
            .eligible_candidates()
            .iter()
            .enumerate()
            .map(|(index, hit)| {
                let requested_bonus = input
                    .trace()
                    .factors
                    .iter()
                    .filter(|factor| factor.candidate_id == hit.memory.id)
                    .map(|factor| factor_bonus(factor.factor_type, factor.contribution))
                    .sum::<f64>();

                CognitiveAdjustedScore::bounded(
                    hit.memory.id.clone(),
                    index + 1,
                    f64::from(hit.score),
                    requested_bonus,
                    input.config().max_bonus(),
                )
            })
            .collect();

        CognitiveBoosterOutput::shadow(&input, proposals, input.trace().confidence)
    }
}

fn factor_bonus(factor_type: CognitiveFactorType, contribution: f64) -> f64 {
    let (trace_max, budget) = match factor_type {
        CognitiveFactorType::TemporalConfidence => (TEMPORAL_TRACE_MAX, TEMPORAL_BUDGET),
        CognitiveFactorType::Reliability => (RELIABILITY_TRACE_MAX, RELIABILITY_BUDGET),
        CognitiveFactorType::ContextAlignment => (CONTEXT_TRACE_MAX, CONTEXT_BUDGET),
        CognitiveFactorType::PreferenceAlignment => (PREFERENCE_TRACE_MAX, PREFERENCE_BUDGET),
        CognitiveFactorType::FailureEvidence => (FAILURE_TRACE_MAX, FAILURE_BUDGET),
        CognitiveFactorType::SemanticMatch => return 0.0,
    };

    normalize_factor(contribution, trace_max) * budget
}

fn normalize_factor(contribution: f64, trace_max: f64) -> f64 {
    if contribution.is_finite() && trace_max.is_finite() && trace_max > 0.0 {
        (contribution / trace_max).clamp(0.0, 1.0)
    } else {
        0.0
    }
}
