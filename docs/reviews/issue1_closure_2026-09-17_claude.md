# Closure record — corrective-work review (GitHub issue #1)

## Round 5 (this round) — A–E implementation prescription

Implements the A–E prescription in order (failing tests first). New counterexamples live in
`tests/test_issue1_round5.py`, watched RED before each section and GREEN after. Fast suite **203 passed**;
local real-report suite **4 passed**. Retains the preservation gates and the accepted R2/R4/R6/R7 fixes and
the approved current-header-fill policy.

| Sec | Commit | Fix | Tests (RED→GREEN) |
|---|---|---|---|
| A | `5676d57` | Three-state `Resolution` (resolved/none/unresolved); pStyle links a MULTIMAP; instance vs level selection separated; order-independent; partial direct-numPr merge | `test_a_heading_selects_linked_level_not_ilvl0`, `test_a_ambiguous_instance_is_unresolved`, `test_a_definition_order_independent`, `test_a_numid0_is_no_numbering_not_unresolved`, `test_a_missing_instance_is_unresolved_not_none`, `test_a_partial_direct_ilvl_merges_with_inherited_instance` |
| B | `a3beb77`,`609b01d` | Reverse-use index BEFORE mutation; one repaired instance per source instance (overlay house props on affected levels, retain healthy levels/starts/overrides, add a missing level, symbol font); rebind ALL users (styles + direct); orphan (lost-numbering) styles; independent instances stay independent | `test_b_partial_corruption_keeps_shared_instance`, `test_b_healthy_direct_user_rebound_to_repaired_instance`, `test_b_independent_instances_sharing_abstract_stay_independent` |
| C | `19c2f45`,`a2bf50e` | Deleted the blanket `asig==style_after` exemption; compare instance identity AND level; authorize only a recorded repair delta, a policy-approved SAME-CATEGORY strip, or an engine-recorded reclassification; `_functioning_direct_numpr` keeps on category-flip / suppression | `test_c_pstyle_change_without_manifest_fails`, `test_c_dropping_functioning_direct_decimal_over_bullet_style_fails`, `test_c_same_format_instance_swap_changes_continuation_fails`, `test_c_valid_label_repair_passes`, `test_c_repair_plus_start_alteration_fails` |
| D | `4faa6ef` | Header background normalized to CONCRETE navy (white/auto/theme, tcPrChange preserved byte-identical); tablespec: theme fill unresolved, not assumed navy | `test_d_white_fill_with_dark_text_is_not_clean`, `test_d_auto_fill_not_assumed_navy_without_active_conditional`, `test_d_theme_fill_is_unresolved_not_navy`, `test_d_repair_normalizes_white_and_auto_and_theme_to_concrete_navy`, `test_d_tracked_current_header_fill_corrected_history_byte_identical` |
| E | `1d8cf87` | Verdict tied to mutation generation; `save()` stamps truthful/unknown on every path; `finalize_save(review_only)` guarded entry point; review-only artifact distinct even in replace mode; audit-write failure not swallowed | `test_e_finalize_save_requires_review_only_for_nonclean`, `test_e_verifier_exception_is_unknown_not_clean`, `test_e_edit_invalidates_finalized_verdict`, `test_e_review_only_output_is_distinct_even_in_replace_mode` |

Fresh real-report evaluation (four outcomes SEPARATE):
- **Preservation:** CLEAN — 11,374 tracked changes, 171 comments, 8 authors; 0 rollbacks; output validates.
- **Numbering correctness:** 0 unintended flips, 3 intended repairs (`1ai`, `ArticleSection`,
  `Listbulletasasentence`), 0 definition-integrity violations, 0 paragraph-reference flips.
- **Table conformance:** 87 tables failing effective format, 190 tables with review deviations (overlap).
- **Unresolved:** 0 unresolved imports, 0 uncorresponded paragraphs, 0 unresolved table parses, 98 table
  review notes; authoritative verdict honestly **not clean / blocking** on the table remainder.
- **Independent resolver evidence:** the A fixtures hand-specify expected results (Heading2 → (1,1), ambiguous
  instance → unresolved, order-independence). **Word accept/reject and rendered-numbering acceptance is
  PENDING** (a manual maintainer step; no runtime dependency added).

