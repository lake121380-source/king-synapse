use synapse_core::{
    CognitiveBooster, CognitiveBoosterConfig, CognitiveBoosterInput, CognitiveTraceEvaluator,
    DeterministicCognitiveBoosterV0, MemoryKind, RecallEngine, RecallHit, RecallQuery, Scope,
    Source, Store, WriteInput, MAX_COGNITIVE_BOOSTER_BONUS,
};

fn recalled_hits() -> Vec<RecallHit> {
    let mut store = Store::open_in_memory().expect("in-memory store should open");
    for (content, kind, confidence) in [
        (
            "production rollback failure evidence requires resource validation",
            MemoryKind::Failure,
            0.98,
        ),
        (
            "production release playbook verifies rollback resources",
            MemoryKind::Playbook,
            0.86,
        ),
        (
            "user prefers reversible production rollout changes",
            MemoryKind::Preference,
            0.91,
        ),
        ("unrelated local prototype note", MemoryKind::Fact, 0.70),
    ] {
        store
            .write(WriteInput {
                content: content.to_string(),
                kind,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: Some(confidence),
                importance: Some(0.85),
            })
            .expect("fixture memory should write");
    }

    RecallEngine::new(&mut store)
        .with_access_recording(false)
        .recall(&RecallQuery {
            query: "production rollback resource validation".to_string(),
            k: Some(8),
            scope_filter: Some(Scope::User),
            kind_filter: None,
        })
        .expect("fixture recall should succeed")
}

fn signature(hits: &[RecallHit]) -> Vec<(String, u32, u32, u32)> {
    hits.iter()
        .map(|hit| {
            (
                hit.memory.id.clone(),
                hit.score.to_bits(),
                hit.rrf_score.to_bits(),
                hit.activation_bonus.to_bits(),
            )
        })
        .collect()
}

#[test]
fn deterministic_v0_returns_identical_shadow_proposals() {
    let hits = recalled_hits();
    let trace = CognitiveTraceEvaluator::evaluate("production rollback resource validation", &hits);
    let config = CognitiveBoosterConfig::shadow(MAX_COGNITIVE_BOOSTER_BONUS, hits.len())
        .expect("valid shadow config");
    let booster = DeterministicCognitiveBoosterV0;

    let first = booster.boost(CognitiveBoosterInput::new(&hits, &trace, &config));
    let second = booster.boost(CognitiveBoosterInput::new(&hits, &trace, &config));

    assert_eq!(booster.name(), "deterministic_cognitive_booster_v0");
    assert_eq!(first, second);
    assert!(!first.runtime_applied());
    assert!(!first.memory_mutated());
}

#[test]
fn deterministic_v0_bonus_is_absolutely_bounded() {
    let hits = recalled_hits();
    let trace = CognitiveTraceEvaluator::evaluate("production rollback resource validation", &hits);
    let config = CognitiveBoosterConfig::shadow(MAX_COGNITIVE_BOOSTER_BONUS, hits.len())
        .expect("valid shadow config");
    let output =
        DeterministicCognitiveBoosterV0.boost(CognitiveBoosterInput::new(&hits, &trace, &config));

    assert!(output.bounded());
    assert!(output.adjusted_scores().iter().all(|score| {
        score.bounded_bonus >= 0.0 && score.bounded_bonus <= MAX_COGNITIVE_BOOSTER_BONUS
    }));
}

#[test]
fn deterministic_v0_does_not_mutate_baseline_hits() {
    let hits = recalled_hits();
    let before = signature(&hits);
    let trace = CognitiveTraceEvaluator::evaluate("production rollback resource validation", &hits);
    let config = CognitiveBoosterConfig::shadow(0.08, hits.len()).expect("valid shadow config");

    let output =
        DeterministicCognitiveBoosterV0.boost(CognitiveBoosterInput::new(&hits, &trace, &config));

    assert_eq!(signature(&hits), before);
    assert!(!output.runtime_applied());
    assert!(!output.memory_mutated());
}

#[test]
fn deterministic_v0_ignores_candidates_outside_limit() {
    let hits = recalled_hits();
    assert!(
        hits.len() >= 3,
        "fixture should retrieve at least three hits"
    );
    let trace = CognitiveTraceEvaluator::evaluate("production rollback resource validation", &hits);
    let config = CognitiveBoosterConfig::shadow(0.10, 2).expect("valid shadow config");
    let output =
        DeterministicCognitiveBoosterV0.boost(CognitiveBoosterInput::new(&hits, &trace, &config));

    let eligible_ids = hits[..2]
        .iter()
        .map(|hit| hit.memory.id.as_str())
        .collect::<Vec<_>>();
    assert_eq!(output.eligible_candidate_count(), 2);
    assert_eq!(output.adjusted_scores().len(), 2);
    assert!(output
        .adjusted_scores()
        .iter()
        .all(|score| eligible_ids.contains(&score.candidate_id.as_str())));
}

#[test]
fn deterministic_v0_is_disabled_by_default() {
    let hits = recalled_hits();
    let trace = CognitiveTraceEvaluator::evaluate("production rollback resource validation", &hits);
    let config = CognitiveBoosterConfig::default();
    let output =
        DeterministicCognitiveBoosterV0.boost(CognitiveBoosterInput::new(&hits, &trace, &config));

    assert!(output.adjusted_scores().is_empty());
    assert_eq!(output.max_bonus(), 0.0);
    assert!(!output.runtime_applied());
}
