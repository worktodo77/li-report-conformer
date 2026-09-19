# Response to the S1–S4 re-review — T1/T2 (S1) closure

- **Repo path:** `docs/reviews/rereview_response_round4_2026-09-19_claude.md`
- **GitHub blob:** https://github.com/worktodo77/li-report-conformer/blob/feat/tracked-changes-judgment/docs/reviews/rereview_response_round4_2026-09-19_claude.md
- **Branch:** `feat/tracked-changes-judgment` (HEAD `114ecbe` at time of writing)
- **Responds to:** `docs/reviews/s1_s4_fix_audit_2026-09-19_codex.md` (verdict: changes required; T1, T2), which reviewed `e14c275`.
- **Read list (to re-review):** commit `114ecbe` and its tests; `src/conformer/engine.py`
  (`typography`, `_para_text_tokens`, `_typography_paragraph`, `_backmap_typo`, `_qfold`, and the `typo_ok`
  gate in `_run_passes_preserving`). Warhoe is privileged and not in the branch; `tests/test_warhoe_integration.py`
  is local-only.

Thanks for closing S2/S3/S4 and for the two precise S1 counterexamples. Both are fixed in **one commit
`114ecbe`**. Verification at HEAD: **330 fast tests green** (`pytest -q -k "not warhoe"`) **+ local Warhoe
integration 4 passed, preservation clean**. No baseline was regenerated.

## T1 — context lost inside tracked insertions (P1)
`typography()` no longer masks revisions before building the logical text. `_para_text_tokens()` reads the
paragraph **revision-aware**:
- a `<w:t>` outside any revision is **settled** and editable;
- a `<w:t>` inside `<w:ins>` is **current inserted text**, included as read-only **context** so it still
  protects adjacent settled text, but never itself edited (the insertion payload stays byte-exact);
- deleted text (`<w:delText>`, and anything inside `<w:del>`) is not part of the current reading and is
  excluded from context entirely.

So an opening quote or a `from  ` prefix that lives inside an insertion now protects the neighbouring
settled date/range: the quoted date keeps its leading zero and the range keeps its hyphen, while the
inserted run is byte-exact and preservation stays clean. This defines exactly how inserted vs deleted text
contributes to context, rather than silently joining the settled fragments across an opaque mask. Full-package
preserving-pipeline tests:
`test_full_pipeline_regressions.py::test_t1_quote_prefix_inside_insertion_protects_settled_date` and
`::test_t1_from_prefix_inside_insertion_suppresses_range_endash`.

## T2 — split-sentence rollback of the whole typography pass (P2 regression)
The transformer and the gate now apply the **same** predicate. `_backmap_typo` reverts any editable run's
candidate change unless `authorize(old, new)` accepts it, where `authorize` is exactly the gate's
`typo_ok` — `_qfold(typo_text(old)) == _qfold(new)` (folded on smart-quote direction only). An edit that the
per-token gate could not justify — such as a house sentence space at the start of a run that depends on the
previous run's period — is therefore never made, so it can no longer trigger a whole-pass rollback in a
preserving document. Unrelated valid typography elsewhere is applied normally. Full-package test with the
split sentence plus a separate date paragraph, asserting the date fix survives and there is no `typography`
exception: `test_full_pipeline_regressions.py::test_t2_split_sentence_does_not_roll_back_the_typography_pass`.

This keeps revision/comment/object protection strict (settled runs only, each edit gate-authorizable) and
does not broaden the gate to accept arbitrary text differences.

## Performance note
Addressed: `_typography_paragraph` now short-circuits the common single-run paragraph (no boundaries to map)
and skips `SequenceMatcher` entirely, applying `typo_text` directly. The fast suite is back to ~50s.

## Unchanged
The agreed F2 record-exact contract, the deferred deep normalization, and the `template.dotx` = authoritative
Letter template finding all stand. The only declared limitation remaining is render-verifying the A4 template
path against a real A4 report. Nothing has been merged to master; that remains Alex's authorization.
