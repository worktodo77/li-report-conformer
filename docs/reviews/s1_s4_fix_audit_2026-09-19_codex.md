# S1–S4 fix re-review — 19 September 2026

**Verdict: changes required. S2, S3, and S4 are closed for the reviewed defects. S1 remains partial, with one remaining context-loss defect and one new preservation-gate regression.** The previous settled-text quotation and multiple-space range examples are now fixed, but the response's claim that all four findings are addressed is premature.

Reviewed the fetched branch `feat/tracked-changes-judgment` at **`e14c275`**, starting with `docs/reviews/rereview_response_round3_2026-09-19_claude.md`. Inspected the implementation and tests in `ae9bcf8`, replayed the previous full-package counterexamples, and checked the real Word reader on the mixed-bold fixture. Source locations below refer to this pinned commit. Only this review document is changed.

## Summary

- **S1, partial:** logical-text typography correctly protects a quotation split across ordinary runs and honors `from  ` with multiple spaces. Tracked content is removed before logical-text context is built, however, so an inserted opening quote or range prefix does not protect adjacent settled text. Both cases still report CLEAN.
- **S1, regression:** paragraph-level sentence spacing and per-token gate authorization disagree. An ordinary sentence boundary split across runs causes a preserving document's entire typography pass to roll back, undoing valid fixes in other paragraphs.
- **S2, closed:** the clean path now uses the shared restyling helper. Both the clean and preserving self-closing-properties fixtures produce one paragraph-properties element.
- **S3, closed:** the UI unresolved predicate includes broken references and unknown state; export handles both exception sites and counts import/correspondence reasons. Replayed UNKNOWN output no longer says “None.”
- **S4, closed:** the three partial-observation cases now block. The actual Word mixed-bold fixture is serialized as null and produces UNVERIFIED rather than a pass.

## T1 — P1 — S1 still loses quotation and range context inside tracked insertions

**Locations:** `src/conformer/engine.py:1320–1347`, `:3039–3053`.

`typography()` masks content revisions before `_typography_paragraph()` concatenates visible `w:t` values. The latter sees only settled text: the inserted text is represented by a sentinel with no `w:t`. That protects the revision payload from mutation, but also erases context needed to protect the neighboring settled text.

**Full-package reproduction:** package `_HEADING` followed by this body paragraph using the committed `_package` helper in `tests/test_full_pipeline_regressions.py`, then call `Conformer.run()`:

```xml
<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>
  <w:ins w:id="88" w:author="Reviewer" w:date="2026-09-19T00:00:00Z">
    <w:r><w:t xml:space="preserve">He said “</w:t></w:r>
  </w:ins>
  <w:r><w:t>03 April 2011</w:t></w:r>
  <w:r><w:t>”.</w:t></w:r>
</w:p>
```

Observed combined text: **`He said “3 April 2011”.`** The quoted date has changed. `exceptions=[]`, `conformance_status()['clean'] == True`, and `verify_preservation()[0] == True`.

A second fixture replaces the insertion's text with `from  ` and the following settled text with `2017-2019`. It produces **`from  2017–2019`**, also with no exceptions and both checks passing. The equivalent all-settled example correctly remains hyphenated after this fix.

This was also present at the previous reviewed commit `b7b77fe`; it is a remaining S1 gap, not a newly introduced regression. It does not request the deferred F2 normalization enhancement or any rewrite of tracked payloads. The issue is deciding whether to change **settled** characters using context that remains visible in the current report.

**Required correction:** retain revision text as read-only context while marking its characters ineligible for edits, or conservatively skip edits whose context crosses a masked revision. Define how current inserted text and deleted historical text contribute to context; do not silently join the settled fragments on either side of an opaque mask. Add full-package preserving-path tests with quote delimiters and `from`/`between` prefixes inside insertions, asserting the settled text and final verdict as well as preservation.

## T2 — P2 — S1's paragraph transform can now roll back all typography in a preserving document

**Locations:** `src/conformer/engine.py:1330–1383`, `:1877–1883`, `:1917–1927`; `src/conformer/revisions.py:471–499`.

The new transformer uses paragraph context, but `stream_violations()` still authorizes each changed text token independently. Folding smart-quote direction only addresses quote glyphs. It does not authorize other edits that become valid because of the preceding run's content.

