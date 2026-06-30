use synapse_core::{MemoryKind, RecallEngine, RecallQuery, Scope, Source, Store, WriteInput};

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
    assert!(m2_hit.from_vector);
    assert!(!m2_hit.from_fts);
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
    assert!(!hits[0].from_vector);
    assert!(hits[0].from_fts || hits[0].from_entity);
}
