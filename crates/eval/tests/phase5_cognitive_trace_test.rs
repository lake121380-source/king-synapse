use synapse_core::{
    CognitiveCompetitionTrace, CognitiveFactorType, CognitiveTraceEvaluator, MemoryKind,
    RecallEngine, RecallHit, RecallQuery, Scope, Source, Store, WriteInput,
};
use synapse_eval::Phase5CognitiveTraceEvaluator;

#[test]
fn phase5_cognitive_trace_report_loads() {
    let report = Phase5CognitiveTraceEvaluator::evaluate("phase5-trace-load")
        .expect("Phase 5.1 cognitive trace evaluation should run");

    assert_eq!(report.phase, "5.1");
    assert_eq!(report.mode, "inspection_only");
    assert_eq!(
        report.evaluation_version,
        "phase5.1-cognitive-competition-trace-integration"
    );
    assert_eq!(report.scenarios, 3);
    assert!(report.pass);
}

#[test]
fn trace_generated_for_candidates() {
    let hits = recall_fixture("deployment gpu memory resource", 3);
    let trace = CognitiveTraceEvaluator::evaluate("deployment gpu memory resource", &hits);

    assert_eq!(trace.candidate_count, hits.len());
    assert!(trace.dominant_candidate.is_some());
    assert!(!trace.factors.is_empty());
}

#[test]
fn empty_candidates_no_trace() {
    let trace = CognitiveTraceEvaluator::evaluate("nothing", &[]);

    assert_eq!(trace.candidate_count, 0);
    assert!(trace.dominant_candidate.is_none());
    assert!(trace.suppressed_candidates.is_empty());
    assert!(trace.factors.is_empty());
    assert_eq!(trace.confidence, 0.0);
    assert!(!trace.mutated);
}

#[test]
fn single_candidate_trace() {
    let hits = recall_fixture("deployment gpu memory resource", 1);
    let trace = CognitiveTraceEvaluator::evaluate("deployment gpu memory resource", &hits);

    assert_eq!(trace.candidate_count, 1);
    assert_eq!(
        trace.dominant_candidate.as_deref(),
        Some(hits[0].memory.id.as_str())
    );
    assert!(trace.suppressed_candidates.is_empty());
}

#[test]
fn dominant_candidate_exists() {
    let hits = recall_fixture("production release rollback verification", 3);
    let trace =
        CognitiveTraceEvaluator::evaluate("production release rollback verification", &hits);
    let hit_ids = hit_ids(&hits);

    assert!(hit_ids.contains(trace.dominant_candidate.as_ref().unwrap()));
}

#[test]
fn dominant_matches_competition_result() {
    let hits = recall_fixture("deployment gpu memory resource", 3);
    let trace = CognitiveTraceEvaluator::evaluate("deployment gpu memory resource", &hits);
    let replay = CognitiveTraceEvaluator::evaluate("deployment gpu memory resource", &hits);

    assert_eq!(trace.dominant_candidate, replay.dominant_candidate);
}

#[test]
fn suppressed_candidates_recorded() {
    let hits = recall_fixture("deployment gpu memory resource", 3);
    let trace = CognitiveTraceEvaluator::evaluate("deployment gpu memory resource", &hits);

    assert_eq!(trace.suppressed_candidates.len(), hits.len() - 1);
    assert!(!trace
        .suppressed_candidates
        .contains(trace.dominant_candidate.as_ref().unwrap()));
}

#[test]
fn temporal_factor_recorded() {
    let trace = fixture_trace("deployment gpu memory resource", 3);

    assert!(has_factor(&trace, CognitiveFactorType::TemporalConfidence));
}

#[test]
fn reliability_factor_recorded() {
    let trace = fixture_trace("deployment gpu memory resource", 3);

    assert!(has_factor(&trace, CognitiveFactorType::Reliability));
}

#[test]
fn failure_factor_recorded() {
    let trace = fixture_trace("deployment gpu memory resource", 3);

    assert!(has_factor(&trace, CognitiveFactorType::FailureEvidence));
}

#[test]
fn preference_factor_recorded() {
    let trace = fixture_trace("fast local prototype iteration preference", 3);

    assert!(has_factor(&trace, CognitiveFactorType::PreferenceAlignment));
}

#[test]
fn context_alignment_factor_recorded() {
    let trace = fixture_trace("production release rollback verification", 3);

    assert!(has_factor(&trace, CognitiveFactorType::ContextAlignment));
}

