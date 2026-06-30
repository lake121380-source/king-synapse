pub fn recall_at_k(returned: &[String], relevant: &[String], k: usize) -> f64 {
    if relevant.is_empty() {
        return 0.0;
    }
    let cut: Vec<&String> = returned.iter().take(k).collect();
    let hit = relevant
        .iter()
        .filter(|r| cut.iter().any(|x| x.as_str() == r.as_str()))
        .count();
    hit as f64 / relevant.len() as f64
}

pub fn reciprocal_rank(returned: &[String], relevant: &[String]) -> f64 {
    for (i, r) in returned.iter().enumerate() {
        if relevant.iter().any(|x| x == r) {
            return 1.0 / (i as f64 + 1.0);
        }
    }
    0.0
}

pub fn ndcg_at_k(returned: &[String], relevant: &[String], k: usize) -> f64 {
    if relevant.is_empty() {
        return 0.0;
    }
    let mut dcg = 0.0;
    for (i, r) in returned.iter().take(k).enumerate() {
        if relevant.iter().any(|x| x == r) {
            dcg += 1.0 / (i as f64 + 2.0).log2();
        }
    }
    let ideal_hits = relevant.len().min(k);
    let mut idcg = 0.0;
    for i in 0..ideal_hits {
        idcg += 1.0 / (i as f64 + 2.0).log2();
    }
    if idcg == 0.0 {
        0.0
    } else {
        dcg / idcg
    }
}

pub fn percentile(latencies: &mut [f64], p: f64) -> f64 {
    if latencies.is_empty() {
        return 0.0;
    }
    latencies.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let idx = ((p / 100.0) * (latencies.len() as f64 - 1.0)).round() as usize;
    latencies[idx.min(latencies.len() - 1)]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(v: &[&str]) -> Vec<String> {
        v.iter().map(|x| x.to_string()).collect()
    }

    #[test]
    fn recall_basic() {
        let r = recall_at_k(&s(&["a", "b", "c"]), &s(&["b"]), 5);
        assert!((r - 1.0).abs() < 1e-9);
        let r = recall_at_k(&s(&["a", "b", "c"]), &s(&["x"]), 5);
        assert!(r.abs() < 1e-9);
    }

    #[test]
    fn mrr_basic() {
        let r = reciprocal_rank(&s(&["a", "b", "c"]), &s(&["c"]));
        assert!((r - 1.0 / 3.0).abs() < 1e-9);
    }

    #[test]
    fn ndcg_basic() {
        let r = ndcg_at_k(&s(&["a", "b"]), &s(&["a"]), 10);
        assert!((r - 1.0).abs() < 1e-9);
        let r = ndcg_at_k(&s(&["b", "a"]), &s(&["a"]), 10);
        assert!(r < 1.0);
    }

    #[test]
    fn percentile_basic() {
        let mut v = vec![10.0, 20.0, 30.0, 40.0, 50.0];
        assert!((percentile(&mut v.clone(), 50.0) - 30.0).abs() < 1e-9);
        assert!(percentile(&mut v, 95.0) >= 40.0);
    }
}
