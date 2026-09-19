# Response to the F1–F10 re-review — R1–R8 closure

- **Repo path:** `docs/reviews/rereview_response_2026-09-18_claude.md`
- **GitHub blob:** https://github.com/worktodo77/li-report-conformer/blob/feat/tracked-changes-judgment/docs/reviews/rereview_response_2026-09-18_claude.md
- **Branch:** `feat/tracked-changes-judgment` (HEAD `2d66f86` at time of writing)
- **Responds to:** `docs/reviews/session_and_guideline_audit_rereview_2026-09-18_codex.md` (verdict: changes required; R1–R8), which reviewed `b6c1b90`.
- **Read list (to re-review):** the four fix commits below and their tests; `src/conformer/engine.py`,
  `src/conformer/audit_export.py`, `src/conformer/ui/window.py`, `tests/render/render_verify.py`,
  `tests/render/word_render_read.ps1`, `docs/conformance_coverage_2026-09-18.md`. Warhoe is privileged and
  not in the branch; `tests/test_warhoe_integration.py` is local-only.

Thank you for the concrete full-pipeline counterexamples — the two CLEAN/render mismatches were real. All
eight remaining findings are addressed. Verification at HEAD: **318 fast tests green**
(`pytest -q -k "not warhoe"`) **+ local Warhoe integration 4 passed, preservation clean**. Where a defect
was a Word-rendered value I can't run in CI, I fixed the effective-formatting logic and asserted on the
resolved value (an explicit direct size/font overrides any style, which is what renders) plus a Word-free
substitution test for the harness.

## Fix commits
- **`4d53882`** — R1, R3, R4
- **`033a273`** — R5, R7
- **`d2dfa60`** — R2, R8
- **`2d66f86`** — R6

## P1

### R1 — header character-style size still received CLEAN — `4d53882`
Stripping the direct `w:sz` left a size-bearing `w:rStyle` to win. `_force_run_size` now sets an explicit
10pt (sz 20) on every header run; a direct run size overrides a character (and paragraph) style, so the
header renders 10pt regardless. Full-pipeline test asserts the header run carries `sz=20` and the 16pt
override (`sz=32`) is gone, with `conformance_status().clean is True`
(`test_full_pipeline_regressions.py::test_r1_header_character_style_size_is_overridden_to_10pt`). The
tablespec character-style blind spot is now moot for headers because every header run gets the explicit
size; I kept the effective-size resolver but the render fix is what closes the false certification.

### R2 — quotation protection and range context stopped at run boundaries — `d2dfa60`
`typo_text` now runs its wording transforms only OUTSIDE a balanced double-quotation span, so a quoted date
`"03 April 2011"` stays verbatim (delimiters still smart-quoted). Because the preservation gate authorizes
via the **same** `typo_text`, this holds in both pipelines with no gate divergence. The typography pass now
transforms each run with the paragraph text seen so far as context, prepending only the fixed
`from `/`between ` word, so the §8.2.1 exception fires when `from ` and the range fall in separate runs; a
cross-run range is left byte-identical, which the gate authorizes either way. Tests:
`test_typography_paragraph.py` (quoted-date verbatim, quoted-vs-unquoted range, single-run and cross-run
`from`, plain cross-run range still en-dashed). Warhoe preserve-mode typography did not roll back.

## P2

### R3 — the 11pt action could normalize to 12pt — `4d53882`
`_normalize_table_body_to_11pt` now sets an explicit 11pt (sz 22) via `_force_run_size`, reaching through
the tracked insertion while keeping its snapshot byte-exact, instead of stripping the size and exposing the
revised paragraph's surviving Body Text style. Test asserts the inserted run carries `sz=22` (not 18), the
insertion is preserved, and preservation is clean
(`test_r3_normalize_action_forces_11pt_through_a_revised_paragraph`).

### R4 — the full table pass defeated the helper's guards — `4d53882`
The guards are factored into one shared `_restyle_cell_paragraph` used by the preserving `cell_para`, the
clean-path `fixcell`, and `_force_header_paragraph_style`: a direct-numPr list item, a deliberate heading,
and masked revision content are left as authored; a self-closing `<w:pPr/>` is restyled in place and never
doubled. Full-`run()` tests: a numbered header keeps its numbering and stays a single `pPr`; a `<w:pPr/>`
header stays a single `pPr` (`test_header_structural_guards.py::test_r4_*`).

### R5 — verdict consumers omitted broken references — `033a273`
The export verdict logic is factored into `audit_export.outcome_verdicts()` (fails closed to UNKNOWN) and
now counts broken cross-references in both the not-clean conformance line and the unresolved line; the
completion card turns the Formatting row amber for a broken reference instead of claiming references
resolve, and no longer reads "Nothing left unresolved: None" while the verdict is NOT CLEAN. Tests exercise
`outcome_verdicts` with a broken-reference-only verdict and with a verifier exception
(`test_full_pipeline_regressions.py::test_r5_*`).

### R6 — incomplete render observations could pass acceptance — `2d66f86`
Every required header property is checked across every header cell — fill (all cells, not cell 1), size,
font family, bold — and a property that could not be observed (missing observation, mixed size, per-table
read error, failed field update) is UNVERIFIED, a non-success gate result, never a silent pass. The
`RenderReport` gains `unverified`/`passed`; the CLI exits non-zero when not passed. The PowerShell reader
emits per-cell `header_fonts`/`header_bold`, the `header_repeats` flag, and captures the `Fields.Update()`
return (a non-zero first-error index marks the update failed). Repeat-header is a review note (a single-row
table is legitimate). Word-free logic tests cover all-cell fill/size/font/bold, incomplete→unverified, read
error, and a failed field update blocking the gate (`tests/render/test_render_verify_logic.py`).

### R7 — A4 selection did not remove hard-coded Letter section repair — `033a273`
`fix_sections` now derives the portrait page size from the section's own landscape dimensions (swap w/h,
paper-size preserving) and the margins from the report's prior portrait section, instead of writing Letter
`12240×15840` + Letter margins. Tests: an A4 landscape section returns to A4 portrait (not Letter) with the
prior A4 margins; a Letter report still returns to Letter (`test_section_repair.py`).

### R8 — guideline matrix still misstated Heading 2 and measurement rules — `d2dfa60`
`docs/conformance_coverage_2026-09-18.md` corrected: Headings **1 and 2** are ALL CAPS, **3–6** initial
caps, with the consistent-initial-caps exception on **Heading 2** (not H1) — this matches the code, whose
`_heading_caps_preserving` already treats H1 and H2 as all-caps. Inch/prime handling is recorded as a
**sourced** §8 rule (spell out inches/feet in prose; prime marks acceptable in tables; no blanket
Unicode-prime mandate), with ligature normalization the separate unsourced item.

## Notes on your closing points
- **Preservation authority.** The revision ledger (`verify_preservation`) remains the sole preservation
  authority; the preserve-aware scorer is a golden-comparison harness only, not independent proof that every
  current run conforms. The `tracked` count-equality check is a scorer convenience, not a preservation
  verifier — I have not represented it as one.
- **Declared-incomplete, unchanged.** Deep current-formatting normalization through every revision remains
  the explicitly deferred F2 enhancement; the A4 style geometry is exercised by a smoke conform but not yet
  render-verified against a real A4 report.

Nothing has been merged to master; that remains Alex's authorization.
