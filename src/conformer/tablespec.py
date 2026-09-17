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


def effective_table_issues(tbl_xml, nsdecls=None):
    """Resolve a table's effective formatting and report where DIRECT overrides defeat the house
    appearance. Each issue: {'kind', 'detail', 'severity'} where severity 'fail' = the house appearance
    is not achieved, 'review' = a meaningful deviation to surface (e.g. subtotal shading), 'unresolved' =
    a construct the engine cannot reliably conform (reported, not silently claimed conformant).
    `nsdecls` = the document's namespace declarations so a fragment with inherited prefixes parses."""
    tbl = _parse(tbl_xml, nsdecls)
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


def table_conformant(tbl_xml, nsdecls=None):
    """True ONLY when the table was evaluated and no 'fail' or 'unresolved' issue remains. An
    unevaluated/unparsed table is NOT conformant — unknown never counts as conformant. ('review' issues
    are surfaced but do not by themselves fail conformance.)"""
    issues = effective_table_issues(tbl_xml, nsdecls)
    return not any(i['severity'] in ('fail', 'unresolved') for i in issues)
