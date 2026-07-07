//! Integration tests for edge hypothesis lifecycle.
//!
//! Validates: candidate -> observed -> confirmed -> graduation to memory_edges.

#[cfg(test)]
mod tests {
    use crate::recall::hypothesis::generator::{EdgeHypothesisGenerator, RuleBasedEdgeGenerator};
    use crate::recall::hypothesis::model::{
        EdgeHypothesisStatus, RetrievalContext,
    };
    use crate::recall::hypothesis::store_ext::HypothesisStore;
    use crate::store::Store;
    use crate::WriteInput;

    fn make_store_with_memories() -> (Store, Vec<String>) {
        let mut store = Store::open_in_memory().unwrap();
        let mut ids = Vec::new();
        for i in 0..5 {
            let input = WriteInput {
                content: format!("memory content {}", i),
                kind: crate::MemoryKind::Fact,
                scope: crate::Scope::Global,
                source: crate::Source::ExplicitUser,
                confidence: None,
                importance: None,
            };
            let id = store.write(input).unwrap();
            ids.push(id.id);
        }
        (store, ids)
    }

    fn run_with_context(
        store: &mut Store,
        gen: &RuleBasedEdgeGenerator,
        query: &str,
        hash: &str,
        tag: &str,
        hit_ids: &[String],
        ts: i64,
    ) {
        let scores: Vec<f32> = hit_ids.iter().map(|_| 0.9).collect();
        let ctx = RetrievalContext {
            query,
            query_context_hash: hash,
            query_context_tag: tag,
            hit_memory_ids: hit_ids,
            hit_scores: &scores,
            timestamp: ts,
        };
        let hyps = gen.generate(&ctx);
        for hyp in &hyps {
            store
                .upsert_hypothesis(hyp, hash, tag, hit_ids, "co-retrieval")
                .unwrap();
        }
    }

    #[test]
    fn hypothesis_lifecycle_candidate_to_confirmed() {
        let (mut store, ids) = make_store_with_memories();
        let gen = RuleBasedEdgeGenerator::new();
        let hit_ids = &ids[0..3];

        // Turn 1: context A
        run_with_context(&mut store, &gen, "query about rust", "ctx_a", "programming", hit_ids, 1000);

        // Verify candidate status after first observation
        let candidates = store
            .get_hypotheses_by_status(EdgeHypothesisStatus::Candidate)
            .unwrap();
        assert!(!candidates.is_empty());

        // Turn 2: different context B
        run_with_context(&mut store, &gen, "query about databases", "ctx_b", "database", hit_ids, 2000);

        // Turn 3: different context C — should graduate to confirmed
        run_with_context(&mut store, &gen, "query about career", "ctx_c", "career", hit_ids, 3000);

        let confirmed = store
            .get_hypotheses_by_status(EdgeHypothesisStatus::Confirmed)
            .unwrap();
        assert!(
            !confirmed.is_empty(),
            "hypotheses should be confirmed after 3 diverse observations"
        );
        assert!(confirmed[0].confidence >= 0.70);

        // Graduate confirmed hypotheses to memory_edges
        let edge_count = store.graduate_confirmed().unwrap();
        assert!(edge_count > 0, "confirmed edges should be written");

        // Verify edges exist with cognitive relation type
        let edge_types = store.count_edges_by_type().unwrap();
        let has_co_activates = edge_types
            .iter()
            .any(|(t, c)| t == "co_activates" && *c > 0);
        assert!(has_co_activates, "co_activates edges should exist");
    }

    #[test]
    fn same_context_does_not_graduate() {
        let (mut store, ids) = make_store_with_memories();
        let gen = RuleBasedEdgeGenerator::new();
        let hit_ids = &ids[0..3];

        // 5 observations but all from the SAME context
        for i in 0..5 {
            run_with_context(&mut store, &gen, "same query", "same_ctx", "same_tag", hit_ids, 1000 + i * 100);
        }

        let confirmed = store
            .get_hypotheses_by_status(EdgeHypothesisStatus::Confirmed)
            .unwrap();
        assert!(
            confirmed.is_empty(),
            "hypotheses from single context should not graduate"
        );
    }

    #[test]
    fn decay_forgets_unconfirmed() {
        let (mut store, ids) = make_store_with_memories();
        let gen = RuleBasedEdgeGenerator::new();
        let hit_ids = &ids[0..2];

        run_with_context(&mut store, &gen, "query", "ctx_a", "tag", hit_ids, 1000);

        // Decay many times
        for _ in 0..10 {
            store.decay_hypotheses().unwrap();
        }

        let forgotten = store
            .get_hypotheses_by_status(EdgeHypothesisStatus::Forgotten)
            .unwrap();
        assert!(
            !forgotten.is_empty(),
            "unconfirmed hypotheses should decay to forgotten"
        );
    }

    #[test]
    fn edge_density_is_lower_than_entity_shared() {
        // With 20 memories and selective co-retrieval (each query hits 3),
        // density should be far below the 96.7% from entity-shared edges.
        let mut store = Store::open_in_memory().unwrap();
        let mut ids = Vec::new();
        for i in 0..20 {
            let input = WriteInput {
                content: format!("memory content {}", i),
                kind: crate::MemoryKind::Fact,
                scope: crate::Scope::Global,
                source: crate::Source::ExplicitUser,
                confidence: None,
                importance: None,
            };
            ids.push(store.write(input).unwrap().id);
        }
        let gen = RuleBasedEdgeGenerator::new();

        // 15 queries, each retrieving 3 memories from different clusters.
        // Only memories within the same cluster get co-retrieved.
        let contexts = [
            ("ctx1", "topic1"), ("ctx2", "topic2"), ("ctx3", "topic3"),
            ("ctx4", "topic4"), ("ctx5", "topic5"), ("ctx6", "topic6"),
            ("ctx7", "topic7"), ("ctx8", "topic8"), ("ctx9", "topic9"),
            ("ctx10", "topic10"), ("ctx11", "topic11"), ("ctx12", "topic12"),
            ("ctx13", "topic13"), ("ctx14", "topic14"), ("ctx15", "topic15"),
        ];

        for (i, (hash, tag)) in contexts.iter().enumerate() {
            // Each query hits a cluster of 3 consecutive memories.
            // Clusters don't overlap, so only intra-cluster pairs get edges.
            let cluster_start = (i % 6) * 3; // clusters: 0-2, 3-5, 6-8, 9-11, 12-14, 15-17
            let hit_ids: Vec<String> = ids[cluster_start..cluster_start + 3].to_vec();
            run_with_context(
                &mut store,
                &gen,
                &format!("query {}", i),
                hash,
                tag,
                &hit_ids,
                1000 + i as i64 * 100,
            );
        }

        store.graduate_confirmed().unwrap();

        let edge_count = store.count_memory_edges().unwrap();
        let n_memories = 20;
        let max_possible = n_memories * (n_memories - 1);
        let density = edge_count as f64 / max_possible as f64 * 100.0;

        println!("edge_count: {}, max_possible: {}, density: {:.1}%", edge_count, max_possible, density);

        // With clustered co-retrieval, only intra-cluster pairs graduate.
        // 6 clusters x 3 choose 2 = 18 pairs x 2 (bidirectional) = 36 edges max.
        // 36/380 = 9.5%. Well below 96.7%.
        assert!(
            density < 20.0,
            "density should be well below entity-shared approach (was 96.7%)"
        );
    }
}
