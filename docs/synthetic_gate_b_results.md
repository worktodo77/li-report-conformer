# Synthetic Conformance Test — Gate B results

**Status:** Gate B COMPLETE — all four reports PASS. For GPT-6's results review.
**Branch:** `feat/tracked-changes-judgment`. **Author:** Claude (Opus 4.8). Date: 2026-09-16.

Gate A was not re-signed (GPT-6 out of tokens); Alex authorised proceeding to Gate B. The scored test
was run, the one issue found (RCA-1) was root-caused and fixed with the narrow CAP GPT-6 specified,
positive/negative regression tests were added, and the suite re-measured to green.

## Result

`python synthetic/measure.py` (saves `synthetic/out/*_scorecard.json`, exits non-zero on any FAIL):

| Report | Verdict | P1 guarantees | Per-instance verdicts |
|---|---|---|---|
| clean  | **PASS** | preservation ✓, valid ✓, indep-reconciliation 0 missing | (no defects) |
| low    | **PASS** | ✓ / ✓ / 0 | resolved 41, expected_hold 9 |
| medium | **PASS** | ✓ / ✓ / 0 | resolved 180, expected_hold 9 |
| high   | **PASS** | ✓ / ✓ / 0 | resolved 561, expected_hold 9 |

Every conformance instance is either **resolved** (change applied correctly at its locator) or a
correct **expected_hold** (protected instance left untouched). Zero `missed`, zero
`incorrectly_changed`, zero `indeterminate`. The clean control has zero false-positive conformance
changes. Unit suite: **92 passed**. Real-document regression: the Warhoe draft (11,374 revisions)
stays preservation-CLEAN with 0 rolled-back passes after the fix.

## RCA-1 / CAP-1 (the one issue found and fixed)

| Field | Content |
|---|---|
| **ID** | RCA-1 / CAP-1 |
| **Reports / class** | all tiers; `page_break` (#4) and `empty_para` (#2), non-tracked |
| **Observed vs expected** | both `missed` — the manual page-break and stray empty paragraphs were not removed |
| **Root cause (ENGINE)** | `_prune_preserving` removes a manual page-break paragraph, deleting a `('BR','page')` content-stream token. Its gate ran in `struct` mode, which drops only `P/TBL/TR/TC` structure tokens, so the removed page-break token registered as *unauthorized content change (1)* and the **whole prune pass rolled back**, taking the empty-paragraph removal with it. Isolated on the low report by diffing the pre/post-prune content stream (removed tokens = `('BR','page'),('P',)`). The trigger is the front-matter page break, which carries no fixture locator — a genuine engine gap, not a fixture artifact. |
| **Severity** | major (a shipped pass, #2/#4, silently did nothing on any revised document) |
| **Reproduction** | `tests/test_revisions.py::test_prune_gate_tolerates_page_break_only_protects_column_and_line_breaks` (gate unit) and `tests/test_ask.py::test_cap1_page_break_pruned_column_line_and_tracked_breaks_protected` (preserve-mode). Watched RED before the fix (the un-pruned page break left 2 page-break tokens, not 1). |
| **CAP — the NARROW fix** | (1) a new `prune` gate mode: `stream_violations(..., ignore_structure=True, ignore_page_breaks=True)` drops **only** the `('BR','page')` token — column breaks `('BR','column')`, line breaks `('BR','')`, and every other token stay protected; it is scoped to the prune pass, **not** applied globally. (2) The prune's page-break branch already matches **only** page-break-*only* paragraphs (`w:type="page"`); the empty-paragraph branch was tightened to require no break / field / object, so a paragraph whose only content is a column or line break is left alone. Result: only *eligible manual page-break paragraphs* can lose a break token, exactly as directed. |
| **Regression tests** | positive: an eligible page break is pruned. negative: a column break, a line break, and a *tracked* page break are all protected (not removed); preservation stays clean and the prune does not roll back. |
| **Verification** | all four reports PASS; 92 unit tests pass; Warhoe preservation CLEAN, 0 exceptions. |
| **Disposition** | **Fixed.** |

## Other exceptions observed (explained, not defects)

- `caption[*]` "local display gate tripped (not applied)": a *tracked* literal caption whose text is an
  insertion — fielding would drop the insertion, so the local gate correctly holds it. Scored as a
  correct `expected_hold` for its instance (P4 explained).

## Artifacts

`synthetic/out/*_scorecard.json` (per-report, per-instance), `*_manifest.json` (ground truth),
`docs/synthetic_testing_plan.md` (procedure/criteria/RCA-CAP process), the generator/validator/scorer
under `synthetic/`, and the regression tests in `tests/`.
