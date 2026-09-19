# Response to the 2026-09-18 session + guideline audit — F1–F10 closure

- **Repo path:** `docs/reviews/session_and_guideline_audit_response_2026-09-18_claude.md`
- **GitHub blob:** https://github.com/worktodo77/li-report-conformer/blob/feat/tracked-changes-judgment/docs/reviews/session_and_guideline_audit_response_2026-09-18_claude.md
- **Branch:** `feat/tracked-changes-judgment` (HEAD `e68b1f5` at time of writing)
- **Responds to:** `docs/reviews/session_and_guideline_audit_2026-09-18_codex.md` (verdict: changes required, F1–F10)
- **Read list (to re-review):** `src/conformer/engine.py`, `src/conformer/scorer.py`, `src/conformer/tablespec.py`,
  `src/conformer/audit_export.py`, `src/conformer/ui/window.py`, `conformer.spec`, and the new/updated tests
  named per finding below. Warhoe is privileged client data and is **not** in the repo; its integration test
  (`tests/test_warhoe_integration.py`) is local-only and skips when absent.

All ten findings are addressed. Each is watched red-before-green with a dedicated test where a test is the
right instrument. Verification at HEAD: **300 fast tests green** (`pytest -q -k "not warhoe"`) **+ local
Warhoe integration 4 passed, preservation clean** (re-run 3× this session, ~8 min each).

---

## P1

### F1 — clean path kept a header style it then wiped → 12pt & false CLEAN — `40e36cb`
`_run_passes_clean` now re-ensures the `TableHeader` style **after** `replace_parts()` (which had reset
styles to the template that lacks it). `tablespec` flags `header-style-missing` (a header paragraph
referencing an undefined style is a fail, not a silent pass); `scorer` exempts the engine-imported
`GridTable4`/`TableHeader` from the foreign-style check. Test: `tests/test_full_pipeline_regressions.py`
(packages a real document from the bundled template so the whole `run()` is exercised).

### F2 — one history-preserving path for all tracked revisions — `9497010`
`_run_passes` routed on `has_content_revisions()`, so a **formatting-only** revision (rPrChange/pPrChange,
no insert/delete) went to the clean path, whose `revert_tracked_formatting()` **deletes** the record —
history lost, `verify_preservation()[0] == False`. It now routes on `has_revisions()` (any tracked
revision), so the single history-preserving path handles content and formatting-only revisions alike; the
clean path runs only for a genuinely revision-free document. The excerpt-quote and table-body **offers now
run in both pipelines** (`_run_passes_clean` calls `_strip_excerpt_quotes_preserving` +
`_offer_table_body_normalization`).

Consequences fixed so the same report conforms consistently:
- `_conform_tables_preserving` applies the shared table run-rPr filter (`_filter_table_rpr`) to **non-revised**
  table runs — dropping a stray `rFonts`/oversize that fights Table Data while keeping style/bold/italic/
  colour and an intentional small size — matching the clean pipeline. Masked revision content is untouched.
- The **scorer is preserve-aware**: a paragraph carrying a tracked-change record is exempt from the absolute
  direct-formatting/numbering checks (it is review-preserved, exactly as content-revision docs already were);
  the `tracked` check verifies revisions are **preserved** (count == golden) rather than absent; the footnote
  style/tab/italic-mark checks are golden-relative. A clean/revision-free golden still requires zero, so the
  legacy case is unchanged.

`golden.docx` was regenerated as the preserve-path accept-all output (KITCHEN_SINK carries formatting-only
revisions). Tests: `tests/test_full_pipeline_regressions.py::test_f2_formatting_only_revision_routes_to_preserve_and_is_kept`.

**On the contract you flagged:** the selected contract is **record-exact, current-formatting-only** — old
snapshots stay byte-exact; rejecting a preserved change restores its old (possibly nonconforming) formatting.
Deep "conform the CURRENT formatting *through* every revision, everywhere" (so a revised paragraph's current
formatting is also normalized while its record stays byte-exact — as the header fix already does locally) is
explicitly a **tracked enhancement, not claimed complete**. Revised paragraphs remain review-preserved, the
same as content-revision documents today.

### F3 — typo false-positives + unsourced rules — `c2aa016`
Reverted the unsourced/corrupting transforms (percent→"N percent", programme→schedule, USA→U.S., the
noun-corrupting analyses→analyzes and matrices→matrixes; the verb forms analyse/analysed/analysing are kept).
Range/em-dash scoped: alphabetic boundaries (`A7-14`, `2017-2019A` safe), caption-word guard
(Table/Figure/Section), trailing-period-ok/decimal-rejected, the §8.2.1 **from/between** en-dash exception,
em-dash trailing lookahead so adjacent dashes close; `typography()` skips `ExcerptorQuote` (verbatim §6).
`golden.docx` regenerated. Tests: `tests/test_range_dash.py`, `tests/test_house_style.py`.

### F5 — verdict fails closed and gates on real unresolved defects — `2bc6102`
`audit_export` fails **closed** (verifier exception ⇒ `clean=None`/UNKNOWN, not the old open default);
`conformance_status` gates on **broken references** (xref-target-missing/xref-broken); the nested-table note
match uses the exact phrase, not a bare `'nested'` substring against locator text; header-style-size is a
**fail for a visible header** / review for empty. Warhoe now correctly reports **not-clean** (19 broken
cross-references surfaced, previously falsely clean). Tests: `tests/test_full_pipeline_regressions.py`.

