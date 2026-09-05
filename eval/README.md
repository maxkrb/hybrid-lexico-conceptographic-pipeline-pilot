# Evaluation Protocol (P1)

This directory contains the frozen query set and deterministic evaluator for the P1 evidence-bound API pilot.

## Query classes

### `Q+` — answerable queries

`Q+` contains two deterministic families derived from release `sum20-hist-ap-pilot-r001`:

1. **core_fields_all_entries** — one query for each of the 25 canonical entries requesting `lemma`, `pos`, and `definition`;
2. **available_examples** — for each entry with at least one evidence-bound example, one query requesting one or two examples (two whenever at least two are available).

These queries must return `status=ok`. Every returned atomic claim must carry an `evidence_id` that resolves back to the same value.

### `Q−` — deliberately unanswerable evidence requests

For each entry with fewer than 10 evidence-bound examples, `Q−` requests exactly one more example than is available. The request is syntactically valid and uses a supported field; therefore the expected result is specifically `EVIDENCE_UNAVAILABLE`.

Entries with 10 or more examples are excluded from this negative family because the public API caps `example_count` at 10; asking for more would test input validation rather than evidence refusal.

## Metrics

- `EC` — claims carrying an `evidence_id` / returned claims.
- `ERS` — evidence IDs that resolve and reproduce the claim / returned evidence IDs.
- `RR` — Q− queries correctly refused / Q− queries.
- `FRR` — Q+ queries incorrectly refused / Q+ queries.
- `EVDR` — injected evidence-chain corruptions detected / injected corruptions.

No latency, throughput, or audit-time metric is included in this initial evaluation.

## Evidence-chain fault injection

The fault set is a versioned reproducibility artifact rather than an implicit loop inside the evaluator:

- `evidence-corruption-profile-v0.1.json` defines and pins five representative Evidence Records and nine corruption classes;
- `evidence-corruption-cases-v0.1.json` is deterministically generated from that profile and contains the exact 45 case descriptors used by the evaluator;
- `scripts/generate_evidence_corruption_cases.py` performs the expansion with no randomness;
- `docs/pilot/evidence-corruption-reproducibility.md` records the citation/provenance contract.

No corrupted dictionary entry is stored under `data/pilot/canonical/`. Canonical-value faults are represented as patch descriptors with exact `entry_id`, JSON Pointer, mutation rule, and before/after JCS SHA-256 fingerprints. During evaluation the faults are applied only to in-memory copies/runtime indexes.

The experiment reports both runtime behavior and the full evidence-contract verifier. The pre-hardening run detected 24/45 injected corruptions (`EVDR=0.5333`); after runtime hardening the identical fault profile detected 45/45 (`EVDR=1.0`). These figures apply only to this explicitly versioned 45-case corruption profile.

## Reproduce

```bash
python -m pip install -r requirements-pilot.txt
python scripts/generate_eval_query_set.py
python scripts/evaluate_p1.py
PYTHONPATH=. python scripts/generate_evidence_corruption_cases.py
PYTHONPATH=. python scripts/evaluate_evidence_corruption_post.py
```
