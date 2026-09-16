# Tracked-Changes Conformance — Build Plan v2 (revised after GPT-6 review)

**Status:** M1.1 **BUILT** (strong ledger + integrity checks + 7 challenge tests). M2 slice 1
**BUILT** (`_run_passes_preserving`: per-pass whole-package transactional rollback, revision-region
skip for conservative passes, dependency-safe `_merge_missing_styles`, exceptions list). Verified on
Warhoe: preservation CLEAN across all 11,374 revisions / 171 comments / 16 binaries; settled regions
conformed (LI styles applied); 7 conflicting passes held back and recorded. 52 tests green. Remaining
M2 work + honest limits below; awaiting GPT-6 review of the M2 implementation.

### M2 slice-1 limitations (for the reviewer)
- **Whole-pass rollback is conservative:** a pass that touches *any* revision is rolled back
  entirely, so e.g. typography is withheld even from clean regions. Region-aware passes (skip revised
  paragraphs) would raise coverage — a later refinement, not required for safety.
- **Performance:** the gate rebuilds the full ledger after every pass (~84s on the 11k-revision
  Warhoe doc). Needs incremental/selective verification before this is production-fast.
- **Allowed-change gate** (`integrity.allowed_change_style_only`) exists but is **not yet wired**
  into `_run_passes_preserving` — only the preservation gate runs per pass. Wiring it (so a faulty
  legacy pass cannot delete ordinary text on a clean paragraph) is the next slice.
- **Style import** currently merges *absent* template styles and never overwrites; a template style
  whose ID already exists in the doc keeps the document's definition (a conformance limitation to
  report), and non-colliding-ID remapping is not yet done.
- **Exceptions report** lives on `self.exceptions`; writing the `_conform_exceptions.json` + original
  archive + SHA-256 manifest is a save-layer task still to do.
- Preserve mode **skips `normalize()`** so untouched revision content stays byte-identical (reordering
  rPr/pPr rewrote format-revision snapshots and produced false "alterations").
**Acceptance criterion (overarching):** every delivered output must pass checks strong enough to
support *its label* — not merely that every recorded revision ID survived.

This v2 adopts GPT-6's review in full. Change log vs v1 at the end.

---

## 1. Problem (unchanged)

The conformer restyles `.docx` expert reports to a house template via ~14 string/regex passes. A
real mid-review draft (Warhoe/Petrobras) carries (per the current ledger) **11,363 revisions** by
**8 authors** + **171 comments**; **46%** of paragraphs are revised. Empirically: the passes crash
on revision markup, and conforming in place lost 32% of revisions and broke the XML. So **full
conformance and exact preservation cannot both hold for every paragraph.** The plan separates a
*review-preserving* output from a *fully-conformed reading* output and makes every mutation verified.

## 2. Preservation contract (revised — accurately named)

We do **not** promise byte-exact XML markup: ElementTree parse→serialize can change namespace
prefixes and empty-element spelling, so "the bytes are identical" is unachievable once we mutate a
part. We promise, **within an explicitly declared supported-feature set**:

- **Revision content** — exact text *and non-text* payload (runs, drawings/objects by relationship,
  tabs, breaks, field instructions incl. `w:delInstrText`, footnote/endnote references).
- **Revision metadata** — `w:author`, `w:date` unchanged (no re-attribution).
- **Revision placement & association** — the change stays in the same paragraph/row/cell/container
  and keeps its relationships (a revision that moves elsewhere but keeps its text+metadata is a
  **failure**, not a pass).
- **Review semantics** — accepting/rejecting the change yields the same *structure, objects, and
  formatting*, not merely the same concatenated text (a preserved paragraph-mark revision can change
  behavior without changing text).

Anything outside the declared supported set produces an **explicit restriction** (a named
unsupported-feature exception), never silent omission.

Separately, we **retain the original package byte-exact as an archive** (original `.docx` + SHA-256)
alongside every output — the true fidelity anchor. Formatting revisions (`pPrChange`, `rPrChange`,
`tblPrChange`, `trPrChange`, `tcPrChange`, `sectPrChange`, numbering changes, …) are original changes
and are never silently removed.

