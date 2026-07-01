//! Benchmark harness contract (RFC-011 Part D, v0.5.3).
//!
//! This module freezes two types that every Phase 5 benchmark must speak:
//!
//! - [`AlgorithmMetric`] — the stable set of metric IDs
//! - [`BenchmarkReport`] — the unified, deterministic value object that
//!   every benchmark returns
//!
//! It does NOT define:
//! - how to compute any specific metric,
//! - how to load a dataset,
//! - how to run a benchmark,
//! - how to export a report.
//!
//! Those responsibilities belong to individual benchmark implementations
//! and (in the future) a separate exporter layer. Keeping this module
//! contract-only is intentional and enforced by RFC-011.
//!
//! ## Invariants
//!
//! - **Deterministic** (RFC-011 Part D rule 1). A `BenchmarkReport` is a
//!   pure function of `(dataset, algorithm, config)`. It MUST NOT carry
//!   runtime metadata such as `timestamp`, `hostname`, `cpu`,
//!   `random_seed`, or `git_dirty`.
//! - **Sparse** (RFC-011 Part D rule 2). A report contains only the
//!   metrics that are meaningful for that benchmark. Missing metrics
//!   are NOT interpreted as `0.0`.
//! - **Finite** (RFC-011 Part D rule 3, SHOULD). Producers SHOULD emit
//!   finite `f64` values. `NaN` / `Inf` are neither validated nor
//!   forbidden by the harness.
//! - **`BTreeMap`, not `HashMap`.** Iteration order is deterministic so
//!   serialized reports diff cleanly in CI.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Stable metric identifiers used across every Phase 5 benchmark.
///
/// Marked `#[non_exhaustive]` so future metrics may be added without
/// breaking downstream `match` arms. The exact numerical definition of
/// each variant is fixed by the benchmark implementation that emits it,
/// not by this enum. Algorithms MUST NOT read metric values.
///
/// `EventReplayLatency` (cost of `MemoryEventStream::recent`) and
/// `AlgorithmLatency` (cost of one `algorithm.run(target, ctx)` call)
/// are intentionally distinct and MUST NOT be collapsed by any
/// consumer.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[non_exhaustive]
pub enum AlgorithmMetric {
    RecallAt10,
    PrecisionAt10,
    MemoryGrowth,
    CompressionRatio,
    ReflectionYield,
    MergePrecision,
    ForgetPrecision,
    HebbianConsistency,
    EventReplayLatency,
    AlgorithmLatency,
}

/// Unified benchmark output. Every Phase 5 benchmark returns a value of
/// this shape.
///
/// `benchmark` is a free-form string; by convention it uses
/// `lowercase-kebab-case` (e.g. `"reference-recall"`, `"reflection-yield"`).
/// The convention is documented, not enforced by the type.
///
/// `metrics` is a `BTreeMap` (not a `HashMap`) so the serialized order is
/// deterministic — required for CI-friendly diffs.
///
/// Marked `#[non_exhaustive]` so future minor versions may add fields
/// without breaking downstream constructions. New fields MUST preserve
/// the deterministic-value-object invariant: no timestamps, no hostnames,
/// no runtime metadata.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[non_exhaustive]
pub struct BenchmarkReport {
    pub benchmark: String,
    pub metrics: BTreeMap<AlgorithmMetric, f64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn all_ten_metrics_are_distinct() {
        let all = [
            AlgorithmMetric::RecallAt10,
            AlgorithmMetric::PrecisionAt10,
            AlgorithmMetric::MemoryGrowth,
            AlgorithmMetric::CompressionRatio,
            AlgorithmMetric::ReflectionYield,
            AlgorithmMetric::MergePrecision,
            AlgorithmMetric::ForgetPrecision,
            AlgorithmMetric::HebbianConsistency,
            AlgorithmMetric::EventReplayLatency,
            AlgorithmMetric::AlgorithmLatency,
        ];
        assert_eq!(all.len(), 10);
        for i in 0..all.len() {
            for j in (i + 1)..all.len() {
                assert_ne!(all[i], all[j]);
            }
        }
    }

