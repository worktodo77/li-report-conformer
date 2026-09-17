"""P0-3 (D-2): a measurement is spelled out (2" -> 2-inch) in BODY prose only. It is a house-style edit,
NOT part of the shared typography transform, so it never rewrites a verbatim Excerpt/Quote or Caption, and
the whole-table item is never touched by the paragraph passes at all."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer, typo_text, house_ok   # noqa: E402


def test_typo_text_no_longer_spells_out_inches():
    # the shared gate/typography transform must NOT convert a measurement any more
    assert '-inch' not in typo_text('a 2" pipe')
    assert typo_text('a 2" pipe') == 'a 2” pipe'          # it only smart-quotes


def test_house_edit_spells_out_body_inches():
    assert Conformer._house_edit('a 2" pipe') == 'a 2-inch pipe'
    # and after typography has already smart-quoted the straight mark
    assert Conformer._house_edit('a 2” pipe') == 'a 2-inch pipe'


def test_house_gate_authorizes_the_inch_edit():
    assert house_ok('a 2" pipe', 'a 2-inch pipe')
    assert house_ok('a 2” pipe', 'a 2-inch pipe')


def test_excerpt_and_caption_styles_are_skipped_by_house_style():
    # the pass that carries the inch rule skips verbatim/quote styles, so an excerpt is never spelled out
    assert 'ExcerptorQuote' in Conformer._HOUSE_SKIP_STYLES
    assert 'Caption' in Conformer._HOUSE_SKIP_STYLES


def test_measurement_inside_a_quote_span_is_left_verbatim():
    # a double-quoted span is verbatim (HC-1): the inch rule does not reach inside it
    assert Conformer._house_edit('the spec "a 2" clearance" applies').count('-inch') == 0
