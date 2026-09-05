# Pre-release / release-binding artifacts

This directory is a **historical lifecycle-stage namespace** for artifacts that bind the candidate release before P3 materialization. Its name does **not** mean that every file in the directory must have an earlier Git commit timestamp than every file under `data/pilot/release/`.

The artifacts are:

- `content-hashes.json` — frozen RFC8785/JCS SHA-256 commitments for all 25 canonical entries;
- `release-reservation.json` — the lifecycle/identity record for `sum20-hist-ap-pilot-r001`; it was created here while the ID was `reserved` and, after P3 materialization, was intentionally updated in place to `state=released` and linked to the frozen release artifacts;
- `evidence-registry.json` — deterministic 840-record P1 Evidence Registry bound to the same release identity;
- `evidence-example.json` — compact Evidence Record example.

The actual P3 release artifacts live under:

- `data/pilot/release/release.json`;
- `data/pilot/release/release-commitment.json`.

## Why this directory is not renamed for r001

The frozen `release.json` explicitly references:

`data/pilot/pre-release/content-hashes.json`.

Consequently, renaming this directory or moving the frozen hash manifest would change the bytes of `release.json`, which would change `release_json_sha256` and therefore rewrite the already materialized `r001` commitment. The namespace is therefore retained as part of the historical provenance of `r001`, even though `release-reservation.json` was later transitioned from `reserved` to `released`.

This is a lifecycle-state transition, not a second release and not an inconsistency in the frozen lexical content. The release identity remains immutable: if canonical content or the normative release commitment changes, a new release such as `sum20-hist-ap-pilot-r002` must be created rather than rewriting `r001`.

For future release series, a less temporally loaded namespace such as `release-inputs/` or `baseline/` may be preferable. Such a migration must not be retroactively applied to frozen `r001`.