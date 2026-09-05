#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import rfc8785
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data/pilot/canonical"
HASH_MANIFEST = ROOT / "data/pilot/pre-release/content-hashes.json"
RELEASE_RESERVATION = ROOT / "data/pilot/pre-release/release-reservation.json"
EVIDENCE_SCHEMA = ROOT / "spec/evidence-record-v0.1.schema.json"
PROFILE_FILE = ROOT / "spec/publishable-field-profile-v0.1.json"
DEFAULT_OUTPUT = ROOT / "data/pilot/pre-release/evidence-registry.json"
DOMAIN = "hybrid-lexico-conceptographic-pipeline/evidence/v1"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def jcs_bytes(value: Any) -> bytes:
    return rfc8785.dumps(value)


def jcs_sha256(value: Any) -> str:
    return hashlib.sha256(jcs_bytes(value)).hexdigest()


def pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def scalar_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    raise TypeError(f"Evidence target must be scalar, got {type(value).__name__}")


def classify_pointer(pointer: str) -> str:
    if pointer == "/lemma/display":
        return "lemma_display"
    if pointer == "/grammar/pos":
        return "grammar_pos"
    if pointer == "/def_short":
        return "def_short"
    if pointer.startswith("/phrases/") and pointer.endswith("/display"):
        return "phrase_display"
    if pointer.endswith("/definition"):
        return "phrase_definition" if pointer.startswith("/phrases/") else "definition"
    if "/examples/" in pointer and pointer.endswith("/text"):
        return "example_text"
    return "other"


def collect_publishable(entry: dict[str, Any]) -> list[tuple[str, Any]]:
    selected: dict[str, Any] = {}

    def add(pointer: str, value: Any) -> None:
        if value is None:
            return
        scalar_type(value)
        selected[pointer] = value

    add("/lemma/display", entry["lemma"]["display"])
    add("/grammar/pos", entry["grammar"]["pos"])
    add("/def_short", entry["def_short"])

    for i, phrase in enumerate(entry.get("phrases", [])):
        if isinstance(phrase, dict) and "display" in phrase:
            add(f"/phrases/{i}/display", phrase["display"])

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}/{pointer_escape(str(key))}"
                if key == "definition" and (
                    child_path.startswith("/senses/") or child_path.startswith("/phrases/")
                ):
                    if child is not None:
                        add(child_path, child)
                elif key == "text" and "/examples/" in child_path:
                    add(child_path, child)
                walk(child, child_path)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path}/{i}")

    walk(entry, "")
    return sorted(selected.items(), key=lambda item: item[0])


def build_record(
    *,
    release_id: str,
    entry_id: str,
    content_sha256: str,
    json_pointer: str,
    target: Any,
) -> dict[str, Any]:
    seed = {
        "domain": DOMAIN,
        "release_id": release_id,
        "entry_id": entry_id,
        "content_sha256": content_sha256,
        "json_pointer": json_pointer,
    }
    return {
        "schema_version": "evidence-record-v0.1",
        "id_profile": "ev1-jcs-sha256",
        "evidence_id": "ev1-" + jcs_sha256(seed),
        "release_id": release_id,
        "entry_id": entry_id,
        "content_sha256": content_sha256,
        "json_pointer": json_pointer,
        "target_type": scalar_type(target),
        "target_hash_profile": "jcs-sha256",
        "target_sha256": jcs_sha256(target),
    }


def build_registry() -> dict[str, Any]:
    reservation = load_json(RELEASE_RESERVATION)
    hash_manifest = load_json(HASH_MANIFEST)
    profile = load_json(PROFILE_FILE)
    evidence_schema = load_json(EVIDENCE_SCHEMA)
    record_validator = Draft202012Validator(evidence_schema)

    # P1 evidence artifacts are bound to the immutable release identity and remain
    # reproducible after P3 promotes that identity from reserved to released.
    # Any other lifecycle state is rejected rather than silently generating records.
    if reservation["state"] not in {"reserved", "released"}:
        raise SystemExit("release identity must be in state=reserved or state=released for deterministic evidence generation")
    if profile["profile_id"] != "publishable-field-profile-v0.1":
        raise SystemExit("unexpected publishable field profile")
    if reservation["entry_count"] != hash_manifest["entry_count"]:
        raise SystemExit("release reservation entry_count does not match content hash manifest")

    manifest_entries = {item["entry_id"]: item for item in hash_manifest["entries"]}
    records: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    entry_counts: OrderedDict[str, int] = OrderedDict()

    for entry_id in sorted(manifest_entries):
        manifest_item = manifest_entries[entry_id]
        canonical_path = ROOT / manifest_item["canonical_file"]
        entry = load_json(canonical_path)

        if entry["entry_id"] != entry_id:
            raise SystemExit(f"entry_id mismatch in {canonical_path}")
        computed_content_hash = jcs_sha256(entry)
        if computed_content_hash != manifest_item["content_sha256"]:
            raise SystemExit(f"content_sha256 mismatch for {entry_id}")

        entry_records: list[dict[str, Any]] = []
        for pointer, target in collect_publishable(entry):
            record = build_record(
                release_id=reservation["release_id"],
                entry_id=entry_id,
                content_sha256=manifest_item["content_sha256"],
                json_pointer=pointer,
                target=target,
            )
            record_validator.validate(record)
            entry_records.append(record)
            class_counts[classify_pointer(pointer)] += 1

        entry_records.sort(key=lambda r: r["json_pointer"])
        entry_counts[entry_id] = len(entry_records)
        records.extend(entry_records)

    records.sort(key=lambda r: (r["entry_id"], r["json_pointer"]))
    evidence_ids = [r["evidence_id"] for r in records]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise SystemExit("duplicate evidence_id detected")

    registry = {
        "registry_version": "evidence-registry-v0.1",
        "release_id": reservation["release_id"],
        "dataset_id": reservation["dataset_id"],
        "evidence_record_schema": "evidence-record-v0.1",
        "id_profile": "ev1-jcs-sha256",
        "selection_profile": profile["profile_id"],
        "entry_count": len(entry_counts),
        "record_count": len(records),
        "field_class_counts": dict(sorted(class_counts.items())),
        "entry_record_counts": entry_counts,
        "records": records,
    }
    return registry


def render_registry(registry: dict[str, Any]) -> bytes:
    return (json.dumps(registry, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    output = args.output if args.output.is_absolute() else ROOT / args.output
    rendered = render_registry(build_registry())

    if args.check:
        if not output.exists():
            raise SystemExit(f"missing generated registry: {output}")
        if output.read_bytes() != rendered:
            raise SystemExit("evidence registry is stale or non-deterministic; regenerate it")
        registry = json.loads(rendered)
        print(
            f"PASS: deterministic evidence registry; entries={registry['entry_count']}; "
            f"records={registry['record_count']}; release={registry['release_id']}"
        )
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(rendered)
    registry = json.loads(rendered)
    print(
        f"WROTE: {output.relative_to(ROOT)}; entries={registry['entry_count']}; "
        f"records={registry['record_count']}; release={registry['release_id']}"
    )


if __name__ == "__main__":
    main()
