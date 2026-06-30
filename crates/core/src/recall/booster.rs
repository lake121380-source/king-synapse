//! `RecallBooster`: additive, retrieval-free post-processors.
//!
//! Contract (Invariant 3 in `docs/RECALL_PIPELINE.md`): a booster may only
//! **add** to `RecallHit::activation_bonus`. It cannot:
//!   - introduce new candidates not already in the hits slice;
//!   - reorder the hits;
//!   - touch any other field on `RecallHit`.
//!
//! The engine handles the resort after every booster has run, so the
//! booster only needs to compute its additive contribution.
//!
//! `BoosterContext` is the only thing a booster reads from. New fields
//! (session, user profile, working-memory buffer) land here as optional
//! references; the trait signature itself does not change.

use crate::error::Result;
use crate::model::RecallQuery;
use crate::recall::hit::RecallHit;
use crate::store::Store;
use crate::working_memory::SessionId;

/// Read-only context handed to every `RecallBooster::apply` invocation.
///
/// Extending this struct (e.g. adding `session: Option<&Session>`) is a
/// minor change; renaming or removing a field is a breaking one and
/// requires an ADR.
#[non_exhaustive]
pub struct BoosterContext<'a> {
    pub query: &'a RecallQuery,
    /// Read-only handle to the store so graph-walking boosters can call
    /// `Store::neighbors` etc. without each booster crate having to
    /// open its own connection.
    pub store: &'a Store,
    pub session_id: Option<SessionId>,
}

impl<'a> BoosterContext<'a> {
    pub fn new(query: &'a RecallQuery, store: &'a Store) -> Self {
        Self {
            query,
            store,
            session_id: None,
        }
    }

    pub fn with_session_id(mut self, session_id: SessionId) -> Self {
        self.session_id = Some(session_id);
        self
    }
}

/// A pure post-processing layer over the recall pipeline.
///
/// Implementations must respect Invariant 3: only `activation_bonus` may
/// change. The engine will resort by final score after every booster runs.
pub trait RecallBooster {
    /// Human-readable name; used by `kr recall --explain`.
    fn name(&self) -> &'static str;

    /// Inspect `hits` and add to each hit's `activation_bonus`. The slice
    /// length and order may be relied on; the booster must not push or
    /// pop entries.
    ///
    /// Return `Ok(())` even when the booster contributed nothing.
    fn apply(&self, ctx: &BoosterContext<'_>, hits: &mut [RecallHit]) -> Result<()>;
}

/// Inert booster, useful for tests and for the default `Vec<&dyn RecallBooster>`.
/// Adding it to a `RecallEngine` must not change the result of `recall()`.
pub struct NoOpBooster;

impl RecallBooster for NoOpBooster {
    fn name(&self) -> &'static str {
        "noop"
    }

    fn apply(&self, _ctx: &BoosterContext<'_>, _hits: &mut [RecallHit]) -> Result<()> {
        Ok(())
    }
}
