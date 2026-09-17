# LI Report Template Guidelines vs. Conformer engine — gap analysis (2026-09-17)

Source of truth: `assets/LI Report Template Guidelines LTR/A4 23 July 2026.docx` + `LI Report Template A4
23 July 2026.dotx`. Compared against the engine (`engine.py`, `tablespec.py`). Legend: ✅ conformed /
⚠️ partial / ❌ NOT checked or WRONG / 🈚 language rule (editorial, out of the deterministic scope agreed
earlier — listed for completeness).

## 0. Ground truth pulled from the July-2026 template (was previously guessed)
- Base font **Times New Roman 12 pt** (Normal sz 24). Headings **Arial Black**, colour **054F8A navy**,
  bold (H1 caps; H2 bold-italic). Numbered Paragraph/Body/List Bullet 12 pt, justified.
- **Table style = `GridTable4`, whose ALIAS is "LI Table"** (Word shows the alias "LI Table" in the table
  gallery; `w:name="Grid Table 4"`, `w:aliases="LI Table"`, basedOn TableNormal). The Warhoe report is
  MISSING this style entirely, so its tables were never conformed to it — the conformer must IMPORT it.
  Full spec: whole table centered, borders single sz 4 colour `auto` (black) all sides + insideH/insideV;
  firstRow header = teal fill `B6DDE8`/accent5 tint 66, centered, **Times New Roman Bold, bold, colour
  `auto` (black), 10 pt (sz 20)**, cantSplit.
  - Header fill **`B6DDE8`** (themeFill **accent5**, tint 66) = **light teal**, NOT navy.
  - Header text **black (`auto`) bold, Times New Roman Bold, 10 pt (sz 20)** — NOT white.
  - Borders **single sz 4 colour `auto` (black)** on all sides — NOT grey `808080`.
  - `Table Data` = Times New Roman **11 pt (sz 22)**, black, centered. `Table or Figure Subtitle` = 11 pt center.
- Footnote Text = 10 pt (sz 20). Excerpt or Quote = italic, indent left 1080/right 360.

## 1. TABLES — biggest miss (this is the "non-compliant table")
| Guideline | Engine now | Status |
|---|---|---|
| House table style is **Grid Table 4** | injects a hardcoded `LITable` constant; `tablespec` verifies "LITable" | ❌ wrong style identity |
| Header fill **teal `B6DDE8`/accent5 tint 66** | sets/verifies **navy `054F8A`** | ❌ wrong colour (turns teal→navy) |
| Header text **black bold TNR 10 pt** | sets/verifies **white** text | ❌ wrong (turns black→white, illegible risk) |
| Header font **10 pt (sz 20)** | uses house sz 22 (11 pt) | ❌ wrong size for header |
| Grid borders **colour `auto` (black) sz 4** | verifies/sets **grey `808080`** grid | ❌ wrong border colour |
| Cell alignment: **first/category column left, number columns right** ("set each column to appropriate alignment") | forces all cells centered | ❌ over-centers data columns |
| Title = `Caption` style, "Table X-Y: Title", centered | caption handling exists | ⚠️ verify against guideline exactly |
| Optional subtitle = `Table or Figure Subtitle` (0 pt after title) | not handled | ❌ not checked |
| Table content = `Table Data` style | sets pStyle TableData | ✅ |
| Excel screenshot header must use the LI teal | n/a (image) | 🈚 |

