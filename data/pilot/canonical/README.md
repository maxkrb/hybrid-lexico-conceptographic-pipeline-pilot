# Canonical pilot layer

This directory contains structured canonical representations derived from the immutable raw pilot entries in `data/pilot/raw/`.

## Rules

1. The raw layer is never edited during canonical conversion.
2. Source wording is preserved for definitions, usage examples, labels, and cross-reference targets.
3. Source labels such as `іст.`, `архт.`, `псих.`, `філос.`, `лінгв.` are preserved verbatim in `labels_source`; they are not silently expanded or normalized.
4. Normalized fields are explicitly marked when inferred. `grammar.pos` is marked with `pos_status = "inferred_from_headword_morphology"` when POS is inferred from source morphology rather than an explicit POS field.
5. Numbered dictionary meanings become `senses[]`; meanings introduced by `//` become `sub_senses[]`.
6. Numbered or marked lexical combinations are represented in `phrases[]`.
7. `def_short` is not newly generated prose: in this pilot it is copied from the first numbered sense and records its source JSON Pointer in `def_short_source_pointer`.
8. Final `evidence_id` values are deliberately absent at this stage. They will be generated only after the canonical entry is stable, its deterministic `content_sha256` is computed, and a release ID exists.
9. Canonical content hashing will be performed over a deterministic serialization, not over the human-readable formatting of these files.
10. If the source gives an example without an explicit attribution, `source_ref` remains empty; no source is invented.
11. The raw layer is the lossless archival source. The canonical P1 layer preserves all modeled senses, sub-senses, labels, definitions, phrase structures and cross-references, while usage examples may be retained as a bounded evidence-bearing subset sufficient for the pilot API tasks. Omitted illustrations remain recoverable from the immutable raw entry and are not treated as absent source data.

## Schema evolution driven by source structure

- `lex-entry-v0.2` (`001`–`005`) established senses, sub-senses, examples, labels and phrase records.
- `lex-entry-v0.3` (`006`–`010`) was introduced after `БІ́ЛИЙ` showed that many lexical combinations are cross-reference-only. It added structured phrase/sub-sense cross-references and permitted `definition: null` for xref-only phrases.
- `lex-entry-v0.4` was introduced after `ГРА́МОТА²` showed that a phrase itself may have distinct sub-senses (`Фі́ЛЬЧИНА ГРА́МОТА`, a/b). It adds phrase `sub_senses[]`, optional example-level source labels, headword labels/homonym number, and verb aspect/inflection metadata.

Batches 4 and 5 (`016`–`025`) required no further schema extension, including the large `ПРА́ВО` entry and the unnumbered main sense with `//` sub-senses in `ПУ́ДРА`. This is the stabilization point selected for the pilot.

## Conversion and migration status

- Raw pilot entries: 25
- Canonicalized: 25 (`001`–`025`)
- Unified schema: `lex-entry-v0.4`
- Legacy canonical batches `001`–`010` were migrated to v0.4 by changing the schema declaration only; source-derived lexical content was not rewritten during migration.
- Remaining schema migrations: none

## Next control step

1. Validate all 25 canonical entries against `spec/canonical-entry-v0.4.schema.json`.
2. Verify raw-file SHA-256 provenance, entry/index consistency, unique identifiers, and resolvability of `def_short_source_pointer`.
3. Only after successful validation, freeze the canonical serialization rules and compute deterministic `content_sha256` values.
4. Build release-level evidence anchors and generate final `evidence_id` values as the next P1 stage.
