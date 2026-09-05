#!/usr/bin/env python3
"""Validate the canonical SUM-20 pilot dataset before release hashing.

This validator is intentionally stricter than JSON Schema alone.  It checks
schema conformance, provenance hashes, index consistency, JSON-Pointer
resolution for def_short, and identifier uniqueness.  It does not compute
release content hashes or evidence IDs; those belong to the next P1 stage.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data" / "pilot" / "canonical"
INDEX_PATH = CANONICAL_DIR / "index.json"
SCHEMA_PATH = ROOT / "spec" / "canonical-entry-v0.4.schema.json"
EXPECTED_SCHEMA_VERSION = "lex-entry-v0.4"
EXPECTED_ENTRY_COUNT = 25


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON Pointer: {pointer!r}")
    node = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            try:
                node = node[int(token)]
            except (ValueError, IndexError) as exc:
                raise KeyError(pointer) from exc
        elif isinstance(node, dict):
            if token not in node:
                raise KeyError(pointer)
            node = node[token]
        else:
            raise KeyError(pointer)
    return node


def iter_ids(entry: dict[str, Any]) -> Iterable[tuple[str, str]]:
    yield "entry_id", entry["entry_id"]

    def examples(items: Iterable[dict[str, Any]]) -> Iterable[tuple[str, str]]:
        for item in items:
            yield "example_id", item["example_id"]

    def subsenses(items: Iterable[dict[str, Any]]) -> Iterable[tuple[str, str]]:
        for sub in items:
            yield "sub_sense_id", sub["sub_sense_id"]
            yield from examples(sub.get("examples", []))

    for sense in entry.get("senses", []):
        yield "sense_id", sense["sense_id"]
        yield from examples(sense.get("examples", []))
        yield from subsenses(sense.get("sub_senses", []))

    for phrase in entry.get("phrases", []):
        yield "phrase_id", phrase["phrase_id"]
        yield from examples(phrase.get("examples", []))
        yield from subsenses(phrase.get("sub_senses", []))


def main() -> int:
    errors: list[str] = []

    schema = load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema)
    index = load_json(INDEX_PATH)

    if index.get("raw_entry_count") != EXPECTED_ENTRY_COUNT:
        errors.append(
            f"index raw_entry_count={index.get('raw_entry_count')!r}, expected {EXPECTED_ENTRY_COUNT}"
        )
    if index.get("canonicalized_entry_count") != EXPECTED_ENTRY_COUNT:
        errors.append(
            "index canonicalized_entry_count="
            f"{index.get('canonicalized_entry_count')!r}, expected {EXPECTED_ENTRY_COUNT}"
        )
    if index.get("target_schema_version") != EXPECTED_SCHEMA_VERSION:
        errors.append("index target_schema_version does not match v0.4")
    if index.get("schema_versions_present") != [EXPECTED_SCHEMA_VERSION]:
        errors.append("index schema_versions_present must contain only lex-entry-v0.4")
    if index.get("remaining_entry_ids"):
        errors.append("index remaining_entry_ids must be empty")
    if index.get("pre_release_schema_migration_required"):
        errors.append("index pre_release_schema_migration_required must be empty")

    index_entries = index.get("entries", [])
    if len(index_entries) != EXPECTED_ENTRY_COUNT:
        errors.append(
            f"index contains {len(index_entries)} entries, expected {EXPECTED_ENTRY_COUNT}"
        )

    disk_files = sorted(CANONICAL_DIR.glob("[0-9][0-9][0-9]-*.json"))
    if len(disk_files) != EXPECTED_ENTRY_COUNT:
        errors.append(
            f"canonical directory contains {len(disk_files)} numbered JSON entries, "
            f"expected {EXPECTED_ENTRY_COUNT}"
        )

    listed_paths = [ROOT / item["canonical_file"] for item in index_entries]
    if len(set(listed_paths)) != len(listed_paths):
        errors.append("duplicate canonical_file path in index")
    if set(disk_files) != set(listed_paths):
        missing = sorted(str(p.relative_to(ROOT)) for p in set(listed_paths) - set(disk_files))
        extra = sorted(str(p.relative_to(ROOT)) for p in set(disk_files) - set(listed_paths))
        if missing:
            errors.append(f"indexed canonical files missing from disk: {missing}")
        if extra:
            errors.append(f"canonical files not listed in index: {extra}")

    all_ids: dict[str, str] = {}
    entry_ids: set[str] = set()

    for item in index_entries:
        canonical_path = ROOT / item["canonical_file"]
        raw_path_from_index = ROOT / item["raw_file"]
        if not canonical_path.is_file():
            errors.append(f"missing canonical file: {item['canonical_file']}")
            continue

        try:
            entry = load_json(canonical_path)
        except Exception as exc:  # pragma: no cover - reported in CI
            errors.append(f"cannot parse {item['canonical_file']}: {exc}")
            continue

        schema_errors = sorted(validator.iter_errors(entry), key=lambda e: list(e.path))
        for err in schema_errors:
            location = "/" + "/".join(str(part) for part in err.path)
            errors.append(f"schema {item['canonical_file']} {location}: {err.message}")

        entry_id = entry.get("entry_id")
        if entry_id != item.get("entry_id"):
            errors.append(
                f"entry_id mismatch for {item['canonical_file']}: "
                f"file={entry_id!r}, index={item.get('entry_id')!r}"
            )
        if entry_id in entry_ids:
            errors.append(f"duplicate entry_id: {entry_id}")
        entry_ids.add(entry_id)

        if entry.get("schema_version") != EXPECTED_SCHEMA_VERSION:
            errors.append(f"{item['canonical_file']} is not lex-entry-v0.4")
        if item.get("schema_version") != EXPECTED_SCHEMA_VERSION:
            errors.append(f"index marks {entry_id} as non-v0.4")

        source = entry.get("source", {})
        raw_path = ROOT / source.get("raw_path", "")
        if raw_path != raw_path_from_index:
            errors.append(
                f"raw path mismatch for {entry_id}: "
                f"canonical={source.get('raw_path')!r}, index={item.get('raw_file')!r}"
            )
        if not raw_path.is_file():
            errors.append(f"missing raw file for {entry_id}: {source.get('raw_path')!r}")
        else:
            actual_raw_hash = sha256_file(raw_path)
            if actual_raw_hash != source.get("raw_sha256"):
                errors.append(
                    f"raw SHA-256 mismatch for {entry_id}: "
                    f"expected {source.get('raw_sha256')}, got {actual_raw_hash}"
                )

        pointer = entry.get("def_short_source_pointer")
        try:
            resolved = resolve_json_pointer(entry, pointer)
        except Exception as exc:
            errors.append(f"cannot resolve def_short_source_pointer for {entry_id}: {exc}")
        else:
            if resolved != entry.get("def_short"):
                errors.append(
                    f"def_short mismatch for {entry_id}: pointer {pointer!r} resolves to different text"
                )

        for kind, identifier in iter_ids(entry):
            prior = all_ids.get(identifier)
            location = f"{item['canonical_file']}:{kind}"
            if prior is not None:
                errors.append(f"duplicate identifier {identifier!r}: {prior} and {location}")
            else:
                all_ids[identifier] = location

    if len(entry_ids) != EXPECTED_ENTRY_COUNT:
        errors.append(f"unique entry_id count={len(entry_ids)}, expected {EXPECTED_ENTRY_COUNT}")

    if errors:
        print(f"FAIL: {len(errors)} validation error(s)", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "PASS: 25 entries; schema=lex-entry-v0.4; "
        "raw SHA-256 provenance verified; index consistent; "
        "def_short pointers resolved; identifiers unique."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
