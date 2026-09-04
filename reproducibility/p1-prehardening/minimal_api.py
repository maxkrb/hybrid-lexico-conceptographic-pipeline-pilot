#!/usr/bin/env python3
"""Minimal evidence-bound HTTP API for the SUM-20 pilot.

The service is deliberately deterministic: it does not generate linguistic content.
Every returned atomic claim must resolve to an Evidence Record in the frozen
P1 registry for the reserved release.
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
    """Case-fold and remove combining marks so АБАК matches АБА́К."""
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
            child_pointer = pointer + "/" + _escape_pointer_token(str(key))
            yield from iter_scalar_pointers(child, child_pointer)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_scalar_pointers(child, pointer + f"/{index}")
    else:
        yield pointer, value


def _target_sha256(value: Any) -> str:
    return hashlib.sha256(rfc8785.dumps(value)).hexdigest()


class EvidenceStore:
    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        index = self._load_json(CANONICAL_INDEX)
        registry = self._load_json(EVIDENCE_REGISTRY)

        self.release_id: str = registry["release_id"]
        self.dataset_id: str = registry["dataset_id"]
        self.registry_version: str = registry["registry_version"]
        self.entry_count: int = registry["entry_count"]
        self.evidence_record_count: int = registry["record_count"]

        self.entries_by_id: dict[str, dict[str, Any]] = {}
        self.entry_files: dict[str, str] = {}
        self.lookup_to_entry_id: dict[str, str] = {}

        for item in index["entries"]:
            entry = self._load_json(Path(item["canonical_file"]))
            entry_id = entry["entry_id"]
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

    def _load_json(self, relative: Path) -> dict[str, Any]:
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def find_entry(self, identifier: str) -> dict[str, Any]:
        entry_id = self.lookup_to_entry_id.get(_normalise_lookup(identifier))
        if not entry_id:
            raise ApiError(404, "ENTRY_NOT_FOUND", query=identifier)
        return self.entries_by_id[entry_id]

    def evidence_for(self, entry_id: str, pointer: str) -> dict[str, Any]:
        record = self.evidence_by_target.get((entry_id, pointer))
        if not record:
            raise ApiError(
                422,
                "EVIDENCE_UNAVAILABLE",
                entry_id=entry_id,
                requested_pointer=pointer,
            )
        return record

    def claim(self, entry: dict[str, Any], field: str, pointer: str) -> dict[str, Any]:
        entry_id = entry["entry_id"]
        try:
            value = resolve_pointer(entry, pointer)
        except (KeyError, IndexError, ValueError):
            raise ApiError(
                422,
                "EVIDENCE_UNAVAILABLE",
                entry_id=entry_id,
                requested_field=field,
                requested_pointer=pointer,
            ) from None
        record = self.evidence_for(entry_id, pointer)
        if _target_sha256(value) != record["target_sha256"]:
            raise ApiError(
                500,
                "EVIDENCE_INTEGRITY_FAILURE",
                entry_id=entry_id,
                evidence_id=record["evidence_id"],
            )
        return {
            "field": field,
            "value": value,
            "evidence_id": record["evidence_id"],
            "json_pointer": pointer,
            "target_sha256": record["target_sha256"],
        }

    def example_pointers(self, entry: dict[str, Any]) -> list[str]:
        pointers: list[str] = []
        for pointer, value in iter_scalar_pointers(entry):
            if isinstance(value, str) and EXAMPLE_POINTER_RE.search(pointer):
                if (entry["entry_id"], pointer) in self.evidence_by_target:
                    pointers.append(pointer)
        return pointers

    def query_entry(
        self,
        identifier: str,
        fields: Iterable[str] = DEFAULT_FIELDS,
        example_count: int = 2,
    ) -> dict[str, Any]:
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
        pointer_by_field = {
            "lemma": "/lemma/display",
            "pos": "/grammar/pos",
            "definition": "/def_short",
        }

        for field in requested:
            if field in pointer_by_field:
                claims.append(self.claim(entry, field, pointer_by_field[field]))
            elif field == "examples":
                pointers = self.example_pointers(entry)
                if len(pointers) < example_count:
                    raise ApiError(
                        422,
                        "EVIDENCE_UNAVAILABLE",
                        entry_id=entry["entry_id"],
                        requested_field="examples",
                        requested_count=example_count,
                        available_count=len(pointers),
                    )
                for index, pointer in enumerate(pointers[:example_count]):
                    claims.append(self.claim(entry, f"examples[{index}]", pointer))

        return {
            "status": "ok",
            "release_id": self.release_id,
            "dataset_id": self.dataset_id,
            "entry_id": entry["entry_id"],
            "canonical_file": self.entry_files[entry["entry_id"]],
            "claims": claims,
        }

    def resolve_evidence(self, evidence_id: str) -> dict[str, Any]:
        record = self.evidence_by_id.get(evidence_id)
        if not record:
            raise ApiError(404, "EVIDENCE_NOT_FOUND", evidence_id=evidence_id)
        entry = self.entries_by_id.get(record["entry_id"])
        if not entry:
            raise ApiError(500, "ENTRY_NOT_FOUND_FOR_EVIDENCE", evidence_id=evidence_id)
        try:
            value = resolve_pointer(entry, record["json_pointer"])
        except (KeyError, IndexError, ValueError):
            raise ApiError(500, "EVIDENCE_POINTER_BROKEN", evidence_id=evidence_id) from None
        actual_target_hash = _target_sha256(value)
        verified = actual_target_hash == record["target_sha256"]
        if not verified:
            raise ApiError(500, "EVIDENCE_INTEGRITY_FAILURE", evidence_id=evidence_id)
        return {
            "status": "ok",
            "verified": True,
            "release_id": self.release_id,
            "record": record,
            "value": value,
        }

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "sum20-evidence-bound-pilot-api",
            "release_id": self.release_id,
            "dataset_id": self.dataset_id,
            "entry_count": self.entry_count,
            "evidence_record_count": self.evidence_record_count,
            "supported_fields": list(SUPPORTED_FIELDS),
        }


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
        server_version = "EvidenceBoundPilotAPI/0.1"

        def _write_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
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
