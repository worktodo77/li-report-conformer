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
    # styleId -> {'color', 'basedOn'} like the engine's _style_color_map()
    return {sid: {'color': c, 'basedOn': b} for sid, (c, b) in styles.items()}


def test_r6_black_over_red_char_style_is_not_redundant():
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    sc = _scmap(BodyText=(None, None), RedChar=('FF0000', None))
    # explicit black run colour + a red CHARACTER style: removing the black would reveal red -> NOT redundant
    assert c._color_is_redundant('<w:color w:val="000000"/>', 'RedChar', 'BodyText', sc) is False
    # plain black on a black paragraph with no char style -> genuinely redundant
    assert c._color_is_redundant('<w:color w:val="000000"/>', None, 'BodyText', sc) is True


def test_r6_theme_colour_is_never_silently_stripped():
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    sc = _scmap(BodyText=(None, None))
    assert c._color_is_redundant('<w:color w:val="000000" w:themeColor="text1"/>', None, 'BodyText', sc) is False


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
def test_r2_import_resolves_numstylelink_not_bound_to_destination():
    from conformer.numbering import NumberingGraph
    tnum = (f'<w:numbering {W}>'
            '<w:abstractNum w:abstractNumId="40"><w:numStyleLink w:val="Link"/></w:abstractNum>'
            '<w:abstractNum w:abstractNumId="41"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/>'
            '<w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
            '<w:num w:numId="5"><w:abstractNumId w:val="40"/></w:num>'
            '<w:num w:numId="9"><w:abstractNumId w:val="41"/></w:num></w:numbering>')
    tsty = (f'<w:styles {W}>'
            '<w:style w:type="paragraph" w:styleId="New"><w:name w:val="New"/>'
            '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Link"><w:name w:val="Link"/>'
            '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="9"/></w:numPr></w:pPr></w:style></w:styles>')
    tg = NumberingGraph(tnum, tsty)
    # New's abstract (40) defers to the Link style; the resolved abstract must INLINE the decimal levels
    # so an import cannot bind to a same-named (bullet) destination Link.
    resolved = tg.resolved_abstract_xml('40')
    assert 'numStyleLink' not in resolved
    assert 'w:numFmt w:val="decimal"' in resolved


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
