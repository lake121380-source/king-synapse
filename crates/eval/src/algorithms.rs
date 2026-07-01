use crate::{AlgorithmMetric, BenchmarkReport};
use std::collections::BTreeMap;
use synapse_core::{
    AlgorithmContext, DeterministicReflectionAlgorithm, ForgetAlgorithm, ForgetOutput,
    ForgetTarget, InMemoryMemoryEventStream, Memory, MemoryEvent, MemoryEventId, MemoryEventKind,
    MemoryEventPayload, MemoryEventStream, MemoryKind, MergeAlgorithm, MergeOutput, MergeTarget,
    ReflectionAlgorithm, ReflectionOutput, RuleBasedForgetAlgorithm, RuleBasedMergeAlgorithm,
    RuleBasedReflectionAlgorithm, Scope, Source, UniformImportanceEstimator,
};

const REFLECTION_BENCHMARK_NAME: &str = "reflection-yield";
const RULE_BASED_REFLECTION_BENCHMARK_NAME: &str = "reflection-yield-rule-based";
const MERGE_BENCHMARK_NAME: &str = "merge-precision";
const FORGET_BENCHMARK_NAME: &str = "forget-precision";

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

/// Run the RFC-013 rule-based Merge benchmark.
///
/// `MergePrecision` is the fraction of emitted `Merge` decisions that are
/// known true positives in the deterministic fixture. `Candidate` decisions
/// are intentionally not counted as merge predictions.
pub fn merge_precision_report() -> BenchmarkReport {
    let groups = merge_fixture();
    let importance = UniformImportanceEstimator;
    let events = InMemoryMemoryEventStream::with_capacity(16);
    let now = chrono::DateTime::from_timestamp(1_700_000_000, 0)
        .expect("fixed benchmark timestamp must be valid");
    let ctx = AlgorithmContext::new(now, None, &importance, &events);
    let algorithm = RuleBasedMergeAlgorithm::default();

    let mut true_positives = 0usize;
    let mut false_positives = 0usize;

    for (target, expected_merge) in groups {
        let predicted_merge = matches!(algorithm.merge(&target, &ctx), MergeOutput::Merge { .. });
        if predicted_merge && expected_merge {
            true_positives += 1;
        } else if predicted_merge {
            false_positives += 1;
        }
    }

    let predicted_count = true_positives + false_positives;
    let precision = if predicted_count == 0 {
        0.0
    } else {
        true_positives as f64 / predicted_count as f64
    };

    BenchmarkReport {
        benchmark: MERGE_BENCHMARK_NAME.to_string(),
        metrics: BTreeMap::from([(AlgorithmMetric::MergePrecision, precision)]),
    }
}

