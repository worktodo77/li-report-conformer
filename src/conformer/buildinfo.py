"""Build identity for the LI Report Conformer.

A packaged build (PyInstaller) carries a `assets/BUILD_STAMP.txt` written by conformer.spec at build time,
holding the git short SHA and UTC build time. `build_id()` returns that string so the app — and every
conformed document's audit record — is self-identifying (no more guessing which commit an .exe/.app came
from). Running from source, it falls back to `git rev-parse`, else 'dev'."""
import os
import subprocess

_STAMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'BUILD_STAMP.txt')


def build_id():
    """The build's git SHA (+ ' built <UTC>' for a packaged build), or a git SHA from the source tree, or
    'dev' when neither is available. Never raises."""
    try:
        with open(_STAMP, encoding='utf-8') as f:
            s = f.read().strip()
            if s:
                return s
    except OSError:
        pass
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        sha = subprocess.run(['git', '-C', here, 'rev-parse', '--short', 'HEAD'],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        if sha:
            dirty = subprocess.run(['git', '-C', here, 'status', '--porcelain'],
                                   capture_output=True, text=True, timeout=5).stdout.strip()
            return sha + ('-dirty' if dirty else '')
    except Exception:
        pass
    return 'dev'


def short_build_id():
    """Just the SHA portion (drops the ' built <time>' suffix) — for a compact UI label."""
    return build_id().split('  ')[0]
