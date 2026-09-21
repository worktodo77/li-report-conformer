"""GPT audit F7: a report is conformed to the LI template matching its OWN page size. The operational
template.dotx is byte-identical to the authoritative Letter (LTR) July 2026 template; the A4 July 2026
template is a separate asset. select_template picks A4 for an A4 report, Letter otherwise. Fictitious."""
import os
import sys
from zipfile import ZipFile, ZIP_DEFLATED

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import (report_page_size, select_template,          # noqa: E402
                              LETTER_TEMPLATE_NAME, A4_TEMPLATE_NAME)

ASSETS = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets')

_A4 = '<w:pgSz w:w="11907" w:h="16839" w:code="9"/>'
_LETTER = '<w:pgSz w:w="12240" w:h="15840" w:code="9"/>'
_LETTER_LAND = '<w:pgSz w:w="15840" w:h="12240" w:orient="landscape" w:code="9"/>'


def _docx(tmp_path, pgsz):
    doc = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body><w:p/><w:sectPr>{pgsz}</w:sectPr></w:body></w:document>')
    p = tmp_path / 'r.docx'
    with ZipFile(p, 'w', ZIP_DEFLATED) as z:
        z.writestr('word/document.xml', doc)
    return str(p)


def test_page_size_detection(tmp_path):
    assert report_page_size(_docx(tmp_path, _A4)) == 'A4'
    assert report_page_size(_docx(tmp_path, _LETTER)) == 'Letter'


def test_landscape_first_section_is_derotated(tmp_path):
    # a report whose first section is landscape Letter must still read as Letter, not A4
    assert report_page_size(_docx(tmp_path, _LETTER_LAND)) == 'Letter'


def test_missing_pgsz_defaults_letter(tmp_path):
    assert report_page_size(_docx(tmp_path, '')) == 'Letter'


def test_select_template_picks_by_size(tmp_path):
    a4 = select_template(_docx(tmp_path, _A4), ASSETS)
    letter = select_template(_docx(tmp_path, _LETTER), ASSETS)
    assert os.path.basename(a4) == A4_TEMPLATE_NAME
    assert os.path.basename(letter) == LETTER_TEMPLATE_NAME
    assert os.path.exists(a4) and os.path.exists(letter)        # both assets are actually bundled


_LEGAL = '<w:pgSz w:w="12240" w:h="20160" w:code="5"/>'
_A3 = '<w:pgSz w:w="16838" w:h="23811"/>'


def test_non_a4_sizes_default_to_letter(tmp_path):
    # GPT self-review: an open-ended `h > 16340` classified US Legal / A3 as A4. Only a tight A4 window is A4.
    assert report_page_size(_docx(tmp_path, _LEGAL)) == 'Letter'
    assert report_page_size(_docx(tmp_path, _A3)) == 'Letter'


def test_majority_vote_ignores_one_stray_leading_section(tmp_path):
    # GPT self-review: trusting only the FIRST pgSz let one stray/corrupted leading section decide the
    # whole (all-Letter) report. A majority vote over all sections is used instead.
    body = ('<w:p/>'
            + ''.join(f'<w:p><w:pPr><w:sectPr>{_LETTER}</w:sectPr></w:pPr></w:p>' for _ in range(4))
            + f'<w:sectPr>{_A4}</w:sectPr>')      # one A4 section among four Letter
    doc = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body>{body}</w:body></w:document>')
    p = tmp_path / 'r.docx'
    with ZipFile(p, 'w', ZIP_DEFLATED) as z:
        z.writestr('word/document.xml', doc)
    assert report_page_size(str(p)) == 'Letter'


def test_select_falls_back_to_letter_when_a4_missing(tmp_path):
    empty = tmp_path / 'assets'
    empty.mkdir()
    (empty / LETTER_TEMPLATE_NAME).write_bytes(b'stub')
    picked = select_template(_docx(tmp_path, _A4), str(empty))   # A4 report but no A4 asset
    assert os.path.basename(picked) == LETTER_TEMPLATE_NAME
