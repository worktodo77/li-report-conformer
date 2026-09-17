"""LI house table specification + an EFFECTIVE-formatting verifier.

Setting tblStyle=LITable and pStyle=TableData does not establish conformance: direct cell borders,
shading, margins, or a paragraph's own justification override the style and defeat the intended house
appearance. This module holds the house spec (sourced from the LITABLE style constant + the TableData
paragraph style) and resolves the EFFECTIVE formatting of a table — style + firstRow conditional + direct
overrides — so a table can be checked by what it renders, not by the style name it carries.

Namespace-aware (ElementTree). Analysis only; the engine performs the edits."""
import re
import xml.etree.ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

# The LI house table appearance (from LITABLE in engine.py + template TableData):
HOUSE = {
    'grid_color': '808080',        # ½pt grey grid on every border
    'grid_sz': '4',
    'header_fill': '054F8A',       # navy header row fill
    'header_text': 'FFFFFF',       # white bold header text
    'cell_margin_lr': '72',        # dxa
    'align': 'center',             # cells + table centered
    'sz': '22',                    # house run size (11pt, half-points) for body + header
}
_DEFAULT_SHD = {'auto', 'clear', None, ''}   # non-fills that don't override the house appearance

# The document's namespace prefixes so a table FRAGMENT (which inherits them from the root) still parses.
# outcome_report passes the real document's declarations; this is a comprehensive fallback.
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


def _border_is_house(borders_el):
    """True when a direct <w:tcBorders>/<w:tblBorders> exactly matches the house grey ½pt grid (so an
    equivalent direct border is not wrongly flagged as an override)."""
    for side in borders_el:
        val = side.get(_w('val'))
        if val in (None, 'nil', 'none'):
            return False
        if val != 'single' or side.get(_w('sz')) not in ('4', None):
            return False
        col = (side.get(_w('color')) or '').upper()
        if col not in (HOUSE['grid_color'], 'AUTO', ''):
            return False
    return True


_GRID_SIDES = ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')


def _borders_form_house_grid(borders_el):
    """The house grid is a grey ½pt line on ALL SIX sides — the four outer edges plus insideH/insideV —
    each ENABLED (val='single', not nil/none), sized ½pt (sz 4) and coloured 808080. One grey side does
    not establish the grid (issue #1 R5): a definition must resolve the whole grid, not merely mention the
    colour somewhere."""
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
        if (side.get(_w('color')) or '').upper() not in (HOUSE['grid_color'], 'AUTO'):
            return False
    return True


def _style_defines_house_table(styles_xml):
    """Verify the LITable style DEFINITION resolves the house appearance by its actual PROPERTIES (a grey
    grid on tblBorders sides; a navy fill on the firstRow conditional's cell shading) — not by a substring
    search that a style merely NAMED '808080 054F8A' would pass. Returns an issue list."""
    if not styles_xml:
        return []
    m = re.search(r'<w:style\b[^>]*w:styleId="LITable".*?</w:style>', styles_xml, re.S)
    if not m:
        return [{'kind': 'style-missing', 'detail': 'LITable style is not defined', 'severity': 'fail'}]
    try:
        el = ET.fromstring(f'<root {_NSDECLS}>{m.group(0)}</root>').find(_w('style'))
    except ET.ParseError:
        el = None
    if el is None:
        return [{'kind': 'style-corrupt', 'detail': 'LITable style did not parse', 'severity': 'fail'}]
    bad = []
    tblPr = el.find(_w('tblPr'))
    borders = tblPr.find(_w('tblBorders')) if tblPr is not None else None
    if not _borders_form_house_grid(borders):
        bad.append('grey ½pt grid on all six borders')
    # the firstRow conditional must establish BOTH the navy fill AND the white header text — a fill alone
    # is not a conformant header definition (issue #1 R5).
    navy = white = False
    for sp in el.findall(_w('tblStylePr')):
        if sp.get(_w('type')) != 'firstRow':
            continue
        tcpr = sp.find(_w('tcPr'))
        shd = tcpr.find(_w('shd')) if tcpr is not None else None
        if shd is not None and (shd.get(_w('fill')) or '').upper() == HOUSE['header_fill']:
            navy = True
        rpr = sp.find(_w('rPr'))
        if rpr is not None and (_val(rpr, 'color') or '').upper() == HOUSE['header_text']:
            white = True
    if not navy:
        bad.append('navy fill on the first-row header')
    if not white:
        bad.append('white header text on the first-row header')
    if bad:
        return [{'kind': 'style-corrupt', 'detail': 'LITable style definition is missing ' + '; '.join(bad),
                 'severity': 'fail'}]
    return []


