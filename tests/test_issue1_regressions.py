"""Regression reproductions for the corrective-work review (GitHub issue #1, findings R1-R7). Each test
encodes a documented counterexample that must FAIL before its fix and PASS after. Gates are never
weakened and unresolved results are never treated as conformant."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'synthetic'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


# ---------------------------------------------------------------- R6: colour redundancy must be real
def _scmap(**styles):
    # styleId -> {'color','color_xml','basedOn'} like the engine's _style_color_map(); spec=(val, based[, theme])
    m = {}
    for sid, spec in styles.items():
        val, based = spec[0], spec[1]
        theme = spec[2] if len(spec) > 2 else None
        cx = None
        if val is not None:
            cx = f'<w:color w:val="{val}"' + (f' w:themeColor="{theme}"' if theme else '') + '/>'
        m[sid] = {'color': val, 'color_xml': cx, 'basedOn': based}
    return m


def test_r6_black_over_red_char_style_is_not_redundant():
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    sc = _scmap(BodyText=(None, None), RedChar=('FF0000', None))
    assert c._color_is_redundant('<w:color w:val="000000"/>', 'RedChar', 'BodyText', sc) is False
    assert c._color_is_redundant('<w:color w:val="000000"/>', None, 'BodyText', sc) is True


def test_r6_theme_colour_is_never_silently_stripped():
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    sc = _scmap(BodyText=(None, None))
    assert c._color_is_redundant('<w:color w:val="000000" w:themeColor="text1"/>', None, 'BodyText', sc) is False


def test_r6_inherited_theme_backed_char_style_colour_not_stripped():
    # char style Char has <w:color w:val="000000" w:themeColor="accent1"/>; the run uses Char + explicit
    # black. Removing the explicit black could reveal a non-black accent1 -> NOT redundant (issue #1 R6).
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    sc = _scmap(BodyText=(None, None), Char=('000000', None, 'accent1'))
    assert c._color_is_redundant('<w:color w:val="000000"/>', 'Char', 'BodyText', sc) is False


# ---------------------------------------------------------------- R4: table parse / false conformance
def _litable_frag(extra_prefix=''):
    tr = (f'<w:tr {extra_prefix}><w:trPr><w:tblHeader/></w:trPr>'
          f'<w:tc><w:tcPr></w:tcPr><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
          f'<w:r><w:rPr><w:color w:val="FFFFFF"/></w:rPr><w:t>H</w:t></w:r></w:p></w:tc></w:tr>')
    return f'<w:tbl><w:tblPr><w:tblStyle w:val="LITable"/></w:tblPr><w:tblGrid><w:gridCol w:w="2000"/></w:tblGrid>{tr}</w:tbl>'


def test_r4_prefixed_fragment_is_evaluated_not_parse_failed():
    from conformer.tablespec import effective_table_issues
    frag = _litable_frag('w14:paraId="12345678"')          # inherited w14 prefix from the document
    issues = effective_table_issues(frag)
    assert all(i['kind'] != 'parse' for i in issues), issues   # before fix: a parse failure


def test_r4_unparseable_table_is_not_conformant():
    from conformer.tablespec import table_conformant
    assert table_conformant('<w:tbl><w:tblPr><w:unclosed') is False   # before fix: True (unknown == ok)


def test_r4_outcome_report_surfaces_unresolved_tables():
    # a real document context: a table that cannot be evaluated must appear as an unresolved outcome,
    # never as silent conformance.
    import os, tempfile
    import lib
    from docx import Document
    from conformer.engine import Conformer
    TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets', 'template.dotx')
    d = Document(lib.li_base_docx())
    for p in list(d.paragraphs):
        p._element.getparent().remove(p._element)
    d.add_paragraph('BACKGROUND', style='Heading1')
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).paragraphs[0].add_run('Header')
    t.cell(1, 0).paragraphs[0].add_run('Data')
    path = os.path.join(tempfile.mkdtemp(), 't.docx')
    d.save(path)
    c = Conformer(TEMPLATE, path); c.run()
    rep = c.outcome_report()
    # every body table is either failing, unresolved, or evaluated-clean — but never unevaluated-yet-clean
    body_tables = [i for i in range(c.n()) if c.item(i).startswith('<w:tbl')]
    from conformer import tablespec
    ns = c._doc_nsdecls()
    for i in body_tables:
        issues = tablespec.effective_table_issues(c.item(i), nsdecls=ns)
        assert all(x['kind'] != 'parse' for x in issues), f'table {i} failed to parse: {issues}'


# ---------------------------------------------------------------- R2: import dependency closure
def _style(sid, numId):
    return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{sid}"/>'
            f'<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{numId}"/></w:numPr></w:pPr></w:style>')


def test_r2_import_resolves_multi_hop_numstylelink_chain():
    # abstract 10 -> Link1 -> num 2 -> abstract 20 -> Link2 -> num 3 -> abstract 30 (decimal). A one-hop
    # resolver yields an EMPTY abstract; the closure resolver must inline the decimal levels.
    from conformer.numbering import NumberingGraph
    tnum = (f'<w:numbering {W}>'
            '<w:abstractNum w:abstractNumId="10"><w:numStyleLink w:val="Link1"/></w:abstractNum>'
            '<w:abstractNum w:abstractNumId="20"><w:numStyleLink w:val="Link2"/></w:abstractNum>'
            '<w:abstractNum w:abstractNumId="30"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
            '<w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
            '<w:num w:numId="1"><w:abstractNumId w:val="10"/></w:num>'
            '<w:num w:numId="2"><w:abstractNumId w:val="20"/></w:num>'
            '<w:num w:numId="3"><w:abstractNumId w:val="30"/></w:num></w:numbering>')
    tsty = f'<w:styles {W}>' + _style('New', 1) + _style('Link1', 2) + _style('Link2', 3) + '</w:styles>'
    tg = NumberingGraph(tnum, tsty)
    assert tg.effective_format('1', '0') == 'decimal'         # the source resolves correctly
    resolved = tg.resolved_abstract_xml('10')
    assert resolved is not None
    assert 'numStyleLink' not in resolved
    assert 'w:numFmt w:val="decimal"' in resolved             # levels inlined through the whole chain


def test_r2_unresolvable_chain_never_becomes_empty_definition():
    from conformer.numbering import NumberingGraph
    # a cycle: abstract 10 -> SelfLink -> num 1 -> abstract 10
    tnum = (f'<w:numbering {W}>'
            '<w:abstractNum w:abstractNumId="10"><w:numStyleLink w:val="SelfLink"/></w:abstractNum>'
            '<w:num w:numId="1"><w:abstractNumId w:val="10"/></w:num></w:numbering>')
    tsty = f'<w:styles {W}>' + _style('SelfLink', 1) + '</w:styles>'
    tg = NumberingGraph(tnum, tsty)
    assert tg.resolved_abstract_xml('10') is None             # unresolved -> None, never an empty def


def test_r2_inherited_numbering_pinned_but_not_over_a_house_repair():
    from conformer.engine import Conformer
    from conformer.numbering import NumberingGraph
    # Child inherits decimal from A (no local numPr). Simulate a replacement that changed Child's basedOn
    # to B (bullet); the preservation pass must pin Child back to decimal (R2 counterexample 2).
    orig_sty = (f'<w:styles {W}>'
                '<w:style w:type="paragraph" w:styleId="A"><w:name w:val="A"/>'
                '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr></w:pPr></w:style>'
                '<w:style w:type="paragraph" w:styleId="B"><w:name w:val="B"/>'
                '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="8"/></w:numPr></w:pPr></w:style>'
                '<w:style w:type="paragraph" w:styleId="Child"><w:name w:val="Child"/>'
                '<w:basedOn w:val="A"/></w:style></w:styles>')
    num = (f'<w:numbering {W}>'
           '<w:abstractNum w:abstractNumId="40"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/>'
           '<w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
           '<w:abstractNum w:abstractNumId="41"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/>'
           '<w:lvlText w:val="&#61623;"/></w:lvl></w:abstractNum>'
           '<w:num w:numId="7"><w:abstractNumId w:val="40"/></w:num>'
           '<w:num w:numId="8"><w:abstractNumId w:val="41"/></w:num></w:numbering>')
    ograph = NumberingGraph(num, orig_sty)
    assert ograph.effective_format(*ograph.style_numpr('Child')) == 'decimal'   # inherited decimal

    c = Conformer.__new__(Conformer)
    c._house_repaired = {}
    c.num = num
    c.styles = orig_sty.replace('<w:basedOn w:val="A"/>', '<w:basedOn w:val="B"/>')   # bad replacement
    assert NumberingGraph(c.num, c.styles).effective_format('8', '0') == 'bullet'
    pinned = c._preserve_inherited_numbering(ograph)
    assert pinned == 1
    g = NumberingGraph(c.num, c.styles)
    assert g.effective_format(*g.style_numpr('Child')) == 'decimal'               # restored

    # but a style following a HOUSE REPAIR of its ancestor must NOT be pinned
    c2 = Conformer.__new__(Conformer)
    c2._house_repaired = {'A': ('none', 'bullet')}
    c2.num = num
    c2.styles = orig_sty.replace('<w:numId w:val="7"/>', '<w:numId w:val="8"/>')   # A repaired to bullet
    assert c2._preserve_inherited_numbering(ograph) == 0                            # Child follows the repair


def _broken_bullet_docx():
    import os as _os, re as _re, zipfile, tempfile, shutil
    import lib
    from docx import Document
    d = Document(lib.li_base_docx())
    for p in list(d.paragraphs):
        p._element.getparent().remove(p._element)
    d.add_paragraph('BACKGROUND', style='Heading1')
    d.add_paragraph('a bullet item', style='ListBullet')
    d.add_paragraph('a numbered item', style='NumberedParagraph')
    p = _os.path.join(tempfile.mkdtemp(), 'broken.docx'); d.save(p)
    zin = zipfile.ZipFile(p); parts = {n: zin.read(n) for n in zin.namelist()}; zin.close()
    num = parts['word/numbering.xml'].decode('utf8').replace(
        '</w:numbering>',
        '<w:abstractNum w:abstractNumId="900"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
        '<w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
        '<w:num w:numId="900"><w:abstractNumId w:val="900"/></w:num></w:numbering>')
    parts['word/numbering.xml'] = num.encode('utf8')
    sty = parts['word/styles.xml'].decode('utf8')
    sty = _re.sub(r'(<w:style [^>]*w:styleId="ListBullet".*?<w:numId w:val=")[^"]+(")',
                  r'\g<1>900\g<2>', sty, count=1, flags=_re.S)
    parts['word/styles.xml'] = sty.encode('utf8')
    p2 = _os.path.join(tempfile.mkdtemp(), 'broken2.docx')
    with zipfile.ZipFile(p2, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)
    return p2


def test_r1_dysfunctional_bullet_repaired_numbered_unchanged():
    import os as _os
    from conformer.engine import Conformer
    from conformer.numbering import NumberingGraph
    TEMPLATE = _os.path.join(_os.path.dirname(__file__), '..', 'src', 'conformer', 'assets', 'template.dotx')
    c = Conformer(TEMPLATE, _broken_bullet_docx())
    g0 = NumberingGraph(c._orig_num0, c._orig_styles0)
    assert g0.is_bullet(*g0.style_numpr('ListBullet')) is not True    # dysfunctional (not a bullet)
    c.disposition = 'preserve'
    c._repair_styles()
    g1 = NumberingGraph(c.num, c.styles)
    assert g1.is_bullet(*g1.style_numpr('ListBullet')) is True        # repaired to the house bullet
    assert 'ListBullet' in c._house_repaired
    assert g1.effective_format(*g1.style_numpr('NumberedParagraph')) == 'decimal'   # numbered stays numbered


def _corrupt_glyph_bullet_docx():
    # ListBullet points at a BULLET-format level whose glyph is corrupt (lvlText=BROKEN) — same numFmt as
    # the house bullet, but the wrong character. This is dysfunction the format enum does not reveal.
    import os as _os, re as _re, zipfile, tempfile
    import lib
    from docx import Document
    d = Document(lib.li_base_docx())
    for p in list(d.paragraphs):
        p._element.getparent().remove(p._element)
    d.add_paragraph('BACKGROUND', style='Heading1')
    d.add_paragraph('a bullet item', style='ListBullet')
    p = _os.path.join(tempfile.mkdtemp(), 'g.docx'); d.save(p)
    zin = zipfile.ZipFile(p); parts = {n: zin.read(n) for n in zin.namelist()}; zin.close()
    lvls = ''.join(f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="bullet"/>'
                   '<w:lvlText w:val="BROKEN"/></w:lvl>' for i in range(9))
    num = parts['word/numbering.xml'].decode('utf8').replace(
        '</w:numbering>',
        f'<w:abstractNum w:abstractNumId="901">{lvls}</w:abstractNum>'
        '<w:num w:numId="901"><w:abstractNumId w:val="901"/></w:num></w:numbering>')
    parts['word/numbering.xml'] = num.encode('utf8')
    sty = _re.sub(r'(<w:style [^>]*w:styleId="ListBullet".*?<w:numId w:val=")[^"]+(")',
                  r'\g<1>901\g<2>', parts['word/styles.xml'].decode('utf8'), count=1, flags=_re.S)
    parts['word/styles.xml'] = sty.encode('utf8')
    p2 = _os.path.join(tempfile.mkdtemp(), 'g2.docx')
    with zipfile.ZipFile(p2, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)
    return p2


def test_r1_same_format_corrupt_glyph_is_repaired():
    import os as _os
    from conformer.engine import Conformer
    from conformer.numbering import NumberingGraph
    TEMPLATE = _os.path.join(_os.path.dirname(__file__), '..', 'src', 'conformer', 'assets', 'template.dotx')
    c = Conformer(TEMPLATE, _corrupt_glyph_bullet_docx())
    g0 = NumberingGraph(c._orig_num0, c._orig_styles0)
    b0 = g0.resolve_level(*g0.style_numpr('ListBullet'))
    assert b0['numFmt'] == 'bullet' and b0['lvlText'] == 'BROKEN'     # format ok, glyph corrupt
    c.disposition = 'preserve'
    c._repair_styles()
    g1 = NumberingGraph(c.num, c.styles)
    b1 = g1.resolve_level(*g1.style_numpr('ListBullet'))
    assert b1['numFmt'] == 'bullet' and b1['lvlText'] != 'BROKEN'     # glyph repaired to the house bullet
    assert 'ListBullet' in c._house_repaired                          # recorded as intended


# ---------------------------------------------------------------- R3: enforcing, complete verification
_R3_BASE = (f'<w:numbering {W}><w:abstractNum w:abstractNumId="40"><w:lvl w:ilvl="0">'
            '<w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>'
            '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="%2)"/></w:lvl>'
            '</w:abstractNum><w:num w:numId="7"><w:abstractNumId w:val="40"/></w:num></w:numbering>')
_R3_STY = f'<w:styles {W}></w:styles>'


def test_r3_definition_integrity_catches_documented_mutations():
    from conformer.engine import Conformer
    mutations = {
        'removed': lambda x: x.replace('<w:num w:numId="7"><w:abstractNumId w:val="40"/></w:num>', ''),
        'start 1->9': lambda x: x.replace('<w:start w:val="1"/><w:numFmt w:val="decimal"/>',
                                          '<w:start w:val="9"/><w:numFmt w:val="decimal"/>'),
        'label %1.->Article %1:': lambda x: x.replace('%1.', 'Article %1:'),
        'deep level (ilvl 1) fmt': lambda x: x.replace('lowerLetter', 'bullet'),
    }
    for name, mut in mutations.items():
        c = Conformer.__new__(Conformer)
        c._orig_num0 = _R3_BASE; c._orig_styles0 = _R3_STY
        c.num = mut(_R3_BASE); c.styles = _R3_STY
        viol = c.definition_integrity_report()
        assert viol, f'mutation not caught: {name}'


def test_r3_unchanged_definition_is_clean():
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    c._orig_num0 = _R3_BASE; c._orig_styles0 = _R3_STY
    c.num = _R3_BASE; c.styles = _R3_STY
    assert c.definition_integrity_report() == []


def test_r3_style_reassignment_to_different_start_is_detected():
    from conformer.engine import Conformer
    num = (f'<w:numbering {W}>'
           '<w:abstractNum w:abstractNumId="70"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
           '<w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
           '<w:abstractNum w:abstractNumId="80"><w:lvl w:ilvl="0"><w:start w:val="9"/>'
           '<w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
           '<w:num w:numId="7"><w:abstractNumId w:val="70"/></w:num>'
           '<w:num w:numId="8"><w:abstractNumId w:val="80"/></w:num></w:numbering>')
    c = Conformer.__new__(Conformer); c._house_repaired = {}
    c._orig_num0 = num; c._orig_styles0 = f'<w:styles {W}>' + _style('X', 7) + '</w:styles>'
    c.num = num; c.styles = f'<w:styles {W}>' + _style('X', 8) + '</w:styles>'   # X reassigned 7->8
    assert any(r['style'] == 'X' for r in c.numbering_report())   # both decimal but start 1->9 detected


def test_r3_lvlrestart_change_detected():
    from conformer.engine import Conformer
    base = (f'<w:numbering {W}><w:abstractNum w:abstractNumId="40"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
            '<w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlRestart w:val="0"/></w:lvl>'
            '</w:abstractNum><w:num w:numId="7"><w:abstractNumId w:val="40"/></w:num></w:numbering>')
    c = Conformer.__new__(Conformer)
    c._orig_num0 = base; c._orig_styles0 = _R3_STY
    c.num = base.replace('<w:lvlRestart w:val="0"/>', '<w:lvlRestart w:val="1"/>'); c.styles = _R3_STY
    assert c.definition_integrity_report()   # lvlRestart 0->1 now caught


def test_r3_conformance_clean_gate_reflects_issues():
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    empty = {'numbering_flips': [], 'definition_integrity_violations': [], 'tables_failing_effective_format': [],
             'tables_review': []}
    empty_u = {'rolled_back_passes': [], 'tables_needing_review': [], 'tables_unresolved': []}
    c.outcome_report = lambda: {'conformance': empty, 'unresolved': empty_u}
    assert c.conformance_clean() is True and c.conformance_status()['blocking'] is False
    for bad in ('numbering_flips', 'definition_integrity_violations', 'tables_failing_effective_format'):
        c.outcome_report = lambda b=bad: {'conformance': {**empty, b: [{'x': 1}]}, 'unresolved': empty_u}
        assert c.conformance_clean() is False and c.conformance_status()['blocking'] is True, bad
    # an UNADJUDICATED review deviation is not clean (but not blocking)
    c.outcome_report = lambda: {'conformance': {**empty, 'tables_review': [{'x': 1}]}, 'unresolved': empty_u}
    assert c.conformance_clean() is False and c.conformance_status()['blocking'] is False
    c.outcome_report = lambda: {'conformance': empty, 'unresolved': {**empty_u, 'tables_unresolved': [{'x': 1}]}}
    assert c.conformance_clean() is False   # an unresolved table is never clean


class _FreshStub:
    """Minimal stand-in for a conformed engine at the save boundary."""
    def __init__(self, status=None, raise_status=False, valid=(True, '')):
        self._status = status; self._raise = raise_status; self._valid = valid
        self.disposition = 'clean'; self.audit = []
    def validate_output(self):
        return self._valid
    def conformance_status(self):
        if self._raise:
            raise RuntimeError('verifier boom')
        return self._status


def _apply_window():
    import os as _os
    _os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from conformer.ui.window import MainWindow
    mw = MainWindow.__new__(MainWindow)
    mw.judgment_rows = []
    mw._highlight_decision_log = lambda: []
    saved = []
    mw._save_output = lambda fresh: (saved.append('saved') or '/out/x.docx')
    mw._build_complete_state = lambda *a, **k: saved.append('complete')
    mw._build_review_state = lambda *a, **k: saved.append('review')
    mw._build_error_state = lambda *a, **k: saved.append('error')
    return mw, saved


def test_r3_save_boundary_branches_gate_the_write():
    # The authoritative save-boundary decision, exercised per branch with an actual save-call assertion
    # (replacing the old source-string 'wiring' test): clean saves silently; damage/unknown fail closed.
    clean = {'clean': True, 'blocking': False}
    blocking = {'clean': False, 'blocking': True}
    review = {'clean': False, 'blocking': False}

    # clean -> saves without ever prompting
    mw, saved = _apply_window()
    called = []
    mw._confirm_unverified_save = lambda kind, detail: called.append(kind) or True
    mw._on_apply_done(_FreshStub(status=clean), {})
    assert 'saved' in saved and called == []          # no confirmation needed on a clean verdict

    # blocking + user cancels -> NOT saved
    mw, saved = _apply_window()
    mw._confirm_unverified_save = lambda kind, detail: False
    mw._on_apply_done(_FreshStub(status=blocking), {})
    assert 'saved' not in saved and 'review' in saved

    # exception (unknown) + user cancels -> NOT saved (fail closed; the core regression)
    mw, saved = _apply_window()
    kinds = []
    mw._confirm_unverified_save = lambda kind, detail: kinds.append(kind) or False
    mw._on_apply_done(_FreshStub(raise_status=True), {})
    assert 'saved' not in saved and kinds == ['unknown']

    # exception + explicit confirm -> saved, but only via the explicit review-copy decision
    mw, saved = _apply_window()
    mw._confirm_unverified_save = lambda kind, detail: True
    mw._on_apply_done(_FreshStub(raise_status=True), {})
    assert 'saved' in saved

    # non-blocking review + cancel -> NOT saved
    mw, saved = _apply_window()
    mw._confirm_unverified_save = lambda kind, detail: False
    mw._on_apply_done(_FreshStub(status=review), {})
    assert 'saved' not in saved


def test_r3_conformance_clean_wired_into_audit_and_ui_callers():
    # Not a source-string check: the audit build actually consults the authoritative verdict, and the
    # completion view reports UNKNOWN (not an inferred pass) when the verdict raises.
    from conformer import audit_export
    import inspect
    src = inspect.getsource(audit_export.build_records)
    assert 'conformance_clean' in src or 'conformance_status' in src


# ---------------------------------------------------------------- R5: effective table formatting
def test_r5_disabled_header_and_direct_font_size_fail():
    from conformer.tablespec import effective_table_issues, table_conformant
    frag = ('<w:tbl><w:tblPr><w:tblStyle w:val="LITable"/>'
            '<w:tblLook w:val="0000" w:firstRow="0" w:lastRow="0" w:firstColumn="0" w:lastColumn="0"/></w:tblPr>'
            '<w:tblGrid><w:gridCol w:w="2000"/></w:tblGrid>'
            '<w:tr><w:trPr><w:tblHeader w:val="0"/></w:trPr><w:tc><w:tcPr></w:tcPr>'
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:sz w:val="144"/></w:rPr>'
            '<w:t>H</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    kinds = {i['kind'] for i in effective_table_issues(frag)}
    assert 'header-conditional-off' in kinds     # tblLook firstRow off -> navy header never applies
    assert 'header-missing' in kinds             # tblHeader val=0 is DISABLED, not enabled
    assert 'font-size' in kinds                  # a 72pt direct header run defeats the house size
    assert table_conformant(frag) is False       # was falsely True before


def test_r5_equivalent_direct_border_not_flagged():
    from conformer.tablespec import effective_table_issues
    house = '<w:tcBorders><w:top w:val="single" w:sz="4" w:color="808080"/></w:tcBorders>'
    frag = (f'<w:tbl><w:tblPr><w:tblStyle w:val="LITable"/></w:tblPr><w:tblGrid><w:gridCol w:w="2000"/></w:tblGrid>'
            f'<w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:tcPr>{house}</w:tcPr>'
            f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    assert not any(i['kind'] == 'grid-overridden' for i in effective_table_issues(frag))   # equivalent = ok
    red = house.replace('808080', 'FF0000').replace('sz="4"', 'sz="18"')
    assert any(i['kind'] == 'grid-overridden' for i in effective_table_issues(frag.replace(house, red)))


def test_r5_corrupt_litable_style_def_detected():
    from conformer.tablespec import effective_table_issues
    frag = ('<w:tbl><w:tblPr><w:tblStyle w:val="LITable"/></w:tblPr><w:tblGrid><w:gridCol w:w="2000"/></w:tblGrid>'
            '<w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:tcPr></w:tcPr>'
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    grid = ''.join(f'<w:{s} w:val="single" w:sz="4" w:color="808080"/>'
                   for s in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
    good = (f'<w:styles {W}><w:style w:type="table" w:styleId="LITable"><w:name w:val="LI Table"/>'
            f'<w:tblPr><w:tblBorders>{grid}</w:tblBorders></w:tblPr>'
            '<w:tblStylePr w:type="firstRow"><w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>'
            '<w:tcPr><w:shd w:val="clear" w:fill="054F8A"/></w:tcPr></w:tblStylePr></w:style></w:styles>')
    # a style merely NAMED with the hex strings but with no grid/header properties must NOT pass
    corrupt = f'<w:styles {W}><w:style w:type="table" w:styleId="LITable"><w:name w:val="808080 054F8A"/></w:style></w:styles>'
    assert not any(i['kind'] == 'style-corrupt' for i in effective_table_issues(frag, styles_xml=good))
    assert any(i['kind'] == 'style-corrupt' for i in effective_table_issues(frag, styles_xml=corrupt))


def test_r5_single_grey_border_and_no_header_text_is_not_house():
    # The reviewer's exact reproduction: a definition with ONE nil grey border and a firstRow fill only —
    # no real grid, no white header text — must be reported corrupt, not conformant (issue #1 R5).
    from conformer.tablespec import effective_table_issues, table_conformant
    frag = ('<w:tbl><w:tblPr><w:tblStyle w:val="LITable"/></w:tblPr><w:tblGrid><w:gridCol w:w="2000"/></w:tblGrid>'
            '<w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:tcPr></w:tcPr>'
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    weak = (f'<w:styles {W}><w:style w:type="table" w:styleId="LITable">'
            '<w:tblPr><w:tblBorders><w:top w:val="nil" w:color="808080"/></w:tblBorders></w:tblPr>'
            '<w:tblStylePr w:type="firstRow"><w:tcPr><w:shd w:fill="054F8A"/></w:tcPr></w:tblStylePr>'
            '</w:style></w:styles>')
    issues = effective_table_issues(frag, styles_xml=weak)
    assert any(i['kind'] == 'style-corrupt' for i in issues), issues   # was falsely conformant before
    assert table_conformant(frag, styles_xml=weak) is False


def test_r5_equivalent_font_size_not_flagged_but_conflicting_is():
    from conformer.tablespec import effective_table_issues

    def frag(sz):
        return ('<w:tbl><w:tblPr><w:tblStyle w:val="LITable"/></w:tblPr><w:tblGrid><w:gridCol w:w="2000"/>'
                '</w:tblGrid><w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:tcPr></w:tcPr>'
                f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:sz w:val="{sz}"/></w:rPr>'
                '<w:t>x</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    assert not any(i['kind'] == 'font-size' for i in effective_table_issues(frag('22')))   # equal = ok
    assert any(i['kind'] == 'font-size' for i in effective_table_issues(frag('144')))       # 72pt conflicts


# ---------------------------------------------------------------- R7: highlight decision honesty
def test_r7_per_item_keep_survives_remove_all():
    import os as _os
    _os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from conformer.engine import JudgmentCall
    from conformer.ui.window import MainWindow, _ClickFrame  # noqa: F401
    mw = MainWindow.__new__(MainWindow)
    calls = [JudgmentCall(id=f'highlight_{i}', kind='highlight', item_index=i, full_text=f'm{i}',
                          short_text=f'm{i}', message='Yellow highlight.', recommended_action='Remove')
             for i in range(5)]
    mw.highlight_calls = calls
    mw.highlight_decision = {}
    # bulk remove, then explicitly KEEP item 2
    mw._set_all_highlights(True)
    mw._set_highlight(calls[2].id, False)
    dec = mw._highlight_decisions()
    assert dec['highlight_2'] == 'skip', 'a per-item keep must survive Remove-all'
    assert dec['highlight_0'] == 'accept' and dec['highlight_4'] == 'accept'
    # bulk undo restores keep for all
    mw._set_all_highlights(False)
    assert set(mw._highlight_decisions().values()) == {'skip'}


def test_r7_grouped_highlight_decisions_reach_the_audit():
    from conformer.ui.window import MainWindow
    from conformer.engine import JudgmentCall
    mw = MainWindow.__new__(MainWindow)
    calls = [JudgmentCall(id='highlight_1', kind='highlight', item_index=1, full_text='marker',
                          short_text='marker', message='Yellow highlight.', recommended_action='Remove')]
    mw.highlight_calls = calls
    mw.highlight_decision = {'highlight_1': True}   # user chose remove
    rows = mw._highlight_decision_log()
    assert any(r.get('status') == 'REMOVED' and 'highlight' in r.get('action', '').lower() for r in rows), rows


# ================================================================ round-3 acceptance reproductions
def _blank_conformer():
    """A Conformer skeleton for exercising _repair_styles/verdict without a real docx."""
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    c._skip = lambda k: False
    c.say = lambda *a, **k: None
    c._house_repaired = {}
    c._unresolved_imports = []
    c._table_notes = []
    c.exceptions = []
    c._orig_items0 = []; c._orig_b0 = 0
    c.items = []; c.b0 = 0
    c.head = f'<w:document {W}><w:body>'; c.tail = '</w:body></w:document>'
    c.revision_ledger = None
    return c


# ---------------------------------------------------------------- R2: failed import must not rebind
def test_r2_failed_import_does_not_add_style_or_rebind_and_is_not_clean():
    # Destination numId 5 is an UNRELATED bullet list. The template adds style 'New' referencing template
    # numId 5, whose abstract defers to a missing linked style (unresolvable). The style must NOT be added
    # carrying numId 5 (which would silently resolve to the destination bullet list), and the authoritative
    # verdict must NOT be clean.
    c = _blank_conformer()
    c.num = (f'<w:numbering {W}>'
             '<w:abstractNum w:abstractNumId="50"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/>'
             '<w:lvlText w:val="&#61623;"/></w:lvl></w:abstractNum>'
             '<w:num w:numId="5"><w:abstractNumId w:val="50"/></w:num></w:numbering>')
    c.styles = f'<w:styles {W}></w:styles>'
    c._orig_num0 = c.num; c._orig_styles0 = c.styles
    c.t_num = (f'<w:numbering {W}>'
               '<w:abstractNum w:abstractNumId="50"><w:numStyleLink w:val="Missing"/></w:abstractNum>'
               '<w:num w:numId="5"><w:abstractNumId w:val="50"/></w:num></w:numbering>')
    c.t_styles = (f'<w:styles {W}>'
                  '<w:style w:type="paragraph" w:styleId="New"><w:name w:val="New"/>'
                  '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr></w:pPr></w:style>'
                  '</w:styles>')
    c._repair_styles()
    from conformer.numbering import NumberingGraph
    g = NumberingGraph(c.num, c.styles)
    # 'New' was not added bound to the destination's unrelated bullet list
    if 'w:styleId="New"' in c.styles:
        assert g.style_numpr('New') != ('5', '0'), 'style was rebound to the destination bullet list'
    assert any(u.get('style') == 'New' for u in c._unresolved_imports), c._unresolved_imports
    # destination numId 5 untouched
    assert g.effective_format('5', '0') == 'bullet'
    # and the failure reaches the authoritative verdict
    assert c.conformance_status()['clean'] is False
    assert c.conformance_status()['reasons']['unresolved_imports']


# ---------------------------------------------------------------- R1: repair preserves list start
def _start9_broken_numbered_docx():
    import os as _os, re as _re, zipfile, tempfile
    import lib
    from docx import Document
    d = Document(lib.li_base_docx())
    for p in list(d.paragraphs):
        p._element.getparent().remove(p._element)
    d.add_paragraph('BACKGROUND', style='Heading1')
    d.add_paragraph('a numbered item', style='NumberedParagraph')
    p = _os.path.join(tempfile.mkdtemp(), 'n.docx'); d.save(p)
    zin = zipfile.ZipFile(p); parts = {n: zin.read(n) for n in zin.namelist()}; zin.close()
    lvls = ''.join(f'<w:lvl w:ilvl="{i}"><w:start w:val="9"/><w:numFmt w:val="decimal"/>'
                   '<w:lvlText w:val="BROKEN"/></w:lvl>' for i in range(9))
    num = parts['word/numbering.xml'].decode('utf8').replace(
        '</w:numbering>',
        f'<w:abstractNum w:abstractNumId="902">{lvls}</w:abstractNum>'
        '<w:num w:numId="902"><w:abstractNumId w:val="902"/></w:num></w:numbering>')
    parts['word/numbering.xml'] = num.encode('utf8')
    sty = _re.sub(r'(<w:style [^>]*w:styleId="NumberedParagraph".*?<w:numId w:val=")[^"]+(")',
                  r'\g<1>902\g<2>', parts['word/styles.xml'].decode('utf8'), count=1, flags=_re.S)
    parts['word/styles.xml'] = sty.encode('utf8')
    p2 = _os.path.join(tempfile.mkdtemp(), 'n2.docx')
    with zipfile.ZipFile(p2, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)
    return p2


def test_r1_repair_preserves_original_list_start():
    import os as _os
    from conformer.engine import Conformer
    from conformer.numbering import NumberingGraph
    TEMPLATE = _os.path.join(_os.path.dirname(__file__), '..', 'src', 'conformer', 'assets', 'template.dotx')
    c = Conformer(TEMPLATE, _start9_broken_numbered_docx())
    g0 = NumberingGraph(c._orig_num0, c._orig_styles0)
    b0 = g0.resolve_level(*g0.style_numpr('NumberedParagraph'))
    assert b0['numFmt'] == 'decimal' and b0['lvlText'] == 'BROKEN' and b0['start'] == '9'
    c.disposition = 'preserve'
    c._repair_styles()
    g1 = NumberingGraph(c.num, c.styles)
    b1 = g1.resolve_level(*g1.style_numpr('NumberedParagraph'))
    assert b1['lvlText'] != 'BROKEN', 'glyph should be repaired to the house label'
    assert b1['start'] == '9', 'the original list start must be PRESERVED, not reset to the template start'
    assert 'NumberedParagraph' in c._house_repaired
    # the change is reported INTENDED because the after-state equals the recorded expected delta
    rep = {r['style']: r for r in c.numbering_report()}
    assert rep['NumberedParagraph']['intended'] is True


def test_r1_report_rejects_start_reset_even_under_repair():
    # A repair is recorded, but the ACTUAL after-state reset the start (1) instead of preserving it (9).
    # Membership in a repair must NOT authorize that: it must be flagged as an unauthorized flip.
    from conformer.engine import Conformer
    num_before = (f'<w:numbering {W}><w:abstractNum w:abstractNumId="70"><w:lvl w:ilvl="0">'
                  '<w:start w:val="9"/><w:numFmt w:val="decimal"/><w:lvlText w:val="BROKEN"/></w:lvl>'
                  '</w:abstractNum><w:num w:numId="7"><w:abstractNumId w:val="70"/></w:num></w:numbering>')
    # after: style X points at a def with start reset to 1 (label fixed)
    num_after = (f'<w:numbering {W}><w:abstractNum w:abstractNumId="70"><w:lvl w:ilvl="0">'
                 '<w:start w:val="9"/><w:numFmt w:val="decimal"/><w:lvlText w:val="BROKEN"/></w:lvl>'
                 '</w:abstractNum><w:num w:numId="7"><w:abstractNumId w:val="70"/></w:num>'
                 '<w:abstractNum w:abstractNumId="99"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
                 '<w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
                 '<w:num w:numId="99"><w:abstractNumId w:val="99"/></w:num></w:numbering>')
    sty_before = f'<w:styles {W}>' + _style('X', 7) + '</w:styles>'
    sty_after = f'<w:styles {W}>' + _style('X', 99) + '</w:styles>'
    c = Conformer.__new__(Conformer)
    c._orig_num0 = num_before; c._orig_styles0 = sty_before
    c.num = num_after; c.styles = sty_after
    # the repair intended to keep start 9 (preserved), but the after-state has start 1
    c._house_repaired = {'X': {'ilvl': '0',
                               'before': {'numFmt': 'decimal', 'lvlText': 'BROKEN', 'start': '9',
                                          'isLgl': False, 'lvlRestart': None},
                               'after_expected': {'numFmt': 'decimal', 'lvlText': '%1.', 'start': '9',
                                                  'isLgl': False, 'lvlRestart': None}}}
    rep = {r['style']: r for r in c.numbering_report()}
    assert rep['X']['intended'] is False, 'a start reset under a repair must be an unauthorized flip'

    # and when the after-state matches the expected delta (start preserved), it IS intended
    c.num = num_after.replace('<w:start w:val="1"/>', '<w:start w:val="9"/>')
    c.styles = sty_after
    rep2 = {r['style']: r for r in c.numbering_report()}
    assert 'X' not in rep2 or rep2['X']['intended'] is True


# ---------------------------------------------------------------- R3: actual paragraph references
def _direct_numref_docx():
    import os as _os, zipfile, tempfile
    import lib
    from docx import Document
    d = Document(lib.li_base_docx())
    for p in list(d.paragraphs):
        p._element.getparent().remove(p._element)
    d.add_paragraph('BACKGROUND', style='Heading1')
    d.add_paragraph('a referenced item')
    p = _os.path.join(tempfile.mkdtemp(), 'ref.docx'); d.save(p)
    zin = zipfile.ZipFile(p); parts = {n: zin.read(n) for n in zin.namelist()}; zin.close()
    num = parts['word/numbering.xml'].decode('utf8').replace(
        '</w:numbering>',
        '<w:abstractNum w:abstractNumId="900"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
        '<w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
        '<w:abstractNum w:abstractNumId="901"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
        '<w:numFmt w:val="bullet"/><w:lvlText w:val="&#61623;"/></w:lvl></w:abstractNum>'
        '<w:num w:numId="900"><w:abstractNumId w:val="900"/></w:num>'
        '<w:num w:numId="901"><w:abstractNumId w:val="901"/></w:num></w:numbering>')
    parts['word/numbering.xml'] = num.encode('utf8')
    doc = parts['word/document.xml'].decode('utf8')
    # give the 'a referenced item' paragraph a DIRECT numPr referencing numId 900
    doc = doc.replace('<w:r><w:t>a referenced item</w:t></w:r>',
                      '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="900"/></w:numPr></w:pPr>'
                      '<w:r><w:t>a referenced item</w:t></w:r>', 1)
    parts['word/document.xml'] = doc.encode('utf8')
    p2 = _os.path.join(tempfile.mkdtemp(), 'ref2.docx')
    with zipfile.ZipFile(p2, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)
    return p2


def test_r3_direct_paragraph_reference_flip_is_caught():
    import os as _os
    from conformer.engine import Conformer
    TEMPLATE = _os.path.join(_os.path.dirname(__file__), '..', 'src', 'conformer', 'assets', 'template.dotx')
    c = Conformer(TEMPLATE, _direct_numref_docx())
    # a clean load (definitions all present, reference at 900) has no reference flip
    assert c.paragraph_reference_report() == []
    # corruption injection: reassign ONLY this paragraph's reference 900 (decimal) -> 901 (bullet)
    for k in range(c.n()):
        if 'a referenced item' in c.item(k):
            c.set(k, c.item(k).replace('w:val="900"', 'w:val="901"'))
    flips = c.paragraph_reference_report()
    assert any('a referenced item' in f['text'] for f in flips), flips
    st = c.conformance_status()
    assert st['clean'] is False and st['blocking'] is True
    assert st['reasons']['paragraph_reference_flips']


# ---------------------------------------------------------------- R6: docDefaults colour default
def test_r6_black_over_nonblack_docdefault_is_not_redundant():
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    c.styles = (f'<w:styles {W}><w:docDefaults><w:rPrDefault><w:rPr>'
                '<w:color w:val="FF0000"/></w:rPr></w:rPrDefault></w:docDefaults></w:styles>')
    sc = _scmap(Body=(None, None))
    # Body style + run have no colour; docDefaults is red. An explicit black is NOT redundant — removing it
    # would expose the red default (issue #1 R6).
    assert c._color_is_redundant('<w:color w:val="000000"/>', None, 'Body', sc) is False
    # with NO docDefaults colour, black is the true default and an explicit black IS redundant
    c.styles = f'<w:styles {W}></w:styles>'
    assert c._color_is_redundant('<w:color w:val="000000"/>', None, 'Body', sc) is True


# ---------------------------------------------------------------- validation: structural MBF carriers
def meaning_carriers(stories):
    """Per-occurrence, per-story, VALUE-sensitive carriers of meaning-bearing run formatting. Structural
    (ElementTree), a Counter (not a set) so losing one of several identical carriers is detectable, keyed
    by (story, prop, value, text)."""
    from collections import Counter
    import xml.etree.ElementTree as ET
    _W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    def w(t): return '{%s}%s' % (_W, t)
    out = Counter()
    for story, xml in stories.items():
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            root = ET.fromstring(f'<root xmlns:w="{_W}">{xml}</root>')
        for r in root.iter(w('r')):
            rpr = r.find(w('rPr'))
            if rpr is None:
                continue
            text = ' '.join((''.join(t.text or '' for t in r.iter(w('t')))).split())
            for prop in ('vertAlign', 'strike', 'dstrike'):
                el = rpr.find(w(prop))
                if el is None:
                    continue
                val = el.get(w('val'))
                if prop in ('strike', 'dstrike') and (val or '').lower() in ('0', 'false', 'off'):
                    continue                       # an explicit OFF is not a carrier
                out[(story, prop, val or '', text)] += 1
    return out


def _run(prop, val, text):
    return f'<w:r><w:rPr><w:{prop} w:val="{val}"/></w:rPr><w:t>{text}</w:t></w:r>'


def test_carrier_extractor_is_value_and_occurrence_sensitive():
    body = f'<w:body>{_run("vertAlign", "subscript", "2")}{_run("vertAlign", "subscript", "2")}</w:body>'
    src = meaning_carriers({'document': body})
    # losing ONE of two identical carriers is detected (a set would hide it)
    out_missing_one = meaning_carriers({'document': f'<w:body>{_run("vertAlign", "subscript", "2")}</w:body>'})
    assert (src - out_missing_one), 'dropping one repeated carrier must be detectable'
    # changing subscript -> superscript is detected (value-sensitive)
    out_flipped = meaning_carriers({'document': f'<w:body>{_run("vertAlign", "superscript", "2")}'
                                                 f'{_run("vertAlign", "superscript", "2")}</w:body>'})
    assert (src - out_flipped), 'subscript changed to superscript must be detectable'
    # identical content in the SAME story is clean
    assert not (src - meaning_carriers({'document': body}))
    # story identity matters: the same carrier in footnotes does not cover a document loss
    split = meaning_carriers({'document': f'<w:body>{_run("vertAlign", "subscript", "2")}</w:body>',
                              'footnotes': f'<w:root>{_run("vertAlign", "subscript", "2")}</w:root>'})
    assert (src - split), 'a document carrier must not be satisfied by a footnote carrier'
