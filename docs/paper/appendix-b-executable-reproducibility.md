# Appendix B. Executable Reproducibility, Scripts, and CI Provenance

This appendix provides the executable inventory behind the experiments. The main paper describes only scripts that are necessary to understand the scientific method; this appendix records the complete pilot execution surface so that implementation detail does not overload Sections 3–7.

## B.1 Execution environment

The reference CI environment uses Python 3.12 and the root `requirements-pilot.txt`. The two non-standard pilot dependencies are pinned as:

```text
jsonschema==4.26.0
rfc8785==0.1.4
```

GitHub Actions is used as the automated reference execution environment. Its role is **reproducibility and executable provenance**, not external historical authentication. In particular, a successful CI rerun is not equivalent to the independent trust anchor required to detect a coordinated rewrite of the entire repository and all unsigned local commitments.

## B.2 Core implementation modules

| File | Role | Main inputs | Main outputs / checks | Paper location |
|---|---|---|---|---|
| `src/minimal_api.py` | P1 evidence-bound HTTP service and Evidence Record resolver | canonical entries, Evidence Registry, release binding artifacts | evidence-bound responses, `EVIDENCE_UNAVAILABLE`, full runtime evidence-chain verification | Secs. 4, 6.8, 7 |
| `src/release_integrity.py` | Shared P3 integrity implementation used by builder, verifier, and evaluator | content-hash manifest, release/Merkle profiles, canonical entries | JCS hashing, Merkle construction, release validation primitives | Secs. 5, 6.10–6.14 |

## B.3 Script inventory

| Script | Experimental function | Principal inputs | Principal output / effect |
|---|---|---|---|
| `scripts/validate_canonical.py` | Validates the 25 canonical SUM-20 entries and raw-source bindings | `data/pilot/raw/`, `data/pilot/canonical/`, `canonical-entry-v0.4.schema.json` | pass/fail validation gate |
| `scripts/build_content_hashes.py` | Computes deterministic RFC8785/JCS SHA-256 entry commitments | canonical entries | `data/pilot/pre-release/content-hashes.json`; `--check` verifies byte-identical frozen manifest |
| `scripts/validate_evidence_contract.py` | Validates P1 release identity and Evidence Record contract examples/bindings | Evidence schema, reservation/release identity, content hashes, canonical entries | pass/fail evidence-contract gate |
| `scripts/generate_evidence_registry.py` | Generates all publishable Evidence Records deterministically | canonical entries, content hashes, release identity, publishable-field profile | 840-record `evidence-registry.json`; `--check` verifies byte identity |
| `scripts/generate_eval_query_set.py` | Builds deterministic P1 Q+/Q− protocol | canonical/evidence state | `eval/query-set-v0.1.json` |
| `scripts/evaluate_p1.py` | Executes the P1 positive/negative query protocol | minimal API state, frozen query set | `eval/results-v0.1.json`; EC, ERS, RR, FRR |
| `scripts/generate_evidence_corruption_cases.py` | Materializes the exact versioned P1 corruption manifest with no randomness | corruption profile, pinned evidence targets, frozen evidence state | `eval/evidence-corruption-cases-v0.1.json` |
| `scripts/evaluate_evidence_corruption.py` | Applies each of the 45 exact P1 corruptions to in-memory copies and evaluates both runtime and strict contract verification | exact corruption cases, canonical entries, content hashes, release identity, `minimal_api.py` | corruption detection results including runtime and full-contract EVDR |
| `scripts/evaluate_evidence_corruption_post.py` | Re-runs the unchanged 45-case manifest against the hardened runtime and binds the result to the pre-hardening baseline | `evaluate_evidence_corruption.py`, exact case manifest, pre-hardening result | `eval/evidence-corruption-results-posthardening-v0.1.json` |
| `scripts/build_release.py` | Materializes deterministic P3 release and external release commitment | canonical/content hashes, release identity, `release-v0.1`, `merkle-profile-v0.1` | `data/pilot/release/release.json`, `release-commitment.json` |
| `scripts/verify_release.py` | Verifies base P3 release against frozen inputs and schemas | canonical entries, content hashes, release, commitment, Merkle profile | pass/fail release verification with reproduced hashes/root |
| `scripts/generate_release_tamper_cases.py` | Generates the exact deterministic 30-case P3 tamper manifest | P3 tamper profile, frozen release/commitment, selected entries | `eval/release-tamper-cases-v0.1.json` |
| `scripts/evaluate_release_tamper.py` | Applies all P3 mutations to in-memory copies and measures release-level detection | frozen base release/commitment, exact 30-case manifest, shared verifier | `eval/release-tamper-results-v0.1.json`; TDR and per-class detections |

The two-layer design of the P1 corruption experiment is deliberate. `evaluate_evidence_corruption.py` contains the common fault application and comparison logic, including the independent full-contract verifier. `evaluate_evidence_corruption_post.py` is a small provenance wrapper that reruns the **same** versioned cases after runtime hardening and records the baseline reference, preventing a changed fault set from being presented as a post-hardening improvement.

## B.4 GitHub Actions workflow inventory

There are eight pilot workflows in `.github/workflows/`.

