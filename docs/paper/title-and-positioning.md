# Submitted title and positioning

## English title

**A Hybrid Lexico-Conceptographic Pipeline with Evidence-Bound Outputs and a Tamper-Evident Blockchain-Ready Release Registry: A Pilot Study**

## Ukrainian working title

**Гібридний лексико-концептографічний конвеєр із доказово прив’язаними результатами та захищеним від підміни реєстром релізів із можливістю подальшого закріплення в блокчейні: пілотне дослідження**

## Author and affiliations

**Maksym Nadutenko** — affiliations 1,2:

1. Ukrainian Lingua-Information Foundation of the National Academy of Sciences of Ukraine, Kyiv, Ukraine.
2. Institute of Applied Control Systems of the National Academy of Sciences of Ukraine (IACS NAS of Ukraine), Kyiv, Ukraine.

## Disclosure of Interests

The author has no competing interests to declare that are relevant to the content of this article.

## Thematic track

**Intelligent Systems**

## Implemented pilot scope

The implemented and experimentally evaluated pilot comprises:

- a 25-entry SUM-20 canonical pilot (`lex-entry-v0.4`);
- RFC8785/JCS canonicalization and SHA-256 per-entry commitments;
- the concrete release instance `sum20-hist-ap-pilot-r001`;
- an 840-record Evidence Registry;
- a minimal evidence-bound HTTP API and resolver;
- Q+/Q− evaluation with EC=1.000, ERS=1.000, RR=1.000, and FRR=0.000;
- the P1 versioned corruption experiment, with runtime EVDR increasing from 0.5333 before hardening to 1.000 after hardening;
- the normative release-manifest contract `release-v0.1`;
- the deterministic Merkle construction contract `merkle-profile-v0.1`;
- the frozen Merkle root `03f36166f45c268d7c8ce4468de6c64dbc884705dd21ab581ee38377da7d3ae2`;
- the RFC8785/JCS SHA-256 hash of the release manifest, `3a8285f98363363345f52f5e4438b04ad06e0f3397add75a25c08efcf2fbef94`;
- a release verifier;
- a versioned 30-case release-tamper experiment with TDR=1.000;
- reproducible GitHub Actions execution with byte-for-byte regeneration checks.

The implemented pilot does not include an off-chain digital-signature or key-management mechanism, blockchain anchoring, an on-chain registry, or a smart contract.

## Release and version terminology

The implementation distinguishes three identifiers that correspond to different architectural levels:

- `sum20-hist-ap-pilot-r001` identifies one concrete frozen release instance;
- `release-v0.1` identifies the schema and contract governing the structure of a release manifest;
- `merkle-profile-v0.1` identifies the algorithmic profile governing construction of the aggregate Merkle commitment.

Accordingly, `release-v0.1` does not denote a second release. The frozen release instance `sum20-hist-ap-pilot-r001` was materialized according to the normative `release-v0.1` contract and the `merkle-profile-v0.1` construction profile.

## Blockchain-readiness boundary

The designation **blockchain-ready** refers to a concrete property of the implemented release layer. P3 produces a compact release commitment consisting of

`release_id + release_json_sha256 + merkle_root`

which can be retained or externally anchored independently of the underlying lexicographic content.

The implemented pilot therefore supports an externally anchorable release fingerprint and is designed to permit future anchoring of the release identifier, manifest hash, and Merkle root. No blockchain anchoring is performed in the current pilot, and no blockchain transaction, on-chain release registry, smart contract, or equivalent blockchain-backed mechanism forms part of the reported implementation.

## Tamper-evidence and trust boundary

The release verifier detected all 30 selective mutations in the versioned P3 release-tamper profile (TDR=1.000) relative to the retained frozen baseline and commitment.

These results establish tamper evidence within the evaluated threat profile; they do not establish that tampering is impossible or that every conceivable attack is detectable. A coordinated rewrite of all local canonical, baseline, release, and unsigned commitment artifacts may remain internally self-consistent in the absence of an independently retained trust anchor.

This constitutes a central architectural boundary rather than merely a limitation of the experiment. It motivates independent retention or authentication of the compact release commitment through mechanisms such as a future publisher digital signature, a transparency mechanism, an institutional timestamp or publication record, or future blockchain anchoring.

GitHub Actions provides executable reproducibility and provenance for the reported pipeline but is not treated as an independent cryptographic trust anchor.

## Digital-signature boundary

The current release commitment explicitly records `signature_status` as `not_implemented`. Consequently, no digital-signature or key-management mechanism is claimed as part of the implemented pilot.

The release commitment is structured so that publisher authentication can be introduced as a future extension. Such an extension may use an off-chain digital signature to authenticate the publisher and the retained release commitment without altering the present claim that the reported pilot itself is unsigned.