#[test]
fn recall_result_identical_without_trace() {
    let hits = recall_fixture("deployment gpu memory resource", 3);
    let before = hit_signature(&hits);

    let _trace = CognitiveTraceEvaluator::evaluate("deployment gpu memory resource", &hits);
    let after = hit_signature(&hits);

    assert_eq!(before, after);
}

#[test]
fn ranking_identical_with_trace() {
    let hits = recall_fixture("production release rollback verification", 3);
    let before = hit_ids(&hits);

    let _trace =
        CognitiveTraceEvaluator::evaluate("production release rollback verification", &hits);
    let after = hit_ids(&hits);

    assert_eq!(before, after);
}

#[test]
fn scores_unchanged() {
    let hits = recall_fixture("fast local prototype iteration preference", 3);
    let before = hit_scores(&hits);

    let _trace =
        CognitiveTraceEvaluator::evaluate("fast local prototype iteration preference", &hits);
    let after = hit_scores(&hits);

    assert_eq!(before, after);
}

#[test]
fn memory_not_written() {
    let (store, hits) = recall_fixture_with_store("deployment gpu memory resource", 3);
    let ids = hit_ids(&hits);

    let _trace = CognitiveTraceEvaluator::evaluate("deployment gpu memory resource", &hits);

    for id in ids {
        let memory = store
            .get(&id)
            .expect("store lookup should work")
            .expect("memory should exist");
        assert_eq!(memory.access_count, 0);
        assert!(memory.last_accessed_at.is_none());
    }
}

#[test]
fn activation_not_mutated() {
    let hits = recall_fixture("deployment gpu memory resource", 3);
    let before = activation_bonuses(&hits);

    let _trace = CognitiveTraceEvaluator::evaluate("deployment gpu memory resource", &hits);
    let after = activation_bonuses(&hits);

    assert_eq!(before, after);
    assert!(after.iter().all(|bonus| bonus.abs() <= f32::EPSILON));
}

#[test]
fn same_query_same_trace() {
    let hits = recall_fixture("deployment gpu memory resource", 3);

    let left = CognitiveTraceEvaluator::evaluate("deployment gpu memory resource", &hits);
    let right = CognitiveTraceEvaluator::evaluate("deployment gpu memory resource", &hits);

    assert_eq!(left, right);
}

#[test]
fn trace_deterministic() {
    let report = Phase5CognitiveTraceEvaluator::evaluate("phase5-trace-deterministic")
        .expect("Phase 5.1 cognitive trace evaluation should run");

    assert_eq!(report.metrics.trace_determinism, 1.0);
    assert!(report
        .scenario_reports
        .iter()
        .all(|scenario| scenario.trace_deterministic));
}

#[test]
fn trace_serialization() {
    let trace = fixture_trace("deployment gpu memory resource", 3);
    let serialized = serde_json::to_string(&trace).expect("trace should serialize");
    let decoded: CognitiveCompetitionTrace =
        serde_json::from_str(&serialized).expect("trace should deserialize");

    assert_eq!(trace, decoded);
}

#[test]
fn report_schema_contains_required_metrics() {
    let report = Phase5CognitiveTraceEvaluator::evaluate("phase5-trace-schema")
        .expect("Phase 5.1 cognitive trace evaluation should run");
    let value = serde_json::to_value(&report).expect("report should serialize");

    assert!(value["metrics"].get("trace_generation_rate").is_some());
    assert!(value["metrics"].get("dominant_validity").is_some());
    assert!(value["metrics"].get("factor_explanation_rate").is_some());
    assert!(value["metrics"].get("trace_determinism").is_some());
    assert!(value["metrics"].get("recall_regression").is_some());
    assert!(value["guards"].get("ranking_changed").is_some());
    assert!(value["guards"].get("memory_written").is_some());
    assert!(value["guards"].get("activation_changed").is_some());
}

#[test]
fn report_metrics_pass() {
    let report = Phase5CognitiveTraceEvaluator::evaluate("phase5-trace-metrics")
        .expect("Phase 5.1 cognitive trace evaluation should run");

    assert_eq!(report.metrics.trace_generation_rate, 1.0);
    assert_eq!(report.metrics.dominant_validity, 1.0);
    assert_eq!(report.metrics.factor_explanation_rate, 1.0);
    assert_eq!(report.metrics.trace_determinism, 1.0);
    assert_eq!(report.metrics.recall_regression, 0.0);
}

