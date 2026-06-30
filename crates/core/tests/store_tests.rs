use std::sync::Arc;
use std::time::Duration;
use synapse_core::{
    MemoryKind, RecallEngine, RecallHit, RecallQuery, Scope, SessionId, Source, Store,
    WorkingMemoryActivationBooster, WorkingMemoryBuffer, WorkingMemoryItem, WriteInput,
};

fn add(store: &mut Store, content: &str, kind: MemoryKind) -> String {
    store
        .write(WriteInput {
            content: content.to_string(),
            kind,
            scope: Scope::Global,
            source: Source::ExplicitUser,
            confidence: Some(1.0),
            importance: Some(0.7),
        })
        .unwrap()
        .id
}

fn recall(store: &mut Store, q: &RecallQuery) -> Vec<synapse_core::RecallHit> {
    RecallEngine::new(store).recall(q).unwrap()
}

fn assert_same_hits(a: &[RecallHit], b: &[RecallHit]) {
    assert_eq!(a.len(), b.len(), "length must match");
    for (a, b) in a.iter().zip(b.iter()) {
        assert_eq!(a.memory.id, b.memory.id, "order must match");
        assert!(
            (a.score - b.score).abs() < 1e-6,
            "final score must match: {} vs {}",
            a.score,
            b.score
        );
        assert!(
            (a.rrf_score - b.rrf_score).abs() < 1e-6,
            "rrf score must match"
        );
        assert_eq!(a.activation_bonus, b.activation_bonus);
        assert_eq!(a.sources, b.sources);
        assert_eq!(a.fts_rank, b.fts_rank);
        assert_eq!(a.entity_rank, b.entity_rank);
        assert_eq!(a.vector_rank, b.vector_rank);
        assert_eq!(a.entity_hits, b.entity_hits);
        assert_eq!(a.rerank_score, b.rerank_score);
    }
}

#[test]
fn roundtrip_and_recall() {
    let mut s = Store::open_in_memory().unwrap();
    add(
        &mut s,
        "pnpm install hangs on Windows behind proxy",
        MemoryKind::Failure,
    );
    add(
        &mut s,
        "use corepack enable then pnpm",
        MemoryKind::Playbook,
    );
    add(
        &mut s,
        "user prefers TypeScript over JavaScript",
        MemoryKind::Preference,
    );

    let q = RecallQuery {
        query: "pnpm windows".to_string(),
        k: Some(5),
        scope_filter: None,
        kind_filter: None,
    };
    let hits = recall(&mut s, &q);
    assert!(!hits.is_empty());
    assert!(hits[0].memory.content.contains("pnpm"));
}

#[test]
fn invalidate_hides_from_recall() {
    let mut s = Store::open_in_memory().unwrap();
    add(&mut s, "use yarn for project foo", MemoryKind::Fact);
    let recent = s.list_recent(10).unwrap();
    let id = recent[0].id.clone();
    s.invalidate(&id, "test").unwrap();

    let q = RecallQuery {
        query: "yarn".to_string(),
        k: Some(5),
        scope_filter: None,
        kind_filter: None,
    };
    let hits = recall(&mut s, &q);
    assert!(hits.is_empty());
}

#[test]
fn entity_expansion_boosts_shared_entity_memories() {
    let mut s = Store::open_in_memory().unwrap();
    let _a = add(&mut s, "pnpm install fails on Windows", MemoryKind::Failure);
    let b = add(
        &mut s,
        "fix the pnpm windows problem with corepack enable",
        MemoryKind::Playbook,
    );

    let q = RecallQuery {
        query: "pnpm windows".to_string(),
        k: Some(5),
        scope_filter: None,
        kind_filter: None,
    };
    let hits = recall(&mut s, &q);
    assert!(hits.iter().any(|h| h.memory.id == b));
    assert!(hits.iter().any(|h| h.entity_hits > 0));
}

#[test]
fn neighbors_returns_shared_entity_memories() {
    let mut s = Store::open_in_memory().unwrap();
    let a = add(&mut s, "pnpm install fails on Windows", MemoryKind::Failure);
    let b = add(
        &mut s,
        "use corepack to fix pnpm on Windows",
        MemoryKind::Playbook,
    );
    let n = s.neighbors(&a, 5).unwrap();
    assert!(n.iter().any(|m| m.id == b));
}

/// Stub embedder for tests: returns a vector keyed to whatever the caller
/// stuffed into `query_to_vec`. Lets us drive the vector branch deterministically.
struct StubEmbedder {
    query_vec: Vec<f32>,
}

