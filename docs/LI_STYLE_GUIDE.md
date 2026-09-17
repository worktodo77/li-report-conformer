# LI Style Guide — Expert Reports (conformer editorial reference)

**Version:** 0.1 (draft for Alex's review) · 2026-09-16
**Scope:** Long International expert reports (delay, disruption, quantum, forensic). Synthesised from
the *Long International House Style Guide v1.0* (blogs/articles), Claire Crevey's tracked-edit analysis
(~2,347 real markups), and the **expert-report conventions from the Expert Assist toolkit**
(`draft-section` skill + its `CLAUDE.md`: LI template styles, Exhibits/Attachments citations, two-space
sentences, capitalize Report/Project, reserved-to-expert content). The house guide governs blogs first;
**expert reports share its core grammar, capitalization, terminology and spelling rules but keep their
own formatting and citation conventions** — the report-specific rules below are marked
*Report-specific*.

The LI template's own *formatting* (ALL-CAPS Heading 1–2, Numbered Paragraph body, Excerpt or Quote,
LI table, sequential footnotes) is already handled by the deterministic conformer; this guide covers
the *writing/editing* house style layered on top.

**This file is the single source of truth for the conformer's house-style work.** It is maintained by
hand. Each rule is tagged:

- **[DET]** — deterministic: a rule the *engine* can apply and verify offline (like the typography
  pass), with a fixed, checkable transform. No LLM.
- **[LLM]** — judgment: a rule that needs the local (Ollama) editorial layer to *suggest* an edit the
  expert reviews (Accept / Change / Skip). Never auto-applied.

Severity: **must** (house rule, high-confidence) · **should** (strong preference) · **consider**
(judgment, offer as a suggestion).

---

## 0. Hard constraints (never violated by any pass or suggestion)

These bind both the deterministic passes and the LLM layer. They mirror the conformer's preservation
contract.

- **HC-1 — Never alter a verbatim quotation.** Text inside quotation marks, block quotes, or reproduced
  contract/standard/case language keeps its exact wording, spelling, capitalization, and punctuation —
  including British spellings ("programme"), defined-term capitals ("the Contractor", "Total Float"),
  and clause labels. Every rule below applies to **LI's own prose only**.
- **HC-2 — Never change a substantive technical or legal statement.** Style edits change *form*, never
  *meaning*: not a number, date, quantum figure, entitlement, standard/clause reference, causal claim,
  or opinion. When an edit would change substance, it is not made.
- **HC-2a — Reserved content is off-limits to the editorial layer.** Causation, entitlement
  (EOT/compensation), concurrency, and quantum are reserved to the expert (Expert Assist rule). The
  LLM may fix mechanics/flow in a sentence that *states* such a matter, but must never reword the
  finding itself, soften/strengthen it, or add/remove a hedge. When unsure whether a rewrite touches a
  reserved opinion, do not suggest it.
- **HC-3 — Never touch tracked content unsafely.** House-style edits run under the same preservation
  gate as the rest of the conformer. On a reviewed draft, a deterministic edit applies only where it
  does not disturb a tracked change/comment; an LLM suggestion is offered but, if accepted, is written
  as a **tracked change** attributed to an editorial author and only on clean (non-revised) text, so
  the expert accepts/rejects it in Word like any reviewer's edit.
- **HC-4 — Defined contract terms.** Capitalize a term (Owner, Contractor, Time for Completion,
  Sub-Clause 8.5, Exceptional Events) **only** when discussing the specific contract that defines and
  capitalizes it. When generalizing across contracts, lowercase. Default in LI prose is lowercase.
- **HC-5 — Authority.** For anything this guide does not address, follow *The Chicago Manual of Style*
  (17th/18th ed.); this guide governs where they differ. Spelling authority: Merriam-Webster (US).

---

## 1. Capitalization — the highest-frequency edit  *(corpus + Claire's #1/#2)*

- **CAP-1 [DET] must — lowercase generic party/role nouns** in LI prose: contractor, owner, employer,
  engineer, subcontractor, government, party, surety, claimant. Corpus: "the contractor" 493 vs 84;
  "the owner" 270 vs 45. Capitalize only per HC-4, at sentence start, or in a title/heading.
- **CAP-2 [DET] must — lowercase generic technical/scheduling terms:** float, total float, free float,
  terminal float, critical path, completion date, contract completion date, delay, concurrent delay,
  extension of time, liquidated damages, turnkey, lump-sum turnkey, change order, differing site
  conditions, commercial operation date. Corpus: float 295 vs 81; critical path 143 vs 18.
