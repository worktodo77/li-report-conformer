"""Built-in self-test: conforms KITCHEN_SINK.docx against golden.docx and reports the score."""
import os, tempfile
from PySide6.QtWidgets import QMessageBox

from conformer.engine import Conformer
from conformer.scorer import score


def _assets_dir():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')


def run_selftest(parent):
    assets = _assets_dir()
    template = os.path.join(assets, 'template.dotx')
    golden = os.path.join(assets, 'golden.docx')
    kitchen = os.path.join(assets, 'KITCHEN_SINK.docx')

    for f, label in [(template, 'template.dotx'), (golden, 'golden.docx'), (kitchen, 'KITCHEN_SINK.docx')]:
        if not os.path.exists(f):
            QMessageBox.critical(parent, 'Self-test failed', f'Missing bundled asset: {label}')
            return

    try:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'selftest_output.docx')
            c = Conformer(template, kitchen)
            c.run()
            c.save(out)
            result = score(golden, out)

        passed = result['_summary']['passed']
        total = result['_summary']['total']

        if passed == total:
            QMessageBox.information(
                parent, 'Self-test passed',
                f'Score: {passed}/{total}\n\n'
                f'Engine conformed KITCHEN_SINK.docx and scored a perfect '
                f'{total}/{total} against golden.docx.\n\n'
                f'{len(c.log)} mechanical fixes, {len(c.judgment)} judgment calls.'
            )
        else:
            failed = [k for k, v in result.items() if not k.startswith('_') and not v['pass']]
            QMessageBox.warning(
                parent, 'Self-test did not pass',
                f'Score: {passed}/{total}\n\n'
                f'Failed checks: {", ".join(failed)}'
            )
    except Exception as e:
        QMessageBox.critical(parent, 'Self-test error', str(e))
