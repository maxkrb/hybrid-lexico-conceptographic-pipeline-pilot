#!/usr/bin/env python3
"""Build the deterministic P3 release manifest and external release commitment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.release_integrity import (
    COMMITMENT_PATH,
    RELEASE_PATH,
    build_release_documents,
    verify_release_state,
    write_json,
)


def serialized(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare generated documents with committed release artifacts")
    args = parser.parse_args()

    release, commitment = build_release_documents()
    errors = verify_release_state(release, commitment)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    if args.check:
        if not RELEASE_PATH.exists() or not COMMITMENT_PATH.exists():
            print("FAIL: committed release artifacts do not exist", file=sys.stderr)
            return 1
        if RELEASE_PATH.read_text(encoding="utf-8") != serialized(release):
            print("FAIL: release.json is not reproducible", file=sys.stderr)
            return 1
        if COMMITMENT_PATH.read_text(encoding="utf-8") != serialized(commitment):
            print("FAIL: release-commitment.json is not reproducible", file=sys.stderr)
            return 1
        print(
            "PASS: release artifacts reproduce exactly; "
            f"merkle_root={release['merkle_root']} release_json_sha256={commitment['release_json_sha256']}"
        )
        return 0

    write_json(RELEASE_PATH, release)
    write_json(COMMITMENT_PATH, commitment)
    print(
        json.dumps(
            {
                "release_id": release["release_id"],
                "entry_count": release["entry_count"],
                "merkle_root": release["merkle_root"],
                "release_json_sha256": commitment["release_json_sha256"],
                "signature_status": commitment["signature_status"],
                "release_file": str(RELEASE_PATH),
                "commitment_file": str(COMMITMENT_PATH),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
