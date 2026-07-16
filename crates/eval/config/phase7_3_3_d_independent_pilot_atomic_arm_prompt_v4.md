# Independent Pilot Atomic Arm v4 — Frozen Single-Proposition Frame Adapter

## System message
Use only the supplied same-case Evidence. Apply conservative entailment. Similar wording alone is insufficient. Preserve the Candidate's criterion, selection direction, scope, time, safety constraints, and reliability. Labels: supported = Evidence entails the whole proposition; partially_supported = Evidence supports a strict subset but not the whole proposition; unsupported = Evidence fails to support or contradicts a material part; not_assessable = the supplied Evidence cannot support a meaningful assessment. Never infer any hidden Reference, Gold, historical label, or other arm. Return bare JSON only.
This Pilot frame was frozen before this execution and is handled by a scope-limited single-proposition adapter. Judge the whole Candidate as exactly one material Atomic Claim. Do not copy the Candidate text and do not emit spans or nested claim objects. Return exactly: {"case_id":"...","operation":"whole_candidate_claim","claim_material":true,"claim_support_label":"supported|partially_supported|unsupported|not_assessable","rationale":"non-empty","candidate_reference_label":"same value as claim_support_label"}. The operation must be whole_candidate_claim, claim_material must be true, and candidate_reference_label must exactly equal claim_support_label.

## User message template
{{ITEM_JSON}}
