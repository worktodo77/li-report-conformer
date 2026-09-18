"""Word-free tests for the render-verifier LOGIC (F6): all header cells are checked, mixed/unreadable
sizes are UNKNOWN not a pass, and both REF error strings count. read_render is monkeypatched so no Word
is needed."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import render_verify as rv   # noqa: E402

_TEAL_BGR = 0xE8DDB6         # B6DDE8 as Word's BGR long


def _data(tables, fields=None):
    return {'ok': True, 'error': None, 'tables': tables, 'table_styles': [],
            'fields': fields or {}, 'lists': [], 'counts': {}, 'timing_ms': {}}


def _verify(monkeypatch, data):
    monkeypatch.setattr(rv, 'read_render', lambda *a, **k: data)
    return rv.verify('x')


def test_all_header_cells_checked_not_just_first(monkeypatch):
    # cell 1 = 10pt, cell 2 = 16pt: must be flagged (the old first-cell-only read missed this)
    t = {'style': 'Grid Table 4,LI Table', 'nested': False,
         'header_cell1_fill_bgr': _TEAL_BGR, 'header_sizes': [10.0, 16.0]}
    r = _verify(monkeypatch, _data([t]))
    assert any(d['kind'] == 'table-header-size' for d in r.fails)


def test_mixed_size_is_unknown_not_pass(monkeypatch):
    t = {'style': 'Grid Table 4,LI Table', 'nested': False,
         'header_cell1_fill_bgr': _TEAL_BGR, 'header_sizes': [9999999]}
    r = _verify(monkeypatch, _data([t]))
    assert not any(d['kind'] == 'table-header-size' for d in r.fails)          # not a silent pass...
    assert any(d['kind'] == 'table-header-size-unknown' for d in r.defects)    # ...surfaced as unknown


def test_all_cells_10pt_passes(monkeypatch):
    t = {'style': 'Grid Table 4,LI Table', 'nested': False,
         'header_cell1_fill_bgr': _TEAL_BGR, 'header_sizes': [10.0, 10.0]}
    r = _verify(monkeypatch, _data([t]))
    assert not any(d['kind'].startswith('table-header-size') for d in r.defects)


def test_ref_error_counts(monkeypatch):
    r = _verify(monkeypatch, _data([], fields={'updated': True, 'update_ok': True,
                                               'pageref_total': 5, 'pageref_showing_1': 0,
                                               'ref_bookmark_errors': 2}))
    assert any(d['kind'] == 'ref-broken' for d in r.fails)


def test_failed_field_update_is_surfaced(monkeypatch):
    r = _verify(monkeypatch, _data([], fields={'updated': True, 'update_ok': False}))
    assert any(d['kind'] == 'field-update-failed' for d in r.defects)
