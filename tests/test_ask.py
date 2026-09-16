"""Interactive ASK structural changes in preserve mode (#8 cross-references first).

Synthetic fixtures only (no client data). Each op is exercised through the real two-pass
analyze()/apply_with_decisions() flow, and every 'challenge' asserts the display gate goes RED on a
deliberately corrupted edit — a green result proves nothing until the gate has been watched failing.
"""
import os
import re
import tempfile
import zipfile

import pytest

from conformer.engine import Conformer
from conformer import revisions as R

ASSETS = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets')
TEMPLATE = os.path.join(ASSETS, 'template.dotx')

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
# Declare the prefixes the template's merged styles/numbering use, so validate_output() is clean
# (a real Word doc declares this full Microsoft prefix set on every part).
NS = (f'xmlns:w="{W}" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
      'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml" '
      'xmlns:w16cid="http://schemas.microsoft.com/office/word/2016/wordml/cid" '
      'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"')


def _part(tag, inner=''):
    return f'<?xml version="1.0"?><w:{tag} {NS}>{inner}</w:{tag}>'.encode('utf8')


def make_docx(path, body, styles_inner=''):
    default_styles = (
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="BodyText"><w:name w:val="Body Text"/></w:style>')
    parts = {
        '[Content_Types].xml':
            b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            b'<Default Extension="xml" ContentType="application/xml"/>'
            b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            b'</Types>',
        '_rels/.rels':
            b'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            b'</Relationships>',
        'word/document.xml': f'<?xml version="1.0"?><w:document {NS}><w:body>{body}</w:body></w:document>'.encode('utf8'),
        'word/styles.xml': _part('styles', styles_inner or default_styles),
        'word/numbering.xml': _part('numbering'),
        'word/footnotes.xml': _part('footnotes'),
        'word/settings.xml': _part('settings'),
    }
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)


# A revised report fragment: literal caption, a body paragraph referencing it, a bookmarked Heading1
# so a Section reference resolves, and a paragraph whose insertion contains a literal reference that
# must stay untouched (masked). One tracked insertion means the doc routes to preserve mode.
BODY = (
    '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
    '<w:bookmarkStart w:id="10" w:name="_Sec_Background"/>'
    '<w:r><w:t>BACKGROUND</w:t></w:r><w:bookmarkEnd w:id="10"/></w:p>'
    '<w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr>'
    '<w:r><w:t>Figure 1-1: The site plan</w:t></w:r></w:p>'
    '<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
    '<w:r><w:t xml:space="preserve">As shown in Figure 1-1 and Section 1, the layout is complex.</w:t></w:r></w:p>'
    '<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
    '<w:r><w:t xml:space="preserve">Refer to Figure 1-1 here. </w:t></w:r>'
    '<w:ins w:id="1" w:author="Ann" w:date="2026-01-02T00:00:00Z">'
    '<w:r><w:t xml:space="preserve">See Figure 1-1 (inserted)</w:t></w:r></w:ins></w:p>'
    '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>'
)


@pytest.fixture
def report():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'r.docx')
        make_docx(p, BODY)
        yield p


def _accept_all(path):
    c = Conformer(TEMPLATE, path)
    calls = c.analyze()
    applied = c.apply_with_decisions({jc.id: 'accept' for jc in calls})
    return calls, applied


def test_preserve_mode_and_ask_calls_emitted(report):
    c = Conformer(TEMPLATE, report)
    calls = c.analyze()
    assert c.disposition == 'preserve'
    kinds = {jc.kind for jc in calls}
    assert 'caption' in kinds and 'xref' in kinds


def test_caption_rebuilt_as_fields_display_preserving(report):
    calls, applied = _accept_all(report)
    cap = next(i for i in range(applied.n()) if applied.style(i) == 'Caption')
    x = applied.item(cap)
    assert 'SEQ Figure' in x and 'STYLEREF' in x and '<w:bookmarkStart' in x
    # the reader still sees exactly the same caption text
    assert applied.text(cap).strip() == 'Figure 1-1: The site plan'


