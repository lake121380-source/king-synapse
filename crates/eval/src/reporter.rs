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
