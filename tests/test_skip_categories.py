"""Every conformance ledger row must be skippable: a row carries a category and the engine honors
decisions['conf:<cat>']=='skip'. Regression for the cross-reference styling and updateFields passes,
which previously ran unconditionally (no Skip)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402


def test_crossref_pass_is_skippable():
    c = Conformer.__new__(Conformer)
    c.decisions = {'conf:crossref': 'skip'}
    assert c._style_crossreferences() == (0, 0)     # skipped -> no work, no styling


def test_update_fields_pass_is_skippable():
    c = Conformer.__new__(Conformer)
    c.decisions = {'conf:update-fields': 'skip'}
    c.settings = '<w:settings></w:settings>'
    c.audit = [('a', 'b')]
    c.force_field_update()
    assert 'updateFields' not in c.settings          # skipped -> field refresh NOT armed


def test_update_fields_runs_when_not_skipped():
    c = Conformer.__new__(Conformer)
    c.decisions = None                               # analyze: nothing skipped
    c.settings = '<w:settings></w:settings>'
    c.audit = [('a', 'b')]
    c.say = lambda *a, **k: None
    c.force_field_update()
    assert '<w:updateFields w:val="true"/>' in c.settings
