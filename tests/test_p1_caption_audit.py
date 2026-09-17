"""P1 (§8.6): audit_captions verifies Table AND Figure caption numbering — a single consistent basis that
is Heading 1 or 2 (flagged, never auto-renumbered, per D-1), and per-section sequential SEQ results
(catching the stale/duplicate/gapped cached fields). audit_figures previously skipped Table captions."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402


def _fld(instr, result):
    return ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> {instr} </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r><w:t>{result}</w:t></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>')


def _cap(kind, basis, section, seq, title='Title', fielded=True):
    inner = f'<w:r><w:t xml:space="preserve">{kind} </w:t></w:r>'
    if fielded:
        inner += _fld(f'STYLEREF {basis} \\s', section)
        inner += '<w:r><w:t>-</w:t></w:r>'
        inner += _fld(f'SEQ {kind} \\* ARABIC \\s {basis}', seq)
    else:
        inner += f'<w:r><w:t>{section}-{seq}</w:t></w:r>'   # static text, no field
    inner += f'<w:r><w:t xml:space="preserve">: {title}</w:t></w:r>'
    return f'<w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr>{inner}</w:p>'


def _c(items):
    c = Conformer.__new__(Conformer)
    c.items = items
    c.b0 = 0
    c.audit = []
    c._log = []
    c.say = lambda kind, i, msg, cat=None: c._log.append((kind, i, msg))
    return c


def _kinds(findings):
    return {k for k, _ in findings}


def test_consistent_h1_sequential_is_clean():
    c = _c([_cap('Table', 1, '1', '1'), _cap('Table', 1, '1', '2'), _cap('Table', 1, '2', '1')])
    f = c.audit_captions()
    assert f == [], f


def test_heading3_basis_flagged_not_renumbered():
    c = _c([_cap('Table', 3, '3.4.2', '1'), _cap('Table', 3, '3.4.2', '2')])
    f = c.audit_captions()
    assert 'basis-not-h1h2' in _kinds(f)
    # flagged only — the caption text/fields are untouched
    assert c.items == [_cap('Table', 3, '3.4.2', '1'), _cap('Table', 3, '3.4.2', '2')]


def test_inconsistent_basis_within_kind_flagged():
    c = _c([_cap('Table', 1, '1', '1'), _cap('Table', 2, '1.1', '1')])
    assert 'basis-inconsistent' in _kinds(c.audit_captions())


def test_stale_sequence_flagged():
    # section '1' has cached 1,2,2 (a duplicate) -> stale
    c = _c([_cap('Table', 1, '1', '1'), _cap('Table', 1, '1', '2'), _cap('Table', 1, '1', '2')])
    assert 'seq-stale' in _kinds(c.audit_captions())


def test_cross_kind_basis_mismatch_flagged():
    c = _c([_cap('Table', 3, '3.4.2', '1'), _cap('Figure', 1, '3', '1')])
    assert 'basis-cross-kind' in _kinds(c.audit_captions())


def test_static_caption_flagged_not_fielded():
    c = _c([_cap('Table', 1, '1', '1', fielded=False)])
    assert 'not-fielded' in _kinds(c.audit_captions())
