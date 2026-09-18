# Session review and authoritative guideline audit

**Author:** Codex · **For:** Alex and Claude · **Date:** 2026-09-18

**Repository:** `worktodo77/li-report-conformer`

**Branch:** `feat/tracked-changes-judgment`

**Reviewed snapshot:** `843a20dc0a9a44817c3f1af3957a3e9b1ea72d48`

**This file:** `docs/reviews/session_and_guideline_audit_2026-09-18_codex.md`

**Request:** [session_review_request_2026-09-18_claude.md](session_review_request_2026-09-18_claude.md)

**Pointer:** https://github.com/worktodo77/li-report-conformer/blob/feat/tracked-changes-judgment/docs/reviews/session_and_guideline_audit_2026-09-18_codex.md

## Verdict

**Changes required. Do not treat this snapshot as a completed implementation of D-A3/D-A4 or as independently verified guideline conformance.** The session fixes several real defects, but a revision-free synthetic report still receives a CLEAN verdict while Word renders its header at **12 pt instead of 10 pt**. Other reproduced failures include editing quoted percentages, removing supposedly preserved small table fonts, losing formatting-change history on the legacy path, and an audit export that reports Clean after verification throws.

The gap analysis is useful as a historical investigation, but it is not a reliable current coverage specification. It combines obsolete status, unsupported synthesis rules, omitted exceptions, and an incorrect assertion that the bundled template's important styles match July's. **The original guidelines settle the date question: `D Month YYYY`, e.g. `3 April 2011`, without a leading zero outside quotations. They do not prescribe Month Day, Year.** No new ruling is necessary to establish what these sources say.

This review changes no implementation and makes no claim to have revalidated Warhoe. Its reported counts, screenshots, and local render results are prior-session evidence, not results reproduced here.

## Scope and evidence

I fetched the named branch from GitHub and reviewed an isolated checkout of the pinned commit. At fetch, remote HEAD and `843a20d` matched. I read the request, the session changes, both planning documents, the source and relevant tests, and the authoritative assets:

- [A4 guidelines](../../src/conformer/assets/LI%20Report%20Template%20Guidelines%20A4%2023%20July%202026.docx).
- [LTR guidelines](../../src/conformer/assets/LI%20Report%20Template%20Guidelines%20LTR%2023%20July%202026.docx).
- [July A4 template](../../src/conformer/assets/LI%20Report%20Template%20A4%2023%20July%202026.dotx), compared with the operational [template.dotx](../../src/conformer/assets/template.dotx).

Guideline evidence below comes from the original DOCX text and OOXML, including tables/text boxes, plus template style and numbering properties. Section names and distinctive text identify passages; I do not assign unverified page numbers. A4/LTR text comparison found layout, spacing, cached page-number, and wording differences, including a shorter LTR explanation of since/because, but no different date rule. The July template's cover also says `DD Month YYYY`.

There are **19 commits dated 2026-09-18 through the requested SHA**, not 20. To avoid silently narrowing the request, I also reviewed the immediately preceding `bfadf91` plan update: the latest 20 commits are covered below. The code delta for this session is `680042d^..843a20d`.

Validation performed:

- Existing complete Python 3.14 environment: `python -m pytest -q -k "not warhoe"` → **278 passed, 4 deselected**, 39 warnings, 82.50 s. Initial default-Python collection failed because `python-docx` was absent; no dependencies were installed. The existing complete environment resolved that environment issue.
- Independent synthetic probes, including complete `Conformer.run()` calls with packages built from the fetched template. No client report was opened or used.
- Actual Microsoft Word COM reads of two synthetic documents using the branch's reader. The clean-path output read **12 pt** in its first header cell. A deliberately bad second header cell escaped the reader/verifier's coverage.
- GitHub Actions inspection at this SHA: Apple Silicon build/test/package/upload job succeeded; Intel job remained queued. This verifies packaging execution, not application launch on a Mac.

The threat model throughout is the requested local desktop application. These findings do not depend on an adversarial network or speculative security requirements.

## A. Findings requiring correction

### F1 — P1 — The clean pipeline discards the newly created header style and falsely passes verification

**Introduced by:** `95dfb06`; missed by `2a2992b`.

**Locations:** `engine.py:890–945`, `1279–1281`, `1640–1649`; `tablespec.py:286–295`.

`fix_tables()` adds `TableHeader` and assigns it to header paragraphs. Later in the same clean run, `replace_parts()` replaces `self.styles` with `self.t_styles`, which does not contain `TableHeader`. The output retains references to a style definition it no longer contains. `_effective_style_size()` returns `None` for that missing style; the new check treats this as no issue.

**Reproduction:** build a two-row table with normal text and no revisions in a package carrying the bundled template's styles/numbering, then run the conformer. The output uses `TableHeader`, its styles part does not define it, and `conformance_status()` returns `clean=True`, with no table failure. Word COM readback reports `header_size=12.0`, `header_name="Times New Roman"`. The render verifier correctly flags this first-cell size defect.

**Required correction:** retain generated style definitions through final style replacement, or eliminate that replacement in the unified pipeline. Missing/unresolved paragraph and character styles must produce an unresolved result, not a pass. Add a full-run regression and Word readback; the existing helper-only style-import test cannot detect this ordering failure.

### F2 — P1 — The architectural pivot is not implemented across the application

**Status:** pre-existing behavior inconsistent with the session's stated new contract.

**Locations:** `engine.py:1618–1649`, `471–486`, `711–718`, `1726–1727`; `revisions.py:325–333`.

`_run_passes()` still selects two materially different pipelines according to `has_content_revisions()`. Formatting-only revisions do not select preservation. That path calls `revert_tracked_formatting()`, which removes `rPrChange`/`pPrChange` records. A synthetic document containing one formatting change and no insertion/deletion finishes with the record gone and `verify_preservation()[0] == False`.