impl synapse_core::QueryEmbedder for StubEmbedder {
    fn embed_query(&mut self, _query: &str) -> synapse_core::Result<Vec<f32>> {
        Ok(self.query_vec.clone())
    }
}

fn make_dense(seed: f32) -> Vec<f32> {
    (0..768).map(|i| seed + (i as f32) * 0.0001).collect()
}

#[test]
fn rrf_pulls_in_vector_only_hit() {
    let mut s = Store::open_in_memory().unwrap();

    // m1: matches by FTS / entity ("rust axum").
    let m1 = add(&mut s, "rust axum middleware tip", MemoryKind::Fact);
    // m2: lexically unrelated, but its vector will be closest to the query.
    let m2 = add(
        &mut s,
        "completely unrelated content about gardening",
        MemoryKind::Fact,
    );

    // Park vectors: m2 sits exactly at the query, m1 far away.
    let v_query = make_dense(0.0);
    let v_far = make_dense(10.0);
    s.put_embedding(&m1, "stub", &v_far).unwrap();
    s.put_embedding(&m2, "stub", &v_query).unwrap();

    let mut emb = StubEmbedder {
        query_vec: v_query.clone(),
    };

    let q = RecallQuery {
        query: "rust axum".to_string(),
        k: Some(5),
        scope_filter: None,
        kind_filter: None,
    };
    let hits = RecallEngine::new(&mut s)
        .with_embedder(&mut emb)
        .recall(&q)
        .unwrap();

    // m1 must surface from FTS+entity; m2 must surface from vector only.
    let ids: Vec<&str> = hits.iter().map(|h| h.memory.id.as_str()).collect();
    assert!(ids.contains(&m1.as_str()), "m1 expected from FTS/entity");
    assert!(ids.contains(&m2.as_str()), "m2 expected from vector branch");

    let m2_hit = hits.iter().find(|h| h.memory.id == m2).unwrap();
    assert!(m2_hit.from_vector());
    assert!(!m2_hit.from_fts());
}

#[test]
fn rrf_without_embedder_falls_back_to_two_branches() {
    let mut s = Store::open_in_memory().unwrap();
    add(&mut s, "rust axum middleware tip", MemoryKind::Fact);

    let q = RecallQuery {
        query: "rust axum".to_string(),
        k: Some(5),
        scope_filter: None,
        kind_filter: None,
    };
    let hits = RecallEngine::new(&mut s).recall(&q).unwrap();
    assert_eq!(hits.len(), 1);
    assert!(!hits[0].from_vector());
    assert!(hits[0].from_fts() || hits[0].from_entity());
}

/// Deterministic reranker that scores hits inversely to their input order
/// (first hit gets the lowest logit), so the engine's final resort surfaces
/// the previously-last candidate first.
struct ReverseReranker;

impl synapse_core::Reranker for ReverseReranker {
    fn rerank(&mut self, _query: &str, docs: &[&str]) -> synapse_core::Result<Vec<f32>> {
        let n = docs.len() as f32;
        Ok((0..docs.len()).map(|i| i as f32 - n).collect())
    }
}

#[test]
fn reranker_reorders_hits_and_stamps_score() {
    let mut s = Store::open_in_memory().unwrap();
    let a = add(&mut s, "pnpm install fails on Windows", MemoryKind::Failure);
    let b = add(
        &mut s,
        "use corepack to fix pnpm on Windows",
        MemoryKind::Playbook,
    );
    let c = add(&mut s, "Windows path separators in pnpm", MemoryKind::Fact);

    let q = RecallQuery {
        query: "pnpm windows".to_string(),
        k: Some(5),
        scope_filter: None,
        kind_filter: None,
    };

    let baseline = RecallEngine::new(&mut s).recall(&q).unwrap();
    assert!(baseline.len() >= 2);
    let baseline_top = baseline[0].memory.id.clone();

    let mut rr = ReverseReranker;
    let reranked = RecallEngine::new(&mut s)
        .with_reranker(&mut rr, 50)
        .recall(&q)
        .unwrap();
    assert!(reranked.iter().all(|h| h.rerank_score.is_some()));
    // ReverseReranker should usually flip the top hit.
    assert_ne!(
        reranked[0].memory.id, baseline_top,
        "reranker should reorder"
    );
    let _ = (a, b, c);
}

