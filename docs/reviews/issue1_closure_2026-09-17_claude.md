# Closure record — corrective-work review (GitHub issue #1)

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
