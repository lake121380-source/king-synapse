use synapse_core::{MemoryKind, RecallQuery, Scope, Source, Store, WriteInput};

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
    let hits = s.recall(&q).unwrap();
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
    let hits = s.recall(&q).unwrap();
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
    let hits = s.recall(&q).unwrap();
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