## 2. HEADINGS
| Guideline | Engine | Status |
|---|---|---|
| H1 & H2 **ALL CAPS**; H3–H6 **initial caps** | `_caps_headings` applies caps to H1/H2 via `<w:caps/>` | ⚠️ verify H3–6 are NOT forced caps; verify initial-caps not enforced (that's editorial) |
| Font **Arial Black**, colour **054F8A** | not normalized (relies on style; strips direct fonts) | ⚠️ OK if style intact; not asserted |
| H2–H6 link to H1 (auto-numbering via pStyle linkage) | resolver models pStyle linkage (A) | ✅ (numbering) |
| "Do not begin text right below a heading with bullets — use a lead-in first" | not checked | ❌ not checked |
| Each H1 section starts on a new page (with exceptions) | not checked | ❌ not checked |

## 3. NUMBERED PARAGRAPHS & SUBLEVELS
| Guideline | Engine | Status |
|---|---|---|
| `Numbered Paragraph` auto-numbers, blank line between | style-based | ✅ |
| Sublevels L1–L4 = 1 / a / i / - , no skipping levels, in sequence | `fix_levels` promotes L2→L1 in some cases | ⚠️ partial; does not verify no-skipped-levels / sequence |
| "Only use Numbered Paragraph for numbered paragraphs, not other numbered lists" | not checked | ❌ |

## 4. EXCERPTS & QUOTES
| Guideline | Engine | Status |
|---|---|---|
| Long quotes use `Excerpt or Quote` (indented italic, **no** quote marks) | not detected/normalized | ❌ not checked |
| Footnote after the quotation, remove italics from footnote | not checked | ❌ |

## 5. BULLETS (4 house styles)
| Guideline | Engine | Status |
|---|---|---|
| `List Bullet` = short phrases/words, **left-aligned with paragraph text, NOT indented**, no space between | repairs dysfunctional bullet styles; restores numId=0-suppressed bullets (new) | ⚠️ restores the bullet but does NOT verify indent/alignment per guideline |
| `List bullet as a sentence` = sentences, 6 pt space | preserved as house style | ⚠️ not verified/normalized |
| `Dash under a bullet` = sublists | recognized as a house style | ⚠️ |
| `List bullet under a numbered list` | recognized | ⚠️ |
| Capitalize first word of a bullet unless a continuation; single-word lists no semicolons; multi-word lists `;`…`; and` | 🈚 editorial | 🈚 |
| Use LI bullet STYLES, not the toolbar bullet icons (direct numPr) | strip/normalize direct numbering (C) | ⚠️ partial |

## 6. FOOTNOTES
| Guideline | Engine | Status |
|---|---|---|
| Footnote number after punctuation, **roman (not italic/bold)** | `fix_footnotes` normalizes reference marks; scorer checks not-italic | ✅/⚠️ |
| Citation in `Footnote Text` style; tab after the number | handled | ✅ |
| Period at end of each footnote; remove trailing blank line | not checked | ❌ |

## 7. TYPOGRAPHY / SPECIAL CHARACTERS
| Guideline | Engine (`typo_text`) | Status |
|---|---|---|
| Two spaces between sentences | ✅ implemented (with abbreviation guard) | ✅ |
| Smart quotes (not prime) | ✅ | ✅ |
| Prime marks **acceptable in tables**; spell out inches/feet in body | converts every `N"`→`N-inch` everywhere, incl. tables | ⚠️ over-applies in tables |
| En dash for ranges (June–August, pp. 178–180) | only `word--word`→en dash | ❌ number/date ranges not handled |
| Em dash (Ctrl+Alt+-) | not handled | ❌ |
| Non-breaking hyphen/space for values+units, US$1 billion | not handled | ❌ |
| No zeros before days 1–9 (`03 April`→`3 April`) | ✅ | ✅ |
| American spelling/punctuation, id./ibid., which/that, who, since/because, possessives, etc. | 🈚 editorial | 🈚 (out of deterministic scope) |

## 8. CAPTIONS / FIGURES
| Guideline | Engine | Status |
|---|---|---|
| Figure/Table numbering via `Caption`, "X-Y: Title", initial caps | figure audit exists | ⚠️ verify format |
| Figure blank lines styled `Space behind/after a Graphic` | handled in graphic pass | ⚠️ |
| Landscape section handling (START/END COPY, section breaks preserved) | section pass preserves breaks | ⚠️ |

## 9. CROSS-REFERENCES (Section 9)
| Guideline | Engine | Status |
|---|---|---|
| Cross-references to headings/tables/figures/paragraphs should be FIELDS (auto-updating) | `rebuild_fields` / caption-xref pass exists | ⚠️ verify coverage vs guideline |

## 10. FONTS & SIZES (global)
| Guideline | Engine | Status |
|---|---|---|
| Body Times New Roman 12 pt; Headings Arial Black; Table 11 pt; Footnote 10 pt | not asserted; relies on styles + strips direct fonts | ⚠️ not verified end-to-end |

## Deeper audit addendum (per-style + template)
- **The bundled `template.dotx` is essentially CORRECT** — it already contains `GridTable4`/"LI Table" with
  the teal header, and its `Heading1`/`NumberedParagraph`/`ListBullet` match the July-2026 template. The
  table defect is 100% engine-side: `engine.py` injects a hardcoded navy `LITABLE` style and stamps
  `tblStyle="LITable"`, and `tablespec.py`'s `HOUSE` verifies navy/white/grey — both **ignore the real teal
  `GridTable4`** the template already carries. (styles.xml differs slightly overall — worth syncing to
  July-2026, but the key styles already match.)
- **Per-style spec is correct in the template and the engine repairs styles FROM the template** (overwrites
  the doc's style def with the template's via `_keep_numpr`), so font/size/colour/spacing/indent END UP
  correct **for any paragraph that uses the right style** — the gaps are (a) tables (forced to the wrong
  style), (b) NO verification that a paragraph is on the correct style or that effective formatting matches,
  and (c) numbering/reference correctness handled separately.
- Exact per-style values now captured (for a future verifier): Heading1-6 Arial Black / navy 054F8A / numId
  16 / line 300 exact / before-after 240 / per-level hanging indents (H2 left720, H3 1080, H4 1350, H5 1710,
  H6 2070); Title Arial Black 13pt center; Title of Project Arial 11pt CAPS; NumberedParagraph 12pt black
  justified numId 18 before/after 240 (= the blank line); NumberedParagraph L1-L4 numId 18 before 120 with
  growing right indent; ListBullet 12pt justified numId 4 right-indent 360 (NO left indent = left-aligned);
  List bullet as a sentence before/after 120 (= 6pt); Dash under a bullet numId 15; List bullet under a
  numbered list numId 14; Excerpt or Quote 12pt italic justified indent left1080/right360; FootnoteText
  10pt after 0 indent hanging 360; TableData 11pt center before/after 60; Table or Figure Subtitle 11pt
  center after 120.
- **Cross-references (§9):** cross-references must be Word FIELDS (auto-updating); there is a `Cross Reference`
  character style. Engine has partial field rebuild — needs a check that cross-refs are fields, not static
  text (one of Claire's items: "not always using cross references").

## Concrete scan of the real Warhoe report (what's actually non-conformant)
- **Tables (333) — the dominant, systemic defect.** NONE use the house `GridTable4`/"LI Table": 265 have
  NO table style at all, 56 use built-in `TableGrid`, 12 use the wrong navy `LITable`. The conformer makes
  it WORSE by stamping navy `LITable` + white text instead of applying `GridTable4` (teal/black). Data-column
  alignment is author-centered (a deviation), and the guideline wants category-left / number-right — the
  engine forces center either way.
- **Font sizes:** thousands of non-house sizes (sz 21/17/18/19 = 10.5/8.5/9/9.5 pt), overwhelmingly in
  tables; the house set is 24/22/20. `strip_direct` removes direct sizes on body paragraphs (→ style's
  12 pt), which is correct; table text sizes are handled only partially and the header should be 10 pt.
- **Paragraph styles are mostly house-correct** — only `FrameContents` (12) is non-house. So per-paragraph
  reclassification is a small job; the author used the template styles.
- **Bullets are mostly correct** — of 218 `ListBullet` paragraphs, only 1 has a stray left indent (guideline:
  no left indent); `strip_direct` would remove it.
- **Cross-references are already fields** — 539 `REF _Ref…` + 371 `STYLEREF`. Good; verify none are static.
- **Bottom line:** the one large, systemic non-conformance in a real report is TABLES (wrong style identity,
  colours, text, borders, sizes, alignment). Most other formatting is already conformed by style-repair +
  direct-format stripping, or already correct in the source. Fixing tables to the real `GridTable4`/"LI
  Table" spec is the highest-leverage change.

## Deep dive: Excerpts/Quotes, Footnotes, Captions (with real-Warhoe counts)

### Excerpts / Quotes
- Engine (`classify`): converts an *italic + left-indent ≥ 700 + no-numbering* paragraph → `Excerpt or
  Quote`, and merges consecutive excerpt lines. ✅ style assignment works.
- ❌ **Does NOT remove quotation marks** from excerpts (guideline: no quote marks with this style). Warhoe:
  **3 of 15** `Excerpt or Quote` paragraphs still contain quote marks → left non-compliant.
- ⚠️ Detection depends on the source already being italic+indented; a long quote left in Body Text with
  quote marks (not yet styled) is not detected.
- ❌ Not checked: footnote placed after the quotation (not the intro sentence); remove italics from a
  footnote that follows an italicized quote.

### Footnotes
- Engine (`fix_footnotes`): sets `Footnote Text` style (fixes **27** Warhoe footnotes not in it), inserts a
  tab after the number (clean mode), keeps the reference mark roman (0 italic marks in Warhoe), and keeps
  meaning-bearing italics in the footnote TEXT (case names) via `keep_rpr_children`. ✅
- ❌ **Does NOT ensure a period at the end of each footnote** (guideline check). Warhoe: **34 of 1,507**
  footnotes do not end with a period → left non-compliant.
- ❌ Does NOT remove a trailing blank line after a footnote (guideline item).
- ❌ Does NOT verify the footnote number sits after end punctuation in the body.
- 🈚 en dash for ranges, `para.`/`p.`/`pp.` conventions — language, out of scope.

### Captions
- Engine (`rebuild_fields`): converts a STATIC `Table N-N: Title` caption into STYLEREF+SEQ fields with a
  bookmark, centers it, restores a missing bookmark. ✅
- Warhoe reality: **328 of 355** captions are ALREADY fields; they use **Heading-3-based `N.N.N-N`
  numbering** (e.g., "Table 3.6.3-5:"). The engine leaves these intact.
- ❌ **The rebuild regex only matches ONE level (`N-N`)** — it would NOT convert a STATIC caption in
  `N.N-N` (Heading 2) or `N.N.N-N` (Heading 3) format. So a report with static multi-level captions is not
  conformed.
- ❌ **No `Table or Figure Subtitle` handling** (apply the style; set 0 pt space after the title). Warhoe
  has 0 subtitles, but this is a general gap.
- Cosmetic: field-generated caption text carries double spaces ("Table  3.4.2 1 : …") — field-driven, not
  the conformer's doing.

## Priority to fix (structural/formatting, in scope)
1. **Tables**: adopt Grid Table 4 identity + teal header `B6DDE8`/accent5, black bold 10 pt header text,
   `auto` sz-4 borders; per-column alignment (category left / numbers right); subtitle handling. (Rewrite
   `HOUSE` in `tablespec.py`, the `LITABLE` constant, and the header repair in `engine.py`.)
2. **Bundle the July-2026 template** (A4 + letter) instead of the older `template.dotx`; drive the house
   spec from the template, not hardcoded constants.
3. Excerpt/Quote normalization; heading "lead-in before bullets" and new-page rules; en/em dash + non-
   breaking + table prime-mark typography; footnote period/blank-line; cross-reference field coverage.

## FULL gap analysis of Section 10 "ADDITIONAL CHECKS" (every item)
Legend: ✅ engine conforms · ⚠️ partial · ❌ in-scope gap (deterministic, engine COULD do) · 🈚 language/
editorial (needs a human or the LLM editorial layer, not the deterministic conformer).

| # | Section-10 check | Engine status |
|---|---|---|
| 1 | Centering tables/figures/titles; indent 0.5" under numbered paragraphs, or full-width no indent | ❌ centers captions but does NOT do the 0.5"-under-numbered-paragraph positioning rule |
| 2 | "this" without a following noun | 🈚 language |
| 3 | Capitalize "Report" (the subject Report) | 🈚 language (context) |
| 4 | Capitalize "Project" (and not the modifier "project") | 🈚 language (context) |
| 5 | Colon-led list → `;` each item, `; and` penultimate, `.` last | 🈚 punctuation/editorial |
| 6 | **Footnotes: period at end; remove a line space after** | ❌ IN SCOPE — 34/1,507 Warhoe footnotes lack an end period; trailing blank line not removed |
| 7 | Use spell check | 🈚 manual |
| 8 | **Double periods** (accidental `..`) | ❌ IN SCOPE (deterministic; must spare `…` ellipsis and `etc.`+end) |
| 9 | **Extra spaces between words** (3+ / mid-sentence doubles) | ❌ IN SCOPE (deterministic; must respect the house 2-spaces-after-sentence rule) |
| 10 | Use the defined acronym thereafter | 🈚 language |
| 11 | Appendices in separate files | 🈚 process |
| 12 | **Line spacing single (preferred) or 1.5, consistent** | ❌ IN SCOPE — engine does not set/verify line spacing |
| 13 | "below." with a period, not a colon | 🈚 language |
| 14 | "since" vs "because" | 🈚 language |
| 15 | "all of the" → "all the" | 🈚 language |
| 16 | "man-hours" hyphen | 🈚 language |
| 17 | **id. / ibid. usage** | ❌ IN SCOPE (deterministic) — the rule is form/locator consistency, not citation meaning: `Ibid. at X`→`Id. at X` (Ibid. never takes a pinpoint) and bare `Id.`→`Ibid.` (same exact location). Regex-level on footnote text; leaves `Id. at X` and bare `Ibid.` alone. Caveat: normalizes the FORM, does not verify the prior source is identical. |
| 18 | Long International / LI naming convention | 🈚 language |
| 19 | **`30"` → "30-inch" (except in excerpts/quotes)** | ⚠️ engine converts every `N"`→`N-inch` — but over-applies inside TABLES (prime marks allowed there per §8.2.2) and EXCERPTS (rule excludes them) |
| 20 | Spell out an abbreviation on first use | 🈚 language |
| 21 | Past-tense verbs for actions | 🈚 language |
| 22 | **Dates `DD Month YYYY`, no leading zero on days 1–9** | ✅/⚠️ engine strips leading zero (`03 April`→`3 April`); cannot convert `3/4/11` (ambiguous) |
| 23 | Oxford comma before "and" | 🈚 language |
| 24 | Attachment (LI-prepared) vs Exhibit (others) numbering | 🈚 semantic |
| 25 | Capitalize first word of a bullet unless a continuation | 🈚 language |
| 26 | Single-word lists no `;`; multi-word lists `;` + `; and` | 🈚 punctuation |
| 27 | **Sentences/multi-line bullets use "List bullet as a sentence"** | ⚠️ `classify` picks it when a bullet is long / ends with `;`/`.`/`:` — heuristic, not verified |
| 28 | Possessive of "…s" → `ULS'` not `ULS's` | 🈚 language |
| 29 | Plural of acronym → `P&IDs` not `P&ID's` | 🈚 language |
| 30 | "which" (after comma) vs "that" | 🈚 language |
| 31 | "who" not "that" for a person | 🈚 language |
| 32 | Avoid ambiguous pronouns | 🈚 language |
| 33 | "farther" (distance) vs "further" (degree) | 🈚 language |
| 34 | Don't start with "this" without a noun | 🈚 language |
| 35 | Company takes singular verb/pronoun | 🈚 language |
| 36 | Minimize "in order to" | 🈚 language |
| 37 | Singular pronoun with singular subject | 🈚 language |
| 38 | Avoid split infinitives | 🈚 language |

### Reconsidered classification (I was too coarse — "language" was over-used)
Several items I first tagged 🈚 actually have a deterministic core; they split into three tiers:
- **Deterministic & safe (auto-fix):** #6 footnote end-period/blank-line, #8 double periods, #9 extra spaces,
  #12 line spacing, **#17 id./ibid. form-vs-locator**, #22 date leading-zero. (Table centering #1 is
  deterministic but layout-complex.)
- **Deterministic-with-risk (better as FLAG-for-review than silent auto-fix, because of false positives):**
  #16 "man hours"→"man-hours" (skip quotes), #28 possessive of an acronym ending in s (`ULS's`→`ULS'`),
  #36 "in order to"→"to", #15 "all of the [noun]"→"all the", #5 colon-led list semicolon/"; and" punctuation
  (list structure is detectable via the existing ListBullet vs List-bullet-as-a-sentence classification).
- **Genuinely non-deterministic (needs meaning / the LLM editorial layer):** #3/#4 capitalize Report/Project,
  #13 below., #14 since/because, #10/#20 acronym-first-use, #21 past tense, #24 attachment vs exhibit,
  #25/#26 bullet capitalization & list punctuation intent, #29 plural-vs-possessive of an acronym, #30 which/
  that, #31 who, #32 ambiguous pronouns, #33 farther/further, #34 "this"+noun, #35 company-singular, #37
  singular-pronoun, #38 split infinitives.

**Section 10 summary:** ~20 of ~38 items are truly LANGUAGE/editorial (out of the deterministic conformer's scope
— these belong to the planned LLM editorial layer or human review). The DETERMINISTIC, in-scope items the
engine could add are only: **#1 table/figure centering-indent, #6 footnote end-period + trailing-blank-line,
#8 double periods, #9 extra spaces, #12 line spacing**, plus tightening **#19** ("N-inch" must skip tables
and excerpts). #22 (dates) and #27 (sentence bullets) are already partially handled.

