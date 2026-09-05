# Appendix A. Machine-Readable Contracts and Reproducibility Artifacts

This appendix records compact structures needed to reproduce the pilot without reproducing substantial dictionary content. Ellipses below stand for lexical text; field names and identifiers correspond to the repository implementation.

## A.1 Canonical lexical entry

All 25 pilot entries conform to `lex-entry-v0.4`:

```json
{
  "schema_version": "lex-entry-v0.4",
  "dataset_id": "sum20-hist-ap-pilot-v0",
  "entry_id": "sum20-hist-ap-001",
  "source": {
    "raw_path": "data/pilot/raw/001-abak.txt",
    "raw_sha256": "...",
    "source_file": "..."
  },
  "lemma": {
    "display": "...",
    "search": "...",
    "variants": []
  },
  "grammar": {
    "pos": "NOUN",
    "pos_status": "inferred_from_headword_morphology"
  },
  "def_short": "...",
  "def_short_source_pointer": "/senses/0/definition",
  "senses": [
    {
      "sense_id": "...",
      "labels_source": ["..."],
      "definition": "...",
      "examples": [],
      "cross_references": []
    }
  ],
  "phrases": []
}
```

The raw source remains a separate immutable artifact.

## A.2 Entry content commitment

```text
canonical_bytes = RFC8785_JCS(entry)
content_sha256 = SHA256(canonical_bytes)
```

Example frozen commitment:

```text
entry_id: sum20-hist-ap-001
content_sha256: 5ba082967e2af654d972507486a3f9e5511dce2558d51f4c676eb5434b8537a5
```

All 25 commitments are stored in `data/pilot/pre-release/content-hashes.json`.

## A.3 Evidence Record v0.1

```json
{
  "schema_version": "evidence-record-v0.1",
  "id_profile": "ev1-jcs-sha256",
  "evidence_id": "ev1-76281c2fb3044f065a068ff78c386585e10987d82a5ee85ecbb0f17669281206",
  "release_id": "sum20-hist-ap-pilot-r001",
  "entry_id": "sum20-hist-ap-001",
  "content_sha256": "5ba082967e2af654d972507486a3f9e5511dce2558d51f4c676eb5434b8537a5",
  "json_pointer": "/def_short",
  "target_type": "string",
  "target_hash_profile": "jcs-sha256",
  "target_sha256": "b1856a735371b0fb9a77d7b77b344bf1c3feba10526eb299703cb2deb1e3c83f"
}
```

The Evidence ID is:

```text
evidence_id = "ev1-" + HEX(SHA256(RFC8785_JCS({
  domain,
  release_id,
  entry_id,
  content_sha256,
  json_pointer
})))
```

## A.4 Evidence Registry summary

```text
registry_version: evidence-registry-v0.1
release_id: sum20-hist-ap-pilot-r001
entry_count: 25
record_count: 840
```

| Field class | Records |
|---|---:|
| `def_short` | 25 |
| sense/sub-sense definitions | 127 |
| example texts | 401 |
| POS | 25 |
| lemma display | 25 |
| phrase definitions | 79 |
| phrase display | 158 |
| **Total** | **840** |

## A.5 Evidence-bound API success shape

```json
{
  "status": "ok",
  "release_id": "sum20-hist-ap-pilot-r001",
  "entry_id": "sum20-hist-ap-003",
  "claims": [
    {
      "field": "definition",
      "value": "...",
      "evidence_id": "ev1-...",
      "json_pointer": "/def_short",
      "target_sha256": "..."
    }
  ]
}
```

## A.6 Evidence-insufficient refusal

```json
{
  "status": "refused",
  "reason": "EVIDENCE_UNAVAILABLE",
  "release_id": "sum20-hist-ap-pilot-r001",
  "entry_id": "sum20-hist-ap-001",
  "requested_field": "examples",
  "requested_count": 2,
  "available_count": 1
}
```

## A.7 P1 evaluation identifiers

```text
query_set_id: p1-eval-qset-v0.1
evaluation_id: p1-eval-run-v0.1
Q+: 50
Q-: 13
returned claims: 124
EC: 1.000
ERS: 1.000
RR: 1.000
FRR: 0.000
```

## A.8 P1 corruption artifact

```text
corruption_profile_id: p1-evidence-corruption-profile-v0.1
case_manifest_id: p1-evidence-corruption-cases-v0.1
case_count: 45
case_manifest_jcs_sha256:
1eedbef2c162788c02b9944ba6ad9403ff33305939fe33cac6442bb260eeccc4
```

Measured runtime EVDR changed from `24/45 = 0.5333` to `45/45 = 1.000` on the unchanged manifest after runtime hardening.

## A.9 P1 hardening provenance

```text
pre-hardening runtime tree:
a4780fffca84d6b7b5bcbe5bf0ae85e2bc84607a

runtime hardening:
cc569bf6ad1256835a3afa0c9e9ee9c50b6c2ec5

frozen P1 corruption artifact:
ae031968410d8d0f3eacb7a0695ded29a402070f
```

