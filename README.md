# Hybrid Lexico-Conceptographic Pipeline — Pilot Reproducibility Package

Public reproducibility package for the paper:

**A Hybrid Lexico-Conceptographic Pipeline with Evidence-Bound Outputs and a Tamper-Evident Blockchain-Ready Release Registry: A Pilot Study**

This repository contains the frozen schemas, pilot data, deterministic generators, evaluation manifests, integrity verifiers, GitHub Actions workflows, and supplementary appendices required to reproduce the reported P1 and P3 experiments.

## Frozen pilot

- dataset: `sum20-hist-ap-pilot-v0`
- release: `sum20-hist-ap-pilot-r001`
- canonical entries: 25
- Evidence Records: 840
- P1 query set: 50 Q+ and 13 Q-
- P1 evidence-corruption cases: 45
- P3 release-tamper cases: 30
- Merkle root: `03f36166f45c268d7c8ce4468de6c64dbc884705dd21ab581ee38377da7d3ae2`
- release manifest JCS SHA-256: `3a8285f98363363345f52f5e4438b04ad06e0f3397add75a25c08efcf2fbef94`

## Reproducibility scope

The package is intentionally narrower than the private development repository. It excludes internal planning files, roadmaps, task lists, handoff notes, superseded manuscript drafts, and other development-only material.

The public package preserves the exact machine-readable inputs and outputs used by the reported experiments, including a separate pre-hardening P1 runtime snapshot so that the unchanged 45-case fault corpus can be evaluated against both the original and hardened resolver implementations.

## Package integrity

The portable SHA-256 manifest is `reproducibility/PACKAGE-FILES.sha256`.

From the repository root:

```bash
sha256sum -c reproducibility/PACKAGE-FILES.sha256
```

The manifest covers all 112 package files other than the manifest itself.

## Trust boundary

The implemented pilot is tamper-evident within the evaluated threat profiles and produces an externally anchorable, blockchain-ready release commitment. It does not implement blockchain anchoring, an on-chain registry, a smart contract, or a digital-signature/key-management mechanism. The release commitment records `signature_status` as `not_implemented`.

GitHub Actions provides executable reproducibility and provenance for the reported pipeline but is not treated as an independent cryptographic trust anchor.

## Rights

No open-source or open-data license is granted. See `RIGHTS.md`. Citation of the paper and repository is permitted; no additional permission to copy, redistribute, modify, or reuse the code, data, or documentation is granted except where required by applicable law or by GitHub's Terms of Service.
