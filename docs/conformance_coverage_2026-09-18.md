# LI Report Conformer — conformance coverage matrix (source-accurate)

**Date:** 2026-09-18 · **Supersedes** (as the specification of record): `docs/guidelines_gap_analysis_2026-09-17.md`
and the coverage claims in `docs/realignment_plan_2026-09-17.md`. Those remain as **dated historical
investigation**, not current spec.
**Source of truth:** the committed authoritative guidelines —
`src/conformer/assets/LI Report Template Guidelines A4 23 July 2026.docx` (and the `LTR` variant) and the
`LI Report Template A4 23 July 2026.dotx` template. **Not** `docs/LI_STYLE_GUIDE.md`, which is a synthesis
and is the origin of several unsourced rules (see §"Source-authority corrections").
**Current behavior column** is at commit `eb2220b` (the reviewed session + GPT audit).
**Reason for rewrite:** GPT/Codex audit `docs/reviews/session_and_guideline_audit_2026-09-18_codex.md`
(verdict: changes required) found the prior gap analysis had shifted section numbers, an incorrect date
rule, unsourced synthesis rules, omitted exceptions, and a false "template styles already match" claim.

> Columns per the audit's request: **Source requirement · Current behavior @ eb2220b · Detection ·
> Repair policy · Output verification · Accepted exception.** "Deterministic" = executes offline; it does
> NOT mean a regex can safely infer meaning. Distinguish *detection* (safe) from *automatic repair*
> (needs scope) from *reviewer-approved repair* (meaning-changing).

---

## Corrected section map (authoritative guideline headings, in order)

| # | Section (Heading 1) | Notable subsections |
|---|---|---|
| §1 | Report Template Guidelines (intro) | paper size A4 vs Letter; logo space |
| §2 | Style Inspector and Style Pane | |
| §3 | Report Level Headings | H1 ALL CAPS + new-page/36pt exception; H2–H6 initial caps; H2–H6 link to H1 numbering |
| §4 | "Heading 1 — Type Heading 1 in All Caps" (a **sample** section, not a rule) | H2…H6 samples |
| §5 | Numbered Paragraphs | Numbered Paragraph Sublevels (L1–L4 = a/i/-) |
| §6 | Excerpts and Quotes | |
| §7 | Other Bulleted and Numbered Lists | List Bullet; List Bullet as a Sentence (**sentence OR multi-line item**); Dash under a bullet; Bullets under a numbered list |
| §8 | Other Guidelines | 8.1 Misc · 8.2 Keyboard Shortcuts (**8.2.1 Hyphens/En/Em dashes**, 8.2.2 Additional Characters) · **8.3 Footnotes** · 8.4 File Names/Footers · 8.5 Copying Text · **8.6 Captions** · 8.7 Inserting a Table · 8.8 Inserting a Figure · 8.9 Too-small figure/table · **8.10 Landscape** · **8.11 Updating Fields** |
| §9 | Cross-References (headings, tables, figures, numbered paragraphs, etc.) | "Insert as hyperlink"; Cross Reference style |
| §10 | Additional Checks | dates, ranges, acronyms, tense, spelling, spacing, etc. |

**The prior gap analysis mislabeled Numbered Paragraphs / Excerpts / Lists as §4/§5/§6/§7; they are
§5/§6/§7, and §8 is Other Guidelines.** Use section title + this number, or a stable requirement ID.

---

## Source-authority corrections (things the prior synthesis got wrong)

1. **Date format — CORRECTED.** §10 Additional Checks specifies **`D Month YYYY`** ("3 April 2011"),
   day-month-year order, **no leading zero on 1–9**, **exempting excerpts/quotes**. It does **NOT**
   prescribe "Month Day, Year" (an American order the synthesis invented). *No ruling from Alex needed —
   the source settles it.* All-numeric dates (`3/4/11`) remain review-only (ambiguous order).
2. **`NUM-2` percentages ("15 percent") — NO SOURCE AUTHORITY.** Neither guideline document mandates
   numeral-plus-"percent". It exists only in the synthesis. → The shipped `780b337` percent rule must be
   **reverted or re-sourced** (get a separate documented LI authority before re-adding).
3. **`programme→schedule` and `U.S.` substitutions — NO SOURCE AUTHORITY** in the originals reviewed.
   "Programme" is not always a schedule. → reconsider; separate documented authority or drop.