---

## 11. Section 8.6 — Captions for Tables and Figures (numbering consistency + section-based numbering)

**Guideline (§8.6 "Captions for Tables and Figures"):** captions are auto-number *fields* keyed to the
section (STYLEREF to the heading level + SEQ), so a table/figure reads `<section>-<n>` (e.g. `Table 3-1`,
`Figure 5-2`); numbering must be **consistent** (all captions of a kind based on the same heading level)
and **sequential within a section**. §8.11 "Updating Fields" says the fields must be refreshed so the
displayed numbers match reality.

### Findings against the real Warhoe report
- **Basis INCONSISTENCY (real):** 311 **Table** captions use `STYLEREF 3` + `SEQ Table \* ARABIC \s 3`
  (Heading-3-based, e.g. `Table 3.4.2-1`), but the 2 **Figure** captions use `STYLEREF 1` (Heading-1-based).
  The two caption families are numbered off *different* heading levels. The guideline wants a single,
  consistent numbering basis. [X] engine has no check for caption-basis consistency.
- **0 static captions** — every caption is a field (good; section prefix auto-matches on field update).
- **STALE cached numbers (real):** 13 of 50 sections show non-sequential cached SEQ results — confirmed
  stale fields, e.g. Table 3.6.3 sequence `[1,2,3,4,5,6,5]` (duplicate 5), Table 3.6.5 `[...,6,8]` (gap),
  Table 3.6.1 shows `[5]`. `settings.xml` has `updateFields=False`, so Word displays the stale cached
  numbers until a manual field update.
