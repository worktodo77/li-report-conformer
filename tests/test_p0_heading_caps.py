"""P0-2: heading capitalization policy (guideline §3). The engine NEVER adds a display <w:caps/> (it breaks
TOC/PDF-bookmark casing); it honors the documented H2 initial-caps exception when applied consistently and
flags inconsistent/wrong casing instead of forcing a text change in the review-preserving pipeline."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402


def _c(items):
    c = Conformer.__new__(Conformer)
    c.items = items
    c.b0 = 0
    c._gen = 0
    c._log = []
    c.say = lambda kind, i, msg, cat=None: c._log.append((kind, i, msg))
    return c


def _h(style, text):
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'


def test_never_adds_caps_attribute():
    c = _c([_h('Heading1', 'INTRODUCTION'), _h('Heading2', 'Analysis of Delay')])
    c._heading_caps_preserving()
    assert '<w:caps/>' not in ''.join(c.items)     # the P0-2 fix: never add display caps


def test_consistent_initial_caps_h2_preserved_and_unflagged():
    c = _c([_h('Heading2', 'Analysis of Delay'), _h('Heading2', 'Assessment of Loss')])
    before = list(c.items)
    c._heading_caps_preserving()
    assert c.items == before                       # the honored exception -> no change
    assert not any('Heading 2' in m for _, _, m in c._log)


def test_consistent_all_caps_h2_unflagged():
    c = _c([_h('Heading2', 'ANALYSIS OF DELAY'), _h('Heading2', 'ASSESSMENT OF LOSS')])
    c._heading_caps_preserving()
    assert not any('Heading 2' in m for _, _, m in c._log)


def test_mixed_h2_casing_flagged():
    c = _c([_h('Heading2', 'ANALYSIS'), _h('Heading2', 'Assessment of Loss')])
    c._heading_caps_preserving()
    assert any('INCONSISTENT' in m for _, _, m in c._log)


def test_lowercase_h1_flagged_not_changed():
    c = _c([_h('Heading1', 'Introduction')])
    before = list(c.items)
    c._heading_caps_preserving()
    assert c.items == before                       # flagged, not force-recased (preservation)
    assert any('Heading 1' in m and 'ALL CAPS' in m for _, _, m in c._log)


def test_allcaps_h1_unflagged():
    c = _c([_h('Heading1', 'INTRODUCTION')])
    c._heading_caps_preserving()
    assert not any('Heading 1' in m for _, _, m in c._log)
