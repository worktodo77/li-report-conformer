"""Smoke test: conformer engine produces a valid output and scores 10/10."""
import os, sys, tempfile, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer
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
