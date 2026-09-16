"""Low-level builders for synthetic expert-report fixtures (test data only — fictitious).

python-docx handles structure/styles/tables/images/comments; raw lxml injection handles the two
things python-docx cannot express: tracked changes (w:ins / w:del / *Change) and Word fields
(STYLEREF / SEQ / REF for captions and cross-references). Everything here is content-neutral
plumbing — the report content and the defect model live in generate.py.
"""
import os
import zipfile
import tempfile

from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets', 'template.dotx')


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


# ---------------------------------------------------------------- tracked changes (lxml)
def _rev(tag, rid, author, date):
    el = OxmlElement(tag)
    el.set(qn('w:id'), str(rid))
    el.set(qn('w:author'), author)
    el.set(qn('w:date'), date)
    return el


def wrap_run_ins(run, ids, author, date):
    """Mark a run as a tracked insertion: <w:ins><w:r>…</w:r></w:ins>."""
    r = run._r
    ins = _rev('w:ins', ids.next(), author, date)
    r.addprevious(ins)
    ins.append(r)
    return ins


def wrap_run_del(run, ids, author, date):
    """Mark a run as a tracked deletion: text becomes delText inside <w:del>."""
    r = run._r
    for t in r.findall(qn('w:t')):
        t.tag = qn('w:delText')
    dele = _rev('w:del', ids.next(), author, date)
    r.addprevious(dele)
    dele.append(r)
    return dele


def mark_paragraph_inserted(p, ids, author, date):
    """Mark a whole paragraph a tracked insertion: every run wrapped in <w:ins> AND the paragraph
    mark itself marked inserted (<w:pPr><w:rPr><w:ins/></w:rPr>)."""
    for run in list(p.runs):
        wrap_run_ins(run, ids, author, date)
    pPr = p._p.get_or_add_pPr()
    rPr = pPr.find(qn('w:rPr'))
    if rPr is None:
        rPr = OxmlElement('w:rPr')
        pPr.insert(0, rPr)
    rPr.insert(0, _rev('w:ins', ids.next(), author, date))


def add_ppr_change(p, ids, author, date, old_ppr_xml):
    """Attach a formatting-revision snapshot (pPrChange) recording a prior paragraph property set."""
    pPr = p._p.get_or_add_pPr()
    ch = _rev('w:pPrChange', ids.next(), author, date)
    ch.append(parse_xml(f'<w:pPr {nsdecls("w")}>{old_ppr_xml}</w:pPr>'))
    pPr.append(ch)


def add_rpr_change(run, ids, author, date, old_rpr_inner):
    """Attach a run formatting-revision snapshot (rPrChange) to a run."""
    rPr = run._r.get_or_add_rPr()
    ch = _rev('w:rPrChange', ids.next(), author, date)
    ch.append(parse_xml(f'<w:rPr {nsdecls("w")}>{old_rpr_inner}</w:rPr>'))
    rPr.append(ch)


# ---------------------------------------------------------------- comments
def add_comment(document, runs, text, author, initials='RV'):
    if not isinstance(runs, (list, tuple)):
        runs = [runs]
    return document.add_comment(runs=list(runs), text=text, author=author, initials=initials)


# ---------------------------------------------------------------- bookmarks & fields
def bookmark(name, bid):
    return (f'<w:bookmarkStart {nsdecls("w")} w:id="{bid}" w:name="{name}"/>',
            f'<w:bookmarkEnd {nsdecls("w")} w:id="{bid}"/>')


def field_runs(instr, cached, rstyle=None):
    """Raw run XML for a Word field: begin / instrText / separate / cached result / end."""
    rp = f'<w:rPr><w:rStyle w:val="{rstyle}"/></w:rPr>' if rstyle else ''
    return (f'<w:r>{rp}<w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r>{rp}<w:instrText xml:space="preserve"> {instr} </w:instrText></w:r>'
            f'<w:r>{rp}<w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r>{rp}<w:t xml:space="preserve">{cached}</w:t></w:r>'
            f'<w:r>{rp}<w:fldChar w:fldCharType="end"/></w:r>')


def append_xml(p, xml):
    """Append a raw run/field/bookmark fragment (already namespaced or wrapped) to a paragraph."""
    p._p.append(parse_xml(xml))


def set_para_xml(p, inner_xml):
    """Replace a paragraph's run content with raw XML (keeps its pPr)."""
    pPr = p._p.find(qn('w:pPr'))
    for child in list(p._p):
        if child is not pPr:
            p._p.remove(child)
    frag = parse_xml(f'<w:pWrap {nsdecls("w")}>{inner_xml}</w:pWrap>')
    for child in list(frag):
        p._p.append(child)


# ---------------------------------------------------------------- direct formatting (defects)
def add_direct_ppr(p, xml):
    """Inject direct paragraph properties (spacing/ind/tabs/etc.) that strip_direct should remove."""
    pPr = p._p.get_or_add_pPr()
    frag = parse_xml(f'<w:pPr {nsdecls("w")}>{xml}</w:pPr>')
    for child in list(frag):
        pPr.append(child)


def add_direct_rpr(run, xml):
    rPr = run._r.get_or_add_rPr()
    frag = parse_xml(f'<w:rPr {nsdecls("w")}>{xml}</w:rPr>')
    for child in list(frag):
        rPr.append(child)


# ---------------------------------------------------------------- foreign style definitions
def has_style(document, style_id):
    styles = document.styles.element
    return any(s.get(qn('w:styleId')) == style_id for s in styles.findall(qn('w:style')))


def ensure_foreign_style(document, style_id, name):
    """Add a custom paragraph style definition (a 'foreign' style classify() must remap)."""
    styles = document.styles.element
    if has_style(document, style_id):
        return
    xml = (f'<w:style {nsdecls("w")} w:type="paragraph" w:customStyle="1" w:styleId="{style_id}">'
           f'<w:name w:val="{name}"/><w:basedOn w:val="Normal"/>'
           f'<w:pPr><w:spacing w:after="120"/></w:pPr>'
           f'<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="22"/></w:rPr></w:style>')
    styles.append(parse_xml(xml))
