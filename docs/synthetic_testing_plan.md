# Synthetic Conformance Test Plan — LI Report Conformer

**Status:** DRAFT for GPT-6 sign-off. Testing does **not** begin until GPT-6 has signed off on the
three synthetic documents **and** this plan. GPT-6 reviews the scored results afterward.

**Author:** Claude (Opus 4.8). **Branch:** `feat/tracked-changes-judgment`.

---

## 1. Purpose

Verify — end to end and against a known ground truth — that the conformer correctly (a) **detects and
fixes** every conformance class it claims to handle, and (b) **preserves** every tracked change,
comment, author, and embedded object while doing so, across a spectrum of document quality. The test
is designed so that *all bases are covered*: every conformance class appears in each document, in both
non-tracked and tracked-change form, inside a document that reads like a real forensic expert report.

## 2. Test articles — three synthetic reports

Three fictitious forensic construction-delay expert reports (invented parties, project, numbers —
no client data), each **~130–160 pages**, generated deterministically by `synthetic/generate.py` and
accompanied by a machine-readable **ground-truth manifest** (`*_manifest.json`) listing every injected
defect and every tracked change. Each report contains: a title/privilege page; a TOC field; Lists of
Figures, Exhibits, and Attachments; a glossary table; twelve numbered sections with sub-headings,
numbered paragraphs, bullet lists, block quotes, footnotes, tables, and figures (charts + a
photograph); tracked changes by five authors; comments; a landscape appendix table; and a signature
block.

| Report | Quality | Character | Injected conformance defects | Tracked changes | Comments | Spelling/grammar |
|---|---|---|---|---|---|---|
| `synthetic_report_90pct.docx` | **90%** | Near-clean; drift only | 56 | 25 | 6 | 31 / 1 |
| `synthetic_report_70pct.docx` | **70%** | Moderately damaged | 191 | 40 | 6 | 149 / 8 |
| `synthetic_report_25pct.docx` | **25%** | Stress tester | 533 | 39 | 16 | 459 / 20 |

"Quality" = the approximate fraction of conformance opportunities left correct; 100% would mean zero
non-conformances and no spelling/grammar errors. Counts above are emitted by the generator and are the
authoritative expected values (see each manifest for the per-instance list).

### 2.1 Conformance classes covered (all present in every report, tracked + non-tracked)

