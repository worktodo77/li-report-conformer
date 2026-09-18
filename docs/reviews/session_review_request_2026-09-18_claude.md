# Review request — 2026-09-18 session (architecture pivot + fixes + improvements) and gap-analysis audit

**Author:** Claude · **For:** GPT / Codex · **Repo:** `worktodo77/li-report-conformer`
**Branch:** `feat/tracked-changes-judgment` · **HEAD at request:** `780b337`
**This file:** `docs/reviews/session_review_request_2026-09-18_claude.md`
**Blob:** https://github.com/worktodo77/li-report-conformer/blob/feat/tracked-changes-judgment/docs/reviews/session_review_request_2026-09-18_claude.md

> Read everything **from the branch** (`git fetch origin feat/tracked-changes-judgment` then read at `780b337`),
> not from pasted chat text. Warhoe (the real report) is privileged and is NOT in the repo; all
> real-file evidence below was produced locally.

---

## What to review

Two asks:

- **A. Review all the work in this session** — the architecture pivot and the 20 commits below.
- **B. Audit the guideline gap analysis** — `docs/guidelines_gap_analysis_2026-09-17.md` and the
  `docs/realignment_plan_2026-09-17.md` — for completeness/accuracy against the LI guidelines, and the
  deterministic-rule (`[DET]`) inventory (§ "Deterministic coverage" below).

Refute rather than confirm. Assume the in-process desktop-app / local-file threat model (no adversarial
network); do not require defenses beyond that.

---

## Context: the pivot

Alex reviewed the conformed Warhoe report in Word and found real defects. The design was reassessed
(`docs/architecture_reassessment_2026-09-18.md`). Decisions:

- **D-A1 (superseded)** two modes → **D-A3: ONE workflow.** Report in, conformed report out.
- **D-A3: conform formatting in place, never emit tracked changes.** If a part does not conform — tracked
  or not — the software conforms it in place, silently. Adding conformance as tracked changes was rejected
  (would bury the report in markup).
- **D-A4: "preserve" = review history, not formatting.** The tool preserves tracked-change *content*
  (inserted/deleted text, authors, dates) and *comments*; it conforms *formatting* everywhere.

A **Word-COM render harness** (`tests/render/`, Windows/PowerShell, no pywin32) was built first, because
250 XML-shape tests were green while the Word output was visibly wrong. It reads the *rendered* state
(table style, header fill/size, list markers, PAGEREF) and became the arbiter for the fixes below.

---

## A. Commit-by-commit (the read-list is each commit's diff)

Foundation / docs:
- `680042d`, `939bcf2` — architecture reassessment; single-workflow decision.
- `47af482` — Word-COM render harness (`tests/render/word_render_read.ps1` + `render_verify.py`).

Fixes (each verified against Warhoe via the render harness):
- `95dfb06` — **header text 10pt**: header cells were stamped `pStyle=TableData` (11pt), and a paragraph
  style overrides the Grid Table 4 firstRow (10pt). Added a 10pt-bold `TableHeader` paragraph style; also
  fixed a header-row marking bug (`.replace('<w:tr>', …)` missed `<w:tr w:rsidR=…>` rows). 318→72 render.
- `c5bf24a` — **centered display equations** (e.g. "Performance Variance = …") were being turned into
  numbered list items and de-centered by `classify()` + `strip_direct()`. Now a directly-centered,
  non-numbered, non-heading paragraph is preserved; direct `jc=center` is kept.
- `4b402c1` — every conformance ledger row is skippable (cross-ref + updateFields got a `_skip` category);
  removed an obsolete tally that only counted judgment calls.
- `111600f` — **header sizes locked INSIDE tracked insertions** conformed (D-A3): `_mask_revisions(content
  =False)` masks only the tracked-change RECORDS so each `rPrChange`/`pPrChange` old snapshot stays
  byte-exact, then every header BODY paragraph is set to `TableHeader` and current run sizes stripped —
  through `<w:ins>`/`<w:del>` wrappers. **Guard:** headings/numbered/bulleted paragraphs in a header cell
  are NEVER reclassified (an earlier blunt version flipped 20 empty `Heading4` paragraphs → reference
  flips). 72→6 render (the 6 are empty `Heading4` header artifacts, left as-is).
