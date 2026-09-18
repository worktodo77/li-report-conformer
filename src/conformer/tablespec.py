"""LI house table specification + an EFFECTIVE-formatting verifier.

The LI house table style is **Grid Table 4** (`w:styleId="GridTable4"`, `w:name="Grid Table 4"`, alias
"LI Table"), carried correctly in the bundled `template.dotx`. Its appearance:
  - whole table centered; grid = single ½pt (sz 4) border colour `auto` (black) on all six sides;
  - firstRow header = TEAL fill `B6DDE8` (themeFill accent5, themeFillTint 66), header text BLACK (`auto`)
    BOLD Times New Roman Bold 10 pt (sz 20);
  - body = Table Data style, Times New Roman 11 pt (sz 22), black, centered.

Setting the style name alone does not establish conformance: direct cell borders, shading, margins, or a
paragraph's own justification override the style and defeat the house appearance. This module holds the
house spec and resolves the EFFECTIVE formatting of a table — style + firstRow conditional + direct
overrides — so a table is checked by what it renders, not by the style name it carries.

Namespace-aware (ElementTree). Analysis only; the engine performs the edits."""
import re
import xml.etree.ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

# The LI house table appearance = Grid Table 4 / "LI Table" (from template.dotx):
HOUSE = {
    'style_id': 'GridTable4',      # w:styleId; w:name "Grid Table 4"; alias "LI Table"
    'style_name': 'Grid Table 4',
    'style_alias': 'LI Table',
    'grid_color': 'auto',          # ½pt black (auto) grid on every border
    'grid_sz': '4',
    'header_fill': 'B6DDE8',       # teal header row fill …
    'header_theme_fill': 'accent5',  # … carried as themeFill accent5 (tint 66); either form is house
    'header_text': 'auto',         # black (auto) BOLD header text (NOT white)
    'header_sz': '20',             # header run size 10 pt (half-points)
    'cell_margin_lr': '72',        # dxa
    'align': 'center',             # cells + table centered
    'sz': '22',                    # body run size 11 pt (half-points)
}
# Colours that count as "black" for a border/text (auto resolves to black in the LI theme):
_BLACK = {'AUTO', '000000', ''}
# Header fills that count as the house teal (concrete hex OR the theme colour it is carried as):
_HOUSE_HEADER_FILLS = {'B6DDE8'}
_DEFAULT_SHD = {'auto', 'clear', None, ''}   # non-fills that don't override the house appearance

# The document's namespace prefixes so a table FRAGMENT (which inherits them from the root) still parses.
_NSDECLS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
    'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml" '
    'xmlns:w16="http://schemas.microsoft.com/office/word/2018/wordml" '
    'xmlns:w16cid="http://schemas.microsoft.com/office/word/2016/wordml/cid" '
    'xmlns:w16se="http://schemas.microsoft.com/office/word/2015/wordml/symex" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
    'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
    'xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:o="urn:schemas-microsoft-com:office:office" '
    'xmlns:w10="urn:schemas-microsoft-com:office:word"'
)


def _w(t):
    return '{%s}%s' % (W, t)


def _val(el, tag, attr='val'):
    if el is None:
        return None
    c = el.find(_w(tag))
    return c.get(_w(attr)) if c is not None else None


def _parse(tbl_xml, nsdecls=None):
    """Parse a single <w:tbl> fragment. It inherits the document's namespace prefixes (w14, r, drawing,
    …), so those declarations must be supplied or the fragment fails to parse. Returns the element or
    None; None must be treated as UNRESOLVED, never as conformant."""
    try:
        root = ET.fromstring(f'<root {nsdecls or _NSDECLS}>{tbl_xml}</root>')
    except ET.ParseError:
        return None
    return root.find(_w('tbl'))


def _direct_rows(tbl):
    """Immediate rows of THIS table (not a nested table's rows) — nested tables live inside a cell."""
    return tbl.findall(_w('tr'))


def _disabled(el):
    """True when a boolean toggle element is explicitly OFF (val='0'/'false'/'off'). A missing val = on."""
    if el is None:
        return None
    v = (el.get(_w('val')) or '').lower()
    return v in ('0', 'false', 'off')


