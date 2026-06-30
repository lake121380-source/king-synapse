use crate::error::Result;
use crate::recall::{BoosterContext, RecallBooster, RecallHit};
use crate::working_memory::{MemoryId, WorkingMemoryBuffer};
use std::collections::HashMap;
use std::sync::Arc;

const DEFAULT_BONUS_WEIGHT: f32 = 1.0;
const BONUS_UNIT: f32 = 0.05;
const BONUS_CAP: f32 = 0.1;

pub struct WorkingMemoryActivationBooster {
    wm: Arc<WorkingMemoryBuffer>,
}

impl WorkingMemoryActivationBooster {
    pub fn new(wm: Arc<WorkingMemoryBuffer>) -> Self {
        Self { wm }
    }

    fn compute_bonus(weight: f32) -> f32 {
        (BONUS_UNIT * weight).min(BONUS_CAP)
    }
}

impl RecallBooster for WorkingMemoryActivationBooster {
    fn name(&self) -> &'static str {
        "working_memory_activation"
    }

    fn apply(&self, ctx: &BoosterContext<'_>, hits: &mut [RecallHit]) -> Result<()> {
        let Some(session_id) = ctx.session_id else {
            return Ok(());
        };

        let weights = linked_memory_weights(self.wm.as_ref(), session_id);
        if weights.is_empty() {
            return Ok(());
        }

        for hit in hits {
            if let Some(weight) = weights.get(&hit.memory.id) {
                hit.activation_bonus =
                    (hit.activation_bonus + Self::compute_bonus(*weight)).min(BONUS_CAP);
            }
        }
        Ok(())
    }
}

pub struct NoOpActivationBooster;

impl RecallBooster for NoOpActivationBooster {
    fn name(&self) -> &'static str {
        "noop_activation"
    }

    fn apply(&self, _ctx: &BoosterContext<'_>, _hits: &mut [RecallHit]) -> Result<()> {
        Ok(())
    }
}

fn linked_memory_weights(
    wm: &WorkingMemoryBuffer,
    session_id: crate::working_memory::SessionId,
) -> HashMap<MemoryId, f32> {
    let mut weights = HashMap::new();
    for item in wm.get_session(session_id) {
        for id in &item.linked_memory_ids {
            *weights.entry(id.clone()).or_insert(0.0) += DEFAULT_BONUS_WEIGHT;
        }
    }
    weights
}
