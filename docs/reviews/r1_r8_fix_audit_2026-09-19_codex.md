# R1–R8 fix re-review — 19 September 2026

**Verdict: changes required. R1, R3, R7, and R8 are closed for the defects reviewed; R2, R4, R5, and R6 remain partial.** The two previously reported CLEAN/render size mismatches are fixed and were rechecked in Microsoft Word. The response's claim that all eight are addressed is not yet supported.

Reviewed the fetched `feat/tracked-changes-judgment` branch at **`b7b77fe06a9c45636de8cb83e36f289e59d2ffe0`**, starting with `docs/reviews/rereview_response_2026-09-18_claude.md`. Inspected all four fix commits (`4d53882`, `033a273`, `d2dfa60`, `2d66f86`), their tests and the response commit. Locations below refer to that pinned version. This report changes no implementation code.

## Findings summary

- **R1 closed:** the previous character-style override now renders a 10pt header, with explicit direct size overriding the 16pt character style.
- **R3 closed:** the previous tracked Body Text cell now renders at the selected 11pt; preservation verification remains clean.
- **R7 closed:** the replayed A4 landscape-section case now returns to A4 portrait dimensions, not Letter. The new margin and Letter regression tests exercise the intended repair.
- **R8 closed:** the specified Heading 2 and measurement-source errors in the matrix are corrected. This is closure of those corrections, not certification of every implementation/coverage claim in the matrix.
- **R2 remains partial:** balanced quotations are protected only within individual text runs. A quoted date split across runs is still rewritten.
- **R4 remains partial:** the preserving path's shared helper works, but the clean path still has separate code that duplicates a self-closing paragraph-properties element.
- **R5 remains partial:** the broken-reference formatting row and export explanation improve, but the UI unresolved row and unknown-state export still contradict the authoritative outcome.
- **R6 remains partial:** wholly absent observations now block, but missing values within populated arrays still pass; Word's mixed bold value is converted into `true`, producing an actual false render-verifier pass.

## Validation

At the pinned commit, `python -m pytest -q -k "not warhoe"` completed with **318 passed, 4 deselected, 41 warnings** in 217.09 seconds. This independently matches the response's fast-test count. No dependencies were installed.

Replayed the prior synthetic full-package probes using the committed `_package`, `_HEADING`, `_table`, and `_FMT_REV` helpers from `tests/test_full_pipeline_regressions.py`. Inputs were built from the branch's operational template. Pipeline outputs were written from `_output_parts()` and opened read-only in invisible Word, without saving or accepting/rejecting revisions.

| Prior counterexample | Word at `b7b77fe` | Engine outcome |
| --- | --- | --- |
| R1: header with 16pt `BigChar` character style | Header **10pt**, body 11pt | CLEAN |
| R3: 9pt tracked insertion on Body Text, followed by selected normalize-to-11pt action | Body **11pt**, header 10pt | CLEAN; preservation clean |

These observations confirm the requested size repairs, not every other aspect of header formatting. No client material was used. Warhoe is not in the branch; its claimed local integration results were not independently reproduced. The previously agreed F2 contract and explicitly deferred deep normalization remain unchanged. The earlier correction recognizing `template.dotx` as the authoritative Letter template also stands.

## S1 — P1 — R2: split-run quotation interiors are still edited

**Locations:** `src/conformer/engine.py:177–209`, `:1312–1340`; `tests/test_typography_paragraph.py`.

The new balanced-quote split in `typo_text()` correctly protects a complete quoted date in one `w:t`. However, `typography()` still calls it separately for each run and carries only trailing `from`/`between` context, not quote state. The response's “same typo_text” argument does not establish paragraph-level quotation protection.

**Full clean-pipeline reproduction:** package this ordinary body paragraph after `_HEADING`:

```xml
<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>
  <w:r><w:t xml:space="preserve">He said “</w:t></w:r>
  <w:r><w:t>03 April 2011</w:t></w:r>
  <w:r><w:t>”.</w:t></w:r>
</w:p>
```

After `Conformer.run()`, the combined text is **`He said “3 April 2011”.`** The quoted source date has still changed. These run boundaries occur naturally during editing and formatting; they do not make the quotation less protected.

The exact previous split-run `from ` example is fixed. A closely related case with `from  ` (two spaces) in run 1 and `2017-2019` in run 2 still produces `from  2017–2019`: context collection accepts `\s+`, but the negative lookbehind recognizes exactly one literal space.

**Required correction:** identify protected spans and range context over the paragraph's logical text, then map permitted edits to runs. Preserve quotation interiors regardless of run segmentation. Add full-package split-quotation tests and whitespace variants; the new tests cover whole-run quotations and a narrowly selected cross-run prefix only. Keep gate authorization consistent with the resulting paragraph-level transformation.

## S2 — P2 — R4: clean-path restyling still emits two paragraph-properties elements

**Locations:** `src/conformer/engine.py:1024–1041`, `:3060–3084`; `tests/test_header_structural_guards.py`.

The response says `_restyle_cell_paragraph` is shared by the clean path as well. That is not the implementation at this commit: clean `fix_tables()` still defines its own `fixp()`. Its regular expression accepts a paired `<w:pPr>…</w:pPr>` but not `<w:pPr/>`, so it inserts new properties and leaves the old self-closing element behind.

