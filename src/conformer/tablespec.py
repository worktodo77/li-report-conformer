"""LI house table specification + an EFFECTIVE-formatting verifier.

Setting tblStyle=LITable and pStyle=TableData does not establish conformance: direct cell borders,
shading, margins, or a paragraph's own justification override the style and defeat the intended house
appearance. This module holds the house spec (sourced from the LITABLE style constant + the TableData
paragraph style) and resolves the EFFECTIVE formatting of a table — style + firstRow conditional + direct
overrides — so a table can be checked by what it renders, not by the style name it carries.

Namespace-aware (ElementTree). Analysis only; the engine performs the edits."""
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
}
_DEFAULT_SHD = {'auto', 'clear', None, ''}   # non-fills that don't override the house appearance


def _w(t):
    return '{%s}%s' % (W, t)


def _val(el, tag, attr='val'):
    if el is None:
        return None
    c = el.find(_w(tag))
    return c.get(_w(attr)) if c is not None else None


def _parse(tbl_xml):
    """Parse a single <w:tbl> fragment (wrapping it so namespaces resolve). Returns the element or None."""
    try:
        root = ET.fromstring(f'<root xmlns:w="{W}" xmlns:mc="http://schemas.openxmlformats.org/'
                             f'markup-compatibility/2006">{tbl_xml}</root>')
    except ET.ParseError:
        return None
    return root.find(_w('tbl'))


def _direct_rows(tbl):
    """Immediate rows of THIS table (not a nested table's rows) — nested tables live inside a cell."""
    return tbl.findall(_w('tr'))


def effective_table_issues(tbl_xml):
    """Resolve a table's effective formatting and report where DIRECT overrides defeat the house
    appearance. Each issue: {'kind', 'detail', 'severity'} where severity 'fail' = the house appearance
    is not achieved, 'review' = a meaningful deviation to surface (e.g. subtotal shading), 'unresolved' =
    a construct the engine cannot reliably conform (reported, not silently claimed conformant)."""
    tbl = _parse(tbl_xml)
    if tbl is None:
        return [{'kind': 'parse', 'detail': 'table did not parse', 'severity': 'unresolved'}]
    issues = []

    tblPr = tbl.find(_w('tblPr'))
    style = _val(tblPr, 'tblStyle') if tblPr is not None else None
    if style != 'LITable':
        issues.append({'kind': 'style', 'detail': f'table style is {style!r}, not LITable',
                       'severity': 'fail'})
    # direct table borders defeat the grey grid
    if tblPr is not None and tblPr.find(_w('tblBorders')) is not None:
        issues.append({'kind': 'grid-overridden', 'detail': 'direct <w:tblBorders> overrides the grid',
                       'severity': 'fail'})

    rows = _direct_rows(tbl)
    for ri, tr in enumerate(rows):
        is_header = ri == 0
        trPr = tr.find(_w('trPr'))
        if is_header and (trPr is None or trPr.find(_w('tblHeader')) is None):
            issues.append({'kind': 'header-missing', 'detail': 'first row is not marked as a repeating '
                           'header (tblHeader)', 'severity': 'fail'})
        for ci, tc in enumerate(tr.findall(_w('tc'))):
            tcPr = tc.find(_w('tcPr'))
            # direct cell borders defeat the grid
            if tcPr is not None and tcPr.find(_w('tcBorders')) is not None:
                issues.append({'kind': 'grid-overridden', 'detail': f'cell r{ri}c{ci} has direct '
                               '<w:tcBorders> overriding the grid', 'severity': 'fail'})
            # shading
            shd = tcPr.find(_w('shd')) if tcPr is not None else None
            fill = shd.get(_w('fill')) if shd is not None else None
            if is_header:
                if fill and fill.lower() not in _DEFAULT_SHD and fill.upper() != HOUSE['header_fill']:
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


def table_conformant(tbl_xml):
    """True when no 'fail' issue remains (review/unresolved may still be present and are surfaced)."""
    return not any(i['severity'] == 'fail' for i in effective_table_issues(tbl_xml))
