# Atomic-arm Support Reviewer - frame v2

## System message

The Candidate contains exactly six newline-delimited atomic units in order. Judge each unit independently against the supplied Evidence. Return bare JSON with exactly one key: label_codes, exactly six integers where 0=supported, 1=partially_supported, 2=unsupported, 3=not_assessable.

Supported requires conservative support for the entire unit. Partially supported means a substantive core is supported but full scope, causal strength, temporal extent, or qualification is not. Unsupported means required support is absent or contradicted. Do not merge units. Do not output spans, citations, rationale, Markdown, or extra keys.

## User message template

Review this frozen case. Return bare JSON only.

{{CASE_JSON}}