def test_body_cross_references_rebuilt_as_ref_fields(report):
    calls, applied = _accept_all(report)
    out = ''.join(applied.items)
    # Figure 1-1 -> REF to the caption bookmark; Section 1 -> REF to the heading bookmark
    assert 'REF _Ref_F11' in out
    assert 'REF _Sec_Background' in out
    body = next(i for i in range(applied.n())
                if 'the layout is complex' in applied.text(i))
    assert applied.text(body).strip() == 'As shown in Figure 1-1 and Section 1, the layout is complex.'


def test_reference_inside_insertion_is_not_touched(report):
    calls, applied = _accept_all(report)
    out = ''.join(applied.items)
    # the literal 'Figure 1-1' INSIDE the tracked insertion stays literal (masked), author intact
    assert 'w:author="Ann"' in out
    ins = next(i for i in range(applied.n()) if 'inserted' in applied.text(i))
    ins_x = applied.item(ins)
    # the plain run before the insertion IS fielded; the inserted run is not
    assert 'REF _Ref_F11' in ins_x                              # plain 'Refer to Figure 1-1'
    assert '<w:ins' in ins_x and 'See Figure 1-1 (inserted)' in ins_x


def test_tracked_adjacent_flagged_for_review(report):
    c = Conformer(TEMPLATE, report)
    calls = c.analyze()
    adj = [jc for jc in calls if jc.kind == 'xref' and 'Review individually' in jc.recommended_action]
    assert adj, 'the paragraph carrying an insertion must be flagged for individual review'


def test_preservation_clean_and_output_valid(report):
    calls, applied = _accept_all(report)
    clean, disc = applied.verify_preservation()
    assert clean, disc
    ok, msg = applied.validate_output()
    assert ok, msg


def test_skip_decision_leaves_literal(report):
    c = Conformer(TEMPLATE, report)
    calls = c.analyze()
    applied = c.apply_with_decisions({jc.id: 'skip' for jc in calls})
    out = ''.join(applied.items)
    assert 'REF _Ref_F11' not in out                            # nothing fielded when all skipped
    body = next(i for i in range(applied.n())
                if 'the layout is complex' in applied.text(i))
    assert 'Figure 1-1' in applied.text(body)


# ---- adversarial: the local display gate must REFUSE a corrupt edit ----

def test_local_gate_rejects_text_dropping_apply(report):
    c = Conformer(TEMPLATE, report)
    c.disposition = 'preserve'
    body = next(i for i in range(c.n()) if 'the layout is complex' in c.text(i))
    # a faulty apply that drops a visible word
    bad = {'index': body, 'apply': lambda cand: c.set(cand['index'],
              c.item(cand['index']).replace('the layout is complex', 'complex'))}
    ok = c._apply_ask_instance('xref', bad)
    assert not ok
    assert any(name.startswith('xref[') for name, _ in c.exceptions)
    # rollback restored the paragraph
    assert 'the layout is complex' in c.text(body)


def test_local_gate_rejects_bookmark_dropping_apply(report):
    c = Conformer(TEMPLATE, report)
    c.disposition = 'preserve'
    head = next(i for i in range(c.n()) if c.style(i) == 'Heading1')
    before = c.item(head)
    bad = {'index': head, 'apply': lambda cand: c.set(cand['index'],
              c.item(cand['index']).replace('<w:bookmarkStart w:id="10" w:name="_Sec_Background"/>', ''))}
    ok = c._apply_ask_instance('xref', bad)
    assert not ok                                                # dropping an existing bookmark is refused
    assert c.item(head) == before


def test_whole_pass_backstop_present(report):
    # accept-all must leave the whole-document display stream identical (display-preserving pass)
    calls, applied = _accept_all(report)
    before = R.visible_stream(Conformer(TEMPLATE, report)._output_parts())
    after = R.visible_stream(applied._output_parts())
    assert not R.visible_violations(before, after)


# ======================================================================== #3 unwrap wrapper tables
HEAD = '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>SECTION</w:t></w:r></w:p>'
INS = (HEAD + '<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
       '<w:ins w:id="9" w:author="Ed" w:date="2026-01-02T00:00:00Z">'
       '<w:r><w:t>an edit</w:t></w:r></w:ins></w:p>')   # heading + an insertion (forces preserve)

