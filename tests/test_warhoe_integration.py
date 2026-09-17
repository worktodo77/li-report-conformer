"""Warhoe integration regression — LOCAL ONLY. The original Warhoe report is privileged client data and
is NEVER committed; this test reads it from $WARHOE_DOCX or the known Desktop path and SKIPS if absent.
It regenerates from the ORIGINAL (not the damaged output) and asserts the coordinated correction on the
real file: 0 list-meaning flips, definition integrity, preservation clean, meaning-bearing formatting
kept, and a second conform is idempotent for numbering.

Run deliberately (it conforms the full report, ~1-2 min each): pytest -q tests/test_warhoe_integration.py
"""
import os
import re
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer               # noqa: E402

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets', 'template.dotx')
_CANDIDATES = [
    os.environ.get('WARHOE_DOCX'),
    r"C:\Users\Alex\Desktop\Project 499 - Warhoe Draft Expert Report - Petrobras_090626 New Master.docx",
]


def _warhoe():
    for p in _CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


pytestmark = pytest.mark.skipif(_warhoe() is None,
                                reason="Warhoe original not available locally (client data; not committed)")


def _conform(path):
    c = Conformer(TEMPLATE, path)
    c.run()
    return c


def test_warhoe_numbering_and_integrity():
    c = _conform(_warhoe())
    # no UNINTENDED flips (intended house repairs of dysfunctional list styles are allowed and recorded)
    unintended = [x for x in c.numbering_report() if not x.get('intended')]
    assert unintended == [], f"unintended list-meaning flips (decimal<->bullet regression): {unintended}"
    assert c.definition_integrity_report() == []
    rep = c.outcome_report()
    assert rep['preservation']['clean'] is True, rep['preservation']
    ok, msg = c.validate_output()
    assert ok, msg


def test_warhoe_preserves_meaning_bearing_formatting():
    # Per-carrier invariant across the DOCUMENT AND FOOTNOTES, comparing the property VALUE (subscript vs
    # superscript, single vs double strike), not merely the presence of a property type on some text. Every
    # (text, value) carrier in the source must still be present in the output — no subscript/superscript/
    # strike is silently normalised away, and none is silently changed to a different value.
    import zipfile
    orig = _warhoe()
    zin = zipfile.ZipFile(orig)
    src = zin.read('word/document.xml').decode('utf8') + zin.read('word/footnotes.xml').decode('utf8')
    c = _conform(orig)
    out = (c.head + ''.join(c.items) + c.tail) + c.fn      # conformed document + footnotes

    def carriers(doc, prop):
        # (text, value) for every run bearing the property, so the VALUE is compared, footnotes included
        pat = (r'<w:r\b[^>]*>(?:(?!</w:r>).)*?<w:%s\b[^>]*?(?:w:val="([^"]*)")?[^>]*/>'
               r'(?:(?!</w:r>).)*?<w:t[^>]*>([^<]+)</w:t>' % prop)
        return {(txt.strip(), (val or '')) for val, txt in re.findall(pat, doc, re.S) if txt.strip()}

    for prop in ('vertAlign', 'strike', 'dstrike'):
        lost = carriers(src, prop) - carriers(out, prop)
        assert lost == set(), f"{prop}: carrier(s) lost/changed after conforming: {sorted(lost)[:5]}"


def test_warhoe_idempotent_numbering():
    d = tempfile.mkdtemp()
    out1 = os.path.join(d, 'w1.docx')
    c1 = _conform(_warhoe()); c1.save(out1)
    c2 = _conform(out1)
    assert [x for x in c2.numbering_report() if not x.get('intended')] == []
    assert c2.definition_integrity_report() == []
