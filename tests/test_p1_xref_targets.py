"""P1 (§9): audit_crossref_targets flags a REF field whose target bookmark is absent from the document."""
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


def _ref(target):
    return ('<w:p><w:r><w:instrText xml:space="preserve"> REF ' + target + ' \\h </w:instrText></w:r>'
            '<w:r><w:t>x</w:t></w:r></w:p>')


def _bookmark(name):
    return f'<w:p><w:bookmarkStart w:id="1" w:name="{name}"/><w:r><w:t>t</w:t></w:r><w:bookmarkEnd w:id="1"/></w:p>'


def test_resolved_reference_not_flagged():
    c = _c([_bookmark('_Ref100'), _ref('_Ref100')])
    assert c.audit_crossref_targets() == []


def test_missing_target_flagged():
    c = _c([_ref('_Ref999')])                       # no matching bookmark
    missing = c.audit_crossref_targets()
    assert '_Ref999' in missing
    assert any(k == 'xref-target-missing' for k, _ in c.audit)


def test_mixed_resolved_and_missing():
    c = _c([_bookmark('_Ref1'), _ref('_Ref1'), _ref('_RefX')])
    assert c.audit_crossref_targets() == ['_RefX']
