use synapse_core::{
    CognitiveAdjustedScore, CognitiveBooster, CognitiveBoosterConfig, CognitiveBoosterConfigError,
    CognitiveBoosterInput, CognitiveBoosterMode, CognitiveBoosterOutput, CognitiveTraceEvaluator,
    MemoryKind, NoOpCognitiveBooster, RecallEngine, RecallHit, RecallQuery, Scope, Source, Store,
    WriteInput, MAX_COGNITIVE_BOOSTER_BONUS,
};

fn assert_f64_eq(actual: f64, expected: f64) {
    assert!(
        (actual - expected).abs() < 1e-12,
        "expected {expected}, got {actual}"
    );
}

fn recalled_hits() -> Vec<RecallHit> {
    let mut store = Store::open_in_memory().expect("in-memory store should open");
    for content in [
        "production rollback failure requires validation",
        "production rollback playbook verifies resources",
        "production release preference favors reversible changes",
    ] {
        store
            .write(WriteInput {
                content: content.to_string(),
                kind: if content.contains("failure") {
                    MemoryKind::Failure
                } else if content.contains("preference") {
                    MemoryKind::Preference
                } else {
                    MemoryKind::Playbook
                },
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: Some(0.9),
                importance: Some(0.85),
            })
            .expect("fixture memory should write");
    }
    let query = RecallQuery {
        query: "production rollback validation".to_string(),
        k: Some(8),
        scope_filter: Some(Scope::User),
        kind_filter: None,
    };
    RecallEngine::new(&mut store)
        .with_access_recording(false)
        .recall(&query)
        .expect("fixture recall should succeed")
}

fn signature(hits: &[RecallHit]) -> Vec<(String, u32, u32)> {
    hits.iter()
        .map(|hit| {
            (
                hit.memory.id.clone(),
                hit.score.to_bits(),
                hit.activation_bonus.to_bits(),
            )
        })
        .collect()
}

#[test]
fn default_configuration_is_strictly_disabled() {
    let config = CognitiveBoosterConfig::default();

    assert!(!config.enabled());
    assert_eq!(config.max_bonus(), 0.0);
    assert_eq!(config.candidate_limit(), 0);

    let serialized = serde_json::to_string(&config).expect("disabled config should serialize");
    let round_trip: CognitiveBoosterConfig =
        serde_json::from_str(&serialized).expect("disabled config should round trip");
    assert_eq!(round_trip, config);
}

#[test]
fn shadow_configuration_requires_explicit_bounded_limits() {
    assert_eq!(
        CognitiveBoosterConfig::shadow(0.0, 3),
        Err(CognitiveBoosterConfigError::InvalidMaxBonus)
    );
    assert_eq!(
        CognitiveBoosterConfig::shadow(f64::NAN, 3),
        Err(CognitiveBoosterConfigError::InvalidMaxBonus)
    );
    assert!(matches!(
        CognitiveBoosterConfig::shadow(MAX_COGNITIVE_BOOSTER_BONUS + 0.01, 3),
        Err(CognitiveBoosterConfigError::MaxBonusExceeded { .. })
    ));
    assert_eq!(
        CognitiveBoosterConfig::shadow(0.05, 0),
        Err(CognitiveBoosterConfigError::EmptyCandidateLimit)
    );

    let config = CognitiveBoosterConfig::shadow(0.05, 2)
        .expect("explicit bounded shadow configuration should be valid");
    assert!(config.enabled());
    assert_eq!(config.max_bonus(), 0.05);
    assert_eq!(config.candidate_limit(), 2);

    let serialized = serde_json::to_string(&config).expect("shadow config should serialize");
    let round_trip: CognitiveBoosterConfig =
        serde_json::from_str(&serialized).expect("validated shadow config should round trip");
    assert_eq!(round_trip, config);

    for invalid in [
        r#"{"enabled":true,"max_bonus":0.5,"candidate_limit":2}"#,
        r#"{"enabled":true,"max_bonus":0.05,"candidate_limit":0}"#,
        r#"{"enabled":false,"max_bonus":0.05,"candidate_limit":2}"#,
    ] {
        assert!(
            serde_json::from_str::<CognitiveBoosterConfig>(invalid).is_err(),
            "deserialization must not bypass config invariants: {invalid}"
        );
    }
}

#[test]
fn input_exposes_only_the_configured_candidate_prefix() {
    let hits = recalled_hits();
    let trace = CognitiveTraceEvaluator::evaluate("production rollback validation", &hits);
    let disabled = CognitiveBoosterConfig::default();
    let disabled_input = CognitiveBoosterInput::new(&hits, &trace, &disabled);
    assert_eq!(disabled_input.candidate_count(), hits.len());
    assert!(disabled_input.eligible_candidates().is_empty());

    let shadow = CognitiveBoosterConfig::shadow(0.05, 2).expect("valid shadow config");
    let shadow_input = CognitiveBoosterInput::new(&hits, &trace, &shadow);
    assert_eq!(shadow_input.candidates().len(), hits.len());
    assert_eq!(shadow_input.eligible_candidates().len(), 2.min(hits.len()));
    assert_eq!(shadow_input.trace(), &trace);
    assert_eq!(shadow_input.config(), &shadow);
}

#[test]
fn noop_booster_never_changes_candidates_or_emits_adjustments() {
    let hits = recalled_hits();
    let before = signature(&hits);
    let trace = CognitiveTraceEvaluator::evaluate("production rollback validation", &hits);
    let config = CognitiveBoosterConfig::shadow(0.05, 2).expect("valid shadow config");
    let booster = NoOpCognitiveBooster;

    let output = booster.boost(CognitiveBoosterInput::new(&hits, &trace, &config));

    assert_eq!(signature(&hits), before);
    assert_eq!(output.mode(), CognitiveBoosterMode::Disabled);
    assert_eq!(output.candidate_count(), hits.len());
    assert_eq!(output.eligible_candidate_count(), 0);
    assert!(output.adjusted_scores().is_empty());
    assert!(output.changed_candidates().is_empty());
    assert!(output.bounded());
    assert!(!output.runtime_applied());
    assert!(!output.memory_mutated());
}

