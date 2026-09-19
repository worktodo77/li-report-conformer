"""Word-free tests for the render-verifier LOGIC (F6 + GPT re-review R6): every header cell's fill and
size is checked, font/bold/repeat are asserted, and an INCOMPLETE observation (missing property, mixed
size, read error, failed field update) is UNVERIFIED — a non-success gate result, never a silent pass.
read_render is monkeypatched so no Word is needed."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import render_verify as rv   # noqa: E402

_TEAL_BGR = 0xE8DDB6         # B6DDE8 as Word's BGR long
_NAVY_BGR = 0x8A4F05         # 054F8A as BGR


def _house_table(**over):
    """A fully-observed, fully-conforming house header (teal fill, 10pt, TNR, bold, repeats)."""
    t = {'style': 'Grid Table 4,LI Table', 'nested': False,
         'header_fills': [_TEAL_BGR, _TEAL_BGR], 'header_sizes': [10.0, 10.0],
         'header_fonts': ['Times New Roman', 'Times New Roman'], 'header_bold': [True, True],
         'header_repeats': True}
    t.update(over)
    return t


def _data(tables, fields=None):
    return {'ok': True, 'error': None, 'tables': tables, 'table_styles': [],
            'fields': fields or {}, 'lists': [], 'counts': {}, 'timing_ms': {}}


def _verify(monkeypatch, data):
    monkeypatch.setattr(rv, 'read_render', lambda *a, **k: data)
    return rv.verify('x')


def test_fully_observed_house_table_passes(monkeypatch):
    r = _verify(monkeypatch, _data([_house_table()]))
    assert r.passed and not r.fails and not r.unverified


def test_all_header_cells_size_checked_not_just_first(monkeypatch):
    r = _verify(monkeypatch, _data([_house_table(header_sizes=[10.0, 16.0])]))
    assert any(d['kind'] == 'table-header-size' for d in r.fails)


def test_all_header_cells_fill_checked_not_just_first(monkeypatch):
    # cell 1 teal, cell 2 navy: the second cell's wrong fill must be caught (R6 — not cell-1-only)
    r = _verify(monkeypatch, _data([_house_table(header_fills=[_TEAL_BGR, _NAVY_BGR])]))
    assert any(d['kind'] == 'table-header-navy' for d in r.fails)


def test_non_house_font_and_non_bold_fail(monkeypatch):
    r1 = _verify(monkeypatch, _data([_house_table(header_fonts=['Arial', 'Arial'])]))
    assert any(d['kind'] == 'table-header-font' for d in r1.fails)
    r2 = _verify(monkeypatch, _data([_house_table(header_bold=[True, False])]))
    assert any(d['kind'] == 'table-header-not-bold' for d in r2.fails)


def test_missing_observation_is_unverified_not_pass(monkeypatch):
    # a house table with NO size observation at all (and no fallback size) is UNVERIFIED, never a pass
    t = _house_table(); t.pop('header_sizes')
    r = _verify(monkeypatch, _data([t]))
    assert not r.passed
    assert any(d['kind'] == 'table-header-incomplete' for d in r.unverified)


def test_mixed_size_is_unverified_not_pass(monkeypatch):
    r = _verify(monkeypatch, _data([_house_table(header_sizes=[9999999])]))
    assert not any(d['kind'] == 'table-header-size' for d in r.fails)          # not a silent size fail...
    assert any(d['kind'] == 'table-header-size-unknown' for d in r.unverified)  # ...unverified
    assert not r.passed


def test_read_error_is_unverified(monkeypatch):
    r = _verify(monkeypatch, _data([_house_table(header_error='COM boom')]))
    assert any(d['kind'] == 'table-header-read-error' for d in r.unverified)
    assert not r.passed


def test_ref_error_counts(monkeypatch):
    r = _verify(monkeypatch, _data([], fields={'updated': True, 'update_ok': True,
                                               'pageref_total': 5, 'pageref_showing_1': 0,
                                               'ref_bookmark_errors': 2}))
    assert any(d['kind'] == 'ref-broken' for d in r.fails)


def test_failed_field_update_is_unverified_and_blocks(monkeypatch):
    r = _verify(monkeypatch, _data([], fields={'updated': True, 'update_ok': False}))
    assert any(d['kind'] == 'field-update-failed' for d in r.unverified)
    assert not r.passed


def test_non_repeating_header_is_review_only(monkeypatch):
    # a header row not marked to repeat is a review note, not a hard fail (a single-row table is fine)
    r = _verify(monkeypatch, _data([_house_table(header_repeats=False)]))
    assert any(d['kind'] == 'table-header-no-repeat' and d['severity'] == 'review' for d in r.defects)
    assert r.passed                                       # review alone does not block the gate
