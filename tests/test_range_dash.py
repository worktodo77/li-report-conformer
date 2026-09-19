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
    assert typo_text('the period 2017-2019.') == f'the period 2017{EN}2019.'   # trailing sentence period OK


def test_ids_refs_and_range_exceptions_are_not_touched():
    for s in ('Table 3-1', 'Figure 5-2', '3.6.15-7', 'C-MT-MC-2020', 'M-H-27',
              '5-10 items', 'well-known', 'a 4-week window', 'pre-2020',
              'A7-14 days',              # activity id with an alphabetic left boundary
              '2017-2019A',              # id with an alphabetic right boundary
              'Table 2017-2019',         # a caption/reference number, not a date range
              '2017-2019.5',             # a decimal, not a year range
              'from 7-14 days',          # §8.2.1: no en dash after "from"
              'between 2017-2019 CD'):   # §8.2.1: no en dash after "between"
        assert typo_text(s) == s, s


EM = '—'


def test_em_dash_closed_up():
    assert typo_text(f'discretion {EM} and concurrency') == f'discretion{EM}and concurrency'
    assert typo_text(f'Contract  {EM} nothing') == f'Contract{EM}nothing'
    assert typo_text(f'a {EM} b {EM} c') == f'a{EM}b{EM}c'           # adjacent em dashes both close
    assert typo_text(f'already{EM}closed') == f'already{EM}closed'   # unchanged
    assert typo_text(f'{EM} start') == f'{EM} start'                 # edge dash left alone
    assert typo_text(EM) == EM                                       # standalone placeholder left alone