| Workflow | Responsibility | Main executable chain |
|---|---|---|
| `validate-canonical.yml` | Canonical/raw validation on relevant push/PR changes | install pinned deps → `validate_canonical.py` |
| `build-content-hashes.yml` | Verify frozen per-entry JCS/SHA-256 commitments | `validate_canonical.py` → `build_content_hashes.py --check` |
| `validate-evidence-contract.yml` | Validate P1 Evidence Record/release-binding contract | `validate_evidence_contract.py` |
| `generate-evidence-registry.yml` | Deterministically regenerate 840 Evidence Records | `generate_evidence_registry.py` → `--check` → commit only if changed |
| `validate-minimal-api.yml` | Validate loaded P1 state, unit tests, and HTTP health smoke test | `minimal_api.py --check` → unit tests → live local HTTP smoke test |
| `build-p1-evaluation.yml` | Generate and run Q+/Q− evaluation and prove byte reproducibility | `generate_eval_query_set.py` → `evaluate_p1.py` → regenerate → `cmp` both artifacts |
| `evaluate-evidence-corruption.yml` | Generate exact P1 fault manifest and run post-hardening corruption experiment | `generate_evidence_corruption_cases.py` → `evaluate_evidence_corruption_post.py` → regenerate/cmp case manifest |
| `build-p3-release.yml` | Complete P3 build, verification, TDR experiment, and byte-for-byte regeneration | `build_release.py` → `verify_release.py` → `generate_release_tamper_cases.py` → `evaluate_release_tamper.py` → repeat all → `cmp` four generated artifacts |

## B.5 P3 Action and commit provenance

The P3 workflow `.github/workflows/build-p3-release.yml` was introduced in the implementation commit:

```text
3f450fbf926409ebcaa9ba80909064862551fd3d
Implement deterministic P3 release and tamper evaluation
```

That same commit introduced the normative P3 schemas/profile and the builder/verifier/tamper generator/evaluator implementation used by the first reference CI run.

The first P3 GitHub Actions execution was:

```text
workflow: Build P3 release and TDR
run_id: 33885931217
run_number: 1
event: push
head_sha: 3f450fbf926409ebcaa9ba80909064862551fd3d
conclusion: success
```

The successful workflow generated and froze the deterministic release and TDR artifacts through:

```text
d7f3ddb07314c29c87b03247d9c16591c72d328a
Freeze deterministic P3 release and tamper results
```

The frozen generated set comprises:

```text
data/pilot/release/release.json
data/pilot/release/release-commitment.json
eval/release-tamper-cases-v0.1.json
eval/release-tamper-results-v0.1.json
```

After P3 materialization, the lifecycle record was promoted from `reserved` to `released` in:

```text
2901fd6c6d4540ae4f0c5ff35876d587137e2c43
Mark r001 release reservation as materialized
```

A subsequent P3 workflow run on that state transition also completed successfully. The Evidence Registry generator initially exposed a lifecycle assumption (`state=reserved` only); this was corrected without changing the 840-record generated registry in:

```text
5e7cdfd953f054e33f10eb788437e2d3d675ed4d
Allow deterministic P1 evidence rebuild after release materialization
```

The post-fix Evidence Registry CI regenerated 25 entries / 840 records, passed its byte-for-byte check, and reported the committed registry already current.

## B.6 P3 byte-for-byte reproducibility contract

`build-p3-release.yml` performs the following reference sequence:

```text
build release.json + release-commitment.json
→ verify base release
→ generate exact 30-case tamper manifest
→ evaluate TDR
→ copy all four generated artifacts
→ rerun builder/verifier/generator/evaluator
→ byte-compare all four regenerated files
→ commit only if deterministic output changed
```

The reported Merkle root, `release_json_sha256`, 30-case manifest fingerprint, and TDR therefore correspond to committed generated artifacts produced by the same code path used in CI.

## B.7 Manual reproduction sequence

A local reproduction of the principal stages is:

```bash
python -m pip install -r requirements-pilot.txt
python scripts/validate_canonical.py
python scripts/build_content_hashes.py --check data/pilot/pre-release/content-hashes.json
python scripts/validate_evidence_contract.py
python scripts/generate_evidence_registry.py --check
python src/minimal_api.py --check
python scripts/generate_eval_query_set.py
python scripts/evaluate_p1.py
PYTHONPATH=. python scripts/generate_evidence_corruption_cases.py
PYTHONPATH=. python scripts/evaluate_evidence_corruption_post.py
PYTHONPATH=. python scripts/build_release.py
PYTHONPATH=. python scripts/verify_release.py
PYTHONPATH=. python scripts/generate_release_tamper_cases.py
PYTHONPATH=. python scripts/evaluate_release_tamper.py
```

For a pristine clone at the frozen release state, scripts that generate artifacts rather than check them may be followed by byte comparison against the committed files, mirroring the corresponding workflows.

## B.8 Relationship between CI reproducibility and blockchain-ready trust

CI answers: **do these versioned inputs and rules reproduce the same outputs and measured results?**

External anchoring answers a different question: **can a later verifier determine that this release commitment existed outside a subsequently rewritten local repository?**

The distinction is essential. GitHub Actions strengthens reproducibility, audit trails, and regression detection, but the paper does not use GitHub Actions as proof against a hypothetical attacker who can rewrite the complete repository history and every local unsigned commitment. The externally anchorable tuple `release_id + release_json_sha256 + merkle_root` is the compact object intended for independent retention or future external authentication or anchoring.
