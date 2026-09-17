# Closure record — corrective-work review (GitHub issue #1)

## Round 3 (this round) — failure-safety and actual-reference verification

Round-2 improvements are retained; the reviewer accepted R4/R7 and confirmed several concrete fixes but
kept R1/R2/R3/R5/R6 open with new P1 reproductions. Round 3 closes those reproductions with boundary /
output tests (not source-string checks). All reproductions live in `tests/test_issue1_regressions.py`
(watched RED before each fix, GREEN after). Fast suite **170 passed**; local real-report suite **3 passed**
(`tests/test_warhoe_integration.py`, ~5m).

| Finding | Round-3 P1 reproduction | Fix |
|---|---|---|
| R2 | failed import hidden; dependent style retained template numId and rebound to an unrelated destination list; `_unresolved_imports` had no consumer | import is now ATOMIC — a style whose dependency does not resolve is **not added/rewired**; the failure is recorded with a style+numId locator and propagated through `conformance_status()` (not clean). `engine.py _repair_styles` |
| R1 | intended label repair also reset an unauthorized list `start`; `intended=True` merely because the style reached a recorded repair | house repair now **preserves the original instance start/lvlRestart** (imports a dedicated copy and copies them back per level); `numbering_report` marks a change intended **only when the actual after-level equals the recorded expected delta** — a start reset under a repair is an unauthorized flip. `engine.py _emit_import`, `_repair_styles`, `numbering_report` |
| R3 (references) | a paragraph's own numId reassigned (900→901) with unchanged text/definitions was **not** caught; definition-only checks cannot prove unchanged use | new `paragraph_reference_report()` resolves each body paragraph's ACTUAL numbering (direct numPr else style) before vs after with same-style stable correspondence, authorizing only recorded house-repair deltas; wired into the blocking verdict. On real Warhoe it surfaces 51 genuine reference changes (heading auto-numbering removed by a pre-existing pass) that the prior style-only check missed |
| R3 (save boundary) | `_on_apply_done` caught every verdict exception and substituted `{'blocking': False}`, so an exception SAVED; completion view fell back to a count-based predicate | the save boundary now **fails closed**: a raised/unknown verdict stops ordinary saving and needs an explicit unverified-review-copy decision; completion view reports UNKNOWN, never an inferred pass. Branch behaviour is covered by save-call assertions (clean/blocking/review/unknown/exception/cancel) |
| R5 | the grid check passed on ANY single 808080 border child; no enabled/width/grid requirement, no header-text check | the style-definition check now requires the full grey ½pt grid on all six sides (enabled, sized, coloured) AND both navy fill and white header text on the firstRow conditional. `tablespec.py _borders_form_house_grid`, `_style_defines_house_table` |
| R6 | `docDefaults/rPrDefault/color=FF0000` + explicit black override → black treated as redundant, exposing the red default | effective-colour resolution now includes `docDefaults`; a colour is redundant only if removal leaves the same effective colour, and absence of a style colour is no longer equated to black. `engine.py _doc_default_color_el`, `_color_is_redundant` |
| validation | the carrier regex could not distinguish subscript/superscript values, used a set, and pooled stories | replaced with a STRUCTURAL, per-occurrence, per-story, value-sensitive extractor (`meaning_carriers`) proven by negative unit tests (drop one repeated carrier; flip subscript→superscript; a footnote carrier cannot satisfy a document loss) and used by the real-report test |

Authoritative Warhoe verdict this round: **not clean / blocking** — 0 unintended style-numbering flips, 3
dysfunctional list styles repaired (start preserved), definition integrity clean, 0 unresolved imports,
meaning-bearing formatting preserved per-occurrence, **but** 51 paragraph-reference changes (heading
auto-numbering removed by a pre-existing pass) and residual table conflicts remain surfaced, never
claimed clean. The heading-numbering behaviour is a pre-existing engine pass now made VISIBLE by the new
verification; it is reported as an open item, not silently accepted or suppressed.

---

Branch: `feat/tracked-changes-judgment`. Round-1 HEAD `489531c`; round-2 HEAD `a37f0aa`.
Acceptance target: Claire's requirements — actually repair dysfunctional bullets and achieve effective
house table formatting while preserving meaningful content and review history. Simply reporting a defect,
or preserving corrupt input, is not completion. Gates were not weakened and no unresolved/unadjudicated
result is treated as clean conformance.

Round 1 fixed the named counterexamples; the reviewer correctly reopened R1/R2/R3/R5/R6 because the general
requirement was not met, and accepted R4/R7. Round 2 addresses the reopened reproductions. Reproductions
live in `tests/test_issue1_regressions.py` (fail before each fix, pass after).

| Finding | Round-1 | Round-2 (commit `a37f0aa`) |
|---|---|---|
| R1 repair the approved definition | wrong-format only | + same-format corrupt glyph repaired (property-level trigger) |
| R2 dependency closure | one-hop | + recursive chain, cycle/dead-end → unresolved, never empty |
| R3 complete + enforcing verdict | fmt/levels 0–2, advisory | + full level record incl lvlRestart, reassignment caught, one verdict wired to audit/UI/save |
| R4 table namespace/parse | **accepted, retained** | unchanged |
| R5 effective table conformance | name-based | + property-based style check, equivalent-size not flagged, review→not-clean, real repair of size/margins |
| R6 effective colour | direct theme only | + inherited theme-backed colour preserved |
| R7 highlight decisions/audit | **accepted, retained** | unchanged (live packaged-app acceptance still outstanding) |

