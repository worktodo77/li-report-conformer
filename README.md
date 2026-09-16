# LI Report Conformer

Desktop app that repairs expert reports to match the LI Word template.

Wraps a Python engine that reads a damaged `.docx`, runs 14 repair passes
(style classification, direct-formatting removal, table normalization,
cross-reference field rebuilding, typography, etc.), and writes a conformed
copy. A PySide6 GUI lets the user review "judgment calls" — ambiguous style
decisions the engine flags — before applying.

## Install

```
pip install -e .
```

Requires Python 3.10+ and PySide6-Essentials 6.7–6.8.

## Run

```
python src/conformer/main.py
```

Or after install: `li-conformer`

## Test

```
python -m pytest tests/
```

## Build

```
pyinstaller conformer.spec
```

Produces `dist/LIReportConformer/` (Windows `.exe`) or
`dist/LI Report Conformer.app` (macOS).

## License

See [LICENSE](LICENSE).
