//! King Synapse core: storage, schema, recall, and entity primitives.
//!
//! Phase 1: SQLite + FTS5 keyword recall fused with 1-hop entity expansion.
//! Append-only event log; entities and `MENTIONS` edges populated at write.
//! Spreading activation, vector index, embedder arrive in Phase 2.

pub mod config;
pub mod embed;
pub mod entity;
pub mod error;
pub mod extract;
pub mod model;
pub mod store;

pub use embed::Embedder;
pub use entity::{Entity, EntityRef, EntityType};
pub use error::{Error, Result};
pub use model::{Memory, MemoryKind, RecallQuery, Scope, Source, WriteInput};
pub use store::{RecallHit, Store};