WRAPPER = (
    '<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/></w:tblPr>'
    '<w:tblGrid><w:gridCol w:w="9000"/></w:tblGrid>'
    '<w:tr><w:tc><w:tcPr><w:tcW w:w="9000" w:type="dxa"/></w:tcPr>'
    '<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr><w:r><w:t>Wrapped one.</w:t></w:r></w:p>'
    '<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr><w:r><w:t>Wrapped two.</w:t></w:r></w:p>'
    '</w:tc></w:tr></w:tbl>')


@pytest.fixture
def wrapper_doc():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'w.docx')
        make_docx(p, INS + WRAPPER + '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>')
        yield p


def test_unwrap_wrapper_table(wrapper_doc):
    calls, applied = _accept_all(wrapper_doc)
    assert any(jc.kind == 'unwrap' for jc in calls)
    out = ''.join(applied.items)
    assert '<w:tbl' not in out                                  # the wrapper shell is gone
    assert 'Wrapped one.' in out and 'Wrapped two.' in out      # its paragraphs survive
    clean, disc = applied.verify_preservation()
    assert clean, disc
    ok, msg = applied.validate_output()
    assert ok, msg


def test_unwrap_preserves_tracked_change_inside():
    # a wrapper table whose cell holds a tracked insertion: still unwrappable, insertion preserved
    body = (HEAD + WRAPPER.replace('<w:r><w:t>Wrapped two.</w:t></w:r>',
                            '<w:ins w:id="3" w:author="Ann" w:date="D"><w:r><w:t>Wrapped two.</w:t></w:r></w:ins>')
            + '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>')
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'x.docx')
        make_docx(p, body)
        calls, applied = _accept_all(p)
        out = ''.join(applied.items)
        assert '<w:tbl' not in out and 'w:author="Ann"' in out
        clean, disc = applied.verify_preservation()
        assert clean, disc
        # the instance carrying a tracked change is flagged for review
        assert any(jc.kind == 'unwrap' and 'Review individually' in jc.recommended_action for jc in calls)


# ======================================================================== #7 drop empty columns
def _two_col(row_texts, extra_second=''):
    rows = ''
    for a in row_texts:
        rows += (f'<w:tr><w:tc><w:tcPr><w:tcW w:w="6000" w:type="dxa"/></w:tcPr>'
                 f'<w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr><w:r><w:t>{a}</w:t></w:r></w:p></w:tc>'
                 f'<w:tc><w:tcPr><w:tcW w:w="3000" w:type="dxa"/></w:tcPr>'
                 f'<w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>{extra_second}</w:p></w:tc></w:tr>')
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="LITable"/><w:tblW w:w="9000" w:type="dxa"/></w:tblPr>'
            '<w:tblGrid><w:gridCol w:w="6000"/><w:gridCol w:w="3000"/></w:tblGrid>' + rows + '</w:tbl>')


def test_drop_empty_column():
    body = INS + _two_col(['Alpha', 'Beta']) + '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>'
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'd.docx')
        make_docx(p, body)
        calls, applied = _accept_all(p)
        assert any(jc.kind == 'dropcol' for jc in calls)
        tbl = next(applied.item(i) for i in range(applied.n()) if applied.item(i).startswith('<w:tbl'))
        assert len(re.findall(r'<w:gridCol', tbl)) == 1          # the empty column is gone
        assert 'Alpha' in tbl and 'Beta' in tbl
        clean, disc = applied.verify_preservation()
        assert clean, disc


def test_empty_column_with_bookmark_is_not_dropped():
    # the 'empty' second column actually holds a bookmark -> it must NOT be treated as droppable
    second = '<w:bookmarkStart w:id="7" w:name="_KEEP"/><w:bookmarkEnd w:id="7"/>'
    body = INS + _two_col(['Alpha', 'Beta'], extra_second=second) + '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>'
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'd2.docx')
        make_docx(p, body)
        calls, applied = _accept_all(p)
        assert not any(jc.kind == 'dropcol' for jc in calls)     # detection skips it
        tbl = next(applied.item(i) for i in range(applied.n()) if applied.item(i).startswith('<w:tbl'))
        assert len(re.findall(r'<w:gridCol', tbl)) == 2 and '_KEEP' in tbl