- **Engine BLIND SPOT (root cause):** `audit_figures()` (engine.py ~1270) explicitly processes **Figure
  captions only** — `if not re.match(r'Figure\b', t): continue` — so all 311 Table captions are never
  audited for sequence/basis. And `force_field_update` (engine.py ~1230) arms `updateFields=true` **only
  if `self.audit` is non-empty**. Because the Table captions are never inspected, the figure audit finds
  nothing table-related, `self.audit` stays empty, `updateFields` is NOT armed, and the conformed output
  ships the **stale** Table numbers. [X]
- **Consequence:** the exact problem Alex raised — caption numbers that are wrong/duplicated/gapped per
  section — passes straight through the conformer unflagged and uncorrected.

### What a correct §8.6 pass would do (deferred to the realignment, no code change yet)
1. Audit **both** Table and Figure captions (generalize `audit_figures` beyond `Figure\b`).
2. Verify each caption family uses a **single, consistent STYLEREF basis**; flag mixed bases (Warhoe: Tables
   on H3, Figures on H1).
3. Verify **sequential per-section** SEQ results; where the cached number is stale, **arm `updateFields`**
   so Word recomputes on open (the fields are already correct field codes — they just need a refresh), and
   report the affected sections rather than silently trusting the cache.
4. Verify the caption's section prefix matches the section it physically sits in (STYLEREF already does this
   once refreshed; flag any caption whose STYLEREF level doesn't match the family standard).