/// Invariant 3 of the recall pipeline: `NoOpBooster` is inert. Attaching it
/// to a `RecallEngine` must not perturb hit order, score, or any of the
/// per-hit provenance fields. This is the contract every `RecallBooster`
/// implementer can copy as a baseline.
#[test]
fn noop_booster_preserves_pipeline_output() {
    let mut s = Store::open_in_memory().unwrap();
    add(&mut s, "axum middleware ordering tip", MemoryKind::Fact);
    add(
        &mut s,
        "use corepack for pnpm on Windows",
        MemoryKind::Playbook,
    );
    add(
        &mut s,
        "jwt refresh tokens should be rotated",
        MemoryKind::Playbook,
    );
    add(
        &mut s,
        "rust traits cannot have async fn (stable)",
        MemoryKind::Fact,
    );

    let q = RecallQuery {
        query: "pnpm windows".to_string(),
        k: Some(5),
        scope_filter: None,
        kind_filter: None,
    };

    let baseline = RecallEngine::new(&mut s).recall(&q).unwrap();
    let booster = synapse_core::NoOpBooster;
    let boosted = RecallEngine::new(&mut s)
        .with_booster(&booster)
        .recall(&q)
        .unwrap();

    assert_same_hits(&baseline, &boosted);
}

#[test]
fn empty_working_memory_booster_preserves_pipeline_output() {
    let mut s = Store::open_in_memory().unwrap();
    add(
        &mut s,
        "use corepack for pnpm on Windows",
        MemoryKind::Playbook,
    );
    add(&mut s, "axum middleware ordering tip", MemoryKind::Fact);

    let q = RecallQuery {
        query: "pnpm windows".to_string(),
        k: Some(5),
        scope_filter: None,
        kind_filter: None,
    };
    let baseline = RecallEngine::new(&mut s).recall(&q).unwrap();
    let session = SessionId::new();
    let booster = WorkingMemoryActivationBooster::new(Arc::new(WorkingMemoryBuffer::new()));
    let boosted = RecallEngine::new(&mut s)
        .with_session_id(session)
        .with_booster(&booster)
        .recall(&q)
        .unwrap();

    assert_same_hits(&baseline, &boosted);
}

#[test]
fn working_memory_booster_boosts_only_same_session_linked_hits() {
    let mut s = Store::open_in_memory().unwrap();
    let linked = add(
        &mut s,
        "use corepack for pnpm on Windows",
        MemoryKind::Playbook,
    );
    let other = add(&mut s, "axum middleware ordering tip", MemoryKind::Fact);
    let session = SessionId::new();
    let wrong_session = SessionId::new();
    let mut wm = WorkingMemoryBuffer::new();

    wm.add(
        session,
        WorkingMemoryItem::new(
            session,
            "current pnpm context",
            vec![linked.clone()],
            Duration::from_secs(60),
        ),
    );
    wm.add(
        wrong_session,
        WorkingMemoryItem::new(
            wrong_session,
            "unrelated axum context",
            vec![other.clone()],
            Duration::from_secs(60),
        ),
    );

    let q = RecallQuery {
        query: "pnpm windows axum".to_string(),
        k: Some(5),
        scope_filter: None,
        kind_filter: None,
    };
    let booster = WorkingMemoryActivationBooster::new(Arc::new(wm));
    let hits = RecallEngine::new(&mut s)
        .with_session_id(session)
        .with_booster(&booster)
        .recall(&q)
        .unwrap();

    let linked_hit = hits.iter().find(|h| h.memory.id == linked).unwrap();
    assert_eq!(linked_hit.activation_bonus, 0.05);
    let other_hit = hits.iter().find(|h| h.memory.id == other).unwrap();
    assert_eq!(other_hit.activation_bonus, 0.0);
}

#[test]
fn working_memory_booster_caps_activation_bonus() {
    let mut s = Store::open_in_memory().unwrap();
    let linked = add(
        &mut s,
        "use corepack for pnpm on Windows",
        MemoryKind::Playbook,
    );
    let session = SessionId::new();
    let mut wm = WorkingMemoryBuffer::new();

    for i in 0..3 {
        wm.add(
            session,
            WorkingMemoryItem::new(
                session,
                format!("context {i}"),
                vec![linked.clone()],
                Duration::from_secs(60),
            ),
        );
    }

    let q = RecallQuery {
        query: "pnpm windows".to_string(),
        k: Some(5),
        scope_filter: None,
        kind_filter: None,
    };
    let booster = WorkingMemoryActivationBooster::new(Arc::new(wm));
    let hits = RecallEngine::new(&mut s)
        .with_session_id(session)
        .with_booster(&booster)
        .recall(&q)
        .unwrap();

    let linked_hit = hits.iter().find(|h| h.memory.id == linked).unwrap();
    assert_eq!(linked_hit.activation_bonus, 0.1);
}