    #[test]
    fn algorithm_metric_is_copy() {
        fn assert_copy<T: Copy>() {}
        assert_copy::<AlgorithmMetric>();
    }

    #[test]
    fn algorithm_metric_ord_enables_btreemap() {
        // Compile + runtime proof: AlgorithmMetric can key a BTreeMap.
        let mut m: BTreeMap<AlgorithmMetric, f64> = BTreeMap::new();
        m.insert(AlgorithmMetric::RecallAt10, 1.0);
        m.insert(AlgorithmMetric::AlgorithmLatency, 0.5);
        assert_eq!(m.len(), 2);
    }

    #[test]
    fn algorithm_metric_serde_roundtrip() {
        let m = AlgorithmMetric::EventReplayLatency;
        let json = serde_json::to_string(&m).unwrap();
        assert_eq!(json, "\"EventReplayLatency\"");
        let back: AlgorithmMetric = serde_json::from_str(&json).unwrap();
        assert_eq!(back, m);
    }

    #[test]
    fn benchmark_report_iteration_is_deterministic() {
        let mut a = BenchmarkReport {
            benchmark: "example".to_string(),
            metrics: BTreeMap::new(),
        };
        a.metrics.insert(AlgorithmMetric::AlgorithmLatency, 2.0);
        a.metrics.insert(AlgorithmMetric::RecallAt10, 1.0);
        a.metrics.insert(AlgorithmMetric::MemoryGrowth, 3.0);

        let mut b = BenchmarkReport {
            benchmark: "example".to_string(),
            metrics: BTreeMap::new(),
        };
        // Different insertion order.
        b.metrics.insert(AlgorithmMetric::MemoryGrowth, 3.0);
        b.metrics.insert(AlgorithmMetric::RecallAt10, 1.0);
        b.metrics.insert(AlgorithmMetric::AlgorithmLatency, 2.0);

        // BTreeMap iterates in key order regardless of insertion order.
        let a_order: Vec<_> = a.metrics.keys().collect();
        let b_order: Vec<_> = b.metrics.keys().collect();
        assert_eq!(a_order, b_order);
        assert_eq!(a, b);
    }

    #[test]
    fn benchmark_report_is_sparse_by_design() {
        // Rule: missing metrics MUST NOT be interpreted as 0.0.
        // The harness contract encodes this by making metrics a map, not
        // a struct with one field per metric. Absent keys simply don't
        // exist; there is no default.
        let report = BenchmarkReport {
            benchmark: "recall-only".to_string(),
            metrics: BTreeMap::from([(AlgorithmMetric::RecallAt10, 1.0)]),
        };
        assert_eq!(report.metrics.len(), 1);
        assert!(!report
            .metrics
            .contains_key(&AlgorithmMetric::AlgorithmLatency));
    }

    #[test]
    fn benchmark_report_serde_roundtrip() {
        let original = BenchmarkReport {
            benchmark: "reference-recall".to_string(),
            metrics: BTreeMap::from([
                (AlgorithmMetric::RecallAt10, 1.0),
                (AlgorithmMetric::AlgorithmLatency, 0.42),
            ]),
        };
        let json = serde_json::to_string(&original).unwrap();
        let decoded: BenchmarkReport = serde_json::from_str(&json).unwrap();
        assert_eq!(decoded, original);
    }

    #[test]
    fn benchmark_report_no_runtime_metadata() {
        // Compile-time proof (via structural exhaustiveness) that
        // BenchmarkReport has no runtime-metadata fields. If someone
        // adds `timestamp` / `hostname` / `random_seed`, this test must
        // be updated AND RFC-011 Part D rule 1 (D8) must be revisited.
        let r = BenchmarkReport {
            benchmark: "x".to_string(),
            metrics: BTreeMap::new(),
        };
        // Every allowed field is destructured here:
        let BenchmarkReport { benchmark, metrics } = &r;
        assert_eq!(benchmark, "x");
        assert!(metrics.is_empty());
    }
}
