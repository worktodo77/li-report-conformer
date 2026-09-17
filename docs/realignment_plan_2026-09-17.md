# LI Report Conformer — realignment plan (2026-09-17)

Consolidates `guidelines_gap_analysis_2026-09-17.md` (§0–§17) into an ordered plan. Organizing principle:
**group fixes by the shared machinery they need, build that machinery once, and reuse it** — because the
three biggest gaps (§3 heading sequence, §8.6 caption sequence/basis, §9 cross-reference targets) all need
the *same* thing: one numbering/reference model that resolves and verifies numbers against a single basis.

Guardrails carried from prior rounds (do not regress):
- Preservation gates stay as-is (content-stream/revision based). Tracked review history is never sacrificed.
- Truthful save (issue #1 E): never stamp "conformed & verified" on an unverified/blocking result.
- The numbering.xml element-ordering fix + `validate_output` ordering gate (the catastrophic-numbering-loss
  fix) stays. Highlight preservation (`_decision_for` requires explicit accept) stays. Bullet restoration
  stays. The three-state NumberingGraph (A), whole-instance repair (B), exact authorization (C) stay.
- Warhoe is privileged client data — never committed. All real-report evidence stays local.

Every workstream ships committed synthetic fixtures + resolution-based checks watched RED before the fix,
per the plan-mode discipline already in the repo.

---

## Priority 0 — STOP the engine from degrading a conforming document

These are cases where the conformer **actively makes a compliant report non-compliant** — the trust problem
Alex raised ("the quality has gotten worse"). Highest priority because the current behavior is worse than
doing nothing.

### P0-1 Table style: navy/white/grey → teal "LI Table" (GridTable4)  [§1, §8.7]
- **Harm today:** engine injects a hardcoded navy `LITABLE` constant and stamps `tblStyle="LITable"`;
  `tablespec.HOUSE` verifies navy `054F8A` fill / white text / grey `808080` borders. The guideline house
  table is **GridTable4 (alias "LI Table")**: teal `B6DDE8` header fill, **black** bold TNR 10 pt header
  text, `auto` (black) single sz-4 borders, Table Data 11 pt centered. The engine turns a correct teal
  table navy and black header text white (illegibility risk) — exactly the "made the table non-compliant"
  screenshot.
- **Fix:** replace `LITABLE`/`HOUSE` with the GridTable4 spec; IMPORT the "LI Table" style from the bundled
  `template.dotx` (which already carries it correctly) when the report lacks it (Warhoe does); stamp
  `GridTable4`; verify effective teal/black/auto against the imported style, not a hardcoded hex.
- **Header-fill correction policy (Alex's ruling):** a header filled the wrong colour is corrected to the
  house colour **even inside a tracked change**, with the `tcPrChange` history left byte-identical (the D
  work already does this for the concrete fill — retarget it from navy to teal).
- **Column alignment:** stop force-centering data columns; the guideline sets each column to its appropriate
  alignment (category/first column left, numeric columns right). At minimum, do not *impose* centering that
  the guideline doesn't require.

### P0-2 Heading caps: stop forcing all-caps over the H2 initial-caps exception  [§2, §3]
- **Harm today:** the default preserving pipeline runs `_caps_headings_preserving`, which ADDS display
  `<w:caps/>` to every H1/H2 — overriding Warhoe's 32 deliberately-consistent initial-caps H2s (the
  guideline's documented long-title exception) and introducing the very display-caps attribute §3 says
  breaks TOC/PDF-bookmark capitalization. The clean pipeline's `fix_headings` does the opposite and
  force-UPPERCASES the literal H2 text (irreversible). The two passes contradict each other.
- **Fix:** one heading-caps policy. Prefer TRUE typed capitals (never a display-only `<w:caps/>`). Detect
  report-wide H2 casing: if H2s are consistently initial-caps, PRESERVE (honor the long-title exception); if
  mixed, flag for review rather than force. H1 → true caps. H3–6 initial-caps title-casing is editorial
  (leave to the LLM layer / human).

### P0-3 Typography: `N"` → `-inch` over-application  [§7, §10 #19]
- **Harm today:** `typo_text` rewrites `(\d)"` → `\1-inch` **everywhere**, including inside tables and
  Excerpt/Quote blocks, and against §7's measurement rule (a measurement may legitimately use a prime mark
  `2″`). Corrupts quoted/tabular content.
- **Fix:** scope the rule out of tables, excerpts, and quoted spans; decide prime-mark vs spelled-out per
  house preference (needs one Alex ruling). Until decided, restrict to body prose only.

---

## Priority 1 — the shared numbering/reference model (build once, reuse three times)

The single highest-leverage build: a model that resolves, for the whole document, **heading numbers,
caption SEQ numbers, and cross-reference targets against one consistent basis**, verifies sequence, and
arms field refresh. It closes §3, §8.6 and §9 sequence/consistency gaps together. Builds on the existing
three-state `NumberingGraph`.

### P1-1 Sequence verifier (headings + captions)  [§3, §8.6, §4]
- Walk the heading tree; resolve each heading's number via NumberingGraph; confirm 1 / 1.1 / 1.1.1 …
  increments per section; flag duplicates, gaps, and H2–6 not linked to their H1. (Directly answers Alex's
  "sequential numbering of sections/subsections".)
- Generalize `audit_figures` beyond `Figure\b` to audit **Table captions too** (311 of 313 on Warhoe are
  currently never inspected). Verify per-section SEQ is sequential; Warhoe shows 13 sections with stale
  cached numbers (dup 5, gaps).
- Extend the numbered-paragraph sublevel check (§4): a sublist must start at L1 and not skip levels
  (Warhoe: 2 sublists start at L2). Currently `fix_levels` catches only one narrow case.

### P1-2 Caption basis conformance  [§8.6]
- Guideline sanctions **only Heading 1 (`N-N`) or Heading 2 (`N.N-N`)** as the caption basis; "Word does not
  allow both at once." Warhoe tables use a **disallowed Heading-3 basis** (`3.4.2-1`) and mix with H1-based
  figures. Detect the basis of each caption family; flag a non-H1/H2 basis and any mixed basis; offer to
  re-base to the house standard (a decision, since it changes every caption/reference number).
- Generalize `rebuild_fields` beyond the single-level `N-N` regex (it also hardcodes `STYLEREF 1`), so it can
  read/verify H2-based `N.N-N` captions instead of silently skipping them.

### P1-3 Field refresh arming  [§8.6, §8.11, §9]
- `force_field_update` currently arms `updateFields=true` only if the (figure-only) `self.audit` is
  non-empty. Once P1-1 audits tables too, a detected stale caption/heading/reference arms the refresh so
  Word recomputes on open — one lever fixes stale captions AND the REF fields that display them.

### P1-4 Cross-reference style + verification  [§9]
- **Biggest concrete §9 miss:** normalize the `CrossReference` character style onto **all** REF fields
  (existing + created). Warhoe: 515/515 fields lack it though the style is defined. Add a pass that styles
  existing fields, not only ones built from literal text.
- Verify existing fields resolve (flag broken/"Error! Reference source not found"; Warhoe clean but no
  guarantee); flag cross-references left as static text.
- Broaden literal→field conversion: multi-level Table/Figure (`N.N-N`), multi-level Section (`N.N`) → H1–H6
  targets (offer/create H2–H6 bookmarks), plus the Numbered-item and Footnote categories (2 of 5 §9 types
  currently unhandled). Reuse the P1-1/P1-2 number resolution so references and captions share one basis.

---

## Priority 2 — deterministic in-scope auto-fixes (clear rules, low false-positive risk)

Each is a self-contained rule the engine can apply deterministically; ship with a fixture + RED-first check.

- **P2-1 Excerpt quote-mark strip** [§5]: an `ExcerptorQuote` paragraph must have no surrounding quotation
  marks (strip a leading open-quote + trailing close-quote, keep interior quotes). Warhoe: 1 real case.
- **P2-2 Footnote end-period + trailing-blank-line** [§10 #6]: ensure each footnote ends with a period;
  remove a trailing blank line. (`fix_footnotes` already normalizes footnote text; add these.)
- **P2-3 Double periods / extra spaces / line spacing** [§10 #8/#9/#12]: collapse `..`→`.` (guarding
  ellipsis and abbreviations), collapse stray multiple spaces (respecting the two-space-after-sentence
  rule already implemented), normalize line spacing to style.
- **P2-4 Footnote-reference-after-punctuation** [§7]: a footnote reference mark sits after the sentence
  period with no leading space; detect a space-before or pre-period mark and fix.
- **P2-5 id./ibid. form-vs-locator** [§10 #17]: the deterministic core Alex confirmed — `Ibid. at X` vs
  bare `Id.`/`Ibid.` normalization by form and locator. Auto-fix tier.
- **P2-6 Date leading-zero** [§10 #22]: already partially handled (`03 April`→`3 April`); keep.
- **P2-7 Sequence checks feed here:** the sublevel no-skip promotion (§4) becomes an auto-fix where the
  target level is unambiguous, else a flag.

---

## Priority 3 — flag-for-review (deterministic to detect, risky to auto-apply)

Surface as review items, do not silently rewrite (false-positive risk):
- En-dash for numeric/date ranges (`178-180`→`178–180`), em-dash spacing [§7] — must skip document numbers
  (`L290-AB-RF`), phone numbers, etc.
- Italicize `i.e.`/`e.g.` + trailing comma [§7] — skip quotes/code/filenames.
- Prime-mark vs spelled-out measurement [§7] — pending the P0-3 ruling.
- Possessive of acronym ending in s (`ULS's`→`ULS'`), "in order to"→"to", "all of the"→"all the",
  colon-led list `;`/`; and` punctuation [§10 #28/#36/#15/#5].
- Italic footnotes that leaked from an italicized excerpt [§5] — indistinguishable from legitimate italic
  case names without context (Warhoe: 55/1480 italic footnotes, mostly case names → flag, never blanket
  strip).
- List Bullet vs List-Bullet-as-a-Sentence when the length heuristic is borderline [§6].
- Bullet immediately under a heading with no lead-in [§3/§6]; heading nested to H5/H6 vs the "four levels
  preferred" guidance [§3].

## Out of scope — language/editorial (the planned LLM layer or human review)
~20 of ~38 Section-10 items: capitalize Report/Project, since/because, which/that, who-vs-that, acronym
first-use spell-out, past-tense actions, attachment-vs-exhibit, ambiguous pronouns, split infinitives,
farther/further, company-singular, etc. Listed in §10 of the gap analysis for completeness.

---

## Suggested sequencing
1. **P0 first** (stop active harm) — table teal spec, heading-caps policy, typo scoping. These restore
   trust and are each fairly self-contained. Rebuild the `.exe` after P0 (it currently lacks even the
   highlight/bullet fixes on the shipped build).
2. **P1 shared model** — the sequence/reference verifier is the structural centerpiece; it turns the
   engine from "normalizes names" into "verifies numbers", which is what §3/§8.6/§9 all actually require.
3. **P2 auto-fixes** — bolt on once the verifier exists (several feed off it).
4. **P3 flags** — a review surface, lowest risk, add incrementally.

## Decisions — RESOLVED by Alex 2026-09-17
- **D-1 Caption basis → FLAG + OFFER, do not auto-renumber.** Detect and report a non-H1/H2 or mixed basis
  (Warhoe: H3 tables `3.4.2-1` mixed with H1 figures) as a review item; offer re-basing as an explicit
  opt-in. Never silently renumber captions/references. Within whatever basis is present, still fix stale/
  duplicate/gapped SEQ numbers.
- **D-2 Measurements → SPELL OUT IN BODY, PRIME IN TABLES.** Body prose: `2"` → `2-inch`/`2 inches`. Tables:
  keep a true prime mark `2″` (do not convert). Excerpts/quotes: untouched. Scope the current blanket
  `N"`→`-inch` accordingly (fixes P0-3).
- **D-3 Column alignment → INFER CONSERVATIVELY, FLAG AMBIGUOUS.** Stop force-centering. Unambiguously
  numeric column → right; first/text column → left; preserve any alignment the author set explicitly; flag
  columns that can't be confidently classified. (Header row stays centered per GridTable4.)
- **D-4 H2 casing → HONOR THE EXCEPTION IF CONSISTENT.** If H2s are consistently initial-caps, preserve
  (documented long-title exception); if consistently all-caps, keep all-caps; if mixed, flag rather than
  force. H1 always true caps; the engine never uses a display-only `<w:caps/>` attribute (breaks TOC/PDF
  bookmarks per §3).