def _is_house_header_fill(shd):
    """True when a <w:shd> establishes the house teal header — either a concrete fill B6DDE8 or the theme
    colour it is carried as (themeFill accent5). Returns None when there is no meaningful fill at all."""
    if shd is None:
        return None
    fill = (shd.get(_w('fill')) or '')
    theme = (shd.get(_w('themeFill')) or '')
    if fill.upper() in _HOUSE_HEADER_FILLS:
        return True
    if theme.lower() == HOUSE['header_theme_fill'] and fill.upper() in ({'', 'AUTO'} | _HOUSE_HEADER_FILLS):
        return True
    if fill.lower() in _DEFAULT_SHD and not theme:
        return None                                   # no real fill
    return False                                      # some other colour


def _border_is_house(borders_el):
    """True when a direct <w:tcBorders>/<w:tblBorders> matches the house black ½pt grid (so an equivalent
    direct border is not wrongly flagged as an override). Inner-side nil is tolerated on a cell (the header
    conditional itself uses insideH nil)."""
    for side in borders_el:
        val = (side.get(_w('val')) or '').lower()
        if val in ('nil', 'none', ''):
            continue                                  # an absent inner side is not a conflicting override
        if val != 'single' or side.get(_w('sz')) not in ('4', None):
            return False
        col = (side.get(_w('color')) or '').upper()
        if col not in _BLACK:
            return False
    return True


_GRID_SIDES = ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')


def _borders_form_house_grid(borders_el):
    """The house grid is a black ½pt line on ALL SIX sides — the four outer edges plus insideH/insideV —
    each ENABLED (val='single'), sized ½pt (sz 4) and coloured `auto`/black. One black side does not
    establish the grid: a definition must resolve the whole grid, not merely mention the colour once."""
    if borders_el is None:
        return False
    for name in _GRID_SIDES:
        side = borders_el.find(_w(name))
        if side is None:
            return False
        if (side.get(_w('val')) or '').lower() != 'single':
            return False
        if side.get(_w('sz')) not in ('4', None):
            return False
        if (side.get(_w('color')) or '').upper() not in _BLACK:
            return False
    return True


def _style_defined(styles_xml, style_id):
    """True when styles.xml actually defines a `w:styleId="style_id"` style."""
    return bool(style_id) and bool(
        re.search(r'<w:style\b[^>]*w:styleId="' + re.escape(style_id) + r'"', styles_xml or ''))


def _effective_style_size(styles_xml, style_id, _seen=None):
    """Resolve a PARAGRAPH style's effective run size (sz, half-points) from styles.xml, following the
    basedOn chain. Returns the value as a string, or None if unset/unknown. The style's own paragraph-mark
    rPr (inside pPr) and any table-style conditionals are excluded so only the run-level style size is read."""
    if not styles_xml or not style_id:
        return None
    _seen = _seen or set()
    if style_id in _seen:
        return None
    _seen.add(style_id)
    m = re.search(r'<w:style\b[^>]*w:styleId="' + re.escape(style_id) + r'".*?</w:style>', styles_xml, re.S)
    if not m:
        return None
    body = m.group(0)
    main = re.sub(r'<w:pPr>.*?</w:pPr>', '', re.sub(r'<w:tblStylePr\b.*?</w:tblStylePr>', '', body, flags=re.S), flags=re.S)
    sz = re.search(r'<w:sz w:val="(\d+)"/>', main)
    if sz:
        return sz.group(1)
    based = re.search(r'<w:basedOn w:val="([^"]+)"', body)
    return _effective_style_size(styles_xml, based.group(1), _seen) if based else None


def _style_defines_house_table(styles_xml):
    """Verify the Grid Table 4 style DEFINITION resolves the house appearance by its actual PROPERTIES (a
    black grid on tblBorders sides; a teal fill + black bold header text on the firstRow conditional) — not
    by a substring search. Returns an issue list."""
    if not styles_xml:
        return []
    m = re.search(r'<w:style\b[^>]*w:styleId="GridTable4".*?</w:style>', styles_xml, re.S)
    if not m:
        return [{'kind': 'style-missing', 'detail': 'GridTable4 ("LI Table") style is not defined',
                 'severity': 'fail'}]
    try:
        el = ET.fromstring(f'<root {_NSDECLS}>{m.group(0)}</root>').find(_w('style'))
    except ET.ParseError:
        el = None
    if el is None:
        return [{'kind': 'style-corrupt', 'detail': 'GridTable4 style did not parse', 'severity': 'fail'}]
    bad = []
    tblPr = el.find(_w('tblPr'))
    borders = tblPr.find(_w('tblBorders')) if tblPr is not None else None
    if not _borders_form_house_grid(borders):
        bad.append('black ½pt grid on all six borders')
    # the firstRow conditional must establish BOTH the teal fill AND black bold header text.
    teal = black_bold = False
    for sp in el.findall(_w('tblStylePr')):
        if sp.get(_w('type')) != 'firstRow':
            continue
        tcpr = sp.find(_w('tcPr'))
        shd = tcpr.find(_w('shd')) if tcpr is not None else None
        if _is_house_header_fill(shd):
            teal = True
        rpr = sp.find(_w('rPr'))
        if rpr is not None:
            has_bold = rpr.find(_w('b')) is not None and not _disabled(rpr.find(_w('b')))
            col = (_val(rpr, 'color') or 'auto').upper()
            if has_bold and col in _BLACK:
                black_bold = True
    if not teal:
        bad.append('teal fill on the first-row header')
    if not black_bold:
        bad.append('black bold text on the first-row header')
    if bad:
        return [{'kind': 'style-corrupt',
                 'detail': 'GridTable4 style definition is missing ' + '; '.join(bad), 'severity': 'fail'}]
    return []