#[test]
fn adjusted_scores_are_capped_and_remain_shadow_only() {
    let score = CognitiveAdjustedScore::bounded("memory-1", 1, 0.8, 0.50, 0.05);

    assert_eq!(score.candidate_id, "memory-1");
    assert_eq!(score.baseline_rank, 1);
    assert_eq!(score.baseline_score, 0.8);
    assert_eq!(score.requested_bonus, 0.50);
    assert_eq!(score.bounded_bonus, 0.05);
    assert_f64_eq(score.adjusted_score, 0.85);
    assert!(score.was_clamped);
    assert!(score.changed());

    let invalid = CognitiveAdjustedScore::bounded("memory-2", 2, 0.7, f64::NAN, 0.05);
    assert_eq!(invalid.bounded_bonus, 0.0);
    assert_eq!(invalid.adjusted_score, 0.7);
    assert!(invalid.was_clamped);
    assert!(!invalid.changed());
}

#[test]
fn shadow_output_rebounds_and_filters_untrusted_proposals() {
    let hits = recalled_hits();
    assert!(hits.len() >= 2, "fixture should return at least two hits");
    let trace = CognitiveTraceEvaluator::evaluate("production rollback validation", &hits);
    let config = CognitiveBoosterConfig::shadow(0.05, 1).expect("valid shadow config");
    let input = CognitiveBoosterInput::new(&hits, &trace, &config);
    let eligible_id = hits[0].memory.id.clone();
    let ineligible_id = hits[1].memory.id.clone();
    let proposals = vec![
        CognitiveAdjustedScore {
            candidate_id: eligible_id.clone(),
            baseline_rank: 99,
            baseline_score: 99.0,
            requested_bonus: 0.50,
            bounded_bonus: 0.50,
            adjusted_score: 99.50,
            was_clamped: false,
        },
        CognitiveAdjustedScore::bounded(ineligible_id, 2, 0.0, 0.05, 0.05),
        CognitiveAdjustedScore::bounded("unknown-memory", 3, 0.0, 0.05, 0.05),
    ];

    let output = CognitiveBoosterOutput::shadow(&input, proposals, 1.4);

    assert_eq!(output.mode(), CognitiveBoosterMode::Shadow);
    assert_eq!(output.candidate_count(), hits.len());
    assert_eq!(output.eligible_candidate_count(), 1);
    assert_eq!(output.max_bonus(), 0.05);
    assert_eq!(output.confidence(), 1.0);
    assert_eq!(output.adjusted_scores().len(), 1);
    let score = &output.adjusted_scores()[0];
    assert_eq!(score.candidate_id, eligible_id);
    assert_eq!(score.baseline_rank, 1);
    assert_f64_eq(score.baseline_score, f64::from(hits[0].score));
    assert_eq!(score.bounded_bonus, 0.05);
    assert_f64_eq(score.adjusted_score, f64::from(hits[0].score) + 0.05);
    assert_eq!(output.changed_candidates(), &[eligible_id]);
    assert!(output.bounded());
    assert!(!output.runtime_applied());
    assert!(!output.memory_mutated());
}

#[test]
fn disabled_input_cannot_emit_a_shadow_output() {
    let hits = recalled_hits();
    let trace = CognitiveTraceEvaluator::evaluate("production rollback validation", &hits);
    let config = CognitiveBoosterConfig::default();
    let input = CognitiveBoosterInput::new(&hits, &trace, &config);
    let proposal = CognitiveAdjustedScore::bounded(
        hits[0].memory.id.clone(),
        1,
        f64::from(hits[0].score),
        0.05,
        0.05,
    );

    let output = CognitiveBoosterOutput::shadow(&input, vec![proposal], 1.0);

    assert_eq!(output.mode(), CognitiveBoosterMode::Disabled);
    assert!(output.adjusted_scores().is_empty());
    assert_eq!(output.max_bonus(), 0.0);
    assert!(!output.runtime_applied());
    assert!(!output.memory_mutated());
}

#[test]
fn noop_contract_is_deterministic_and_object_safe() {
    let hits = recalled_hits();
    let trace = CognitiveTraceEvaluator::evaluate("production rollback validation", &hits);
    let config = CognitiveBoosterConfig::default();
    let booster: &dyn CognitiveBooster = &NoOpCognitiveBooster;

    let first = booster.boost(CognitiveBoosterInput::new(&hits, &trace, &config));
    let second = booster.boost(CognitiveBoosterInput::new(&hits, &trace, &config));

    assert_eq!(booster.name(), "cognitive_booster_noop");
    assert_eq!(first, second);
}

#[test]
fn output_contract_has_a_stable_serializable_shape() {
    let output = CognitiveBoosterOutput::disabled(4);
    let value = serde_json::to_value(output).expect("output should serialize");

    for field in [
        "mode",
        "candidate_count",
        "eligible_candidate_count",
        "adjusted_scores",
        "confidence",
        "changed_candidates",
        "max_bonus",
        "bounded",
        "runtime_applied",
        "memory_mutated",
    ] {
        assert!(value.get(field).is_some(), "missing output field {field}");
    }
    assert_eq!(value["mode"], "disabled");
    assert_eq!(value["runtime_applied"], false);
    assert_eq!(value["memory_mutated"], false);
}