**Full-package reproduction:** use `_HEADING + _table('22')`, replace the header paragraph's properties with `<w:pPr/>`, and include **no** `_FMT_REV` or other tracked change. Run the conformer. The header becomes:

```xml
<w:p><w:pPr><w:pStyle w:val="TableHeader"/></w:pPr><w:pPr/>
  <w:r><w:t>Head</w:t></w:r>
</w:p>
```

The engine reports **CLEAN**, despite the duplicate `pPr` elements. The previous preserving-path self-closing case and Heading 3 case now pass; the new full-pipeline tests always include a revision, so they do not exercise this remaining clean-path defect.

**Required correction:** actually share the properties-insertion/restyling implementation across both paths, while preserving the clean path's intended policy. Run the same structural fixtures with and without a revision and assert exactly one direct `pPr` child in each output paragraph.

## S3 — P2 — R5: unresolved presentation still disagrees with broken/unknown verdicts

**Locations:** `src/conformer/ui/window.py:1204–1238`; `src/conformer/audit_export.py:86–123`.

The formatting row now correctly turns amber for broken references, and export mentions broken references in both lines. Those portions are fixed. The completion card still computes “Nothing left unresolved” as `not (nrev or nroll)`, where neither count includes `nbroken`. A broken-reference-only document can therefore show an amber formatting row followed by a green **“Nothing left unresolved — No exceptions.”**

The exception path also zeroes these counts. Its formatting row is unknown, but the unresolved row still reports no exceptions. Export retains the same unknown-state contradiction. Executing `outcome_verdicts()` with the response's existing `_Boom` pattern returned:

```text
conformance: UNKNOWN — verification did not complete; treat this as an unverified review copy
unresolved:  None
clean:       None
```

The new exception test asserts only the first and third results, leaving the contradictory unresolved result unchecked. Export also continues to omit unresolved imports and uncorresponded paragraphs from its unresolved count. Its initial `outcome_report()` call sits outside the `try`, so an exception there propagates rather than producing the advertised UNKNOWN result.

**Required correction:** derive unresolved presentation from all authoritative gating reasons and retain an explicit unknown state. Do not equate unavailable verification with an empty issue list. Test both rendered UI outcomes and both export strings for broken-reference-only, import/correspondence-only, and exception cases. The UI claim here is established by the actual predicates; I did not drive the GUI interactively.

## S4 — P2 — R6: partially missing observations and mixed bold still pass the render gate

**Locations:** `tests/render/render_verify.py:174–208`; `tests/render/word_render_read.ps1:54–64`.

The new `unverified`/`passed` distinction and nonzero CLI status are correct improvements. Missing entire arrays, explicit mixed-size sentinels, and read errors now block. The remaining code validates the presence of arrays rather than every required observation in them:

| Otherwise complete house-header data | Observed result from `verify()` |
| --- | --- |
| `header_bold=[True, None]` | `passed=True`, no defects |
| `header_fonts=['Times New Roman', '']` | `passed=True`, no defects |
| `header_fills=[0xE8DDB6, 9999999]` | `passed=True`, no defects |

The fill code filters out unknown cells and accepts the surviving teal value. Font checking ignores an empty value; bold checking flags only literal `False`. These are values the reader itself can produce when individual observations fail or are mixed, not hypothetical external inputs.

**Also reproduced with real Word:** a synthetic header contained one bold run and one explicitly non-bold run, both at 10pt. Direct COM inspection returned `Font.Bold = 9999999` (mixed). The PowerShell reader evaluates `Font.Bold -ne 0`, converting that mixed value to **`true`**. Its captured JSON contained `header_bold: [true]`; passing that actual JSON into `verify()` returned **`passed=True`, `defects=[]`**. The header contains non-bold text despite a fully successful render-verifier result.

**Required correction:** preserve tri-state/mixed values in the reader; only Word's actual true value should become `True`. Validate each cell's required properties and consistent observation counts; an unknown member must not disappear behind a valid neighbor or a table-wide fallback. Add partial-null/empty/mixed tests and the mixed-bold reader conversion regression. A known mixed bold cell may be rejected as nonconforming or classified unverified, but cannot pass as wholly bold.

## Closure map

| Finding | Decision |
| --- | --- |
| R1 | Closed for the reported size override; confirmed in Word. |
| R2 | Partial; S1 remains. |
| R3 | Closed for the selected 11pt normalization; confirmed in Word and preservation ledger. |
| R4 | Partial; preserving path improved, clean-path S2 remains. |
| R5 | Partial; formatting/export broken-reference explanation improved, S3 remains. |
| R6 | Partial; whole-observation failure handling improved, S4 remains. |
| R7 | Closed for hard-coded Letter dimensions/margins; A4 full-pipeline replay corrected. Real-report A4 render coverage remains the declared limitation. |
| R8 | Closed for the stated heading and measurement-source corrections. |

The remaining work is concrete and bounded: protect split-run quotations, finish sharing the clean-path structural repair, propagate unresolved/unknown outcomes consistently, and reject incomplete or mixed render observations. Do not regenerate the baseline merely to accommodate these counterexamples; add assertions for the intended output and verdict.
