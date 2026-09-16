"""Generate synthetic fictitious forensic expert reports at three quality tiers, exercising every
conformance class the LI conformer checks — in both non-tracked and tracked-change form — plus full
front matter (TOC, lists of figures/tables/exhibits/attachments), images, tables, footnotes, and a
landscape section. Each report is emitted with a ground-truth manifest of every injected defect,
which is the expected-results baseline for the testing plan.

    python synthetic/generate.py            # builds all three tiers into synthetic/out/

Nothing here is real: all names, projects, figures, and quotations are invented test data.
"""
import os
import sys
import json
import random
import zipfile
import shutil

import docx
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml, OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
import lib
import content as C

ASSETS = os.path.join(HERE, 'assets')
OUT = os.path.join(HERE, 'out')

# quality tiers: fraction of eligible bulk elements left CLEAN, plus damage knobs
TIERS = {
    '90': dict(quality=0.90, extra_defects=0.06, spelling=0.01, grammar=0.004, tracked_density=0.9),
    '70': dict(quality=0.70, extra_defects=0.28, spelling=0.05, grammar=0.02, tracked_density=1.0),
    '25': dict(quality=0.25, extra_defects=0.78, spelling=0.16, grammar=0.08, tracked_density=1.2),
}

DATE = "2026-04-1{d}T09:{mm}:00Z"

# spelling/grammar corruptions (applied to plain, non-tracked, non-defect text only, per tier rate)
MISSPELL = {'the': 'teh', 'analysis': 'analsyis', 'schedule': 'schedual', 'delay': 'dealy',
            'critical': 'critcal', 'completion': 'completition', 'contractor': 'contracter',
            'evidence': 'evidance', 'programme': 'programe', 'extension': 'extention'}
GRAMMAR = [(' is ', ' are '), (' was ', ' were '), (' has ', ' have '), (' its ', " it's "),
           (' affect ', ' effect '), (' their ', ' there ')]