4. **`analyses → analyzes` CORRUPTS THE NOUN.** "the analyses are complete" → "the analyzes are complete".
   `matrices → matrixes` is not required by these guidelines. → remove these ambiguous lexical rewrites
   from unconditional repair.
5. **En-dash `from`/`between` exception (§8.2.1) — MISSING.** The source explicitly says **do not** use an
   en dash for a span introduced by "from" or "between". The shipped range rule (`26a6117`) ignores this.
6. **Acronym pluralization exceptions (§10).** Apostrophe **is** allowed for abbreviations with mixed case
   or two-plus interior periods (`M.A.'s`, `Ph.D.'s`); plurals differ from possessives (`RFI's response`).
   The blanket `EOT's→EOTs` rule (`_ACR_PLURAL_RE`) is unsafe as stated.
7. **Column alignment is contextual (§8.7), not universal.** "Appropriate alignment"; category-left /
   numbers-right is an **example**, not a rule that every first column is left or every header centered.
   D-3 is project policy, not verbatim guideline.
8. **Ligatures normalization** and **inch/prime handling** are not stated verbatim; treat as separately
   authorized normalizations with protected-content policy. The originals illustrate straight prime
   characters, not a mandate to Unicode-prime everything.
9. **Sentence-bullet criterion (§7):** "List Bullet as a Sentence" applies to a sentence **or an item
   spanning more than one line** — not merely sentence-vs-short-phrase. Character length only flags
   candidates; it does not measure rendered lines.
10. **Tense/naming are contextual (§10):** prefer **past tense for completed acts, present for opinions**;
    it does not ban "shall" universally. LI naming: **`Long International, Inc.`** at first appearance in
    Section I, then `Long International`, with `LI` allowed during drafting.

---

## Coverage matrix

Legend: **✅ implemented & sourced · ⚠ partial / needs scope · ❌ not implemented · ✋ unsourced (remove or
re-source) · 🐞 defect (see F-number in the audit).**

### §3 Report-level headings
| Requirement (source) | Current @ eb2220b | Detection | Repair policy | Verification | Exception |
|---|---|---|---|---|---|
| H1 ALL CAPS; H2–H6 initial caps | ⚠ `_heading_caps_preserving` flags lowercase H1 / inconsistent H2, never force-recases; adds no `<w:caps/>` | present | flag only (D-4) | render caps | H1 long-title initial-caps exception if consistent (D-4) |
| H1 new-page + 36pt short-section exception | ❌ not modeled | — | — | — | the exception itself |
| H2–H6 auto-numbering links to H1; correct sequence/restart/parent | ⚠ `audit_headings` flags level-skips only; **sequence/restart/parent not verified** (F/12) | partial | audit | none | hidden "Hidden text for numbering" H2 must not leak to TOC (§8.6) |

### §5 Numbered paragraphs (+ sublevels L1–L4 = 1/a/i/-)
| Style presence correct | ✅ styles resolve (NumberingGraph) | resolve numFmt | — | render marker | L4 = dash |
| Correct start-at-L1 / no-skips / restart / separation from other lists | ⚠ `audit_headings` sublevel-skip only; **start/restart/separation not verified** | partial | audit | none | |

### §6 Excerpts and quotes
| Excerpt style; verbatim; no surrounding quote marks | ⚠🐞 `_strip_excerpt_quotes_preserving` offers outer-pair removal but **pairing unsafe (F8)**, and only on the **preserve pipeline (F2)** | style + first/last char | judgment call | preservation gate | **never alter excerpt interior**; opens-only multi-para left alone |

### §7 Other bulleted and numbered lists
| List Bullet / as-a-sentence / dash-under / bullets-under-numbered | ⚠ style-name recognition partial; effective indent/marker/context, **multi-line-item criterion**, short-item spacing, sentence-continuation casing not modeled | partial | style repair | render marker | operational-template drift (F7) undercuts "style repair solves it" |