In the preserving path, `strip_direct()` still skips revised paragraphs wholesale. The header fix reaches through revisions in one table-specific location; it does not conform fonts, sizes, styles, and other formatting everywhere. The new excerpt-quote and table-body offers only run in the preserving pipeline. A revision-free block quote gets no new quote-removal offer. The same report can therefore receive different conformance behavior merely because an unrelated insertion exists elsewhere.

The design document also contradicts the request: architecture §5 says old formatting snapshots are normalized so rejection cannot restore nonconforming formatting, while the request and implementation say snapshots remain byte-exact. Architecture §8 still calls this an open item. Preserving old values necessarily permits rejection to restore them. These are different guarantees; document the selected contract explicitly. For this review I used the request's **record-exact, current-formatting-only** interpretation.

**Required correction:** use one history-preserving conformance path, including formatting-only revisions and comments; apply current-formatting changes across supported stories/wrappers; share the same feature offers and gates. Keep the design marked incomplete until this is true. Retain the existing content, comment, numbering, and rollback protections during the migration.

### F3 — P1 — New automatic text edits alter verbatim quotations and identifiers

**Introduced/exposed by:** `26a6117`, `d93b370`, `780b337`.

**Locations:** `engine.py:142–155`, `1200–1211`, `1224–1257`, `house_norm()`.

The gate is not independent evidence of semantic safety: it authorizes the same text transform. Two full-run counterexamples pass preservation with no rolled-back pass:

1. Body quotation split into runs: `He said “the value ` / **`30%`** / ` was final.”` becomes `He said “the value 30 percent was final.”`. `_house_edit()` only sees one run at a time, so its double-quote-span protection cannot see the enclosing quotation. Different formatting, a spell-check edit, or ordinary Word run splitting is sufficient to trigger this.
2. An `ExcerptorQuote` paragraph containing `“The period was 2017-2019 inclusive.”` becomes `The period was 2017–2019 inclusive.`. Removing the outer pair can be a separate approved operation, but changing the interior hyphen is not verbatim preservation. `typography()` does not exclude excerpts or protect inline quoted spans.

Additional direct counterexamples to the claimed false-positive-free range patterns:

| Input | Actual transform | Problem |
|---|---|---|
| `A7-14 days` | `A7–14 days` | Time-unit pattern lacks an alphabetic left boundary; can rewrite an activity identifier. |
| `Table 2017-2019` | `Table 2017–2019` | Year pattern does not exclude a syntactically valid caption/reference number. |
| `2017-2019A` | `2017–2019A` | Year pattern lacks an alphabetic right boundary. |
| `from 7-14 days` / `between 2017-2019 inclusive` | En dash inserted | Original §8.2.1 explicitly excludes en dashes for spans introduced by “from” or “between.” Flag the wording rather than silently applying this rule. |
| `10%-20%` | `10 percent-20 percent` | Percent rule works independently of range recognition; NUM-4 coverage is incomplete. |
| `2017-2019.` | Unchanged | The terminal punctuation period is rejected as though it were part of a numeric identifier. |
| `a — b — c` | `a—b — c` | Consuming the neighboring character prevents matching the adjacent second dash in the same pass. |

Currency/ordinary hyphen examples already covered by the tests remain useful, but they do not prove this scoping claim. `15%20encoded` also becomes `15 percent20encoded`; prose detection is currently a style/run proxy rather than recognition of quantities versus URLs or identifiers.

**Required correction:** recognize protected quotation spans across runs before applying any text transform, leave excerpt interiors untouched, map approved edits back to runs, and guard identifiers/captions/fields and the explicit range exceptions. Add negative tests at full-pipeline level. Percentage spelling also needs an authority separate from these original guidelines; see part B.

### F4 — P2 — “Keep smaller table fonts by default” and the normalization alternative do not work as offered

**Introduced by:** `f81e0a5`.

**Locations:** `engine.py:1687`, `1727`, `1838–1886`, `2972–2975`.

The earlier `_conform_tables_preserving()` removes every unmasked direct `w:sz` other than 22. Consequently, an ordinary 9 pt body is already normalized before `_offer_table_body_normalization()` runs. A complete template-backed run removes the 9 pt size, offers **no** `table-body-size` judgment, and reports CLEAN.

Conversely, the small sizes still present because they sit inside `w:ins`/`w:del` can generate an offer, but `_normalize_table_body_to_11pt()` uses `_mask_revisions()` with its default `content=True`. It cannot reach those sizes when normalization is selected. A helper probe confirmed the 9 pt size survives the normalization method.

The detector also counts explicit `w:sz` values rather than effective sizes for all runs. One explicit 9 pt run and many unstyled 11 pt runs satisfy “all explicit sizes below 22,” although the table is not uniformly small. `w:szCs`, style-inherited sizes, and nested-table geometry are not adequately represented.

**Required correction:** determine effective body sizes before destructive normalization, retain the chosen default, and ensure the explicit alternative changes all intended current formatting while preserving old records. Test analyze→apply, tracked and untracked bodies, mixed/inherited sizes, and nested tables. The current tests bypass the earlier table pass and therefore miss the feature failure.

### F5 — P1 — The verdict and audit can still certify unresolved or unverified output

**Introduced/expanded by:** `283fe64`, `2a2992b`; the omission of structural advisories predates these changes.

**Locations:** `engine.py:2658–2707`, `1559–1572`; `tablespec.py:286–295`; `audit_export.py:181–199`; `ui/window.py:1197–1229`.

Demoting completed header-fill corrections and legitimate numeric-column alignment is reasonable. Demoting **all** `tables_review` entries is not:

- A visible tracked header paragraph on `Heading4` resolves to 11.5 pt. The new check emits `header-style-size` with severity `review`; the verdict demotes it to informational and returns `clean=True`. This is not restricted to the six empty historical artifacts cited in the request. It accepts actual visible wrong-size headers. The displayed detail also truncates 11.5 to 11 because it uses integer division.
- The resolution check only inspects the first paragraph and only when **no** direct size occurs anywhere in the cell. A correct direct 10 pt run can suppress checking other runs that inherit 11/12 pt. Character styles and defaults are also missing from this resolution model.
- A complete synthetic run with `REF _Missing \\h` emits `xref-target-missing` into `self.audit`, but still returns `clean=True`. Known broken references, disallowed caption bases, and heading-level audit findings are not inputs to `conformance_status()`. Refresh cannot recreate a missing target. Separate advisory preferences from actual unresolved conformance defects.
- In `audit_export.build_records()`, an exception from `conformance_status()` falls back to `not (n_flip or n_integ or n_tblfail)`. I injected a verifier exception on a real synthetic conformer: exported `conformance_clean=True`, conformance verdict “Clean,” unresolved verdict “None.” This reintroduces the fail-open behavior the plan explicitly forbids. The UI's corresponding exception branch also zeroes the unresolved counts and can display “Nothing left unresolved,” despite unknown verification.

The lowercase substring test `'nested' in note` happens to distinguish the two current message bodies, but also examines the locator/heading text. A heading containing “nested” can turn a completed correction into an unresolved note; an additional unresolved note type would default to informational. Use typed reason codes and an explicit allowlist of informational outcomes.

**Required correction:** make unknown fail closed; propagate verified failures and genuinely unresolved audits into one shared verdict; classify specific legitimate variations individually. Do not equate “preserved” with “approved by the guidelines.” Exercise save labels, UI, JSON audit, and exported audit together.

### F6 — P1 — The Word harness is useful but is not yet a trustworthy acceptance gate

**Introduced by:** `47af482`.

**Locations:** `tests/render/word_render_read.ps1:48–96`; `tests/render/render_verify.py:38–52`, `130–210`.