## 12. Section 3 — Report Level Headings

**Guideline (§3):** LI heading styles 1–6 exist; **four levels preferred, 5–6 discouraged unless truly
needed**. **Type headings first in "Body Text" to see capitalization**, because caps "may not appear
correctly in the Table of Contents and final PDF bookmarks even if it looks correct in the body." **All caps
for Headings 1 and 2; initial caps for 3–6.** Documented **exception: a very long Heading 2 may use initial
caps, applied consistently throughout the report and its annexes/appendices.** Headings 2–6 **link to
Heading 1**, so numbering increments automatically (1., 1.1, 1.1.1, 2., 2.1 …). Each **Heading 1 starts on a
new page** (exception: a short section may instead take **36 pts space above**). Below a heading, begin in
**Numbered Paragraph** style; **do not start with bullets directly under a heading — use a lead-in sentence
first.** Long heading: break with Shift+Enter and delete the created space.

### Ground truth confirmed in the template + Warhoe
- Neither the **Heading1 nor Heading2 style carries `<w:caps>`** (template and Warhoe). "All caps" is meant
  to be achieved by **true typed capitals**, matching the guideline's TOC/PDF-bookmark rationale — a display
  `<w:caps/>` attribute would NOT propagate to the TOC/bookmarks, which is exactly what the guideline warns
  against.
