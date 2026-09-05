#!/usr/bin/env python3
"""Generate the exact deterministic P3 release-tamper case manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.release_integrity import (
    COMMITMENT_PATH,
    CONTENT_HASHES_PATH,
    RELEASE_PATH,
    flip_last_hex,
    jcs_sha256,
    load_json,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "eval" / "release-tamper-profile-v0.1.json"
OUTPUT_PATH = ROOT / "eval" / "release-tamper-cases-v0.1.json"
PROFILE_ID = "p3-release-tamper-profile-v0.1"
CASE_MANIFEST_ID = "p3-release-tamper-cases-v0.1"


def _content_item_map(content_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["entry_id"]: item for item in content_manifest["entries"]}


def _release_entry_map(release: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {item["entry_id"]: item for item in release["entries"]}


def build_case_manifest() -> dict[str, Any]:
    profile = load_json(PROFILE_PATH)
    release = load_json(RELEASE_PATH)
    commitment = load_json(COMMITMENT_PATH)
    content_manifest = load_json(CONTENT_HASHES_PATH)

    if profile.get("profile_id") != PROFILE_ID:
        raise ValueError("unexpected release-tamper profile id")
    if profile.get("release_id") != release.get("release_id"):
        raise ValueError("tamper profile is not bound to the generated release")

    entry_map = _release_entry_map(release)
    content_map = _content_item_map(content_manifest)
    ordered_ids = [item["entry_id"] for item in release["entries"]]
    samples = profile["entry_samples"]
    for entry_id in samples:
        if entry_id not in entry_map or entry_id not in content_map:
            raise ValueError(f"sample entry is not in frozen release: {entry_id}")

    cases: list[dict[str, Any]] = []
    case_number = 1

    def add_case(payload: dict[str, Any]) -> None:
        nonlocal case_number
        cases.append({"case_id": f"RT-{case_number:03d}", **payload})
        case_number += 1

    for corruption in profile["corruption_classes"]:
        corruption_id = corruption["id"]
        if corruption.get("per_entry_sample"):
            for sample_index, entry_id in enumerate(samples):
                release_entry = entry_map[entry_id]

                if corruption_id == "canonical_content_mutation":
                    document = load_json(ROOT / content_map[entry_id]["canonical_file"])
                    pointer = corruption["target_pointer"]
                    if pointer != "/def_short":
                        raise ValueError("v0.1 canonical mutation generator supports /def_short only")
                    before = document["def_short"]
                    after = before + corruption["literal"]
                    mutation = {
                        "target": "canonical_entry.scalar_at_json_pointer",
                        "entry_id": entry_id,
                        "json_pointer": pointer,
                        "operation": corruption["operation"],
                        "literal": corruption["literal"],
                        "before_target_jcs_sha256": jcs_sha256(before),
                        "after_target_jcs_sha256": jcs_sha256(after),
                    }

                elif corruption_id == "release_entry_digest_mutation":
                    before = release_entry["content_sha256"]
                    mutation = {
                        "target": "release.entries.content_sha256",
                        "entry_id": entry_id,
                        "operation": corruption["operation"],
                        "before": before,
                        "after": flip_last_hex(before),
                    }

                elif corruption_id == "release_entry_digest_remap":
                    index = ordered_ids.index(entry_id)
                    source_entry_id = ordered_ids[(index + 1) % len(ordered_ids)]
                    before = release_entry["content_sha256"]
                    after = entry_map[source_entry_id]["content_sha256"]
                    mutation = {
                        "target": "release.entries.content_sha256",
                        "entry_id": entry_id,
                        "operation": corruption["operation"],
                        "before": before,
                        "after": after,
                        "digest_source_entry_id": source_entry_id,
                    }

                elif corruption_id == "release_entry_id_mutation":
                    synthetic_number = int(corruption["synthetic_id_start"]) + sample_index
                    mutation = {
                        "target": "release.entries.entry_id",
                        "entry_id": entry_id,
                        "operation": corruption["operation"],
                        "before": entry_id,
                        "after": f"sum20-hist-ap-{synthetic_number:03d}",
                    }

                elif corruption_id == "release_entry_removal":
                    mutation = {
                        "target": "release.entries",
                        "entry_id": entry_id,
                        "operation": corruption["operation"],
                        "removed_entry": release_entry,
                        "entry_count_before": release["entry_count"],
                        "entry_count_after": release["entry_count"] - 1,
                    }

                else:
                    raise ValueError(f"unsupported per-entry corruption class: {corruption_id}")

                add_case(
                    {
                        "corruption_class": corruption_id,
                        "sample_entry_id": entry_id,
                        "mutation": mutation,
                    }
                )
            continue

        if corruption_id == "release_entry_addition":
            source_id = corruption["digest_source_entry_id"]
            added_entry = {
                "entry_id": corruption["synthetic_entry_id"],
                "content_sha256": entry_map[source_id]["content_sha256"],
            }
            mutation = {
                "target": "release.entries",
                "operation": corruption["operation"],
                "added_entry": added_entry,
                "digest_source_entry_id": source_id,
                "entry_count_before": release["entry_count"],
                "entry_count_after": release["entry_count"] + 1,
            }

        elif corruption_id == "release_entry_reorder":
            first = release["entries"][0]["entry_id"]
            second = release["entries"][1]["entry_id"]
            mutation = {
                "target": "release.entries",
                "operation": corruption["operation"],
                "swap_indices": [0, 1],
                "entry_ids_before": [first, second],
                "entry_ids_after": [second, first],
            }

        elif corruption_id == "merkle_root_mutation":
            before = release["merkle_root"]
            mutation = {
                "target": "release.merkle_root",
                "operation": corruption["operation"],
                "before": before,
                "after": flip_last_hex(before),
            }

        elif corruption_id == "release_id_mutation":
            mutation = {
                "target": "release.release_id",
                "operation": corruption["operation"],
                "before": release["release_id"],
                "after": corruption["value"],
            }

        elif corruption_id == "release_commitment_hash_mutation":
            before = commitment["release_json_sha256"]
            mutation = {
                "target": "commitment.release_json_sha256",
                "operation": corruption["operation"],
                "before": before,
                "after": flip_last_hex(before),
            }

        else:
            raise ValueError(f"unsupported global corruption class: {corruption_id}")

        add_case({"corruption_class": corruption_id, "mutation": mutation})

    expected = profile["case_construction"]["expected_case_count"]
    if len(cases) != expected:
        raise ValueError(f"expected {expected} tamper cases, generated {len(cases)}")

    return {
        "case_manifest_id": CASE_MANIFEST_ID,
        "profile_id": profile["profile_id"],
        "release_id": release["release_id"],
        "release_json_sha256": commitment["release_json_sha256"],
        "merkle_root": release["merkle_root"],
        "generator": "scripts/generate_release_tamper_cases.py",
        "construction": profile["case_construction"],
        "entry_samples": samples,
        "cases": cases,
    }


def main() -> int:
    manifest = build_case_manifest()
    write_json(OUTPUT_PATH, manifest)
    print(
        json.dumps(
            {
                "case_manifest_id": manifest["case_manifest_id"],
                "cases": len(manifest["cases"]),
                "output": str(OUTPUT_PATH),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