def effective_table_issues(tbl_xml, nsdecls=None, styles_xml=None):
    """Resolve a table's EFFECTIVE formatting and report where the house appearance is not achieved.
    Severity 'fail' = house appearance not achieved, 'review' = a meaningful deviation to surface,
    'unresolved' = a construct that cannot be reliably conformed (never silently claimed conformant).
    `nsdecls` = document namespace declarations (so inherited prefixes parse); `styles_xml` lets the
    check verify the LITable style DEFINITION itself, not just the assigned name."""
    tbl = _parse(tbl_xml, nsdecls)
    if tbl is None:
        return [{'kind': 'parse', 'detail': 'table did not parse', 'severity': 'unresolved'}]
    issues = list(_style_defines_house_table(styles_xml))

    tblPr = tbl.find(_w('tblPr'))
    style = _val(tblPr, 'tblStyle') if tblPr is not None else None
    if style != 'LITable':
        issues.append({'kind': 'style', 'detail': f'table style is {style!r}, not LITable',
                       'severity': 'fail'})
    # direct table borders that are NOT the house grid defeat it
    tblB = tblPr.find(_w('tblBorders')) if tblPr is not None else None
    if tblB is not None and not _border_is_house(tblB):
        issues.append({'kind': 'grid-overridden', 'detail': 'direct <w:tblBorders> overrides the grid',
                       'severity': 'fail'})
    # the first-row conditional (navy header) must be ENABLED via tblLook, or the header never applies
    look = tblPr.find(_w('tblLook')) if tblPr is not None else None
    if look is not None and (look.get(_w('firstRow')) or '1').lower() in ('0', 'false'):
        issues.append({'kind': 'header-conditional-off', 'detail': 'tblLook firstRow is off, so the navy '
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
            # a direct run font size that CONFLICTS with the house size (e.g. a 72pt run); a direct size
            # equal to the house size is equivalent and not flagged
            for r in tc.iter(_w('r')):
                sz = _val(r.find(_w('rPr')), 'sz') if r.find(_w('rPr')) is not None else None
                if sz is not None and sz != HOUSE['sz']:
                    issues.append({'kind': 'font-size', 'detail': f'cell r{ri}c{ci} run has a direct font '
                                   f'size ({int(sz) // 2}pt) conflicting with the house size',
                                   'severity': 'fail' if is_header else 'review'})
                    break
            # shading
            shd = tcPr.find(_w('shd')) if tcPr is not None else None
            fill = shd.get(_w('fill')) if shd is not None else None
            theme_fill = shd is not None and (shd.get(_w('themeFill')) or shd.get(_w('themeColor')))
            if is_header:
                if theme_fill and (not fill or fill.lower() in _DEFAULT_SHD):
                    # a theme-only background: its effective colour cannot be established here -> unresolved
                    issues.append({'kind': 'header-fill-theme', 'detail': f'header cell c{ci} uses a theme '
                                   'fill; effective background colour is not established (not proven navy)',
                                   'severity': 'unresolved'})
                elif fill and fill.lower() not in _DEFAULT_SHD and fill.upper() != HOUSE['header_fill']:
                    issues.append({'kind': 'header-fill', 'detail': f'header cell c{ci} fill {fill} is '
                                   f"not the house navy {HOUSE['header_fill']}", 'severity': 'fail'})
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
                # header legibility: white text vs its actual background
                if is_header:
                    for r in p.findall(_w('r')):
                        rpr = r.find(_w('rPr'))
                        col = _val(rpr, 'color') if rpr is not None else None
                        bg = fill.upper() if (fill and fill.lower() not in _DEFAULT_SHD) else HOUSE['header_fill']
                        if col and col.upper() != HOUSE['header_text'] and bg == HOUSE['header_fill']:
                            issues.append({'kind': 'header-illegible', 'detail': f'header cell c{ci} run '
                                           f'colour {col} on navy background', 'severity': 'fail'})
    return issues


def table_conformant(tbl_xml, nsdecls=None, styles_xml=None):
    """True ONLY when the table was evaluated and no 'fail' or 'unresolved' issue remains. An
    unevaluated/unparsed table is NOT conformant — unknown never counts as conformant. ('review' issues
    are surfaced but do not by themselves fail conformance.)"""
    issues = effective_table_issues(tbl_xml, nsdecls, styles_xml)
    return not any(i['severity'] in ('fail', 'unresolved') for i in issues)
