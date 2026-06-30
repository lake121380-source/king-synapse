//! King Synapse core: storage, schema, recall, and entity primitives.
//!
//! Phase 2: SQLite + FTS5 + vec0 (sqlite-vec) storage with a separate
//! RecallEngine that fuses FTS, entity-graph, and vector hits via RRF.
//! Store is now query-agnostic; embedding lives behind a trait so it can
//! be swapped or mocked.

pub mod config;
pub mod embed;
pub mod entity;
pub mod error;
pub mod extract;
pub mod model;
pub mod recall;
pub mod rerank;
pub mod store;

pub use embed::Embedder;
pub use entity::{Entity, EntityRef, EntityType};
pub use error::{Error, Result};
pub use model::{Memory, MemoryKind, RecallQuery, Scope, Source, WriteInput};
pub use recall::{QueryEmbedder, RecallEngine, RecallHit, DEFAULT_RERANK_POOL};
pub use rerank::{FastEmbedReranker, Reranker};
pub use store::Store;
