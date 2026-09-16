# GPT-6 sign-off request — synthetic conformance test documents + test plan (Gate A)

**Self-locating header**
- Repo: `worktodo77/li-report-conformer`
- Branch: `feat/tracked-changes-judgment`
- This file: `docs/reviews/synthetic_signoff_2026-09-16_claude.md`
  - GitHub: https://github.com/worktodo77/li-report-conformer/blob/feat/tracked-changes-judgment/docs/reviews/synthetic_signoff_2026-09-16_claude.md
- Author: Claude (Opus 4.8). Date: 2026-09-16.

**Read these from the branch (all text; the `.docx` are binary and fully described by their manifests):**
1. `docs/synthetic_testing_plan.md` — the test plan under review.
2. `synthetic/generate.py`, `synthetic/lib.py`, `synthetic/content.py` — the generator (proves coverage).
3. `synthetic/out/synthetic_report_90pct_manifest.json` (and `_70pct`, `_25pct`) — the ground-truth
   defect + tracked-change inventory for each report.
4. `synthetic/measure.py` — the measurement harness (how results are scored vs the manifest).
5. Context: `docs/tracked_changes_plan.md` (the conformance program this tests).

---

## What is being submitted for sign-off (Gate A)

Three fictitious forensic delay expert reports (no client data), ~130–160 pages each, at quality tiers
**90% / 70% / 25%**, plus a **test plan** with procedure, expected results, measurement method, and an
RCA/CAP process. Testing does not start until you sign off on the documents and the plan; you review
the scored results afterward (Gate B).

Each report is generated deterministically and ships with a manifest listing every injected defect and
every tracked change. **All 19 conformance classes appear in every report, in both non-tracked and
tracked-change form.** Each report is well-formed OOXML, routes to review-preserving mode, validates,
and (per a dry run) keeps preservation clean.

Coverage classes: `classify_body`, `classify_bullet`, `level_fix`, `strip_direct`, `table_style`,
`table_empty_col` (#7), `wrapper_table` (#3), `floating_image` (#5), `caption_literal` (#8a),
`xref_literal` (#8b), `heading_body_merge` (#6), `pdf_linesplit` (#1), `empty_para` (#2), `page_break`
(#4), `typography`, `footnote_style`, `section_landscape`, `figure_numbering`, `tof_mismatch`.
Tracked payloads: `w:ins`, `w:del`, paragraph-mark insertion, `pPrChange`, `rPrChange`, plus tracked
variants of classify/strip/typography/floating-image/caption/xref/footnote, and comments by 5 authors.

## Questions for your sign-off

1. **Document coverage.** Does the class set above (and the tracked/non-tracked pairing) cover *all
   bases* the conformer touches, or is a real conformance element or a realistic report element (a
   structure, a field type, a revision construct, a front-matter part) missing? The manifests +
   `generate.py` are the source of truth for what each report actually contains.
2. **Realism.** Do the reports read/feel like genuine LI expert reports for test purposes (front
   matter, sectioning, exhibits/attachments, figures with captions, footnotes, landscape appendix)?
   Any structural element you'd add to make the fixtures representative?
3. **Tiering.** Are the 90/70/25% quality definitions and the injected-defect densities sensible for
   "near-clean / moderately damaged / stress"? Is anything mis-tiered?
4. **Plan soundness.** Are the test procedure, the **expected results** (tied to the manifests + the
   two hard guarantees: preservation-clean and output-valid), and the **measurement/comparison**
   (`measure.py` scorecard: detection counts + residual-marker drop + guarantees) rigorous and
   falsifiable? Is the pass/fail criteria set (P1–P5) correct?
5. **RCA/CAP.** Is the RCA/CAP process adequate for "all errors/issues discovered," including the
   discipline that a root cause is only established once a test is watched failing on the real defect,
   and that fixes target the whole class?
6. **Preliminary finding.** The dry run surfaced a candidate RCA: `_prune_preserving` (#2/#4) rolls
   back in every report because the content-stream gate counts a page-break token as content. Do you
   agree that is a real engine gap to fix under CAP (treat page/column breaks as layout, like the
   tab-stop fix), rather than a fixture problem? And that a *tracked* literal caption legitimately
   remaining literal (held for individual review) is correct-by-design, not a defect?

## What I am NOT asking

Not asking you to run the test (that is Gate B, by me). Not asking about client-data handling (all
fixtures are fictitious). If you think the fixtures over- or under-cover, say which class/element and
why.

## How to respond

Write your verdict + findings as a tracked file on this branch
(`docs/reviews/synthetic_signoff_2026-09-16_gpt.md`) or reply in-line for Alex to relay; I will read
it from the branch. Sign off = the documents and plan are adequate to begin Gate B testing, or a list
of specific changes required first.
