"""P1 (§3/§4): audit_headings flags a heading that SKIPS a level (H1 -> H3 with no H2) and a
numbered-paragraph sublist that starts above L1 or jumps a sublevel."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402


def _c(items):
    c = Conformer.__new__(Conformer)
    c.items = items
    c.b0 = 0
    c.audit = []
    c._log = []
    c.say = lambda kind, i, msg, cat=None: c._log.append((kind, i, msg))
    return c


def _p(style, text='x'):
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'


def _kinds(findings):
    return {k for k, _ in findings}


def test_proper_heading_tree_is_clean():
    c = _c([_p('Heading1'), _p('Heading2'), _p('Heading3'), _p('Heading2'), _p('Heading3'), _p('Heading1')])
    assert c.audit_headings() == []


def test_heading_level_skip_flagged():
    c = _c([_p('Heading1'), _p('Heading3')])          # H1 -> H3, no H2
    assert 'heading-skip' in _kinds(c.audit_headings())


def test_deeper_then_back_is_ok():
    c = _c([_p('Heading1'), _p('Heading2'), _p('Heading3'), _p('Heading1'), _p('Heading2')])
    assert c.audit_headings() == []


def test_sublevel_starting_at_l2_flagged():
    c = _c([_p('NumberedParagraph'), _p('NumberedParagraphL2')])   # starts at "a" not "1"
    assert 'sublevel-skip' in _kinds(c.audit_headings())


def test_sublevel_sequential_is_clean():
    c = _c([_p('NumberedParagraphL1'), _p('NumberedParagraphL2'), _p('NumberedParagraphL3')])
    assert 'sublevel-skip' not in _kinds(c.audit_headings())


def test_sublevel_jump_l1_to_l3_flagged():
    c = _c([_p('NumberedParagraphL1'), _p('NumberedParagraphL3')])
    assert 'sublevel-skip' in _kinds(c.audit_headings())
