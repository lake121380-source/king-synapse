//! Algorithm execution context (RFC-011 Part C).
//!
//! `AlgorithmContext` represents the **execution environment** for every
//! Phase 5 adaptive-memory algorithm. It intentionally does NOT carry the
//! evaluation target — the target (a memory, edge, event, or group) is
//! always passed as an explicit method parameter, e.g.
//! `importance.estimate(memory, ctx)`.
//!
//! v0.5.2 closes the trait-object surface: the only trait-object fields
//! this struct will ever carry are `importance: &'a dyn ImportanceEstimator`
//! and `events: &'a dyn MemoryEventStream`. Per RFC-011 Part C rule 3, no
//! further service dependencies may be added (no `&dyn Store`, no
//! `&dyn RecallEngine`, no `&dyn PolicyEngine`, no `&dyn Graph`, no
//! `&dyn LlmClient`, no others).
//!
//! `#[non_exhaustive]` remains on the struct so future minor versions may
//! still add plain-data fields (`Option<...>`, `Default`-able) additively
//! under RFC-011 Part C rule 4.

use crate::adaptive::event_stream::MemoryEventStream;
use crate::adaptive::importance::ImportanceEstimator;
use crate::working_memory::SessionId;
use chrono::{DateTime, Utc};

/// Execution environment shared by all Phase 5 adaptive-memory algorithms.
///
/// Constructed via [`AlgorithmContext::new`]. Consumers MUST NOT rely on
/// the exact field list — the struct is `#[non_exhaustive]`.
#[derive(Clone, Copy)]
#[non_exhaustive]
pub struct AlgorithmContext<'a> {
    /// Logical current time, provided by the caller. Algorithms MUST NOT
    /// read the system clock directly.
    pub now: DateTime<Utc>,
    /// Optional session scope. `None` denotes a global (non-session)
    /// invocation.
    pub session_id: Option<SessionId>,
    /// Shared importance estimator. Frozen at v0.5.2 as the sole allowed
    /// trait-object field for "how important is a memory".
    pub importance: &'a dyn ImportanceEstimator,
    /// Shared append-only event log. Frozen at v0.5.2 as the sole allowed
    /// trait-object field for "what recently happened".
    pub events: &'a dyn MemoryEventStream,
}

impl<'a> AlgorithmContext<'a> {
    /// Construct a context. This is the only supported constructor.
    ///
    /// No builder variant is provided — every Phase 5 algorithm invocation
    /// carries the same four inputs.
    pub fn new(
        now: DateTime<Utc>,
        session_id: Option<SessionId>,
        importance: &'a dyn ImportanceEstimator,
        events: &'a dyn MemoryEventStream,
    ) -> Self {
        Self {
            now,
            session_id,
            importance,
            events,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adaptive::event_stream::NoOpMemoryEventStream;
    use crate::adaptive::importance::{NoOpImportanceEstimator, UniformImportanceEstimator};
    use crate::working_memory::SessionId;
    use uuid::Uuid;

    #[test]
    fn constructs_without_session() {
        let now = Utc::now();
        let est = NoOpImportanceEstimator;
        let evs = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(now, None, &est, &evs);
        assert_eq!(ctx.now, now);
        assert!(ctx.session_id.is_none());
    }

    #[test]
    fn constructs_with_session() {
        let now = Utc::now();
        let sid = SessionId(Uuid::nil());
        let est = UniformImportanceEstimator;
        let evs = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(now, Some(sid), &est, &evs);
        assert_eq!(ctx.session_id, Some(sid));
    }

    #[test]
    fn context_is_copy() {
        fn assert_copy<T: Copy>() {}
        assert_copy::<AlgorithmContext<'_>>();
    }

    #[test]
    fn context_holds_trait_object_borrows() {
        // Compile-time proof that the fields are &dyn references, not
        // owned; the estimator and stream live in stack locals and the
        // context can be freely copied inside the same scope.
        let est = NoOpImportanceEstimator;
        let evs = NoOpMemoryEventStream;
        let ctx = AlgorithmContext::new(Utc::now(), None, &est, &evs);
        let copy = ctx;
        assert_eq!(ctx.now, copy.now);
    }
}
