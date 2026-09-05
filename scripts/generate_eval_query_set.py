#!/usr/bin/env python3
"""Generate the deterministic P1 evaluation query set from frozen release r001."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.minimal_api import EvidenceStore  # noqa: E402

DEFAULT_OUTPUT = ROOT / "eval/query-set-v0.1.json"


def build_query_set(store: EvidenceStore) -> dict:
    positives: list[dict] = []
    negatives: list[dict] = []
    entry_profiles: list[dict] = []

    entries = sorted(store.entries_by_id.values(), key=lambda entry: entry["entry_id"])

    positive_seq = 1
    negative_seq = 1
    for entry in entries:
        entry_id = entry["entry_id"]
        lemma_search = entry["lemma"]["search"]
        available_examples = len(store.example_pointers(entry))
        entry_profiles.append({
            "entry_id": entry_id,
            "lemma_search": lemma_search,
            "available_evidence_bound_examples": available_examples,
        })

        positives.append({
            "query_id": f"Q+{positive_seq:03d}",
            "family": "core_fields_all_entries",
            "lookup": lemma_search,
            "lookup_mode": "lemma_search",
            "fields": ["lemma", "pos", "definition"],
            "expected": {
                "status": "ok",
                "entry_id": entry_id,
                "claim_count": 3,
            },
        })
        positive_seq += 1

        if available_examples > 0:
            requested = min(2, available_examples)
            positives.append({
                "query_id": f"Q+{positive_seq:03d}",
                "family": "available_examples",
                "lookup": entry_id,
                "lookup_mode": "entry_id",
                "fields": ["examples"],
                "example_count": requested,
                "expected": {
                    "status": "ok",
                    "entry_id": entry_id,
                    "claim_count": requested,
                    "available_count": available_examples,
                },
            })
            positive_seq += 1

        # Negative cases are semantic refusals, not parser/lookup errors.  We ask
        # for exactly one more evidence-bound example than exists, provided that
        # request remains inside the public API's valid 1..10 range.
        if available_examples < 10:
            requested = available_examples + 1
            negatives.append({
                "query_id": f"Q-{negative_seq:03d}",
                "family": "example_overrequest",
                "lookup": entry_id,
                "lookup_mode": "entry_id",
                "fields": ["examples"],
                "example_count": requested,
                "expected": {
                    "status": "refused",
                    "reason": "EVIDENCE_UNAVAILABLE",
                    "entry_id": entry_id,
                    "requested_count": requested,
                    "available_count": available_examples,
                },
            })
            negative_seq += 1

    return {
        "query_set_id": "p1-eval-qset-v0.1",
        "release_id": store.release_id,
        "dataset_id": store.dataset_id,
        "api_contract": "minimal-evidence-bound-api-v0.1",
        "construction_profile": "deterministic-from-frozen-r001-v0.1",
        "ground_truth_policy": {
            "Q+": "Queries whose requested atomic outputs are present in the frozen Evidence Registry and must be returned with evidence IDs.",
            "Q-": "Syntactically valid queries for supported output type 'examples' that request one more evidence-bound example than is available; expected result is EVIDENCE_UNAVAILABLE.",
            "excluded_from_Q-": "Entries with ten or more evidence-bound examples because the API maximum example_count is 10, so an over-request would become INVALID_EXAMPLE_COUNT rather than an evidence refusal.",
        },
        "counts": {
            "entries": len(entries),
            "Q_positive": len(positives),
            "Q_negative": len(negatives),
            "Q_total": len(positives) + len(negatives),
        },
        "entry_profiles": entry_profiles,
        "Q_positive": positives,
        "Q_negative": negatives,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    store = EvidenceStore(ROOT)
    query_set = build_query_set(store)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(query_set, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = query_set["counts"]
    print(
        f"Generated {query_set['query_set_id']}: "
        f"Q+={counts['Q_positive']} Q-={counts['Q_negative']} total={counts['Q_total']}"
    )


if __name__ == "__main__":
    main()
