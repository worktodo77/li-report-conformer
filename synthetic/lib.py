"""Low-level builders for synthetic expert-report fixtures (test data only — fictitious).

python-docx handles structure/styles/tables/images/comments; raw lxml injection handles the two
things python-docx cannot express: tracked changes (w:ins / w:del / *Change) and Word fields
(STYLEREF / SEQ / REF for captions and cross-references). Everything here is content-neutral
plumbing — the report content and the defect model live in generate.py.

Builders are correct-by-construction: they emit schema-ordered OOXML. Deliberately malformed markup,
where needed, lives only in clearly named negative fixtures — never here.
"""
import os
import zipfile
import tempfile

from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets', 'template.dotx')


class AssetError(RuntimeError):
    """Raised when a declared fixture asset (image, comment) cannot be created — fail loud so a
    defect is never declared against content that does not exist."""


# ---------------------------------------------------------------- base package
def li_base_docx():
    """python-docx refuses a .dotx; copy the LI template to a temp .docx with the document (not
    template) content type, so the generated report carries every LI style but is a real document."""
    tmp = os.path.join(tempfile.mkdtemp(), 'li_base.docx')
    zin = zipfile.ZipFile(os.path.abspath(TEMPLATE))
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for n in zin.namelist():
            data = zin.read(n)
            if n == '[Content_Types].xml':
                data = data.replace(b'wordprocessingml.template.main+xml',
                                    b'wordprocessingml.document.main+xml')
            zout.writestr(n, data)
    return tmp


# ---------------------------------------------------------------- revision-id allocator
class Ids:
    def __init__(self):
        self._n = 1000

    def next(self):
        self._n += 1
        return self._n


# ---------------------------------------------------------------- pPr child ordering
# CT_PPr sequence (subset we touch): pStyle, keepNext, keepLines, ..., numPr, ..., ind, ..., jc, ...,
# rPr, sectPr, pPrChange. The paragraph-mark rPr and pPrChange go near the END, never before pStyle.
def ppr_insert_rpr(pPr, rPr):
    anchor = pPr.find(qn('w:sectPr'))
    if anchor is None:
        anchor = pPr.find(qn('w:pPrChange'))
    if anchor is not None:
        anchor.addprevious(rPr)
    else:
        pPr.append(rPr)


# ---------------------------------------------------------------- tracked changes (lxml)
def _rev(tag, rid, author, date):
    el = OxmlElement(tag)
    el.set(qn('w:id'), str(rid))
    el.set(qn('w:author'), author)
    el.set(qn('w:date'), date)
    return el


def run_text(run):
    return ''.join(t.text or '' for t in run._r.findall(qn('w:t')))


def wrap_run_ins(run, ids, author, date):
    r = run._r
    rid = ids.next()
    ins = _rev('w:ins', rid, author, date)
    r.addprevious(ins)
    ins.append(r)
    return {'kind': 'ins', 'id': rid, 'author': author, 'date': date, 'payload_text': run_text(run)}


def wrap_run_del(run, ids, author, date):
    r = run._r
    payload = run_text(run)
    for t in r.findall(qn('w:t')):
        t.tag = qn('w:delText')
    rid = ids.next()
    dele = _rev('w:del', rid, author, date)
    r.addprevious(dele)
    dele.append(r)
    return {'kind': 'del', 'id': rid, 'author': author, 'date': date, 'payload_text': payload}


def mark_paragraph_inserted(p, ids, author, date):
    """Whole paragraph a tracked insertion: every run wrapped in <w:ins> AND the paragraph mark
    itself marked inserted (rPr/ins in pPr, in schema order). Returns the revision records."""
    recs = []
    for run in list(p.runs):
        recs.append(wrap_run_ins(run, ids, author, date))
    pPr = p._p.get_or_add_pPr()
    rPr = pPr.find(qn('w:rPr'))
    if rPr is None:
        rPr = OxmlElement('w:rPr')
        ppr_insert_rpr(pPr, rPr)
    rid = ids.next()
    rPr.insert(0, _rev('w:ins', rid, author, date))
    recs.append({'kind': 'para_inserted', 'id': rid, 'author': author, 'date': date,
                 'payload_text': p.text})
    return recs


