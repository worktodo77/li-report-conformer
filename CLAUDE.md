# LI Report Conformer

## What this is
PySide6 desktop app wrapping the conformer engine (`src/conformer/engine.py`).
Repairs expert reports to match the LI Word template. Ships as Windows `.exe` + macOS `.app`.

## Architecture
- `src/conformer/engine.py` — two-pass conformer: `analyze()` identifies fixes, `apply(decisions)` applies them
- `src/conformer/ui/` — PySide6 GUI (Concept A "Ledger" design, FieldIQ visual language)
- `src/conformer/scorer.py` — 10-check scorer (golden vs candidate)
- `src/conformer/assets/` — bundled template, golden.docx, KITCHEN_SINK.docx

## Design reference
FieldIQ visual language: warm paper `#faf9f6`, navy `#1f3a5f`, Source Serif 4 / Public Sans / IBM Plex Mono,
2-3px radii, hairline rules. See `src/conformer/ui/styles.qss`.

## Key rules
- Judgment calls are INTERACTIVE: engine identifies but does NOT apply them until the user reviews
- Two output modes: "Save conformed copy" (default) and "Replace in place" (OneDrive/SharePoint)
- Backup to `_LI Conformer Backups/` before writing; revert button
- Validate output XML + zip completeness after conforming; refuse to overwrite on failure
- Check for `~$name.docx` Word lock file before processing

## Run
```
python src/conformer/main.py
```

## Test
```
python -m pytest tests/
```

## Build
```
pyinstaller conformer.spec
```
