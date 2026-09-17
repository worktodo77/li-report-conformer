# Closure record — corrective-work review (GitHub issue #1)

Branch: `feat/tracked-changes-judgment`. Reviewed HEAD was `2e20e59`.
Acceptance target: Claire's requirements — repair dysfunctional bullets and achieve effective house table
formatting while preserving meaningful content and review history. Gates were **not** weakened and no
unresolved/unevaluated result is treated as clean conformance.

Every finding has a reproduction that fails on the pre-fix code and passes after. Reproductions live in
`tests/test_issue1_regressions.py` unless noted.

| Finding | Commit | Status |
|---|---|---|
| R7 — highlight decision honesty + audit | `746f0a6` | Closed |
| R6 — colour redundancy silently changing visible colour | `1ba486e` | Closed |
| R4 — table parse failures = false conformance | `f144a86` | Closed |
| R1 + R2 — repair dysfunctional bullets; import closure; inherited numbering | `ad0bbb5` | Closed |
| R3 — incomplete/advisory numbering + definition verification | `af3e803` | Closed |
| R5 — effective table formatting + speculative nested mutation | `9840099` | Closed (concrete gaps); one framework item scoped as remaining |

Full suite: **155 passed** (fast) + the local real-report suite (`tests/test_warhoe_integration.py`,
skips if the original is absent; never committed).

---

