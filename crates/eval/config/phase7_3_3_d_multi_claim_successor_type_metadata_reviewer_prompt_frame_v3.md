# Type/Metadata Reviewer — Fixed Code Representation v3

## System message

Classify the six frozen Claims in their supplied order. Do not change Claims and do not judge evidence or support.

Return bare JSON with exactly two keys: role_codes and type_codes. Each value must be an array of exactly six integers. Position i classifies Claim position i.

Role codes: 0=anchor, 1=support, 2=qualification, 3=boundary, 4=prediction, 5=exception.
Type codes: 0=proposition, 1=causal, 2=prediction, 3=scope, 4=falsifiability, 5=limitation, 6=condition, 7=exception.

All claim_origin values are reconstructed as explicit by the Adapter and must not be output. Do not output Claim IDs, labels, rationale, confidence, Markdown, or extra keys.

## User message template

Classify this frozen ordered Claim list. Return bare JSON only.

{{CASE_JSON}}
