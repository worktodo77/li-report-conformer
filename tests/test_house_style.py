"""Deterministic LI house-style pass (docs/LI_STYLE_GUIDE.md [DET] rules).

Covers the per-token transforms, the gate authorization (house_ok), and a preserve-mode integration
where house style is applied to clean prose while a tracked change is preserved. Fictitious content.
"""
import os
import re
import tempfile
import zipfile

from conformer.engine import Conformer, house_ok, house_norm  # noqa: F401

ASSETS = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets')
TEMPLATE = os.path.join(ASSETS, 'template.dotx')
he = Conformer._house_edit
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = (f'xmlns:w="{W}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
      'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml" '
      'xmlns:w16cid="http://schemas.microsoft.com/office/word/2016/wordml/cid" '
      'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"')


def test_lowercase_generic_after_determiner():
    assert he('The Contractor shall notify the Owner.') == 'The contractor shall notify the owner.'
    assert he('the Total Float and the Critical Path') == 'the total float and the critical path'


def test_sentence_initial_generic_not_lowered():
    # a term with no preceding determiner (genuinely sentence-initial) keeps its capital
    assert he('Contractor delays are common.') == 'Contractor delays are common.'
    assert he('Float belongs to the project.').startswith('Float belongs')


def test_report_project_capitalized():
    assert he('We reviewed the project and this report.') == 'We reviewed the Project and this Report.'
    # Report/Project stay capital and are not lowered by the generic rule
    assert he('The Report and the Project are done.') == 'The Report and the Project are done.'


def test_terminology_and_spelling():
    assert he('The programme was analysed using the matrices.') == \
        'The schedule was analyzed using the matrixes.'
    assert he('behaviour, colour, organisation') == 'behavior, color, organization'


def test_currency_prefix_and_eg_preserved():
    assert he('The sum was US$212,400,000.') == 'The sum was US$212,400,000.'   # currency untouched
    assert he('i.e., a windows analysis') == 'i.e., a windows analysis'          # no double comma
    assert he('e.g. the owner') == 'e.g., the owner'
    assert he('the USA and U.S.A.') == 'the U.S. and U.S.'


def test_acronym_plural():
    assert he("the EOT's and RFI's") == 'the EOTs and RFIs'


def test_quotation_span_untouched():
    # a defined-term capital inside a quotation is preserved (HC-1)
    assert he('The contract defines "the Contractor" as a Party.') == \
        'The contract defines "the Contractor" as a party.'   # only the unquoted "a Party" changes


def test_house_ok_gate():
    assert house_ok('The Contractor notified the Owner.', he('The Contractor notified the Owner.'))
    assert not house_ok('the contractor increased scope', 'the contractor reduced scope')
    assert not house_ok('the delay was 30 days', 'the delay was 40 days')


# ---- preserve-mode integration: house style on clean prose, tracked change preserved ----
def _make_docx(path, body):
    def part(tag, inner=''):
        return f'<?xml version="1.0"?><w:{tag} {NS}>{inner}</w:{tag}>'.encode()
    parts = {
        '[Content_Types].xml': b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/></Types>',
        '_rels/.rels': b'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        'word/document.xml': f'<?xml version="1.0"?><w:document {NS}><w:body>{body}</w:body></w:document>'.encode(),
        'word/styles.xml': part('styles', '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style><w:style w:type="paragraph" w:styleId="NumberedParagraph"><w:name w:val="Numbered Paragraph"/></w:style>'),
        'word/numbering.xml': part('numbering'),
        'word/footnotes.xml': part('footnotes'),
        'word/settings.xml': part('settings'),
    }
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)


def test_preserve_mode_house_style_applies_and_preserves_tracked():
    body = (
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>OPINION</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:pStyle w:val="NumberedParagraph"/></w:pPr>'
        '<w:r><w:t xml:space="preserve">In my opinion the Contractor delayed the Owner, and the programme slipped. </w:t></w:r>'
        '<w:ins w:id="1" w:author="Ann" w:date="2026-01-02T00:00:00Z">'
        '<w:r><w:t xml:space="preserve">the Contractor disputes this</w:t></w:r></w:ins></w:p>'
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>')
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'r.docx')
        _make_docx(p, body)
        c = Conformer(TEMPLATE, p)
        c.run()
        assert c.disposition == 'preserve'
        out = ''.join(c.items)
        # settled prose is house-styled: "the Contractor"->"the contractor", programme->schedule
        assert 'the contractor delayed the owner' in out
        assert 'the schedule slipped' in out
        # the tracked insertion's text is masked -> untouched (still "the Contractor"), author intact
        assert '<w:ins' in out and 'the Contractor disputes this' in out and 'w:author="Ann"' in out
        clean, disc = c.verify_preservation()
        assert clean, disc
        assert not any(name == 'house_style' for name, _ in c.exceptions)