def mark_paragraph_deleted(p, ids, author, date):
    """Whole paragraph a tracked deletion: runs -> del, and the paragraph MARK deleted (rPr/del in
    pPr) so accepting removes the paragraph and rejecting keeps it."""
    recs = []
    for run in list(p.runs):
        recs.append(wrap_run_del(run, ids, author, date))
    pPr = p._p.get_or_add_pPr()
    rPr = pPr.find(qn('w:rPr'))
    if rPr is None:
        rPr = OxmlElement('w:rPr')
        ppr_insert_rpr(pPr, rPr)
    rid = ids.next()
    rPr.insert(0, _rev('w:del', rid, author, date))
    recs.append({'kind': 'para_deleted', 'id': rid, 'author': author, 'date': date,
                 'payload_text': p.text})
    return recs


def mark_paragraph_mark_deleted(p, ids, author, date):
    """Mark only the paragraph boundary as deleted; leave visible runs retained."""
    pPr = p._p.get_or_add_pPr()
    rPr = pPr.find(qn('w:rPr'))
    if rPr is None:
        rPr = OxmlElement('w:rPr')
        ppr_insert_rpr(pPr, rPr)
    rid = ids.next()
    rPr.append(_rev('w:del', rid, author, date))
    return {'kind': 'para_mark_del', 'id': rid, 'author': author, 'date': date,
            'payload_text': p.text}

def add_ppr_change(p, ids, author, date, old_ppr_xml):
    pPr = p._p.get_or_add_pPr()
    rid = ids.next()
    ch = _rev('w:pPrChange', rid, author, date)
    ch.append(parse_xml(f'<w:pPr {nsdecls("w")}>{old_ppr_xml}</w:pPr>'))
    pPr.append(ch)
    return {'kind': 'pPrChange', 'id': rid, 'author': author, 'date': date, 'payload_text': ''}


def add_rpr_change(run, ids, author, date, old_rpr_inner):
    rPr = run._r.get_or_add_rPr()
    rid = ids.next()
    ch = _rev('w:rPrChange', rid, author, date)
    ch.append(parse_xml(f'<w:rPr {nsdecls("w")}>{old_rpr_inner}</w:rPr>'))
    rPr.append(ch)
    return {'kind': 'rPrChange', 'id': rid, 'author': author, 'date': date, 'payload_text': ''}


def move_runs(run_from, run_to, ids, author, date, mv_name):
    """A tracked MOVE: mark run_from with moveFrom + range markers and run_to with moveTo. Minimal
    but schema-valid: wraps each run in the move element and brackets it with move*RangeStart/End."""
    recs = []
    for run, tag, rng in ((run_from, 'w:moveFrom', 'moveFrom'), (run_to, 'w:moveTo', 'moveTo')):
        r = run._r
        rid = ids.next()
        mv = _rev(tag, rid, author, date)
        r.addprevious(mv)
        mv.append(r)
        start = OxmlElement('w:%sRangeStart' % rng)
        range_id = ids.next()
        start.set(qn('w:id'), str(range_id)); start.set(qn('w:name'), mv_name)
        end = OxmlElement('w:%sRangeEnd' % rng); end.set(qn('w:id'), str(range_id))
        mv.addprevious(start); mv.addnext(end)
        recs.append({'kind': rng, 'id': rid, 'author': author, 'date': date,
                     'payload_text': run_text(run)})
    return recs


def add_cell_revision(cell, ins_or_del, ids, author, date):
    """A tracked table-cell property revision (cellIns/cellDel) in the cell's tcPr."""
    tcPr = cell._tc.get_or_add_tcPr()
    tag = 'w:cellIns' if ins_or_del == 'ins' else 'w:cellDel'
    rid = ids.next()
    tcPr.append(_rev(tag, rid, author, date))
    return {'kind': tag.split(':')[1], 'id': rid, 'author': author, 'date': date, 'payload_text': ''}


# ---------------------------------------------------------------- comments
def add_comment(document, runs, text, author, initials='RV'):
    if not isinstance(runs, (list, tuple)):
        runs = [runs]
    try:
        return document.add_comment(runs=list(runs), text=text, author=author, initials=initials)
    except Exception as e:                       # fail loud — a declared comment must be created
        raise AssetError('comment could not be created: %s' % e)