## 3. Milestones (reordered per GPT-6 — preserve review history first)

Default disposition for a **revision-bearing** input is **preserve review history** (M2). Accept /
reject (M3) is an **explicit branch choice**, not the default. Clean inputs bypass all of this and
use the existing pipeline unchanged.

### M1.1 — Complete inventory + strong ledger + no-op round-trip (FIRST, foundational)
Rework `src/conformer/revisions.py` so the ledger can actually support a preservation claim:
- **Structured payloads**, not just concatenated text. Per revision capture: ordered content tokens
  covering text, tabs, breaks, field instructions (`instrText`/`delInstrText`), drawings/objects
  (by `r:embed`/`r:id` relationship target, not pixels), footnote/endnote references, and nested
  revisions. `w:del` payload reads `w:delText`/`w:delInstrText`; content deletions of objects are
  captured by relationship.
- **Placement & association** signature per revision: enclosing story part + a stable path
  (paragraph identity, table row/cell coordinates, container) so a relocated-but-identical revision
  is detected.
- **Comments**: bodies + anchors (`commentRangeStart/End`) + references (`commentReference`), not
  just IDs; include modern comment parts (`commentsExtended`, `commentsIds`) when present.
- **All story parts**: `document.xml`, `footnotes.xml`, `endnotes.xml`, **headers/footers**,
  `comments*.xml`. A revision-bearing part we don't yet support ⇒ explicit restriction.
- **Unsupported-feature detection**: enumerate revision constructs we can inventory vs not; unknown
  constructs are surfaced, not dropped.
- **SHA-256** throughout; but the point is *what is compared* (structured payload + placement +
  associations), not the hash function.
- **No-op round-trip verification**: parse→serialize with no disposition must produce a ledger
  identical to the original's (proves the ledger + serialization path themselves preserve).

Gate = `verify_preservation()` compares structured before/after ledgers and reports lost /
payload-altered / placement-changed / metadata-altered / comment-body-or-anchor-altered / introduced.

### M2 — Conservative review-preserving conformance (the DEFAULT for revised docs)
Apply only operations proven safe against the contract; verify after **every mutating pass**; roll
back any pass that disturbs a revision; report exceptions. Deliverables:
- **Per-pass transactional rollback.** For each pass: snapshot the whole in-memory package → apply →
  `verify_preservation()` immediately → on any discrepancy, **roll back the entire pass** and record
  an exception (do **not** attempt per-paragraph revert — unsafe after merges/splits/object moves).
  Whole-package snapshot first; selective rollback only later if needed for performance.
- **Conservative operation set** (see §4): genuinely read-only + conditional style/level changes
  that provably don't touch a property group under a formatting revision. Everything payload- or
  structure-altering on a revised region is skipped and logged.
- **Dependency-safe style import** (see §5) — required even for style-only conformance; **replaces
  the current wholesale `replace_parts` for revision docs.**
- **Outputs**: review-preserving `.docx` + `<name>_conform_exceptions.json` (every region left
  style-only/unconformed and why) + the byte-exact original archive + SHA-256 manifest. UI states
  plainly: "N regions fully conformed; M regions with tracked changes conformed conservatively
  (listed)." Never labeled "fully conformed."

### M3 — Accept / reject projectors (explicit branch; declared feature set)
Parsed-XML projectors for a **declared, independently-tested** revision feature set (§6). Unknown
constructs **block** that projection with a named restriction rather than guessing. Staged &
verified: `Original → verified projection → conformance → verified conformed result`.

### M4 — Expand compatible transformations; optional reconstruction
Migrate more conflicting passes to parsed-XML property-level operations, widening M2 coverage.
Reconstruction (redline) only **if explicitly requested**: capture source-span provenance before
projection; attribution establishes **source lineage, not an unchanged original edit** if the text
was transformed; ambiguous/mixed spans are marked generated, never silently attributed; output
labeled "reconstructed comparison," never "original tracked changes."

## 4. Per-pass classification (revised — nothing is unconditionally safe)

