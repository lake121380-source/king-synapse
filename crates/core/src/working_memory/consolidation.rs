use crate::model::Memory;
use crate::working_memory::{SessionId, WorkingMemoryBuffer, WorkingMemoryItem};

pub trait ConsolidationPolicy {
    fn should_consolidate(item: &WorkingMemoryItem) -> bool;

    fn consolidate(session: SessionId, buffer: &WorkingMemoryBuffer) -> Vec<Memory>;
}

pub struct NoOpConsolidation;

impl ConsolidationPolicy for NoOpConsolidation {
    fn should_consolidate(_item: &WorkingMemoryItem) -> bool {
        false
    }

    fn consolidate(_session: SessionId, _buffer: &WorkingMemoryBuffer) -> Vec<Memory> {
        Vec::new()
    }
}