/// Run the RFC-014 rule-based Forget benchmark.
///
/// `ForgetPrecision` is the fraction of emitted `Forget` decisions that are
/// known true positives in the deterministic fixture. `Candidate` decisions
/// are intentionally not counted as forget predictions.
pub fn forget_precision_report() -> BenchmarkReport {
    let groups = forget_fixture();
    let importance = UniformImportanceEstimator;
    let events = InMemoryMemoryEventStream::with_capacity(16);
    let now = chrono::DateTime::from_timestamp(1_700_000_000, 0)
        .expect("fixed benchmark timestamp must be valid");
    let ctx = AlgorithmContext::new(now, None, &importance, &events);
    let algorithm = RuleBasedForgetAlgorithm::default();

    let mut true_positives = 0usize;
    let mut false_positives = 0usize;

    for (target, expected_forget) in groups {
        let predicted_forget =
            matches!(algorithm.forget(&target, &ctx), ForgetOutput::Forget { .. });
        if predicted_forget && expected_forget {
            true_positives += 1;
        } else if predicted_forget {
            false_positives += 1;
        }
    }

    let predicted_count = true_positives + false_positives;
    let precision = if predicted_count == 0 {
        0.0
    } else {
        true_positives as f64 / predicted_count as f64
    };

    BenchmarkReport {
        benchmark: FORGET_BENCHMARK_NAME.to_string(),
        metrics: BTreeMap::from([(AlgorithmMetric::ForgetPrecision, precision)]),
    }
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

fn merge_fixture() -> Vec<(MergeTarget, bool)> {
    let mut superseded_duplicate = memory_with_kind(
        "merge-superseded-b",
        MemoryKind::Failure,
        Scope::Global,
        "Fix JWT refresh error by rotating token cache.",
    );
    superseded_duplicate.superseded_by = Some("merge-newer".to_string());

    vec![
        (
            MergeTarget::new(vec![
                memory_with_kind(
                    "merge-duplicate-a",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Fix JWT refresh error by rotating token cache.",
                ),
                memory_with_kind(
                    "merge-duplicate-b",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Fix JWT refresh error by rotating token cache.",
                ),
            ]),
            true,
        ),
        (
            MergeTarget::new(vec![
                memory_with_kind(
                    "merge-preference-a",
                    MemoryKind::Preference,
                    Scope::User,
                    "Prefer concise Chinese summaries.",
                ),
                memory_with_kind(
                    "merge-preference-b",
                    MemoryKind::Preference,
                    Scope::User,
                    "Prefer concise Chinese summaries.",
                ),
            ]),
            true,
        ),
        (
            MergeTarget::new(vec![
                memory_with_kind(
                    "merge-candidate-a",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Fix JWT refresh error in auth middleware.",
                ),
                memory_with_kind(
                    "merge-candidate-b",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Avoid JWT refresh failure in auth handler.",
                ),
            ]),
            false,
        ),
        (
            MergeTarget::new(vec![
                memory_with_kind(
                    "merge-unrelated-a",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Fix JWT refresh error.",
                ),
                memory_with_kind(
                    "merge-unrelated-b",
                    MemoryKind::Preference,
                    Scope::User,
                    "Prefer concise Chinese summaries.",
                ),
            ]),
            false,
        ),
        (
            MergeTarget::new(vec![
                memory_with_kind(
                    "merge-superseded-a",
                    MemoryKind::Failure,
                    Scope::Global,
                    "Fix JWT refresh error by rotating token cache.",
                ),
                superseded_duplicate,
            ]),
            false,
        ),
    ]
}

fn forget_fixture() -> Vec<(ForgetTarget, bool)> {
    let mut expired = memory_with_kind(
        "forget-expired",
        MemoryKind::State,
        Scope::Global,
        "Expired temporary deploy state.",
    );
    expired.valid_to = Some(1);

    let mut superseded = memory_with_kind(
        "forget-superseded",
        MemoryKind::Fact,
        Scope::Global,
        "Old vector dimension was 384.",
    );
    superseded.superseded_by = Some("new-vector-dim".to_string());

    let mut stale_scratch = memory_with_kind(
        "forget-stale-scratch",
        MemoryKind::State,
        Scope::Global,
        "todo",
    );
    stale_scratch.confidence = 0.2;
    stale_scratch.importance = 0.1;
    stale_scratch.valid_from = 1_600_000_000;

    let mut protected = memory_with_kind(
        "forget-protected",
        MemoryKind::Playbook,
        Scope::Global,
        "Critical recovery playbook must be retained.",
    );
    protected.importance = 0.95;
    protected.valid_from = 1_600_000_000;

    let mut recent = memory_with_kind(
        "forget-recent",
        MemoryKind::Fact,
        Scope::Global,
        "Recently used deployment note.",
    );
    recent.importance = 0.1;
    recent.confidence = 0.1;
    recent.last_accessed_at = Some(1_700_000_000 - 60);

    let mut candidate = memory_with_kind(
        "forget-candidate",
        MemoryKind::Fact,
        Scope::Global,
        "Old rarely used fact.",
    );
    candidate.confidence = 0.7;
    candidate.importance = 0.4;
    candidate.valid_from = 1_600_000_000;

    vec![
        (ForgetTarget::new(expired), true),
        (ForgetTarget::new(superseded), true),
        (ForgetTarget::new(stale_scratch), true),
        (ForgetTarget::new(protected), false),
        (ForgetTarget::new(recent), false),
        (ForgetTarget::new(candidate), false),
    ]
}

fn memory(id: &str, content: &str) -> Memory {
    memory_with_kind(id, MemoryKind::Fact, Scope::Global, content)
}

fn memory_with_kind(id: &str, kind: MemoryKind, scope: Scope, content: &str) -> Memory {
    Memory {
        id: id.to_string(),
        kind,
        scope,
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

    #[test]
    fn merge_precision_report_is_deterministic() {
        let a = merge_precision_report();
        let b = merge_precision_report();

        assert_eq!(a, b);
    }

    #[test]
    fn merge_precision_report_uses_contract_shape() {
        let report = merge_precision_report();

        assert_eq!(report.benchmark, "merge-precision");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::MergePrecision),
            Some(&1.0)
        );
    }

    #[test]
    fn forget_precision_report_is_deterministic() {
        let a = forget_precision_report();
        let b = forget_precision_report();

        assert_eq!(a, b);
    }

    #[test]
    fn forget_precision_report_uses_contract_shape() {
        let report = forget_precision_report();

        assert_eq!(report.benchmark, "forget-precision");
        assert_eq!(report.metrics.len(), 1);
        assert_eq!(
            report.metrics.get(&AlgorithmMetric::ForgetPrecision),
            Some(&1.0)
        );
    }
}
