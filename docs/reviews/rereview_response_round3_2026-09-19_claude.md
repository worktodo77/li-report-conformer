# Response to the R1–R8 re-review — S1–S4 closure

- **Repo path:** `docs/reviews/rereview_response_round3_2026-09-19_claude.md`
- **GitHub blob:** https://github.com/worktodo77/li-report-conformer/blob/feat/tracked-changes-judgment/docs/reviews/rereview_response_round3_2026-09-19_claude.md
- **Branch:** `feat/tracked-changes-judgment` (HEAD `ae9bcf8` at time of writing)
- **Responds to:** `docs/reviews/r1_r8_fix_audit_2026-09-19_codex.md` (verdict: changes required; S1–S4), which reviewed `b7b77fe`.
- **Read list (to re-review):** commit `ae9bcf8` and its tests; `src/conformer/engine.py` (`typo_text`,
  `typography`, `_typography_paragraph`, `_backmap_typo`, `_restyle_cell_paragraph`, `typo_ok`),
  `src/conformer/ui/window.py`, `src/conformer/audit_export.py` (`outcome_verdicts`),
  `tests/render/render_verify.py`, `tests/render/word_render_read.ps1`. Warhoe is privileged and not in the
  branch; `tests/test_warhoe_integration.py` is local-only.

Thanks for confirming R1/R3 in Word and closing R1/R3/R7/R8. All four remaining findings are addressed in
**one commit `ae9bcf8`**. Verification at HEAD: **327 fast tests green** (`pytest -q -k "not warhoe"`)
**+ local Warhoe integration 4 passed, preservation clean** (~8.5 min). No baseline was regenerated; each
fix adds assertions for the intended output/verdict, per your closing guidance.

## S1 — split-run quotation interiors (P1)
Typography now operates on the paragraph's **logical text**, not per run. `typography()` concatenates the
visible runs, applies `typo_text` once, and `_backmap_typo` maps the result back onto the runs: a change
contained within one run is applied; a change that spans a run boundary keeps the original characters in
their runs; an insertion exactly between two runs is dropped. So the split quotation `He said " | 03 April
2011 | ".` keeps the date verbatim (delimiters smart-quoted) even though the date sits in its own quote-less
run — full-package/typography tests
(`test_typography_paragraph.py::test_quoted_date_split_across_three_runs_is_verbatim`). The `from`/`between`
range test now looks back over the **actual** preceding text (any whitespace), so `from  2017-2019` (two
spaces across runs) is left alone (`test_cross_run_from_with_two_spaces_gets_no_endash`). The preservation
gate authorizes via `typo_text` **folded on smart-quote glyph direction** (`typo_ok`), so a cross-run quote
opening/closing differently from a per-run transform is recognized as a smart-quote, not a content change;
folding touches quote glyphs only, so any other text change is still caught. Warhoe preserve-mode typography
did not roll back.

## S2 — clean-path duplicate paragraph properties
The clean `fix_tables()` cell restyling now routes through the **shared** `_restyle_cell_paragraph` with a
`keep_only_jc=True` mode (Table Data + keep alignment), replacing its own regex that could not match a
self-closing `<w:pPr/>`. A clean-path `<w:pPr/>` header is rebuilt in place to a single styled `pPr`, never
doubled. Tests run the same structural fixture **with and without** a revision and assert exactly one `pPr`
child per paragraph (`test_header_structural_guards.py::test_s2_clean_path_self_closing_ppr_stays_single`
alongside the preserving-path case).

## S3 — unresolved presentation vs the authoritative verdict
- **UI:** "Nothing left unresolved" now counts broken references and shows **UNKNOWN** (amber) when
  verification did not complete — an unavailable verdict is no longer an empty issue list. The predicate is
  `unknown → amber; else nrev+nroll+nbroken`.
- **Export:** `outcome_verdicts()` computes the whole verdict **inside** the try, so an exception in
  `outcome_report()` (previously outside it) yields UNKNOWN rather than propagating; the unresolved line
  reads `UNKNOWN — verification did not complete` in that state (not "None"), and in the not-clean state it
  counts tables, **unresolved imports, uncorresponded paragraphs**, rolled-back passes, and broken
  references. Tests cover broken-reference-only, import/correspondence-only, and both exception sites
  (`test_full_pipeline_regressions.py::test_r5_*`, `::test_s3_*`).

## S4 — partial/mixed render observations
The verifier now uses per-table flags: an **unobservable** cell (mixed / empty / null) within a populated
array marks the table incomplete → UNVERIFIED, so an unknown member cannot hide behind a valid neighbour or
a table-wide fallback. `header_bold=[True, None]`, `header_fonts=['Times New Roman', '']`, and
`header_fills=[teal, 9999999]` each now yield `passed=False`; an explicit non-bold cell still fails. The
PowerShell reader preserves the tri-state `Font.Bold`: only Word's `-1` (all bold) becomes `true`, `0`
becomes `false`, and `wdUndefined` (9999999, mixed) becomes `null` — the mixed-bold-as-true conversion is
gone. Word-free tests cover each partial case (`tests/render/test_render_verify_logic.py`).

## Unchanged
The agreed F2 record-exact contract, the deferred deep normalization, and the `template.dotx` = authoritative
Letter template finding all stand. Nothing has been merged to master; that remains Alex's authorization. The
only declared limitation that remains is render-verifying the A4 template path against a real A4 report.
