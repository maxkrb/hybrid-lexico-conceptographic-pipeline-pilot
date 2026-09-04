"""Deterministic P3 release construction and integrity verification."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema
import rfc8785

ROOT = Path(__file__).resolve().parents[1]
CONTENT_HASHES_PATH = ROOT / "data" / "pilot" / "pre-release" / "content-hashes.json"
RESERVATION_PATH = ROOT / "data" / "pilot" / "pre-release" / "release-reservation.json"
MERKLE_PROFILE_PATH = ROOT / "spec" / "merkle-profile-v0.1.json"
RELEASE_SCHEMA_PATH = ROOT / "spec" / "release-v0.1.schema.json"
COMMITMENT_SCHEMA_PATH = ROOT / "spec" / "release-commitment-v0.1.schema.json"
RELEASE_PATH = ROOT / "data" / "pilot" / "release" / "release.json"
COMMITMENT_PATH = ROOT / "data" / "pilot" / "release" / "release-commitment.json"

RELEASE_SCHEMA_VERSION = "release-v0.1"
COMMITMENT_VERSION = "release-commitment-v0.1"
MERKLE_PROFILE_ID = "merkle-profile-v0.1"
CANONICALIZATION = "RFC8785-JCS"
HASH_ALGORITHM = "SHA-256"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def jcs_bytes(document: Any) -> bytes:
    encoded = rfc8785.dumps(document)
    if not isinstance(encoded, bytes):
        raise TypeError("rfc8785.dumps() must return bytes")
    return encoded


def jcs_sha256(document: Any) -> str:
    return hashlib.sha256(jcs_bytes(document)).hexdigest()


def flip_last_hex(value: str) -> str:
    if not value:
        raise ValueError("cannot mutate empty hexadecimal value")
    last = value[-1]
    replacement = "0" if last != "0" else "1"
    return value[:-1] + replacement


def load_merkle_profile(root: Path = ROOT) -> dict[str, Any]:
    profile = load_json(root / "spec" / "merkle-profile-v0.1.json")
    if profile.get("profile_id") != MERKLE_PROFILE_ID:
        raise ValueError("unexpected Merkle profile id")
    if profile.get("hash_algorithm") != HASH_ALGORITHM:
        raise ValueError("unsupported Merkle hash algorithm")
    if profile.get("entry_order") != "ascending UTF-8 byte order of entry_id":
        raise ValueError("unsupported Merkle entry ordering")
    if profile.get("odd_node_rule") != "duplicate_last":
        raise ValueError("unsupported Merkle odd-node rule")
    if profile.get("leaf", {}).get("encoding") != CANONICALIZATION:
        raise ValueError("unsupported Merkle leaf encoding")
    if profile.get("internal_node", {}).get("encoding") != CANONICALIZATION:
        raise ValueError("unsupported Merkle node encoding")
    return profile


def entry_sort_key(entry: dict[str, str]) -> bytes:
    return entry["entry_id"].encode("utf-8")


def merkle_leaf(entry: dict[str, str], profile: dict[str, Any]) -> str:
    preimage = {
        "domain": profile["leaf"]["domain"],
        "entry_id": entry["entry_id"],
        "content_sha256": entry["content_sha256"],
    }
    return jcs_sha256(preimage)


def merkle_node(left_sha256: str, right_sha256: str, profile: dict[str, Any]) -> str:
    preimage = {
        "domain": profile["internal_node"]["domain"],
        "left_sha256": left_sha256,
        "right_sha256": right_sha256,
    }
    return jcs_sha256(preimage)


def compute_merkle_root(entries: list[dict[str, str]], profile: dict[str, Any]) -> str:
    if not entries:
        raise ValueError("cannot build a Merkle root for an empty release")
    level = [merkle_leaf(entry, profile) for entry in entries]
    while len(level) > 1:
        next_level: list[str] = []
        for index in range(0, len(level), 2):
            left = level[index]
            right = level[index + 1] if index + 1 < len(level) else left
            next_level.append(merkle_node(left, right, profile))
        level = next_level
    return level[0]


def expected_release_entries(content_manifest: dict[str, Any]) -> list[dict[str, str]]:
    entries = [
        {
            "entry_id": item["entry_id"],
            "content_sha256": item["content_sha256"],
        }
        for item in content_manifest["entries"]
    ]
    return sorted(entries, key=entry_sort_key)


def build_release_documents(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    content_manifest = load_json(root / "data" / "pilot" / "pre-release" / "content-hashes.json")
    reservation = load_json(root / "data" / "pilot" / "pre-release" / "release-reservation.json")
    profile = load_merkle_profile(root)

    if content_manifest.get("entry_count") != reservation.get("entry_count"):
        raise ValueError("reservation and content-hash manifest disagree on entry count")
    if content_manifest.get("dataset_id") != reservation.get("dataset_id"):
        raise ValueError("reservation and content-hash manifest disagree on dataset id")
    if content_manifest.get("schema_version") != reservation.get("entry_schema_version"):
        raise ValueError("reservation and content-hash manifest disagree on entry schema")
    if content_manifest.get("canonicalization") != CANONICALIZATION:
        raise ValueError("content-hash manifest uses unexpected canonicalization")
    if content_manifest.get("hash_algorithm") != HASH_ALGORITHM:
        raise ValueError("content-hash manifest uses unexpected hash algorithm")

    entries = expected_release_entries(content_manifest)
    merkle_root = compute_merkle_root(entries, profile)

    release = {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "release_id": reservation["release_id"],
        "dataset_id": reservation["dataset_id"],
        "release_sequence": reservation["release_sequence"],
        "entry_schema_version": reservation["entry_schema_version"],
        "canonicalization": CANONICALIZATION,
        "hash_algorithm": HASH_ALGORITHM,
        "entry_count": len(entries),
        "content_hash_manifest": "data/pilot/pre-release/content-hashes.json",
        "merkle_profile": profile["profile_id"],
        "entries": entries,
        "merkle_root": merkle_root,
    }

    commitment = {
        "commitment_version": COMMITMENT_VERSION,
        "release_id": release["release_id"],
        "release_json": "data/pilot/release/release.json",
        "canonicalization": CANONICALIZATION,
        "hash_algorithm": HASH_ALGORITHM,
        "release_json_sha256": jcs_sha256(release),
        "merkle_root": merkle_root,
        "signature_status": "not_implemented",
    }
    return release, commitment


def _schema_error_messages(instance: Any, schema: dict[str, Any], label: str) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{label} schema: {error.message}" for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path))]


def verify_release_state(
    release: dict[str, Any],
    commitment: dict[str, Any],
    *,
    root: Path = ROOT,
    canonical_overrides: dict[str, Any] | None = None,
) -> list[str]:
    """Return a list of integrity violations; an empty list means verified."""
    errors: list[str] = []
    overrides = canonical_overrides or {}

    release_schema = load_json(root / "spec" / "release-v0.1.schema.json")
    commitment_schema = load_json(root / "spec" / "release-commitment-v0.1.schema.json")
    errors.extend(_schema_error_messages(release, release_schema, "release"))
    errors.extend(_schema_error_messages(commitment, commitment_schema, "commitment"))

    reservation = load_json(root / "data" / "pilot" / "pre-release" / "release-reservation.json")
    content_manifest = load_json(root / "data" / "pilot" / "pre-release" / "content-hashes.json")
    profile = load_merkle_profile(root)
    expected_entries = expected_release_entries(content_manifest)

    if release.get("release_id") != reservation.get("release_id"):
        errors.append("release_id does not match frozen release reservation")
    if release.get("dataset_id") != reservation.get("dataset_id"):
        errors.append("dataset_id does not match frozen release reservation")
    if release.get("release_sequence") != reservation.get("release_sequence"):
        errors.append("release_sequence does not match frozen release reservation")
    if release.get("entry_schema_version") != reservation.get("entry_schema_version"):
        errors.append("entry_schema_version does not match frozen release reservation")
    if release.get("entry_count") != len(release.get("entries", [])):
        errors.append("release entry_count does not equal the number of manifest entries")
    if release.get("entry_count") != content_manifest.get("entry_count"):
        errors.append("release entry_count does not match frozen content manifest")
    if release.get("merkle_profile") != profile.get("profile_id"):
        errors.append("release Merkle profile does not match frozen profile")

    release_entries = release.get("entries", [])
    if isinstance(release_entries, list):
        try:
            sorted_entries = sorted(release_entries, key=entry_sort_key)
            if release_entries != sorted_entries:
                errors.append("release entries are not in canonical entry_id order")
        except Exception as exc:  # malformed test inputs should be detected, not crash verifier
            errors.append(f"release entry ordering cannot be evaluated: {exc}")
        if release_entries != expected_entries:
            errors.append("release entry_id/content_sha256 mapping differs from frozen content manifest")

    # Recompute each canonical entry hash against the frozen pre-release manifest.
    for item in content_manifest.get("entries", []):
        entry_id = item["entry_id"]
        if entry_id in overrides:
            document = overrides[entry_id]
        else:
            document = load_json(root / item["canonical_file"])
        actual = jcs_sha256(document)
        if actual != item["content_sha256"]:
            errors.append(f"canonical content hash mismatch for {entry_id}")

    try:
        recomputed_root = compute_merkle_root(release_entries, profile)
        if release.get("merkle_root") != recomputed_root:
            errors.append("release merkle_root does not reproduce from manifest entries")
    except Exception as exc:
        errors.append(f"Merkle root cannot be recomputed: {exc}")

    if commitment.get("release_id") != release.get("release_id"):
        errors.append("commitment release_id does not match release manifest")
    if commitment.get("merkle_root") != release.get("merkle_root"):
        errors.append("commitment merkle_root does not match release manifest")
    if commitment.get("release_json_sha256") != jcs_sha256(release):
        errors.append("release_json_sha256 does not match RFC8785-JCS release manifest")
    if commitment.get("signature_status") != "not_implemented":
        errors.append("unexpected signature status for unsigned P3 pilot")

    return errors


def verified_release_documents(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    release = load_json(root / "data" / "pilot" / "release" / "release.json")
    commitment = load_json(root / "data" / "pilot" / "release" / "release-commitment.json")
    errors = verify_release_state(release, commitment, root=root)
    if errors:
        raise ValueError("; ".join(errors))
    return release, commitment


def deep_copy_documents(release: dict[str, Any], commitment: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    return deepcopy(release), deepcopy(commitment)
