//! Temporal Memory Transition prototype (Phase 2.5).
//!
//! This module is algorithm-local. It models how later evidence can change a
//! memory's future influence without deleting the memory, rewriting its content,
//! changing recall, or mutating the persisted memory schema.

use serde::{Deserialize, Serialize};

pub mod reactivation;
pub mod supersession;

pub use reactivation::{
    ReactivationDecision, RuleBasedTemporalReactivationPolicy, TemporalReactivationPolicy,
};
pub use supersession::{
    RuleBasedTemporalSupersessionPolicy, SupersessionDecision, TemporalSupersessionPolicy,
};

const DEFAULT_CHALLENGED_MULTIPLIER: f32 = 0.55;
const DEFAULT_SUPERSEDED_MULTIPLIER: f32 = 0.20;
const DEFAULT_SUPERSEDE_AFTER_FAILURES: u8 = 3;

/// Temporal influence state for a memory.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[non_exhaustive]
pub enum MemoryInfluenceState {
    Active,
    Challenged,
    Superseded,
}

/// Evidence event used by the transition prototype.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[non_exhaustive]
pub enum TemporalEvent {
    SupportingEvidence,
    Contradiction,
    FailureOutcome,
    NewPreference,
}

/// An in-memory influence profile for a persisted memory.
///
/// `stored` intentionally remains true across transitions. Phase 2.5 changes
/// influence state only; it does not delete or rewrite the source memory.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct TemporalMemoryProfile {
    pub memory_id: String,
    pub stored: bool,
    pub state: MemoryInfluenceState,
    pub base_influence: f32,
    pub current_influence: f32,
    pub contradiction_count: u8,
    pub failure_count: u8,
    pub supersession_pressure: f32,
    pub reactivation_pressure: f32,
    pub transition_history: Vec<TemporalTransitionStep>,
}

impl TemporalMemoryProfile {
    pub fn new(memory_id: impl Into<String>, base_influence: f32) -> Self {
        let base_influence = sanitize_influence(base_influence);
        Self {
            memory_id: memory_id.into(),
            stored: true,
            state: MemoryInfluenceState::Active,
            base_influence,
            current_influence: base_influence,
            contradiction_count: 0,
            failure_count: 0,
            supersession_pressure: 0.0,
            reactivation_pressure: 0.0,
            transition_history: Vec::new(),
        }
    }

    pub fn with_state(mut self, state: MemoryInfluenceState) -> Self {
        self.state = state;
        self.current_influence = influence_for_state(state, self.base_influence, default_config());
        self
    }
}

/// One auditable transition in the temporal influence path.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct TemporalTransitionStep {
    pub memory_id: String,
    pub event: TemporalEvent,
    pub from: MemoryInfluenceState,
    pub to: MemoryInfluenceState,
    pub influence_before: f32,
    pub influence_after: f32,
    pub supersession_pressure_before: f32,
    pub supersession_pressure_after: f32,
    pub reactivation_pressure_before: f32,
    pub reactivation_pressure_after: f32,
    pub reason: String,
}

/// Result of applying a temporal event.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct TemporalTransitionReport {
    pub memory: TemporalMemoryProfile,
    pub transition: TemporalTransitionStep,
}

pub trait TemporalTransitionEngine {
    fn apply(
        &self,
        memory: TemporalMemoryProfile,
        event: TemporalEvent,
    ) -> TemporalTransitionReport;

    fn apply_many(
        &self,
        mut memory: TemporalMemoryProfile,
        events: &[TemporalEvent],
    ) -> TemporalTransitionReport {
        if events.is_empty() {
            return self.apply(memory, TemporalEvent::SupportingEvidence);
        }

        let mut report = self.apply(memory, events[0]);
        memory = report.memory.clone();
        for event in &events[1..] {
            report = self.apply(memory, *event);
            memory = report.memory.clone();
        }
        report
    }
}

/// Minimal deterministic transition rule for Phase 2.5.
#[derive(Debug, Clone, Copy)]
pub struct RuleBasedTemporalTransitionEngine {
    challenged_multiplier: f32,
    superseded_multiplier: f32,
    supersede_after_failures: u8,
    supersession_policy: RuleBasedTemporalSupersessionPolicy,
    reactivation_policy: RuleBasedTemporalReactivationPolicy,
}