- **Heading1 style carries `pageBreakBefore`** (template and Warhoe) — so "each H1 on a new page" is
  satisfied by the *style*; a per-paragraph absence of the attribute is NOT a violation. (Warhoe: only 1 of
  7 H1s has a *direct* pageBreakBefore; the rest inherit it from the style — compliant.)
- Warhoe heading census: H1=7, H2=32, H3=136, H4=360, H5=117, H6=1.

### Findings against the real Warhoe report
- **H1 caps — COMPLIANT:** all 6 body H1s are true UPPERCASE text, 0 `<w:caps/>` attrs. [OK]
- **H2 caps — the author used the documented exception:** all 32 H2s are typed in **initial caps** (0
  uppercase, 0 caps attr), consistently. Per §3 this is the *permitted* long-title exception (initial-caps
  H2 applied consistently). [OK] for the report — but [X] for the engine, which cannot honor it (below).
- **[X] TWO CONTRADICTORY heading-caps passes in the engine:**
  - `_run_passes_preserving` (the DEFAULT pipeline used on real reports) runs `_caps_headings_preserving`
    (engine.py ~1545), which **adds `<w:caps/>`** to every H1/H2 run — forcing DISPLAY all-caps. On Warhoe
    this would override all 32 deliberate initial-caps H2s AND introduce the display-caps attribute the
    guideline says breaks TOC/PDF-bookmark caps (body would show ALL CAPS while the TOC shows Initial Caps —
    the precise inconsistency §3 warns against).
  - `_run_passes_clean` runs `fix_headings` (engine.py ~546), which does the OPPOSITE — **removes `<w:caps/>`
    and force-UPPERCASES the literal text**. On Warhoe this would irreversibly destroy the initial-caps H2
    exception ("Long International's Analysis…" → "LONG INTERNATIONAL'S ANALYSIS…").
  - Both are wrong for the H2 exception case, and they disagree with each other. Correct behavior: detect a
    report-wide consistent H2 casing and PRESERVE it (or flag), and prefer TRUE typed caps over the display
    `<w:caps/>` attribute so TOC/bookmarks stay correct.
