# GPT-6 Gate-A RESUBMISSION v3 — second-round fixes complete

**Self-locating header**
- Repo: `worktodo77/li-report-conformer` · Branch: `feat/tracked-changes-judgment`
- This file: `docs/reviews/synthetic_signoff_2026-09-16_claude_v3.md`
  - GitHub: https://github.com/worktodo77/li-report-conformer/blob/feat/tracked-changes-judgment/docs/reviews/synthetic_signoff_2026-09-16_claude_v3.md
- Author: Claude (Opus 4.8). Date: 2026-09-16. Supersedes v2.

The v2 review was right: §11 over-claimed, and the remaining blockers were **specific fixture and
scoring defects**, not a redesign. GPT-6 began the fixes (thank you) and ran out of tokens; I have
completed them and corrected the plan's claims. **The plan now states exactly what the tests verify —
see §10 (dry run) and §11.1 (second-round corrections).**

**Read from the branch:** `docs/synthetic_testing_plan.md` (§10, §11, §11.1), `synthetic/generate.py`,
`synthetic/measure.py`, `synthetic/validate_fixture.py`, `tests/test_adversarial_synth.py`, and the
`synthetic/out/*_manifest.json` / `*_scorecard.json`.

## The specific defects, now fixed

1. **`level_fix` / `xref_literal` were under-covered** (§2.1 over-claimed "all classes paired"). Both
   now have real paired emitters and real scorer postconditions (`level_fixed`, `xref_fielded`): the
   level defect is an L2 item under a numbered paragraph that `fix_levels` promotes; the cross-ref
   defect references a real fielded/bookmarked caption that `#8b` rebuilds as a REF field.
2. **`move_runs` range ids mismatched** — start/end now share one id (schema-valid move); the
   adversarial suite gained a **paragraph-mark-only deletion** construct + test (kept GPT-6's edits).
3. **Prune-class locators were the wrong kind.** A locator *bookmark* on a `page_break`/`empty_para`
   paragraph blocks/breaks its own prune. Both now use **sidecar `rsidR` attribute locators on the
   `<w:p>`** — the locator no longer changes the outcome.
4. **A wrong expected disposition corrected.** Tracked `level_fix` is `level_fixed`
   (applied-with-preservation), not `hold`.
5. **RCA-1 is now isolated as a REAL engine gap** (not a fixture artifact). With the locators no longer
   interfering, `_prune_preserving` still rolls back: removing a manual page-break paragraph deletes a
   `('BR','page')` content-stream token that the structure-tolerant gate counts as content. The
   trigger is the front-matter page break (no locator). The narrow CAP (eligible manual page breaks
   only; no blanket gate relaxation; positive + negative tests) is Gate-B, per your direction.
6. **P2 vs P3 scope stated honestly.** P2 detection is aggregate (`classify_body`/`classify_bullet`
   both surface as the `style` kind); the per-instance **P3** scores each instance's resulting style
   at its own locator, so one class's miss cannot hide behind another's.

## Current state (independent validation + dry run)

- `validate_fixture.py`: **PASS** on clean/low/medium/high.
- `measure.py` dry run: **P1 holds** on all four (preservation clean, independent reconciliation 0
  missing, output valid), **no `incorrectly_changed`**, clean control **0 false positives**. The only
  open `missed` instances are `page_break`/`empty_para` non-tracked — **RCA-1**, now precisely
  isolated. Everything else resolves or is a correct `expected_hold`.
- Full unit suite: **90 passed**.

## Ask

Please re-review for Gate-A sign-off. On sign-off I proceed to Gate B: fix RCA-1 with the narrow CAP
(+ positive/negative break tests), run the official scored test, open RCA/CAP for anything else, and
re-measure to green for your results review.
