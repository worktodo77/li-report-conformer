# F1–F10 fix re-review — 18 September 2026

**Verdict: changes required.** Several fixes are complete, but full-pipeline counterexamples remain outside the new tests. Two outputs still report CLEAN despite a visibly wrong font. The response's blanket statement that all ten findings are addressed is too strong.

Reviewed the fetched branch `feat/tracked-changes-judgment` at **`b6c1b908119847492ad18975382dfa1b80ebb4c3`**, including the response, all ten commits after my prior review commit `eb2220b`, their aggregate changes and tests, and both original guideline DOCX files. This is a re-review of the fixes, not a repetition of the original session audit. Source locations below refer to this pinned commit.

## Summary

- **Closed: F1, F8, F10.** Header-style restoration, safe excerpt pairing, and the Intel runner change address those defects. F1 does not close the separate effective-formatting gaps under F5.
- **F2 routing fix accepted; broader work explicitly deferred.** Formatting-only revisions now enter the preserving pipeline. I accept the clarified record-exact/current-formatting-only contract: rejecting a revision may restore nonconforming historical formatting. Normalizing current formatting throughout every revised paragraph is declared unfinished, so I do not count its mere deferral as a new defect.
- **F3 remains partial:** inline quotations are still changed, and a run boundary bypasses the `from` range exception.
- **F4 remains partial:** selecting normalization can produce a 12pt table body, not the promised 11pt, with CLEAN and preservation both passing.
- **F5 remains partial:** character-style overrides evade header verification, and the UI/export summaries omit newly gated broken references.
- **F6 remains partial:** all-cell size checks improved, but missing observations and later-cell fill defects can still pass the render verifier.
- **F7 corrected:** I withdraw my earlier claim that the operational template is stale. The new A4 selection is useful, but section repair still writes Letter dimensions into an A4 report.
- **F9 remains partial:** the preceding table pass defeats both the heading guard and the self-closing-properties fix.
- **The new coverage matrix still misstates source requirements**, particularly Heading 2 capitalization and the heading level eligible for the long-title exception.

## Validation and limits

At the pinned commit, `python -m pytest -q -k "not warhoe"` produced **300 passed, 4 deselected** in 216.13 seconds. I used the existing Python environment; no dependencies were installed. I also exercised template-backed synthetic documents through `Conformer.run()` and `apply_with_decisions()`, then opened the relevant outputs in invisible, read-only Microsoft Word and queried their actual fonts. A revision-free control table rendered at **10pt header / 11pt body** and reported CLEAN, corroborating F1's closure. Synthetic inputs contain no client material.

