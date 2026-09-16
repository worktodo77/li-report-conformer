"""Generate synthetic fictitious forensic expert reports at four defect-density tiers (a clean
control plus low/medium/high), exercising every conformance class the LI conformer checks — in both
non-tracked and tracked-change form — with full front matter, images, tables, footnotes, comments,
tracked changes by five authors, and a landscape section.

Ground truth is authoritative and per-instance:
  * every defect carries a stable locator bookmark, a revision_relation (unrelated / inside_revision
    / adjacent_to_revision) and an explicit expected_disposition (what the engine should do to THIS
    instance — including 'hold' for instances the preservation gate must not touch);
  * every tracked change is recorded as an actual occurrence (kind, id, author, date, payload,
    locator) — counts are DERIVED from that list, never hand-incremented;
  * generation FAILS LOUD if a declared asset (image/comment) cannot be created.

    python synthetic/generate.py                 # builds clean + low + medium + high into out/

Hard, difficult tracked constructs (paragraph-mark deletion, moves, cell revisions, corrupted style
definitions, comment-inside-removed) live in the companion adversarial suite (adversarial.py), not
forced into the long reports. Nothing here is real: all names/projects/figures/quotes are invented.
"""
import os
import sys
import json
import random
import hashlib
import zipfile
import shutil

import docx
from docx import Document
from docx.shared import Inches
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.text import WD_BREAK
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
import lib
import content as C

ASSETS = os.path.join(HERE, 'assets')
OUT = os.path.join(HERE, 'out')
GENERATOR_VERSION = '2.0'

# defect-density tiers with FIXED seeds (reproducible regardless of PYTHONHASHSEED).
TIERS = {
    'clean':  dict(seed=101, bulk_defect=0.0,  spelling=0.0,  grammar=0.0),
    'low':    dict(seed=202, bulk_defect=0.03, spelling=0.004, grammar=0.002),
    'medium': dict(seed=303, bulk_defect=0.17, spelling=0.03,  grammar=0.015),
    'high':   dict(seed=404, bulk_defect=0.72, spelling=0.14,  grammar=0.06),
}
# informal labels; the manifest's computed_quality (element pass-rate) is the authoritative figure.
TIER_QUALITY = {'clean': '100% control', 'low': '~90%', 'medium': '~70%', 'high': '~25%'}

MISSPELL = {'the': 'teh', 'analysis': 'analsyis', 'schedule': 'schedual', 'delay': 'dealy',
            'critical': 'critcal', 'completion': 'completition', 'contractor': 'contracter',
            'evidence': 'evidance', 'programme': 'programe', 'extension': 'extention'}
GRAMMAR = [(' is ', ' are '), (' was ', ' were '), (' has ', ' have '), (' its ', " it's "),
           (' affect ', ' effect '), (' their ', ' there ')]


def _sha(path):
    try:
        with open(path, 'rb') as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return None


def _shatext(t):
    return hashlib.sha256(t.encode('utf8')).hexdigest()[:12]


