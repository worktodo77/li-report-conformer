"""PUNC-2 / NUM-4: en dash for number/date ranges — scoped so caption numbers, activity IDs and other
hyphenated tokens common in schedule reports are never touched."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import typo_text   # noqa: E402

EN = '–'


def test_ranges_get_en_dash():
    assert typo_text('7-14 days') == f'7{EN}14 days'
    assert typo_text('11-91 CD') == f'11{EN}91 CD'
    assert typo_text('31-60 calendar days') == f'31{EN}60 calendar days'
    assert typo_text('over 2017-2019 the schedule') == f'over 2017{EN}2019 the schedule'
    assert typo_text('2020-2022') == f'2020{EN}2022'


def test_ids_and_refs_are_not_touched():
    for s in ('Table 3-1', 'Figure 5-2', '3.6.15-7', 'C-MT-MC-2020', 'M-H-27',
              '5-10 items', 'well-known', 'a 4-week window', 'pre-2020'):
        assert typo_text(s) == s, s