impl RuleBasedTemporalTransitionEngine {
    pub fn new(
        challenged_multiplier: f32,
        superseded_multiplier: f32,
        supersede_after_failures: u8,
    ) -> Self {
        let challenged_multiplier = sanitize_influence(challenged_multiplier);
        let mut superseded_multiplier = sanitize_influence(superseded_multiplier);
        if superseded_multiplier > challenged_multiplier {
            superseded_multiplier = challenged_multiplier;
        }
        Self {
            challenged_multiplier,
            superseded_multiplier,
            supersede_after_failures: supersede_after_failures.max(1),
            supersession_policy: RuleBasedTemporalSupersessionPolicy::default(),
            reactivation_policy: RuleBasedTemporalReactivationPolicy::default(),
        }
    }

    pub fn challenged_multiplier(&self) -> f32 {
        self.challenged_multiplier
    }

    pub fn superseded_multiplier(&self) -> f32 {
        self.superseded_multiplier
    }

    pub fn supersede_after_failures(&self) -> u8 {
        self.supersede_after_failures
    }

    pub fn supersession_policy(&self) -> RuleBasedTemporalSupersessionPolicy {
        self.supersession_policy
    }

    pub fn reactivation_policy(&self) -> RuleBasedTemporalReactivationPolicy {
        self.reactivation_policy
    }
}

impl Default for RuleBasedTemporalTransitionEngine {
    fn default() -> Self {
        default_config()
    }
}

impl TemporalTransitionEngine for RuleBasedTemporalTransitionEngine {
    fn apply(
        &self,
        mut memory: TemporalMemoryProfile,
        event: TemporalEvent,
    ) -> TemporalTransitionReport {
        memory.stored = true;
        memory.base_influence = sanitize_influence(memory.base_influence);
        memory.current_influence = sanitize_influence(memory.current_influence);
        memory.supersession_pressure = sanitize_influence(memory.supersession_pressure);
        memory.reactivation_pressure = sanitize_influence(memory.reactivation_pressure);

        let from = memory.state;
        let influence_before = memory.current_influence;
        let supersession_pressure_before = memory.supersession_pressure;
        let reactivation_pressure_before = memory.reactivation_pressure;
        update_evidence_counts(&mut memory, event);
        let supersession =
            self.supersession_policy
                .evaluate(memory.state, event, memory.supersession_pressure);
        let reactivation =
            self.reactivation_policy
                .evaluate(memory.state, event, memory.reactivation_pressure);
        memory.supersession_pressure = supersession.pressure_after;
        memory.reactivation_pressure = reactivation.pressure_after;
        memory.state = next_state(
            memory.state,
            event,
            &memory,
            self,
            &supersession,
            &reactivation,
        );
        memory.current_influence = influence_for_state(memory.state, memory.base_influence, *self);

        let transition = TemporalTransitionStep {
            memory_id: memory.memory_id.clone(),
            event,
            from,
            to: memory.state,
            influence_before,
            influence_after: memory.current_influence,
            supersession_pressure_before,
            supersession_pressure_after: memory.supersession_pressure,
            reactivation_pressure_before,
            reactivation_pressure_after: memory.reactivation_pressure,
            reason: transition_reason(
                from,
                memory.state,
                event,
                &memory,
                self,
                &supersession,
                &reactivation,
            ),
        };
        memory.transition_history.push(transition.clone());

        TemporalTransitionReport { memory, transition }
    }
}

fn update_evidence_counts(memory: &mut TemporalMemoryProfile, event: TemporalEvent) {
    match event {
        TemporalEvent::Contradiction | TemporalEvent::NewPreference => {
            memory.contradiction_count = memory.contradiction_count.saturating_add(1);
        }
        TemporalEvent::FailureOutcome => {
            memory.failure_count = memory.failure_count.saturating_add(1);
        }
        TemporalEvent::SupportingEvidence => {
            memory.contradiction_count = memory.contradiction_count.saturating_sub(1);
            memory.failure_count = memory.failure_count.saturating_sub(1);
        }
    }
}

