"""Regression reproductions for the corrective-work review (GitHub issue #1, findings R1-R7). Each test
encodes a documented counterexample that must FAIL before its fix and PASS after. Gates are never
weakened and unresolved results are never treated as conformant."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'synthetic'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


# ---------------------------------------------------------------- R7: highlight decision honesty
def test_r7_per_item_keep_survives_remove_all():
    import os as _os
    _os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from conformer.engine import JudgmentCall
    from conformer.ui.window import MainWindow, _ClickFrame  # noqa: F401
    mw = MainWindow.__new__(MainWindow)
    calls = [JudgmentCall(id=f'highlight_{i}', kind='highlight', item_index=i, full_text=f'm{i}',
                          short_text=f'm{i}', message='Yellow highlight.', recommended_action='Remove')
             for i in range(5)]
    mw.highlight_calls = calls
    mw.highlight_decision = {}
    # bulk remove, then explicitly KEEP item 2
    mw._set_all_highlights(True)
    mw._set_highlight(calls[2].id, False)
    dec = mw._highlight_decisions()
    assert dec['highlight_2'] == 'skip', 'a per-item keep must survive Remove-all'
    assert dec['highlight_0'] == 'accept' and dec['highlight_4'] == 'accept'
    # bulk undo restores keep for all
    mw._set_all_highlights(False)
    assert set(mw._highlight_decisions().values()) == {'skip'}


def test_r7_grouped_highlight_decisions_reach_the_audit():
    from conformer.ui.window import MainWindow
    from conformer.engine import JudgmentCall
    mw = MainWindow.__new__(MainWindow)
    calls = [JudgmentCall(id='highlight_1', kind='highlight', item_index=1, full_text='marker',
                          short_text='marker', message='Yellow highlight.', recommended_action='Remove')]
    mw.highlight_calls = calls
    mw.highlight_decision = {'highlight_1': True}   # user chose remove
    rows = mw._highlight_decision_log()
    assert any(r.get('status') == 'REMOVED' and 'highlight' in r.get('action', '').lower() for r in rows), rows
