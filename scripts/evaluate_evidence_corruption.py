#!/usr/bin/env python3
"""Evaluate the versioned 45-case evidence-corruption manifest."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import rfc8785

from src.minimal_api import ApiError, EvidenceStore, resolve_pointer

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "eval/evidence-corruption-cases-v0.1.json"
HASHES = ROOT / "data/pilot/pre-release/content-hashes.json"
RESERVATION = ROOT / "data/pilot/pre-release/release-reservation.json"
DOMAIN = "hybrid-lexico-conceptographic-pipeline/evidence/v1"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_jcs(value: Any) -> str:
    return hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    raise ValueError("non-atomic target")


def set_pointer(document: Any, pointer: str, new_value: Any) -> None:
    tokens = pointer[1:].split("/")
    current = document
    for raw in tokens[:-1]:
        token = raw.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    final = tokens[-1].replace("~1", "/").replace("~0", "~")
    if isinstance(current, list):
        current[int(final)] = new_value
    else:
        current[final] = new_value


def mutated_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return value + " [TAMPERED]"
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value + 1
    if value is None:
        return "TAMPERED"
    raise ValueError("target is not scalar")


def strict_verify(record: dict[str, Any], entries: dict[str, dict[str, Any]], manifest: dict[str, dict[str, Any]], expected_release_id: str) -> None:
    if record["release_id"] != expected_release_id:
        raise ValueError("RELEASE_ID_MISMATCH")
    item = manifest.get(record["entry_id"])
    if item is None:
        raise ValueError("ENTRY_ID_NOT_IN_FROZEN_MANIFEST")
    if record["content_sha256"] != item["content_sha256"]:
        raise ValueError("CONTENT_SHA256_MISMATCH")
    entry = entries[record["entry_id"]]
    if sha256_jcs(entry) != item["content_sha256"]:
        raise ValueError("CANONICAL_CONTENT_HASH_MISMATCH")
    target = resolve_pointer(entry, record["json_pointer"])
    if isinstance(target, (dict, list)):
        raise ValueError("NON_ATOMIC_TARGET")
    if json_type(target) != record["target_type"]:
        raise ValueError("TARGET_TYPE_MISMATCH")
    if sha256_jcs(target) != record["target_sha256"]:
        raise ValueError("TARGET_SHA256_MISMATCH")
    preimage = {
        "domain": DOMAIN,
        "release_id": record["release_id"],
        "entry_id": record["entry_id"],
        "content_sha256": record["content_sha256"],
        "json_pointer": record["json_pointer"],
    }
    expected_id = "ev1-" + hashlib.sha256(rfc8785.dumps(preimage)).hexdigest()
    if expected_id != record["evidence_id"]:
        raise ValueError("EVIDENCE_ID_MISMATCH")


def apply_case(case: dict[str, Any], record: dict[str, Any], entries: dict[str, dict[str, Any]]) -> None:
    mutation = case["mutation"]
    operation = mutation["operation"]

    if operation == "replace":
        field = mutation["target"].split(".")[-1]
        if record.get(field) != mutation["before"]:
            raise ValueError(f"case base mismatch for {case['case_id']}: {field}")
        record[field] = mutation["after"]
        return

    if operation == "mutate_scalar":
        entry = entries[mutation["entry_id"]]
        value = resolve_pointer(entry, mutation["json_pointer"])
        if sha256_jcs(value) != mutation["before_target_sha256"]:
            raise ValueError(f"canonical base mismatch for {case['case_id']}")
        changed = mutated_scalar(value)
        if sha256_jcs(changed) != mutation["after_target_sha256"]:
            raise ValueError(f"canonical mutation mismatch for {case['case_id']}")
        set_pointer(entry, mutation["json_pointer"], changed)
        return

    if operation == "delete_anchor":
        return

    raise ValueError(f"unsupported case operation: {operation}")


def runtime_trial(case: dict[str, Any], base_record: dict[str, Any]) -> dict[str, Any]:
    store = EvidenceStore(ROOT)
    original_id = case["base_evidence_id"]
    record = store.evidence_by_id.get(original_id)
    if record != base_record:
        raise ValueError(f"runtime base record differs from case manifest: {case['case_id']}")

    if case["mutation"]["operation"] == "delete_anchor":
        store.evidence_by_id.pop(original_id, None)
        store.evidence_by_target.pop((case["base_entry_id"], case["base_json_pointer"]), None)
    else:
        apply_case(case, record, store.entries_by_id)

    try:
        store.resolve_evidence(original_id)
        return {"detected": False, "reason": "RUNTIME_ACCEPTED_CORRUPTION"}
    except ApiError as exc:
        return {"detected": True, "reason": exc.reason}
    except Exception as exc:
        return {"detected": True, "reason": type(exc).__name__}


def strict_trial(case: dict[str, Any], base_record: dict[str, Any], clean_entries: dict[str, dict[str, Any]], manifest: dict[str, dict[str, Any]], release_id: str) -> dict[str, Any]:
    if case["mutation"]["operation"] == "delete_anchor":
        return {"detected": True, "reason": "MISSING_EVIDENCE_RECORD"}

    record = copy.deepcopy(base_record)
    entries = copy.deepcopy(clean_entries)
    apply_case(case, record, entries)
    try:
        strict_verify(record, entries, manifest, release_id)
        return {"detected": False, "reason": "STRICT_VERIFIER_ACCEPTED_CORRUPTION"}
    except Exception as exc:
        return {"detected": True, "reason": str(exc) or type(exc).__name__}


def summarise(trials: list[dict[str, Any]], class_order: list[str]) -> dict[str, Any]:
    by_class: dict[str, dict[str, Any]] = {}
    for kind in class_order:
        rows = [x for x in trials if x["corruption_class"] == kind]
        detected = sum(1 for x in rows if x["detected"])
        by_class[kind] = {"injected": len(rows), "detected": detected, "rate": detected / len(rows)}
    detected_total = sum(1 for x in trials if x["detected"])
    return {
        "injected": len(trials),
        "detected": detected_total,
        "EVDR": detected_total / len(trials),
        "by_class": by_class,
        "undetected": [x for x in trials if not x["detected"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="eval/evidence-corruption-results-current-v0.1.json")
    args = parser.parse_args()

    case_manifest = load(CASES)
    hashes = load(HASHES)
    reservation = load(RESERVATION)
    if case_manifest["release_id"] != reservation["release_id"]:
        raise SystemExit("case manifest release differs from reserved release")

    manifest = {x["entry_id"]: x for x in hashes["entries"]}
    clean_entries = {entry_id: load(ROOT / item["canonical_file"]) for entry_id, item in manifest.items()}
    base_records = {sample["evidence_id"]: sample["base_record"] for sample in case_manifest["samples"]}

    clean_store = EvidenceStore(ROOT)
    for evidence_id, base_record in base_records.items():
        if clean_store.evidence_by_id.get(evidence_id) != base_record:
            raise SystemExit(f"case manifest base record is stale: {evidence_id}")
        clean_store.resolve_evidence(evidence_id)
        strict_verify(base_record, clean_entries, manifest, reservation["release_id"])

    class_order = list(dict.fromkeys(case["corruption_class"] for case in case_manifest["cases"]))
    runtime_trials: list[dict[str, Any]] = []
    strict_trials: list[dict[str, Any]] = []

    for case in case_manifest["cases"]:
        base_record = base_records[case["base_evidence_id"]]
        rt = runtime_trial(case, base_record)
        runtime_trials.append({
            "case_id": case["case_id"],
            "corruption_class": case["corruption_class"],
            "sample_class": case["sample_class"],
            "entry_id": case["base_entry_id"],
            "json_pointer": case["base_json_pointer"],
            **rt,
        })
        st = strict_trial(case, base_record, clean_entries, manifest, reservation["release_id"])
        strict_trials.append({
            "case_id": case["case_id"],
            "corruption_class": case["corruption_class"],
            "sample_class": case["sample_class"],
            "entry_id": case["base_entry_id"],
            "json_pointer": case["base_json_pointer"],
            **st,
        })

    result = {
        "experiment_id": "p1-evidence-corruption-current-v0.1",
        "release_id": reservation["release_id"],
        "corruption_profile_id": case_manifest["profile_id"],
        "case_manifest_id": case_manifest["case_manifest_id"],
        "case_manifest_file": str(CASES.relative_to(ROOT)),
        "case_manifest_jcs_sha256": sha256_jcs(case_manifest),
        "profile": {
            "total_injections": len(case_manifest["cases"]),
            "corruption_classes": class_order,
            "sample_classes": [sample["sample_class"] for sample in case_manifest["samples"]],
            "frozen_artifacts_mutated": False,
            "method": "in-memory application of exact versioned case descriptors",
        },
        "runtime_current": summarise(runtime_trials, class_order),
        "full_contract_verifier": summarise(strict_trials, class_order),
    }

    out = ROOT / args.output
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "runtime_EVDR": result["runtime_current"]["EVDR"],
        "strict_EVDR": result["full_contract_verifier"]["EVDR"],
        "case_manifest_jcs_sha256": result["case_manifest_jcs_sha256"],
        "output": str(out.relative_to(ROOT)),
    }))


if __name__ == "__main__":
    main()
