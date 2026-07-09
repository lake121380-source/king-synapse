use super::{MemoryInfluenceState, TemporalEvent};
use serde::{Deserialize, Serialize};

const DEFAULT_REACTIVATION_THRESHOLD: f32 = 0.85;
const DEFAULT_SUPPORT_WEIGHT: f32 = 0.20;
const DEFAULT_COUNTER_DECAY: f32 = 0.50;

/// Auditable pressure update for temporal reactivation.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct ReactivationDecision {
    pub pressure_before: f32,
    pub event_pressure: f32,
    pub pressure_after: f32,
    pub threshold: f32,
    pub should_reactivate: bool,
}

/// Policy that converts later supporting evidence into recovery pressure.
pub trait TemporalReactivationPolicy {
    fn evaluate(
        &self,
        current_state: MemoryInfluenceState,
        event: TemporalEvent,
        current_pressure: f32,
    ) -> ReactivationDecision;
}

/// Minimal deterministic reactivation policy for Phase 2.9.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct RuleBasedTemporalReactivationPolicy {
    reactivation_threshold: f32,
    support_weight: f32,
    counter_decay: f32,
}

impl RuleBasedTemporalReactivationPolicy {
    pub fn new(reactivation_threshold: f32, support_weight: f32, counter_decay: f32) -> Self {
        Self {
            reactivation_threshold: sanitize_pressure(reactivation_threshold).max(f32::EPSILON),
            support_weight: sanitize_pressure(support_weight),
            counter_decay: sanitize_pressure(counter_decay),
        }
    }

    pub fn reactivation_threshold(&self) -> f32 {
        self.reactivation_threshold
    }

    pub fn support_weight(&self) -> f32 {
        self.support_weight
    }
}

impl Default for RuleBasedTemporalReactivationPolicy {
    fn default() -> Self {
        Self::new(
            DEFAULT_REACTIVATION_THRESHOLD,
            DEFAULT_SUPPORT_WEIGHT,
            DEFAULT_COUNTER_DECAY,
        )
    }
}

impl TemporalReactivationPolicy for RuleBasedTemporalReactivationPolicy {
    fn evaluate(
        &self,
        current_state: MemoryInfluenceState,
        event: TemporalEvent,
        current_pressure: f32,
    ) -> ReactivationDecision {
        let pressure_before = sanitize_pressure(current_pressure);
        let event_pressure = match (current_state, event) {
            (MemoryInfluenceState::Superseded, TemporalEvent::SupportingEvidence) => {
                self.support_weight
            }
            (MemoryInfluenceState::Superseded, _) => -pressure_before * self.counter_decay,
            (_, TemporalEvent::SupportingEvidence) => 0.0,
            (_, _) => -pressure_before * self.counter_decay,
        };
        let pressure_after = (pressure_before + event_pressure).clamp(0.0, 1.0);
        let should_reactivate = current_state == MemoryInfluenceState::Superseded
            && event == TemporalEvent::SupportingEvidence
            && pressure_after >= self.reactivation_threshold;

        ReactivationDecision {
            pressure_before,
            event_pressure,
            pressure_after,
            threshold: self.reactivation_threshold,
            should_reactivate,
        }
    }
}

fn sanitize_pressure(value: f32) -> f32 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        0.0
    }
}