## R1 — repair existing corrupt house numbering (P1)  — commit `ad0bbb5`
**Root cause:** `_repair_styles` only *contained* the defect (kept the document's numPr), so a dysfunctional
List Bullet (resolving to decimal / missing) stayed broken; a before==after comparison hid it.
**Fix:** `_repair_styles` now HOUSE-REPAIRS a house-controlled list style whose document numbering resolves
to the wrong format vs the template's intended format — it imports the template's list (fresh ids) and
rewires the style. Headings are excluded (ambiguous → left to review). The change is recorded
(`self._house_repaired`) and marked `intended` so verification distinguishes it from an accidental flip.
Ordinary numbered paragraphs stay numbered.
**Evidence:** `test_r1_dysfunctional_bullet_repaired_numbered_unchanged` (broken ListBullet → house bullet;
NumberedParagraph stays decimal; recorded in `_house_repaired`). Real Warhoe: 0 unintended flips.

## R2 — import dependency closure; preserve inherited numbering (P1) — commit `ad0bbb5`
**Root cause (cx1):** the importer copied one abstractNum keeping its `numStyleLink`, which rebound to a
same-named but different destination style (decimal → bullet). **(cx2):** replacing a style's def changed
inherited numbering that `_keep_numpr` (local numPr only) could not protect.
**Fix (cx1):** `NumberingGraph.resolved_abstract_xml` inlines a linked style's levels and drops the
`numStyleLink`, so an import is self-contained. **(cx2):** `_preserve_inherited_numbering` pins back the
original resolved numbering of any style whose format changed without an intended repair — and does NOT
pin a style whose original basedOn chain reaches a house-repaired ancestor (it follows the repair).
**Evidence:** `test_r2_import_resolves_numstylelink_not_bound_to_destination`,
`test_r2_inherited_numbering_pinned_but_not_over_a_house_repair`. Real Warhoe: definition integrity clean.

## R3 — complete + enforcing verification (P1) — commit `af3e803`
**Root cause:** `numbering_report`/`definition_integrity_report` returned `[]` for real mutations (removed
definition, start 1→9, label `%1.`→`Article %1:`) — comparing only `numFmt` over levels 0–2 — and the
verdict was advisory.
**Fix:** `definition_integrity_report` resolves the full level record (`numFmt`, `lvlText`, `start`,
`isLgl`) across **every** level the original defines, flags removed/unresolvable definitions, and catches
meaning changes. `conformance_clean()` is the authoritative, enforcing verdict (no unintended flips, no
integrity violations, no tables failing effective format, nothing unresolved). The audit surfaces
`Conformance verified clean: Yes/No` gated on this — not on ZIP/XML validity — and the UI three-outcome
shows amber when not clean, so a partial/unresolved result is never presented as clean.
**Evidence:** `test_r3_definition_integrity_catches_documented_mutations` (all four mutations),
`test_r3_unchanged_definition_is_clean`, `test_r3_conformance_clean_gate_reflects_issues`.

## R4 — table parse failures are not conformance (P1) — commit `f144a86`
**Root cause:** the fragment parser declared only `w`+`mc`, so any table using an inherited prefix
(`w14`, `r`, drawing) failed to parse and returned `unresolved`, while `table_conformant` only checked
`fail` — so all 333 real tables were reported conformant without evaluation.
**Fix:** `_parse` accepts the document's namespace declarations (comprehensive fallback); `_doc_nsdecls`
extracts the real root declarations; `outcome_report` evaluates every body table with them and surfaces
failing / unresolved / review tables separately, each with a stable locator. `table_conformant` returns
False on any `fail` or `unresolved` — unknown never counts as conformant. Audit + UI three-outcome counts
include unresolved tables.
**Evidence:** `test_r4_prefixed_fragment_is_evaluated_not_parse_failed`,
`test_r4_unparseable_table_is_not_conformant`, `test_r4_outcome_report_surfaces_unresolved_tables`.

## R5 — effective table formatting; no speculative nested mutation (P1) — commit `9840099`
**Root cause:** the checker judged by the LITable *name* and missed effective formatting — a disabled
header marker (`tblHeader w:val=0`, `tblLook firstRow=0`) with a 72pt direct header run read as conformant;
every direct cell border was flagged even when equivalent to the house grid; the style *definition* was
never verified; nested tables were mutated by flat regexes.
**Fix:** the verifier treats disabled header markers/conditional as a failed header, flags direct run font
sizes (fail for header, review for body), flags direct cell borders only when they differ from the house
½pt `808080` grid, flags direct cell margins, and verifies the LITable style *definition* (grey grid +
navy header) when styles are supplied — detecting a corrupt/missing def. The engine table pass now leaves
a table containing a nested table **untouched** and reports it with a locator for independent review.
**Evidence:** `test_r5_disabled_header_and_direct_font_size_fail`,
`test_r5_equivalent_direct_border_not_flagged`, `test_r5_corrupt_litable_style_def_detected`, plus
`tests/test_table_effective_format.py`.
**Remaining scope (declared, not hidden):** a full approved-roles/variants framework with geometry-
preserving precise repair of *every* override (merged-cell-aware header roles, per-property theme-resolved
targets) is larger work. The concrete false-conformance gaps are closed; incomplete/ambiguous cases are now
reported as `review`/`unresolved` with locators and are excluded from a clean verdict — never claimed clean.

## R6 — colour redundancy judged by effective colour (P1) — commit `1ba486e`
**Root cause:** an explicit black run colour over a red character style was stripped as "redundant" vs the
paragraph style, so the run then inherited red — a silent visible-colour change; theme colours and the
clean pipeline's later template-style replacement were outside the comparison.
**Fix:** `_color_is_redundant` strips a direct colour silently only when removing it leaves the same
effective colour — the character style's colour when the run has an `rStyle`, otherwise the paragraph
style's. Theme colours are never silently stripped. The clean pipeline runs the colour pass after
`replace_parts`, so redundancy is judged against the final styles.
**Evidence:** `test_r6_black_over_red_char_style_is_not_redundant`,
`test_r6_theme_colour_is_never_silently_stripped`.

## R7 — highlight decision honesty + audit fidelity (P2) — commit `746f0a6`
**Root cause:** Remove-all then unchecking one item still removed it (`remove_all OR id in set`), and
grouped highlight decisions never reached the saved judgment audit (built only from `judgment_rows`).
**Fix:** one authoritative per-id decision map; a per-item choice always wins; the bulk toggle updates
every id (not just the rendered page); `_highlight_decisions()` is the single source consumed by apply;
`_highlight_decision_log()` records grouped keep/remove into `decisions_log` so the audit matches the
applied map. Control scope stated explicitly (body-text highlights).
**Evidence:** `test_r7_per_item_keep_survives_remove_all`,
`test_r7_grouped_highlight_decisions_reach_the_audit`.

---

## Limits of this closure
- The three outcomes (preservation / conformance / unresolved) remain reported **separately**; a clean
  preservation result never stands in for conformance.
- The real-report tests were strengthened (per-occurrence formatting carriers, intended-vs-unintended flip
  distinction) but Word-rendering / live-GUI / frozen-exe acceptance is a manual step for the maintainer.
- R5's approved-roles/variants framework is explicitly scoped as remaining; it does not produce false
  clean verdicts in the interim.