### §8 Other guidelines
| §8.2.1 hyphen/en/em dash incl. **from/between exclusion** | ⚠🐞 em-dash close-up + ranges added (`d93b370`,`26a6117`) but **false positives + from/between missing (F3)** | text regex | scoped repair | gate (but gate == the transform) | from/between; IDs; captions; quoted spans |
| §8.2.2 additional characters; **Latin italics** (`i.e.,`/`e.g.,`, `force majeure`) | ⚠ e.g./i.e. get a comma (`_EG_RE`) but **not italics**; other Latin not handled | partial | formatting repair | render italic | quoted/field/citation text |
| §8.3 Footnotes: Footnote Text style; **roman reference marks**; placement after punctuation; citation scheme **varies by report/client**; locator forms (`para.`,`p.`,`pp.`) | ⚠ `fix_footnotes` normalizes Footnote Text; **reference placement/marks not verified**; no citation-scheme awareness | partial | structural only | render | client-specific citation formatting; quoted titles; source tags |
| §8.6 Captions: basis H1 (N-N) or H2 (N.N-N), consistent; **H2 prerequisite even in figure-less sections** + hidden numbering H2 not in TOC | ⚠ `audit_captions` flags basis + per-section SEQ; **H2 prerequisite/hidden-heading not modeled**; audit findings **do not gate CLEAN (F5)** | audit | flag (D-1) | none | |
| §8.7 Inserting a table: GridTable4/"LI Table"; teal `B6DDE8` header, black bold TNR 10pt; **repeat header on multipage**; **table caption first page only**; images-of-tables labeled Tables w/ source | ⚠🐞 header teal/10pt largely conformed **but clean-path loses TableHeader → 12pt & false CLEAN (F1)**; repeat-header/multipage-caption/table-image not modeled; alignment is contextual not universal | tablespec | in-place repair | **render harness (has F6 bugs)** | subtotal shading; meaningful small fonts (kept, F4) |
| §8.8 Inserting a figure; §8.9 too-small (landscape/attachment, not font-shrink) | ❌ not modeled | — | — | render/layout | |
| §8.10 Landscape: 1" margins, protected section breaks, remove START/END COPY, **portrait-after-landscape header 1.3"/footer 0.5"/continued page numbers**; A4 vs Letter | ⚠ `fix_sections` hardcodes a **Letter** final portrait section; A4 profile + the geometry properties not verified | partial | — | none | agreed spacing exceptions |
| §8.11 Updating fields **incl. footnote fields separately** | ⚠🐞 `force_field_update` arms `updateFields=true`; **footnote-field refresh not demonstrated**; harness `updated=True` even if update throws (F6) | — | arm refresh | none | |

### §9 Cross-references
| Field-based; **"Insert as hyperlink"** switch; **Cross Reference** char style; targets resolve; all 5 categories; all stories (incl. footnotes) | ⚠ `_style_crossreferences` applies the char style to existing REF; `audit_crossref_targets` flags missing bookmarks — **but broken-ref audit does not gate CLEAN (F5)**; hyperlink switch not verified; multi-level/section/footnote categories partial | audit + style | style + field build | none | |

### §10 Additional checks
| Dates `D Month YYYY`, no leading zero, exempt quotes | ⚠ only leading-zero strip in `typo_text` (which also touches quotes); **order/format not enforced** | text | scoped repair (named-month only) | — | quotations; all-numeric ambiguous |
| Number/date **ranges** en dash (with from/between exclusion) | ⚠🐞 partial + false positives (F3) | text | scoped repair | gate | from/between |
| Percentages | ✋🐞 shipped "N percent" is **UNSOURCED (revert/re-source)** + splits quotes (F3) | — | — | — | — |
| Serial (Oxford) comma (§8.1) | ❌ needs list parsing | — | reviewer | — | comma can change meaning |
| Acronyms: define-on-first-use; pluralize (with `M.A.'s` exception) | ⚠ plural rule unsafe (exceptions); first-use not tracked | doc-state | detect / reviewer | — | mixed-case / 2+ periods; possessives |
| Two spaces between sentences | ✅ `_sentence_space` (partial across runs/abbrev) | text | repair | — | verbatim excerpts |
| American spelling | ⚠🐞 finite dict; `analyses→analyzes` corrupts noun; `matrices→matrixes` not required | text | repair (remove ambiguous) | — | quoted text |
| that/which; since/because; But/However; spell 0–9; scare quotes; shall→past | ❌ / ✋ — meaning-changing; several **not found in source** (But/However, blanket 0–9, scare-quote removal, blanket shall/since) | — | **reviewer-approved only** | — | — |

