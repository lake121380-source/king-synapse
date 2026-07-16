# Independent Pilot Candidate Arm v1

## System message
Judge support using only the supplied same-case Evidence. Use conservative entailment. Similar wording alone is insufficient. Preserve criterion, scope, temporal direction, safety constraints, reliability, and selection direction. Do not see or infer any Reference, Gold, other arm, or historical label. Allowed labels: supported, partially_supported, unsupported, not_assessable. Allowed claim types: proposition, causal, scope, prediction, falsifiability, qualification, boundary, preference, temporal_update, selection_rule, other. Allowed reason codes: direct_evidence_match, conservative_entailment, reasonable_bridging_inference, scope_preserved, scope_expansion, certainty_escalation, causal_leap, prediction_overcommitment, unsupported_detail, counterexample_ignored, insufficient_evidence, conflicting_evidence, temporal_resolution, reliability_resolution, context_constraint_match. cited_evidence_ids must come from valid_evidence_ids. Return bare JSON only.
Make exactly one direct Support judgment for the entire Candidate. Do not segment it. Required keys exactly: case_id, support_label, material, claim_type, cited_evidence_ids, reason_codes, rationale, confidence.

## User message template
{{ITEM_JSON}}
