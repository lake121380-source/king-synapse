use super::{MemoryInfluenceState, TemporalEvent};
use serde::{Deserialize, Serialize};

const DEFAULT_PRESSURE_THRESHOLD: f32 = 0.65;
const DEFAULT_SUPPORT_DECAY: f32 = 0.45;
const DEFAULT_CONTRADICTION_WEIGHT: f32 = 0.35;
const DEFAULT_FAILURE_WEIGHT: f32 = 0.30;
const DEFAULT_NEW_PREFERENCE_WEIGHT: f32 = 0.30;

/// Auditable pressure update for temporal supersession.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct SupersessionDecision {
    pub pressure_before: f32,
    pub event_pressure: f32,
    pub pressure_after: f32,
    pub threshold: f32,
    pub should_supersede: bool,
}

/// Policy that converts temporal evidence into displacement pressure.
pub trait TemporalSupersessionPolicy {
    fn evaluate(
        &self,
        current_state: MemoryInfluenceState,
        event: TemporalEvent,
        current_pressure: f32,
    ) -> SupersessionDecision;
}

/// Minimal deterministic supersession policy for Phase 2.7.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct RuleBasedTemporalSupersessionPolicy {
    pressure_threshold: f32,
    support_decay: f32,
    contradiction_weight: f32,
    failure_weight: f32,
    new_preference_weight: f32,
}

impl RuleBasedTemporalSupersessionPolicy {
    pub fn new(
        pressure_threshold: f32,
        support_decay: f32,
        contradiction_weight: f32,
        failure_weight: f32,
        new_preference_weight: f32,
    ) -> Self {
        Self {
            pressure_threshold: sanitize_pressure(pressure_threshold).max(f32::EPSILON),
            support_decay: sanitize_pressure(support_decay),
            contradiction_weight: sanitize_pressure(contradiction_weight),
            failure_weight: sanitize_pressure(failure_weight),
            new_preference_weight: sanitize_pressure(new_preference_weight),
        }
    }

    pub fn pressure_threshold(&self) -> f32 {
        self.pressure_threshold
    }

    pub fn support_decay(&self) -> f32 {
        self.support_decay
    }
}

impl Default for RuleBasedTemporalSupersessionPolicy {
    fn default() -> Self {
        Self::new(
            DEFAULT_PRESSURE_THRESHOLD,
            DEFAULT_SUPPORT_DECAY,
            DEFAULT_CONTRADICTION_WEIGHT,
            DEFAULT_FAILURE_WEIGHT,
            DEFAULT_NEW_PREFERENCE_WEIGHT,
        )
    }
}

impl TemporalSupersessionPolicy for RuleBasedTemporalSupersessionPolicy {
    fn evaluate(
        &self,
        current_state: MemoryInfluenceState,
        event: TemporalEvent,
        current_pressure: f32,
    ) -> SupersessionDecision {
        let pressure_before = sanitize_pressure(current_pressure);
        let event_pressure = match event {
            TemporalEvent::SupportingEvidence => -pressure_before * self.support_decay,
            TemporalEvent::Contradiction => self.contradiction_weight,
            TemporalEvent::FailureOutcome => self.failure_weight,
            TemporalEvent::NewPreference => self.new_preference_weight,
        };
        let pressure_after = (pressure_before + event_pressure).clamp(0.0, 1.0);
        let should_supersede = current_state != MemoryInfluenceState::Superseded
            && pressure_after >= self.pressure_threshold;

        SupersessionDecision {
            pressure_before,
            event_pressure,
            pressure_after,
            threshold: self.pressure_threshold,
            should_supersede,
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