### Missing / underrepresented requirements (add as rows when addressed)
- **Front matter:** cover title caps; author initial-caps/full names; post-nominal period convention
  (`P.E.`, `Ph.D.` vs CCP/PSP); remove instructional placeholders; Lists of Tables/Figures/Attachments
  use "Table of Figures" with hanging indents. Detect placeholders; never invent names or delete
  intentional draft/confidentiality labels.
- **Paper size / page geometry** (§1, §8.1, §8.10): Letter vs A4 profiles; logo space; landscape margins;
  portrait-after-landscape header 1.3"/footer 0.5"/continued page numbers.
- **H2 caption-basis prerequisite** (§8.6): an H2 is required even in figure-less sections when that basis
  is chosen; hidden numbering heading must not leak into the TOC.
- **Tables-as-images** (§8.7): label Tables (not Figures), source footnote/subtitle.
- **Figures / long tables** (§8.8, §8.10): title/subtitle/graphic spacing; multipage caption on first page
  only + repeating header; small images → landscape/attachment, not font shrink.
- **Cross-reference hyperlinks & stories** (§9): verify the "Insert as hyperlink" switch on existing REFs;
  cover footnotes and other stories.

---

## Reopened items and priorities (corrected)

Do **not** add more automatic text rules before repairing the preservation and verdict defects.

- **Reopen P0 — template & effective formatting:** adopt the authoritative July template with explicit
  A4/Letter handling and list-numbering dependency verification (F7); the app/build still select the
  older `template.dotx`. Inspect *effective* runs, not just absence of direct formatting.
- **Reopen P1 — real sequence & field results:** heading/caption sequence/restart/parent; footnote-field
  refresh execution + results; broken-ref/heading/caption audits must feed the verdict (F5).
- **Correctness first (P1 fixes for the shipped session):** F1 (clean-path style loss / false CLEAN),
  F3 (text-edit false positives + protected spans + from/between), F5 (fail-open verdict + gating),
  F6 (render-harness constant + coverage), plus revert/re-source the unsourced rules (percent,
  programme→schedule, U.S., analyses→analyzes).
- **Then P2:** F4 (body-font offer), F8 (excerpt pairing), F9 (header structural guards), F10 (macOS
  runner), equation predicate scope, "every row skippable" over-claim.

## Corrected deterministic inventory (source authority ≠ safe coverage)

| Rule family | Source authority | Safe coverage now | Treatment |
|---|---|---|---|
| CAP-1/2 generic terms | not the synthesis's word lists | determiner heuristic partial | separate approved project glossary; flag ambiguous defined terms |
| CAP-5 Report/Project | source supports subject-Report/Project **and lowercase modifiers** | `_HOUSE_CAP_RE` mis-capitalizes "the project schedule" | contextual/glossary; current regex unsafe |
| ACR-2 plural | explicit **with exceptions** | unsafe (exceptions, curly-quote ordering) | syntax/exception-guarded repair |
| PUNC-2/NUM-4 ranges | explicit **with from/between exception** | false positives (F3) | scoped after protected-span handling |
| PUNC-5 e.g./i.e. | requires **italics + comma** | comma only | add italics; scope out quotes/fields/citations |
| PUNC-6 two spaces | explicit | partial across runs | boundary-aware; exempt excerpts |
| Dates | `D Month YYYY`, no leading zero | leading-zero only, touches quotes | named-month scoped; quote-exempt |
| American spelling | explicit | ambiguous rewrites corrupt (`analyses`) | remove ambiguous lexical rewrites |
| **Percent / programme→schedule / U.S. / matrices** | **NOT in source** | shipped/partial | **revert or re-source** |
| Ligatures / inch / prime | not verbatim | partial | separately authorized; context-scoped |
| TERM/CITE consistency; that/which; Oxford comma | explicit (consistency, that/which, Oxford) | not implemented | audit + reviewer; not doc-state alone |
| shall/since/But-However/0–9/scare quotes | **several not in source**; tense/since are contextual | not implemented | reviewer-approved only |

---

*Prepared 2026-09-18 in response to the GPT/Codex audit (`eb2220b`). This document changes no code; it is
the corrected specification the fixes will be verified against.*