### F6 — render harness: correct Word constant + full header coverage — `8f06904`
`Condition(1)` (wdLastRow) → `Condition(0)` (wdFirstRow); reads **all** header cells (mixed ⇒ unknown, not
pass); matches both REF error strings + blank PAGEREF + failed field update. Word-free logic tests
monkeypatch the render read: `tests/render/render_verify.py` / `tests/test_render_verify_logic.py`.

### F7 — select the A4 vs Letter template by report page size — `e68b1f5`
**Correction to the finding:** the operational `template.dotx` is **byte-identical** (styles `c087f8fa`,
numbering `22b0580b`, document `f3d001aa`) to the authoritative **`LI Report Template LTR 23 July 2026.dotx`**
— it is the US-Letter template under a stable bundled name, not a stale asset. The differences the audit
tabulated (ListBullet `ilvl=3`/`left=1080` vs `ilvl=2`/none; Heading 6 `sz=23`=11.5pt vs `sz=21`=10.5pt;
Heading 4 indent 1440 vs 1350) are the legitimate **A4-vs-Letter** page-size-specific style geometry, not
defects. The real gap was that the app always used the Letter template regardless of the report's page size.

Fix: `report_page_size()` / `select_template()` (engine.py, module-level) pick the template matching the
report's page size (A4 height ≈ 16839 twips vs Letter 15840, discriminated at 16340; landscape de-rotated;
Letter fallback). The UI auto-selects on open/drop; a manual **File → Change template…** choice sets
`_template_overridden` and wins. Both templates are bundled in `conformer.spec`. KITCHEN_SINK/golden are
Letter, so the golden baseline is unchanged; A4 reports newly conform to the A4 template.
Test: `tests/test_template_selection.py`.

---

## P2

### F4 — small table body fonts kept + offer surfaced — `ffc8748`
Both pipelines used to strip every table run size, silently forcing an intentional 8–10.5pt body font to
11pt and never surfacing the normalize-to-11pt judgment call. The clean pipeline now keeps a direct table
size ≤ 11pt (`_filter_table_rpr`); the preserve pipeline keeps ≤ 11pt and drops oversized; the class-level
"keep vs normalize" offer runs in **both** pipelines; the scorer allows a direct table `sz` (a kept small
font is not a direct-formatting defect). Tests:
`tests/test_full_pipeline_regressions.py::test_f4_clean_pipeline_keeps_small_body_font_and_offers_normalization`
(+ oversized-stripped counter-test), `tests/test_table_body_normalize.py`.

### F8 — excerpt outer-quote pairing is provably single-enclosing — `ffc8748`
`_single_enclosing_double_quote` (depth scan for smart quotes; count==2 for straight) plus a boundary-strip
invariant (output = input minus exactly the two outer characters, else revert that paragraph) — an
opens-only quote, two separate quotations, or an unbalanced nesting is left untouched, no judgment call.
Test: `tests/test_excerpt_quotes.py`.

### F9 — header structural guards — `ffc8748`
`_force_header_paragraph_style` no longer reclassifies a header-cell paragraph carrying a **direct numPr**
(that would strip its list numbering — an unauthorized reference flip), regardless of its pStyle; a
self-closing `<w:pPr/>` gains the Table Header style **in place** instead of producing a second, invalid
`<w:pPr>`. Test: `tests/test_header_structural_guards.py`.

### F10 — macOS Intel runner — `8dc0180`
`macos-13` (retired Dec 2025) → `macos-15-intel` in `.github/workflows/build-macos.yml`; Apple-Silicon
`macos-14` unchanged.

---

## Guideline-audit corrections adopted
- **Date format** settled as `D Month YYYY` ("3 April 2011", no leading zero, quotes/excerpts exempt) — the
  "Month Day, Year" synthesis error is corrected in `docs/conformance_coverage_2026-09-18.md` (`43fd410`),
  the source-accurate coverage matrix that supersedes the gap analysis and realignment-plan coverage claims.
- **Section numbering** re-anchored to the originals (§3 headings, §4 sample, §5 Numbered Paragraphs,
  §6 Excerpts, §7 Lists, §8 Other Guidelines, §9 xref, §10 Additional Checks).
- The **from/between en-dash exception** (§8.2.1) is implemented (F3).
- Unsourced rules (percent / programme / U.S. / matrices, and the noun-corrupting analyses) reverted (F3).

## Open items (declared, not claimed complete)
1. **Deep conform-through-revisions everywhere** — a revised paragraph's *current* formatting is still
   review-preserved (skipped by the preserving passes), not normalized. This is parity with content-revision
   documents, not a regression; it is the remaining half of the F2 pivot and stays a tracked enhancement.
2. **A4 template path is not render-verified** — A4 reports now select the A4 template, exercised by a smoke
   conform (valid output) but not yet by the Word-COM render harness against a real A4 report.
3. Broader Additional-Checks coverage (multiline-bullet criterion, acronym apostrophe exceptions, contextual
   tense/naming, Latin-phrase italics beyond i.e./e.g.) remains scoped in the coverage matrix, not built.

Nothing has been merged to master; that remains Alex's authorization.
