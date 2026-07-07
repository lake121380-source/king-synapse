pub(crate) const SCHEMA_SQL: &str = "
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS memories (
    id              TEXT PRIMARY KEY,
    kind            TEXT NOT NULL,
    scope           TEXT NOT NULL,
    content         TEXT NOT NULL,
    source          TEXT NOT NULL,
    confidence      REAL NOT NULL DEFAULT 1.0,
    importance      REAL NOT NULL DEFAULT 0.5,
    valid_from      INTEGER NOT NULL,
    valid_to        INTEGER,
    superseded_by   TEXT REFERENCES memories(id),
    access_count    INTEGER NOT NULL DEFAULT 0,
    last_accessed_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope);
CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);
CREATE INDEX IF NOT EXISTS idx_memories_valid_to ON memories(valid_to);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    content='memories',
    content_rowid='rowid',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.rowid, old.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.rowid, old.content);
    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
END;

CREATE TABLE IF NOT EXISTS events (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    memory_id    TEXT,
    payload      TEXT NOT NULL,
    actor        TEXT NOT NULL,
    device_id    TEXT,
    created_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_memory ON events(memory_id);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);

CREATE TABLE IF NOT EXISTS entities (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    name        TEXT NOT NULL,
    normalized  TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    UNIQUE(type, normalized)
);
CREATE INDEX IF NOT EXISTS idx_entities_norm ON entities(normalized);

CREATE TABLE IF NOT EXISTS memory_entities (
    memory_id  TEXT NOT NULL REFERENCES memories(id),
    entity_id  TEXT NOT NULL REFERENCES entities(id),
    edge       TEXT NOT NULL DEFAULT 'mentions',
    weight     REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (memory_id, entity_id, edge)
);
CREATE INDEX IF NOT EXISTS idx_me_entity ON memory_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_me_memory ON memory_entities(memory_id);

CREATE TABLE IF NOT EXISTS memory_edges (
    source     TEXT NOT NULL REFERENCES memories(id),
    target     TEXT NOT NULL REFERENCES memories(id),
    edge       TEXT NOT NULL DEFAULT 'associates',
    weight     REAL NOT NULL DEFAULT 0.0,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (source, target, edge)
);
CREATE INDEX IF NOT EXISTS idx_memory_edges_source ON memory_edges(source);
CREATE INDEX IF NOT EXISTS idx_memory_edges_target ON memory_edges(target);

CREATE TABLE IF NOT EXISTS edge_hypotheses (
    id                  TEXT PRIMARY KEY,
    source              TEXT NOT NULL REFERENCES memories(id),
    target              TEXT NOT NULL REFERENCES memories(id),
    relation            TEXT NOT NULL,
    confidence          REAL NOT NULL DEFAULT 0.0,
    observations        INTEGER NOT NULL DEFAULT 0,
    distinct_contexts   INTEGER NOT NULL DEFAULT 0,
    predictive_utility  REAL NOT NULL DEFAULT 0.0,
    first_seen          INTEGER NOT NULL,
    last_seen           INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'candidate',
    confirmed_at        INTEGER,
    disputed_at         INTEGER,
    decayed_turns       INTEGER NOT NULL DEFAULT 0,
    UNIQUE(source, target, relation)
);
CREATE INDEX IF NOT EXISTS idx_edge_hyp_source ON edge_hypotheses(source);
CREATE INDEX IF NOT EXISTS idx_edge_hyp_target ON edge_hypotheses(target);
CREATE INDEX IF NOT EXISTS idx_edge_hyp_status ON edge_hypotheses(status);

CREATE TABLE IF NOT EXISTS edge_evidence (
    id                      TEXT PRIMARY KEY,
    hypothesis_id           TEXT NOT NULL REFERENCES edge_hypotheses(id),
    query_context_hash      TEXT NOT NULL,
    query_context_tag       TEXT NOT NULL,
    supporting_memory_ids   TEXT NOT NULL,
    reason_summary          TEXT NOT NULL,
    utility_before_rank     INTEGER,
    utility_after_rank      INTEGER,
    observed_at             INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edge_ev_hyp ON edge_evidence(hypothesis_id);

CREATE TABLE IF NOT EXISTS embedding_state (
    memory_id   TEXT PRIMARY KEY REFERENCES memories(id),
    model       TEXT NOT NULL,
    dim         INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    updated_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_emb_status ON embedding_state(status);
";

pub(crate) const VEC_DIM: usize = 768;

pub(crate) fn vec_schema_sql() -> String {
    format!(
        "CREATE VIRTUAL TABLE IF NOT EXISTS memory_vecs USING vec0(
            memory_id TEXT PRIMARY KEY,
            embedding float[{VEC_DIM}]
        );"
    )
}