- **CAP-3 [DET] must — keep true proper nouns capitalized:** Long International, FIDIC, AACE
  International, NEC, the Silver Book, the Red Book, named projects/organizations/people, and formal
  document/section titles (Schedule Basis Memorandum, Analysis of Alternatives).
- **CAP-4 [DET] context-sensitive:** the same word is lowercase generic ("owners furnish equipment")
  but capitalized when quoting a contract that defines it. Detection must respect HC-1/HC-4 — a
  deterministic recapitalization runs on prose spans, never inside a quotation or a discussion pinned
  to a specific contract's defined term. Where context is ambiguous, downgrade to **[LLM] consider**.
- **CAP-5 [DET] must — EXPERT-REPORT EXCEPTION: capitalize "Report" and "Project".** In an LI expert
  report, "Report" and "Project" are the specific report and project under discussion and are
  capitalized — this **overrides** CAP-1/CAP-2 for these two words. (Expert Assist house rule; does not
  apply to blogs/articles.) All other generic party/technical nouns stay lowercase per CAP-1/2.
  *Report-specific — not in the blog guide.*

## 2. Tense and voice  *(Claire's #7, #6)*

- **TENSE-1 [DET] must — no "shall"/future-tense legalese in LI's own explanatory prose.** "shall be
  entitled to" → "is entitled to"; "entitlement shall be determined" → "entitlement is determined".
  Present tense for general principles and contract mechanics. **Does not apply inside quotations
  (HC-1)** or where "shall" states a specific obligation being analysed rather than explained —
  ambiguous cases are **[LLM] consider**.
- **VOICE-1 [LLM] should — prefer the active voice; front the logical subject.** Recast passive,
  subject-trailing sentences so the actor leads. Especially for figure/table references (see §8).
- **TENSE-2 [LLM] consider — past tense only for specific historical events, case facts, project
  narratives;** present tense for principles.

## 3. Acronyms  *(Claire's #3)*

- **ACR-1 [DET] must — define on first use, then always use the acronym.** First use: spell out
  (lowercase generic expansion) + acronym in parentheses — "extension of time (EOT)", "liquidated
  damages (LDs)", "critical path method (CPM)". Every later mention uses the acronym; do **not** revert
  to the spelled-out form once defined. This is checkable deterministically (track first-definition,
  flag later spelled-out repeats and undefined acronyms).
- **ACR-2 [DET] must — pluralize with a lowercase s, no apostrophe:** LDs, EOTs, RFIs.
- **ACR-3 [DET] should — lowercase the expansion of generic terms;** capitalize only proper-noun
  expansions. Common LI acronyms: EPC, LSTK, EOT, LD(s), CPM, QRA, AOA, FEL-1, NEC, RFI, FIDIC, DAAB,
  PMC.

## 4. Terminology and preferred usage  *(§10 + Claire's #10/#14)*

Use the preferred term in LI prose; the avoided term is retained only inside quotations.

| Preferred [DET] must | Avoid | Note |
|---|---|---|
| schedule | programme | British "programme" only when quoting a UK/FIDIC contract. |
| analyze, modeling, behavior, organization, judgment, prioritize (US -ize) | analyse, modelling, behaviour, -ise | American English (HC-5). |
| matrixes | matrices | LI house plural (corpus 5 vs 0). |
| U.S. | US, USA | Periods, no spaces (in prose). |
| cause-and-effect relationship | cause/effect, cause effect | Hyphenate the modifier; keep "cause-effect matrix/matrixes" as the LI product term. |
| first-come, first-served basis | first-used basis | |
| extension of time (EOT) → EOT | time extension | Define, then EOT. |

- **TERM-1 [DET] must — defined-term consistency:** once a label is chosen for a concept/party, use it
  consistently within the document; do not alternate synonyms ("employer"/"owner") for the same role
  unless the contract under discussion uses a specific defined term.

## 5. Grammar and precision  *(§5 + Claire's #8/#9)*

- **GRAM-1 [DET] should — because/if, not since/where, for cause/condition.** "since" (causal) →
  "because" (reserve "since" for time); "where" (conditional) → "if".
