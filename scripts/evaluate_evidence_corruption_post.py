#!/usr/bin/env python3
"""Run the exact versioned v0.1 fault cases against the hardened runtime."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMP = ROOT / "eval/.evidence-corruption-post.tmp.json"
OUTPUT = ROOT / "eval/evidence-corruption-results-posthardening-v0.1.json"


def main() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/evaluate_evidence_corruption.py"),
            "--output",
            str(TEMP.relative_to(ROOT)),
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )
    data = json.loads(TEMP.read_text(encoding="utf-8"))
    data["experiment_id"] = "p1-evidence-corruption-posthardening-v0.1"
    data["baseline_reference"] = "eval/evidence-corruption-results-prehardening-v0.1.json"
    data["runtime_post_hardening"] = data.pop("runtime_current")
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    TEMP.unlink(missing_ok=True)
    print(json.dumps({
        "runtime_post_hardening_EVDR": data["runtime_post_hardening"]["EVDR"],
        "strict_EVDR": data["full_contract_verifier"]["EVDR"],
        "case_manifest_id": data["case_manifest_id"],
        "case_manifest_jcs_sha256": data["case_manifest_jcs_sha256"],
        "output": str(OUTPUT.relative_to(ROOT)),
    }))


if __name__ == "__main__":
    main()