- **Read-only:** `audit_figures` (if genuinely read-only — to be confirmed).
- **Explicit-behavior:** `force_field_update` — updating fields on open changes derived values
  (numbering, TOF). Treat as a disclosed behavior, not automatically harmless; in review-preserving
  mode it is opt-in and recorded.
- **Conditional** (allowed on a revised region only when it does **not** touch a property group that
  a `pPrChange`/`rPrChange` (or structural revision) governs): `classify` (`pStyle`), `fix_levels`.
  Rationale: changing the *current* `pStyle`/level silently changes what an existing formatting
  revision now represents, even though the old snapshot is unchanged.
- **Migrate first, property-level allowlist:** `strip_direct` — rebuild as parsed-XML that removes
  only allow-listed direct properties, never a whole `pPr`/`rPr`, and never a property under a
  formatting revision.
- **Deferred (payload/structure-altering — stay off revised regions until individually supported):**
  `typography` (alters revision payload characters — migrating it to XML does **not** make the
  alteration faithful), `merge_pdf_lines`, `fix_headings` (uppercase/split), `fix_tables`,
  `fix_figures`, `fix_footnotes`, `rebuild_fields`, `revert_tracked_formatting` (must become
  disposition-aware, never unconditional), `replace_parts` (superseded by §5 for revision docs),
  `unwrap_and_prune`, `fix_sections`.

## 5. Dependency-safe style import (early — affects even style-only conformance)
Replace wholesale `styles.xml`/`numbering.xml` swap for revision docs with a merge policy:
- **Retain** every existing definition that supports preserved content or a revision snapshot,
  unchanged. **Never overwrite an existing style just because its ID matches the template's.**
- **Import** house definitions under **non-colliding IDs**, bringing their dependencies: `basedOn`,
  linked styles, numbering references, numbering **instances/overrides/abstract definitions**,
  document defaults, theme-dependent formatting, and any references appearing in historical
  snapshots.
- **Do not casually change global document defaults** — that silently reformats supposedly protected
  content. Preserving old definitions + remapping references is necessary **but not sufficient**;
  the *current* properties of revised paragraphs also matter (hence §4 "conditional").

## 6. Accept/reject support matrix (M3 — required before implementation)
Dispatch depends on element **and** structural context. The matrix must cover, each with tests:
- Run insertions/deletions; **paragraph-mark** insertions/deletions.
- **Moves** and their ranges (`moveFrom`/`moveTo` + `move*RangeStart/End`).
- **Table** revisions: **row** (`w:ins`/`w:del` in `trPr` = the row itself), **cell**
  (insert/delete/merge, `cellIns`/`cellDel`/`cellMerge`), **grid**, and property revisions —
  removing a marker is **not** the same as rejecting the row/cell.
- **Numbering** and **section** revisions.
- Revisions **inside property snapshots** and supported containers.
- **Deleted field instructions** (`w:delInstrText`) as well as deleted text.
- **Unknown case ⇒ block that projection** (explicit restriction).

Paragraph-mark merges: the "adopt the next paragraph's `pPr`" rule is **not** approved as universal.
It requires specific tests for consecutive deleted boundaries, list items, section boundaries,
table cells/rows, other container boundaries, and end-of-document; and the merge must **preserve
non-run children** (bookmarks, comment markers, etc.), not just "join runs."

## 7. Comments — explicit disposition policy
- **Review-preserving (M2):** preserve original anchors *and* bodies exactly.
- **Accept/reject reading copies (M3):** reproduce a tested Word behavior or a **disclosed product
  policy**. Where a comment's target disappears (e.g. anchored wholly inside a rejected insertion),
  retain it in an **audit appendix/manifest with its original context** — never silently relocate it
  onto unrelated text and never silently discard it.
- **Fixtures:** comments wholly inside removed content, spanning retained+removed content, crossing
  paragraph merges, attached to moved content, and with modern comment metadata.

## 8. Verification & test strategy (revised)
- **Cadence:** verify after **each mutating pass** *and* again on the **serialized output package**
  (not merely once per disposition).
