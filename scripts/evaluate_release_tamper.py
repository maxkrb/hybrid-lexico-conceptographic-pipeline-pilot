#!/usr/bin/env python3
"""Run the deterministic P3 release-level tamper-detection experiment."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.release_integrity import (
    COMMITMENT_PATH,
    CONTENT_HASHES_PATH,
    RELEASE_PATH,
    jcs_sha256,
    load_json,
    verify_release_state,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval" / "release-tamper-cases-v0.1.json"
OUTPUT_PATH = ROOT / "eval" / "release-tamper-results-v0.1.json"
EXPERIMENT_ID = "p3-release-tamper-run-v0.1"


def _content_map() -> dict[str, dict[str, Any]]:
    manifest = load_json(CONTENT_HASHES_PATH)
    return {item["entry_id"]: item for item in manifest["entries"]}


def _find_release_entry(release: dict[str, Any], entry_id: str) -> dict[str, str]:
    for item in release["entries"]:
        if item["entry_id"] == entry_id:
            return item
    raise KeyError(entry_id)


def apply_case(
    base_release: dict[str, Any],
    base_commitment: dict[str, Any],
    case: dict[str, Any],
    content_map: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    release = deepcopy(base_release)
    commitment = deepcopy(base_commitment)
    overrides: dict[str, Any] = {}
    mutation = case["mutation"]
    corruption_class = case["corruption_class"]

    if corruption_class == "canonical_content_mutation":
        entry_id = mutation["entry_id"]
        document = deepcopy(load_json(ROOT / content_map[entry_id]["canonical_file"]))
        pointer = mutation["json_pointer"]
        if pointer != "/def_short":
            raise ValueError("v0.1 evaluator supports /def_short canonical mutation only")
        before = document["def_short"]
        if jcs_sha256(before) != mutation["before_target_jcs_sha256"]:
            raise ValueError(f"case {case['case_id']} before-target fingerprint mismatch")
        document["def_short"] = before + mutation["literal"]
        if jcs_sha256(document["def_short"]) != mutation["after_target_jcs_sha256"]:
            raise ValueError(f"case {case['case_id']} after-target fingerprint mismatch")
        overrides[entry_id] = document

    elif corruption_class in {"release_entry_digest_mutation", "release_entry_digest_remap"}:
        entry = _find_release_entry(release, mutation["entry_id"])
        if entry["content_sha256"] != mutation["before"]:
            raise ValueError(f"case {case['case_id']} release digest before-value mismatch")
        entry["content_sha256"] = mutation["after"]

    elif corruption_class == "release_entry_id_mutation":
        entry = _find_release_entry(release, mutation["before"])
        entry["entry_id"] = mutation["after"]

    elif corruption_class == "release_entry_removal":
        entry_id = mutation["entry_id"]
        release["entries"] = [item for item in release["entries"] if item["entry_id"] != entry_id]
        release["entry_count"] = mutation["entry_count_after"]

    elif corruption_class == "release_entry_addition":
        release["entries"].append(deepcopy(mutation["added_entry"]))
        release["entry_count"] = mutation["entry_count_after"]

    elif corruption_class == "release_entry_reorder":
        left, right = mutation["swap_indices"]
        release["entries"][left], release["entries"][right] = release["entries"][right], release["entries"][left]

    elif corruption_class == "merkle_root_mutation":
        if release["merkle_root"] != mutation["before"]:
            raise ValueError(f"case {case['case_id']} Merkle-root before-value mismatch")
        release["merkle_root"] = mutation["after"]

    elif corruption_class == "release_id_mutation":
        if release["release_id"] != mutation["before"]:
            raise ValueError(f"case {case['case_id']} release-id before-value mismatch")
        release["release_id"] = mutation["after"]

    elif corruption_class == "release_commitment_hash_mutation":
        if commitment["release_json_sha256"] != mutation["before"]:
            raise ValueError(f"case {case['case_id']} commitment-hash before-value mismatch")
        commitment["release_json_sha256"] = mutation["after"]

    else:
        raise ValueError(f"unsupported release tamper class: {corruption_class}")

    return release, commitment, overrides


def evaluate() -> dict[str, Any]:
    base_release = load_json(RELEASE_PATH)
    base_commitment = load_json(COMMITMENT_PATH)
    cases_manifest = load_json(CASES_PATH)
    content_map = _content_map()

    base_errors = verify_release_state(base_release, base_commitment)
    if base_errors:
        raise ValueError("base release does not verify: " + "; ".join(base_errors))

    case_results: list[dict[str, Any]] = []
    by_class: dict[str, dict[str, Any]] = {}
    undetected: list[str] = []

    for case in cases_manifest["cases"]:
        release, commitment, overrides = apply_case(base_release, base_commitment, case, content_map)
        violations = verify_release_state(
            release,
            commitment,
            canonical_overrides=overrides,
        )
        detected = bool(violations)
        if not detected:
            undetected.append(case["case_id"])

        class_id = case["corruption_class"]
        bucket = by_class.setdefault(class_id, {"injected": 0, "detected": 0})
        bucket["injected"] += 1
        if detected:
            bucket["detected"] += 1

        case_results.append(
            {
                "case_id": case["case_id"],
                "corruption_class": class_id,
                "detected": detected,
                "violations": violations,
            }
        )

    for bucket in by_class.values():
        bucket["rate"] = bucket["detected"] / bucket["injected"]

    injected = len(case_results)
    detected = sum(1 for item in case_results if item["detected"])
    tdr = detected / injected if injected else 0.0

    return {
        "experiment_id": EXPERIMENT_ID,
        "release_id": base_release["release_id"],
        "release_schema_version": base_release["schema_version"],
        "merkle_profile_id": base_release["merkle_profile"],
        "base_merkle_root": base_release["merkle_root"],
        "base_release_json_sha256": base_commitment["release_json_sha256"],
        "case_manifest_id": cases_manifest["case_manifest_id"],
        "case_manifest_file": "eval/release-tamper-cases-v0.1.json",
        "case_manifest_jcs_sha256": jcs_sha256(cases_manifest),
        "frozen_artifacts_mutated": False,
        "verifier": {
            "injected": injected,
            "detected": detected,
            "TDR": tdr,
            "by_class": by_class,
            "undetected": undetected,
        },
        "cases": case_results,
    }


def main() -> int:
    result = evaluate()
    write_json(OUTPUT_PATH, result)
    print(
        json.dumps(
            {
                "TDR": result["verifier"]["TDR"],
                "detected": result["verifier"]["detected"],
                "injected": result["verifier"]["injected"],
                "case_manifest_jcs_sha256": result["case_manifest_jcs_sha256"],
                "output": str(OUTPUT_PATH),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