- **GRAM-2 [LLM] should — generic statements use "a/an" or a bare plural, not "the".** "the contractor"
  (speaking generally) → "a contractor"/"contractors"; "the" only for a specific, identified party.
  (Judgment: requires knowing whether the reference is generic or specific.)
- **GRAM-3 [DET] should — that (restrictive, no comma) vs which (nonrestrictive, comma).**
- **GRAM-4 [LLM] should — parallelism** in lists, series, and compared clauses; and plural-possessive
  agreement after recasting ("superintendents' logs").
- **GRAM-5 [DET] should — "However," (formal) over sentence-initial "But"** in formal report prose.
- **GRAM-6 [DET] keep — "and/or"** as-is; do not expand to "A, B, or both" unless clarity demands.

## 6. Punctuation  *(§7)*  — mostly the existing typography pass

- **PUNC-1 [DET] must — serial (Oxford) comma** throughout.
- **PUNC-2 [DET] must — em dash closed up (no spaces); en dash for number/date ranges** ("7–14 days",
  "2017–2019"); hyphen for compound modifiers before a noun ("lump-sum turnkey contract",
  "owner-caused delay").
- **PUNC-3 [DET] should — em dash not a default clause joiner:** "discretion — and concurrency" →
  "discretion, and concurrency" (prefer a comma or a new sentence).
- **PUNC-4 [DET] must — remove scare/emphasis quotation marks** around ordinary words ('fly' → fly);
  keep quotes for genuine quotations and first-use defined contract phrases. Periods/commas inside the
  closing quote.
- **PUNC-5 [DET] — e.g. / i.e. lowercase, each followed by a comma.**
- **PUNC-6 [DET] must — TWO spaces between sentences** in expert-report prose (Expert Assist
  convention; the conformer's typography pass already does this). *Report-specific — the blog guide is
  single-space; expert reports are double.*

## 7. Numbers, dates, units  *(§8)*  — extends the existing typography/date pass

- **NUM-1 [DET] should — spell out zero–nine, numerals 10+;** numerals for all measurements,
  percentages, money, clause/figure numbers.
- **NUM-2 [DET] must — percentages: numeral + "percent" in prose ("15 percent");** "%" allowed in
  tables/figures.
- **NUM-3 [DET] must — money: "$1.2 million", "$500,000";** identify a non-USD currency on first use.
- **NUM-4 [DET] must — dates Month Day, Year ("March 5, 2026"); ranges en dash ("2017–2019").**

## 8. Figures, tables, cross-references  *(§13 + Claire's #6)*

- **FIG-1 [LLM] should — active, subject-fronted cross-references:** "Figure 1 below shows…", "as
  Figure 2 illustrates", "Table 3 sets forth…". Avoid "is shown in Figure 1". Add a direction word
  ("below"/"above") on first reference. (The deterministic conformer already rebuilds cross-references
  as fields, §8 of the tracked-changes plan; this rule is about the *phrasing* around them.)
- **FIG-2 [LLM] should — introduce every figure/table in the text before it appears;** flag any visual
  dropped in unreferenced. (Detection is deterministic — a figure with no textual reference — but the
  fix is a suggested sentence, so [LLM].)
- **FIG-3 [LLM] consider — captions in title case, concise;** table cells parallel and complete where
  the table is expository.

## 9. Citations and footnotes  *(expert-report scheme, from Expert Assist + §12)*

- **CITE-0 [DET] must — Exhibits vs Attachments.** In LI expert reports, cited sources carry a tag:
  **Exhibits = documents prepared by others** (project reports, schedules, correspondence);
  **Attachments = LI-prepared work product** (event logs, analyses, figures). Tags read "[Exhibit N]"
  and "[Attachment LI-NN]". The exact scheme is set per matter (intake); the audit enforces
  consistency, that every citation resolves to a listed Exhibit/Attachment, and that every listed one
  is cited. *Report-specific.*
- **CITE-1 [DET] must — footnotes numbered sequentially, in order of appearance;** no uncited
  assertions. Format consistent (author, title, source, year; Chicago notes for anything unspecified).
- **CITE-2 [DET] must — name standards/bodies precisely and consistently:** "AACE International
  Recommended Practice 29R-03", "SCL Delay and Disruption Protocol (2nd ed.)", "the FIDIC Silver Book
  2017 (2nd ed.)", FIDIC forms by colour, clauses by the contract's own label ("Sub-Clause 8.5",
  "Clause 21") with the clause name's capitalization preserved when quoting (HC-1).
