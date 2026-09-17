"""Table EFFECTIVE-formatting verifier (conformer.tablespec): conformance is judged by what a table
renders, not by the style name it carries. The key acceptance criterion: a table with the correct
tblStyle=LITable but a direct override that defeats the house appearance must FAIL."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'synthetic'))

from conformer.tablespec import effective_table_issues, table_conformant   # noqa: E402


def _cell(text, tcpr='', ppr=''):
    return f'<w:tc><w:tcPr>{tcpr}</w:tcPr><w:p><w:pPr>{ppr}</w:pPr><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>'


def _header_cell(text, fill='B6DDE8', color='auto'):
    return (f'<w:tc><w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="{fill}"/></w:tcPr>'
            f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:color w:val="{color}"/></w:rPr>'
            f'<w:t>{text}</w:t></w:r></w:p></w:tc>')


def _table(rows, tblpr_extra=''):
    body = ''.join(rows)
    return (f'<w:tbl><w:tblPr><w:tblStyle w:val="GridTable4"/>{tblpr_extra}</w:tblPr>'
            f'<w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="2000"/></w:tblGrid>{body}</w:tbl>')


def _conformant_table():
    header = '<w:tr><w:trPr><w:tblHeader/></w:trPr>' + _header_cell('Term') + _header_cell('Value') + '</w:tr>'
    body = '<w:tr>' + _cell('Alpha', ppr='<w:jc w:val="center"/>') + _cell('1', ppr='<w:jc w:val="center"/>') + '</w:tr>'
    return _table([header, body])


def test_conformant_table_has_no_failures():
    issues = effective_table_issues(_conformant_table())
    assert [i for i in issues if i['severity'] == 'fail'] == [], issues
    assert table_conformant(_conformant_table())


def test_correct_style_name_but_direct_cell_border_fails():
    # THE acceptance criterion: tblStyle is LITable, but a direct <w:tcBorders> defeats the grey grid.
    header = '<w:tr><w:trPr><w:tblHeader/></w:trPr>' + _header_cell('Term') + _header_cell('Value') + '</w:tr>'
    bad = ('<w:tr><w:tc><w:tcPr><w:tcBorders><w:top w:val="single" w:sz="18" w:color="FF0000"/>'
           '</w:tcBorders></w:tcPr><w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p></w:tc>'
           + _cell('1', ppr='<w:jc w:val="center"/>') + '</w:tr>')
    issues = effective_table_issues(_table([header, bad]))
    assert any(i['kind'] == 'grid-overridden' and i['severity'] == 'fail' for i in issues), issues
    assert not table_conformant(_table([header, bad]))


def test_direct_table_borders_fail():
    # a NON-house direct table border (red, thick) overrides the grey grid and must fail
    t = _conformant_table().replace('<w:tblStyle w:val="GridTable4"/>',
                                    '<w:tblStyle w:val="GridTable4"/><w:tblBorders>'
                                    '<w:top w:val="single" w:sz="18" w:color="FF0000"/></w:tblBorders>')
    assert any(i['kind'] == 'grid-overridden' for i in effective_table_issues(t))


def test_missing_header_marker_fails():
    header = '<w:tr>' + _header_cell('Term') + _header_cell('Value') + '</w:tr>'   # no tblHeader
    body = '<w:tr>' + _cell('a', ppr='<w:jc w:val="center"/>') + _cell('b', ppr='<w:jc w:val="center"/>') + '</w:tr>'
    assert any(i['kind'] == 'header-missing' for i in effective_table_issues(_table([header, body])))


def test_header_wrong_fill_fails():
    header = '<w:tr><w:trPr><w:tblHeader/></w:trPr>' + _header_cell('Term', fill='FF0000') + _header_cell('V') + '</w:tr>'
    body = '<w:tr>' + _cell('a', ppr='<w:jc w:val="center"/>') + _cell('b', ppr='<w:jc w:val="center"/>') + '</w:tr>'
    assert any(i['kind'] == 'header-fill' for i in effective_table_issues(_table([header, body])))


def test_subtotal_shading_is_review_not_fail():
    header = '<w:tr><w:trPr><w:tblHeader/></w:trPr>' + _header_cell('Term') + _header_cell('V') + '</w:tr>'
    sub = ('<w:tr>' + _cell('Subtotal', tcpr='<w:shd w:val="clear" w:color="auto" w:fill="D9D9D9"/>',
                             ppr='<w:jc w:val="center"/>')
           + _cell('9', ppr='<w:jc w:val="center"/>') + '</w:tr>')
    issues = effective_table_issues(_table([header, sub]))
    assert any(i['kind'] == 'cell-shading' and i['severity'] == 'review' for i in issues)
    assert table_conformant(_table([header, sub]))   # review does not fail conformance


def test_nested_table_reported_unresolved():
    inner = _table(['<w:tr><w:trPr><w:tblHeader/></w:trPr>' + _header_cell('n') + _header_cell('m') + '</w:tr>'])
    header = '<w:tr><w:trPr><w:tblHeader/></w:trPr>' + _header_cell('Term') + _header_cell('V') + '</w:tr>'
    nesting = '<w:tr><w:tc><w:tcPr></w:tcPr>' + inner + '</w:tc>' + _cell('x', ppr='<w:jc w:val="center"/>') + '</w:tr>'
    issues = effective_table_issues(_table([header, nesting]))
    assert any(i['kind'] == 'nested-table' and i['severity'] == 'unresolved' for i in issues)


def test_engine_strips_direct_cell_borders_and_reports_nested():
    import lib
    from docx import Document
    from docx.oxml.ns import qn
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    from conformer.engine import Conformer
    TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets', 'template.dotx')
    d = Document(lib.li_base_docx())
    for p in list(d.paragraphs):
        p._element.getparent().remove(p._element)
    d.add_paragraph('BACKGROUND', style='Heading1')
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).paragraphs[0].add_run('Header')
    t.cell(1, 0).paragraphs[0].add_run('Data')
    # inject a direct red cell border that fights the house grid
    tcPr = t.cell(1, 0)._tc.get_or_add_tcPr()
    tcPr.append(parse_xml(f'<w:tcBorders {nsdecls("w")}><w:top w:val="single" w:sz="24" w:color="FF0000"/></w:tcBorders>'))
    path = os.path.join(tempfile.mkdtemp(), 'tbl.docx')
    d.save(path)

    c = Conformer(TEMPLATE, path)
    c.run()
    out = c.head + ''.join(c.items) + c.tail
    assert 'FF0000' not in out                 # the injected direct grid-override border was removed
    # and the conformed table carries the LI style with no direct cell borders left on my table
    my_tbl = [it for it in c.items if it.startswith('<w:tbl') and 'Data' in it]
    assert my_tbl and '<w:tcBorders>' not in my_tbl[0] and 'w:val="GridTable4"' in my_tbl[0]
    ok, _ = c.validate_output()
    assert ok
