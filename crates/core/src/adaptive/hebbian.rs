//! Hebbian Algorithm skeleton and rule-based reference (RFC-015).
//!
//! This module is algorithm-local. It consumes `MemoryEvent + AlgorithmContext`
//! from RFC-011 and does not extend the shared adaptive model.

use crate::adaptive::{AlgorithmContext, MemoryEvent, MemoryEventKind, MemoryEventPayload};
use crate::working_memory::EdgeUpdatePlan;
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

const DEFAULT_EDGE_DELTA: f32 = 0.1;
const DEFAULT_MAX_EDGES: usize = 32;

pub trait HebbianAlgorithm {
    fn reinforce(&self, target: &HebbianTarget, ctx: &AlgorithmContext<'_>) -> HebbianOutput;
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct HebbianTarget {
    pub events: Vec<MemoryEvent>,
}

impl HebbianTarget {
    pub fn new(events: Vec<MemoryEvent>) -> Self {
        Self { events }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub enum HebbianOutput {
    Skipped {
        reason: HebbianSkipReason,
    },
    Plans {
        plans: Vec<EdgeUpdatePlan>,
        evidence_count: usize,
    },
}

impl HebbianOutput {
    pub fn is_empty(&self) -> bool {
        matches!(
            self,
            Self::Skipped {
                reason: HebbianSkipReason::NoOp
            }
        )
    }

    pub fn plans(&self) -> &[EdgeUpdatePlan] {
        match self {
            Self::Plans { plans, .. } => plans,
            Self::Skipped { .. } => &[],
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[non_exhaustive]
pub enum HebbianSkipReason {
    NoOp,
    EmptyEvents,
    InsufficientCooccurrence,
}

#[derive(Debug, Clone, Copy, Default)]
pub struct NoOpHebbianAlgorithm;

impl HebbianAlgorithm for NoOpHebbianAlgorithm {
    fn reinforce(&self, _target: &HebbianTarget, _ctx: &AlgorithmContext<'_>) -> HebbianOutput {
        HebbianOutput::Skipped {
            reason: HebbianSkipReason::NoOp,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct RuleBasedHebbianAlgorithm {
    edge_delta: f32,
    max_edges: usize,
}

impl RuleBasedHebbianAlgorithm {
    pub fn new(edge_delta: f32, max_edges: usize) -> Self {
        let edge_delta = if edge_delta.is_finite() {
            edge_delta.max(0.0)
        } else {
            DEFAULT_EDGE_DELTA
        };
        Self {
            edge_delta,
            max_edges,
        }
    }

    pub fn edge_delta(&self) -> f32 {
        self.edge_delta
    }

    pub fn max_edges(&self) -> usize {
        self.max_edges
    }
}

impl Default for RuleBasedHebbianAlgorithm {
    fn default() -> Self {
        Self::new(DEFAULT_EDGE_DELTA, DEFAULT_MAX_EDGES)
    }
}

impl HebbianAlgorithm for RuleBasedHebbianAlgorithm {
    fn reinforce(&self, target: &HebbianTarget, _ctx: &AlgorithmContext<'_>) -> HebbianOutput {
        if target.events.is_empty() {
            return HebbianOutput::Skipped {
                reason: HebbianSkipReason::EmptyEvents,
            };
        }

        let mut plans = Vec::new();
        let mut seen = BTreeSet::new();
        let mut evidence_count = 0usize;

        for event in &target.events {
            let memory_ids = normalized_memory_ids(event);
            if memory_ids.len() < 2 {
                continue;
            }

            evidence_count += 1;
            let delta = self.edge_delta * event_weight(event);
            for source in &memory_ids {
                for target in &memory_ids {
                    if source == target {
                        continue;
                    }
                    if !seen.insert((source.clone(), target.clone())) {
                        continue;
                    }
                    plans.push(EdgeUpdatePlan {
                        source: source.clone(),
                        target: target.clone(),
                        weight_delta: delta,
                    });
                    if plans.len() >= self.max_edges {
                        return HebbianOutput::Plans {
                            plans,
                            evidence_count,
                        };
                    }
                }
            }
        }

        if plans.is_empty() {
            HebbianOutput::Skipped {
                reason: HebbianSkipReason::InsufficientCooccurrence,
            }
        } else {
            HebbianOutput::Plans {
                plans,
                evidence_count,
            }
        }
    }
}

fn normalized_memory_ids(event: &MemoryEvent) -> Vec<String> {
    event
        .memory_ids
        .iter()
        .filter_map(|id| {
            let id = id.trim();
            if id.is_empty() {
                None
            } else {
                Some(id.to_string())
            }
        })
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect()
}

fn event_weight(event: &MemoryEvent) -> f32 {
    let base = match event.kind {
        MemoryEventKind::Recalled => 1.0,
        MemoryEventKind::Written => 0.7,
        MemoryEventKind::Updated => 0.8,
        MemoryEventKind::Invalidated => 0.3,
        MemoryEventKind::Reflected => 1.2,
        MemoryEventKind::Reinforced => 1.4,
        MemoryEventKind::MergeCompleted => 1.3,
        MemoryEventKind::Forgotten => 0.2,
    };

    match &event.payload {
        MemoryEventPayload::Recalled { hit_count, .. } if *hit_count > 1 => base + 0.1,
        MemoryEventPayload::Reinforced { delta, .. } if delta.is_finite() => {
            base + delta.abs().min(0.5)
        }
        _ => base,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adaptive::{NoOpImportanceEstimator, NoOpMemoryEventStream};
    use chrono::Utc;

    fn event(kind: MemoryEventKind, memory_ids: &[&str]) -> MemoryEvent {
        MemoryEvent {
            id: crate::adaptive::MemoryEventId::nil(),
            timestamp: Utc::now(),
            session_id: None,
            kind,
            memory_ids: memory_ids.iter().map(|id| id.to_string()).collect(),
            payload: MemoryEventPayload::Empty,
        }
    }

    fn ctx<'a>(
        importance: &'a NoOpImportanceEstimator,
        events: &'a NoOpMemoryEventStream,
    ) -> AlgorithmContext<'a> {
        AlgorithmContext::new(Utc::now(), None, importance, events)
    }

    #[test]
    fn noop_hebbian_algorithm_returns_empty_output() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let algorithm = NoOpHebbianAlgorithm;

        let output = algorithm.reinforce(&HebbianTarget::default(), &ctx(&importance, &events));

        assert_eq!(
            output,
            HebbianOutput::Skipped {
                reason: HebbianSkipReason::NoOp,
            }
        );
        assert!(output.is_empty());
    }

    #[test]
    fn rule_based_hebbian_skips_empty_events() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let algorithm = RuleBasedHebbianAlgorithm::default();

        let output = algorithm.reinforce(&HebbianTarget::default(), &ctx(&importance, &events));

        assert_eq!(
            output,
            HebbianOutput::Skipped {
                reason: HebbianSkipReason::EmptyEvents,
            }
        );
    }

    #[test]
    fn rule_based_hebbian_skips_single_memory_events() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let algorithm = RuleBasedHebbianAlgorithm::default();
        let target = HebbianTarget::new(vec![event(MemoryEventKind::Recalled, &["a"])]);

        let output = algorithm.reinforce(&target, &ctx(&importance, &events));

        assert_eq!(
            output,
            HebbianOutput::Skipped {
                reason: HebbianSkipReason::InsufficientCooccurrence,
            }
        );
    }

    #[test]
    fn rule_based_hebbian_generates_bidirectional_edges() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let algorithm = RuleBasedHebbianAlgorithm::default();
        let target = HebbianTarget::new(vec![event(MemoryEventKind::Recalled, &["b", "a"])]);

        let output = algorithm.reinforce(&target, &ctx(&importance, &events));

        assert_eq!(
            output,
            HebbianOutput::Plans {
                plans: vec![
                    EdgeUpdatePlan {
                        source: "a".to_string(),
                        target: "b".to_string(),
                        weight_delta: 0.1,
                    },
                    EdgeUpdatePlan {
                        source: "b".to_string(),
                        target: "a".to_string(),
                        weight_delta: 0.1,
                    },
                ],
                evidence_count: 1,
            }
        );
    }

    #[test]
    fn rule_based_hebbian_deduplicates_edges() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let algorithm = RuleBasedHebbianAlgorithm::default();
        let target = HebbianTarget::new(vec![
            event(MemoryEventKind::Recalled, &["a", "b", "a"]),
            event(MemoryEventKind::Updated, &["b", "a"]),
        ]);

        let output = algorithm.reinforce(&target, &ctx(&importance, &events));

        assert_eq!(output.plans().len(), 2);
    }

    #[test]
    fn rule_based_hebbian_respects_max_edges() {
        let importance = NoOpImportanceEstimator;
        let events = NoOpMemoryEventStream;
        let algorithm = RuleBasedHebbianAlgorithm::new(0.2, 3);
        let target = HebbianTarget::new(vec![event(
            MemoryEventKind::MergeCompleted,
            &["a", "b", "c"],
        )]);

        let output = algorithm.reinforce(&target, &ctx(&importance, &events));

        assert!(matches!(
            output,
            HebbianOutput::Plans {
                plans,
                evidence_count: 1,
            } if plans.len() == 3
        ));
    }

    #[test]
    fn rule_based_hebbian_config_is_sanitized() {
        let algorithm = RuleBasedHebbianAlgorithm::new(f32::NAN, 7);

        assert_eq!(algorithm.edge_delta(), 0.1);
        assert_eq!(algorithm.max_edges(), 7);
    }
}
