use crate::error::Result;
use crate::model::RecallQuery;
use crate::recall::{LatentActivationContext, LatentActivationHit, LatentActivationProbe};
use crate::{RecallEngine, RecallHit, Store};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryLatentActivationReport {
    pub seeds: Vec<RecallHit>,
    pub activations: Vec<LatentActivationHit>,
}

pub struct QueryLatentActivationProbe {
    latent_probe: LatentActivationProbe,
    seed_limit: usize,
}

impl QueryLatentActivationProbe {
    pub fn new(latent_probe: LatentActivationProbe, seed_limit: usize) -> Self {
        Self {
            latent_probe,
            seed_limit: seed_limit.max(1),
        }
    }

    pub fn seed_limit(&self) -> usize {
        self.seed_limit
    }

    pub fn latent_probe(&self) -> &LatentActivationProbe {
        &self.latent_probe
    }

    pub fn probe(
        &self,
        store: &mut Store,
        query: &RecallQuery,
        activation_limit: usize,
        context: &LatentActivationContext,
    ) -> Result<QueryLatentActivationReport> {
        if activation_limit == 0 {
            return Ok(QueryLatentActivationReport {
                seeds: Vec::new(),
                activations: Vec::new(),
            });
        }

        let seed_query = RecallQuery {
            query: query.query.clone(),
            k: Some(self.seed_limit),
            scope_filter: query.scope_filter.clone(),
            kind_filter: query.kind_filter,
        };
        let seeds = RecallEngine::new(store).recall(&seed_query)?;
        let seed_ids = seeds
            .iter()
            .map(|hit| hit.memory.id.as_str())
            .collect::<Vec<_>>();
        let activations =
            self.latent_probe
                .activate_with_context(store, &seed_ids, activation_limit, context)?;

        Ok(QueryLatentActivationReport { seeds, activations })
    }
}

impl Default for QueryLatentActivationProbe {
    fn default() -> Self {
        Self::new(LatentActivationProbe::default(), 3)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{MemoryKind, Scope, Source, WriteInput};

    fn add(store: &mut Store, content: &str) -> String {
        store
            .write(WriteInput {
                content: content.to_string(),
                kind: MemoryKind::Fact,
                scope: Scope::User,
                source: Source::ExplicitUser,
                confidence: Some(1.0),
                importance: Some(0.7),
            })
            .unwrap()
            .id
    }

    #[test]
    fn query_latent_probe_uses_recall_hits_as_seed_memories() {
        let mut store = Store::open_in_memory().unwrap();
        let seed = add(&mut store, "forgot morning water before work");
        let latent = add(&mut store, "bad mood affects commute attention");
        store.update_edge(&seed, &latent, 2.0).unwrap();

        let query = RecallQuery {
            query: "morning water".to_string(),
            k: None,
            scope_filter: None,
            kind_filter: None,
        };
        let context =
            LatentActivationContext::new(vec!["mood".to_string()], vec!["commute".to_string()]);
        let probe = QueryLatentActivationProbe::new(
            LatentActivationProbe::with_config(0.05, 0.25, 2, 0.5, 10),
            2,
        );
        let report = probe.probe(&mut store, &query, 10, &context).unwrap();

        assert_eq!(report.seeds.len(), 1);
        assert_eq!(report.seeds[0].memory.id, seed);
        assert_eq!(report.activations.len(), 1);
        assert_eq!(report.activations[0].memory.id, latent);
        assert_eq!(
            report.activations[0].matched_terms,
            vec!["goal:commute".to_string(), "state:mood".to_string()]
        );
    }

    #[test]
    fn query_latent_probe_returns_empty_report_for_zero_activation_limit() {
        let mut store = Store::open_in_memory().unwrap();
        add(&mut store, "forgot morning water before work");
        let query = RecallQuery {
            query: "morning water".to_string(),
            k: None,
            scope_filter: None,
            kind_filter: None,
        };
        let report = QueryLatentActivationProbe::default()
            .probe(&mut store, &query, 0, &LatentActivationContext::default())
            .unwrap();

        assert!(report.seeds.is_empty());
        assert!(report.activations.is_empty());
    }
}
