"""Word-COM RENDER acceptance harness for the LI Report Conformer.

Drives `word_render_read.ps1` (Word COM via PowerShell — no pywin32 dependency), then checks the
*rendered* state against the LI July-2026 guideline. This is the check that catches what XML-shape tests
miss: a table stamped GridTable4 that still renders navy, a NumberedParagraph style that renders as
bullets, a TOC whose PAGEREF all resolve to page 1.

Windows + Word only. `verify(docx)` returns a RenderReport; `python render_verify.py <docx> [--fields]`
prints it. Not a pytest gate yet — run deliberately; a full Warhoe pass with --fields takes minutes.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

_HERE = os.path.dirname(os.path.abspath(__file__))
_PS1 = os.path.join(_HERE, 'word_render_read.ps1')

# WdColor sentinels
_AUTOMATIC = -16777216
_UNDEFINED = 9999999
# Guideline house values
HOUSE_HEADER_RGB = 'B6DDE8'      # teal
OLD_NAVY_RGB = '054F8A'          # the wrong color the engine used to inject
HOUSE_TABLE_STYLES = {'Grid Table 4', 'LI Table'}
HOUSE_HEADER_PT = 10.0
HOUSE_HEADER_FONT = 'Times New Roman'
# House list styles (lower-cased) and what marker class each should render
NUMBER_STYLES = {'numbered paragraph', 'numbered paragraph l1', 'numbered paragraph l2',
                 'numbered paragraph l3'}
DASH_STYLES = {'numbered paragraph l4'}                 # the "-" sublevel; a dash is correct here
BULLET_STYLES = {'list bullet', 'list bullet as a sentence', 'dash under a bullet',
                 'list bullet under a numbered list'}
ALL_HOUSE_LIST_STYLES = NUMBER_STYLES | DASH_STYLES | BULLET_STYLES

def classify_marker(marker):
    """Bullet vs number from the RENDERED list marker (ListString). ListType is unreliable — a
    multilevel list reports type 4 (outline) for both its bullet and its numbered levels."""
    if marker is None:
        return 'unknown'
    m = str(marker).strip()
    if m == '':
        return 'bullet'                          # empty marker = a bullet level in Word
    if re.search(r'[0-9]', m):
        return 'number'                          # 1.  3.4.2  (1)
    if re.match(r'^[A-Za-z]{1,3}[.)]', m):
        return 'number'                          # a.  iv.  B)
    return 'bullet'                              # •  -  –  ▪  o  etc.


def bgr_to_rgb_hex(v):
    """Word BackgroundPatternColor is a BGR long. Return 'RRGGBB', or a token for auto/undefined/none."""
    if v is None:
        return None
    try:
        v = int(v)
    except (TypeError, ValueError):
        return str(v)
    if v == _AUTOMATIC:
        return 'AUTO'
    if v == _UNDEFINED:
        return 'MIXED'
    if v < 0:
        return f'?{v}'
    r, g, b = v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF
    return f'{r:02X}{g:02X}{b:02X}'


@dataclass
class RenderReport:
    path: str
    ok: bool
    error: str | None
    raw: dict
    defects: list = field(default_factory=list)

    def add(self, severity, kind, detail):
        self.defects.append({'severity': severity, 'kind': kind, 'detail': detail})

    @property
    def fails(self):
        return [d for d in self.defects if d['severity'] == 'fail']

    @property
    def unverified(self):
        """Defects that mean a required property could NOT be observed — an incomplete render read, not a
        pass (GPT re-review R6). As a release gate these block just like a fail."""
        return [d for d in self.defects if d['severity'] == 'unverified']

    @property
    def passed(self):
        """A release-gate pass requires zero failures AND zero unverified observations; a plain 'review'
        item (a real but non-blocking observation) does not block."""
        return not (self.fails or self.unverified)


def _as_list(x):
    """PowerShell ConvertTo-Json collapses a 1-element array to an object; normalize back to a list."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _style_parts(s):
    """Word's Style.NameLocal joins a style's name and its aliases with commas
    (e.g. 'Grid Table 4,LI Table'). Return the individual names."""
    return {p.strip() for p in (s or '').split(',') if p.strip()}