fn next_state(
    current: MemoryInfluenceState,
    event: TemporalEvent,
    memory: &TemporalMemoryProfile,
    config: &RuleBasedTemporalTransitionEngine,
    supersession: &SupersessionDecision,
    reactivation: &ReactivationDecision,
) -> MemoryInfluenceState {
    match (current, event) {
        (MemoryInfluenceState::Active, TemporalEvent::Contradiction)
        | (MemoryInfluenceState::Active, TemporalEvent::FailureOutcome)
        | (MemoryInfluenceState::Active, TemporalEvent::NewPreference) => {
            if supersession.should_supersede {
                MemoryInfluenceState::Superseded
            } else {
                MemoryInfluenceState::Challenged
            }
        }
        (MemoryInfluenceState::Challenged, _) if supersession.should_supersede => {
            MemoryInfluenceState::Superseded
        }
        (MemoryInfluenceState::Challenged, TemporalEvent::FailureOutcome)
            if memory.failure_count >= config.supersede_after_failures =>
        {
            MemoryInfluenceState::Superseded
        }
        (MemoryInfluenceState::Challenged, TemporalEvent::Contradiction)
        | (MemoryInfluenceState::Challenged, TemporalEvent::NewPreference)
            if memory.contradiction_count >= 2 =>
        {
            MemoryInfluenceState::Superseded
        }
        (MemoryInfluenceState::Superseded, TemporalEvent::SupportingEvidence)
            if reactivation.should_reactivate =>
        {
            MemoryInfluenceState::Challenged
        }
        (MemoryInfluenceState::Superseded, _) => MemoryInfluenceState::Superseded,
        (state, TemporalEvent::SupportingEvidence) => state,
        (state, _) => state,
    }
}

fn influence_for_state(
    state: MemoryInfluenceState,
    base_influence: f32,
    config: RuleBasedTemporalTransitionEngine,
) -> f32 {
    let base_influence = sanitize_influence(base_influence);
    match state {
        MemoryInfluenceState::Active => base_influence,
        MemoryInfluenceState::Challenged => base_influence * config.challenged_multiplier,
        MemoryInfluenceState::Superseded => base_influence * config.superseded_multiplier,
    }
    .clamp(0.0, 1.0)
}

fn transition_reason(
    from: MemoryInfluenceState,
    to: MemoryInfluenceState,
    event: TemporalEvent,
    memory: &TemporalMemoryProfile,
    config: &RuleBasedTemporalTransitionEngine,
    supersession: &SupersessionDecision,
    reactivation: &ReactivationDecision,
) -> String {
    match (from, to, event) {
        (MemoryInfluenceState::Active, MemoryInfluenceState::Challenged, _) => {
            format!(
                "challenged: later evidence raised displacement pressure to {:.2}",
                supersession.pressure_after
            )
        }
        (_, MemoryInfluenceState::Superseded, _) if supersession.should_supersede => {
            format!(
                "superseded: displacement pressure {:.2} crossed threshold {:.2}",
                supersession.pressure_after, supersession.threshold
            )
        }
        (
            MemoryInfluenceState::Challenged,
            MemoryInfluenceState::Superseded,
            TemporalEvent::FailureOutcome,
        ) => {
            format!(
                "superseded: repeated failure evidence reached threshold {}",
                config.supersede_after_failures
            )
        }
        (MemoryInfluenceState::Challenged, MemoryInfluenceState::Superseded, _) => {
            "superseded: repeated contradictory evidence changed future influence".to_string()
        }
        (
            MemoryInfluenceState::Superseded,
            MemoryInfluenceState::Challenged,
            TemporalEvent::SupportingEvidence,
        ) => {
            format!(
                "reactivated: supporting evidence pressure {:.2} crossed threshold {:.2}",
                reactivation.pressure_after, reactivation.threshold
            )
        }
        (MemoryInfluenceState::Superseded, MemoryInfluenceState::Superseded, _) => {
            format!(
                "preserved: memory remains stored while influence stays low; reactivation pressure is {:.2}",
                reactivation.pressure_after
            )
        }
        (_, _, TemporalEvent::SupportingEvidence)
            if memory.contradiction_count == 0 && memory.failure_count == 0 =>
        {
            "stable: supporting evidence preserved current influence".to_string()
        }
        _ if from == to => "stable: evidence did not cross transition threshold".to_string(),
        _ => "updated: temporal evidence changed influence state".to_string(),
    }
}

fn sanitize_influence(value: f32) -> f32 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        0.0
    }
}

fn default_config() -> RuleBasedTemporalTransitionEngine {
    RuleBasedTemporalTransitionEngine::new(
        DEFAULT_CHALLENGED_MULTIPLIER,
        DEFAULT_SUPERSEDED_MULTIPLIER,
        DEFAULT_SUPERSEDE_AFTER_FAILURES,
    )
}
