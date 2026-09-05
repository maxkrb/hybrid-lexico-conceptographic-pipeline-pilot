#!/usr/bin/env python3
"""Verify the committed P3 release manifest against frozen canonical artifacts."""

from __future__ import annotations

import json
import sys

from src.release_integrity import COMMITMENT_PATH, RELEASE_PATH, load_json, verify_release_state


def main() -> int:
    if not RELEASE_PATH.exists() or not COMMITMENT_PATH.exists():
        print("FAIL: P3 release artifacts are missing; run scripts/build_release.py first", file=sys.stderr)
        return 1

    release = load_json(RELEASE_PATH)
    commitment = load_json(COMMITMENT_PATH)
    errors = verify_release_state(release, commitment)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "verified",
                "release_id": release["release_id"],
                "entry_count": release["entry_count"],
                "merkle_profile": release["merkle_profile"],
                "merkle_root": release["merkle_root"],
                "release_json_sha256": commitment["release_json_sha256"],
                "signature_status": commitment["signature_status"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
