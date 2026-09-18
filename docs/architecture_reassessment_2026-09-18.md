# Architecture Reassessment — Conformer engine vs. heavily-tracked expert reports

**Date:** 2026-09-18
**Branch:** `feat/tracked-changes-judgment`
**Trigger:** Alex's in-Word review of the conformed Warhoe report surfaced five concrete defects in
rapid succession. He asked to *reassess the whole approach* rather than patch. This document is the
reassessment: what broke, why, and the architecture to fix it.

> **Status: DESIGN — no code changes proposed here are built yet.** Decisions settled so far are recorded
> in §4. Build order is deferred to Alex (see §8).

---

## 1. What Alex observed (the real-report evidence)

All five are from the **conformed** Warhoe output, reviewed in Word. Each was reproduced locally against
the privileged original (client data — never committed; probes run inline and discarded).

| # | Observation | Verified? |
|---|---|---|
| 1 | "98 tables need independent review (nested/complex)" — *disbelieved nested tables exist* | **Confirmed a mislabel** — 0 nested tables |
| 2 | Table formatting not conformed to the guideline | **Confirmed** — 68 tables fail header format |
| 3 | Bullet lists not conformed to the proper style | **Confirmed** the styles are untouched; render is style-driven |
| 4 | Some bullet lists rendered as numbered lists (incorrect) | **Confirmed** style-based, definition-driven |
| 5 | Everything in the TOC / List of Tables points to page 1 | **Not yet root-caused** (see §6) |
| — | "Conformance not verified clean" dialog on save | Expected behaviour — the tool's honest self-report |

---

## 2. Findings in detail (with the evidence)

### 2.1 The "98 nested/complex" label is a bug
`nested tables found: 0` across all 333 tables. The 98 come from `_table_notes`, which is fed by **two**
code paths — nested tables (`engine.py:2749`, **0 hits**) and *header cells whose fill is itself a tracked
change* (`engine.py:2714`, all 98). The summary string at `engine.py:2803` hard-codes "(nested/complex)"
regardless of which path fed it. **A reporting defect, not a table defect** — but it destroyed trust in the
number and misdirected diagnosis.

### 2.2 Tables fail because the format is frozen inside tracked changes
68 tables fail effective formatting; every one is a **header-row font-size** conflict. The failing sizes are
8–10.5pt (`sz` 16/17/18/19/21) and **63 of 68 sit inside tracked `<w:ins>`/`<w:del>` markup**. The engine's
contract is *preserve tracked content byte-for-byte*, so it masks those runs and cannot rewrite the size.
Result: it preserves faithfully and flags the table non-conforming. Only ~5 fails are plain (no tracked
markup) and are genuine missed fixes. **This is the core tension, not a stray bug** (see §3.1).

### 2.3 / 2.4 The flagged lists are style-based; the engine never restyled them
Both lists Alex flagged use paragraph style **`NumberedParagraphL1` with no direct `numPr`**. The style is
**identical before and after** conforming. So the marker (bullet vs "1./a.") is decided entirely by what
that shared style's numbering definition resolves to in the conformed `numbering.xml`/`styles.xml`. The
visible "bullets became numbers" is a **style-definition** effect of the numbering-graph repair changing what
the shared style points to — not a per-paragraph restyle. Correctly fixing it is a tree/graph problem, not a
regex substitution.

### 2.5 TOC / List of Tables all show page 1 — open
`force_field_update` (`engine.py:1255`) only sets `<w:updateFields val="true"/>`; it does **not** rewrite
cached results. So "page 1" is either (a) fields awaiting Word's recalc, or (b) PAGEREF bookmark targets
disturbed by the conform. **Distinguishing test:** in Word, `Ctrl+A` → `F9` → "update entire table"; real
numbers ⇒ benign refresh, "Error! Bookmark not found"/still-1 ⇒ real defect. To be root-caused in the
verification phase.

---

## 3. Root cause — two structural mismatches

Every finding reduces to one of two architectural mismatches. Neither is a small bug.

### 3.1 "Preserve tracked changes" is implemented as "don't touch tracked content" — which forbids conformance
The engine masks every tracked insertion/deletion and edits around it, keeping it byte-exact. On a lightly
marked document this is fine. **Warhoe is a live, heavily-tracked draft**, so most of the formatting that
needs conforming lives *inside* tracked edits — and is therefore skipped. The preservation contract, as
built, **forbids the very edits conformance requires.** No amount of engine cleverness resolves this while
the rule is "skip tracked content."

**The resolution (Alex, 2026-09-18):** don't skip, and **don't add new tracked changes either** — conform
the formatting **in place**, silently, *reaching through* the tracked wrapper. A wrong font size inside a
`<w:ins>` is simply corrected; the `<w:ins>` wrapper, its author/date, and the inserted text all stay. What
is preserved is the **review history** — the revision *content* (which words were inserted/deleted, by whom,
when) and the *comments*. What is conformed is **formatting, everywhere**, tracked or not. Adding conformance
as new tracked changes was explicitly rejected: it would bury the report in markup and make it a nightmare to
review.

**Honest consequence (recorded, not relitigated):** editing formatting inside a tracked insertion means the
inserted text's formatting will differ from exactly what the reviewer typed. The who/what/when of the edit is
fully preserved; only its non-conforming formatting is silently corrected. This is consistent with Alex's
prior ruling (2026-09-17) that a wrong header fill is corrected to house even when it is a tracked change.

