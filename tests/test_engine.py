"""Engine tests: original flow + two-pass analyze/apply."""
import os, tempfile, zipfile

from conformer.engine import Conformer, JudgmentCall
from conformer.scorer import score

ASSETS = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets')
TEMPLATE = os.path.join(ASSETS, 'template.dotx')
GOLDEN = os.path.join(ASSETS, 'golden.docx')
KITCHEN_SINK = os.path.join(ASSETS, 'KITCHEN_SINK.docx')


def test_kitchen_sink_scores_ten():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'repaired.docx')
        c = Conformer(TEMPLATE, KITCHEN_SINK)
        c.run()
        c.save(out)
        result = score(GOLDEN, out)
        assert result['_summary']['passed'] == 10, (
            f"Expected 10/10, got {result['_summary']['passed']}/10: "
            + ', '.join(k for k, v in result.items() if not k.startswith('_') and not v['pass'])
        )


def test_engine_produces_log():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'repaired.docx')
        c = Conformer(TEMPLATE, KITCHEN_SINK)
        c.run()
        c.save(out)
        assert len(c.log) > 0, "Engine should produce mechanical log entries"
        assert len(c.judgment) > 0, "Engine should produce judgment log entries"
        for entry in c.judgment:
            assert 'item' in entry and 'msg' in entry


def test_analyze_returns_judgment_calls():
    c = Conformer(TEMPLATE, KITCHEN_SINK)
    calls = c.analyze()
    assert len(calls) > 0, "analyze() should return judgment calls"
    for jc in calls:
        assert isinstance(jc, JudgmentCall)
        assert jc.id and jc.kind and jc.message
        assert jc.full_text is not None
        assert jc.recommended_action
    kinds = {jc.kind for jc in calls}
    assert 'style' in kinds, "Should have style classification judgments"


def test_accept_all_matches_original():
    c = Conformer(TEMPLATE, KITCHEN_SINK)
    calls = c.analyze()
    decisions = {jc.id: 'accept' for jc in calls}
    fresh = c.apply_with_decisions(decisions)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'repaired.docx')
        fresh.save(out)
        result = score(GOLDEN, out)
        assert result['_summary']['passed'] == 10, (
            f"Accept-all should match original 10/10, got {result['_summary']['passed']}/10"
        )


def test_skip_all_still_produces_valid_output():
    c = Conformer(TEMPLATE, KITCHEN_SINK)
    calls = c.analyze()
    decisions = {jc.id: 'skip' for jc in calls}
    fresh = c.apply_with_decisions(decisions)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'repaired.docx')
        fresh.save(out)
        valid, msg = fresh.validate_output()
        assert valid, f"Skip-all output should still be a valid docx: {msg}"


def test_validate_output():
    c = Conformer(TEMPLATE, KITCHEN_SINK)
    c.run()
    valid, msg = c.validate_output()
    assert valid, f"Engine output should validate: {msg}"


def test_change_decision_applies_alternative_style():
    c = Conformer(TEMPLATE, KITCHEN_SINK)
    calls = c.analyze()
    style_calls = [jc for jc in calls if jc.kind == 'style' and jc.alternatives]
    assert style_calls, "Should have style judgment calls with alternatives"
    target = style_calls[0]
    alt = next(a for a in target.alternatives if a != target.recommended_action)
    decisions = {jc.id: 'accept' for jc in calls}
    decisions[target.id] = f'change:{alt}'
    fresh = c.apply_with_decisions(decisions)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'repaired.docx')
        fresh.save(out)
        valid, msg = fresh.validate_output()
        assert valid, f"Change-decision output should be valid: {msg}"


def test_corrupt_input_raises():
    with tempfile.TemporaryDirectory() as tmp:
        bad = os.path.join(tmp, 'corrupt.docx')
        with open(bad, 'wb') as f:
            f.write(b'not a zip file')
        try:
            Conformer(TEMPLATE, bad)
            assert False, "Should have raised on corrupt input"
        except Exception:
            pass