**Incorrect constant:** the reader calls `.Table.Condition(1)` and labels it first-row formatting. `wdFirstRow` is **0**; **1 is `wdLastRow`**. This is confirmed by [Microsoft's WdConditionCode documentation](https://learn.microsoft.com/en-us/office/vba/api/word.wdconditioncode). In the actual synthetic read, the purported first-row style returned automatic fill, bold=0, size=11, while the first cell rendered teal and bold. Any fallback inference from this record is based on the wrong row.

**Coverage holes demonstrated:** the reader samples only `Rows.Item(1).Cells.Item(1)`. A two-column fixture with first header 10 pt and second header 16 pt produces **zero verifier defects**. A stubbed reader result with mixed size `9999999`, nonbold text and Calibri likewise produces zero defects. Font name, bold, and repeating-header properties are collected but not asserted. Missing size, mixed size, and `header_error` do not become unknown/failure.

**Field and list limitations:**

- REF failure matching looks only for `Bookmark not found`; the ordinary REF error `Error! Reference source not found.` is not counted. Blank PAGEREFs are collected but not failed.
- `updated=True` records the requested switch even when update operations throw and their exceptions are swallowed. The update return value is discarded. Footnote and other story fields are not explicitly traversed; the guidelines specifically require footnote field updates separately.
- “At least half the references show 1” is a heuristic, not proof of incorrect destinations. A short document can legitimately reference page 1 repeatedly. The test needs known bookmark/page expectations and confirmed repagination/updates.
- `ListString` is better than `ListType` for mixed outline definitions, and BGR→RGB conversion and comma-separated style aliases are correct for the observed English Word data. However, an empty marker is classified as a bullet, suppressed/unlisted list paragraphs can escape `Document.ListParagraphs`, and the test checks marker class rather than sequence or destination identity. `a.`, `1.`, and duplicate `1.` can all pass a numbered-style check.
- Scan caps and skipped nested tables need explicit coverage/unknown reporting. “No defects” cannot mean the entire document renders to the guideline.

**Required correction:** fix the constant, assert all relevant cells/runs and rendering properties, treat inaccessible/mixed observations as unresolved, verify every required story's field updates and results, and commit a synthetic Word acceptance suite with known expected failures. Keep the present reader as diagnostic instrumentation until then. It is not currently invoked by pytest/CI or the production save gate.

### F7 — P1 — The operational template is materially different from the authoritative July template

**Status:** audit inaccuracy and unclosed realignment work; `9d3644b` adds the new asset without selecting it.

**Locations:** gap-analysis “Deeper audit addendum”; `ui/window.py:565`; `conformer.spec` asset list.

The claim that important styles already match is false for `ListBullet`, among others. Direct OOXML comparison:

| Property | Operational `template.dotx` | July A4 `.dotx` |
|---|---|---|
| `ListBullet` direct left indent | 1080 twips | Absent |
| `ListBullet` numbering level | `ilvl=3` | `ilvl=2` |
| `Heading4` left/hanging indent | 1440/1440 | 1350/1350 |
| `Heading5` left/hanging indent | 1800/1800 | 1710/1710 |
| `Heading6` left/hanging indent | 2160/2160 | 2070/2070 |
| `Heading6` font size | `sz=23` = 11.5 pt | `sz=21` = 10.5 pt |

There are also title, spacing, TOC-tab, and complex-script-property differences. Some are page-size-specific, which is another reason not to collapse A4 and Letter into an unqualified “same template.” `GridTable4` does support the core teal/black/10 pt header specification; that does not validate all the other styles.

**Required correction:** finish the already-planned authoritative-template adoption with explicit A4/Letter handling and list-numbering dependency verification. The original guideline DOCX is not a Letter `.dotx` substitute; §1 expressly says not to use the guideline document as the template. Do not mark template-driven font/indent conformance complete while the app and build still select the older asset.

### F8 — P2 — The excerpt heuristic does not establish that a paragraph contains one outer quote pair

**Introduced by:** `a9100ca`.

**Locations:** `engine.py:1806–1836`, `1888–1908`.

The opening and closing marks are checked against independent sets, not paired or balanced. Reproduced:

- `“A quote ending in a nested ‘word’` → `A quote ending in a nested ‘word`. This is an opens-only outer quote, yet the code removes its opening double quote and the inner closing single quote.
- `“One quote.” Some prose. “Another quote.”` → `One quote.” Some prose. “Another quote.`. These are two quotations, not one pair surrounding an excerpt.

The judgment call makes intentional boundary removal reviewable, but the default recommendation is still based on a false assertion that the pair is redundant. `verify_preservation()` protects revisions/comments, not arbitrary settled quotation punctuation. Leading/trailing empty `w:t` runs or text-bearing fields can also cause the helper to remove only one boundary. The tests cover a single-run happy path and skip, not these cases.

**Required correction:** match the exact pair, check nesting and that the outer quote encloses the entire excerpt, find the first/last actual text character across runs, and reject ambiguous/field-containing cases. Preserve opens-only multi-paragraph quotations. Add a local text invariant: accepted output must equal input minus exactly the approved two boundary characters.

### F9 — P2 — Header repair still lacks structural guards for some ordinary OOXML cases

**Introduced/exposed by:** `111600f`.

**Locations:** `engine.py:2848–2867`, `2894–2901`, `2986–2998`.

For the canonical `w:*` change records tested, masking/unmasking preserves the old snapshot string exactly while removing current size properties; inserted/deleted text and wrapper metadata are not the target of these substitutions. I reproduced that positive property. It is not evidence that every whole-pipeline case is safe or conformed:

- `_HEADER_BODY_STYLES` is a small allowlist, not a numbering guard. `Normal` plus an explicit `numPr` is reclassified to `TableHeader`, contrary to the stated “numbered paragraphs are never reclassified” promise. A default/style-inherited list needs resolution too. Conversely, a non-numbered `BodyText` or custom body style can be excluded unnecessarily.
- An input `<w:p><w:pPr/><w:ins ...>...</w:ins></w:p>` produces **two `w:pPr` children**: a new styled one plus the original self-closing one. It is well-formed XML but not valid paragraph-property structure. `validate_output()` checks XML parsing, not this schema constraint.
- Before the header-specific guard runs, `cell_para()` changes every unmasked styled cell paragraph to `TableData`, including an untracked heading/list. The later guard cannot recover the original style. Test the complete table pass, not only `_repair_stray_header_formatting()`.
- Size/color stripping does not resolve character styles or normalize explicit font/bold overrides. Preserving an old formatting snapshot is compatible with current-formatting repair, but does not ensure rejecting the old change still looks conforming.

**Required correction:** operate on current paragraph/run properties structurally, keep a single `pPr`, resolve numbering before reclassification, and share the guard across all table passes. Add both accept/reject projection checks and current Word-format checks; retain old snapshots byte-exact under the request's contract.

### F10 — P2 — Intel macOS builds target a retired runner

**Introduced by:** `dce3bd2`; not fixed by `595334f`.

**Location:** `.github/workflows/build-macos.yml:27`.

`macos-13` was retired in December 2025. See [GitHub's retirement notice](https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down/) and [current runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners). A supported explicit Intel label is `macos-15-intel`; use a supported ARM label for Apple Silicon and assert `platform.machine()` in each job. At inspection, [this SHA's Intel job](https://github.com/worktodo77/li-report-conformer/actions/runs/35396476192/job/105766364328) was queued while [Apple Silicon](https://github.com/worktodo77/li-report-conformer/actions/runs/35396476192/job/105766364552) had built and uploaded successfully.

The platform-extension/icon changes are directionally sound. Do not claim a runnable dual-architecture release solely from PyInstaller success: add an application-start smoke check and verify the collected Qt platform plugin exists in the produced app. No Mac launch verification was performed in this review.

### Other focused observations

- **Centered equations (`c5bf24a`):** preserving the demonstrated centered Normal equation is correct. The predicate is too broad to certify that every centered paragraph is a display equation, and too narrow for style-inherited centering/native math without direct `jc`. More concretely, `strip_direct()` now retains `jc=center` on **every** paragraph style, even numbered body prose/headings excluded from the classification exemption. Preserve the display element's alignment using one explicit classification policy; flag ambiguous ordinary prose. This is a scope/coverage issue, not evidence the demonstrated equation fix itself fails.
- **Every row skippable (`4b402c1`):** the two newly categorized operations work in their tests, and removing the misleading tally is reasonable. The absolute claim remains untrue: the UI explicitly renders uncategorized log entries as static labels. Clean-path operations such as `fix_tables`, `fix_sections`, and `replace_parts` still emit uncategorized changes and lack matching category skip gates. Read-only audit summaries need not be skippable, but all actual mutations advertised as skippable must round-trip through analyze/apply.

## Commit coverage

All hashes below are in the fetched history; grouped rows still cover each named commit.

| Commit(s) | Review result |
|---|---|
| `bfadf91` | Reviewed as twentieth/backstop commit. “P1 complete” means a reduced delivery scope, not completion of the original P1 contract. Heading numbers being live does not prove correct sequence, restart, or parent linkage. |
| `680042d`, `939bcf2` | Useful diagnosis and contract direction; implementation and old-record policy remain inconsistent (F2). |
| `47af482` | Useful Word instrumentation; wrong condition constant and acceptance blind spots (F6). |
| `95dfb06` | Attributed-row insertion repair is sound for tested rows; clean pipeline loses the new header style (F1). |
| `c5bf24a` | Demonstrated equation case improved; classification/strip scopes disagree, as noted above. |
| `4b402c1` | Cross-reference styling/updateFields skip guards and tally removal are valid narrow improvements; universal Skip claim is too broad. |
| `111600f` | Current header formatting can pass through revisions without changing tested old snapshots; guard/structure coverage incomplete (F2, F9). |
| `283fe64` | Distinguish completed corrections from unresolved work, but blanket informational treatment and fail-open audit fallback are incorrect (F5). |
| `dce3bd2`, `595334f` | ARM CI packaging succeeded; Intel runner retired; dependency/test addition alone does not close launch validation (F10). |
| `a9100ca` | Explicit quote-removal offer is reasonable; enclosing-pair detection is unsafe (F8), feature absent from clean path (F2). |
| `f81e0a5` | Offer is contradicted by earlier normalization and cannot reach surviving tracked sizes (F4). |
| `2a2992b` | Adds a useful paragraph-style lookup; incomplete cascade and non-gating severity miss F1/F5. |
| `26a6117`, `d93b370`, `780b337` | Positive examples pass, but scope, quotation, identifier, and repeated-dash failures remain (F3). |
| `dd4d9ba`, `9d3644b`, `843a20d` | Review request and original-source assets make this audit possible. New source is not yet the operational template (F7); several completion claims need correction. |

## B. Audit against the original LI guidelines

### Source interpretation corrections

1. **Dates are settled by the originals.** Additional Checks, “For dates,” says `DD Month YYYY`, illustrates `3 April 2011`, forbids leading zeros on 1–9, and exempts excerpts/quotes. The same text appears in A4 and LTR. Month Day, Year is a synthesis error. Convert only unambiguous dates outside protected content; numeric `3/4/11` still needs interpretation.
2. **Section references are shifted in much of the gap analysis.** The original has §5 Numbered Paragraphs, §6 Excerpts and Quotes, §7 Other Bulleted and Numbered Lists, §8 Other Guidelines. The intervening sample heading section is numbered §4. The gap analysis repeatedly calls these §4/§5/§6/§7. Use section title plus original number, or stable requirement IDs with exact source anchors.
3. **Column alignment is contextual, not a universal positional rule.** §8.7 says “appropriate alignment” and gives category-left/numbers-right as an example. It does not require every first column left, including a numeric first column, or all headers centered irrespective of meaningful layout. Template defaults and authored exceptions must be distinguished. D-3 is an additional project policy, not verbatim guideline text; its promised conservative inference is not delivered merely by retaining existing direct alignment.
4. **The en-dash exception is missing.** §8.2.1 explicitly says not to use an en dash after “from” or “between.” This omission directly affects the new rule (F3).
5. **Acronym pluralization has an explicit exception.** Additional Checks permits apostrophes for abbreviations with mixed case or two or more interior periods, e.g. `M.A.’s`, `Ph.D.’s`. It also distinguishes plurals from possessives. The gap's one-line plural rule omits this qualification; a blanket apostrophe removal is not safe.
6. **Sentence bullets also include multiline items.** Additional Checks says a sentence **or an item using more than one line** uses “List bullet as a sentence.” Gap §15 says the real criterion is sentences versus short phrases, omitting this second condition. Character length can flag candidates but does not measure rendered lines.
7. **Footnotes require both rules and exceptions.** §8.3 specifies roman reference marks, placement after punctuation, and examples using `para.`, `p.`, `pp.`, en dashes, a period followed by two spaces and a bold bracketed exhibit identifier. It also explicitly allows citation formatting to vary by report/client. The gap dismisses locator forms/ranges as language while proposing unconditional end-period insertion. A citation ending in a source tag must not be treated as though punctuation belongs after the tag; preserve quoted titles and deliberate source formatting. Detect first, apply only structurally unambiguous repairs.
8. **Latin formatting is broader than e.g./i.e.** §8.1 includes `force majeure` and other Latin phrases; §8.2.2 requires italicized `i.e.,`/`e.g.,`. Adding commas alone is incomplete. This is a strong scoped formatting candidate after quote/field recognition is fixed.
9. **Footnote-field refresh is not demonstrated.** The gap's §17 assertion that `updateFields=true` satisfies the separate footnote update requirement is not evidence. The original §8.11 expressly distinguishes the footnote selection/update step. The harness does not validate it. Field-refresh arming, successful execution, and correct refreshed results are three different coverage claims.
10. **Contextual tense and naming rules must survive simplification.** Additional Checks prefers past tense for completed acts and present tense for opinions; it does not ban “shall” universally. It spells out `Long International, Inc.` at first appearance in Section I, then `Long International`, while allowing `LI` during drafting. Record that explicit convention separately from general acronym expansion.

### Coverage crosswalk for gap-analysis sections 0–17

This table evaluates the gap analysis as a whole, including its deeper addenda, rather than treating an early stale row as the final conclusion.

| Gap section | Audit conclusion and required correction |
|---|---|
| **0 Ground truth** | Core Normal/NumberedParagraph/TableData/FootnoteText sizes, teal/black table style, and Excerpt indents are supported by the July template. Do not generalize all heading sizes: H6 is 10.5 pt. Distinguish ASCII/complex-script font properties and actual style/numbering inheritance. |
| **1 Tables** | Correct diagnosis of the former navy/white/gray implementation. Mark those historical defects as repaired where verified, retain F1/F4/F5/F9 as current. Column alignment is an example, not a universal first-column rule. Add repeat-header checks for multipage tables and table captions appearing only on the first page. |
| **2 Headings** | The later H2 exception discussion corrects the initial oversimplification. Include genuine typed caps, explicit H1 new-page/36 pt exception, and the lead-in rule. Consistent initial caps alone is not proof that an exception was approved, although D-4 authorizes preserving it for this project. |
| **3 Numbered paragraphs** | Style presence is not verified sequence. Retain start-at-L1/no-skips, correct markers/restarts, and separation from other numbered lists. Fix source reference to original §5. |
| **4 Excerpts** | Detection exists, so “not detected/normalized” is stale even within the document's own addendum. Boundary stripping is now offered only on one path and needs F8. Preserve excerpt interiors and source/footnote placement. Original §6. |
| **5 Bullets** | Style-name recognition is partial coverage. Add effective list indent/marker/context, multiline-item criterion, short-item spacing, and sentence-continuation casing/punctuation exceptions. Operational template drift invalidates the “style repair solves it” assumption. Original §7. |
| **6 Footnotes** | Reference/body styles are partial implementation. Verify reference placement and punctuation independently. Add report-specific citation scheme and locator/tag formatting; avoid unconditional punctuation surgery. |
| **7 Typography** | Good inventory start; ranges/em-dash statuses are stale and implemented coverage is not complete. Add from/between exception, all relevant Latin formatting, paragraph-wide quote protection, and distinctions among body measurements, table prime marks, and quoted text. Footnote text is not automatically covered by body `typography()`. |
| **8 Captions/figures** | Subtitle handling remains open. Add image-of-a-table classification/source attribution, multipage table caption/repeat-header behavior, page-size-specific geometry, following-section header distance/page continuation, and actual readable-size/layout checks. |
| **9 Cross-references** | Field requirement supported; add hyperlink switch, Cross Reference style, targets, cached results, all five categories, all relevant stories. Update statuses for new existing-REF styling/target audit while retaining unresolved coverage. |
| **10 Fonts/sizes + template addendum** | Template-driven conformance is conditional on the correct template, style, cascade, and final output. “Important styles already match” is incorrect (F7). Inspect effective runs, not just absence of direct formatting. |
| **11 Caption numbering** | H1/H2 basis and consistency accurately reflect source §8.6. Add the hidden H2 prerequisite described below. An armed refresh is not fixed sequence; audit findings do not currently gate CLEAN. |
| **12 Report headings** | Detailed source reading is largely accurate. Keep sequence verification open; Word computing numbers live does not ensure correct parent links/restarts. Original §3. |
| **13 Numbered sublevels** | Correctly recognizes deeper sequence gaps; update partial implemented audit status. Original §5, not §4. |
| **14 Quotes** | Good distinction between leaked italics and legitimate citation italics. Correct source number, update current status, and qualify “deterministic safe” boundary removal with F8. |
| **15 Lists** | Correct concern about hierarchy/context; amend the multiline-item omission and fix original §7 reference. |
| **16 Dashes/primes/footnotes** | Add range exceptions; grammar determines inches versus adjectival `-inch`. The originals illustrate straight prime characters, not a requirement to replace all with Unicode primes. Footnote example uses `para.` rather than `paragraph` or **¶**; gap text incorrectly substitutes **§** in one summary. |
| **17 Cross-reference deep audit** | Preserve useful target/style taxonomy, update implemented statuses, and retract automatic footnote-refresh assurance. No cached “Error!” text is not proof all bookmarks resolve: the plan itself later reports 12 missing targets. |

The unnumbered “FULL gap analysis of Section 10” does enumerate the 38 main additional-check bullets, but its classifications need the corrections above. Several Warhoe claims also contradict one another: 1,507 versus 1,480 footnotes, 0 versus 13 static captions, and no broken references versus 12 missing targets. These may describe different snapshots or counting methods. Preserve them as dated evidence with input/output hash and method; do not present them as one current census.

### Missing or materially underrepresented source requirements

These deserve explicit rows in a revised coverage matrix, even where the result is advisory or a workflow limitation:

- **Front matter:** cover project/report titles in caps, author initial caps/full names, the specified post-nominal period convention (`P.E.`, `P.Eng.`, `Ph.D.`, `M.B.A.` versus CCP/CCE/PSP), and removal of instructional placeholders. Lists of Tables/Figures/Attachments/Exhibits use “Table of Figures,” with hanging indents adjusted to the numbering scheme. Detect placeholders; do not invent names or delete intentional draft/confidentiality labels.
- **Paper size and page geometry:** §1/§8.1 distinguish Letter and A4 and reserve space for the logo. §8.10 specifies landscape one-inch margins, protected section breaks, removal of START/END COPY instructions, and portrait-after-landscape header distance **1.3 inches**, footer **0.5 inches**, and page numbers continuing from the previous section. Merely preserving some section breaks does not verify these properties. `fix_sections()` also hardcodes a Letter-sized final portrait section, so A4 needs an explicit profile.
- **H2 caption basis prerequisite:** §8.6 requires an H2 even in sections without figures/tables when that basis is chosen, and explains the hidden “Hidden text for numbering” heading, which must not leak into the TOC. Basis detection alone misses this structural requirement.
- **Tables represented by images:** §8.7 says label them Tables, not Figures, and supply a source footnote at the end of the title or a source subtitle. The source/label choice is advisory; existing label/source presence and subtitle/caption styling can be checked deterministically.
- **Figures and long tables:** §8.8 gives the title/subtitle/graphic-spacing sequence; §8.10 says a multipage table's caption appears only on the first page while its header repeats. A small image may need landscape or an external attachment instead of font shrinking. Render/layout inspection is needed for readability.
- **Cross-reference hyperlinks and stories:** §9 explicitly requests “Insert as hyperlink,” not just a field and a character style. Verify existing switches, not only newly built fields. Include footnotes and other relevant stories in field coverage and refresh evidence.
- **Explicit text exceptions and conventions:** from/between ranges; acronym apostrophe exceptions; Latin italics; first/full LI naming; modifier lowercase `project`; current opinions versus completed-action tense. These are not adequately represented by broad deterministic/editorial labels.

### Corrected deterministic-rule inventory

“Deterministic” describes execution, not whether a regex can safely infer meaning. Separate **source authority**, **detection**, **automatic repair**, **reviewer-approved repair**, and **verification**. The following uses the request's IDs only as labels; they are not identifiers in the original guidelines.

| Rule family | Authority and actual coverage | Appropriate treatment |
|---|---|---|
| **CAP-1/2** generic parties/technical terms | The originals do not specify the synthesis's complete lowercase word lists. Determiners do not distinguish generic roles from contract-defined terms. | Separate source/approved project policy; flag ambiguous defined terms, do not call this verified guideline coverage. |
| **CAP-3** proper nouns | Avoiding a few names is not a general proper-noun recognizer. No standalone comprehensive implementation was found. | Preserve known names; audit against an explicit matter glossary rather than claim complete coverage. |
| **CAP-5** Report/Project | Original Additional Checks explicitly supports subject-Report/subject-Project capitalization **and lowercase project modifiers**. `_HOUSE_CAP_RE` changes `the project schedule` to `the Project schedule` and cannot establish that `the report` is the subject Report. | Contextual candidates/approved glossary; current regex is unsafe/incomplete. |
| **ACR-1** first-use/thereafter | Explicit original requirement, plus separate LI naming convention. | Document state can detect missing definitions/unused expansions. Automatically inventing expansions or resolving competing definitions needs review. |
| **ACR-2** pluralization | Explicit with possessive and mixed-case/period exceptions. `_ACR_PLURAL_RE` only accepts straight apostrophes and `[A-Z]{2,}`; typography runs first and converts them to curly. It does not cover `P&ID’s` as documented, and `RFI's response` can be possessive. | Repair recognized plurals with syntax/exception guards; do not advertise complete implementation. |
| **PUNC-1** Oxford comma | Explicit in §8.1 and Additional Checks. | Detect/review parsed lists. This needs clause/list understanding, not simply document-level state; commas can change meaning. |
| **PUNC-2 / NUM-4 ranges** | Explicit with exceptions. Partial patterns, false positives and quotation edits reproduced (F3). | Scoped repair after protected-span/context handling; ambiguous IDs and constructions remain review items. |
| **PUNC-5** e.g./i.e. | Originals require italics and following comma; implementation does not complete the formatting requirement. | Good deterministic formatting/comma candidate outside quotes, fields, identifiers, and citations requiring exact text. |
| **PUNC-6** sentence spacing | Two spaces explicitly required. Current run-local regex is partial for sentence boundaries across runs and abbreviation/quote cases. | Paragraph-level boundary-aware repair; do not alter verbatim excerpts. |
| **NUM-2** percentages | No numeral-plus-“percent” mandate was found in either original guideline document. It is present in the synthesis. | Record separate authority if intended; do not silently treat it as established by these originals. Also fix F3 before any automatic use. |
| **NUM-4 date format** | Originals say `D Month YYYY`, no leading zero except quotations. Current leading-zero handling is partial and lives in typography, which also touches quotations. | Unambiguous named-month formats are a scoped deterministic opportunity; ambiguous all-numeric dates are review-only. |
| **American spelling/punctuation** | Explicit §8.1. A finite dictionary is partial, and `analyses → analyzes` corrupts the noun: `The analyses are complete` becomes `The analyzes are complete`. `matrices → matrixes` is not required by these guidelines. | Remove ambiguous lexical rewrites from unconditional repair; handle punctuation placement and quote protection separately. |
| **programme→schedule / U.S.** | These exact substitution mandates are not stated in the original sources reviewed. “Programme” is not always a schedule. | Separate documented authority/context; no blanket claim of original-guideline compliance. |
| **Inches/feet and smart quotes** | Explicit body/table/quotation distinction. The current body rule handles inch-like forms, not the whole feet/inches grammar. `2-inch` versus `2 inches` depends on use. Smartening straight characters must spare tabular measurements and quoted exceptions. | Context-scoped repairs; test complete quantities and split runs. |
| **Ligatures** | Reasonable text normalization, but not an explicit requirement located in these guidelines. | Label as a separately authorized normalization, with protected content policy. |
| **TERM-1 / CITE-2** consistency | Broad consistency is useful; these originals specifically require agreed citation schemes and precise LI naming, not the synthesis's full terminology taxonomy. | Document-wide audit with an approved glossary/source scheme. |
| **GRAM-3** that/which | Explicit original guidance. | Local syntactic/semantic analysis and review; document-wide state alone does not make it safe. |
| **TENSE-1 / GRAM-1** | Originals distinguish completed acts from opinions and temporal since from causal because. | Reviewer-approved semantic edits. Do not implement a blanket shall→present or since→because substitution. |
| **GRAM-5 / NUM-1 / PUNC-4 / PUNC-3** | Sentence-initial But→However, blanket 0–9 spelling, scare-quote removal, and general avoidance of em-dash clause joining were not found as rules in the original guideline text. Excerpt boundary marks are a separate explicit requirement. | First establish separate authority; if retained, reviewer-approved editorial suggestions, never inferred automatic conformance. |

The proposed split is therefore **not right as stated**. The defer/review direction for meaning-changing work is sensible, but several “implemented DET” entries lack source authority or safe coverage, and GRAM-3/PUNC-1 are not merely missing a document-state mechanism.

### Safe opportunities and corrected priorities

Do not add more automatic text rules before repairing the preservation and verdict failures. After those fixes, useful bounded work includes:

1. **Deterministic audits first:** unresolved/missing style IDs, effective sizes, repeated headers, missing bookmarks, hyperlink switches, heading/list level skips, subtitle adjacency and caption spacing, source placeholders, and section geometry against the selected paper profile. These can identify defects without guessing substantive content.
2. **Formatting repairs with known scope:** italicize recognized Latin expressions; apply Footnote Reference/Footnote Text and roman reference marks; set caption-after spacing to zero when followed by a confirmed subtitle; remove demonstrably empty trailing footnote paragraphs while preserving anchors/fields; repair approved header formatting across current tracked and untracked content.
3. **Carefully scoped text repairs:** explicit month-name date normalization, quote-exempt leading-zero removal, and clearly identified page/date/time ranges with all original exceptions. Split-run and protected-span handling are prerequisites.
4. **Keep contextual repairs reviewable:** citation `id./ibid.` depends on the preceding source/locator even though the guideline gives form examples; do not infer same-location meaning solely from a bare `Id.`. Likewise footnote terminal punctuation, list semicolons, possessives, acronym expansion, and causal since need contextual checks. The plan may retain an explicitly approved narrow form-only id./ibid. policy, but must not call it citation verification.
5. **Respect selected spacing/layout exceptions:** the originals permit agreed single or 1.5 spacing. “Normalize to template” is not permission to erase an agreed 1.5-spaced report or the H1 36 pt short-section exception. Record the profile or surface the choice.

Update the realignment plan with distinct columns for source requirement, current behavior at a named SHA, detecting test, repair policy, output verification, and accepted exception. Reopen P0 template/effective-formatting and P1 actual sequence/field-result work. “Deferred because Warhoe already uses fields” is a scope decision, not evidence the general requirement is satisfied.

## Reproduction appendix

These examples use only tracked repository assets. They capture the principal full-pipeline defects without a privileged report. Run from the repository root with the project's dependencies available and `src` on Python's import path. The example creates a new `review_probe_output` folder; use a fresh destination for repeat runs.

```python
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import re
from conformer.engine import Conformer
from tests.test_table_body_normalize import _tbl

tpl = Path("src/conformer/assets/template.dotx")
dest = Path("review_probe_output")
dest.mkdir(exist_ok=False)
heading = ('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
           '<w:r><w:t>INTRODUCTION</w:t></w:r></w:p>')
revision = ('<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
            '<w:ins w:id="99" w:author="Reviewer" '
            'w:date="2026-09-18T00:00:00Z">'
            '<w:r><w:t>Tracked content</w:t></w:r></w:ins></w:p>')

def package(name, body):
    with ZipFile(tpl) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts['[Content_Types].xml'] = parts['[Content_Types].xml'].replace(
        b'wordprocessingml.template.main+xml',
        b'wordprocessingml.document.main+xml')
    xml = parts['word/document.xml'].decode('utf-8')
    sect = re.findall(r'<w:sectPr\b.*?</w:sectPr>', xml, re.S)[-1]
    parts['word/document.xml'] = re.sub(
        r'<w:body>.*</w:body>',
        lambda _: '<w:body>' + body + sect + '</w:body>',
        xml, flags=re.S).encode('utf-8')
    path = dest / (name + '.docx')
    with ZipFile(path, 'w', ZIP_DEFLATED) as z:
        for n, data in parts.items():
            z.writestr(n, data)
    return path

for name, extra in [('clean', ''), ('preserve', revision)]:
    src = package(name, heading + _tbl() + extra)  # 9 pt table body
    c = Conformer(str(tpl), str(src))
    c.run()
    print(name, 'clean:', c.conformance_clean(),
          'header style defined:', 'w:styleId="TableHeader"' in c.styles,
          '9 pt retained:', 'w:sz w:val="18"' in ''.join(c.items),
          'body-size offers:', [j.id for j in c.pending_judgments
                                if j.kind == 'table-body-size'])
    with ZipFile(dest / (name + '-out.docx'), 'w', ZIP_DEFLATED) as z:
        for n, data in c._output_parts().items():
            z.writestr(n, data)
```

Observed at `843a20d`: both cases print `clean: True`; the clean case has no header style definition; neither retains 9 pt or offers `table-body-size`. Running `tests/render/word_render_read.ps1` on `clean-out.docx` returns header size **12.0**. For the quotation failure, replace `_tbl()` with three body runs enclosing a quoted `30%`, and retain `revision`: the middle run becomes `30 percent` without a preservation exception.

Additional compact probes:

```python
from conformer.engine import Conformer, typo_text
from tests.test_excerpt_quotes import _pass_conformer, _excerpt, _text

assert typo_text('A7-14 days') == 'A7–14 days'
assert typo_text('Table 2017-2019') == 'Table 2017–2019'
assert typo_text('a — b — c') == 'a—b — c'
assert Conformer._house_edit('the project schedule') == 'the Project schedule'
assert Conformer._house_edit('The analyses are complete.') == 'The analyzes are complete.'
c = _pass_conformer([_excerpt('“A quote ending in a nested ‘word’')])
c._strip_excerpt_quotes_preserving()
assert _text(c.items[0]) == 'A quote ending in a nested ‘word'
```

Before signoff, add lasting regression tests for these failures, verify both revision-free and revised inputs through analyze/apply/save, and rerun the corrected Word acceptance suite. The existing 278 passing tests are a baseline to preserve, not evidence that these counterexamples conform.
