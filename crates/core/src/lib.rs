//! King Synapse core: storage, schema, and recall primitives.
//!
//! Phase 0 scope: SQLite + FTS5 keyword recall, append-only event log,
//! memory types tagged but not yet specialized. Spreading activation,
//! vector index, graph layer all arrive in later phases.

pub mod config;
pub mod error;
pub mod model;
pub mod store;

pub use error::{Error, Result};
pub use model::{Memory, MemoryKind, RecallQuery, Scope, Source, WriteInput};
pub use store::{RecallHit, Store};