class Report:
    def __init__(self, tier):
        self.tier = tier
        self.cfg = TIERS[tier]
        self.rng = random.Random(self.cfg['seed'])
        self.doc = Document(lib.li_base_docx())
        self.ids = lib.Ids()
        self.bid = 5000
        self.fnid = 1
        self.date_n = 0
        self.footnotes = []              # (id, text, defect_style, author-or-None-for-tracked)
        self.section_no = 0
        self.fig_seq = {}
        self.tab_seq = {}
        self.tof_entries = []            # (anchor, displayed_title, real_bool)
        self.lot_entries = []
        self.lof_heading = None
        self.lot_heading = None
        self.defects = []
        self.revisions = []
        self.comments = []
        self.elements = 0                # conformance-eligible elements (quality denominator)
        self._cur_elem = 0
        self._bad_elems = set()
        self.spelling = 0
        self.grammar = 0
        self._clear_body()

    # -- infra --------------------------------------------------------------
    def _clear_body(self):
        body = self.doc.element.body
        for child in list(body):
            if child.tag != qn('w:sectPr'):
                body.remove(child)

    def new_bookmark(self):
        self.bid += 1
        return self.bid

    def author(self):
        a = self.rng.choice(C.AUTHORS)
        return a[0], a[1]

    def date(self):
        self.date_n += 1
        return "2026-04-%02dT%02d:%02d:00Z" % (1 + self.date_n % 27, 8 + self.date_n % 10,
                                               self.date_n % 60)

    def loc(self, p, tag):
        name = '_LOC_%s_%04d' % (tag, len(self.defects) + len(self.revisions) + 1)
        lib.add_locator(p, name, self.new_bookmark())
        return name

    def _elem(self):
        self.elements += 1
        self._cur_elem = self.elements
        return self._cur_elem

    def record(self, cls, locator, relation, disposition, note='', data=None):
        self._bad_elems.add(self._cur_elem)
        self.defects.append({'id': 'D%03d' % (len(self.defects) + 1), 'cls': cls,
                             'locator': locator, 'revision_relation': relation,
                             'expected_disposition': disposition, 'note': note, 'data': data or {}})

    def add_rev(self, rec, locator=None, part='document', relation='inside_revision'):
        rec = dict(rec); rec['locator'] = locator; rec['part'] = part
        self.revisions.append(rec)
        return rec

    # -- tracked-change wrappers (single source of truth) -------------------
    def ins_run(self, run, p, locator=None):
        a, _ = self.author()
        rec = lib.wrap_run_ins(run, self.ids, a, self.date())
        return self.add_rev(rec, locator)

    def del_run(self, run, p, locator=None):
        a, _ = self.author()
        rec = lib.wrap_run_del(run, self.ids, a, self.date())
        return self.add_rev(rec, locator)

    def comment_on(self, p, run, locator=None):
        a, ini = self.author()
        text = self.rng.choice(["Please confirm the source for this figure.",
                                "Consider tightening this opinion.",
                                "Cross-check against the window analysis.",
                                "Is this the correct data date?"])
        lib.add_comment(self.doc, run, text, a, ini)
        self.comments.append({'author': a, 'anchor_locator': locator, 'text_sha': _shatext(text)})

    # -- text helpers -------------------------------------------------------
    def fill(self, tmpl):
        return tmpl.format(a=self.rng.choice(C.ACTIVITIES), n=self.rng.randint(12, 240),
                           m="%s update" % self.rng.choice(['March', 'April', 'May', 'June']))

    def corrupt_text(self, t):
        words = t.split(' ')
        for i, w in enumerate(words):
            lw = w.lower().strip('.,;:')
            if lw in MISSPELL and self.rng.random() < self.cfg['spelling']:
                words[i] = w.replace(lw, MISSPELL[lw]); self.spelling += 1
        t = ' '.join(words)
        for a, b in GRAMMAR:
            if a in t and self.rng.random() < self.cfg['grammar']:
                t = t.replace(a, b, 1); self.grammar += 1
        return t

    def bulk(self):
        return self.rng.random() < self.cfg['bulk_defect']

    # -- headings / paragraphs ---------------------------------------------
    def heading(self, text, level=1):
        if level == 1:
            self.section_no += 1
        return self.doc.add_paragraph(text, style='Heading%d' % level)

    def para(self, text, style='NumberedParagraph'):
        """A body paragraph; bulk tier may make it a foreign-style and/or direct-formatted defect.
        Returns (paragraph, recorded_a_defect) so the caller never adds a stray tracked change to a
        paragraph already recorded as a non-tracked defect."""
        self._elem()
        text = self.corrupt_text(text)
        p = self.doc.add_paragraph(text, style=style)
        defect = False
        if self.tier != 'clean' and self.bulk():
            lib.ensure_foreign_style(self.doc, 'FirmBody', 'Firm Body')
            p.style = self.doc.styles['Normal']
            self.record('classify_body', self.loc(p, 'cb'), 'unrelated', 'restyle_to_LI', text[:40])
            defect = True
        if self.tier != 'clean' and self.bulk() and p.runs:
            lib.add_direct_rpr(p.runs[0], '<w:rFonts w:ascii="Calibri"/><w:sz w:val="20"/>'
                                          '<w:color w:val="FF0000"/>')
            self.record('strip_direct', self.loc(p, 'sd'), 'unrelated', 'strip_direct_formatting',
                        text[:40], data={'gone_marker': 'FF0000'})
            defect = True
        return p, defect

    def maybe_track_clean(self, p):
        """Randomly mark a CLEAN paragraph (no recorded defect) with a tracked insertion/comment.
        Run references are captured up front: ins_run re-parents a run into <w:ins>, after which
        python-docx's p.runs no longer lists it."""
        if self.tier == 'clean':
            return
        runs = list(p.runs)
        if not runs:
            return
        if self.rng.random() < 0.05:
            self.comment_on(p, runs[0], self.loc(p, 'cm'))
        if self.rng.random() < 0.12:
            self.ins_run(runs[-1], p, self.loc(p, 'ins'))

    # ================================================================ per-class emitters
    # Each returns after recording the defect (and any tracked change) with a stable locator and an
    # explicit expected_disposition. The tracked variant of a class specifies what SHOULD happen to
    # that instance — often 'hold' (the preservation gate must leave it untouched), which is a
    # correctness property, not a failure.

    def _new_style_para(self, text, foreign):
        p = self.doc.add_paragraph(text, style='Normal' if foreign else 'NumberedParagraph')
        return p

    def emit_classify_body(self, tracked):
        self._elem()
        lib.ensure_foreign_style(self.doc, 'FirmBody', 'Firm Body')
        p = self.doc.add_paragraph(self.fill(self.rng.choice(C.FINDING)), style='FirmBody')
        loc = self.loc(p, 'cb')
        if tracked and p.runs:
            self.ins_run(p.runs[-1], p, loc)
            self.record('classify_body', loc, 'inside_revision', 'restyle_to_LI',
                        'foreign style, run inserted; restyle AND preserve edit')
        else:
            self.record('classify_body', loc, 'unrelated', 'restyle_to_LI', 'foreign style')

    def emit_classify_bullet(self, tracked):
        self._elem()
        p = self.doc.add_paragraph(self.fill(self.rng.choice(C.FINDING)), style='List Paragraph')
        p._p.get_or_add_pPr().append(parse_xml('<w:numPr %s><w:ilvl w:val="0"/><w:numId w:val="1"/>'
                                               '</w:numPr>' % nsdecls('w')))
        loc = self.loc(p, 'cbul')
        if tracked and p.runs:
            self.ins_run(p.runs[-1], p, loc)
            self.record('classify_bullet', loc, 'inside_revision', 'restyle_to_LI', 'bullet, inserted')
        else:
            self.record('classify_bullet', loc, 'unrelated', 'restyle_to_LI', 'ListParagraph bullet')

    def emit_strip_direct(self, tracked):
        self._elem()
        p = self.doc.add_paragraph(self.fill(self.rng.choice(C.FINDING)), style='NumberedParagraph')
        lib.add_direct_ppr(p, '<w:spacing w:before="240" w:after="240"/><w:ind w:left="720"/>')
        if p.runs:
            lib.add_direct_rpr(p.runs[0], '<w:rFonts w:ascii="Calibri"/><w:sz w:val="28"/>')
        loc = self.loc(p, 'sd')
        if tracked and p.runs:
            self.ins_run(p.runs[-1], p, loc)
            # preserve mode SKIPS direct-formatting stripping on a revised paragraph -> HOLD
            self.record('strip_direct', loc, 'inside_revision', 'hold',
                        'direct formatting on a revised paragraph is left to protect the edit')
        else:
            self.record('strip_direct', loc, 'unrelated', 'strip_direct_formatting', 'direct fmt',
                        data={'gone_marker': 'Calibri'})

    def emit_typography(self, tracked):
        self._elem()
        raw = ('The Engineer stated the works were "substantially complete" -- a view I do not share '
               '-- and fixed the milestone at 05 June with a 3" tolerance.')
        p = self.doc.add_paragraph(raw, style='NumberedParagraph')
        loc = self.loc(p, 'typo')
        if tracked and p.runs:
            self.ins_run(p.runs[0], p, loc)   # the straight-quote text IS the insertion
            # typography masks revision content -> the inserted characters are PRESERVED, not changed
            self.record('typography', loc, 'inside_revision', 'hold',
                        'inserted text keeps its straight quotes (payload preserved)')
        else:
            self.record('typography', loc, 'unrelated', 'typography_applied', 'straight quotes/dashes',
                        data={'no_straight_quote': True})

    def emit_footnote(self, tracked, defect):
        self._elem()
        p = self.doc.add_paragraph(self.fill(self.rng.choice(C.FINDING)), style='NumberedParagraph')
        loc = self.loc(p, 'fn')
        fid = self.fnid; self.fnid += 1
        text = self.fill(self.rng.choice(C.FOOTNOTES))
        p._p.append(parse_xml('<w:r %s><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>'
                              '<w:footnoteReference w:id="%d"/></w:r>' % (nsdecls('w'), fid)))
        # tracked footnote: the footnote body carries an insertion -> fix_footnotes skips it -> HOLD
        self.footnotes.append((fid, text, defect, tracked, loc))
        if defect:
            disp = 'hold' if tracked else 'footnote_restyled'
            rel = 'inside_revision' if tracked else 'unrelated'
            self.record('footnote_style', loc, rel, disp, 'footnote %d style' % fid,
                        data={'fid': fid})

    def emit_pdf_linesplit(self, tracked):
        # No locator BOOKMARK here: the merge pass skips any paragraph carrying a bookmark, so a
        # bookmark would itself prevent the merge. Locate by content instead, and let the merge (or
        # the hold) be driven only by the revision.
        self._elem()
        # a UNIQUE sentence (so the content locator cannot collide with a clean quote elsewhere)
        uid = len(self.defects) + 1
        a = ("In respect of matter number %d the tribunal held that the extension of time had been "
             "validly claimed and was supported by the contemporaneous" % uid)
        b = "record, and that the relevant notice provisions had been substantially complied with."
        self.doc.add_paragraph(a, style='ExcerptorQuote')
        p2 = self.doc.add_paragraph(b, style='ExcerptorQuote')
        snippet = 'text:In respect of matter number %d ' % uid
        if tracked and p2.runs:
            self.ins_run(p2.runs[-1], p2, snippet)   # a revision in an excerpt -> merge skips it
            self.record('pdf_linesplit', snippet, 'adjacent_to_revision', 'hold',
                        'a split excerpt carries a revision -> not merged',
                        data={'first_half_len': len(a)})
        else:
            self.record('pdf_linesplit', snippet, 'unrelated', 'merged', 'PDF line-split excerpt',
                        data={'min_len': len(a) + 3, 'first_half_len': len(a)})

    def emit_empty_para(self, tracked):
        self._elem()
        p = self.doc.add_paragraph('', style='NumberedParagraph')
        # Sidecar locator (an rsidR attribute on the <w:p>, not a bookmark): a bookmark would add
        # BMS/BME tokens whose loss on pruning trips the structure gate, so the locator would itself
        # prevent the removal we are trying to measure.
        loc = 'text:__SYN_EMPTY_%04d__' % self.elements
        p._p.set(qn('w:rsidR'), loc.split(':', 1)[1])
        if tracked:
            r = p.add_run(' ')
            self.ins_run(r, p, loc)   # the empty paragraph is itself a tracked insertion
            self.record('empty_para', loc, 'inside_revision', 'hold',
                        'a tracked empty paragraph must not be pruned')
        else:
            self.record('empty_para', loc, 'unrelated', 'removed', 'stray empty numbered paragraph')

    def emit_page_break(self, tracked):
        self._elem()
        p = self.doc.add_paragraph(style='NumberedParagraph')
        r = p.add_run(); r.add_break(WD_BREAK.PAGE)
        # Sidecar locator on the <w:p> (a valid rsidR attribute, matched by the prune's `<w:p\b[^>]*>`):
        # a bookmark or a marker on the <w:br> would change the pure page-break shape and block the
        # prune match, so the locator would itself prevent the removal we are measuring.
        loc = 'text:__SYN_PAGE_BREAK_%04d__' % self.elements
        p._p.set(qn('w:rsidR'), loc.split(':', 1)[1])
        if tracked:
            self.ins_run(r, p, loc)
            self.record('page_break', loc, 'inside_revision', 'hold',
                        'a tracked manual page break must not be pruned')
        else:
            self.record('page_break', loc, 'unrelated', 'removed', 'manual page-break paragraph')

    def emit_heading_body_merge(self, tracked):
        self._elem()
        p = self.doc.add_paragraph(style='Heading2')
        p.add_run("Basis of the Delay Assessment")
        p.add_run("  ")
        body_run = p.add_run("This body sentence was merged into the heading and must be split out.")
        loc = self.loc(p, 'hbm')
        if tracked:
            self.ins_run(body_run, p, loc)
            self.record('heading_body_merge', loc, 'inside_revision', 'hold',
                        'merged heading whose body text is a tracked insertion -> not split')
        else:
            self.record('heading_body_merge', loc, 'unrelated', 'split', 'heading+body merged',
                        data={'body_marker': 'must be split out'})

    def emit_level_fix(self, tracked):
        """A nested-list level defect: an L2 list item directly under a numbered paragraph, which
        fix_levels promotes to L1. Paired with a tracked-content case that must be held."""
        self._elem()
        self.doc.add_paragraph('A numbered lead-in paragraph introduces the sub-list.',
                               style='NumberedParagraph')                     # the promotion anchor
        p = self.doc.add_paragraph('A nested sub-item that started at level two.',
                                   style='NumberedParagraphL2')
        loc = self.loc(p, 'lvl')
        if tracked and p.runs:
            self.ins_run(p.runs[-1], p, loc)
            # the promotion is a pStyle change (L2 -> L1), orthogonal to the tracked content, so the
            # engine applies it AND preserves the edit — like classify. Not a hold.
            self.record('level_fix', loc, 'inside_revision', 'level_fixed',
                        'L2 promotion applies to a revised paragraph; the edit is preserved')
        else:
            self.record('level_fix', loc, 'unrelated', 'level_fixed',
                        'L2 under a numbered paragraph -> promote to L1')

    def emit_xref_literal(self, tracked):
        """A literal cross-reference ('See Figure X-Y'). In the clean case #8b rebuilds it as a REF
        field pointing at a REAL, fielded, bookmarked caption created here; in the tracked case the
        reference text is itself an insertion (masked from #8b) and must remain literal."""
        self._elem()
        sec, seq, _name = self.figure('window_table.png', 'Reference target for a cross-reference')
        label = "Figure %d-%d" % (sec, seq)
        p = self.doc.add_paragraph('See %s for the delay analysis.' % label,
                                   style='NumberedParagraph')
        loc = self.loc(p, 'xref')
        if tracked and p.runs:
            self.ins_run(p.runs[-1], p, loc)
            self.record('xref_literal', loc, 'inside_revision', 'hold',
                        'the cross-reference is inside a tracked insertion (masked) -> stays literal')
        else:
            self.record('xref_literal', loc, 'unrelated', 'xref_fielded',
                        'literal cross-reference -> REF field', data={'label': label})
    # -- tables -------------------------------------------------------------
    def _ensure_litable(self):
        if not lib.has_style(self.doc, 'LITable'):
            from conformer.engine import LITABLE
            self.doc.styles.element.append(
                parse_xml(LITABLE.replace('<w:style ', '<w:style %s ' % nsdecls('w'), 1)))

    def table_with_caption(self, clean, empty_col=False, tracked=False):
        self._elem()
        header = ["Window", "Data date", "Forecast finish", "Slippage (days)"]
        t = self.doc.add_table(rows=6, cols=4 + (1 if empty_col else 0))
        for ci, h in enumerate(header):
            t.cell(0, ci).paragraphs[0].add_run(h)
        for ri in range(1, 6):
            vals = ["W-%d" % ri, "%02d/26" % ri, "Q%d-27" % (ri % 4 + 1), str(self.rng.randint(0, 40))]
            for ci, v in enumerate(vals):
                t.cell(ri, ci).paragraphs[0].add_run(v)
        # caption (fielded when clean) with a real bookmark target
        self.tab_seq[self.section_no] = self.tab_seq.get(self.section_no, 0) + 1
        seq = self.tab_seq[self.section_no]
        name = "_Ref_T%d%d%d" % (self.section_no, seq, self.rng.randint(100, 999))
        cap = self.doc.add_paragraph(style='Caption')
        b0, b1 = lib.bookmark(name, self.new_bookmark())
        title = "Window analysis of the %s works" % self.rng.choice(C.ACTIVITIES)
        if clean:
            self._ensure_litable(); t.style = 'LITable'
            inner = (b0 + '<w:r><w:t xml:space="preserve">Table </w:t></w:r>'
                     + lib.field_runs('STYLEREF 1 \\s', str(self.section_no))
                     + '<w:r><w:t xml:space="preserve">-</w:t></w:r>'
                     + lib.field_runs('SEQ Table \\* ARABIC \\s 1', str(seq))
                     + '<w:r><w:t xml:space="preserve">: %s</w:t></w:r>' % title + b1)
            lib.set_para_xml(cap, inner)
        else:
            t._tbl.tblPr.append(parse_xml(
                '<w:tblBorders %s><w:top w:val="single" w:sz="12" w:space="0" w:color="FF0000"/>'
                '<w:bottom w:val="single" w:sz="12" w:space="0" w:color="FF0000"/></w:tblBorders>'
                % nsdecls('w')))
            lib.set_para_xml(cap, b0 + '<w:r><w:t xml:space="preserve">Table %d-%d: %s</w:t></w:r>'
                             % (self.section_no, seq, title) + b1)
        self.lot_entries.append((name, "Table %d-%d: %s" % (self.section_no, seq, title), True))
        loc = self.loc(t.cell(0, 0).paragraphs[0], 'tbl')
        if tracked:
            rec_run = t.cell(1, 0).paragraphs[0].runs[0]
            self.ins_run(rec_run, None, loc)
            if empty_col:
                self.record('table_empty_col', loc, 'adjacent_to_revision', 'columns_dropped',
                            'the empty column has no tracked content; dropping it does not touch the '
                            'cell revision. Flagged for individual review.')
            else:
                self.record('table_style', loc, 'adjacent_to_revision', 'set_LITable',
                            'unstyled table with a cell revision -> styled, edit preserved')
        else:
            if empty_col:
                self.record('table_empty_col', loc, 'unrelated', 'columns_dropped', 'empty column')
            elif not clean:
                self.record('table_style', loc, 'unrelated', 'set_LITable', 'unstyled table')

    def wrapper_table(self, tracked):
        self._elem()
        t = self.doc.add_table(rows=1, cols=1)
        c = t.cell(0, 0)
        c.paragraphs[0].add_run("This paragraph was wrapped inside a single-cell layout table and "
                                "should be unwrapped into ordinary body text.")
        p2 = c.add_paragraph("A second wrapped paragraph continues the passage.")
        loc = self.loc(c.paragraphs[0], 'wrap')
        if tracked and p2.runs:
            self.ins_run(p2.runs[-1], p2, loc)
            self.record('wrapper_table', loc, 'inside_revision', 'unwrapped',
                        'unwrapping moves the wrapped content (including the edit) to body text; '
                        'words, tracked status and author are preserved. Flagged for review.')
        else:
            self.record('wrapper_table', loc, 'unrelated', 'unwrapped', 'single-cell wrapper')

    # -- figures ------------------------------------------------------------
    def figure(self, image, title, floating=False, wrong_number=False, tof_mismatch=False,
               caption_literal=False, tracked=False, structural_defect=None):
        self._elem()
        img_path = os.path.join(ASSETS, image)
        if not os.path.exists(img_path):
            raise lib.AssetError('missing figure asset: %s' % img_path)
        self.fig_seq[self.section_no] = self.fig_seq.get(self.section_no, 0) + 1
        seq = self.fig_seq[self.section_no]
        disp_sec = self.section_no + (1 if wrong_number else 0)
        name = "_Ref_F%d%d%d" % (disp_sec, seq, self.rng.randint(100, 999))
        ip = self.doc.add_paragraph(style='SpacebehindafteraGraphic')
        run = ip.add_run()
        run.add_picture(img_path, width=Inches(5.5))
        img_loc = self.loc(ip, 'fig')
        if floating:
            self._make_floating(ip)
            if tracked and ip.runs:
                self.ins_run(ip.runs[-1], ip, img_loc)
                self.record('floating_image', img_loc, 'inside_revision', 'inline',
                            'floating image is inlined (a layout change); the inserted object is '
                            'preserved. Flagged for individual review.')
            else:
                self.record('floating_image', img_loc, 'unrelated', 'inline', 'floating picture')
        # caption
        cap = self.doc.add_paragraph(style='Caption')
        b0, b1 = lib.bookmark(name, self.new_bookmark())
        if caption_literal:
            lib.set_para_xml(cap, b0 + '<w:r><w:t xml:space="preserve">Figure %d-%d: %s</w:t></w:r>'
                             % (disp_sec, seq, title) + b1)
            # locate the caption by its OWN _Ref bookmark (preserved by #8a), not a separate _LOC
            # whose loss would trip the caption rebuild's bookmark guard.
            self._elem()
            if tracked and cap.runs:
                self.ins_run(cap.runs[0], cap, name)
                self.record('caption_literal', name, 'inside_revision', 'hold',
                            'literal caption whose text is a revision -> fielding would drop the '
                            'insertion, so it is held for individual review')
            else:
                self.record('caption_literal', name, 'unrelated', 'fielded', 'literal caption')
        else:
            inner = (b0 + '<w:r><w:t xml:space="preserve">Figure </w:t></w:r>'
                     + lib.field_runs('STYLEREF 1 \\s', str(disp_sec))
                     + '<w:r><w:t xml:space="preserve">-</w:t></w:r>'
                     + lib.field_runs('SEQ Figure \\* ARABIC \\s 1', str(seq))
                     + '<w:r><w:t xml:space="preserve">: %s</w:t></w:r>' % title + b1)
            lib.set_para_xml(cap, inner)
        if wrong_number:
            self.record('figure_numbering', self.loc(cap, 'fnum'), 'unrelated', 'audit_flag',
                        'caption section number does not match its section')
        shown = title + (" (revised)" if tof_mismatch else "")
        if tof_mismatch:
            self.record('tof_mismatch', self.loc(cap, 'tof'), 'unrelated', 'audit_flag',
                        'List-of-Figures title differs from the caption')
        self.tof_entries.append((name, "Figure %d-%d: %s" % (disp_sec, seq, shown), True))
        return disp_sec, seq, name

    def _make_floating(self, p):
        """Inline drawing -> floating anchor with schema-correct child order (wrap BEFORE docPr)."""
        for inline in list(p._p.iter(qn('wp:inline'))):
            anchor = parse_xml(
                '<wp:anchor %s distT="0" distB="0" distL="114300" distR="114300" simplePos="0" '
                'relativeHeight="2" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">'
                '<wp:simplePos x="0" y="0"/>'
                '<wp:positionH relativeFrom="column"><wp:posOffset>0</wp:posOffset></wp:positionH>'
                '<wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV>'
                '</wp:anchor>' % nsdecls('wp'))
            docpr = None
            children = list(inline)
            for ch in children:
                if ch.tag == qn('wp:docPr'):
                    docpr = ch
            wrap = parse_xml('<wp:wrapNone %s/>' % nsdecls('wp'))
            for ch in children:
                if ch is docpr:
                    anchor.append(wrap)        # wrapNone immediately before docPr
                anchor.append(ch)
            if docpr is None:
                anchor.append(wrap)
            inline.getparent().replace(inline, anchor)
            break

    def emit_section_landscape(self):
        self._elem()
        sec = self.doc.add_section(WD_SECTION.NEW_PAGE)
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = sec.page_height, sec.page_width
        h = self.doc.add_paragraph("Appendix A — Delay Ledger", style='Heading1')
        loc = self.loc(h, 'land')
        t = self.doc.add_table(rows=6, cols=7)
        hdr = ["Event", "Start", "Finish", "Owner", "Excusable", "Compensable", "Net days"]
        for ci, hh in enumerate(hdr):
            t.cell(0, ci).paragraphs[0].add_run(hh)
        for ri in range(1, 6):
            for ci in range(7):
                t.cell(ri, ci).paragraphs[0].add_run(
                    str(self.rng.randint(0, 30)) if ci >= 4 else "E%d" % ri)
        self.record('section_landscape', loc, 'unrelated', 'portrait_restored',
                    'landscape block needs the portrait section restored')

    # ================================================================ body assembly
    def _guaranteed_queue(self):
        if self.tier == 'clean':
            return []
        pairs = []
        trackable = ['classify_body', 'classify_bullet', 'strip_direct', 'typography',
                     'pdf_linesplit', 'empty_para', 'page_break', 'heading_body_merge',
                     'wrapper_table', 'floating_image', 'caption_literal', 'footnote_style',
                     'table_style', 'table_empty_col', 'level_fix', 'xref_literal']
        untracked_only = ['section_landscape', 'figure_numbering', 'tof_mismatch']
        for cls in trackable:
            pairs.append((cls, False)); pairs.append((cls, True))
        for cls in untracked_only:
            pairs.append((cls, False))
        self.rng.shuffle(pairs)
        return pairs

    def _emit_guaranteed(self, cls, tracked):
        if cls == 'classify_body': self.emit_classify_body(tracked)
        elif cls == 'classify_bullet': self.emit_classify_bullet(tracked)
        elif cls == 'strip_direct': self.emit_strip_direct(tracked)
        elif cls == 'typography': self.emit_typography(tracked)
        elif cls == 'pdf_linesplit': self.emit_pdf_linesplit(tracked)
        elif cls == 'empty_para': self.emit_empty_para(tracked)
        elif cls == 'page_break': self.emit_page_break(tracked)
        elif cls == 'heading_body_merge': self.emit_heading_body_merge(tracked)
        elif cls == 'wrapper_table': self.wrapper_table(tracked)
        elif cls == 'floating_image':
            self.figure('gantt.png', 'As-planned versus as-built schedule', floating=True,
                        tracked=tracked)
        elif cls == 'caption_literal':
            self.figure('scurve.png', 'Planned versus actual cumulative progress',
                        caption_literal=True, tracked=tracked)
        elif cls == 'footnote_style': self.emit_footnote(tracked, defect=True)
        elif cls == 'table_style': self.table_with_caption(clean=False, tracked=tracked)
        elif cls == 'table_empty_col':
            self.table_with_caption(clean=False, empty_col=True, tracked=tracked)
        elif cls == 'level_fix': self.emit_level_fix(tracked)
        elif cls == 'xref_literal': self.emit_xref_literal(tracked)
        elif cls == 'section_landscape': pass   # emitted once at the end
        elif cls == 'figure_numbering':
            self.figure('bar_delay.png', 'Delay days by causal category', wrong_number=True)
        elif cls == 'tof_mismatch':
            self.figure('float_hist.png', 'Distribution of total float', tof_mismatch=True)

    _BODY_IMAGES = ['gantt.png', 'scurve.png', 'bar_delay.png', 'float_hist.png', 'window_table.png']

    def body(self):
        queue = self._guaranteed_queue()
        landscape_pending = any(c == 'section_landscape' for c, _ in queue)
        queue = [(c, t) for c, t in queue if c != 'section_landscape']
        per_section = max(1, (len(queue) // max(1, len(C.SECTIONS) - 1)) + 1)
        for si, (title, key) in enumerate(C.SECTIONS):
            self.heading(title, 1)
            pools = {'method': C.METHOD, 'background': C.BACKGROUND, 'opinions': C.OPINION,
                     'conclusions': C.OPINION}.get(key, C.FINDING)
            for sub in range(self.rng.randint(3, 4)):
                self.doc.add_paragraph(self.fill(self.rng.choice(
                    ["Analysis of the {a} Works", "The {a} Window", "Findings on {a}",
                     "Assessment of the {a} Delay"])), style='Heading2')
                for i in range(self.rng.randint(7, 10)):
                    p, dfct = self.para(self.fill(self.rng.choice(pools)) + " "
                                        + self.fill(self.rng.choice(C.FINDING)))
                    if not dfct:
                        self.maybe_track_clean(p)
                # emit a couple of guaranteed defects, interspersed
                for _ in range(per_section):
                    if queue:
                        cls, tracked = queue.pop()
                        self._emit_guaranteed(cls, tracked)
                # a clean figure or table in the flow
                if self.rng.random() < 0.5:
                    self.figure(self.rng.choice(self._BODY_IMAGES),
                                self.fill(self.rng.choice(["Progress on the {a} works",
                                                           "Float erosion across the {a} window"])))
                if self.rng.random() < 0.35:
                    self.table_with_caption(clean=True)
                # a clean block quote (or a clean footnote)
                self.doc.add_paragraph(self.rng.choice(C.QUOTE), style='ExcerptorQuote')
                self.emit_footnote(tracked=False, defect=False)
        # drain any leftover guaranteed defects in a final matters section
        if queue:
            self.heading("Further Matters Arising", 1)
            self.doc.add_paragraph("The following additional matters are addressed for completeness.",
                                   style='NumberedParagraph')
            while queue:
                cls, tracked = queue.pop()
                self.doc.add_paragraph(self.fill(self.rng.choice(C.FINDING)),
                                       style='NumberedParagraph')
                self._emit_guaranteed(cls, tracked)
        self._landscape_pending = landscape_pending

    # ================================================================ front & back matter
    def front_matter(self):
        d = self.doc
        d.add_paragraph("PRIVILEGED AND CONFIDENTIAL", style='PRIVCONFSTATEMENT')
        d.add_paragraph("EXPERT REPORT ON DELAY", style='Title')
        d.add_paragraph("In the matter of %s" % C.CASE, style='Subtitle')
        for line in [C.PROJECT.title(), "Prepared for %s" % C.COUNSEL,
                     "On behalf of %s" % C.CONTRACTOR, "By %s, %s" % (C.EXPERT, C.FIRM),
                     "DRAFT for review — subject to revision."]:
            d.add_paragraph(line, style='BodyText')
        d.add_paragraph(style='NumberedParagraph').add_run().add_break(WD_BREAK.PAGE)
        d.add_paragraph("TABLE OF CONTENTS", style='TOCListTitle')
        toc = d.add_paragraph(style='TOC1')
        lib.set_para_xml(toc, lib.field_runs('TOC \\o "1-3" \\h \\z \\u', "Update this field in Word"))
        # list headings kept as anchors; their entries are inserted after the body is built
        self.lof_heading = d.add_paragraph("LIST OF FIGURES", style='TOCListTitle')
        self.lot_heading = d.add_paragraph("LIST OF TABLES", style='TOCListTitle')
        self._list_block("LIST OF EXHIBITS", C.EXHIBITS)
        self._list_block("LIST OF ATTACHMENTS", C.ATTACHMENTS)
        self._glossary()

    def _list_block(self, title, items):
        self.doc.add_paragraph(title, style='TOCListTitle')
        for i, it in enumerate(items, 1):
            self.doc.add_paragraph("%d.  %s" % (i, it), style='ListBullet')

    def _glossary(self):
        self.doc.add_paragraph("GLOSSARY OF ABBREVIATIONS", style='TOCListTitle')
        self._ensure_litable()
        t = self.doc.add_table(rows=len(C.ACRONYMS), cols=2)
        t.style = 'LITable'
        for ri, (ab, full) in enumerate(C.ACRONYMS):
            t.cell(ri, 0).paragraphs[0].add_run(ab)
            t.cell(ri, 1).paragraphs[0].add_run(full)

    def _fill_lists(self):
        """Insert List-of-Figures / List-of-Tables entries directly after their headings (no bulk
        move of the body, so the final sectPr stays at the end of the document)."""
        for heading, entries in ((self.lof_heading, self.tof_entries),
                                 (self.lot_heading, self.lot_entries)):
            anchor = heading._p
            for name, disp, _real in entries:
                p = self.doc.add_paragraph(style='TableofFigures')
                self.doc.element.body.remove(p._p)
                lib.set_para_xml(p, '<w:hyperlink %s w:anchor="%s"><w:r><w:t xml:space="preserve">%s'
                                 '</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>%d</w:t></w:r></w:hyperlink>'
                                 % (nsdecls('w'), name, disp, self.rng.randint(3, 90)))
                anchor.addnext(p._p)
                anchor = p._p

    def signature(self):
        self.doc.add_paragraph("DECLARATION", style='Heading1')
        self.doc.add_paragraph("I confirm this report sets out my independent opinion and that I "
                               "understand my duty to the Tribunal.", style='NumberedParagraph')
        for line in ["Signed:", C.EXPERT, C.FIRM, "Date:  ___________"]:
            self.doc.add_paragraph(line, style='BodyText')

    # ================================================================ build / save / manifest
    def build(self):
        self.front_matter()
        self.body()
        self.signature()
        if getattr(self, '_landscape_pending', False):
            self.emit_section_landscape()
        self._fill_lists()
        return self

    def save(self, path):
        self.doc.save(path)
        self._inject_footnotes(path)

    def _inject_footnotes(self, path):
        if not self.footnotes:
            return
        tmp = path + '.tmp'
        zin = zipfile.ZipFile(path)
        fn_xml = zin.read('word/footnotes.xml').decode('utf8') if 'word/footnotes.xml' in zin.namelist() else None
        defs = ''
        for fid, text, defect, tracked, loc in self.footnotes:
            style = 'CommentText' if defect else 'FootnoteText'
            body = '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>'
            if tracked:
                a, _ = self.author(); rid = self.ids.next(); dt = self.date()
                body += ('<w:ins w:id="%d" w:author="%s" w:date="%s">'
                         '<w:r><w:t xml:space="preserve"> %s</w:t></w:r></w:ins>' % (rid, a, dt, text))
                self.revisions.append({'kind': 'ins', 'id': rid, 'author': a, 'date': dt,
                                       'payload_text': ' ' + text, 'locator': loc, 'part': 'footnotes'})
            else:
                body += '<w:r><w:t xml:space="preserve"> %s</w:t></w:r>' % text
            defs += ('<w:footnote w:id="%d"><w:p><w:pPr><w:pStyle w:val="%s"/></w:pPr>%s</w:p>'
                     '</w:footnote>' % (fid, style, body))
        if fn_xml is not None:
            fn_xml = fn_xml.replace('</w:footnotes>', defs + '</w:footnotes>')
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for n in zin.namelist():
                data = zin.read(n)
                if n == 'word/footnotes.xml' and fn_xml is not None:
                    data = fn_xml.encode('utf8')
                zout.writestr(n, data)
        zin.close()
        shutil.move(tmp, path)

    def manifest(self, docx_path):
        from collections import Counter
        tracked_by_kind = Counter(r['kind'] for r in self.revisions)
        counts = Counter(d['cls'] for d in self.defects)
        holds = [d for d in self.defects if d['expected_disposition'] == 'hold']
        return {
            'generator_version': GENERATOR_VERSION,
            'tier': self.tier, 'quality_label': TIER_QUALITY[self.tier], 'seed': self.cfg['seed'],
            'provenance': {'template_sha': _sha(lib.TEMPLATE),
                           'assets': {a: _sha(os.path.join(ASSETS, a))
                                      for a in sorted(os.listdir(ASSETS)) if a.endswith('.png')},
                           'deps': {'python_docx': docx.__version__}},
            'elements': self.elements,
            'non_conforming_elements': len(self._bad_elems),
            'total_defects': len(self.defects),
            'computed_quality': round(1 - len(self._bad_elems) / max(1, self.elements), 3),
            'expected_holds': len(holds),
            'counts': dict(counts),
            'revisions': self.revisions,
            'tracked_by_kind': dict(tracked_by_kind),
            'tracked_total': len(self.revisions),
            'comments': self.comments,
            'comment_count': len(self.comments),
            'authors': sorted({r['author'] for r in self.revisions}),
            'spelling_errors': self.spelling, 'grammar_errors': self.grammar,
            'figures': len(self.tof_entries), 'tables': len(self.lot_entries),
            'expected_preservation': 'clean',
            'defects': self.defects,
        }


def build_tier(tier):
    os.makedirs(OUT, exist_ok=True)
    r = Report(tier).build()
    docx_path = os.path.join(OUT, 'synthetic_report_%s.docx' % tier)
    r.save(docx_path)
    man = r.manifest(docx_path)
    with open(os.path.join(OUT, 'synthetic_report_%s_manifest.json' % tier), 'w', encoding='utf8') as fh:
        json.dump(man, fh, indent=2)
    return docx_path, man


if __name__ == '__main__':
    tiers = sys.argv[1:] or ['clean', 'low', 'medium', 'high']
    for t in tiers:
        dp, man = build_tier(t)
        print('%-7s q=%s defects=%d (holds=%d) revs=%d comments=%d figs=%d tabs=%d spell=%d -> %s'
              % (t, man['computed_quality'], man['total_defects'], man['expected_holds'],
                 man['tracked_total'], man['comment_count'], man['figures'], man['tables'],
                 man['spelling_errors'], os.path.basename(dp)))