- **Occurrence-aware, ordered projection tests** (replaces the broken "contains every ins payload /
  no del payload" check): compare against hand-authored *expected documents* for small fixtures —
  ordered token streams including structural tokens and object references — so deleting one of two
  identical words, or an insertion legitimately vanishing inside an accepted deletion, is judged
  correctly. Independent **Word comparisons** for supported combinations (dev-only, never a runtime
  dependency).
- **Staged claims:** `Original → verified projection → conformance → verified conformed result`. The
  conformed result is **not** claimed equal to Word's original projection text (typography /
  restructuring changes it); that equality belongs to the intermediate projection only.
- **"Fully resolved" means** no unresolved *supported* revision constructs remain — including
  formatting and structural revisions — not merely "zero `w:ins`/`w:del`."
- Existing 41 tests stay green; clean docs bypass all revision logic.

## 9. Guarantees & explicit limitations
- **Review-preserving (default):** revision content + metadata + placement + review semantics
  preserved within the supported set, verified after every pass; regions we cannot safely conform
  are reported, never silently altered. XML serialization may differ from the original; the original
  package is retained byte-exact as the archive.
- **Accept/reject:** the *intermediate projection* equals Word's accept/reject for the declared,
  tested feature set; unknown constructs block the projection. Comments handled per §7.
- **Reconstruction (M4):** establishes source **lineage**, not an unchanged original edit; generated
  content is marked and labeled; never presented as the original tracked changes.
- **Inherent limit:** full conformance + exact preservation are not simultaneously achievable for
  every paragraph; conflicting passes stay off revised regions until individually supported.

## 10. Sequence
1. **M1.1** strong ledger (structured payloads, placement, comments, all parts, unsupported-feature
   detection, no-op round-trip). *Prerequisite for trusting any gate.*
2. **M2** conservative review-preserving conformance + dependency-safe style import + per-pass
   transactional rollback + exceptions. *Default path for revised docs.*
3. **M3** accept/reject projectors for the declared feature set (support matrix + occurrence-aware
   tests). *Explicit branch.*
4. **M4** expand compatible transforms; optional reconstruction.

## Amendments accepted (post-v2 GPT-6 re-review) — binding on M1.1

1. **Two-part formatting guarantee.** (a) Original content, structural decisions, and formatting
   *revisions* retain their meaning; (b) explicitly permitted house-format changes may alter
   presentation where they do **not** rewrite an existing revision's operation. When a formatting
   revision applies, protect the **entire** relevant current property set **and** its historical
   snapshot — not just the properties that differ (a `pPrChange`/`rPrChange` stores the whole
   previous property set, not per-attribute deltas).
2. **Ledger depth.** Relationship *targets* are not enough — capture rel type, target mode, resolved
   target, and a **hash of the target's content** (image/OLE/chart bytes); protect drawing
   dimensions/crop/placement. Container identity is not enough — record each revision's **ordered
   position** relative to surrounding content/markers (an intra-paragraph move must fail). Do **not**
   treat paragraph indexes / row coords as stable identity — assign **internal identities before
   mutation** and track permitted structural changes explicitly.
3. **No-op match is a test, not proof.** Add independent checks beyond the ledger: preservation of
   XML **outside the declared mutation scope**; **namespace / mc-compatibility integrity**
   (`mc:Ignorable`, `mc:Choice/@Requires` prefixes must stay bound — ElementTree needs an explicit
   preservation strategy); package **relationships** and **protected binary parts**; applicable
   schema/semantic validation.
4. **Allowed-change check per pass.** Each mutating pass gets two gates: (a) preservation
   (revisions/comments/deps intact) **and** (b) allowed-change — all *other* differences are limited
   to that pass's **declared** operations (e.g. a style pass may change named `pStyle` + import
   required defs; it must not alter text, remove paragraphs, or touch unrelated relationships).
