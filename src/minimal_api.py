#!/usr/bin/env python3
"""Minimal evidence-bound HTTP API for the SUM-20 pilot.

The service is deterministic and does not generate linguistic content. Every
returned atomic claim must resolve to an Evidence Record in the frozen P1
registry and satisfy the complete evidence-record integrity contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlparse

import rfc8785

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_INDEX = Path("data/pilot/canonical/index.json")
EVIDENCE_REGISTRY = Path("data/pilot/pre-release/evidence-registry.json")
CONTENT_HASHES = Path("data/pilot/pre-release/content-hashes.json")
RELEASE_RESERVATION = Path("data/pilot/pre-release/release-reservation.json")
EVIDENCE_DOMAIN = "hybrid-lexico-conceptographic-pipeline/evidence/v1"

SUPPORTED_FIELDS = ("lemma", "pos", "definition", "examples")
DEFAULT_FIELDS = ("lemma", "pos", "definition")
EXAMPLE_POINTER_RE = re.compile(r"(?:^|/)examples/[0-9]+/text$")


class ApiError(Exception):
    def __init__(self, status_code: int, reason: str, **details: Any) -> None:
        super().__init__(reason)
        self.status_code = status_code
        self.reason = reason
        self.details = details

    def payload(self, release_id: str) -> dict[str, Any]:
        return {
            "status": "refused" if self.reason == "EVIDENCE_UNAVAILABLE" else "error",
            "reason": self.reason,
            "release_id": release_id,
            **self.details,
        }


def _normalise_lookup(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.strip())
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", without_marks).casefold()


def _escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def resolve_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise KeyError(pointer)
    return current


def iter_scalar_pointers(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from iter_scalar_pointers(child, pointer + "/" + _escape_pointer_token(str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_scalar_pointers(child, pointer + f"/{index}")
    else:
        yield pointer, value


def _sha256_jcs(value: Any) -> str:
    return hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    raise ValueError("non-atomic JSON value")


class EvidenceStore:
    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        index = self._load_json(CANONICAL_INDEX)
        registry = self._load_json(EVIDENCE_REGISTRY)
        reservation = self._load_json(RELEASE_RESERVATION)
        hashes = self._load_json(CONTENT_HASHES)

        self.release_id: str = reservation["release_id"]
        self.dataset_id: str = registry["dataset_id"]
        self.registry_version: str = registry["registry_version"]
        self.entry_count: int = registry["entry_count"]
        self.evidence_record_count: int = registry["record_count"]

        if registry["release_id"] != self.release_id:
            raise ValueError("Evidence Registry release_id differs from reserved release")

        self.content_manifest: dict[str, dict[str, Any]] = {
            item["entry_id"]: item for item in hashes["entries"]
        }
        self.entries_by_id: dict[str, dict[str, Any]] = {}
        self.entry_files: dict[str, str] = {}
        self.lookup_to_entry_id: dict[str, str] = {}

        for item in index["entries"]:
            entry = self._load_json(Path(item["canonical_file"]))
            entry_id = entry["entry_id"]
            manifest_item = self.content_manifest.get(entry_id)
            if manifest_item is None:
                raise ValueError(f"Canonical entry missing from frozen content manifest: {entry_id}")
            if manifest_item["canonical_file"] != item["canonical_file"]:
                raise ValueError(f"Canonical path differs from frozen content manifest: {entry_id}")
            if _sha256_jcs(entry) != manifest_item["content_sha256"]:
                raise ValueError(f"Canonical entry no longer reproduces frozen content hash: {entry_id}")
            self.entries_by_id[entry_id] = entry
            self.entry_files[entry_id] = item["canonical_file"]
            for candidate in (entry_id, entry["lemma"]["search"], entry["lemma"]["display"]):
                self.lookup_to_entry_id[_normalise_lookup(candidate)] = entry_id

        self.evidence_by_id: dict[str, dict[str, Any]] = {}
        self.evidence_by_target: dict[tuple[str, str], dict[str, Any]] = {}
        for record in registry["records"]:
            evidence_id = record["evidence_id"]
            target = (record["entry_id"], record["json_pointer"])
            if evidence_id in self.evidence_by_id or target in self.evidence_by_target:
                raise ValueError(f"Duplicate evidence key: {evidence_id} / {target}")
            self.evidence_by_id[evidence_id] = record
            self.evidence_by_target[target] = record

        if len(self.entries_by_id) != self.entry_count:
            raise ValueError("Evidence registry entry_count does not match canonical index")
        if len(self.evidence_by_id) != self.evidence_record_count:
            raise ValueError("Evidence registry record_count does not match records")

        for evidence_id, record in self.evidence_by_id.items():
            self.verify_record(record, lookup_evidence_id=evidence_id)

    def _load_json(self, relative: Path) -> dict[str, Any]:
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def _integrity_failure(self, record: dict[str, Any], check: str, **details: Any) -> None:
        raise ApiError(500, "EVIDENCE_INTEGRITY_FAILURE", evidence_id=record.get("evidence_id"), integrity_check=check, **details)

    def verify_record(self, record: dict[str, Any], *, lookup_evidence_id: str | None = None, expected_entry_id: str | None = None, expected_pointer: str | None = None) -> Any:
        if lookup_evidence_id is not None and record.get("evidence_id") != lookup_evidence_id:
            self._integrity_failure(record, "lookup_evidence_id_binding")
        if expected_entry_id is not None and record.get("entry_id") != expected_entry_id:
            self._integrity_failure(record, "entry_id_binding", expected_entry_id=expected_entry_id)
        if expected_pointer is not None and record.get("json_pointer") != expected_pointer:
            self._integrity_failure(record, "json_pointer_binding", expected_pointer=expected_pointer)
        if record.get("release_id") != self.release_id:
            self._integrity_failure(record, "release_id")
        entry_id = record.get("entry_id")
        manifest_item = self.content_manifest.get(entry_id)
        if manifest_item is None:
            self._integrity_failure(record, "entry_id_in_frozen_manifest")
        if record.get("content_sha256") != manifest_item["content_sha256"]:
            self._integrity_failure(record, "content_sha256_vs_manifest")
        entry = self.entries_by_id.get(entry_id)
        if entry is None:
            self._integrity_failure(record, "entry_presence")
        if _sha256_jcs(entry) != manifest_item["content_sha256"]:
            self._integrity_failure(record, "canonical_content_sha256")
        try:
            value = resolve_pointer(entry, record["json_pointer"])
        except (KeyError, IndexError, ValueError, TypeError):
            self._integrity_failure(record, "json_pointer_resolution")
            raise AssertionError("unreachable")
        if isinstance(value, (dict, list)):
            self._integrity_failure(record, "atomic_target")
        actual_type = _json_type(value)
        if actual_type != record.get("target_type"):
            self._integrity_failure(record, "target_type", actual_type=actual_type)
        if _sha256_jcs(value) != record.get("target_sha256"):
            self._integrity_failure(record, "target_sha256")
        preimage = {"domain": EVIDENCE_DOMAIN,"release_id": record["release_id"],"entry_id": record["entry_id"],"content_sha256": record["content_sha256"],"json_pointer": record["json_pointer"]}
        expected_evidence_id = "ev1-" + hashlib.sha256(rfc8785.dumps(preimage)).hexdigest()
        if expected_evidence_id != record.get("evidence_id"):
            self._integrity_failure(record, "evidence_id_reproduction")
        return value

    def find_entry(self, identifier: str) -> dict[str, Any]:
        entry_id = self.lookup_to_entry_id.get(_normalise_lookup(identifier))
        if not entry_id:
            raise ApiError(404, "ENTRY_NOT_FOUND", query=identifier)
        return self.entries_by_id[entry_id]

    def evidence_for(self, entry_id: str, pointer: str) -> dict[str, Any]:
        record = self.evidence_by_target.get((entry_id, pointer))
        if not record:
            raise ApiError(422, "EVIDENCE_UNAVAILABLE", entry_id=entry_id, requested_pointer=pointer)
        return record

    def claim(self, entry: dict[str, Any], field: str, pointer: str) -> dict[str, Any]:
        entry_id = entry["entry_id"]
        record = self.evidence_for(entry_id, pointer)
        value = self.verify_record(record, expected_entry_id=entry_id, expected_pointer=pointer)
        return {"field": field,"value": value,"evidence_id": record["evidence_id"],"json_pointer": pointer,"target_sha256": record["target_sha256"]}

    def example_pointers(self, entry: dict[str, Any]) -> list[str]:
        pointers: list[str] = []
        for pointer, value in iter_scalar_pointers(entry):
            if isinstance(value, str) and EXAMPLE_POINTER_RE.search(pointer) and (entry["entry_id"], pointer) in self.evidence_by_target:
                pointers.append(pointer)
        return pointers

    def query_entry(self, identifier: str, fields: Iterable[str] = DEFAULT_FIELDS, example_count: int = 2) -> dict[str, Any]:
        requested = list(dict.fromkeys(fields))
        if not requested:
            raise ApiError(400, "NO_FIELDS_REQUESTED")
        unsupported = [field for field in requested if field not in SUPPORTED_FIELDS]
        if unsupported:
            raise ApiError(400, "UNSUPPORTED_FIELD", requested_fields=unsupported)
        if not 1 <= example_count <= 10:
            raise ApiError(400, "INVALID_EXAMPLE_COUNT", example_count=example_count)
        entry = self.find_entry(identifier)
        claims: list[dict[str, Any]] = []
        pointer_by_field = {"lemma": "/lemma/display","pos": "/grammar/pos","definition": "/def_short"}
        for field in requested:
            if field in pointer_by_field:
                claims.append(self.claim(entry, field, pointer_by_field[field]))
            elif field == "examples":
                pointers = self.example_pointers(entry)
                if len(pointers) < example_count:
                    raise ApiError(422, "EVIDENCE_UNAVAILABLE", entry_id=entry["entry_id"], requested_field="examples", requested_count=example_count, available_count=len(pointers))
                for index, pointer in enumerate(pointers[:example_count]):
                    claims.append(self.claim(entry, f"examples[{index}]", pointer))
        return {"status": "ok","release_id": self.release_id,"dataset_id": self.dataset_id,"entry_id": entry["entry_id"],"canonical_file": self.entry_files[entry["entry_id"]],"claims": claims}

    def resolve_evidence(self, evidence_id: str) -> dict[str, Any]:
        record = self.evidence_by_id.get(evidence_id)
        if not record:
            raise ApiError(404, "EVIDENCE_NOT_FOUND", evidence_id=evidence_id)
        value = self.verify_record(record, lookup_evidence_id=evidence_id)
        return {"status": "ok","verified": True,"release_id": self.release_id,"record": record,"value": value}

    def health(self) -> dict[str, Any]:
        return {"status": "ok","service": "sum20-evidence-bound-pilot-api","release_id": self.release_id,"dataset_id": self.dataset_id,"entry_count": self.entry_count,"evidence_record_count": self.evidence_record_count,"supported_fields": list(SUPPORTED_FIELDS),"integrity_profile": "full-evidence-contract-v0.1"}


def dispatch_get(store: EvidenceStore, raw_path: str) -> tuple[int, dict[str, Any]]:
    parsed = urlparse(raw_path)
    path = parsed.path.rstrip("/") or "/"
    params = parse_qs(parsed.query, keep_blank_values=True)
    try:
        if path == "/v1/health":
            return 200, store.health()
        if path.startswith("/v1/entries/"):
            identifier = unquote(path[len("/v1/entries/"):])
            fields_text = params.get("fields", [",".join(DEFAULT_FIELDS)])[0]
            fields = [item.strip() for item in fields_text.split(",") if item.strip()]
            try:
                example_count = int(params.get("example_count", ["2"])[0])
            except ValueError:
                raise ApiError(400, "INVALID_EXAMPLE_COUNT") from None
            return 200, store.query_entry(identifier, fields, example_count)
        if path.startswith("/v1/evidence/"):
            evidence_id = unquote(path[len("/v1/evidence/"):])
            return 200, store.resolve_evidence(evidence_id)
        raise ApiError(404, "ROUTE_NOT_FOUND", path=path)
    except ApiError as exc:
        return exc.status_code, exc.payload(store.release_id)


def make_handler(store: EvidenceStore):
    class Handler(BaseHTTPRequestHandler):
        server_version = "EvidenceBoundPilotAPI/0.2"
        def _write_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self) -> None:
            status, payload = dispatch_get(store, self.path)
            self._write_json(status, payload)
        def log_message(self, format: str, *args: Any) -> None:
            return
    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--check", action="store_true", help="load frozen data and print health JSON")
    args = parser.parse_args()
    store = EvidenceStore(ROOT)
    if args.check:
        print(json.dumps(store.health(), ensure_ascii=False, indent=2))
        return
    server = ThreadingHTTPServer((args.host, args.port), make_handler(store))
    print(f"Serving {store.release_id} on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