GitHub Actions [run 35414962682](https://github.com/worktodo77/li-report-conformer/actions/runs/35414962682), at code commit `e68b1f5`, succeeded for both Intel and Apple Silicon, including tests, packaging, and the Qt plugin presence check. The later `b6c1b90` commit only adds the response. This establishes build success, not an interactive macOS launch test.

Warhoe is not in the fetched branch. I have not independently reproduced the response's local Warhoe results. No implementation files are changed by this review.

## Remaining findings

### R1 — P1 — F5: character-style header overrides still receive CLEAN

**Locations:** `src/conformer/engine.py:938`, `:3037`; `src/conformer/tablespec.py:274–309`.

The table run filter retains `w:rStyle`. Header repair removes direct `w:sz` but leaves the character style. The effective verifier checks direct sizes and the first paragraph's style; it does not resolve the character style attached to the actual text run.

**Reproduced through the full preserving pipeline:** package a normal two-row table from the bundled template; give the header run `rStyle="BigChar"`; define that character style with `sz="32"`; include the existing `_FMT_REV` fixture outside the table so the preserving path runs. Use 11pt body text so there is no small-font variation. Output:

```text
conformance_status(): clean=True, blocking=False, all issue lists empty
Word Tables.Item(1).Cell(1,1).Range.Font.Size: 16.0
Word header range Style.NameLocal: Big Char
```

The expected header is 10pt. This is the same false-certification class as the original finding, beyond the now-fixed missing-paragraph-style case. Resolve the effective formatting of each visible run, including character styles and inheritance, or report unsupported resolution as unverified. Add a pipeline test with this override and a rendered assertion.

### R2 — P1 — F3: quotation protection and range context stop at run boundaries

**Locations:** `src/conformer/engine.py:177–203`, `:1265–1273`.

Removing the unsourced percent/programme/USA/analyses/matrices transformations was correct. Excluding `ExcerptorQuote` also fixes that particular style. Ordinary body quotations remain unprotected because `typography()` transforms each `w:t` independently.

**Reproduced through the clean pipeline:**

```text
Input body sentence:  He said “03 April 2011”.
Output:               He said “3 April 2011”.

Input consecutive runs: <w:t xml:space="preserve">from </w:t>
                        <w:t>2017-2019</w:t>  [bold second run]
Output text:            from 2017–2019
```

The first changes quoted source wording despite the stated quote exemption; the second violates the newly adopted from/between exception even though the equivalent single-run test passes. Word commonly splits runs for emphasis, edits, and proofing. Determine quotation spans and range context at paragraph level, then apply permitted changes back to runs. Add split-run and inline-quotation cases, not only `typo_text()` string tests.

### R3 — P2 — F4: the 11pt action can normalize to 12pt and certify success

**Locations:** `src/conformer/engine.py:1976–2018`, `:3129–3142`.

The new direct-small-size preservation and offers work for the tested `TableData` paragraphs. `_normalize_table_body_to_11pt()` assumes that removing a direct size exposes Table Data's 11pt. That assumption fails for the revised paragraphs the preceding pass deliberately leaves on their authored style.

**Reproduced:** use a body cell with paragraph style `BodyText`, containing a tracked insertion whose text has direct `sz="18"` (9pt). Analyze, then apply the offered `change:Normalize all table bodies to 11pt`. The insertion remains, its direct size is removed, and its paragraph remains `BodyText`.

```text
verify_preservation(): True, no discrepancies
conformance_status(): clean=True, blocking=False
Word body cell Font.Size: 12.0
Word body cell Style.NameLocal: Body Text
Word header cell Font.Size: 10.0
```

This is not a demand to finish the deferred general F2 enhancement: the user explicitly selected an existing action promising 11pt, and this action now reaches through tracked insertions. Apply current 11pt formatting independently of the surviving paragraph/character style, without rewriting historical snapshots, or leave the action unresolved when that cannot be done. Test the rendered result as well as the absence of `sz="18"`.

### R4 — P2 — F9: the full table pass still defeats the helper's guards

**Locations:** `src/conformer/engine.py:2980–3013`, `:3129–3143`.

The helper's direct-`numPr` and `<w:pPr/>` fixes are valid in isolation. Before it runs, `cell_para()` still unconditionally replaces an unmasked paragraph's style and only recognizes the exact `<w:pPr>` opening tag.

**Two full-pipeline reproductions**, each with an unrelated `_FMT_REV` outside an otherwise ordinary table:

1. A header paragraph styled `Heading3` becomes `TableData`, then `TableHeader`. The heading/reference guard arrives too late. The final verifier reports an uncorresponded numbered paragraph, so this example is **not** falsely CLEAN; nevertheless the transformation the guard was supposed to prevent has occurred.
2. A header beginning with `<w:pPr/>` becomes:

   ```xml
   <w:p><w:pPr><w:pStyle w:val="TableHeader"/></w:pPr><w:pPr/>…</w:p>
   ```

   There are still two paragraph-properties elements. The helper cannot repair the duplicate already introduced by `cell_para()`.

Move the structural checks and correct properties insertion into the earlier table transformation as well, preferably using one shared implementation. Extend `test_header_structural_guards.py` with full-package `run()` tests.

### R5 — P2 — F5: verdict consumers omit broken references and can contradict the gate

**Locations:** `src/conformer/ui/window.py:1197–1230`; `src/conformer/audit_export.py:179–204`.

The engine correctly includes `broken_references` in its unresolved reasons, and export correctly labels verification exceptions UNKNOWN. The displayed explanations were not updated consistently:

- The UI uses `not st['blocking']` for “Formatting conforms” and counts tables/imports/paragraph correspondence/rollbacks for “Nothing left unresolved.” It does not count `broken_references`. A broken-reference-only verdict is not clean but is nonblocking, so both rows can show green; the detail even claims that references resolve as intended.
- Export's unresolved summary counts only tables and rolled-back passes. A broken-reference-only case can say NOT CLEAN with zero listed formatting failures, then “Unresolved / exceptions: None.”
- If verification raises in the UI, the formatting row becomes unknown, but resetting the unresolved counts to zero still yields “Nothing left unresolved — No exceptions.”

Generate all three outcomes from the complete authoritative verdict, including unknown state and every gating reason. Exercise the broken-reference stub already added to `test_full_pipeline_regressions.py` through the presentation/export layer, not only `conformance_status()`.

### R6 — P2 — F6: incomplete render observations can still pass acceptance

**Locations:** `tests/render/render_verify.py:148–183`, `:265`; `tests/render/word_render_read.ps1:49–72`.

`Condition(0)`, all-cell size collection, and the added REF strings are improvements. The reader now collects `header_fills`, but the verifier still bases fill acceptance on cell 1. It also ignores a missing size array, a missing fallback size, and the reader's `header_error`.

**Executed against `verify()` using the same Word-free read substitution as the new tests:**

| Reader data for a house-style table | Observed result |
| --- | --- |
| Teal first-cell fill; no size observations | No defects, no failures |
| Two 10pt cells; fills `[teal, black]`; first-cell fill teal | No defects, no failures |
| Mixed size sentinel `9999999` | Review defect, but no failures |

The last case is now visibly flagged, which is progress, but CLI status remains zero because it depends only on `r.fails`. Font family, boldness, and repeating-header state are still not asserted. Field-update exceptions are likewise review-only, and the PowerShell call discards the `Fields.Update()` return value.

Check every observed cell's effective fill and required text properties. Missing/incomplete observations must produce an unverified acceptance result with a non-success status when the harness is used as a release gate. Preserve the useful distinction between proven wrong formatting and inability to verify it; neither establishes a pass.

### R7 — P2 — F7 follow-up: A4 selection does not remove hard-coded Letter section repair

**Locations:** `src/conformer/engine.py:25–48`, `:1327–1344`.

`select_template()` correctly chooses the bundled A4 template for the basic inputs covered by its tests. On the clean path, `fix_sections()` still writes portrait size `12240 × 15840` and Letter-specific margins whenever it repairs a final landscape section.

**Reproduced with a template-backed A4 landscape document and an ensuing Heading 1:** selection returned `LI Report Template A4 23 July 2026.dotx`, while the output contained:

```xml
<w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>
<w:pgSz w:w="12240" w:h="15840" w:code="9"/>
```

The second section is Letter. This synthetic example was not CLEAN; the evidence here is the output page-size mutation, not a false-clean assertion. The pre-existing hard-coded repair becomes relevant now that A4 conformance is explicitly supported. Derive portrait dimensions/margins from the selected template or the appropriate source section, and add a full-pipeline A4 landscape-to-portrait test.

### R8 — P2 — guideline matrix: Heading 2 and measurement requirements are still misstated

**Locations:** `docs/conformance_coverage_2026-09-18.md:28`, `:64–66`, `:84`, `:167`.

I re-read `word/document.xml` from both **LI Report Template Guidelines A4 23 July 2026.docx** and the **LTR** variant. In both, the operative §3 paragraph says to use all caps for **Headings 1 and 2**, initial caps for **3–6**, and allows a consistent initial-caps exception for a very long **Heading 2** title. The matrix instead says “H1 ALL CAPS; H2–H6 initial caps” and assigns the long-title exception to **H1**. The sample Heading 2 in §4 does use initial caps, but that does not erase §3's explicit rule and exception. Record the sample inconsistency if necessary rather than silently reversing the rule.

The matrix also groups “inch/prime handling” under “not verbatim.” §8 explicitly distinguishes prime marks from smart quotes and says to spell out inches/feet in report prose, with prime marks acceptable in tables to save space. A blanket mandate to substitute Unicode primes is not sourced, and ligature normalization is a separate question; the actual measurement/context requirement is sourced and belongs in the matrix as such.

The corrected date format, section mapping, and removal of unsupported deterministic substitutions are useful improvements. The new matrix supersedes the old documents as an inventory, but cannot yet be described as wholly source-accurate.

## F7 correction to my original review

I **withdraw the original stale-template allegation**. I compared the operational Letter template with the A4 template and treated legitimate variant differences as age/drift. That inference was wrong. The ListBullet, Heading 4, and Heading 6 differences I listed are not evidence of a defect in the Letter asset.

The operational `template.dotx` at this commit has the exact MD5 part hashes quoted in the response:

| Part | MD5 |
| --- | --- |
| `word/styles.xml` | `c087f8fa11ce50b13be39a326d07f143` |
| `word/numbering.xml` | `22b0580b72935f2a06151e9ba8048f49` |
| `word/document.xml` | `f3d001aa431b46b075cd3be1d023a998` |

I accept the clarified provenance that this is the authoritative Letter template under its operational name. A separately named LTR `.dotx` is not present in this pinned tree, so these checks corroborate the reported operational part hashes rather than constitute an independent whole-file comparison of two bundled copies. No replacement of the Letter template is requested. R7 concerns the new A4 execution path, separately from this correction.

## Disposition by original finding

| Finding | Disposition at `b6c1b90` |
| --- | --- |
| F1 | Closed: `TableHeader` is re-established after clean-path template replacement; dedicated full-pipeline test passes. |
| F2 | Routing defect fixed; clarified historical-snapshot contract accepted. Deep current-formatting normalization remains the explicitly declared enhancement. |
| F3 | Partial; keep open for R2. |
| F4 | Partial; keep open for R3. |
| F5 | Partial; keep open for R1 and R5. |
| F6 | Partial; keep open for R6. |
| F7 | Original stale-template inference withdrawn; selector implemented; R7 remains on A4 section repair. |
| F8 | Closed: pairing and exact-boundary invariant address the original destructive cases; new tests pass. |
| F9 | Partial; keep open for R4. |
| F10 | Closed: replacement runner and successful two-architecture build observed. |

The preserve-aware scorer changes are consistent with needing a different baseline, but revision **count equality** is not record-exact preservation verification. Keep the revision ledger as the preservation authority. Likewise, exempting a whole table containing one revision and allowing all table `sz` values makes the scorer unsuitable as independent evidence that every current run conforms. The 300 passing tests establish the tested cases; they do not supersede the rendered counterexamples above.

## Reproduction starting point

The probes used the committed helpers in `tests/test_full_pipeline_regressions.py`: `_package`, `_HEADING`, `_table`, and `_FMT_REV`. Each was packaged into a separate temporary directory from the branch's `template.dotx`. Instantiate `Conformer(template_path, source_path)`, call `run()`, and inspect `items` and `conformance_status()`. For R3, use the returned judgment ID in `apply_with_decisions()` with the explicit `change:Normalize all table bodies to 11pt` value. Write `_output_parts()` into a DOCX ZIP to examine precisely the final package in Word. No revision acceptance/rejection or Word save was performed.

These are ordinary local report constructs, not adversarial network inputs. The next tests should target interactions between passes and actual effective formatting, especially the two CLEAN/render mismatches, before treating F1–F10 as collectively closed.