## R1 — repair the approved definition, not only its format name
Round 2: house repair triggers when the resolved house PROPERTIES (list `numFmt` AND the level glyph
`lvlText`) differ from the template's approved definition — so a bullet whose glyph is corrupt
(`numFmt=bullet`, `lvlText=BROKEN`) is repaired, while a functional list that differs only in `start`/
`lvlRestart` (instance semantics, not authorised to change) does not trigger and is left intact. Each
repair records its expected before→after. **Evidence:** `test_r1_dysfunctional_bullet_repaired_numbered_
unchanged` (wrong format), `test_r1_same_format_corrupt_glyph_is_repaired` (same format, corrupt glyph).
Real Warhoe: 3 dysfunctional list styles actually repaired; numbered paragraphs unchanged.

## R2 — dependency closure, recursively
Round 2: `NumberingGraph.resolved_levels_xml` follows the `numStyleLink` chain RECURSIVELY (cycle- and
dead-end-safe); `resolved_abstract_xml` inlines the fully-resolved levels or returns None, and an
unresolvable import is recorded (`_unresolved_imports`) rather than emitted as an apparently-valid empty
definition. **Evidence:** `test_r2_import_resolves_multi_hop_numstylelink_chain`,
`test_r2_unresolvable_chain_never_becomes_empty_definition`, plus the round-1 inheritance-preservation test.

## R3 — complete verification and one enforcing verdict
Round 2: `numbering_report` compares the FULL resolved level record (`numFmt`, `lvlText`, `start`, `isLgl`,
`lvlRestart`) per style, so a style REASSIGNED to a same-format list with a different start, and a
`lvlRestart` change, are caught; `definition_integrity_report` adds `lvlRestart`. `_preserve_inherited_
numbering` is record-based and also suppresses UNINTENDED gained numbering (numId-0 override; the graph
treats numId 0 as no-list). `conformance_status()` is the single authoritative verdict — `blocking` =
unauthorised semantic damage (unintended flips, integrity violations, tables failing effective format),
`clean` also requires nothing unadjudicated (review/unresolved). It is now wired into the audit summary,
the UI three-outcome, and a save-boundary warning; the save is no longer treated as clean on ZIP/XML
validity alone. **Evidence:** `test_r3_style_reassignment_to_different_start_is_detected`,
`test_r3_lvlrestart_change_detected`, `test_r3_conformance_clean_gate_reflects_issues`,
`test_r3_conformance_clean_is_wired_into_audit_and_ui`.
**Correction to round-1 closure:** round 1 wrongly implied full paragraph/historical reference comparison
and an enforcing gate; that was not true then. Style-level resolution now covers reassignment; direct-
paragraph and historical-snapshot references remain covered indirectly (definitions are unchanged, verified
by `definition_integrity_report`) rather than by per-paragraph diffing — stated as a limitation below.

## R4 — accepted, retained (unchanged)
Namespace-context parsing and unresolved surfacing stand.

## R5 — effective table conformance and real repair
Round 2: the LITable style-definition check parses the actual PROPERTIES (grey grid on the table borders +
navy fill on the firstRow conditional's cell shading), so a style merely NAMED `808080 054F8A` fails; a
direct run size EQUAL to the house 11pt is no longer flagged while a conflicting one is; the preserve table
pass now REPAIRS conflicting direct cell margins and run sizes (not only detects them); review and
unresolved results route through `conformance_status()` so an unadjudicated review deviation is never
silently clean. **Evidence:** `test_r5_corrupt_litable_style_def_detected`,
`test_r5_equivalent_font_size_not_flagged_but_conflicting_is`, `test_r5_disabled_header_and_direct_font_
size_fail`. **Correction to round-1 closure:** round 1 claimed review cases were excluded from a clean
verdict; they were not (the verdict ignored `tables_review`). They are now.
**Remaining scope (declared):** a full approved-roles/variants framework (merged-cell-aware header roles,
per-property theme-resolved targets, header-shading repair) is staged; unresolved/review results are
surfaced with locators and are excluded from a clean verdict, never claimed clean.

## R6 — inherited theme-backed colour preserved
Round 2: `_style_color_map` retains the full `<w:color/>` element (theme/tint/shade), and
`_color_is_redundant` refuses to strip when EITHER the direct or the inherited colour is theme-backed —
so an explicit black over a theme-backed character-style colour is preserved. **Evidence:**
`test_r6_inherited_theme_backed_char_style_colour_not_stripped` (+ the retained direct-theme and
red-character-style cases).

## R7 — accepted, retained (unchanged)
Authoritative per-id decision map and audit wiring stand. Live packaged-app acceptance remains a separate
outstanding manual check.

## Corrections to round-1 evidence
- The real-report formatting test now compares per-carrier (text, property VALUE) across the DOCUMENT AND
  FOOTNOTES (`tests/test_warhoe_integration.py`), not a text-only set over the main document — addressing
  the omitted footnote carriers and un-compared values. (`test_warhoe_preserves_meaning_bearing_formatting`.)
- The R3 regression previously only injected a prebuilt outcome dict; a wiring test now asserts
  `conformance_clean`/`conformance_status` are used by the audit, UI and save path.

## Honest limits still open
- R5's approved-roles/variants framework and header-shading repair are staged; they never produce a false
  clean verdict.
- Direct-paragraph and historical-snapshot reference diffing is covered via definition integrity, not
  per-paragraph comparison.
- Live Word / packaged-app acceptance (accept/reject, field updates, list restarts) is a manual step for
  the maintainer; the model/engine tests are evidence, not a substitute.
