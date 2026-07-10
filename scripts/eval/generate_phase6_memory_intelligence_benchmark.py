#!/usr/bin/env python3
"""Generate the frozen Phase 6.0 deterministic Agent-memory benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "crates/eval/datasets/memory_intelligence/agent_memory_benchmark.toml"
SCENARIOS_PER_CATEGORY = 32

CATEGORIES = [
    {
        "name": "temporal_update",
        "short": "tmp",
        "intervention_required": True,
        "expected_kind": "state",
        "trap_kind": "state",
        "expected_confidence": 0.95,
        "trap_confidence": 0.92,
        "expected_recent": True,
        "trap_recent": False,
        "signals": ["temporal", "semantic"],
        "reason": "the later confirmed state supersedes the older semantically stronger state",
        "expected_text": "later confirmed state is active and replaces the earlier state",
        "trap_text": "older state has strong lexical overlap but is no longer active",
    },
    {
        "name": "failure_override",
        "short": "fail",
        "intervention_required": True,
        "expected_kind": "failure",
        "trap_kind": "playbook",
        "expected_confidence": 0.96,
        "trap_confidence": 0.93,
        "expected_recent": False,
        "trap_recent": False,
        "signals": ["failure", "semantic"],
        "reason": "verified failure evidence must override the previously successful playbook",
        "expected_text": "verified failure evidence says this approach caused harm and must not be repeated",
        "trap_text": "older successful playbook recommends repeating the approach",
    },
    {
        "name": "reliability_conflict",
        "short": "rel",
        "intervention_required": False,
        "expected_kind": "fact",
        "trap_kind": "fact",
        "expected_confidence": 0.99,
        "trap_confidence": 0.48,
        "expected_recent": False,
        "trap_recent": False,
        "signals": ["reliability", "semantic"],
        "reason": "direct user confirmation outranks a lexically stronger unverified report",
        "expected_text": "direct user confirmation establishes the reliable fact",
        "trap_text": "unverified third party report repeats the claim but remains unreliable",
    },
    {
        "name": "preference_evolution",
        "short": "pref",
        "intervention_required": True,
        "expected_kind": "preference",
        "trap_kind": "preference",
        "expected_confidence": 0.96,
        "trap_confidence": 0.91,
        "expected_recent": True,
        "trap_recent": False,
        "signals": ["preference", "temporal", "semantic"],
        "reason": "the current explicit preference supersedes the older preference",
        "expected_text": "current explicit preference replaces the earlier choice",
        "trap_text": "older preference is repeated often but has been superseded",
    },
    {
        "name": "contextual_constraint",
        "short": "ctx",
        "intervention_required": True,
        "expected_kind": "playbook",
        "trap_kind": "playbook",
        "expected_confidence": 0.94,
        "trap_confidence": 0.91,
        "expected_recent": False,
        "trap_recent": False,
        "signals": ["context", "semantic"],
        "reason": "the active task constraint selects the context-compatible playbook",
        "expected_text": "playbook satisfies the active safety and scope constraint",
        "trap_text": "generic playbook has stronger overlap but violates the active constraint",
    },
    {
        "name": "failure_vs_recency_failure_wins",
        "short": "frf",
        "intervention_required": True,
        "expected_kind": "failure",
        "trap_kind": "playbook",
        "expected_confidence": 0.97,
        "trap_confidence": 0.92,
        "expected_recent": False,
        "trap_recent": True,
        "signals": ["failure", "recency", "semantic"],
        "reason": "unresolved failure evidence must beat a recently accessed unsafe playbook",
        "expected_text": "unresolved failure evidence remains authoritative despite not being recently accessed",
        "trap_text": "unsafe playbook was accessed recently but still repeats the failed approach",
    },
    {
        "name": "failure_vs_recency_recency_wins",
        "short": "frr",
        "intervention_required": True,
        "expected_kind": "playbook",
        "trap_kind": "failure",
        "expected_confidence": 0.95,
        "trap_confidence": 0.91,
        "expected_recent": True,
        "trap_recent": False,
        "signals": ["failure", "recency", "temporal"],
        "reason": "a later verified recovery supersedes resolved historical failure evidence",
        "expected_text": "later verified recovery playbook is active after the historical failure was resolved",
        "trap_text": "historical failure record is important but explicitly resolved",
    },
    {
        "name": "reliability_vs_recency_reliability_wins",
        "short": "rrl",
        "intervention_required": False,
        "expected_kind": "fact",
        "trap_kind": "state",
        "expected_confidence": 0.99,
        "trap_confidence": 0.44,
        "expected_recent": False,
        "trap_recent": True,
        "signals": ["reliability", "recency", "semantic"],
        "reason": "high-confidence confirmation beats a recent but weak observation",
        "expected_text": "high confidence confirmation remains authoritative",
        "trap_text": "recent weak observation is accessible but not verified",
    },
    {
        "name": "reliability_vs_recency_recency_wins",
        "short": "rrr",
        "intervention_required": True,
        "expected_kind": "state",
        "trap_kind": "fact",
        "expected_confidence": 0.91,
        "trap_confidence": 0.98,
        "expected_recent": True,
        "trap_recent": False,
        "signals": ["reliability", "recency", "temporal"],
        "reason": "a current observed state supersedes a reliable but explicitly stale fact",
        "expected_text": "current observed state is active and the older reliable fact is stale",
        "trap_text": "older fact was highly reliable when recorded but is explicitly stale now",
    },
    {
        "name": "no_intervention",
        "short": "safe",
        "intervention_required": False,
        "expected_kind": "fact",
        "trap_kind": "state",
        "expected_confidence": 0.98,
        "trap_confidence": 0.70,
        "expected_recent": True,
        "trap_recent": False,
        "signals": ["semantic", "reliability", "recency"],
        "reason": "baseline evidence is already clear and no cognitive intervention is needed",
        "expected_text": "clear current confirmed answer should remain first",
        "trap_text": "secondary state is related but clearly weaker",
    },
]

VARIANTS = [
    ("session record", "decision note", "background observation"),
    ("conversation turn", "working note", "archived observation"),
    ("agent episode", "task note", "neutral observation"),
    ("long horizon turn", "review note", "historical observation"),
]


def q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def split_for(index: int) -> str:
    if index < 16:
        return "train"
    if index < 24:
        return "validation"
    return "test"


def phrase(global_index: int) -> str:
    return f"mora{global_index:03d} sela{global_index:03d} navi{global_index:03d}"


def repeated(base: str, count: int) -> str:
    return " ".join([base] * count)


def memory_block(
    *,
    label: str,
    content: str,
    kind: str,
    confidence: float,
    importance: float,
    recently_accessed: bool,
    relevant: bool,
    turn: int,
    role: str,
) -> list[str]:
    return [
        "[[scenario.memory]]",
        f"label = {q(label)}",
        f"content = {q(content)}",
        f"kind = {q(kind)}",
        f"confidence = {confidence:.2f}",
        f"importance = {importance:.2f}",
        f"recently_accessed = {'true' if recently_accessed else 'false'}",
        f"relevant = {'true' if relevant else 'false'}",
        f"turn = {turn}",
        f"role = {q(role)}",
        "",
    ]


def generate() -> str:
    lines = [
        "# Generated by scripts/eval/generate_phase6_memory_intelligence_benchmark.py",
        "# Do not hand-edit; regenerate and validate with --check.",
        "schema_version = 1",
        'benchmark_version = "phase6.0-memory-intelligence-benchmark-v1"',
        "generator_seed = 600320",
        "",
    ]
    global_index = 0
    for category in CATEGORIES:
        for local_index in range(SCENARIOS_PER_CATEGORY):
            global_index += 1
            split = split_for(local_index)
            base = phrase(global_index)
            variant = local_index % len(VARIANTS)
            session_word, note_word, archive_word = VARIANTS[variant]
            intervention_required = category["intervention_required"]
            expected_repeats = 4 + (local_index % 2) if intervention_required else 7
            trap_repeats = 7 if intervention_required else 5
            secondary_repeats = 6 if intervention_required else 4

            lines.extend(
                [
                    "[[scenario]]",
                    f'id = {q(f"mi_{split}_{category["short"]}_{local_index + 1:03d}")}',
                    f"split = {q(split)}",
                    f"category = {q(category['name'])}",
                    f"query = {q(base)}",
                    'expected_top = "expected"',
                    f"intervention_required = {'true' if intervention_required else 'false'}",
                    f"timeline_length = {6 + variant}",
                    f"template_variant = {variant}",
                    f"expected_reason = {q(category['reason'])}",
                    "conflicting_signals = [" + ", ".join(q(v) for v in category["signals"]) + "]",
                    "",
                ]
            )

            expected_content = (
                f"{repeated(base, expected_repeats)}: {session_word}: "
                f"{category['expected_text']}."
            )
            trap_content = (
                f"{repeated(base, trap_repeats)}: {note_word}: "
                f"{category['trap_text']}."
            )
            secondary_content = (
                f"{repeated(base, secondary_repeats)}: competing signal record for controlled "
                f"long-term memory conflict evaluation."
            )
            archive_content = (
                f"{repeated(base, 3)}: {archive_word} retained for provenance without a current decision."
            )
            generic_content = f"{repeated(base, 2)}: generic state with no verified authority."
            weak_content = f"{base}: tentative preference with weak evidence."

            memories = [
                dict(
                    label="semantic_trap",
                    content=trap_content,
                    kind=category["trap_kind"],
                    confidence=category["trap_confidence"],
                    importance=0.97 if intervention_required else 0.88,
                    recently_accessed=category["trap_recent"],
                    relevant=False,
                    turn=1,
                    role="competing_prior",
                ),
                dict(
                    label="secondary_conflict",
                    content=secondary_content,
                    kind="state",
                    confidence=0.80,
                    importance=0.82,
                    recently_accessed=False,
                    relevant=False,
                    turn=2,
                    role="secondary_competitor",
                ),
                dict(
                    label="archive_note",
                    content=archive_content,
                    kind="fact",
                    confidence=0.82,
                    importance=0.78,
                    recently_accessed=False,
                    relevant=False,
                    turn=3,
                    role="provenance_only",
                ),
                dict(
                    label="generic_state",
                    content=generic_content,
                    kind="state",
                    confidence=0.76,
                    importance=0.77,
                    recently_accessed=False,
                    relevant=False,
                    turn=4,
                    role="background_state",
                ),
                dict(
                    label="weak_preference",
                    content=weak_content,
                    kind="preference",
                    confidence=0.68,
                    importance=0.74,
                    recently_accessed=False,
                    relevant=False,
                    turn=5,
                    role="weak_signal",
                ),
                dict(
                    label="expected",
                    content=expected_content,
                    kind=category["expected_kind"],
                    confidence=category["expected_confidence"],
                    importance=0.84 if intervention_required else 0.98,
                    recently_accessed=category["expected_recent"],
                    relevant=True,
                    turn=6 + variant,
                    role="ground_truth",
                ),
            ]
            for memory in memories:
                lines.extend(memory_block(**memory))

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the checked-in dataset differs")
    args = parser.parse_args()
    rendered = generate()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            print(f"FAIL generated dataset differs: {OUTPUT}")
            return 1
        print(f"PASS generated dataset is reproducible: {OUTPUT}")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"wrote {SCENARIOS_PER_CATEGORY * len(CATEGORIES)} scenarios to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
