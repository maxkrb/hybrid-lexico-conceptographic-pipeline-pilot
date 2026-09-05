#!/usr/bin/env python3
"""Generate the exact deterministic 45-case P1 evidence-corruption manifest."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import rfc8785

from src.minimal_api import resolve_pointer

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "eval/evidence-corruption-profile-v0.1.json"
REGISTRY = ROOT / "data/pilot/pre-release/evidence-registry.json"
HASHES = ROOT / "data/pilot/pre-release/content-hashes.json"
DEFAULT_OUTPUT = ROOT / "eval/evidence-corruption-cases-v0.1.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def flip_hex(value: str) -> str:
    tail = "0" if value[-1] != "0" else "1"
    return value[:-1] + tail


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


def sha256_jcs(value: Any) -> str:
    return hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT)))
    args = parser.parse_args()

    profile = load(PROFILE)
    registry = load(REGISTRY)
    hashes = load(HASHES)

    if profile["release_id"] != registry["release_id"]:
        raise SystemExit("profile release_id differs from Evidence Registry")
    if profile["registry_version"] != registry["registry_version"]:
        raise SystemExit("profile registry_version differs from Evidence Registry")

    records_by_id = {record["evidence_id"]: record for record in registry["records"]}
    manifest_items = {item["entry_id"]: item for item in hashes["entries"]}
    entry_ids = sorted(manifest_items)

    samples: list[dict[str, Any]] = []
    for pinned in profile["samples"]:
        record = records_by_id.get(pinned["evidence_id"])
        if record is None:
            raise SystemExit(f"missing pinned evidence record: {pinned['evidence_id']}")
        if record["entry_id"] != pinned["entry_id"] or record["json_pointer"] != pinned["json_pointer"]:
            raise SystemExit(f"pinned sample no longer matches registry: {pinned['sample_class']}")
        samples.append({
            "sample_class": pinned["sample_class"],
            "entry_id": pinned["entry_id"],
            "json_pointer": pinned["json_pointer"],
            "evidence_id": pinned["evidence_id"],
            "base_record": copy.deepcopy(record),
        })

    cases: list[dict[str, Any]] = []
    canonical_rules = next(
        item["rules"] for item in profile["corruption_classes"]
        if item["id"] == "canonical_value_mutation"
    )

    for corruption in profile["corruption_classes"]:
        kind = corruption["id"]
        for sample in samples:
            record = sample["base_record"]
            mutation: dict[str, Any]

            if kind == "bad_json_pointer":
                mutation = {
                    "target": "evidence_record.json_pointer",
                    "operation": "replace",
                    "before": record["json_pointer"],
                    "after": record["json_pointer"] + corruption["literal"],
                }
            elif kind == "stale_content_sha256":
                mutation = {
                    "target": "evidence_record.content_sha256",
                    "operation": "replace",
                    "before": record["content_sha256"],
                    "after": flip_hex(record["content_sha256"]),
                }
            elif kind == "wrong_entry_id":
                pos = entry_ids.index(record["entry_id"])
                other = entry_ids[(pos + 1) % len(entry_ids)]
                mutation = {
                    "target": "evidence_record.entry_id",
                    "operation": "replace",
                    "before": record["entry_id"],
                    "after": other,
                }
            elif kind == "wrong_release_id":
                mutation = {
                    "target": "evidence_record.release_id",
                    "operation": "replace",
                    "before": record["release_id"],
                    "after": corruption["value"],
                }
            elif kind == "modified_target_sha256":
                mutation = {
                    "target": "evidence_record.target_sha256",
                    "operation": "replace",
                    "before": record["target_sha256"],
                    "after": flip_hex(record["target_sha256"]),
                }
            elif kind == "modified_evidence_id":
                mutation = {
                    "target": "evidence_record.evidence_id",
                    "operation": "replace",
                    "before": record["evidence_id"],
                    "after": "ev1-" + flip_hex(record["evidence_id"][4:]),
                }
            elif kind == "wrong_target_type":
                wrong_type = "number" if record["target_type"] != "number" else "string"
                mutation = {
                    "target": "evidence_record.target_type",
                    "operation": "replace",
                    "before": record["target_type"],
                    "after": wrong_type,
                }
            elif kind == "canonical_value_mutation":
                item = manifest_items[record["entry_id"]]
                entry = load(ROOT / item["canonical_file"])
                value = resolve_pointer(entry, record["json_pointer"])
                changed = mutated_scalar(value)
                mutation = {
                    "target": "canonical_entry.scalar_at_json_pointer",
                    "operation": "mutate_scalar",
                    "entry_id": record["entry_id"],
                    "json_pointer": record["json_pointer"],
                    "before_target_sha256": sha256_jcs(value),
                    "after_target_sha256": sha256_jcs(changed),
                    "rule": canonical_rules,
                }
            elif kind == "deleted_anchor":
                mutation = {
                    "target": "runtime_evidence_indexes",
                    "operation": "delete_anchor",
                    "evidence_id": record["evidence_id"],
                    "entry_id": record["entry_id"],
                    "json_pointer": record["json_pointer"],
                }
            else:
                raise SystemExit(f"unsupported corruption class: {kind}")

            cases.append({
                "case_id": f"EC-{len(cases) + 1:03d}",
                "corruption_class": kind,
                "sample_class": sample["sample_class"],
                "base_evidence_id": record["evidence_id"],
                "base_entry_id": record["entry_id"],
                "base_json_pointer": record["json_pointer"],
                "mutation": mutation,
            })

    expected = profile["case_construction"]["expected_case_count"]
    if len(cases) != expected:
        raise SystemExit(f"case count mismatch: expected {expected}, got {len(cases)}")

    result = {
        "case_manifest_id": "p1-evidence-corruption-cases-v0.1",
        "profile_id": profile["profile_id"],
        "release_id": profile["release_id"],
        "registry_version": profile["registry_version"],
        "generator": "scripts/generate_evidence_corruption_cases.py",
        "construction": profile["case_construction"],
        "samples": samples,
        "cases": cases,
    }
    out = ROOT / args.output
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "case_manifest_id": result["case_manifest_id"],
        "cases": len(cases),
        "output": str(out.relative_to(ROOT)),
    }))


if __name__ == "__main__":
    main()
