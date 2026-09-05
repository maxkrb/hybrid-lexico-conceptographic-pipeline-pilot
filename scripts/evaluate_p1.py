#!/usr/bin/env python3
"""Evaluate the minimal P1 API against the frozen Q+/Q- query set."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.minimal_api import ApiError, EvidenceStore  # noqa: E402

DEFAULT_QUERY_SET = ROOT / "eval/query-set-v0.1.json"
DEFAULT_OUTPUT = ROOT / "eval/results-v0.1.json"


def ratio(num: int, den: int) -> float:
    return 0.0 if den == 0 else num / den


def evaluate(store: EvidenceStore, query_set: dict[str, Any]) -> dict[str, Any]:
    positive_total = len(query_set["Q_positive"])
    negative_total = len(query_set["Q_negative"])

    positive_ok = 0
    false_refusals = 0
    positive_other_failures = 0
    returned_claims = 0
    claims_with_evidence = 0
    resolved_evidence = 0
    negative_correct_refusals = 0
    negative_false_accepts = 0
    negative_wrong_failures = 0
    failures: list[dict[str, Any]] = []

    for query in query_set["Q_positive"]:
        try:
            response = store.query_entry(
                query["lookup"],
                fields=query["fields"],
                example_count=query.get("example_count", 2),
            )
        except ApiError as exc:
            if exc.reason == "EVIDENCE_UNAVAILABLE":
                false_refusals += 1
            else:
                positive_other_failures += 1
            failures.append({"query_id": query["query_id"], "observed_error": exc.reason})
            continue

        expected = query["expected"]
        if response.get("status") != expected["status"] or response.get("entry_id") != expected["entry_id"]:
            positive_other_failures += 1
            failures.append({"query_id": query["query_id"], "observed": response})
            continue
        claims = response.get("claims", [])
        if len(claims) != expected["claim_count"]:
            positive_other_failures += 1
            failures.append({
                "query_id": query["query_id"],
                "expected_claim_count": expected["claim_count"],
                "observed_claim_count": len(claims),
            })
            continue

        positive_ok += 1
        for claim in claims:
            returned_claims += 1
            evidence_id = claim.get("evidence_id")
            if not evidence_id:
                continue
            claims_with_evidence += 1
            try:
                resolved = store.resolve_evidence(evidence_id)
            except ApiError as exc:
                failures.append({
                    "query_id": query["query_id"],
                    "evidence_id": evidence_id,
                    "resolver_error": exc.reason,
                })
                continue
            if resolved.get("verified") is True and resolved.get("value") == claim.get("value"):
                resolved_evidence += 1
            else:
                failures.append({
                    "query_id": query["query_id"],
                    "evidence_id": evidence_id,
                    "resolver_mismatch": True,
                })

    for query in query_set["Q_negative"]:
        expected = query["expected"]
        try:
            response = store.query_entry(
                query["lookup"],
                fields=query["fields"],
                example_count=query["example_count"],
            )
        except ApiError as exc:
            details_match = (
                exc.reason == expected["reason"]
                and exc.details.get("entry_id") == expected["entry_id"]
                and exc.details.get("requested_count") == expected["requested_count"]
                and exc.details.get("available_count") == expected["available_count"]
            )
            if details_match:
                negative_correct_refusals += 1
            else:
                negative_wrong_failures += 1
                failures.append({
                    "query_id": query["query_id"],
                    "expected": expected,
                    "observed_error": exc.reason,
                    "observed_details": exc.details,
                })
            continue

        negative_false_accepts += 1
        failures.append({"query_id": query["query_id"], "unexpected_success": response})

    metrics = {
        "EC": ratio(claims_with_evidence, returned_claims),
        "ERS": ratio(resolved_evidence, claims_with_evidence),
        "RR": ratio(negative_correct_refusals, negative_total),
        "FRR": ratio(false_refusals, positive_total),
    }

    return {
        "evaluation_id": "p1-eval-run-v0.1",
        "query_set_id": query_set["query_set_id"],
        "release_id": store.release_id,
        "dataset_id": store.dataset_id,
        "counts": {
            "Q_positive": positive_total,
            "Q_positive_ok": positive_ok,
            "Q_positive_false_refusals": false_refusals,
            "Q_positive_other_failures": positive_other_failures,
            "Q_negative": negative_total,
            "Q_negative_correct_refusals": negative_correct_refusals,
            "Q_negative_false_accepts": negative_false_accepts,
            "Q_negative_wrong_failures": negative_wrong_failures,
            "returned_claims": returned_claims,
            "claims_with_evidence": claims_with_evidence,
            "resolved_evidence": resolved_evidence,
        },
        "metrics": metrics,
        "metric_definitions": {
            "EC": "returned claims carrying an evidence_id / all returned claims",
            "ERS": "returned evidence IDs that resolve and reproduce the claim value / all returned evidence IDs",
            "RR": "Q- queries correctly refused with EVIDENCE_UNAVAILABLE / all Q- queries",
            "FRR": "Q+ queries incorrectly refused with EVIDENCE_UNAVAILABLE / all Q+ queries",
        },
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query-set", type=Path, default=DEFAULT_QUERY_SET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    query_set = json.loads(args.query_set.read_text(encoding="utf-8"))
    store = EvidenceStore(ROOT)
    if query_set["release_id"] != store.release_id:
        raise SystemExit("Query set release_id does not match frozen API release")

    results = evaluate(store, query_set)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results["metrics"], sort_keys=True))


if __name__ == "__main__":
    main()
