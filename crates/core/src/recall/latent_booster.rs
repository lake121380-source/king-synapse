use crate::error::Result;
use crate::recall::{
    BoosterContext, LatentActivationContext, LatentActivationProbe, RecallBooster, RecallHit,
};
use std::collections::HashMap;

const DEFAULT_SCALE: f32 = 0.05;
const DEFAULT_CAP: f32 = 0.10;
const DEFAULT_DECAY: f32 = 0.5;
const DEFAULT_STEPS: usize = 2;
const DEFAULT_FANOUT: usize = 16;
const DEFAULT_SEED_LIMIT: usize = 3;

pub struct LatentActivationBooster {
    probe: LatentActivationProbe,
    context: LatentActivationContext,
    seed_limit: usize,
}

impl LatentActivationBooster {
    pub fn new(context: LatentActivationContext) -> Self {
        Self::with_config(
            DEFAULT_SCALE,
            DEFAULT_CAP,
            DEFAULT_STEPS,
            DEFAULT_DECAY,
            DEFAULT_FANOUT,
            DEFAULT_SEED_LIMIT,
            context,
        )
    }

    pub fn with_config(
        scale: f32,
        cap: f32,
        steps: usize,
        decay: f32,
        fanout: usize,
        seed_limit: usize,
        context: LatentActivationContext,
    ) -> Self {
        Self {
            probe: LatentActivationProbe::with_config(scale, cap, steps, decay, fanout),
            context,
            seed_limit: seed_limit.max(1),
        }
    }

    pub fn context(&self) -> &LatentActivationContext {
        &self.context
    }

    pub fn seed_limit(&self) -> usize {
        self.seed_limit
    }
}

impl RecallBooster for LatentActivationBooster {
    fn name(&self) -> &'static str {
        "latent_activation"
    }

    fn apply(&self, ctx: &BoosterContext<'_>, hits: &mut [RecallHit]) -> Result<()> {
        if hits.len() < 2 {
            return Ok(());
        }

        let seed_ids = hits
            .iter()
            .take(self.seed_limit)
            .map(|hit| hit.memory.id.as_str())
            .collect::<Vec<_>>();
        let activations =
            self.probe
                .activate_with_context(ctx.store, &seed_ids, hits.len(), &self.context)?;
        if activations.is_empty() {
            return Ok(());
        }

        let bonuses = activations
            .into_iter()
            .map(|hit| (hit.memory.id, hit.activation))
            .collect::<HashMap<_, _>>();
        for hit in hits {
            if let Some(bonus) = bonuses.get(&hit.memory.id) {
                hit.activation_bonus += *bonus;
            }
        }
        Ok(())
    }
}
