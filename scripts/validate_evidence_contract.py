#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

import rfc8785
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec" / "evidence-record-v0.1.schema.json"
RECORD = ROOT / "data" / "pilot" / "pre-release" / "evidence-example.json"
RESERVATION = ROOT / "data" / "pilot" / "pre-release" / "release-reservation.json"
HASHES = ROOT / "data" / "pilot" / "pre-release" / "content-hashes.json"
DOMAIN = "hybrid-lexico-conceptographic-pipeline/evidence/v1"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_pointer(doc, pointer):
    if not pointer.startswith("/"):
        raise ValueError("P1 evidence pointer must be non-root and start with '/'")
    current = doc
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not token.isdigit():
                raise ValueError(f"non-numeric array index: {token!r}")
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise ValueError("pointer continues below a scalar value")
    return current


def json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    raise ValueError("P1 atomic evidence target must be a JSON scalar")


def sha256_jcs(value):
    return hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def main():
    schema = load(SCHEMA)
    record = load(RECORD)
    reservation = load(RESERVATION)
    hashes = load(HASHES)

    Draft202012Validator(schema).validate(record)

    if record["release_id"] != reservation["release_id"]:
        raise SystemExit("release_id does not match reserved release")

    matches = [x for x in hashes["entries"] if x["entry_id"] == record["entry_id"]]
    if len(matches) != 1:
        raise SystemExit("entry_id must resolve exactly once in content-hashes.json")
    item = matches[0]
    if item["content_sha256"] != record["content_sha256"]:
        raise SystemExit("Evidence Record content_sha256 differs from frozen manifest")

    entry = load(ROOT / item["canonical_file"])
    if sha256_jcs(entry) != record["content_sha256"]:
        raise SystemExit("canonical entry does not reproduce frozen content_sha256")

    target = resolve_pointer(entry, record["json_pointer"])
    if isinstance(target, (dict, list)):
        raise SystemExit("Evidence Record points to a non-atomic JSON target")
    if json_type(target) != record["target_type"]:
        raise SystemExit("target_type mismatch")
    if sha256_jcs(target) != record["target_sha256"]:
        raise SystemExit("target_sha256 mismatch")

    preimage = {
        "domain": DOMAIN,
        "release_id": record["release_id"],
        "entry_id": record["entry_id"],
        "content_sha256": record["content_sha256"],
        "json_pointer": record["json_pointer"],
    }
    expected_id = "ev1-" + hashlib.sha256(rfc8785.dumps(preimage)).hexdigest()
    if expected_id != record["evidence_id"]:
        raise SystemExit("evidence_id mismatch")

    print(
        "PASS: evidence-record-v0.1; release_id reserved; schema valid; "
        "entry content hash verified; JSON Pointer resolved; target hash and evidence_id reproduced."
    )


if __name__ == "__main__":
    main()
