"""NUM-2: in body prose a percentage is spelled 'N percent' (numeral kept); '%' is allowed in tables,
which house_style never touches (they are not paragraphs). Quoted text is left verbatim (HC-1)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer, house_norm   # noqa: E402


def test_percent_spelled_in_prose():
    assert Conformer._house_edit('the schedule was 60% complete') == 'the schedule was 60 percent complete'
    assert Conformer._house_edit('15.5% variance and 90 % done') == '15.5 percent variance and 90 percent done'


def test_quoted_percent_left_verbatim():
    assert Conformer._house_edit('the term “30%” here') == 'the term “30%” here'


def test_gate_authorizes_percent():
    # house_norm canonicalizes both forms identically, so the content-stream gate permits the edit
    assert house_norm('60%') == house_norm('60 percent')
    assert house_norm('a 15.5% rise') == house_norm('a 15.5 percent rise')
