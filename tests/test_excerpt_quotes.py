"""§5: a block-quote excerpt is set off by its own style, so surrounding quotation marks are redundant.
A self-contained excerpt (opens AND closes with a quote) is offered as a judgment call to strip the outer
pair; the verbatim text between is untouched. A quote that only OPENS is left alone (ambiguous close)."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402


def _text(x):
    return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', x))


def _excerpt(text):
    return ('<w:p><w:pPr><w:pStyle w:val="ExcerptorQuote"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>')


def test_strip_leading_and_trailing_quote_helpers():
    c = Conformer.__new__(Conformer)
    c.items = [_excerpt('“quoted text.”')]
    c.b0 = 0
    c._strip_leading_quote(0)
    c._strip_trailing_quote(0)
    assert _text(c.items[0]) == 'quoted text.'          # outer smart quotes removed, period kept


def _pass_conformer(items):
    c = Conformer.__new__(Conformer)
    c.items = items
    c.b0 = 0
    c.decisions = None                                  # analyze: default accept
    c.pending_judgments = []
    c._jcall_counter = 0
    c.log = []
    c.judgment = []
    c.exceptions = []
    c.verify_preservation = lambda: (True, None)
    c._snapshot = lambda: list(c.items)
    c._restore = lambda s: None
    return c


def test_self_contained_excerpt_stripped_opens_only_left():
    c = _pass_conformer([
        _excerpt('“A fully self-contained quotation.”'),   # opens AND closes -> strip
        _excerpt('“A quote that only opens here'),               # opens only -> leave
        _excerpt('ordinary excerpt text without quotes.'),           # no quotes -> leave
    ])
    c._strip_excerpt_quotes_preserving()
    assert len([j for j in c.pending_judgments if j.kind == 'excerpt-quotes']) == 1
    assert _text(c.items[0]) == 'A fully self-contained quotation.'
    assert _text(c.items[1]) == '“A quote that only opens here'   # unchanged
    assert _text(c.items[2]) == 'ordinary excerpt text without quotes.'


def test_skip_flag_leaves_excerpt_quotes():
    c = _pass_conformer([_excerpt('“Keep these quotes.”')])
    c.decisions = {'excerpt-quotes_1': 'skip'}           # user skipped this judgment call
    c._strip_excerpt_quotes_preserving()
    assert _text(c.items[0]) == '“Keep these quotes.”'      # left as-is
