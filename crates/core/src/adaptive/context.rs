//! Algorithm execution context (RFC-011 Part C).
//!
//! `AlgorithmContext` represents the **execution environment** for every
//! Phase 5 adaptive-memory algorithm. It intentionally does NOT carry the
//! evaluation target — the target (a memory, edge, event, or group) is
//! always passed as an explicit method parameter, e.g.
//! `importance.estimate(memory, ctx)`.
//!
//! v0.5.1 scope: `now` and optional `session_id` only. Trait-object fields
//! (`importance`, `events`) are added additively in v0.5.2. Per RFC-011
//! Part C rule 3, after v0.5.2 the trait-object surface of this struct is
//! closed and no further service dependencies may be added.

use crate::working_memory::SessionId;
use chrono::{DateTime, Utc};

/// Execution environment shared by all Phase 5 adaptive-memory algorithms.
///
/// This struct is `#[non_exhaustive]`. Consumers MUST construct it via
/// [`AlgorithmContext::new`] (or a future builder) and MUST NOT rely on the
/// exact field list.
#[derive(Debug, Clone, Copy)]
#[non_exhaustive]
pub struct AlgorithmContext {
    /// Logical current time, provided by the caller. Algorithms MUST NOT
    /// read the system clock directly.
    pub now: DateTime<Utc>,
    /// Optional session scope. `None` denotes a global (non-session)
    /// invocation.
    pub session_id: Option<SessionId>,
}

impl AlgorithmContext {
    /// Construct a context with an explicit clock reading and optional
    /// session scope.
    pub fn new(now: DateTime<Utc>, session_id: Option<SessionId>) -> Self {
        Self { now, session_id }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::working_memory::SessionId;
    use uuid::Uuid;

    #[test]
    fn constructs_without_session() {
        let now = Utc::now();
        let ctx = AlgorithmContext::new(now, None);
        assert_eq!(ctx.now, now);
        assert!(ctx.session_id.is_none());
    }

    #[test]
    fn constructs_with_session() {
        let now = Utc::now();
        let sid = SessionId(Uuid::nil());
        let ctx = AlgorithmContext::new(now, Some(sid));
        assert_eq!(ctx.session_id, Some(sid));
    }

    #[test]
    fn context_is_copy() {
        fn assert_copy<T: Copy>() {}
        assert_copy::<AlgorithmContext>();
    }
}
