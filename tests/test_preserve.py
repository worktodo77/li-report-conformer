"""M2 review-preserving pipeline: transactional per-pass rollback + conservative conformance.

Builds a tiny synthetic revised .docx (no client data) with one clean paragraph and one revised
paragraph, and asserts: preserve mode activates, every tracked change survives, the clean paragraph
is conformed while the revised one is left alone, and a pass that would disturb a revision is rolled
back and recorded as an exception.
"""
import os
import tempfile
import zipfile

import pytest

from conformer.engine import Conformer

ASSETS = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets')
TEMPLATE = os.path.join(ASSETS, 'template.dotx')

WNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

DOC_BODY = (
    '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>INTRODUCTION</w:t></w:r></w:p>'
    # clean, non-LI style -> classify should conform it in preserve mode
    '<w:p><w:pPr><w:pStyle w:val="MyBody"/></w:pPr>'
    '<w:r><w:t>This paragraph has no tracked changes at all.</w:t></w:r></w:p>'
    # revised paragraph: an insertion whose text carries a straight quote, so typography WOULD
    # alter the inserted payload -> the gate must roll typography back.
    '<w:p><w:pPr><w:pStyle w:val="MyBody"/></w:pPr>'
    '<w:r><w:t xml:space="preserve">The plaintiff </w:t></w:r>'
    '<w:ins w:id="1" w:author="Ann" w:date="2026-01-02T00:00:00Z">'
    '<w:r><w:t xml:space="preserve">said "yes"</w:t></w:r></w:ins></w:p>'
    '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>'
)


def _part(tag, inner=''):
    return f'<?xml version="1.0"?><w:{tag} {WNS}>{inner}</w:{tag}>'.encode('utf8')


def _make_docx(path, body):
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
        'word/document.xml': f'<?xml version="1.0"?><w:document {WNS}><w:body>{body}</w:body></w:document>'.encode('utf8'),
        'word/styles.xml': _part('styles',
            '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>'
            '<w:style w:type="paragraph" w:styleId="MyBody"><w:name w:val="My Body"/></w:style>'),
        'word/numbering.xml': _part('numbering'),
        'word/footnotes.xml': _part('footnotes'),
        'word/settings.xml': _part('settings'),
    }
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)


@pytest.fixture
def revised_docx():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'revised.docx')
        _make_docx(p, DOC_BODY)
        yield p


def test_preserve_mode_activates_and_preserves_every_revision(revised_docx):
    c = Conformer(TEMPLATE, revised_docx)
    c.run()
    assert c.disposition == 'preserve'
    clean, disc = c.verify_preservation()
    assert clean, disc
    # the insertion (id/author/text) still present, unaltered
    out = ''.join(c.items)
    assert 'w:author="Ann"' in out and 'said &quot;yes&quot;' in out or 'said "yes"' in out


def test_preserve_conforms_styles_incl_revised_paragraph(revised_docx):
    c = Conformer(TEMPLATE, revised_docx)
    c.run()
    styles = [c.style(i) for i in range(c.n()) if c.is_par(i)]
    # both the clean and the revised 'MyBody' paragraphs get an LI style (pStyle is orthogonal to
    # the tracked content), and no paragraph is left on the non-LI 'MyBody' style.
    assert 'MyBody' not in styles
    # ...while the insertion (author + text) is still intact and preservation is clean
    clean, disc = c.verify_preservation()
    assert clean, disc
    out = ''.join(c.items)
    assert 'w:author="Ann"' in out


def test_preserve_typography_is_revision_safe(revised_docx):
    c = Conformer(TEMPLATE, revised_docx)
    c.run()
    # typography is no longer rolled back (it masks revision text), and the inserted quote keeps its
    # straight quotes (the payload was not rewritten).
    assert not any(name == 'typography' for name, _ in c.exceptions), c.exceptions
    out = ''.join(c.items)
    assert 'said "yes"' in out
    clean, _ = c.verify_preservation()
    assert clean


def test_preserve_gate_catches_and_rollback_restores(revised_docx):
    import re
    c = Conformer(TEMPLATE, revised_docx)
    c.disposition = 'preserve'
    snap = c._snapshot()
    for i in range(c.n()):                       # simulate a pass that drops the insertion
        if 'w:author="Ann"' in c.item(i):
            c.set(i, re.sub(r'<w:ins\b.*?</w:ins>', '', c.item(i), flags=re.S))
    clean, disc = c.verify_preservation()
    assert not clean and disc['lost']            # the gate catches the lost edit
    c._restore(snap)
    clean2, _ = c.verify_preservation()
    assert clean2                                # rollback fully restores


def test_clean_document_uses_legacy_pipeline(revised_docx):
    # a doc with the insertion removed has no revisions -> legacy pipeline, no preserve overhead
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'clean.docx')
        _make_docx(p, DOC_BODY.replace(
            '<w:ins w:id="1" w:author="Ann" w:date="2026-01-02T00:00:00Z">'
            '<w:r><w:t xml:space="preserve">said "yes"</w:t></w:r></w:ins>', ''))
        c = Conformer(TEMPLATE, p)
        c.run()
        assert c.disposition is None
        assert c.exceptions == []
