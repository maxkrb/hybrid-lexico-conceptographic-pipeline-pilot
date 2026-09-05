# P3 Frozen Release Artifacts

This directory is generated from the already frozen P1 canonical entry commitments.

Files:

- `release.json` — deterministic `release-v0.1` manifest for `sum20-hist-ap-pilot-r001`;
- `release-commitment.json` — external JCS SHA-256 commitment to `release.json`, carrying the same Merkle root.

The release manifest intentionally contains no volatile build timestamp and no self-hash. Its stable external fingerprint is computed as:

`release_json_sha256 = SHA256(RFC8785_JCS(release.json))`.

The current P3 core is unsigned. `signature_status=not_implemented` is recorded explicitly; optional off-chain signing is a separate future extension and is not required for the Merkle/TDR experiment.

The Merkle construction is versioned in `spec/merkle-profile-v0.1.json`. Corrupted release/canonical copies are never persisted here; the release-level tamper experiment applies versioned mutations only to in-memory copies and stores exact mutation descriptors under `eval/`.