def read_render(docx_path, update_fields=False, timeout=1800):
    """Run the PowerShell reader and return its parsed dict."""
    if os.name != 'nt':
        raise RuntimeError('render harness requires Windows + Word')
    if not os.path.exists(docx_path):
        raise FileNotFoundError(docx_path)
    out_json = docx_path + '.render.json'
    cmd = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', _PS1,
           '-Path', os.path.abspath(docx_path), '-Out', out_json]
    if update_fields:
        cmd.append('-UpdateFields')
    subprocess.run(cmd, check=True, timeout=timeout,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with open(out_json, encoding='utf-8-sig') as f:
        data = json.load(f)
    try:
        os.remove(out_json)
    except OSError:
        pass
    return data


def _effective_header_fill(tbl, styles_by_name):
    """Rendered header fill: direct cell shading if concrete, else the applied style's firstRow fill."""
    direct = bgr_to_rgb_hex(tbl.get('header_cell1_fill_bgr'))
    if direct and direct not in ('AUTO', 'MIXED') and not direct.startswith('?'):
        return direct, 'direct'
    st = styles_by_name.get(tbl.get('style'))
    if st:
        sfill = bgr_to_rgb_hex(st.get('firstrow_fill_bgr'))
        if sfill and sfill not in ('AUTO', 'MIXED') and not sfill.startswith('?'):
            return sfill, 'style'
    return direct or 'AUTO', 'none'


def verify(docx_path, update_fields=False, timeout=1800):
    """Read the rendered doc and check it against the guideline. Returns a RenderReport."""
    data = read_render(docx_path, update_fields=update_fields, timeout=timeout)
    rep = RenderReport(path=docx_path, ok=bool(data.get('ok')), error=data.get('error'), raw=data)
    if not rep.ok:
        rep.add('fail', 'harness', f'Word reader failed: {rep.error}')
        return rep

    styles_by_name = {s.get('name'): s for s in _as_list(data.get('table_styles'))}

    # ---- tables ----
    # Every REQUIRED header property is checked across EVERY header cell: fill, size, font, bold, and the
    # repeat-header flag. A concrete wrong value is a fail; a value that could not be observed (no fill, no
    # size, no font/bold observation, a mixed size, or a per-table read error) is UNVERIFIED, never a
    # silent pass, so an incomplete render read cannot certify the table (GPT re-review R6).
    tables = _as_list(data.get('tables'))
    nonhouse_style = navy = wrong_size = wrong_fill = unknown_size = 0
    wrong_font = not_bold = not_repeat = incomplete = read_err = 0
    for t in tables:
        if t.get('nested'):
            continue  # nested tables read via a flat header row are not meaningful here
        if not (_style_parts(t.get('style')) & HOUSE_TABLE_STYLES):
            nonhouse_style += 1
            continue
        if t.get('header_error'):
            read_err += 1
            continue
        # Per-table flags. An UNOBSERVABLE cell (mixed / empty / null) within a populated array marks the
        # table incomplete — it must NOT disappear behind a valid neighbour or a table-wide fallback
        # (GPT re-review S4). A concrete wrong value in ANY cell is a fail.
        miss = f_navy = f_fill = f_size = f_unknownsz = f_font = f_bold = False
        style_fill = None
        _st = styles_by_name.get(t.get('style'))
        if _st is not None:
            style_fill = bgr_to_rgb_hex(_st.get('firstrow_fill_bgr'))
        # fill — EVERY header cell; AUTO resolves through the style's firstRow fill
        fills = [bgr_to_rgb_hex(v) for v in _as_list(t.get('header_fills'))]
        if not fills:
            eff, _src = _effective_header_fill(t, styles_by_name)
            fills = [eff] if eff else []
        if not fills:
            miss = True
        for f in fills:
            if f == OLD_NAVY_RGB:
                f_navy = True
            elif f == 'AUTO':
                if style_fill == HOUSE_HEADER_RGB:
                    pass                                   # the style supplies teal
                elif style_fill == OLD_NAVY_RGB:
                    f_navy = True
                elif style_fill and style_fill not in ('AUTO', 'MIXED') and not str(style_fill).startswith('?'):
                    f_fill = True
                else:
                    miss = True                            # no concrete fill anywhere
            elif f in ('MIXED', None) or str(f).startswith('?'):
                miss = True                                # cell fill could not be read
            elif f != HOUSE_HEADER_RGB:
                f_fill = True
        # size — every header cell
        sizes = _as_list(t.get('header_sizes')) or ([t.get('header_size')] if t.get('header_size') is not None else [])
        if not sizes:
            miss = True
        for s in sizes:
            if not isinstance(s, (int, float)) or s == _UNDEFINED:
                f_unknownsz = True                         # mixed/unreadable cell size
            elif abs(s - HOUSE_HEADER_PT) > 0.01:
                f_size = True
        # font family — a null/empty cell value is unobserved, not a pass
        fonts = _as_list(t.get('header_fonts'))
        if not fonts:
            miss = True
        for f in fonts:
            if not f:
                miss = True
            elif f != HOUSE_HEADER_FONT:
                f_font = True
        # bold — True / False / None(=mixed/unreadable)
        bolds = _as_list(t.get('header_bold'))
        if not bolds:
            miss = True
        for b in bolds:
            if b is None:
                miss = True
            elif b is False:
                f_bold = True
        if f_navy:
            navy += 1
        elif f_fill:
            wrong_fill += 1
        if f_size:
            wrong_size += 1
        if f_unknownsz:
            unknown_size += 1
        if f_font:
            wrong_font += 1
        if f_bold:
            not_bold += 1
        # repeat-as-header (tblHeader) — a review item, not a hard fail (a single-row table is legitimate)
        if t.get('header_repeats') is None:
            miss = True
        elif t.get('header_repeats') is False:
            not_repeat += 1
        if miss:
            incomplete += 1
    if nonhouse_style:
        rep.add('fail', 'table-style', f'{nonhouse_style} table(s) not on a house table style (Grid Table 4 / LI Table)')
    if navy:
        rep.add('fail', 'table-header-navy', f'{navy} table header(s) render NAVY {OLD_NAVY_RGB}, not house teal {HOUSE_HEADER_RGB}')
    if wrong_fill:
        rep.add('fail', 'table-header-fill', f'{wrong_fill} table header(s) render a non-house fill (not teal {HOUSE_HEADER_RGB})')
    if wrong_size:
        rep.add('fail', 'table-header-size', f'{wrong_size} table header(s) have a cell not rendering at {HOUSE_HEADER_PT:g}pt')
    if wrong_font:
        rep.add('fail', 'table-header-font', f'{wrong_font} table header(s) render a non-house font (not {HOUSE_HEADER_FONT})')
    if not_bold:
        rep.add('fail', 'table-header-not-bold', f'{not_bold} table header(s) render a non-bold cell')
    if not_repeat:
        rep.add('review', 'table-header-no-repeat', f'{not_repeat} table header row(s) are not marked to repeat across pages')
    if unknown_size:
        rep.add('unverified', 'table-header-size-unknown', f'{unknown_size} table header(s) have an unreadable/mixed cell size')
    if read_err:
        rep.add('unverified', 'table-header-read-error', f'{read_err} table header(s) could not be read')
    if incomplete:
        rep.add('unverified', 'table-header-incomplete', f'{incomplete} house table(s) missing a required header observation (fill/size/font/bold/repeat)')

    # ---- fields / TOC ----
    fields = data.get('fields') or {}
    if fields.get('updated') and fields.get('update_ok') is False:
        rep.add('unverified', 'field-update-failed', 'a field/TOC update threw — PAGEREF/REF results below are unverified')
    pr, pr1, prb = fields.get('pageref_total', 0), fields.get('pageref_showing_1', 0), fields.get('pageref_blank', 0)
    # A wholly-collapsed set (every PAGEREF renders "1") is the exact wrong-render this check names, so it
    # fails regardless of N — the max(3, …) floor alone let a small (<=2 field) TOC collapse silently pass
    # (GPT self-review).
    if pr and pr1 and (pr1 == pr or pr1 >= max(3, pr // 2)):
        rep.add('fail', 'toc-page-1', f'{pr1} of {pr} PAGEREF fields render page "1" — TOC/List of Tables collapsed to page 1'
                + ('' if fields.get('updated') else ' (fields NOT updated; rerun with --fields to confirm live)'))
    if prb:
        rep.add('review', 'pageref-blank', f'{prb} PAGEREF field(s) render blank (target may be missing)')
    if fields.get('ref_bookmark_errors'):
        rep.add('fail', 'ref-broken', f"{fields['ref_bookmark_errors']} REF field(s) render an error "
                "('Bookmark not found' / 'Reference source not found')")

    # ---- lists: check the rendered marker against what each house style should render ----
    # Guideline: Numbered Paragraph + L1/L2/L3 = a number (1./a./i.); L4 = a dash "-"; the four bullet
    # styles = a bullet glyph. L4-as-dash classifies as 'bullet' and is CORRECT, so it is not a defect.
    lists = _as_list(data.get('lists'))
    num_style_as_bullet = bullet_style_as_num = dash_style_as_num = 0
    other_styles = {}
    for l in lists:
        low = (l.get('style') or '').lower()
        cls = classify_marker(l.get('marker'))
        if low in NUMBER_STYLES and cls == 'bullet':
            num_style_as_bullet += 1
        elif low in DASH_STYLES and cls == 'number':
            dash_style_as_num += 1
        elif low in BULLET_STYLES and cls == 'number':
            bullet_style_as_num += 1
        elif low not in ALL_HOUSE_LIST_STYLES and not low.startswith(('heading', 'toc', 'table of')):
            other_styles[low] = other_styles.get(low, 0) + 1
    if num_style_as_bullet:
        rep.add('fail', 'list-number-as-bullet',
                f'{num_style_as_bullet} numbered-paragraph item(s) render as a BULLET (should be 1./a./i.)')
    if bullet_style_as_num:
        rep.add('fail', 'list-bullet-as-number',
                f'{bullet_style_as_num} bullet-style item(s) render as a NUMBER')
    if dash_style_as_num:
        rep.add('fail', 'list-dash-as-number',
                f'{dash_style_as_num} L4 (dash-sublevel) item(s) render as a NUMBER')
    if other_styles:
        top = ', '.join(f'{k}×{v}' for k, v in sorted(other_styles.items(), key=lambda kv: -kv[1])[:6])
        rep.add('review', 'list-nonhouse-style',
                f'{sum(other_styles.values())} list item(s) on non-house list styles: {top}')

    return rep


def _fmt(rep):
    d = rep.raw
    lines = [f'RENDER VERIFY: {os.path.basename(rep.path)}',
             f"  ok={rep.ok} counts={d.get('counts')}",
             f"  timing_ms={d.get('timing_ms')}"]
    if rep.error:
        lines.append(f'  ERROR: {rep.error}')
    lines.append(f"  table styles seen: {[s.get('name') for s in _as_list(d.get('table_styles'))]}")
    for s in _as_list(d.get('table_styles')):
        lines.append(f"    style '{s.get('name')}' firstRow fill={bgr_to_rgb_hex(s.get('firstrow_fill_bgr'))} "
                     f"bold={s.get('firstrow_bold')} size={s.get('firstrow_size')}")
    lines.append(f"  fields: {d.get('fields')}")
    # list-style -> rendered marker tally (the truthful bullet-vs-number evidence)
    tally = {}
    for l in _as_list(d.get('lists')):
        marker = (l.get('marker') or '').strip()
        key = (l.get('style'), marker, classify_marker(l.get('marker')))
        tally[key] = tally.get(key, 0) + 1
    if tally:
        lines.append('  list style -> rendered marker (bullet/number), count')
        for (st, marker, cls) in sorted(tally, key=lambda k: -tally[k]):
            lines.append(f"    {st!r:38s} marker={marker!r:8s} {cls:7s} x{tally[(st, marker, cls)]}")
    lines.append(f'  DEFECTS ({len(rep.fails)} fail, {len(rep.unverified)} unverified) — '
                 f'gate {"PASS" if rep.passed else "NOT PASS"}:')
    for x in rep.defects:
        lines.append(f"    [{x['severity']}] {x['kind']}: {x['detail']}")
    if not rep.defects:
        lines.append('    (none — renders to guideline)')
    return '\n'.join(lines)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    do_fields = '--fields' in sys.argv
    if not args:
        print('usage: python render_verify.py <docx> [--fields]')
        sys.exit(2)
    r = verify(args[0], update_fields=do_fields)
    print(_fmt(r))
    # a release gate fails on a real defect OR an unverified observation (incomplete read is not a pass)
    sys.exit(0 if r.passed else 1)