**Full-package reproduction:** include the existing `_FMT_REV` fixture in an unrelated paragraph to select the preserving pipeline. Follow it with:

```xml
<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>
  <w:r><w:t>First sentence.</w:t></w:r>
  <w:r><w:t xml:space="preserve"> Next sentence.</w:t></w:r>
</w:p>
<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>
  <w:r><w:t>on 03 April 2011</w:t></w:r>
</w:p>
```

The paragraph transform inserts the house sentence space at the start of the second run. The per-token `typo_ok` predicate sees only ` Next sentence.` and cannot derive that insertion without the preceding sentence-ending period. It rejects the change, causing `_run_passes_preserving()` to restore the snapshot for the **entire typography pass**.

| Same fixture | `b7b77fe` | `e14c275` |
| --- | --- | --- |
| Typography exceptions | None | `('typography', 'unauthorized content change (1)')` |
| Separate unquoted date paragraph | `on 3 April 2011` | `on 03 April 2011` |
| Conformance clean | True | False |
| Preservation clean | True | True |

This comparison was executed against both pinned checkouts. The new gate correctly refuses an edit it cannot authorize, so this is **not** silent corruption or a false-CLEAN case. It is a regression in successful conformance: an ordinary run split now suppresses unrelated valid typography fixes across the document.

**Required correction:** make authorization validate the same context-aware, boundary-preserving edit plan that the transformer actually applies, while maintaining strict revision/comment/object protection. Alternatively, suppress any edit that cannot be justified by the current gate until both agree. Do not broaden the gate to accept arbitrary text differences. Add a full preserving-pipeline fixture with the split sentence and a separate valid typography change; assert both intended results and no rollback. The new typography tests exercise a stubbed application path and do not reach this integration gate.

## Closure evidence for S2–S4

**S2:** replayed the clean two-row table whose header started with `<w:pPr/>`; output now has one `pPr` containing `TableHeader`, and no leftover self-closing sibling. The preserving counterpart also remains structurally correct. The shared helper is now actually used by clean `fix_tables()`.

**S3:** replayed the verifier-exception stub; `outcome_verdicts()` returns UNKNOWN for both conformance and unresolved outcomes, with `clean=None`. The new tests cover exceptions in `outcome_report()` and `conformance_status()`, plus imports and uncorresponded paragraphs. Source inspection confirms the UI now includes `nbroken` and explicitly renders unknown unresolved state amber. No interactive GUI session was used for this review.

**S4:** replayed `header_bold=[True, None]`, `header_fonts=['Times New Roman', '']`, and `header_fills=[teal, 9999999]`; each now returns `passed=False` with an unverified observation. Also opened the previous mixed-bold DOCX with the committed PowerShell Word reader. The real JSON contains `header_bold: [null]`; replaying that JSON through `verify()` yields `passed=False` and `table-header-incomplete` with severity `unverified`. This confirms the actual reader conversion, not just the mocked tests.

## Scope and limits

`python -m pytest -q -k "not warhoe"` completed with **327 passed, 4 deselected, 41 warnings** in **605.17 seconds**. This independently confirms the reported fast-test count; the additional full-package probes above expose cases those tests do not cover.

Non-gating performance observation: the new full-text diff adds substantial cost even when there is only one run to map. On a 2,250-character paragraph repeating the existing stress-test sentence 50 times, `typo_text()` took approximately 0.0008 seconds while `_typography_paragraph()` took 0.56 seconds. These timings were collected during the suite run, not as an isolated benchmark. Consider avoiding the general `SequenceMatcher(autojunk=False)` mapping when segmentation does not require it. This is an optimization note, not a third correctness finding.

Synthetic full-package fixtures were built from the branch's operational template; no client data or dependency installation was involved. Word opened the mixed-bold output read-only and closed without saving. Warhoe is absent from the branch, so its reported local integration results are not independently verified here.

Previous closures R1/R3/R7/R8 stand, as do the agreed F2 record-exact contract, the deferred deeper normalization, and the correction that `template.dotx` is the authoritative Letter template. Real-report A4 render verification remains a stated limitation. This review is scoped to S1–S4 and their changes; it is not a claim that every guideline rule or every report shape has been verified.

The next change should be limited to S1's context and authorization integration, with tests through the real preserving pipeline. The exact previous settled-text examples now work; the two remaining examples explain why S1 cannot yet be closed.
