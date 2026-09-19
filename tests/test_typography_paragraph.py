"""GPT re-review R2: typography must protect quoted source wording and honour the §8.2.1 from/between
range exception across run boundaries. typo_text alone (per token) covers the quote-interior and the
single-run from case; the cross-run from case is covered by the typography pass. Fictitious content."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import typo_text, Conformer   # noqa: E402

LQ, RQ = '“', '”'
ENDASH = '–'


def test_quoted_date_interior_is_verbatim():
    # the quoted date must NOT be normalized; the delimiters are still smart-quoted
    assert typo_text('He said "03 April 2011".') == f'He said {LQ}03 April 2011{RQ}.'
    # ...but an UNQUOTED date is still normalized
    assert typo_text('on 03 April 2011') == 'on 3 April 2011'


def test_quoted_range_verbatim_but_unquoted_range_gets_endash():
    assert typo_text('see "2017-2019" values') == f'see {LQ}2017-2019{RQ} values'
    assert typo_text('spanning 2017-2019') == f'spanning 2017{ENDASH}2019'


def test_from_between_exception_single_run():
    assert typo_text('from 2017-2019') == 'from 2017-2019'
    assert typo_text('between 2017-2019') == 'between 2017-2019'


# ── cross-run from/between exception through the typography pass ──
def _para_typography(items):
    c = Conformer.__new__(Conformer)
    c.items = list(items); c.b0 = 0
    c.disposition = None
    c.log = []; c.judgment = []
    c._skip = lambda *a: False
    # _apply_text_edit in clean mode just needs to set the item; stub the bookkeeping it calls
    def _apply(kind, label, i, before, after):
        c.set(i, after); return True
    c._apply_text_edit = _apply
    c.say = lambda *a, **k: None
    c.typography()
    return c


def _text(x):
    return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', x))


def test_cross_run_from_range_gets_no_endash():
    # "from " ends run 1; the range is the (bold) run 2 — the exception must still apply
    p = ('<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
         '<w:r><w:t xml:space="preserve">the period from </w:t></w:r>'
         '<w:r><w:rPr><w:b/></w:rPr><w:t>2017-2019</w:t></w:r></w:p>')
    c = _para_typography([p])
    assert _text(c.item(0)) == 'the period from 2017-2019'          # no en dash across the boundary
    assert ENDASH not in c.item(0)


def test_cross_run_plain_range_still_gets_endash():
    # a range NOT introduced by from/between is still normalized across runs
    p = ('<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
         '<w:r><w:t xml:space="preserve">the period </w:t></w:r>'
         '<w:r><w:rPr><w:b/></w:rPr><w:t>2017-2019</w:t></w:r></w:p>')
    c = _para_typography([p])
    assert _text(c.item(0)) == f'the period 2017{ENDASH}2019'