- **[!] Heading-depth "four levels preferred":** Warhoe uses all six levels heavily (H5=117, H6=1). §3 says
  5–6 are discouraged unless truly needed. No engine check flags deep nesting. Advisory only (cannot be
  auto-fixed — it's an editorial/structure judgment).
- **[X] Sequential heading numbering NOT verified:** §3's H2–6-link-to-H1 auto-increment (1., 1.1, 1.1.1 …)
  is style-based numbering with no number text in the body, so a duplicate/gap/broken-link only shows once
  Word renders it. The engine resolves numbering (NumberingGraph) but has **no verifier that walks the
  heading tree and confirms the section/subsection sequence** — the same class as the §8.6 caption-sequence
  gap. This is the "sequential numbering of sections/subsections" Alex asked to verify.
- **[X] Lead-in rule (no bullets directly under a heading) NOT checked:** §3 requires a lead-in
  sentence/paragraph before bullets; the engine's bullet passes never verify that the paragraph after a
  heading is a Numbered Paragraph/Body lead-in rather than a bullet.
- **N/A auto-fix items (editorial):** initial-caps title-casing of H3–6 with the lowercase-word list (the,
  in, to, or, a, an, and, for) is language/editorial; Shift+Enter line-break cleanup is layout-editorial.

### What a correct §3 pass would do (deferred to the realignment, no code change yet)
1. **Reconcile the two caps passes into one policy:** prefer TRUE typed capitals for H1 (and H2 unless the
   report consistently uses the initial-caps exception); never add a display-only `<w:caps/>` that desyncs
   the TOC/bookmarks; detect report-wide H2 casing consistency and honor the documented long-title exception
   rather than force-flipping it.
2. Add a **heading-sequence verifier** (shared with §8.6): resolve each heading's number via NumberingGraph,
   confirm 1/1.1/1.1.1 increments per section, flag duplicates, gaps, and H2–6 not linked to their H1.
3. Flag (advisory) sections nested to H5/H6 as "deeper than the preferred four levels."
4. Flag a bullet that immediately follows a heading with no lead-in paragraph.
