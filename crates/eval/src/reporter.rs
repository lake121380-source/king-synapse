use crate::types::Report;

pub fn print_table(r: &Report) {
    println!("=== King Synapse recall bench ===");
    println!("tag:            {}", r.tag);
    println!("dataset:        {}", r.dataset);
    println!("vectors:        {}", r.vectors_enabled);
    println!(
        "rerank:         {} (pool={})",
        r.rerank_enabled, r.rerank_pool
    );
    println!(
        "rrf:            k={:.1} weights=fts:{:.2} entity:{:.2} vector:{:.2}",
        r.rrf_k, r.rrf_weights.fts, r.rrf_weights.entity, r.rrf_weights.vector
    );
    println!(
        "corpus:         {} memories / {} queries / top-{}",
        r.n_memories, r.n_queries, r.k
    );
    println!("---------------------------------");
    println!("Recall@5:       {:.3}", r.recall_at_5);
    println!("Recall@10:      {:.3}", r.recall_at_10);
    println!("MRR@10:         {:.3}", r.mrr_at_10);
    println!("NDCG@10:        {:.3}", r.ndcg_at_10);
    println!("P50 latency:    {:.2} ms", r.p50_latency_ms);
    println!("P95 latency:    {:.2} ms", r.p95_latency_ms);
    println!("total wall:     {:.1} ms", r.total_ms);
    if let Some(survival) = r.semantic_survival.as_ref() {
        println!(
            "semantic survival: {} -> {} -> {} -> {} -> {}",
            survival.candidate_count,
            survival.unique_accepted_edges,
            survival.confirmed_count,
            survival.graduated_count,
            survival.activated_count
        );
        println!(
            "semantic utility:  q={} affected={} edges={} useful={} harmful={} rank_delta={:.3} mrr_delta={:.4}",
            survival.utility.evaluated_queries,
            survival.utility.affected_queries,
            survival.utility.affected_edges,
            survival.utility.useful_edges,
            survival.utility.harmful_edges,
            survival.utility.mean_rank_delta,
            survival.utility.mean_mrr_delta
        );
        println!(
            "edge attribution:  tested={} edges={} useful={} harmful={} rank_delta={:.3} mrr_delta={:.4}",
            survival.utility.attribution_evaluated_edges,
            survival.utility.attribution_affected_edges,
            survival.utility.causal_useful_edges,
            survival.utility.causal_harmful_edges,
            survival.utility.mean_causal_rank_delta,
            survival.utility.mean_causal_mrr_delta
        );
        println!(
            "edge governance:   trusted={} suspect={} dormant={} weight={:.3} q={} changed={} rank_delta={:.3} mrr_delta={:.4}",
            survival.governance.trusted_edges,
            survival.governance.suspect_edges,
            survival.governance.dormant_edges,
            survival.governance.mean_governance_weight,
            survival.governance.evaluated_queries,
            survival.governance.changed_queries,
            survival.governance.mean_rank_delta_vs_full_graph,
            survival.governance.mean_mrr_delta_vs_full_graph
        );
        let policy_summary = survival
            .policy_search
            .policies
            .iter()
            .map(|policy| format!("{}:{:.4}", policy.name, policy.mean_mrr_delta_vs_full_graph))
            .collect::<Vec<_>>()
            .join(", ");
        println!(
            "policy search:     best={} [{}]",
            survival
                .policy_search
                .best_policy_by_mrr
                .as_deref()
                .unwrap_or("none"),
            policy_summary
        );
    }
    println!();
    println!("Per-query misses (Recall@10 < 1.0, up to 12):");
    let mut shown = 0;
    for q in &r.per_query {
        if q.recall_at_10 >= 1.0 - 1e-9 {
            continue;
        }
        let preview: String = q
            .returned
            .iter()
            .take(5)
            .cloned()
            .collect::<Vec<_>>()
            .join(", ");
        println!(
            "  R@10={:.2} rr={:.2} q={:?} want={:?} got=[{}]",
            q.recall_at_10, q.rr, q.query, q.relevant, preview
        );
        shown += 1;
        if shown >= 12 {
            break;
        }
    }
    if shown == 0 {
        println!("  (all queries hit Recall@10 == 1.0)");
    }
}