---

## Round 4 — list-instance semantics, complete reference coverage, honest artifacts, heading repair

The reviewer accepted R2 and R6 as closed (with R4/R7), and kept R1/R3/R5 open. Round 4 addresses the R1
and R3 reproductions and repairs the heading numbering; R5 (effective table repair) is staged with honest,
non-false-clean reporting. Reproductions are in `tests/test_issue1_round4.py` (+ `test_issue1_regressions.py`),
watched RED before each fix, GREEN after. Fast suite **177 passed**; local real-report suite **4 passed**.

| Finding | Round-4 P1 reproduction | Fix |
|---|---|---|
| R1 | repairing two levels of ONE shared multilevel list split it into two independent instances (continuation/parent-child lost) | house repair is planned PER ORIGINAL NUMBERING INSTANCE: styles sharing a source numId are rewired to ONE shared imported instance; independent lists stay independent; template instance overrides are dropped when preserving original starts. `engine.py _repair_styles` |
| R3 (typography) | ordinary typography (an apostrophe) changed a paragraph's text, so text-keyed correspondence dropped it and an unauthorized numbering mutation went unchecked | correspondence is now by stable `w14:paraId` first, then same-style typography-FOLDED text; an original numbered paragraph with no stable match is surfaced UNRESOLVED, never silently dropped. `engine.py _paragraph_reference_scan` |
| R3 (coverage) | a paragraph INSIDE a table cell had its numId reassigned and was not checked (scan only saw top-level `<w:p>`) | the scan traverses every `<w:p>` in the body INCLUDING table cells, and resolves current AND historical (`pPrChange`) references. `engine.py _paragraph_reference_scan` |
| R3 (heading repair) | functioning heading numbering appeared stripped (the 51 "changes") | it was a resolver gap: heading numbering comes from the list→style `pStyle` linkage, so the redundant direct `numPr` is safely normalised away (house rule) with NO number lost. `NumberingGraph` now resolves pStyle-linked numbering; `strip_direct` keeps a direct `numPr` only when removing it would leave the paragraph with no numbering at all. On real Warhoe: **0 reference flips, 0 number loss.** `numbering.py`, `engine.py strip_direct` |
| R3 (P2 artifact) | after confirming an unverified save, the normal filename/label were used and the label still claimed "conformed and verified" | the actual verdict + the explicit review-only decision are carried into the artifact: a distinct `REVIEW COPY - UNVERIFIED` filename, a verdict-based `docProps` contentStatus, and an audit recording the verdict, reason counts and the review-only flag; the completion view and dialogs no longer claim conformance for a not-clean copy, and human counts include paragraph-reference and unresolved-import reasons. `engine.py verdict_label/_artifact_label/build_audit`, `window.py` |
| R5 | effective table repair (header shading/size) | header repair BUILT and applied. Per the maintainer ruling, a WRONG header fill is corrected to the house colour **even when it is a tracked change** — the tracked-change RECORD (`tcPrChange` snapshot + every ins/del mark) is preserved, only the CURRENT wrong fill is normalised so the house navy wins. Run size/colour are normalised on cells with no run-level tracked change. Real report: header-fill fails **1,479 → 14**, preservation clean, 0 rollbacks, valid output; 9 headers now flagged `header-illegible` (navy fill exposed a tracked dark text colour — surfaced for review, tracked run text not rewritten). R5 stays OPEN on residual font-size and review-level deviations. `engine.py _repair_stray_header_formatting/_correct_current_header_fill` |

Authoritative Warhoe verdict this round: **not clean / blocking** — 0 unintended style flips, 0 paragraph-
reference flips, 0 uncorresponded numbered paragraphs, 3 dysfunctional list styles repaired (start
preserved, shared instances kept), definition integrity clean, 0 unresolved imports, and the safely-
repairable table headers normalised to house (853 stray cells; 322→103 failing tables) with tracked
reviewer edits preserved and flagged for adjudication. Blocking remains ONLY on the tracked/review table
remainder (R5, open). No accidental numbering loss, and no tracked review history, is destroyed to make the
gate pass.

---

## Round 3 — failure-safety and actual-reference verification

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
