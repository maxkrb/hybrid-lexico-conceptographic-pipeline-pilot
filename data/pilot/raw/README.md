# Raw pilot entries (SUM-20 historical-label sample)

This directory contains a deliberately stratified set of **25 dictionary entries** extracted verbatim from the supplied DOCX source for the P1+P3 pilot.

## Editorial boundary

Only the finalized **А–П** portion of the source is eligible. The last dictionary headword before the excluded `Р` range is **П'ЯТИРІЧЧЯ**; the first excluded dictionary headword is **РАДА**. The selected 25-entry pilot is entirely before that boundary.

## Raw-data policy

- No lexical, spelling, punctuation, or editorial corrections are applied to the extracted text.
- Paragraph boundaries are preserved as line breaks.
- Word formatting (bold/italic) is not encoded in the `.txt` raw layer.
- `index.json` records stable pilot `entry_id` values, source paragraph bounds, next-headword checks, and SHA-256 hashes of every raw file.
- Structured/canonical JSON derived from these files belongs in a later processing layer and must not overwrite the raw source.

## Sampling rationale

The sample intentionally mixes compact and large entries, mono- and polysemous entries, historical and modern senses, lexical variants, specialized labels, fixed expressions, cross-references, and multiple usage illustrations. This supports later testing of sense-level, example-level, and phrase-level evidence anchors.

`ГРАМОТА` is represented by the second homonymous entry (`ГРАМОТА²` in the source), because it provides the document/historical sense and richer phrase-level structures relevant to the pilot.
