# Synthetic Conformance Test Plan — LI Report Conformer (v2)

**Status:** DRAFT for GPT-6 sign-off (resubmission after the Gate-A review). Testing (Gate B) does not
begin until GPT-6 signs off on the documents **and** this plan. GPT-6 reviews the scored results after.

**Author:** Claude (Opus 4.8). **Branch:** `feat/tracked-changes-judgment`.

This revision rebuilds the ground truth to be **per-instance and independently verifiable**, and
rebuilds the scorer to **enforce** the pass criteria. See §11 for the point-by-point response to the
Gate-A review.

---

## 1. Purpose

Verify — against a known, per-instance ground truth — that the conformer (a) detects and correctly
disposes of every conformance class it handles, and (b) preserves every tracked change, comment,
author, and object while doing so, across a spectrum of document quality including a clean control.

## 2. Test articles — four reports + an adversarial suite

Fictitious forensic construction-delay expert reports (invented parties/project/figures — no client
data), generated deterministically by `synthetic/generate.py`, each with a per-instance
`*_manifest.json`. A **clean control** measures false positives; three defect-density tiers span
near-clean to stress.

| Report | Density | computed_quality (element pass-rate) | ~pages | Defects | Tracked changes | Comments |
|---|---|---|---|---|---|---|
| `synthetic_report_clean.docx`  | control | 1.000 | ~59 | 0   | 0  | 0 |
| `synthetic_report_low.docx`    | low     | ~0.89 | ~65 | ~49 | ~47 | ~15 |
| `synthetic_report_medium.docx` | medium  | ~0.67 | ~67 | ~174 | ~42 | ~20 |
| `synthetic_report_high.docx`   | high    | ~0.22 | ~58 | ~502 | ~19 | ~4 |

`computed_quality` = 1 − (non-conforming elements / conformance-eligible elements), an **element
pass-rate over a real denominator** — it is the authoritative figure; the "low/medium/high" labels are
informal. Page counts are **estimated** from word/figure/table volume (see §9 on rendered pagination).

Each report has full front matter (title/privilege page, TOC field, **List of Figures, List of
Tables**, List of Exhibits, List of Attachments, glossary), twelve numbered sections with sub-headings,
numbered paragraphs, bullet lists, block quotes, footnotes, tables, and figures (charts + a
photograph), tracked changes by five authors, comments, and a landscape appendix. Reproducibility:
fixed integer seeds (not `hash()`), recorded in the manifest with generator version, template/asset
SHAs, and dependency versions.

**Adversarial suite** (`tests/test_adversarial_synth.py`): small, targeted fixtures for the hard
constructs kept out of the long reports — paragraph-mark deletion, a move (`moveFrom`/`moveTo`), a
table-cell revision (`cellDel`, surfaced as a restriction), a tracked table row, a **corrupted List
Bullet style definition** and a **corrupted table-style definition** (Claire's real complaint;
repaired from the template), and a comment anchored wholly inside a deleted region. Each asserts the
engine's expected disposition with preservation verified clean.

### 2.1 Conformance classes (each present in every report, non-tracked and tracked)