def effective_table_issues(tbl_xml, nsdecls=None, styles_xml=None):
    """Resolve a table's EFFECTIVE formatting and report where the house appearance is not achieved.
    Severity 'fail' = house appearance not achieved, 'review' = a meaningful deviation to surface,
    'unresolved' = a construct that cannot be reliably conformed (never silently claimed conformant).
    `nsdecls` = document namespace declarations; `styles_xml` lets the check verify the GridTable4 style
    DEFINITION itself, not just the assigned name."""
    tbl = _parse(tbl_xml, nsdecls)
    if tbl is None:
        return [{'kind': 'parse', 'detail': 'table did not parse', 'severity': 'unresolved'}]
    issues = list(_style_defines_house_table(styles_xml))

    tblPr = tbl.find(_w('tblPr'))
    style = _val(tblPr, 'tblStyle') if tblPr is not None else None
    if style != HOUSE['style_id']:
        issues.append({'kind': 'style', 'detail': f'table style is {style!r}, not GridTable4 ("LI Table")',
                       'severity': 'fail'})
    # direct table borders that are NOT the house grid defeat it
    tblB = tblPr.find(_w('tblBorders')) if tblPr is not None else None
    if tblB is not None and not _border_is_house(tblB):
        issues.append({'kind': 'grid-overridden', 'detail': 'direct <w:tblBorders> overrides the grid',
                       'severity': 'fail'})
    # the first-row conditional (teal header) must be ENABLED via tblLook, or the header never applies
    look = tblPr.find(_w('tblLook')) if tblPr is not None else None
    if look is not None and (look.get(_w('firstRow')) or '1').lower() in ('0', 'false'):
        issues.append({'kind': 'header-conditional-off', 'detail': 'tblLook firstRow is off, so the teal '
                       'header formatting is not applied', 'severity': 'fail'})

    rows = _direct_rows(tbl)
    for ri, tr in enumerate(rows):
        is_header = ri == 0
        trPr = tr.find(_w('trPr'))
        hdr = trPr.find(_w('tblHeader')) if trPr is not None else None
        if is_header and (hdr is None or _disabled(hdr)):
            issues.append({'kind': 'header-missing', 'detail': 'first row is not an ENABLED repeating '
                           'header (tblHeader missing or off)', 'severity': 'fail'})
        for ci, tc in enumerate(tr.findall(_w('tc'))):
            tcPr = tc.find(_w('tcPr'))
            # direct cell borders that are not the house grid defeat it (an equivalent one is fine)
            tcb = tcPr.find(_w('tcBorders')) if tcPr is not None else None
            if tcb is not None and not _border_is_house(tcb):
                issues.append({'kind': 'grid-overridden', 'detail': f'cell r{ri}c{ci} has direct '
                               '<w:tcBorders> overriding the grid', 'severity': 'fail'})
            # direct cell margins override the house 72-twip margins
            if tcPr is not None and tcPr.find(_w('tcMar')) is not None:
                issues.append({'kind': 'cell-margins', 'detail': f'cell r{ri}c{ci} has direct margins '
                               'overriding the house cell margins', 'severity': 'review'})
            # a direct run font size that CONFLICTS with the house size (header 10pt/sz20, body 11pt/sz22);
            # a direct size equal to the house size is equivalent and not flagged
            want_sz = HOUSE['header_sz'] if is_header else HOUSE['sz']
            direct_szs = []
            for r in tc.iter(_w('r')):
                sz = _val(r.find(_w('rPr')), 'sz') if r.find(_w('rPr')) is not None else None
                if sz is not None:
                    direct_szs.append(sz)
                if sz is not None and sz != want_sz:
                    issues.append({'kind': 'font-size', 'detail': f'cell r{ri}c{ci} run has a direct font '
                                   f'size ({int(sz) // 2}pt) conflicting with the house '
                                   f'{int(want_sz) // 2}pt', 'severity': 'fail' if is_header else 'review'})
                    break
            # EFFECTIVE header size: with no direct run size, the header renders at its paragraph STYLE's
            # size — and a paragraph style overrides the Grid Table 4 firstRow rPr. So a header cell whose
            # first paragraph resolves to a non-10pt style (e.g. a stray Heading in a header cell) renders
            # the wrong size even though no direct run size flags it. This catches the style-resolved case
            # the direct-size check misses (surfaced as review — informational).
            if is_header and styles_xml:
                p0 = tc.find(_w('p'))
                pst = _val(p0.find(_w('pPr')), 'pStyle') if p0 is not None and p0.find(_w('pPr')) is not None else None
                if pst and not _style_defined(styles_xml, pst):
                    # a header paragraph referencing a style absent from styles.xml renders at the default
                    # size (Word ~12pt) — an unresolved defect, never a silent pass (GPT audit F1).
                    issues.append({'kind': 'header-style-missing', 'detail': f'header cell c{ci} first '
                                   f'paragraph references undefined style {pst!r}', 'severity': 'fail'})
                elif not direct_szs:
                    eff = _effective_style_size(styles_xml, pst)
                    if eff is not None and eff != want_sz:
                        # A VISIBLE header (the cell has text) rendering the wrong size is a real defect
                        # (fail); an EMPTY header paragraph (e.g. a stray blank Heading) is an artifact
                        # surfaced for review only (GPT audit F5).
                        has_text = any((t.text or '').strip() for t in tc.iter(_w('t')))
                        issues.append({'kind': 'header-style-size', 'detail': f'header cell c{ci} first '
                                       f'paragraph style {pst!r} renders at {int(eff) // 2}pt, not the house '
                                       f'{int(want_sz) // 2}pt', 'severity': 'fail' if has_text else 'review'})
            # shading
            shd = tcPr.find(_w('shd')) if tcPr is not None else None
            fill = shd.get(_w('fill')) if shd is not None else None
            if is_header:
                house_fill = _is_house_header_fill(shd)
                if house_fill is False:
                    issues.append({'kind': 'header-fill', 'detail': f'header cell c{ci} fill {fill} is '
                                   f"not the house teal {HOUSE['header_fill']}", 'severity': 'fail'})
                # house_fill True (teal) or None (inherits the conditional) are both fine
            elif fill and fill.lower() not in _DEFAULT_SHD:
                issues.append({'kind': 'cell-shading', 'detail': f'cell r{ri}c{ci} has fill {fill} '
                               '(meaningful shading — e.g. a subtotal row)', 'severity': 'review'})
            # nested table → conform independently; report as unresolved by this flat pass
            if tc.find(_w('tbl')) is not None:
                issues.append({'kind': 'nested-table', 'detail': f'cell r{ri}c{ci} contains a nested '
                               'table (conform independently)', 'severity': 'unresolved'})
            # cell paragraph justification: a direct jc != center defeats centering
            for p in tc.findall(_w('p')):
                jc = _val(p.find(_w('pPr')), 'jc') if p.find(_w('pPr')) is not None else None
                if jc and jc not in ('center',):
                    issues.append({'kind': 'not-centered', 'detail': f'cell r{ri}c{ci} paragraph jc={jc}',
                                   'severity': 'review'})
                # header text must be black (auto), not white or another colour
                if is_header:
                    for r in p.findall(_w('r')):
                        rpr = r.find(_w('rPr'))
                        col = _val(rpr, 'color') if rpr is not None else None
                        if col and col.upper() not in _BLACK:
                            issues.append({'kind': 'header-text', 'detail': f'header cell c{ci} run colour '
                                           f'{col} is not the house black header text', 'severity': 'fail'})
    return issues


def table_conformant(tbl_xml, nsdecls=None, styles_xml=None):
    """True ONLY when the table was evaluated and no 'fail' or 'unresolved' issue remains. An
    unevaluated/unparsed table is NOT conformant — unknown never counts as conformant. ('review' issues
    are surfaced but do not by themselves fail conformance.)"""
    issues = effective_table_issues(tbl_xml, nsdecls, styles_xml)
    return not any(i['severity'] in ('fail', 'unresolved') for i in issues)
