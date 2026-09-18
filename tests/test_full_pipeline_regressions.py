"""Full-pipeline regressions for the GPT audit findings (packages a real document from the bundled
template so the WHOLE Conformer.run() is exercised, not a single helper). No client data."""
import os
import re
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer            # noqa: E402
from conformer import tablespec                    # noqa: E402

_TPL = Path(__file__).resolve().parents[1] / 'src' / 'conformer' / 'assets' / 'template.dotx'

_HEADING = ('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>INTRODUCTION</w:t></w:r></w:p>')


def _table(body_sz='18'):
    """A clean two-row table: a header row + a body row at a smaller (body_sz) font."""
    hdr = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
           '<w:r><w:t>Head</w:t></w:r></w:p></w:tc></w:tr>')
    body = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="{body_sz}"/></w:rPr><w:t>data</w:t></w:r></w:p></w:tc></w:tr>')
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="dxa"/>'
            '<w:tblLook w:val="04A0"/></w:tblPr><w:tblGrid><w:gridCol w:w="5000"/></w:tblGrid>'
            + hdr + body + '</w:tbl>')


def _package(tmp_path, body):
    with ZipFile(_TPL) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts['[Content_Types].xml'] = parts['[Content_Types].xml'].replace(
        b'wordprocessingml.template.main+xml', b'wordprocessingml.document.main+xml')
    xml = parts['word/document.xml'].decode('utf-8')
    sect = re.findall(r'<w:sectPr\b.*?</w:sectPr>', xml, re.S)[-1]
    parts['word/document.xml'] = re.sub(
        r'<w:body>.*</w:body>', lambda _: '<w:body>' + body + sect + '</w:body>', xml, flags=re.S
    ).encode('utf-8')
    src = tmp_path / 'in.docx'
    with ZipFile(src, 'w', ZIP_DEFLATED) as z:
        for n, data in parts.items():
            z.writestr(n, data)
    return str(src), str(_TPL)


def test_f1_clean_path_keeps_table_header_style(tmp_path):
    """F1: the clean pipeline added TableHeader in fix_tables() then replace_parts() wiped it, so the
    output referenced a style it no longer defined (Word rendered 12pt) and still verdicted CLEAN."""
    src, tpl = _package(tmp_path, _HEADING + _table())
    c = Conformer(tpl, src)
    c.run()
    hdr_row = re.search(r'<w:tbl>.*?<w:tr\b.*?</w:tr>', ''.join(c.items), re.S).group(0)
    assert '<w:pStyle w:val="TableHeader"/>' in hdr_row        # header uses the 10pt style
    assert 'w:styleId="TableHeader"' in c.styles               # ...and the style is DEFINED in the output


def test_f1_verifier_flags_header_paragraph_style_missing_from_styles():
    """Defense in depth: a header cell paragraph referencing a style absent from styles.xml is a defect,
    not a silent pass."""
    styles = '<w:styles><w:style w:type="paragraph" w:styleId="TableData"><w:rPr><w:sz w:val="22"/></w:rPr></w:style></w:styles>'
    tbl = ('<w:tbl><w:tblPr><w:tblStyle w:val="GridTable4"/><w:tblLook w:val="04A0" w:firstRow="1"/></w:tblPr>'
           '<w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:tcPr>'
           '<w:shd w:val="clear" w:color="auto" w:fill="B6DDE8"/></w:tcPr>'
           '<w:p><w:pPr><w:pStyle w:val="TableHeader"/></w:pPr><w:r><w:t>H</w:t></w:r></w:p></w:tc></w:tr>'
           '<w:tr><w:tc><w:tcPr/><w:p><w:r><w:t>d</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    kinds = {i['kind'] for i in tablespec.effective_table_issues(tbl, styles_xml=styles)}
    assert 'header-style-missing' in kinds


def test_f5_broken_references_gate_clean():
    """F5: a known broken cross-reference (missing target) is a genuine unresolved defect that a field
    refresh cannot fix, so the verdict must not be CLEAN."""
    c = Conformer.__new__(Conformer)
    c.audit = [('xref-target-missing', '3 cross-reference(s) point to a missing bookmark')]
    empty = {'numbering_flips': [], 'definition_integrity_violations': [],
             'tables_failing_effective_format': [], 'tables_review': []}
    empty_u = {'rolled_back_passes': [], 'tables_needing_review': [], 'tables_unresolved': []}
    c.outcome_report = lambda: {'conformance': empty, 'unresolved': empty_u}
    st = c.conformance_status()
    assert st['clean'] is False
    assert st['reasons']['broken_references']


def test_f5_advisory_audits_do_not_gate_clean():
    # a caption-basis / heading-skip advisory (not a broken ref) stays out of the verdict
    c = Conformer.__new__(Conformer)
    c.audit = [('basis-not-h1h2', 'Table caption uses a Heading 3 basis'), ('heading-skip', 'H4 -> H6')]
    empty = {'numbering_flips': [], 'definition_integrity_violations': [],
             'tables_failing_effective_format': [], 'tables_review': []}
    empty_u = {'rolled_back_passes': [], 'tables_needing_review': [], 'tables_unresolved': []}
    c.outcome_report = lambda: {'conformance': empty, 'unresolved': empty_u}
    assert c.conformance_status()['clean'] is True