class Report:
    def __init__(self, tier):
        self.tier = tier
        self.cfg = TIERS[tier]
        self.rng = random.Random(hash(tier) & 0xffff)
        self.doc = Document(lib.li_base_docx())
        self.ids = lib.Ids()
        self.bid = 5000
        self.fnid = 1
        self.footnotes = []              # (id, text, defect_style, tracked)
        self.section_no = 0
        self.fig_seq = {}                # section -> count
        self.tab_seq = {}
        self.fig_bookmarks = []          # (name, caption_title, section, seq)  actual
        self.tof_entries = []            # (anchor_name, displayed_title)  what List of Figures shows
        self.manifest = {'tier': tier, 'quality_target': self.cfg['quality'], 'defects': [],
                         'tracked': {'ins': 0, 'del': 0, 'ppr_change': 0, 'rpr_change': 0,
                                     'para_inserted': 0}, 'comments': 0,
                         'authors': sorted({a for a, _ in C.AUTHORS}), 'counts': {}}
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
        return DATE.format(d=self.rng.randint(0, 9), mm=self.rng.randint(10, 59))

    def record(self, cls, tracked, note, expect):
        self.manifest['defects'].append(
            {'id': f'D{len(self.manifest["defects"])+1:03d}', 'cls': cls,
             'tracked': bool(tracked), 'section': self.section_no, 'note': note, 'expect': expect})
        self.manifest['counts'][cls] = self.manifest['counts'].get(cls, 0) + 1

    # -- text helpers -------------------------------------------------------
    def fill(self, tmpl):
        return tmpl.format(a=self.rng.choice(C.ACTIVITIES), n=self.rng.randint(12, 240),
                           m=f"{self.rng.choice(['March','April','May','June'])} update")

    def corrupt_text(self, t):
        """Inject tier-rate spelling/grammar errors into ordinary prose; records nothing (these are
        quality errors the conformer does not claim to fix — they are measured separately)."""
        words = t.split(' ')
        for i, w in enumerate(words):
            lw = w.lower().strip('.,;:')
            if lw in MISSPELL and self.rng.random() < self.cfg['spelling']:
                words[i] = w.replace(lw, MISSPELL[lw]); self.manifest.setdefault('spelling', 0)
                self.manifest['spelling'] = self.manifest.get('spelling', 0) + 1
        t = ' '.join(words)
        for a, b in GRAMMAR:
            if a in t and self.rng.random() < self.cfg['grammar']:
                t = t.replace(a, b, 1); self.manifest['grammar'] = self.manifest.get('grammar', 0) + 1
        return t

    def roll_defect(self):
        return self.rng.random() < self.cfg['extra_defects']

    # -- block emitters -----------------------------------------------------
    def heading(self, text, level=1):
        if level == 1:
            self.section_no += 1
        p = self.doc.add_paragraph(text, style=f'Heading{level}')
        return p

    def para(self, text, style='NumberedParagraph', clean_style=None, allow_defect=True):
        """A body paragraph. May be emitted with a foreign style (classify defect) and/or direct
        formatting (strip_direct defect) depending on tier."""
        text = self.corrupt_text(text)
        defect_style = allow_defect and self.roll_defect()
        if defect_style:
            lib.ensure_foreign_style(self.doc, 'FirmBody', 'Firm Body')
            p = self.doc.add_paragraph(text, style='Normal')
            self.record('classify_body', False, text[:40], 'map foreign/Normal -> NumberedParagraph')
        else:
            p = self.doc.add_paragraph(text, style=style)
        if allow_defect and self.roll_defect():
            lib.add_direct_rpr(p.runs[0] if p.runs else p.add_run(''),
                               '<w:rFonts w:ascii="Calibri"/><w:sz w:val="20"/><w:color w:val="FF0000"/>')
            self.record('strip_direct', False, text[:40], 'remove direct run formatting')
        return p

    def maybe_track(self, p, force=False):
        """With tier probability, mark the paragraph's last run a tracked insertion by an author."""
        if not force and self.rng.random() > 0.12 * self.cfg['tracked_density']:
            return
        if not p.runs:
            return
        a, _ = self.author()
        lib.wrap_run_ins(p.runs[-1], self.ids, a, self.date())
        self.manifest['tracked']['ins'] += 1

    def maybe_comment(self, p):
        if self.rng.random() > 0.06 * self.cfg['tracked_density'] or not p.runs:
            return
        a, ini = self.author()
        try:
            lib.add_comment(self.doc, p.runs[0], self.rng.choice([
                "Please confirm the source for this figure.",
                "Consider tightening this opinion.",
                "Cross-check against the window analysis.",
                "Is this the correct data date?"]), a, ini)
            self.manifest['comments'] += 1
        except Exception:
            pass

    # -- lists ---------------------------------------------------------------
    def bullet(self, text, sentence=False, defect=None):
        text = self.corrupt_text(text)
        if defect == 'foreign':
            p = self.doc.add_paragraph(text, style='List Paragraph')
            self._num(p, bullet=True)
            self.record('classify_bullet', False, text[:40], 'map ListParagraph bullet -> ListBullet*')
        elif defect == 'level':
            p = self.doc.add_paragraph(text, style='NumberedParagraphL2')
            self.record('level_fix', False, text[:40], 'promote L2 under numbered para -> L1')
        else:
            p = self.doc.add_paragraph(text, style='Listbulletasasentence' if sentence else 'ListBullet')
        return p

    def _num(self, p, bullet=False):
        ppr = p._p.get_or_add_pPr()
        ppr.append(parse_xml('<w:numPr %s><w:ilvl w:val="0"/><w:numId w:val="%d"/></w:numPr>'
                             % (nsdecls("w"), 1 if bullet else 2)))

    def quote(self, text, split=False):
        if split and self.roll_defect():
            words = text.split(' '); mid = len(words) // 2
            a = ' '.join(words[:mid]).rstrip('.'); b = ' '.join(words[mid:])
            self.doc.add_paragraph(a, style='ExcerptorQuote')
            self.doc.add_paragraph(b, style='ExcerptorQuote')
            self.record('pdf_linesplit', False, a[:40], 'merge PDF line-split excerpts (#1)')
        else:
            self.doc.add_paragraph(text, style='ExcerptorQuote')

    def typo_para(self, tracked=False):
        raw = ('The Engineer stated that the works were "substantially complete" -- a view I do not '
               'share -- and fixed the milestone at 05 June with a 3" tolerance.')
        p = self.doc.add_paragraph(raw, style='NumberedParagraph')
        self.record('typography', tracked, raw[:40], 'smart quotes, en dash, date, inch mark')
        if tracked and p.runs:
            a, _ = self.author(); lib.wrap_run_ins(p.runs[-1], self.ids, a, self.date())
            self.manifest['tracked']['ins'] += 1
        return p

    # -- tables -------------------------------------------------------------
    def _ensure_litable(self):
        if not lib.has_style(self.doc, 'LITable'):
            from conformer.engine import LITABLE
            self.doc.styles.element.append(
                parse_xml(LITABLE.replace('<w:style ', '<w:style %s ' % nsdecls("w"), 1)))

    def data_table(self, clean=True, empty_col=False):
        header = ["Window", "Data date", "Forecast finish", "Slippage (days)"]
        t = self.doc.add_table(rows=6, cols=4 + (1 if empty_col else 0))
        for ci, h in enumerate(header):
            t.cell(0, ci).paragraphs[0].add_run(h)
        for ri in range(1, 6):
            vals = ["W-%d" % ri, "%02d/26" % ri, "Q%d-27" % (ri % 4 + 1), str(self.rng.randint(0, 40))]
            for ci, v in enumerate(vals):
                t.cell(ri, ci).paragraphs[0].add_run(v)
        if clean and not empty_col:
            self._ensure_litable(); t.style = 'LITable'
        else:
            t._tbl.tblPr.append(parse_xml(
                '<w:tblBorders %s><w:top w:val="single" w:sz="12" w:space="0" w:color="FF0000"/>'
                '<w:bottom w:val="single" w:sz="12" w:space="0" w:color="FF0000"/></w:tblBorders>'
                % nsdecls("w")))
            self.record('table_style', False, 'window table', 'set table to LITable style')
            if empty_col:
                self.record('table_empty_col', False, 'window table', 'drop empty column (#7)')
        return t

    def wrapper_table(self):
        t = self.doc.add_table(rows=1, cols=1)
        c = t.cell(0, 0)
        c.paragraphs[0].add_run("This paragraph was wrapped inside a single-cell layout table by a "
                                "prior word processor and should be unwrapped.")
        c.add_paragraph("A second wrapped paragraph continues the same passage.")
        self.record('wrapper_table', False, 'single-cell wrapper', 'unwrap wrapper table (#3)')
        return t

    # -- figures ------------------------------------------------------------
    def figure(self, image, title, floating=False, wrong_number=False, tof_mismatch=False,
               caption_literal=False, tracked=False):
        self.fig_seq[self.section_no] = self.fig_seq.get(self.section_no, 0) + 1
        seq = self.fig_seq[self.section_no]
        disp_sec = self.section_no + (1 if wrong_number else 0)
        if wrong_number:
            self.record('figure_numbering', False, title[:30], 'audit flags caption numbering drift')
        label = "Figure %d-%d" % (disp_sec, seq)
        name = "_Ref_F%d%d%d" % (disp_sec, seq, self.rng.randint(100, 999))
        ip = self.doc.add_paragraph(style='SpacebehindafteraGraphic')
        run = ip.add_run()
        try:
            run.add_picture(os.path.join(ASSETS, image), width=Inches(5.5))
        except Exception:
            run.add_text('[image]')
        if floating:
            self._make_floating(ip)
            self.record('floating_image', tracked, title[:30], 'convert floating image to inline (#5)')
        caption_text = "%s: %s" % (label, title)
        if caption_literal:
            cp = self.doc.add_paragraph(caption_text, style='Caption')
            self.record('caption_literal', tracked, caption_text[:40], 'rebuild caption as fields (#8a)')
        else:
            cp = self.doc.add_paragraph(style='Caption')
            b0, b1 = lib.bookmark(name, self.new_bookmark())
            inner = (b0 + '<w:r><w:t xml:space="preserve">Figure </w:t></w:r>'
                     + lib.field_runs('STYLEREF 1 \\s', str(disp_sec))
                     + '<w:r><w:t xml:space="preserve">-</w:t></w:r>'
                     + lib.field_runs('SEQ Figure \\* ARABIC \\s 1', str(seq))
                     + '<w:r><w:t xml:space="preserve">: %s</w:t></w:r>' % title + b1)
            lib.set_para_xml(cp, inner)
        if tracked and cp.runs:
            a, _ = self.author(); lib.wrap_run_ins(cp.runs[-1], self.ids, a, self.date())
            self.manifest['tracked']['ins'] += 1
        self.fig_bookmarks.append((name, title, disp_sec, seq))
        shown = title + (" (revised)" if tof_mismatch else "")
        if tof_mismatch:
            self.record('tof_mismatch', False, title[:30], 'audit flags ToF title mismatch')
        self.tof_entries.append((name, "Figure %d-%d: %s" % (disp_sec, seq, shown)))
        return ip, cp

    def _make_floating(self, p):
        for inline in list(p._p.iter(qn('wp:inline'))):
            anchor = parse_xml(
                '<wp:anchor %s distT="0" distB="0" distL="114300" distR="114300" simplePos="0" '
                'relativeHeight="2" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">'
                '<wp:simplePos x="0" y="0"/>'
                '<wp:positionH relativeFrom="column"><wp:posOffset>0</wp:posOffset></wp:positionH>'
                '<wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV>'
                '</wp:anchor>' % nsdecls("wp"))
            for ch in list(inline):
                anchor.append(ch)
            anchor.append(parse_xml('<wp:wrapNone %s/>' % nsdecls("wp")))
            inline.getparent().replace(inline, anchor)
            break

    def heading_body_merge(self):
        p = self.doc.add_paragraph(style='Heading2')
        p.add_run("Basis of the Delay Assessment")
        p.add_run("  ")
        p.add_run("This body sentence was mistakenly merged into the heading paragraph and must be "
                  "split back into ordinary numbered text.")
        self.record('heading_body_merge', False, 'Basis of the Delay', 'split heading from body (#6)')
        return p

    def footnote(self, p, defect=False, tracked=False):
        fid = self.fnid; self.fnid += 1
        text = self.fill(self.rng.choice(C.FOOTNOTES))
        p._p.append(parse_xml(
            '<w:r %s><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>'
            '<w:footnoteReference w:id="%d"/></w:r>' % (nsdecls("w"), fid)))
        self.footnotes.append((fid, text, defect, tracked))
        if defect:
            self.record('footnote_style', tracked, text[:30], 'set footnote to FootnoteText style')

    def stray_empty(self):
        self.doc.add_paragraph('', style='NumberedParagraph')
        self.record('empty_para', False, '(empty)', 'delete empty numbered paragraph (#2)')

    def page_break_para(self):
        p = self.doc.add_paragraph(style='NumberedParagraph')
        p.add_run().add_break(docx.enum.text.WD_BREAK.PAGE)
        self.record('page_break', False, '(page break)', 'remove manual page-break paragraph (#4)')

    # -- front matter -------------------------------------------------------
    def front_matter(self):
        d = self.doc
        d.add_paragraph("PRIVILEGED AND CONFIDENTIAL", style='PRIVCONFSTATEMENT')
        d.add_paragraph("EXPERT REPORT ON DELAY", style='Title')
        d.add_paragraph("In the matter of %s" % C.CASE, style='Subtitle')
        for line in ["%s" % C.PROJECT.title(), "Prepared for %s" % C.COUNSEL,
                     "On behalf of %s" % C.CONTRACTOR, "By %s, %s" % (C.EXPERT, C.FIRM),
                     "This report is a DRAFT prepared for review and is subject to revision."]:
            d.add_paragraph(line, style='BodyText')
        p = d.add_paragraph(style='NumberedParagraph'); p.add_run().add_break(docx.enum.text.WD_BREAK.PAGE)

        # Table of Contents (field with cached entries)
        d.add_paragraph("TABLE OF CONTENTS", style='TOCListTitle')
        toc = d.add_paragraph(style='TOC1')
        lib.set_para_xml(toc, lib.field_runs('TOC \\o "1-3" \\h \\z \\u', "Right-click to update field"))

        # List of Figures / Tables / Exhibits / Attachments and acronyms are filled after the body,
        # once figures/tables exist; we insert placeholders and patch later. For simplicity we build
        # them here from what will be generated (front matter is emitted last in build()).

    def list_of_figures(self):
        self.doc.add_paragraph("LIST OF FIGURES", style='TOCListTitle')
        for anchor, disp in self.tof_entries:
            p = self.doc.add_paragraph(style='TableofFigures')
            lib.set_para_xml(p, '<w:hyperlink %s w:anchor="%s"><w:r><w:t xml:space="preserve">%s</w:t>'
                             '</w:r><w:r><w:tab/></w:r><w:r><w:t>%d</w:t></w:r></w:hyperlink>'
                             % (nsdecls("w"), anchor, disp, self.rng.randint(3, 60)))

    def list_block(self, title, items, sentence=False):
        self.doc.add_paragraph(title, style='TOCListTitle')
        for i, it in enumerate(items, 1):
            p = self.doc.add_paragraph(style='ListBullet')
            p.add_run("%d.  %s" % (i, it))

    def acronyms(self):
        self.doc.add_paragraph("GLOSSARY OF ABBREVIATIONS", style='TOCListTitle')
        t = self.doc.add_table(rows=len(C.ACRONYMS), cols=2)
        self._ensure_litable(); t.style = 'LITable'
        for ri, (ab, full) in enumerate(C.ACRONYMS):
            t.cell(ri, 0).paragraphs[0].add_run(ab)
            t.cell(ri, 1).paragraphs[0].add_run(full)

    # -- landscape section --------------------------------------------------
    def landscape_wide_table(self):
        sec = self.doc.add_section(docx.enum.section.WD_SECTION.NEW_PAGE)
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = sec.page_height, sec.page_width
        self.doc.add_paragraph("Appendix A — Delay Ledger (landscape)", style='Heading1')
        t = self.doc.add_table(rows=6, cols=7)
        hdr = ["Event", "Start", "Finish", "Owner", "Excusable", "Compensable", "Net days"]
        for ci, h in enumerate(hdr):
            t.cell(0, ci).paragraphs[0].add_run(h)
        for ri in range(1, 6):
            for ci in range(7):
                t.cell(ri, ci).paragraphs[0].add_run(str(self.rng.randint(0, 30)) if ci >= 4 else "E%d" % ri)
        self.record('section_landscape', False, 'Appendix A', 'restore portrait section after landscape')
        # a following portrait section so fix_sections has a landscape-then-portrait boundary
        self.doc.add_section(docx.enum.section.WD_SECTION.NEW_PAGE)

    # -- body ---------------------------------------------------------------
    def body(self):
        for title, key in C.SECTIONS:
            h = self.heading(title, 1)
            lib.wrap_run_ins(h.runs[-1], self.ids, *self._track()) if self.rng.random() < 0.1 else None
            self._section_body(key)

    def _track(self):
        a, _ = self.author(); self.manifest['tracked']['ins'] += 1
        return a, self.date()

    _BODY_IMAGES = ['gantt.png', 'scurve.png', 'bar_delay.png', 'float_hist.png', 'window_table.png']

    def _section_body(self, key):
        pools = {'method': C.METHOD, 'background': C.BACKGROUND, 'opinions': C.OPINION,
                 'conclusions': C.OPINION}.get(key, C.FINDING)
        n_sub = self.rng.randint(2, 3)
        for sub in range(n_sub):
            self.doc.add_paragraph(self.fill(self.rng.choice(
                ["Analysis of the {a} Works", "The {a} Window", "Findings on {a}",
                 "Assessment of the {a} Delay", "The Record Concerning {a}"])), style='Heading2')
            for i in range(self.rng.randint(5, 9)):
                txt = (self.fill(self.rng.choice(pools)) + " " + self.fill(self.rng.choice(C.FINDING))
                       + " " + self.fill(self.rng.choice(C.FINDING)))
                p = self.para(txt)
                if self.rng.random() < 0.35:
                    self.footnote(p, defect=self.roll_defect(), tracked=self.rng.random() < 0.2)
                self.maybe_track(p); self.maybe_comment(p)
            # a bullet list
            for b in range(self.rng.randint(2, 4)):
                self.bullet(self.fill(self.rng.choice(C.FINDING)), sentence=self.rng.random() < 0.5,
                            defect='foreign' if self.roll_defect() else None)
            # a block quote (occasionally a PDF line split)
            self.quote(self.rng.choice(C.QUOTE), split=True)
            # a clean figure or table in the flow
            if self.rng.random() < 0.6:
                self.figure(self.rng.choice(self._BODY_IMAGES),
                            self.fill(self.rng.choice(["As-planned versus as-built {a} schedule",
                                                       "Cumulative progress on {a}",
                                                       "Float erosion across the {a} window"])))
            if self.rng.random() < 0.4:
                self.data_table(clean=not self.roll_defect())

    # -- guaranteed coverage: force one of every class, tracked + non-tracked
    def guaranteed_coverage(self):
        self.heading("Comprehensive Element Coverage", 1)
        # classify + strip_direct (non-tracked already appear in body; force tracked ones)
        lib.ensure_foreign_style(self.doc, 'FirmBody', 'Firm Body')
        p = self.doc.add_paragraph("This body paragraph uses a foreign firm style and carries a "
                                   "tracked insertion, so its style is conformed while the edit is "
                                   "preserved.", style='Normal')
        self.record('classify_body', True, 'foreign+tracked', 'map to NumberedParagraph, preserve edit')
        lib.wrap_run_ins(p.runs[-1], self.ids, *self._track())
        p2 = self.doc.add_paragraph("Direct-formatted paragraph with a tracked deletion.",
                                    style='NumberedParagraph')
        lib.add_direct_ppr(p2, '<w:spacing w:before="240" w:after="240"/><w:ind w:left="720"/>')
        self.record('strip_direct', True, 'direct+tracked', 'strip direct formatting, preserve edit')
        if p2.runs:
            lib.wrap_run_del(p2.runs[0], self.ids, *self._track()[:1] + (self.date(),))
            self.manifest['tracked']['del'] += 1
        # bullets: foreign (non-tracked) + level fix
        self.bullet("A bulleted item on a foreign list style.", defect='foreign')
        self.doc.add_paragraph("A numbered lead-in paragraph introducing sub-items:",
                               style='NumberedParagraph')
        self.bullet("A sub-item that started at level two under a numbered paragraph.", defect='level')
        # typography, tracked + non-tracked
        self.typo_para(tracked=False)
        self.typo_para(tracked=True)
        # pdf line split
        old = self.cfg['extra_defects']; self.cfg['extra_defects'] = 1.0
        self.quote("The tribunal held that the extension of time was validly claimed and that the "
                   "notice provisions had been substantially complied with by the contractor.", split=True)
        self.cfg['extra_defects'] = old
        # empty para + page break + heading/body merge
        self.stray_empty(); self.page_break_para(); self.heading_body_merge()
        # tables: style defect + empty column + wrapper
        self.data_table(clean=False)
        self.data_table(clean=False, empty_col=True)
        self.wrapper_table()
        # figures: floating (tracked), literal caption (tracked), numbering drift, ToF mismatch, clean
        self.figure('gantt.png', 'As-planned versus as-built schedule', floating=True, tracked=True)
        self.figure('scurve.png', 'Planned versus actual cumulative progress', caption_literal=True,
                    tracked=True)
        self.figure('bar_delay.png', 'Delay days by causal category', wrong_number=True)
        self.figure('float_hist.png', 'Distribution of total float', tof_mismatch=True)
        self.figure('window_table.png', 'Forecast completion slippage by update')   # clean
        self.figure('site_photo.png', 'General view of the works')                  # clean
        # cross-references (literal, one tracked-adjacent) targeting the clean figures
        target = self.fig_bookmarks[-2][0]
        p = self.doc.add_paragraph("As shown in Figure %d-%d and discussed in Section 7, the slippage "
                                   "accumulated across the windows." % (self.fig_bookmarks[-2][2],
                                   self.fig_bookmarks[-2][3]), style='NumberedParagraph')
        self.record('xref_literal', False, 'literal xref', 'rebuild literal cross-reference as REF (#8b)')
        pt = self.doc.add_paragraph("Refer also to Figure %d-%d for the causal breakdown." %
                                    (self.fig_bookmarks[-4][2], self.fig_bookmarks[-4][3]),
                                    style='NumberedParagraph')
        self.record('xref_literal', True, 'literal xref tracked-adjacent', 'rebuild REF (#8b), flag review')
        if pt.runs:
            lib.wrap_run_ins(pt.runs[-1], self.ids, *self._track())
        # a pPrChange + rPrChange formatting revision (must be preserved)
        pc = self.doc.add_paragraph("This paragraph carries a formatting revision snapshot.",
                                    style='NumberedParagraph')
        lib.add_ppr_change(pc, self.ids, self.author()[0], self.date(),
                           '<w:pStyle w:val="BodyText"/><w:jc w:val="both"/>')
        self.manifest['tracked']['ppr_change'] += 1
        if pc.runs:
            lib.add_rpr_change(pc.runs[0], self.ids, self.author()[0], self.date(), '<w:i/>')
            self.manifest['tracked']['rpr_change'] += 1
        # a wholly-inserted paragraph (paragraph-mark insertion)
        ip = self.doc.add_paragraph("This entire paragraph was inserted as a tracked change by a "
                                    "reviewer and must survive conforming.", style='NumberedParagraph')
        lib.mark_paragraph_inserted(ip, self.ids, *self._track())
        self.manifest['tracked']['para_inserted'] += 1
        # footnote with foreign style, tracked
        fp = self.doc.add_paragraph("A paragraph bearing a footnote whose style must be conformed.",
                                    style='NumberedParagraph')
        self.footnote(fp, defect=True, tracked=True)

    def signature(self):
        self.doc.add_paragraph("DECLARATION", style='Heading1')
        self.doc.add_paragraph("I confirm that this report sets out my independent opinion and that I "
                               "understand my duty to the Tribunal.", style='NumberedParagraph')
        for line in ["", "", "Signed:", C.EXPERT, C.FIRM, "Date:  ___________"]:
            self.doc.add_paragraph(line, style='BodyText')

    # -- assembly + save ----------------------------------------------------
    def build(self):
        self.front_matter()
        self.body()
        self.guaranteed_coverage()
        self.landscape_wide_table()
        self.signature()
        # front-matter lists that depend on generated content: append at end, then reorder to front
        pre = len(self.doc.element.body)
        self.list_of_figures()
        self.list_block("LIST OF EXHIBITS", C.EXHIBITS)
        self.list_block("LIST OF ATTACHMENTS", C.ATTACHMENTS)
        self.acronyms()
        self._move_to_front(pre)
        return self

    def _move_to_front(self, from_index):
        """Move the trailing list blocks to just after the TOC (front matter)."""
        body = self.doc.element.body
        children = list(body)
        tail = children[from_index:]
        # find insertion point: after the TOC1 paragraph
        anchor = None
        for ch in children:
            if ch.tag == qn('w:p'):
                ppr = ch.find(qn('w:pPr'))
                if ppr is not None:
                    st = ppr.find(qn('w:pStyle'))
                    if st is not None and st.get(qn('w:val')) == 'TOC1':
                        anchor = ch; break
        if anchor is None:
            return
        for el in tail:
            body.remove(el)
        for el in reversed(tail):
            anchor.addnext(el)

    def save(self, path):
        self.doc.save(path)
        self._inject_footnotes(path)
        self._finalize_manifest()

    def _inject_footnotes(self, path):
        if not self.footnotes:
            return
        tmp = path + '.tmp'
        zin = zipfile.ZipFile(path)
        fn_xml = None
        for n in zin.namelist():
            if n == 'word/footnotes.xml':
                fn_xml = zin.read(n).decode('utf8')
        defs = ''
        for fid, text, defect, tracked in self.footnotes:
            style = 'CommentText' if defect else 'FootnoteText'
            run = '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>' \
                  '<w:r><w:t xml:space="preserve"> %s</w:t></w:r>' % text
            if tracked:
                run = ('<w:ins w:id="%d" w:author="%s" w:date="%s">%s</w:ins>'
                       % (self.ids.next(), self.author()[0], self.date(),
                          '<w:r><w:t xml:space="preserve"> %s</w:t></w:r>' % text))
                run = ('<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>'
                       + run)
            defs += ('<w:footnote w:id="%d"><w:p><w:pPr><w:pStyle w:val="%s"/></w:pPr>%s</w:p>'
                     '</w:footnote>' % (fid, style, run))
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

    def _finalize_manifest(self):
        m = self.manifest
        m['total_defects'] = len(m['defects'])
        m['tracked_total'] = sum(m['tracked'].values())
        m['spelling_errors'] = m.get('spelling', 0)
        m['grammar_errors'] = m.get('grammar', 0)
        m['figures'] = len(self.fig_bookmarks)
        m['expected_preservation'] = 'clean'


def build_tier(tier):
    os.makedirs(OUT, exist_ok=True)
    r = Report(tier).build()
    docx_path = os.path.join(OUT, 'synthetic_report_%spct.docx' % tier)
    r.save(docx_path)
    man_path = os.path.join(OUT, 'synthetic_report_%spct_manifest.json' % tier)
    with open(man_path, 'w', encoding='utf8') as fh:
        json.dump(r.manifest, fh, indent=2)
    return docx_path, man_path, r.manifest


if __name__ == '__main__':
    tiers = sys.argv[1:] or ['90', '70', '25']
    for t in tiers:
        dp, mp, man = build_tier(t)
        print('%s%% -> %s  (%d defects, %d tracked, %d comments, %d figures, %d spelling)'
              % (t, os.path.basename(dp), man['total_defects'], man['tracked_total'],
                 man['comments'], man['figures'], man.get('spelling_errors', 0)))
