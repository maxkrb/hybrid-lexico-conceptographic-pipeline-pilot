# Submitted title and positioning

## English title — submitted

**A Hybrid Lexico-Conceptographic Pipeline with Evidence-Bound Outputs and a Tamper-Evident Blockchain-Ready Release Registry: A Pilot Study**

## Ukrainian working title

**Гібридний лексико-концептографічний конвеєр із доказово прив’язаними результатами та захищеним від підміни реєстром релізів із можливістю подальшого закріплення в блокчейні: пілотне дослідження**

## Author and affiliations for the Springer manuscript

**Maksym Nadutenko** — affiliations 1,2:

1. Ukrainian Lingua-Information Foundation of the National Academy of Sciences of Ukraine, Kyiv, Ukraine.
2. Institute of Applied Control Systems of the National Academy of Sciences of Ukraine (IACS NAS of Ukraine), Kyiv, Ukraine.

Confirmed disclosure statement for the manuscript:

> **Disclosure of Interests.** The author has no competing interests to declare that are relevant to the content of this article.

## Thematic track

**Intelligent Systems**

## Implemented pilot boundary

Implemented and experimentally evaluated:

- 25-entry SUM-20 canonical pilot (`lex-entry-v0.4`);
- RFC8785/JCS + SHA-256 per-entry commitments;
- concrete release instance `sum20-hist-ap-pilot-r001`;
- 840-record Evidence Registry;
- minimal evidence-bound HTTP API and resolver;
- Q+/Q− evaluation: EC=1.000, ERS=1.000, RR=1.000, FRR=0.000;
- P1 versioned corruption experiment: runtime EVDR 0.5333 before hardening and 1.000 after hardening;
- normative release-manifest contract `release-v0.1`;
- deterministic Merkle construction contract `merkle-profile-v0.1`;
- frozen Merkle root `03f36166f45c268d7c8ce4468de6c64dbc884705dd21ab581ee38377da7d3ae2`;
- external release JCS SHA-256 `3a8285f98363363345f52f5e4438b04ad06e0f3397add75a25c08efcf2fbef94`;
- release verifier;
- versioned 30-case release-tamper experiment with TDR=1.000;
- reproducible GitHub Actions execution with byte-for-byte regeneration checks.

Not implemented as current results:

- off-chain digital signature / key-management profile;
- blockchain anchoring;
- on-chain registry or smart contract.

## Release/version terminology

Three identifiers are intentionally separate and must not be conflated:

- `sum20-hist-ap-pilot-r001` — one **concrete frozen release instance**;
- `release-v0.1` — the **schema/contract** defining what a release manifest contains;
- `merkle-profile-v0.1` — the **algorithmic profile** defining how the aggregate Merkle commitment is calculated.

Thus `release-v0.1` is not a second release competing with `r001`. The already reserved `r001` was materialized according to the normative `release-v0.1` contract and `merkle-profile-v0.1`.

## Blockchain wording rule

`Blockchain-ready` has a concrete implemented basis: P3 emits a compact release tuple

`release_id + release_json_sha256 + merkle_root`

that can be retained or externally anchored independently of the lexicographic content. The current paper may therefore describe the release layer as **blockchain-ready**, but it must not say that the pilot is **blockchain-anchored**.

Preferred formulations:

- `blockchain-ready release registry`;
- `blockchain-ready release commitment`;
- `designed for future blockchain anchoring`;
- `externally anchorable release fingerprint`;
- `optional future anchoring of release_id, manifest hash, and Merkle root`.

Avoid as current results:

- `blockchain-anchored registry`;
- `on-chain release registry`;
- `minted snapshot`;
- `blockchain transaction`;
- `smart-contract-backed release`.

## Tamper-evident wording rule

The strongest supported wording is:

> The verifier detected all 30 selective mutations in the versioned P3 release-tamper profile (TDR=1.000) relative to the retained frozen baseline/commitment.

Do **not** write that tampering is impossible or that every attack is detected. A coordinated rewrite of all local canonical, baseline, release, and unsigned commitment artifacts can remain internally self-consistent without an independently retained trust anchor.

This is a **central architectural boundary**, not merely a limitation paragraph. It motivates external retention/authentication of the compact release commitment through a publisher signature, transparency mechanism, institutional timestamp/publication record, or future blockchain anchoring.

GitHub Actions provides executable reproducibility and provenance for the reported pipeline but is not treated as that independent cryptographic trust anchor.

## Signing wording rule

The current release commitment records `signature_status=not_implemented`.

Allowed future-oriented formulations:

- `optionally signable release commitment`;
- `an off-chain signature may authenticate the publisher in a future extension`.

Avoid `signed release manifest` as a current-result phrase.
