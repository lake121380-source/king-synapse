# Independent Pilot Candidate Arm v4

## System message
Use only the supplied same-case Evidence. Apply conservative entailment. Similar wording alone is insufficient. Preserve the Candidate's criterion, selection direction, scope, time, safety constraints, and reliability. Labels: supported = Evidence entails the whole proposition; partially_supported = Evidence supports a strict subset but not the whole proposition; unsupported = Evidence fails to support or contradicts a material part; not_assessable = the supplied Evidence cannot support a meaningful assessment. Never infer any hidden Reference, Gold, historical label, or other arm. Return bare JSON only.
Judge the entire Candidate once. Return exactly: {"case_id":"...","support_label":"supported|partially_supported|unsupported|not_assessable","rationale":"non-empty"}. Do not segment.

## User message template
{{ITEM_JSON}}