# ---------------------------------------------------------------- bookmarks, locators & fields
def bookmark(name, bid):
    return (f'<w:bookmarkStart {nsdecls("w")} w:id="{bid}" w:name="{name}"/>',
            f'<w:bookmarkEnd {nsdecls("w")} w:id="{bid}"/>')


def add_locator(p, name, bid):
    """Place an invisible locator bookmark at the START of a paragraph (survives conforming; used by
    the scorer to find each defect/revision instance by a stable anchor)."""
    pPr = p._p.find(qn('w:pPr'))
    start = parse_xml(f'<w:bookmarkStart {nsdecls("w")} w:id="{bid}" w:name="{name}"/>')
    end = parse_xml(f'<w:bookmarkEnd {nsdecls("w")} w:id="{bid}"/>')
    if pPr is not None:
        pPr.addnext(end); pPr.addnext(start)
    else:
        p._p.insert(0, end); p._p.insert(0, start)


def field_runs(instr, cached, rstyle=None):
    rp = f'<w:rPr><w:rStyle w:val="{rstyle}"/></w:rPr>' if rstyle else ''
    return (f'<w:r>{rp}<w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r>{rp}<w:instrText xml:space="preserve"> {instr} </w:instrText></w:r>'
            f'<w:r>{rp}<w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r>{rp}<w:t xml:space="preserve">{cached}</w:t></w:r>'
            f'<w:r>{rp}<w:fldChar w:fldCharType="end"/></w:r>')


def append_xml(p, xml):
    p._p.append(parse_xml(xml))


def set_para_xml(p, inner_xml):
    pPr = p._p.find(qn('w:pPr'))
    for child in list(p._p):
        if child is not pPr:
            p._p.remove(child)
    frag = parse_xml(f'<w:pWrap {nsdecls("w")}>{inner_xml}</w:pWrap>')
    for child in list(frag):
        p._p.append(child)


# ---------------------------------------------------------------- direct formatting (defects)
def add_direct_ppr(p, xml):
    pPr = p._p.get_or_add_pPr()
    frag = parse_xml(f'<w:pPr {nsdecls("w")}>{xml}</w:pPr>')
    for child in list(frag):
        pPr.append(child)


def add_direct_rpr(run, xml):
    rPr = run._r.get_or_add_rPr()
    frag = parse_xml(f'<w:rPr {nsdecls("w")}>{xml}</w:rPr>')
    for child in list(frag):
        rPr.append(child)


# ---------------------------------------------------------------- style definitions
def has_style(document, style_id):
    styles = document.styles.element
    return any(s.get(qn('w:styleId')) == style_id for s in styles.findall(qn('w:style')))


def ensure_foreign_style(document, style_id, name):
    if has_style(document, style_id):
        return
    xml = (f'<w:style {nsdecls("w")} w:type="paragraph" w:customStyle="1" w:styleId="{style_id}">'
           f'<w:name w:val="{name}"/><w:basedOn w:val="Normal"/>'
           f'<w:pPr><w:spacing w:after="120"/></w:pPr>'
           f'<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="22"/></w:rPr></w:style>')
    document.styles.element.append(parse_xml(xml))


def corrupt_style_def(document, style_id):
    """Overwrite an EXISTING LI style definition with a broken one (Claire's real complaint: a
    corrupt List Bullet / table style). Returns True if a definition was corrupted."""
    styles = document.styles.element
    for s in styles.findall(qn('w:style')):
        if s.get(qn('w:styleId')) == style_id:
            # strip its real formatting children, leave a hollow, wrongly-based definition
            name = None
            for ch in list(s):
                if ch.tag == qn('w:name'):
                    name = ch
                s.remove(ch)
            if name is not None:
                s.append(name)
            based = OxmlElement('w:basedOn'); based.set(qn('w:val'), 'Normal'); s.append(based)
            # a nonsense direct pPr so the style no longer does its job
            s.append(parse_xml(f'<w:pPr {nsdecls("w")}><w:spacing w:after="0" w:line="0"/></w:pPr>'))
            return True
    return False