5. **Unsupported features → one of three explicit outcomes:** preserve the part/dependency group
   untouched and continue; skip the operation and report; or block that output. A warning alone never
   authorizes destructive legacy passes over unsupported content. Run the **full preflight inventory
   before** choosing the clean-document bypass (old 3-part zero ≠ revision-free). A **"revised
   region"** includes relevant ancestors + linked structures (row/cell, paragraph boundaries, move
   ranges, comments, fields, section deps) — local paragraph inspection is insufficient.
6. **Defaults/theme rule (resolves the v2 contradiction):** preserve the **destination** document's
   global defaults and theme; where imported house styles need different defaults/theme, express the
   required formatting **locally** in the imported definitions when supported, else report a
   conformance limitation. Never import defaults/theme wholesale.

**M1.1 acceptance = these challenge tests each fail correctly:**
| Deliberate modification | Expected result |
|---|---|
| Change image bytes, same rel target | preservation failure (binary hash) |
| Move a revision within the same paragraph | placement failure |
| Change current props while keeping `rPrChange` unchanged | preservation failure (protected-property policy) |
| Delete ordinary text during style assignment | allowed-change failure |
| Break a namespace binding used by compat markup | serialization/validation failure |
| Revisions only in a header/footer | clean-document bypass prevented |
| Import a conflicting template style/default | preserve existing deps or report an exception |

## Structural-change policy in preserve mode (Alex, 2026-09-16)

Formatting conforms automatically (content-stream invariant guarantees words/positions/authors of
tracked changes are untouched — including formatting *inside* an inserted paragraph: an expert's
copy-pasted list item gets the right style while staying a tracked insertion by its author). Content
STRUCTURE changes are governed per type:

- **Auto-apply** (reshape only clean content; ledger still guarantees no tracked change/comment is
  touched, else rolled back): #1 merge PDF line-break splits, #2 delete empty paragraphs, #4 remove
  manual page breaks, #9 uppercase headings (as caps FORMATTING, letters unchanged — not a text edit).
- **Ask** (surface as interactive JudgmentCalls, accept/reject per instance; any instance on/adjacent
  to a tracked change or comment flagged for individual review): #3 unwrap single-cell wrapper tables,
  #5 extract floating image → inline, #6 split caption/heading from body, #7 drop empty table columns,
  #8 rebuild caption/cross-references as fields (recommend Accept — displayed text unchanged).

Implementation notes: auto structural passes verify the LEDGER (tracked content + comments + binaries)
rather than the full content-stream (they legitimately change clean-content structure); they must skip
tracked-adjacent instances so the ledger stays clean. Ask passes emit one JudgmentCall per instance
through the existing two-pass analyze/apply mechanism.

## Change log vs v1 (what GPT-6's review changed)
1. Ledger reframed as insufficient → **M1.1** with structured text+non-text payloads, placement/
   associations, comment bodies/anchors, all story parts, unsupported-feature detection, no-op
   round-trip; SHA-256.
2. Dropped "byte-exact markup"; contract now = exact content+metadata+placement+semantics within a
   declared feature set, + original package kept byte-exact as archive; projection semantics cover
   structure/objects/formatting, not just text.
3. Accept/reject expanded to a full **support matrix** with context-dependent dispatch; unknown ⇒
   block; paragraph-merge rule de-approved pending tests; preserve non-run children.
4. Removed the incorrect payload-presence test → **occurrence-aware ordered expected projections**;
   staged Original→projection→conform→result; "no unresolved supported constructs."
5. M3 skip-guard recovery changed from per-paragraph revert to **per-pass transactional rollback**;
   verify after each mutating pass + final package.
6. "Compatible: run everywhere" removed; `classify`/`fix_levels` now **conditional**;
   `force_field_update` = explicit behavior; `strip_direct` via property allowlists; typography
   stays deferred.
7. Style "merge, don't replace" given a full **dependency policy** and promoted to an early
   milestone; don't overwrite by matching ID; don't change global defaults.
8. Comments given an **explicit disposition policy** + fixtures.
9. Milestones **reordered**: preserve-review-history (M2) before accept/reject (M3); **default =
   preserve** for revised docs, accept/reject explicit.
10. M4 attribution reworded: **lineage, not exact original edit** after transformation.
