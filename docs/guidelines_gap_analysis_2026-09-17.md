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
| 17 | id. / ibid. usage | 🈚 language |
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

**Section 10 summary:** ~32 of ~38 items are LANGUAGE/editorial (out of the deterministic conformer's scope
— these belong to the planned LLM editorial layer or human review). The DETERMINISTIC, in-scope items the
engine could add are only: **#1 table/figure centering-indent, #6 footnote end-period + trailing-blank-line,
#8 double periods, #9 extra spaces, #12 line spacing**, plus tightening **#19** ("N-inch" must skip tables
and excerpts). #22 (dates) and #27 (sentence bullets) are already partially handled.
