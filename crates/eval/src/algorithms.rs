use crate::{AlgorithmMetric, BenchmarkReport};
use std::collections::BTreeMap;
use synapse_core::{
    AlgorithmContext, DeterministicReflectionAlgorithm, InMemoryMemoryEventStream, Memory,
    MemoryEvent, MemoryEventId, MemoryEventKind, MemoryEventPayload, MemoryEventStream, MemoryKind,
    ReflectionAlgorithm, ReflectionOutput, RuleBasedReflectionAlgorithm, Scope, Source,
    UniformImportanceEstimator,
};

const REFLECTION_BENCHMARK_NAME: &str = "reflection-yield";
const RULE_BASED_REFLECTION_BENCHMARK_NAME: &str = "reflection-yield-rule-based";

/// Run the RFC-012 deterministic reference benchmark for Reflection.
///
/// `ReflectionYield` is the fraction of structurally eligible memories that
/// produce a candidate output. The fixture is intentionally small and fixed so
/// the `BenchmarkReport` remains a deterministic value object.
pub fn reflection_yield_report() -> BenchmarkReport {
    reflection_yield_report_for(
        REFLECTION_BENCHMARK_NAME,
        &DeterministicReflectionAlgorithm::default(),
    )
}

/// Run the v0.6.6 rule-based Reflection benchmark.
pub fn rule_based_reflection_yield_report() -> BenchmarkReport {
    reflection_yield_report_for(
        RULE_BASED_REFLECTION_BENCHMARK_NAME,
        &RuleBasedReflectionAlgorithm::default(),
    )
}

fn reflection_yield_report_for(
    benchmark_name: &str,
    algorithm: &dyn ReflectionAlgorithm,
) -> BenchmarkReport {
    let memories = reflection_fixture();
    let eligible_count = memories
        .iter()
        .filter(|memory| is_reflection_eligible(memory))
        .count();

    let importance = UniformImportanceEstimator;
    let events = InMemoryMemoryEventStream::with_capacity(16);
    let now = chrono::DateTime::from_timestamp(1_700_000_000, 0)
        .expect("fixed benchmark timestamp must be valid");

    for memory in &memories {
        if is_reflection_eligible(memory) {
            events.record(MemoryEvent {
                id: MemoryEventId::nil(),
                timestamp: now,
                session_id: None,
                kind: MemoryEventKind::Written,
                memory_ids: vec![memory.id.clone()],
                payload: MemoryEventPayload::Empty,
            });
        }
    }

    let ctx = AlgorithmContext::new(now, None, &importance, &events);
    let produced_count = memories
        .iter()
        .filter(|memory| {
            matches!(
                algorithm.reflect(memory, &ctx),
                ReflectionOutput::Candidate { .. } | ReflectionOutput::Produced { .. }
            )
        })
        .count();

    let yield_value = if eligible_count == 0 {
        0.0
    } else {
        produced_count as f64 / eligible_count as f64
    };

    BenchmarkReport {
        benchmark: benchmark_name.to_string(),
        metrics: BTreeMap::from([(AlgorithmMetric::ReflectionYield, yield_value)]),
    }
}

fn is_reflection_eligible(memory: &Memory) -> bool {
    !memory.content.trim().is_empty() && memory.valid_to.is_none() && memory.superseded_by.is_none()
}

fn reflection_fixture() -> Vec<Memory> {
    let mut superseded = memory("m-superseded", "Old belief superseded by a newer memory.");
    superseded.superseded_by = Some("m-newer".to_string());

    let mut expired = memory("m-expired", "Expired temporary state.");
    expired.valid_to = Some(1);

    vec![
        memory(
            "m-fact",
            "JWT refresh failures should be reflected after repeated 401 fixes.",
        ),
        memory(
            "m-preference",
            "User prefers concise Chinese summaries for project handoffs.",
        ),
        memory(
            "m-playbook",
            "When SQLite FTS misses CJK text, check tokenizer settings first.",
        ),
        memory("m-empty", "   "),
        superseded,
        expired,
    ]
}

fn memory(id: &str, content: &str) -> Memory {
    Memory {
        id: id.to_string(),
        kind: MemoryKind::Fact,
        scope: Scope::Global,
        content: content.to_string(),
        source: Source::ExplicitUser,
        confidence: 1.0,
        importance: 0.5,
        valid_from: 0,
        valid_to: None,
        superseded_by: None,
        access_count: 0,
        last_accessed_at: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reflection_yield_report_is_deterministic() {
        let a = reflection_yield_report();
        let b = reflection_yield_report();

        assert_eq!(a, b);
    }

    #[test]
    fn reflection_yield_report_uses_contract_shape() {
        let report = reflection_yield_report();

        assert_eq!(report.benchmark, "reflection-yield");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::ReflectionYield),
            Some(&1.0)
        );
    }

    #[test]
    fn rule_based_reflection_yield_report_uses_contract_shape() {
        let report = rule_based_reflection_yield_report();

        assert_eq!(report.benchmark, "reflection-yield-rule-based");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::ReflectionYield),
            Some(&1.0)
        );
    }
}
