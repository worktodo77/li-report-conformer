"""GPT audit F9: structural guards for header-cell paragraph-style normalization.

`_force_header_paragraph_style` gives plain header-cell body paragraphs the 10pt Table Header style. Two
OOXML shapes must not be mishandled: (1) a paragraph carrying a DIRECT numPr is a list item — reclassifying
it would silently strip its numbering (an unauthorized reference flip), so it is left as authored; (2) a
self-closing <w:pPr/> must gain the style IN PLACE, never as a second <w:pPr> element (invalid paragraph
structure). Fictitious content."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402

fp = Conformer._force_header_paragraph_style


def _pcount(p):
    return len(re.findall(r'<w:pPr\b', p))


def test_plain_default_paragraph_gets_header_style():
    p = '<w:p><w:r><w:t>Head</w:t></w:r></w:p>'
    out = fp(p)
    assert '<w:pStyle w:val="TableHeader"/>' in out
    assert _pcount(out) == 1


def test_self_closing_ppr_does_not_duplicate():
    # F9: <w:pPr/> must become a single styled <w:pPr>...</w:pPr>, not a paragraph with two pPr children.
    p = '<w:p><w:pPr/><w:r><w:t>Head</w:t></w:r></w:p>'
    out = fp(p)
    assert _pcount(out) == 1, out
    assert '<w:pStyle w:val="TableHeader"/>' in out
    assert '<w:pPr/>' not in out


def test_body_style_paragraph_is_reclassified():
    p = '<w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr><w:r><w:t>Head</w:t></w:r></w:p>'
    out = fp(p)
    assert '<w:pStyle w:val="TableHeader"/>' in out and 'TableData' not in out


def test_numbered_paragraph_is_never_reclassified():
    # F9: a direct numPr means a numbered/bulleted list item — leave the style AND the numbering untouched
    # even though its pStyle (Normal) is otherwise a body style eligible for reclassification.
    p = ('<w:p><w:pPr><w:pStyle w:val="Normal"/>'
         '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr></w:pPr>'
         '<w:r><w:t>a numbered item</w:t></w:r></w:p>')
    out = fp(p)
    assert out == p                                   # untouched: style kept, numbering kept
    assert '<w:numId w:val="7"/>' in out


def test_heading_paragraph_is_never_reclassified():
    p = '<w:p><w:pPr><w:pStyle w:val="Heading3"/></w:pPr><w:r><w:t>A heading</w:t></w:r></w:p>'
    assert fp(p) == p                                 # non-body deliberate style left as authored


# ── R4: the guards must hold through the FULL table pass, not only in the helper ──
import re as _re                                                                     # noqa: E402
from pathlib import Path as _Path                                                    # noqa: E402
from zipfile import ZipFile as _ZipFile, ZIP_DEFLATED as _ZD                         # noqa: E402

_TPL = _Path(__file__).resolve().parents[1] / 'src' / 'conformer' / 'assets' / 'template.dotx'
_H1 = '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>INTRO</w:t></w:r></w:p>'
_FMT_REV = ('<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr><w:r><w:rPr><w:b/>'
            '<w:rPrChange w:id="9" w:author="R" w:date="2026-01-01T00:00:00Z"><w:rPr/></w:rPrChange></w:rPr>'
            '<w:t xml:space="preserve">bolded under review</w:t></w:r></w:p>')


def _pkg(tmp_path, body):
    with _ZipFile(_TPL) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts['[Content_Types].xml'] = parts['[Content_Types].xml'].replace(
        b'wordprocessingml.template.main+xml', b'wordprocessingml.document.main+xml')
    xml = parts['word/document.xml'].decode('utf-8')
    sect = _re.findall(r'<w:sectPr\b.*?</w:sectPr>', xml, _re.S)[-1]
    parts['word/document.xml'] = _re.sub(r'<w:body>.*</w:body>',
                                         lambda _: '<w:body>' + body + sect + '</w:body>', xml, flags=_re.S).encode()
    src = tmp_path / 'in.docx'
    with _ZipFile(src, 'w', _ZD) as z:
        for n, d in parts.items():
            z.writestr(n, d)
    from conformer.engine import Conformer
    c = Conformer(str(_TPL), str(src)); c.run()
    return c


def _first_header_para(c):
    tbl = next(x for x in c.items if x.startswith('<w:tbl'))
    row = _re.findall(r'<w:tr\b.*?</w:tr>', tbl, _re.S)[0]
    return _re.search(r'<w:p\b.*?</w:p>', row, _re.S).group(0)


def test_r4_full_pass_leaves_numbered_header_and_single_ppr(tmp_path):
    # a header cell whose paragraph is a direct-numPr list must keep its numbering through the whole
    # table pass (cell_para -> header helper), not be flattened to Table Header.
    hdr = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="Normal"/>'
           '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr></w:pPr>'
           '<w:r><w:t>numbered head</w:t></w:r></w:p></w:tc></w:tr>')
    body = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
            '<w:r><w:t>data</w:t></w:r></w:p></w:tc></w:tr>')
    tbl = ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="dxa"/>'
           '<w:tblLook w:val="04A0"/></w:tblPr><w:tblGrid><w:gridCol w:w="5000"/></w:tblGrid>' + hdr + body + '</w:tbl>')
    c = _pkg(tmp_path, _H1 + tbl + _FMT_REV)
    hp = _first_header_para(c)
    assert '<w:numId w:val="7"/>' in hp                       # numbering kept
    assert 'TableHeader' not in hp                            # not reclassified
    assert hp.count('<w:pPr') == 1                            # exactly one paragraph-properties element


def test_r4_full_pass_self_closing_ppr_stays_single(tmp_path):
    hdr = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr/><w:r><w:t>plain head</w:t></w:r></w:p></w:tc></w:tr>')
    body = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
            '<w:r><w:t>data</w:t></w:r></w:p></w:tc></w:tr>')
    tbl = ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="dxa"/>'
           '<w:tblLook w:val="04A0"/></w:tblPr><w:tblGrid><w:gridCol w:w="5000"/></w:tblGrid>' + hdr + body + '</w:tbl>')
    c = _pkg(tmp_path, _H1 + tbl + _FMT_REV)
    hp = _first_header_para(c)
    assert hp.count('<w:pPr') == 1                            # never a second pPr from cell_para (R4)
    assert '<w:pStyle w:val="TableHeader"/>' in hp
    assert '<w:pPr/>' not in hp