### 3.2 Structural correctness is done with regex on XML strings
Numbering resolution, style inheritance, field/bookmark integrity, and table-cell geometry are tree/graph
problems. Regex handles the easy 80% and mishandles the structural 20% — exactly the bullet↔number,
PAGEREF/TOC, and header-detection failures above. The codebase already concedes this: `numbering.py` is
lxml, an island in an otherwise regex engine. Surgically editing properties **inside** tracked wrappers
(§3.1) without disturbing the ins/del/comment structure is not safe with string regex; it needs a tree model.

### 3.3 Verification measured names and counts, not rendered effect
250 tests were green while the Word output was visibly wrong. "333/333 GridTable4 stamped" was *true* and the
tables still looked wrong. **The test suite asserts XML shape, never rendered result.** Any path forward is
untrustworthy until a rendering-level check exists (§6).

---

## 4. Decisions settled

- **D-A1 — SUPERSEDED 2026-09-18 PM.** ~~Two modes, shipped separately.~~ Reversed by D-A3: two workflow
  tracks make the software too complex. **One workflow only.**
- **D-A2 (2026-09-18): Design doc before code.** This reassessment is written and reviewable before any
  rebuild begins. *(Alex, "Write the design doc first".)*
- **D-A3 (2026-09-18): One workflow; conform in place; never add tracked changes.** A single path: report in,
  conformed report out. Conformance fixes are applied **silently, in place** — including on formatting that
  sits inside a tracked change. Emitting conformance as new tracked changes is rejected (it makes the document
  a nightmare to review). *(Alex, "just one workflow… I do not want us adding tracked changes for the
  conformance fixes… regardless if it is tracked change or not, the software shall conform those instances.")*
- **D-A4 (2026-09-18): "Preserve" = review history, not formatting.** The tool preserves the tracked-change
  **content** (which words were inserted/deleted, by whom, when) and the **comments**. It does **not** preserve
  non-conforming **formatting** — that is conformed everywhere. This refines the older "preserve tracked
  changes byte-exact" contract, which conflated content with formatting.

---

## 5. Target architecture — one workflow

A single conform path. No modes, no accepted-copy branch, no tracked-change emission.

**Preserve (untouched):**
- Tracked-change **structure and content**: `<w:ins>`/`<w:del>`/`<w:moveFrom>`/`<w:moveTo>` wrappers with
  their authors and dates, and the inserted/deleted **text** itself.
- **Comments** and their anchors.
- Document substance — no wording, quotes, or content changes.

**Conform (everywhere, in place, silently):**
- All formatting to the guideline — fonts, sizes, colours, paragraph/character styles, list numbering,
  tables, captions, cross-references — **regardless of whether the run sits inside a tracked change.** The
  engine reaches through the wrapper and corrects the property; the wrapper stays.
- Where a reviewer's tracked *formatting* change (`rPrChange`/`tcPrChange`) set a non-conforming value, the
  current effective formatting is conformed; the old-value change-record is normalised so "reject" cannot
  revert to a non-conforming state. *(Consistent with the 2026-09-17 header-fill ruling.)*

**Implementation consequences:**
- Move the structural + property passes onto a **tree model (lxml)** so formatting can be edited safely
  *inside* tracked wrappers without disturbing revision structure, content, or comments (§3.2). Retire the
  "mask tracked content and skip it" behaviour for formatting; masking is no longer how preservation works.
- List numbering is owned fully by the `numbering.py` graph (retire the regex numbering paths).
- Existing UI, ledger, gates, and audit scaffolding are retained; the ledger now records in-place formatting
  corrections rather than emitted tracked changes.

---

## 6. The missing foundation — a Word-level verification harness

Root cause 3.3 must be closed first or every fix stays unverifiable.

- **Word-COM acceptance harness** (Alex is on Windows 11 with Word): open the conformed file, update fields,
  and read back the **actual rendered state** — TOC/LOT page numbers, header fills, list markers, table run
  sizes — asserting against the guideline.
- Re-run it against the *current* Warhoe output to produce one truthful, complete defect list (and to
  root-cause finding 2.5).
- It becomes the acceptance gate every conform change must pass — replacing "XML-shape green" with
  "renders correctly."

---

## 7. What is a quick bug-fix vs. what is the rebuild

Kept separate so small honest wins aren't blocked on the big build:

- **Quick, in-place fixes** (independent of the rebuild): the "98 nested/complex" mislabel (2.1); the ~5
  plain-table header fails (2.2); likely finding 2.5 once root-caused.
- **Rebuild** (the two mismatches, under the single contract): conform-through-tracked-wrappers in place —
  no tracked-change emission (3.1 / D-A3); tree-model structural passes so those in-place edits are safe
  (3.2); retire the mask-and-skip formatting behaviour (§5).

---

## 8. Open items / next decision

- **Build order** is the next call (verification-harness-first is the standing recommendation, so no fix is
  trusted on XML-shape alone again). Options: harness first → then the conform rebuild; or start the conform
  rebuild now with the harness built alongside.
- **Ledger semantics** under D-A3: the audit now records in-place formatting corrections (what conformed,
  where) rather than emitted tracked changes — confirm the log shape at rebuild kickoff.
- **rPrChange/tcPrChange handling**: normalising the old-value record so "reject" can't revert to a
  non-conforming state (per §5) — confirm at kickoff.
- Finding 2.5 root cause (folds into the verification phase).

---

*Reassessment written 2026-09-18 in response to Alex's Warhoe review. No engine code changed by this
document.*
