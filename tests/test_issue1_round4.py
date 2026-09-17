"""Round-4 acceptance reproductions for GitHub issue #1 (R1 list-instance semantics, R3 complete
reference coverage + accurate review-copy output). Each encodes a documented counterexample that must FAIL
before its fix and PASS after. Gates are not weakened; unresolved results are never treated as conformant."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'synthetic'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
W14 = 'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"'
TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets', 'template.dotx')


def _blank_conformer(num, sty, tnum, tsty):
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    c._skip = lambda k: False
    c.say = lambda *a, **k: None
    c._house_repaired = {}
    c._unresolved_imports = []
    c._table_notes = []
    c.num = num; c.styles = sty
    c._orig_num0 = num; c._orig_styles0 = sty
    c.t_num = tnum; c.t_styles = tsty
    c.items = []; c.b0 = 0; c._orig_items0 = []; c._orig_b0 = 0
    return c


# ---------------------------------------------------------------- R1: shared multilevel list instance
def _np_styles(numsrc):
    return (f'<w:styles {W}>'
            '<w:style w:type="paragraph" w:styleId="NumberedParagraph"><w:name w:val="NumberedParagraph"/>'
            f'<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{numsrc}"/></w:numPr></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="NumberedParagraphL1"><w:name w:val="NumberedParagraphL1"/>'
            f'<w:pPr><w:numPr><w:ilvl w:val="1"/><w:numId w:val="{numsrc}"/></w:numPr></w:pPr></w:style>'
            '</w:styles>')


def test_r1_shared_multilevel_list_repaired_to_one_instance():
    from conformer.numbering import NumberingGraph
    num = (f'<w:numbering {W}>'
           '<w:abstractNum w:abstractNumId="50"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
           '<w:numFmt w:val="decimal"/><w:lvlText w:val="BROKEN1"/></w:lvl>'
           '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="BROKEN2"/></w:lvl>'
           '</w:abstractNum><w:num w:numId="5"><w:abstractNumId w:val="50"/></w:num></w:numbering>')
    tnum = (f'<w:numbering {W}>'
            '<w:abstractNum w:abstractNumId="70"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
            '<w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>'
            '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2."/></w:lvl>'
            '</w:abstractNum><w:num w:numId="9"><w:abstractNumId w:val="70"/></w:num></w:numbering>')
    c = _blank_conformer(num, _np_styles('5'), tnum, _np_styles('9'))
    c._repair_styles()
    g = NumberingGraph(c.num, c.styles)
    np0 = g.style_numpr('NumberedParagraph'); np1 = g.style_numpr('NumberedParagraphL1')
    assert np0[0] == np1[0], f'shared list split into separate instances: {np0} vs {np1}'
    assert np0[1] == '0' and np1[1] == '1'
    assert g.resolve_level(*np0)['lvlText'] == '%1.'
    assert g.resolve_level(*np1)['lvlText'] == '%1.%2.'


def test_r1_independent_lists_stay_independent():
    from conformer.numbering import NumberingGraph
    num = (f'<w:numbering {W}>'
           '<w:abstractNum w:abstractNumId="50"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/>'
           '<w:lvlText w:val="BROKENA"/></w:lvl></w:abstractNum>'
           '<w:abstractNum w:abstractNumId="51"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/>'
           '<w:lvlText w:val="BROKENB"/></w:lvl></w:abstractNum>'
           '<w:num w:numId="5"><w:abstractNumId w:val="50"/></w:num>'
           '<w:num w:numId="6"><w:abstractNumId w:val="51"/></w:num></w:numbering>')

    def sty(a, b):
        return (f'<w:styles {W}>'
                '<w:style w:type="paragraph" w:styleId="ListNumber"><w:name w:val="ListNumber"/>'
                f'<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{a}"/></w:numPr></w:pPr></w:style>'
                '<w:style w:type="paragraph" w:styleId="ListNumber2"><w:name w:val="ListNumber2"/>'
                f'<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{b}"/></w:numPr></w:pPr></w:style></w:styles>')
    tnum = (f'<w:numbering {W}>'
            '<w:abstractNum w:abstractNumId="70"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/>'
            '<w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
            '<w:abstractNum w:abstractNumId="71"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/>'
            '<w:lvlText w:val="%1)"/></w:lvl></w:abstractNum>'
            '<w:num w:numId="8"><w:abstractNumId w:val="70"/></w:num>'
            '<w:num w:numId="9"><w:abstractNumId w:val="71"/></w:num></w:numbering>')
    c = _blank_conformer(num, sty('5', '6'), tnum, sty('8', '9'))
    c._repair_styles()
    g = NumberingGraph(c.num, c.styles)
    assert g.style_numpr('ListNumber')[0] != g.style_numpr('ListNumber2')[0], 'independent lists were merged'


# ---------------------------------------------------------------- R3: coverage — typography + table cells
def _numref_docx(build_paragraph):
    import zipfile, tempfile
    import lib
    from docx import Document
    d = Document(lib.li_base_docx())
    for p in list(d.paragraphs):
        p._element.getparent().remove(p._element)
    d.add_paragraph('BACKGROUND', style='Heading1')
    d.add_paragraph('ANCHOR-PARA')
    p = os.path.join(tempfile.mkdtemp(), 'r.docx'); d.save(p)
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
    doc = doc.replace('<w:r><w:t>ANCHOR-PARA</w:t></w:r>', build_paragraph, 1)
    parts['word/document.xml'] = doc.encode('utf8')
    p2 = os.path.join(tempfile.mkdtemp(), 'r2.docx')
    with zipfile.ZipFile(p2, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)
    return p2


def test_r3_typography_change_does_not_disable_reference_check():
    from conformer.engine import Conformer
    apos = '’'
    para = ('<w:p w14:paraId="11112222"><w:pPr><w:numPr><w:ilvl w:val="0"/>'
            '<w:numId w:val="900"/></w:numPr></w:pPr><w:r><w:t>The contractor'
            + "'s submission.</w:t></w:r></w:p>")
    c = Conformer(TEMPLATE, _numref_docx(para))
    assert c.paragraph_reference_report() == []
    for k in range(c.n()):
        if 'contractor' in c.item(k):
            c.set(k, c.item(k).replace('w:val="900"', 'w:val="901"').replace("contractor's", 'contractor' + apos + 's'))
    flips = c.paragraph_reference_report()
    assert any('contractor' in f['text'] for f in flips), flips
    assert c.conformance_status()['blocking'] is True


def test_r3_table_cell_reference_change_is_covered():
    from conformer.engine import Conformer
    cell_para = ('<w:tbl><w:tblPr><w:tblStyle w:val="LITable"/></w:tblPr><w:tblGrid><w:gridCol w:w="2000"/>'
                 '</w:tblGrid><w:tr><w:tc><w:tcPr></w:tcPr>'
                 '<w:p w14:paraId="33334444"><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="900"/>'
                 '</w:numPr></w:pPr><w:r><w:t>cell numbered line</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    c = Conformer(TEMPLATE, _numref_docx(cell_para))
    assert not any('cell numbered' in f['text'] for f in c.paragraph_reference_report())
    joined = ''.join(c.items)
    assert '<w:tbl' in joined and 'cell numbered line' in joined
    for k in range(len(c.items)):
        if 'cell numbered line' in c.items[k]:
            c.items[k] = c.items[k].replace('w:val="900"', 'w:val="901"')
    flips = c.paragraph_reference_report()
    assert any('cell numbered' in f['text'] for f in flips), 'table-cell reference change not covered'


# ---------------------------------------------------------------- R3: accurate artifact labeling
def test_r3_verdict_label_is_honest_per_state():
    from conformer.engine import Conformer
    assert 'UNVERIFIED' in Conformer.verdict_label(None).upper()
    assert 'UNVERIFIED' in Conformer.verdict_label({'clean': False, 'blocking': True}).upper()
    assert 'verified clean' in Conformer.verdict_label({'clean': True, 'blocking': False}).lower()


def test_r3_review_copy_artifact_is_labeled_unverified():
    # The REAL save path (not a stub): a blocking verdict yields an UNVERIFIED docProps contentStatus and an
    # audit that records the verdict and the review-only decision.
    import zipfile, tempfile, re as _re
    import lib
    from docx import Document
    from conformer.engine import Conformer
    d = Document(lib.li_base_docx())
    d.add_paragraph('BACKGROUND', style='Heading1')
    src = os.path.join(tempfile.mkdtemp(), 'in.docx'); d.save(src)
    c = Conformer(TEMPLATE, src)
    c._save_verdict = {'clean': False, 'blocking': True,
                       'reasons': {'paragraph_reference_flips': [{'x': 1}]}}
    c._save_forced_review = True
    out = os.path.join(tempfile.mkdtemp(), 'out.docx')
    c.save(out)
    core = zipfile.ZipFile(out).read('docProps/core.xml').decode('utf8')
    status = _re.search(r'<cp:contentStatus>(.*?)</cp:contentStatus>', core, _re.S)
    assert status and 'UNVERIFIED' in status.group(1).upper(), core[:400]
    audit = c.build_audit()
    assert audit['verification_completed'] is True
    assert audit['saved_as_review_only'] is True
    assert audit['conformance_verdict']['blocking'] is True
    assert 'UNVERIFIED' in audit['label'].upper()


# ---------------------------------------------------------------- R3: heading numbering preserved (linkage)
def test_r3_linked_heading_numbering_resolves_through_pstyle():
    from conformer.numbering import NumberingGraph
    num = (f'<w:numbering {W}><w:abstractNum w:abstractNumId="20">'
           '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2"/>'
           '<w:pStyle w:val="Heading2"/></w:lvl></w:abstractNum>'
           '<w:num w:numId="1"><w:abstractNumId w:val="20"/></w:num></w:numbering>')
    sty = (f'<w:styles {W}><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
           '</w:style></w:styles>')
    g = NumberingGraph(num, sty)
    assert g.style_numpr('Heading2') == ('1', '1')          # numbered via list->style linkage, no style numPr
    assert g.resolve_level(*g.style_numpr('Heading2'))['lvlText'] == '%1.%2'


# ---------------------------------------------------------------- R5: header repair (fill corrected even if tracked)
def test_r5_header_fill_corrected_even_when_tracked_record_preserved():
    # Maintainer ruling: a WRONG header fill is corrected to the house colour even when it is a tracked
    # change. Cell A carries a STRAY non-house fill (+ small font, dark colour); cell B's non-house CURRENT
    # fill is a tracked change (tcPrChange whose OLD snapshot held a different colour). Both current fills
    # are corrected (removed so the style navy applies); the tracked-change RECORD (tcPrChange + its old
    # colour) is preserved untouched.
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    c._table_notes = []
    row = ('<w:tr><w:trPr><w:tblHeader/></w:trPr>'
           '<w:tc><w:tcPr><w:shd w:val="clear" w:fill="BDD6EE"/></w:tcPr>'
           '<w:p><w:r><w:rPr><w:sz w:val="18"/><w:color w:val="222222"/></w:rPr><w:t>A</w:t></w:r></w:p></w:tc>'
           '<w:tc><w:tcPr><w:shd w:val="clear" w:fill="D9EAF7"/>'
           '<w:tcPrChange w:id="9" w:author="R"><w:tcPr><w:shd w:val="clear" w:fill="ABCDEF"/></w:tcPr>'
           '</w:tcPrChange></w:tcPr><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr>')
    tbl = f'<w:tbl>{row}</w:tbl>'
    out, rep, tracked_fixed = c._repair_stray_header_formatting(tbl, 'T1')
    assert rep == 2 and tracked_fixed == 1
    assert 'BDD6EE' not in out and 'D9EAF7' not in out   # current fills corrected (tracked one too)
    assert out.count('w:fill="054F8A"') == 2            # both current backgrounds are concrete house navy
    assert 'tcPrChange' in out and 'ABCDEF' in out      # the tracked-change record + its old colour preserved
    assert '<w:sz' not in out and 'w:val="222222"' not in out  # stray-cell run overrides normalised
    assert any('TRACKED' in n and 'corrected' in n for n in c._table_notes)


def test_r5_header_repair_skips_nonheader_row():
    # A first row that is NOT a header (no tblHeader) must be left alone by the header repair.
    from conformer.engine import Conformer
    c = Conformer.__new__(Conformer)
    c._table_notes = []
    tbl = ('<w:tbl><w:tr><w:tc><w:tcPr><w:shd w:val="clear" w:fill="BDD6EE"/></w:tcPr>'
           '<w:p><w:r><w:t>x</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    out, rep, flag = c._repair_stray_header_formatting(tbl, 'T2')
    assert out == tbl and rep == 0 and flag == 0