- `283fe64` — **verdict semantics**: informational table surfacings (small data fonts, right-aligned
  numbers, subtotal shading; and "tracked header-fill corrected, record preserved" notes) no longer gate
  `clean`. `clean` gates on blocking damage AND genuinely-unresolved items (unresolved/**nested** tables,
  unresolved imports, uncorresponded numbered paragraphs, rolled-back passes). A table note is split:
  a *nested* note is unresolved; a *tracked-fill* note is informational. Warhoe now verdicts CLEAN.

macOS build:
- `dce3bd2`, `595334f` — `.github/workflows/build-macos.yml` (GitHub macOS runners, Intel + Apple
  Silicon) + cross-platform spec (Qt plugin ext per platform; `.ico` icon only on Windows).

Improvements (§ = LI guideline section):
- `a9100ca` — §5 strip redundant surrounding quotes from a **self-contained** block-quote excerpt
  (judgment call; only clean excerpts; verbatim middle untouched; opens-only left alone).
- `f81e0a5` — small table **body fonts kept by default**; a single class-level judgment call offers to
  normalize all to 11pt (Warhoe: 92 uniform-small tables, 0 scattered outliers → intentional).
- `2a2992b` — **harden**: `tablespec._effective_style_size` + a `header-style-size` check catch the
  style-resolved header size the render harness caught but the direct-size check missed (CI, no Word).
- `26a6117` — §7 en dash for number/date **ranges**, scoped false-positive-free (year-year; N-N + time
  unit); IDs/caption numbers/`4-week`/`pre-2020`/bare N-N untouched.
- `d93b370` — §7 PUNC-2 em dash closed up (between non-space chars only).
- `780b337` — NUM-2 percentages → "N percent" in **prose** (tables keep `%`; quotes verbatim); added to
  `_house_edit` AND `house_norm` so the content-stream gate authorizes it.

Test count: **278 fast tests** green (`pytest -k "not warhoe"`); the local-only Warhoe integration test is
skip-if-absent.

---

## Focused questions (please refute)

1. **D-A3 through tracked content** (`111600f`): does `_mask_revisions(content=False)` truly keep every
   tracked-change RECORD byte-exact while conforming current formatting? Can a header edit inside an
   `<w:ins>`/`<w:del>` corrupt accept/reject, change inserted *text*, or disturb a `rPrChange` old value?
   Is the `_HEADER_BODY_STYLES` guard the complete set that must never be reclassified?
2. **Verdict semantics** (`283fe64`): is demoting `tables_review` + tracked-fill notes to *informational*
   sound, or does it hide something a reviewer must act on? Is the nested-vs-informational note split by
   substring `'nested'` robust? Does anything now report CLEAN that should not?
3. **Typography as the gate-authorized change** (`26a6117`, `d93b370`, `780b337`): `typo_text` /
   `house_norm` ARE the only authorized text edits, so a false-positive pattern silently corrupts and the
   gate cannot catch it. Are the range/em-dash/percent patterns truly false-positive-free (esp. in
   schedule text: activity IDs, caption numbers, currency, ranges like `10%-20%`)?
4. **Equation preservation** (`c5bf24a`): is "directly-centered, non-numbered, non-heading paragraph →
   preserve" too broad (could it skip a paragraph that SHOULD be conformed) or too narrow?
5. **Excerpt quote-strip** (`a9100ca`): any HC-1 (never edit a verbatim quote) risk in stripping the outer
   pair from a self-contained excerpt?
6. **Render harness** (`47af482`): are the guideline assertions right (BGR→RGB, `NameLocal` alias split,
   `ListString` vs `ListType`, effective-size resolution)? Anything it claims that Word would not?

---

## B. Gap-analysis audit

Please audit `docs/guidelines_gap_analysis_2026-09-17.md` (§0–§17) and `docs/realignment_plan_2026-09-17.md`
against the authoritative LI guidelines
(`src/conformer/assets/LI Report Template Guidelines A4 23 July 2026.docx` + the `.dotx` template):

- Are any guideline requirements **missing** from the gap analysis, or **mischaracterized** (e.g. a rule
  called out-of-scope that is actually deterministic, or vice-versa)?
- **Deterministic coverage** — implemented `[DET]`: CAP-1/2/3/5, ACR-2, PUNC-2 (em dash + ranges),
  PUNC-5, PUNC-6, NUM-2, NUM-4 (ranges), British→American / programme→schedule / U.S. / inch / smart
  quotes / ligatures. NOT implemented: ACR-1 (first-use), TERM-1/CITE-2 (term consistency), GRAM-3
  (that/which), PUNC-1 (Oxford comma) — all need document-level state; and TENSE-1, GRAM-1 (since→because),
  GRAM-5 (But→However), NUM-1 (spell 0–9), PUNC-4 (scare quotes), PUNC-3 — meaning-changing, proposed as
  reviewer-approved judgment calls. Is this split right? Any clean [DET] win we missed?
- **Open ruling for Alex:** NUM-4 date format is ambiguous — the guide says "Month Day, Year" but an
  earlier note said "DD Month YYYY". Which is the house format? (Blocking the date-reformat rule.)

---

## How to respond

Per the repo workflow: write your verdict as a tracked file `docs/reviews/<topic>_2026-09-18_codex.md`
with a self-locating header, commit+push it to `feat/tracked-changes-judgment`, and hand Alex a one-line
pointer. Nothing here is merged to master; that remains gated on Alex.