## A.10 Frozen P3 `release.json`

The actual P3 release schema is `release-v0.1`. The release contains all 25 `{entry_id, content_sha256}` pairs; abbreviated form:

```json
{
  "schema_version": "release-v0.1",
  "release_id": "sum20-hist-ap-pilot-r001",
  "dataset_id": "sum20-hist-ap-pilot-v0",
  "release_sequence": 1,
  "entry_schema_version": "lex-entry-v0.4",
  "canonicalization": "RFC8785-JCS",
  "hash_algorithm": "SHA-256",
  "entry_count": 25,
  "content_hash_manifest": "data/pilot/pre-release/content-hashes.json",
  "merkle_profile": "merkle-profile-v0.1",
  "entries": [
    {
      "entry_id": "sum20-hist-ap-001",
      "content_sha256": "5ba082967e2af654d972507486a3f9e5511dce2558d51f4c676eb5434b8537a5"
    }
  ],
  "merkle_root": "03f36166f45c268d7c8ce4468de6c64dbc884705dd21ab581ee38377da7d3ae2"
}
```

The complete object is `data/pilot/release/release.json`.

## A.11 Merkle profile v0.1

Entry order:

```text
ascending UTF-8 byte order of entry_id
```

Leaf:

```text
SHA256(RFC8785_JCS({
  "domain": "hybrid-lexico-conceptographic-pipeline/merkle/leaf/v1",
  "entry_id": entry_id,
  "content_sha256": content_sha256
}))
```

Internal node:

```text
SHA256(RFC8785_JCS({
  "domain": "hybrid-lexico-conceptographic-pipeline/merkle/node/v1",
  "left_sha256": left,
  "right_sha256": right
}))
```

Odd-node rule: `duplicate_last`.

Frozen root:

```text
03f36166f45c268d7c8ce4468de6c64dbc884705dd21ab581ee38377da7d3ae2
```

## A.12 External release commitment

```json
{
  "commitment_version": "release-commitment-v0.1",
  "release_id": "sum20-hist-ap-pilot-r001",
  "release_json": "data/pilot/release/release.json",
  "canonicalization": "RFC8785-JCS",
  "hash_algorithm": "SHA-256",
  "release_json_sha256": "3a8285f98363363345f52f5e4438b04ad06e0f3397add75a25c08efcf2fbef94",
  "merkle_root": "03f36166f45c268d7c8ce4468de6c64dbc884705dd21ab581ee38377da7d3ae2",
  "signature_status": "not_implemented"
}
```

No digital signature or blockchain transaction is claimed in this pilot.

## A.13 P3 exact tamper set

```text
profile_id: p3-release-tamper-profile-v0.1
case_manifest_id: p3-release-tamper-cases-v0.1
experiment_id: p3-release-tamper-run-v0.1
case_count: 30
case_manifest_jcs_sha256:
99d26735e658e2f6604c544fe4d59b0b4abbabc200f9ef7103e8bb6b428a3298
TDR: 30/30 = 1.000
```

The ten corruption classes are canonical content mutation, release digest mutation, digest remap, entry-ID mutation, entry removal, entry addition, entry reorder, Merkle-root mutation, release-ID mutation, and external release-hash mutation.

Generated files:

```text
eval/release-tamper-cases-v0.1.json
eval/release-tamper-results-v0.1.json
```

Implementation/generator files:

```text
src/release_integrity.py
scripts/build_release.py
scripts/verify_release.py
scripts/generate_release_tamper_cases.py
scripts/evaluate_release_tamper.py
```

## A.14 P3 provenance

```text
P3 implementation commit:
3f450fbf926409ebcaa9ba80909064862551fd3d

frozen generated P3 artifacts:
d7f3ddb07314c29c87b03247d9c16591c72d328a
```

## A.15 Minimal reproduction commands

```bash
python -m pip install -r requirements-pilot.txt
python scripts/validate_canonical.py
python scripts/build_content_hashes.py --check data/pilot/pre-release/content-hashes.json
python src/minimal_api.py --check
python scripts/evaluate_p1.py
PYTHONPATH=. python scripts/generate_evidence_corruption_cases.py
PYTHONPATH=. python scripts/evaluate_evidence_corruption_post.py
PYTHONPATH=. python scripts/build_release.py
PYTHONPATH=. python scripts/verify_release.py
PYTHONPATH=. python scripts/generate_release_tamper_cases.py
PYTHONPATH=. python scripts/evaluate_release_tamper.py
```

## A.16 Security boundary

The P3 hash/Merkle verifier detects the versioned 30-case selective tamper profile relative to the retained frozen baseline. A fully coordinated replacement of every local source, hash manifest, release manifest, root, and unsigned commitment can be made internally self-consistent. Detecting that stronger attack requires an independently retained commitment, authenticated signature, transparency log, or future blockchain anchor.
