#!/usr/bin/env python3
"""Build deterministic SHA-256 commitments for validated canonical entries.

Entry bytes are produced with RFC 8785 JSON Canonicalization Scheme (JCS).
The resulting content hashes are intentionally stored outside the entry JSON,
so the committed object does not contain its own digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import rfc8785

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data" / "pilot" / "canonical"
INDEX_PATH = CANONICAL_DIR / "index.json"
EXPECTED_SCHEMA_VERSION = "lex-entry-v0.4"
EXPECTED_ENTRY_COUNT = 25
CANONICALIZATION = "RFC8785-JCS"
HASH_ALGORITHM = "SHA-256"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def jcs_bytes(document: Any) -> bytes:
    encoded = rfc8785.dumps(document)
    if not isinstance(encoded, bytes):
        raise TypeError("rfc8785.dumps() must return bytes")
    return encoded


def entry_hash(document: Any) -> str:
    return hashlib.sha256(jcs_bytes(document)).hexdigest()


def build_manifest() -> dict[str, Any]:
    index = load_json(INDEX_PATH)
    if index.get("target_schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError("canonical index is not frozen on lex-entry-v0.4")
    entries = index.get("entries", [])
    if len(entries) != EXPECTED_ENTRY_COUNT:
        raise ValueError(f"expected {EXPECTED_ENTRY_COUNT} indexed entries, got {len(entries)}")

    output_entries: list[dict[str, str]] = []
    for item in sorted(entries, key=lambda row: row["entry_id"]):
        path = ROOT / item["canonical_file"]
        document = load_json(path)
        if document.get("schema_version") != EXPECTED_SCHEMA_VERSION:
            raise ValueError(f"{item['canonical_file']} is not {EXPECTED_SCHEMA_VERSION}")
        if document.get("entry_id") != item["entry_id"]:
            raise ValueError(f"entry_id mismatch in {item['canonical_file']}")
        output_entries.append(
            {
                "entry_id": item["entry_id"],
                "canonical_file": item["canonical_file"],
                "content_sha256": entry_hash(document),
            }
        )

    return {
        "dataset_id": index["dataset_id"],
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "canonicalization": CANONICALIZATION,
        "hash_algorithm": HASH_ALGORITHM,
        "entry_count": len(output_entries),
        "entries": output_entries,
    }


def manifest_text(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--output", type=Path, help="write generated manifest to this path")
    group.add_argument("--check", type=Path, help="compare generated manifest with an existing file")
    group.add_argument("--stdout", action="store_true", help="print generated manifest (default)")
    args = parser.parse_args()

    manifest = build_manifest()
    text = manifest_text(manifest)

    if args.check:
        expected = args.check.read_text(encoding="utf-8")
        if expected != text:
            print(f"FAIL: {args.check} is not reproducible from canonical entries", file=sys.stderr)
            return 1
        print(
            f"PASS: {len(manifest['entries'])} RFC8785-JCS entry commitments match {args.check}"
        )
        return 0

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"WROTE: {args.output} ({len(manifest['entries'])} entry commitments)")
        return 0

    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