`classify_body`, `classify_bullet`, `level_fix`, `strip_direct`, `table_style`, `table_empty_col` (#7),
`wrapper_table` (#3), `floating_image` (#5), `caption_literal` (#8a), `xref_literal` (#8b),
`heading_body_merge` (#6), `pdf_linesplit` (#1), `empty_para` (#2), `page_break` (#4), `typography`,
`footnote_style`, `section_landscape`, `figure_numbering` (audit), `tof_mismatch` (audit).

## 3. Per-instance ground truth (the manifest)

Every defect record carries: a stable **locator** (an invisible bookmark at the instance, or a
`text:` content locator where a bookmark would itself change the outcome, e.g. the merge pass), a
**revision_relation** (`unrelated` / `inside_revision` / `adjacent_to_revision`), and an explicit
**expected_disposition** — what the engine should do to *this* instance. Dispositions are exact:
`restyle_to_LI`, `strip_direct_formatting`, `set_LITable`, `columns_dropped`, `unwrapped`, `inline`,
`fielded`, `split`, `merged`, `typography_applied`, `footnote_restyled`, `portrait_restored`,
`removed`, `audit_flag`, or **`hold`**.

A `hold` is asserted **only** where the operation would actually disturb tracked content — e.g. a
literal caption whose text is itself a tracked insertion (fielding would drop the insertion), a
revised paragraph's direct formatting (preserve mode leaves it), inserted text with straight quotes
(typography preserves the payload). Where a structural op preserves the edit — inlining a tracked
floating image, dropping an empty column beside a cell revision, unwrapping a wrapper whose content is
inserted — the expected disposition is the **applied** outcome (`inline` / `columns_dropped` /
`unwrapped`), flagged for individual review, **not** a hold. "A rollback is not correct merely because
tracked content is nearby."

Every tracked change is recorded as an **actual occurrence** (kind, id, author, date, payload,
locator, part); all counts are **derived** from that list, never hand-incremented. Generation **fails
loud** if a declared asset (image/comment) cannot be created.

## 4. Independent validation (before any conformance testing)

`synthetic/validate_fixture.py` is an **independent oracle** — it does not use the conformer's gate.
For each report it checks: XML well-formedness of every part; document (not template) content type;
the **final `sectPr` is the last body element** and no bare `sectPr` appears mid-body; every floating
anchor places its wrap element **before** `docPr`; no paragraph-mark `rPr` precedes `pStyle`; every
relationship/media target resolves; and **manifest reconciliation** — every recorded revision id is
present with matching author, every locator resolves, every comment exists with matching author, every
List-of-Figures/Tables hyperlink anchor has a bookmark target. It exits non-zero on any failure. All
four reports currently pass.

## 5. Test procedure (Gate B, by Claude)

For each report: (1) assert `preserve` routing; (2) `analyze()` → JudgmentCalls, mechanical actions,
audit findings, analyze-stage exceptions; (3) `apply_with_decisions(ACCEPT ALL CONFORMANCE
SUGGESTIONS)` and capture the **fresh conformer's apply-stage exceptions**; (4) **save and re-open**
the conformed `.docx`; (5) the two guarantees — the engine's preservation gate **and** an independent
reconciliation of every recorded revision against the re-opened output — plus output validity; (6)
score **each** manifest instance at its locator against its `expected_disposition`. `python
synthetic/measure.py` runs it and exits non-zero on any FAIL.

## 6. Expected results & pass criteria

Each instance receives one verdict: **resolved** (change applied correctly), **expected_hold**
(protected instance correctly left untouched), **missed** (a required change did not happen),
**incorrectly_changed** (protected content was modified — a serious defect), or **indeterminate**.

- **P1 (blocking):** `preservation_clean` AND independent reconciliation (0 missing revisions) AND
  `output_valid`, for every report.
- **P2:** every non-tracked ASK class is detected (its JudgmentCall kind present) at ≥ its injected
  count. Body vs bullet classification are counted against the same `style` kind but scored per
  instance in P3, so a miss in one cannot hide behind the other.
- **P3:** zero `missed` and zero `incorrectly_changed` instances.
- **P4:** every rolled-back pass is explained — a known tracked-adjacent hold, or an open RCA.
- **P5:** the figure audit reports the injected `figure_numbering` and `tof_mismatch`.

A report is **PASS** when P1–P5 hold, **PARTIAL** when P1 holds but a P2/P3/P4/P5 item is open,
**FAIL** when P1 fails. The suite passes when all four reports PASS.

## 7. Root-cause analysis (RCA) for every issue

Each discrepancy opens an RCA record: `RCA-<n>`; report/class/instance (manifest defect id(s));
observed verdict vs expected disposition; minimal reproduction (added to `tests/` if not already
covered); **root cause with the layer named — fixture, manifest, scorer, or engine** — established by
reading code and watching a test go RED on the real defect; severity (blocking / major / minor). A
failing test reproduces a *symptom*; the diagnosis must also present evidence linking the cause to that
failure.

## 8. Corrective action plan (CAP) for every issue

Each RCA gets a `CAP-<n>`: the fix (engine change, or fixture/manifest/scorer correction, or a ruling
that it is a disclosed limitation); a regression test (run ≥8× for flaky-prone areas); re-measure to a
cleared scorecard signal; verification (preservation still clean + full suite green); disposition
(Fixed / Accepted-as-limitation / Deferred). **"Accepted as limitation" remains a disclosed
limitation** in `docs/tracked_changes_plan.md` — it never silently converts a failed capability into a
suite pass.

## 9. Realism, scope, and honest limitations

- **List of Tables** is emitted; the literal caption carries its own bookmark target so its
  List-of-Figures hyperlink resolves; the guaranteed-coverage instances are **distributed through the
  body**, not collected in a visible test-catalogue section.
- The **TOC** is a real field with placeholder cached text and the figure/table lists use placeholder
  page numbers — Word regenerates both on open; they are not asserted.
- **Pagination is estimated** (~58–67 pages) from word/figure/table volume; a pixel-accurate page
  count and representative rendered pages require opening in Word (no headless renderer is available
  here). Rendered/visual sign-off is a manual step and is **not** inferred from the manifest.
- These tiers stress **defect density**, not **revision density** (they carry tens of revisions). The
  revision-density stress case is the real 11,374-revision Warhoe draft; a high-revision synthetic
  variant can be added if wanted, but is out of scope for the conformance-coverage goal here.

## 10. Preliminary dry run (illustrative; the official scored run is Gate B)

All four reports: **P1 holds** (preservation clean, independent reconciliation 0 missing, output
valid), no `incorrectly_changed` instances, and every non-`hold` instance resolves except two:

- **RCA-1 candidate (major, ENGINE layer):** `page_break` and `empty_para` non-tracked instances are
  `missed` in every tier — `_prune_preserving` (#2/#4) rolls the whole pass back because the
  content-stream gate counts a page-break token (`<w:br w:type="page"/>`) as content. **Isolated
  reproduction and a fix are Gate-B work.** The proposed CAP is **narrow**, per the review: authorize
  removal only of *identified, eligible manual page-break paragraphs*; do **not** globally ignore
  page/column breaks in the gate; keep all other breaks (line breaks, column breaks elsewhere)
  protected; add positive tests for the permitted deletion and negative tests proving unrelated or
  protected breaks cannot disappear.

The clean control produces zero conformance changes beyond the expected baseline (no false positives).

## 11. Response to the Gate-A review

1. **Structural fixture errors — fixed.** `_move_to_front` is gone: the List-of-Figures/Tables entries
   are now inserted directly after their headings, so the **final `sectPr` stays last** (verified).
   The floating anchor now places `wrapNone` **before `docPr`**; the paragraph-mark `rPr` is inserted
   after `pStyle`. `validate_fixture.py` checks all three independently. Deliberately malformed markup
   lives only in named negative fixtures, never in the builders.
2. **Manifest as ground truth — rebuilt.** Per-instance locators + explicit expected dispositions +
   `revision_relation`. Every revision is a recorded occurrence; counts are derived. The phantom
   insertion (a deletion mislabelled via `_track`) and the uncounted footnote insertions are fixed;
   `maybe_track` no longer decorates a paragraph already recorded as a defect. The "tracked
   floating-image" now wraps the **drawing run**, not a caption. Generation fails loud on a missing
   asset. `validate_fixture.py` reconciles every recorded revision/comment/locator against the saved
   package independently.
3. **`measure.py` enforces P1–P5 — rebuilt.** Per-instance verdicts, explicit PASS/PARTIAL/FAIL, and a
   non-zero exit on FAIL. It saves and re-opens the conformed `.docx`, captures apply-stage exceptions
   from the fresh conformer, distinguishes body vs bullet at the instance level, and scores each
   structural class by a **postcondition at its locator** (a wrapper gaining a style still counts as a
   wrapper; a caption losing its style is still not a field). The decision set is named "accept all
   conformance suggestions."
4. **Validity — independent.** `validate_fixture.py` separates well-formedness, package/reference
   integrity, and structural-order checks, and reconciles preservation against the manifest
   **independently of the engine's gate**. (Full schema validation and true Word-open evidence remain
   a manual step — noted, not claimed.)
5. **Paired coverage — corrected + adversarial suite.** Every trackable class now has a non-tracked
   **and** a tracked instance with a per-instance expected disposition (often `hold`). The hard
   constructs (paragraph-mark deletion, move, cell/row revisions, corrupted style definitions,
   comment-inside-deletion) are a **separate** adversarial suite, and unsupported constructs map to an
   explicit restriction (`cellDel`).
6. **Reproducibility + tiering — corrected.** Fixed integer seeds recorded with provenance;
   `computed_quality` is an element pass-rate over a real denominator; a clean control measures false
   positives. Density labels are informal. The revision-density point is acknowledged in §9.
7. **Expected outcomes + pruning CAP — corrected.** The contradictory tracked-caption and
   tracked-typography expectations are fixed to per-instance holds that match preservation. The
   pruning CAP is constrained to eligible manual page-break instances with positive/negative tests;
   the blanket gate relaxation is **not** proposed.

## 12. Deliverables & sign-off gates

- **Gate A (this resubmission):** four reports + manifests + this plan + `generate.py`, `lib.py`,
  `content.py`, `measure.py`, `validate_fixture.py`, `tests/test_adversarial_synth.py`,
  `synthetic/assets/*.png`, on `feat/tracked-changes-judgment`. → GPT-6 signs off on documents + plan.
- **Gate B:** Claude runs the official scored test, opens RCA/CAP for every issue (starting RCA-1),
  fixes on the branch, re-measures to green. → GPT-6 reviews the scored results + RCAs/CAPs.