`classify_body`, `classify_bullet`, `level_fix`, `strip_direct`, `table_style`, `table_empty_col`
(#7), `wrapper_table` (#3), `floating_image` (#5), `caption_literal` (#8a), `xref_literal` (#8b),
`heading_body_merge` (#6), `pdf_linesplit` (#1), `empty_para` (#2), `page_break` (#4), `typography`,
`footnote_style`, `section_landscape`, `figure_numbering` (audit), `tof_mismatch` (audit).

Tracked-change payloads present in every report: run insertions (`w:ins`), run deletions (`w:del`),
a paragraph-mark insertion, a `pPrChange` and an `rPrChange` formatting-revision snapshot, plus
tracked variants of `classify_body`, `strip_direct`, `typography`, `floating_image`, `caption_literal`,
`xref_literal`, and a tracked footnote — so the preservation gate and the tracked-adjacent review flag
are exercised.

## 3. Test procedure (executed by Claude)

For each of the three reports:

1. **Load & route.** Open with `Conformer(template, report)`. Assert it routes to `preserve`
   disposition (`revision_ledger.has_content_revisions()` is true).
2. **Analyze.** Run `analyze()`; capture JudgmentCalls (by kind), mechanical-action count,
   figure-audit findings (by level), and any rolled-back passes (`exceptions`).
3. **Apply.** Run `apply_with_decisions(accept-all)` to produce the conformed output.
4. **Preservation gate.** Run `verify_preservation()` on the output; require it **clean** (no lost /
   altered / re-attributed revision, no lost/edited comment, no altered binary).
5. **Structural validity.** Run `validate_output()`; require **valid** (every XML part well-formed,
   required parts present).
6. **Residual rescan.** Re-scan the conformed output for residual defect markers (literal captions,
   floating images, wrapper tables, unstyled tables, foreign body styles, straight quotes in text)
   and record the drop from the pre-conformance baseline.
7. **Score.** `synthetic/measure.py` writes `*_scorecard.json` comparing observed signals to the
   manifest, per class.

The whole run is `python synthetic/measure.py`; it is deterministic and repeatable.

## 4. Expected results

**Hard guarantees (must hold for all three reports; a failure is a STOP-ship defect):**

- **Preservation clean.** Every injected tracked change, comment, author, and binary survives
  unchanged. Expected `tracked_total` / `comments` per manifest.
- **Output valid.** Conformed `.docx` is well-formed OOXML and opens.
- **No crash / graceful holds.** Any pass that cannot be applied safely is rolled back and recorded,
  never applied destructively.

**Conformance expectations (per class; measured as detection + residual drop):**

- **Detected.** For each ASK class the engine emits the mapped JudgmentCall kind (`style`, `level`,
  `caption`, `xref`, `unwrap`, `dropcol`, `imgextract`, `splitcap`); for the audit classes it emits
  the mapped audit finding. Detected count should be ≥ injected count for that class (the engine may
  also flag naturally-occurring instances).
- **Resolved.** After accept-all, residual markers for a class drop to **0** for non-tracked
  instances: `foreign_body_styles → 0`, `unstyled_tables → 0`, `floating_images → 0`,
  `wrapper_tables → 0`; `straight_quotes` in text materially reduced.
- **Held-by-design (not a failure).** An instance **on or adjacent to a tracked change/comment** is
  flagged `needs_review` and, if the accept-all edit would disturb protected content, is rolled back
  by the local gate and left as authored. These appear as a residual that does **not** clear and as a
  `passes_rolled_back` entry; they are correct behaviour, not defects.
- **Advisory only.** `figure_numbering` and `tof_mismatch` produce figure-audit findings; they do not
  mutate the document (Word renumbers on open). Expected: the audit reports them.
- **Out of scope.** Spelling and grammar errors are **not** corrected by the conformer; they are
  counted in the manifest and reported, but their persistence is expected, not a defect.

Each manifest's `counts`, `tracked`, `comments`, and `expected_preservation` fields are the numeric
baseline. The scorecard's `classes[*].injected` vs `detected` and `residuals_before` vs
`residuals_after` are the comparison.

## 5. Measurement & comparison

`synthetic/measure.py` produces, per report, a `*_scorecard.json` with:

- `guarantees`: `preservation_clean`, `preservation_discrepancies`, `output_valid`.
- `analyze`: `judgment_calls` (by kind), `mechanical_actions`, `audit_findings` (by level),
  `passes_rolled_back`.
- `residuals_before` / `residuals_after`: the residual-marker rescan.
- `classes[cls]`: `{injected, signal, detected}` for every manifest class.

**Pass criteria per report:**

- P1 (blocking): `preservation_clean = true` and `output_valid = true`.
- P2: every non-tracked ASK class is *detected* (mapped JudgmentCall present) at ≥ its injected count.
- P3: residual markers for non-tracked structural classes drop to 0.
- P4: every `passes_rolled_back` entry is explained (either a known tracked-adjacent hold or an RCA
  item — see §6).
- P5: figure-audit reports the injected `figure_numbering` and `tof_mismatch`.

A report **passes** when P1–P3 and P5 hold and every P4 exception is either a by-design hold or has a
closed CAP. The suite passes when all three reports pass.

## 6. Root-cause analysis (RCA) for every issue discovered

For each discrepancy (a guarantee failure, a missing detection, a non-clearing residual that is *not*
a by-design hold, or an unexplained rolled-back pass), open an RCA record:

| Field | Content |
|---|---|
| ID | `RCA-<n>` |
| Report / class / instance | which document, conformance class, manifest defect id(s) |
| Observed vs expected | scorecard signal vs manifest baseline |
| Reproduction | minimal synthetic fixture (add to `tests/` if not already covered) |
| Root cause | the specific engine behaviour, established by reading code + a failing test watched go RED |
| Severity | blocking (preservation/validity), major (class not fixed), minor (advisory/cosmetic) |

RCA discipline follows the repo standard: *a green result proves nothing* — the root cause is only
established once a test has been watched failing on the real defect, and fixes target the whole class,
not the single repro.

## 7. Corrective action plan (CAP) for every issue

Each RCA gets a CAP record:

| Field | Content |
|---|---|
| ID | `CAP-<n>` (1:1 with `RCA-<n>`) |
| Fix | the code change (engine/gate) or the ruling (accept as by-design; document as a limitation) |
| Regression test | the synthetic fixture / unit test that now passes, run ≥8× if flaky-prone |
| Re-measure | re-run `measure.py`; the scorecard signal clears |
| Verification | preservation still clean + full suite green + no new residual |
| Disposition | Fixed / Accepted-as-limitation / Deferred (with reason) |

CAPs that change the engine are committed on the feature branch with the RCA/CAP id in the message.
CAPs that rule an issue "by design" update `docs/tracked_changes_plan.md` limitations and the plan.

## 8. Preliminary dry-run (illustrative — not the official scored run)

A dry run of `measure.py` over the three reports already establishes the harness works and surfaces
the expected signals. Notable preliminary observations (to be confirmed and RCA'd in the official run
after sign-off):

- **All three reports:** preservation **clean**, output **valid**; `foreign_body_styles`,
  `unstyled_tables`, `floating_images`, `wrapper_tables` all drop to **0**; all five ASK JudgmentCall
  kinds plus `style`/`level` fire; figure-audit reports the injected numbering and ToF defects.
- **Candidate RCA-1 (major):** `_prune_preserving` (#2 empty paragraphs / #4 manual page breaks) is
  **rolled back** in every report. Preliminary root cause: the content-stream gate counts a
  page-break token (`<w:br w:type="page"/>`) as content, so removing a manual page-break paragraph
  reads as an unauthorized content change and the whole prune pass reverts. Candidate CAP: treat
  page/column break tokens as layout (droppable) in the structure-tolerant gate, mirroring the
  existing tab-stop fix; add a regression fixture. **To be confirmed under RCA in the official run.**
- **By-design hold (not a defect):** the single *tracked* literal caption is flagged `needs_review`
  and left as authored by the local gate; its residual does not clear. This is correct
  tracked-adjacent behaviour and will be recorded as such, not as an RCA.

## 9. Deliverables & sign-off gates

1. **Gate A (this submission):** three synthetic reports + manifests + this plan + the generator and
   measurement code, on `feat/tracked-changes-judgment`. → **GPT-6 signs off on documents + plan.**
2. **Gate B:** after sign-off, Claude runs the official scored test, opens RCA/CAP for every issue,
   applies fixes on the branch, re-measures to green. → **GPT-6 reviews the scored results + RCAs/CAPs.**

Artifacts: `synthetic/generate.py`, `synthetic/lib.py`, `synthetic/content.py`, `synthetic/measure.py`,
`synthetic/assets/*.png`, `synthetic/out/*.docx`, `synthetic/out/*_manifest.json`,
`synthetic/out/*_scorecard.json` (produced at Gate B).