- **CITE-3 [LLM] should — shorten a long case name to a short form after first use** ("Multiplex
  Construction (UK) Ltd v Honeywell Control Systems Ltd" → "Multiplex").
- *(CITE-0/1/2 structural checks are the footnote-citation **audit** feature — a separate advisory
  panel, sibling of Figure Integrity — not an editing suggestion.)*

## 10. Sentence craft — concision and the flow moves  *(§4 + Claire's flow rubric)*  — **[LLM] core**

The judgment half of the LI edit. The local editorial model proposes rewrites the expert reviews;
apply the kind and degree below, **never** altering substance (HC-2) or a quotation (HC-1).

- **CONC-1 [LLM] should — cut every word that does no work.** Delete throat-clearing openers ("To start
  with,"), redundant intensifiers ("increasingly more" → "increasingly"), and empty machinery
  ("in order to" → "to"; "the fact that" → cut; "in terms of" → cut; "a number of" → a count).
- **FLOW moves [LLM] consider** — offer as suggestions, one per applicable sentence:
  1. **Front the cause/condition** — lead with the reason or "if" clause that drives the sentence.
  2. **Split run-ons** — break semicolon/comma-splice chains into single-idea sentences.
  3. **Merge and subordinate** — fold a repeated subject into a relative clause.
  4. **Promote the real subject** — replace hollow lead-ins ("There is…", "Tracing one path…") with
     the actual actor.
  5. **Condense wordy machinery** to its meaning.
  6. **Fragments → prose** — turn stacked fragments/table clauses into complete, parallel sentences.
  7. **Reorder for sequence** — events and dependencies in the order they occur.
  8. **Tighten legal prose** — keep defined mechanics exact; remove throat-clearing.
  9. **Shorten citations after first use** (see CITE-3).

Worked example (mechanical + flow together):
> **Before:** "All float contained in the schedule is deemed to be owned by the Project and shall not
> be for the exclusive benefit of either the Owner or Contractor."
> **After:** "The project owns all float, so float exclusively benefits neither the owner nor the
> contractor." *(moves: condense; promote the real subject; CAP-2 lowercase; TENSE-1 present.)*

---

## 11. Build mapping (how this guide becomes features)

- **Deterministic house-style pass(es) [DET]** — a new conformer pass family (siblings of `typography`)
  applying CAP-1/2/3, TENSE-1, ACR-1/2, TERM table, GRAM-1/3/5/6, PUNC-1..5, NUM-1..4, under the
  preservation gate (authorized-edit predicate per rule; skip revised regions; verbatim-quote guard).
- **Editorial layer [LLM]** — the local (Ollama) advisory pass applying VOICE-1, GRAM-2/4, FIG-1/2/3,
  CITE-3, CONC-1 and the flow moves, emitting reviewable JudgmentCalls; accepted edits written as
  tracked changes on clean text only.
- **Footnote/citation audit** — CITE-4 structural checks as an advisory panel (separate feature).

## 12. Maintenance

- Edit this file to change house style; both the deterministic passes and the LLM prompt read from it.
- Keep the **[DET]/[LLM]** tag and **severity** on every rule — the build depends on them.
- Provenance: LI House Style Guide v1.0 (blogs/articles) + Claire Crevey edit analysis + expert-report
  conventions. When a rule is expert-report-specific (not in the blog guide), note it. Corpus counts
  are retained as evidence that a rule is the house norm.
- Open questions for Alex are collected at the end of this section as they arise.

### Open questions
- ~~Q1. Citation/footnote format.~~ **Resolved** from Expert Assist: Exhibits (others' documents) vs
  Attachments (LI work product), tagged "[Exhibit N]"/"[Attachment LI-NN]", footnotes numbered in order
  of appearance, no uncited assertions (CITE-0/1/2). Per-matter scheme still comes from the intake —
  the audit should read it where available and otherwise apply this default.
- Q2. Should CAP-4/TENSE-1 ambiguous cases stay [LLM consider] (safer) or become [DET] with a
  conservative rule set?
- Q3. Editorial author name for accepted LLM edits written as tracked changes (e.g., "LI Editorial").
- Q4. Confirm the two-space-between-sentences rule (PUNC-6) and the capitalize-Report/Project rule
  (CAP-5) are current LI expert-report house style (they come from the Expert Assist toolkit, not the
  blog guide).
