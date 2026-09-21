# Proactive adversarial self-review — 21 September 2026

- **Repo path:** `docs/reviews/self_review_2026-09-21_claude.md`
- **Branch:** `feat/tracked-changes-judgment`; fixes in commit **`13c282e`** (on top of `dc6b59e`, the T1/T2 response state).
- **Purpose:** this is NOT a response to a GPT review. While waiting on the next external review, I ran an
  independent adversarial pass (four critic agents, each in its own worktree) to find NEW defect classes
  before they ship. Every finding was reproduced red with a synthetic full-package fixture, fixed red-green,
  and no baseline was regenerated.

**Verification:** 342 fast tests (`pytest -q -k "not warhoe"`) + local Warhoe integration 4 passed,
preservation clean.

## Fixed (13)

### Tables
- **D1 (P1):** `_filter_table_rpr` silently stripped meaning-bearing run formatting — super/subscript
  (`w:vertAlign`, e.g. CO₂), strike, highlight, and symbol/complex-script fonts — from every table cell
  while reporting CLEAN. It now uses the shared `keep_rpr_children` policy (plus the ≤11pt size keep), so a
  scientific subscript or a Symbol glyph survives; ordinary body fonts/underline are still normalised.
- **D2:** the clean pipeline wiped **every** `<w:shd>`, deleting a meaningful subtotal-row fill; it now
  strips only the **header** row's fill (so the teal shows) and keeps body shading — parity with the
  preserving path.
- **D3:** the clean pipeline had no nested-table guard, so it restyled the nested table and summed its
  `gridCol`s into the outer table width; it now leaves a nested table untouched and notes it, matching the
  preserving path.
- **D4:** a table that marks a **later** row as a repeating header (a genuine multi-row header, or a spacer
  row above the real header) was only partly conformed yet reported CLEAN; `tablespec` now emits a
  `multi-header-row` issue at `unresolved` severity, which gates the verdict.

### Typography / house style
- **house_style split-run quotation (P1):** `house_style` ran per run, so a quoted defined-term split across
  runs (`… "` | `the Contractor breached` | `" …`) was silently lowercased — corrupting quoted evidence —
  while CLEAN. The revision-aware paragraph-logical machinery was generalized to `_transform_paragraph` and
  `house_style` now runs through it (settled runs only, each edit authorized by `house_ok`).
- **Move revisions (P1/P2):** `_para_text_tokens` now treats `<w:moveTo>` as read-only **context** (it was
  editable, so editing a moved-in payload tripped the gate and rolled back the WHOLE typography pass) and
  excludes `<w:moveFrom>` from context (its trailing words were poisoning the from/between range exception).

### Sections / template
- **fix_sections (P1):** when the next Heading 1 immediately followed the prior section break with no
  landscape-content paragraph between, the repair wrote a **second** `<w:sectPr>` into the paragraph that
  already ended the prior section (invalid OOXML); it now hosts the landscape section on a fresh paragraph.
  The positional `re.sub(..., 1)` count is now a keyword argument.
- **report_page_size:** classifies A4 only inside a tight height window (US Legal 20160 / A3 23811 are no
  longer misread as A4 — they fall to the safe Letter default) and uses a **majority vote** over all
  sections, so one stray/corrupted leading section can no longer decide the whole report's template.

### Verdict / render / UI
- **render `toc-page-1`:** a wholly-collapsed PAGEREF set now fails regardless of N — the `max(3, …)` floor
  let a ≤2-field TOC that renders 100% page "1" pass silently.
- **audit_export:** the NOT-CLEAN conformance line now counts `paragraph_reference_flips` (the UI already
  did), so the two consumers agree on the blocking cause.
- **completion card:** no longer claims "Word will renumber on open" over broken cross-references — those
  need a manual target fix, which the engine's own gating rationale states.

## Considered and declined (not defects)
- **fix_sections margins when there is no prior portrait section:** Word margins are orientation-relative, so
  keeping the section's existing margins is defensible; the case is a degenerate all-landscape document.
- **`finalize_save()` dead / `save()` ungated:** the live GUI save path already gates on the authoritative
  verdict before writing (review-only vs normal filename); `finalize_save` is a tested belt-and-suspenders
  entry point and the CLI is a developer path. No live mis-labeled output. Left as a hygiene note.