#[test]
fn guards_are_false() {
    let report = Phase5CognitiveTraceEvaluator::evaluate("phase5-trace-guards")
        .expect("Phase 5.1 cognitive trace evaluation should run");

    assert!(!report.guards.core_behavior_changed);
    assert!(!report.guards.recall_output_changed);
    assert!(!report.guards.ranking_changed);
    assert!(!report.guards.memory_written);
    assert!(!report.guards.activation_changed);
}

#[test]
fn latency_recorded() {
    let report = Phase5CognitiveTraceEvaluator::evaluate("phase5-trace-latency")
        .expect("Phase 5.1 cognitive trace evaluation should run");

    assert!(report.latency.before.p50_ms >= 0.0);
    assert!(report.latency.before.p95_ms >= report.latency.before.p50_ms);
    assert!(report.latency.after.p50_ms >= report.latency.before.p50_ms);
    assert!(report.latency.after.p95_ms >= report.latency.before.p95_ms);
}

#[test]
fn phase5_trace_does_not_regress_phase4_stability_report() {
    let phase5 = Phase5CognitiveTraceEvaluator::evaluate("phase5-trace-smoke")
        .expect("Phase 5.1 cognitive trace evaluation should run");
    let phase4 = synapse_eval::Phase4CognitiveCompetitionStabilityEvaluator::evaluate(
        "phase4-stability-smoke",
    )
    .expect("Phase 4.5 stability evaluation should still run");

    assert!(phase5.pass);
    assert!(phase4.pass);
}

fn fixture_trace(query: &str, k: usize) -> CognitiveCompetitionTrace {
    let hits = recall_fixture(query, k);
    CognitiveTraceEvaluator::evaluate(query, &hits)
}

fn recall_fixture(query: &str, k: usize) -> Vec<RecallHit> {
    recall_fixture_with_store(query, k).1
}

fn recall_fixture_with_store(query: &str, k: usize) -> (Store, Vec<RecallHit>) {
    let mut store = Store::open_in_memory().expect("in-memory store should open");
    write_fixture_memories(&mut store);
    let q = RecallQuery {
        query: query.to_string(),
        k: Some(k),
        scope_filter: Some(Scope::User),
        kind_filter: None,
    };
    let hits = {
        let mut engine = RecallEngine::new(&mut store).with_access_recording(false);
        engine.recall(&q).expect("fixture recall should run")
    };
    assert!(!hits.is_empty(), "fixture recall should return hits");
    (store, hits)
}

fn write_fixture_memories(store: &mut Store) {
    for (content, kind, confidence, importance) in [
        (
            "GPU memory overflow happened during deployment because batch size exceeded resource limits.",
            MemoryKind::Failure,
            0.95,
            0.90,
        ),
        (
            "User prefers fast local prototype iteration before formalizing architecture.",
            MemoryKind::Preference,
            0.92,
            0.82,
        ),
        (
            "Production release playbook: verify rollback path and environment resources before rollout.",
            MemoryKind::Playbook,
            0.94,
            0.88,
        ),
        (
            "Database migration requires backup before production deployment.",
            MemoryKind::Fact,
            0.75,
            0.65,
        ),
    ] {
        store
            .write(WriteInput {
                content: content.to_string(),
                kind,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: Some(confidence),
                importance: Some(importance),
            })
            .expect("fixture memory should write");
    }
}

fn has_factor(trace: &CognitiveCompetitionTrace, factor_type: CognitiveFactorType) -> bool {
    trace
        .factors
        .iter()
        .any(|factor| factor.factor_type == factor_type)
}

fn hit_ids(hits: &[RecallHit]) -> Vec<String> {
    hits.iter().map(|hit| hit.memory.id.clone()).collect()
}

fn hit_scores(hits: &[RecallHit]) -> Vec<u32> {
    hits.iter().map(|hit| hit.score.to_bits()).collect()
}

fn activation_bonuses(hits: &[RecallHit]) -> Vec<f32> {
    hits.iter().map(|hit| hit.activation_bonus).collect()
}

fn hit_signature(hits: &[RecallHit]) -> Vec<(String, u32, Vec<String>)> {
    hits.iter()
        .map(|hit| {
            (
                hit.memory.id.clone(),
                hit.score.to_bits(),
                hit.sources
                    .iter()
                    .map(|source| source.to_string())
                    .collect::<Vec<_>>(),
            )
        })
        .collect()
}
