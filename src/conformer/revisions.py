"""Revision ledger + preservation verification (M1.1).

Correctness backbone for conforming reviewed drafts. Read-only and namespace-aware (ElementTree):
we inventory every tracked change / comment / protected dependency with a STRUCTURED payload, then
after a transformation we rebuild the inventory and diff it, so a silently lost, altered, moved, or
re-attributed edit is detected and blockable rather than shipped in a legal document.

Per GPT-6 review, the ledger records — not just concatenated text:
  * ordered content tokens (text, tabs, breaks, field instructions incl. delInstrText, footnote/
    endnote refs, drawings/objects by relationship + a HASH of the target's bytes);
  * placement (enclosing paragraph identity + the ordered content BEFORE the revision) so an
    intra-paragraph or cross-paragraph move fails;
  * for a formatting revision (*Change): BOTH the recorded historical snapshot AND the current
    property set it governs (protected-property policy — a pPrChange/rPrChange stores the whole
    previous property set, so protecting only the differing props is wrong);
  * comments: bodies + anchors + references (not just ids);
  * protected binary parts (media/embeddings/charts) and relationship maps;
  * an explicit list of revision constructs we do not yet fully support (a restriction, not silence).
"""
import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
RNS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
def _w(t): return f'{{{W}}}{t}'
def _r(t): return f'{{{RNS}}}{t}'
def _local(tag): return tag.rsplit('}', 1)[-1]
def _sha(b): return hashlib.sha256(b).hexdigest()[:16]

CONTENT_REV = {'ins', 'del', 'moveFrom', 'moveTo'}
FORMAT_REV = {'pPrChange', 'rPrChange', 'tblPrChange', 'trPrChange', 'tcPrChange',
              'sectPrChange', 'tblPrExChange', 'tblGridChange', 'numberingChange'}
RANGE_MARKERS = {'moveFromRangeStart', 'moveFromRangeEnd', 'moveToRangeStart', 'moveToRangeEnd',
                 'customXmlInsRangeStart', 'customXmlInsRangeEnd',
                 'customXmlDelRangeStart', 'customXmlDelRangeEnd'}
CELL_REV = {'cellIns', 'cellDel', 'cellMerge'}
# Revision constructs we FULLY structure in M1.1. Anything revision-ish outside this becomes an
# explicit restriction (GPT amendment 5), never silently dropped.
SUPPORTED = CONTENT_REV | FORMAT_REV
DETECTED_UNSUPPORTED = CELL_REV  # detected + flagged as an explicit restriction, not yet structured

STORY_RE = re.compile(r'word/(document|footnotes|endnotes|header\d*|footer\d*|comments\w*)\.xml$')
BINARY_RE = re.compile(r'word/(media|embeddings|charts)/')


@dataclass(frozen=True)
class Revision:
    part: str
    kind: str            # ins | del | moveFrom | moveTo | *-para | <*Change>
    rid: str
    author: str
    date: str
    payload: tuple       # content tokens, OR (snapshot_hash, current_props_hash) for *Change
    placement: tuple     # (enclosing-paragraph identity, ordered-prefix hash)
    context: str

    def identity(self):
        return (self.part, self.kind, self.rid)


# ---------------------------------------------------------------- relationship resolution
def _rels_for(parts, part):
    d, f = part.rsplit('/', 1)
    rels = f'{d}/_rels/{f}.rels'
    out = {}
    if rels in parts:
        try:
            root = ET.fromstring(parts[rels])
        except ET.ParseError:
            return out
        for rel in root:
            out[rel.get('Id')] = (rel.get('Type'), rel.get('Target'), rel.get('TargetMode') or 'Internal')
    return out


def _resolve(part, target):
    base = part.rsplit('/', 1)[0]
    stack = []
    for seg in f'{base}/{target}'.split('/'):
        if seg == '..':
            if stack: stack.pop()
        elif seg not in ('', '.'):
            stack.append(seg)
    return '/'.join(stack)


def _drawing_token(node, part, rels, parts):
    rid = node.get(_r('embed')) or node.get(_r('link')) or node.get(_r('id'))
    typ, target, mode = rels.get(rid, (None, None, None))
    content_hash = None
    if target and mode != 'External':
        resolved = _resolve(part, target)
        if resolved in parts:
            content_hash = _sha(parts[resolved])
    return ('drawing', typ, mode, target, content_hash)


def _content_tokens(elem, part, rels, parts):
    """Ordered structured payload of a content revision — text AND non-text."""
    toks = []
    for node in elem.iter():
        tag = node.tag
        if tag.endswith('}blip') or tag.endswith('}imagedata') or tag.endswith('}OLEObject'):
            toks.append(_drawing_token(node, part, rels, parts)); continue
        if not tag.startswith('{' + W + '}'):
            continue
        local = _local(tag)
        if local == 't' and node.text is not None:
            toks.append(('text', node.text))
        elif local == 'delText' and node.text is not None:
            toks.append(('deltext', node.text))
        elif local == 'instrText' and node.text is not None:
            toks.append(('instr', node.text))
        elif local == 'delInstrText' and node.text is not None:
            toks.append(('delinstr', node.text))
        elif local == 'tab':
            toks.append(('tab',))
        elif local in ('br', 'cr'):
            toks.append(('break', node.get(_w('type')) or ''))
        elif local == 'noBreakHyphen':
            toks.append(('nbhyphen',))
        elif local == 'footnoteReference':
            toks.append(('footnoteRef', node.get(_w('id'))))
        elif local == 'endnoteReference':
            toks.append(('endnoteRef', node.get(_w('id'))))
        elif local == 'sym':
            toks.append(('sym', node.get(_w('char'))))
    return tuple(toks)


def _para_text(para):
    return ''.join(n.text or '' for n in para.iter()
                   if _local(n.tag) in ('t', 'delText') and n.text)


def _placement(elem, para):
    """Conformance-robust placement: the ORDERED sequence of revision ids and bookmark names in the
    enclosing paragraph, plus this revision's index in it. This is stable when surrounding prose is
    reformatted (typography, styles) but changes when a revision is reordered within its paragraph or
    moved to a different paragraph — which is what 'placement' must catch. It deliberately does NOT
    depend on the mutable text around the revision."""
    if para is None:
        return ((), -1)
    seq = []
    idx = -1
    for n in para.iter():
        lt = _local(n.tag)
        if lt in CONTENT_REV or lt in FORMAT_REV:
            if n is elem:
                idx = len(seq)
            seq.append(f'{lt}:{n.get(_w("id"), "")}')
        elif lt == 'bookmarkStart':
            seq.append(f'bm:{n.get(_w("name"), "")}')
    return (tuple(seq), idx)


def _is_para_mark(elem, parent_of):
    if len(elem):
        return False
    p = parent_of.get(elem)
    gp = parent_of.get(p) if p is not None else None
    return p is not None and _local(p.tag) == 'rPr' and gp is not None and _local(gp.tag) == 'pPr'


def _nearest_para(elem, parent_of):
    node = elem
    while node is not None and _local(node.tag) != 'p':
        node = parent_of.get(node)
    return node


def _canon(elem):
    """Canonical bytes of an element's children (for property-set hashing)."""
    return b''.join(ET.tostring(c) for c in elem)


def parse_part(xml_bytes, part, parts):
    revs, unsupported = [], []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return revs, [(part, 'parse-error', '')]
    parent_of = {c: p for p in root.iter() for c in p}
    rels = _rels_for(parts, part)
    for elem in root.iter():
        if not elem.tag.startswith('{' + W + '}'):
            continue
        local = _local(elem.tag)
        rid = elem.get(_w('id'), '')
        author = elem.get(_w('author'), '')
        date = elem.get(_w('date'), '')
        para = _nearest_para(elem, parent_of)
        ctx = ' '.join(_para_text(para).split())[:80] if para is not None else ''
        if local in CONTENT_REV:
            para_mark = _is_para_mark(elem, parent_of)
            kind = f'{local}-para' if para_mark else local
            payload = () if para_mark else _content_tokens(elem, part, rels, parts)
            revs.append(Revision(part, kind, rid, author, date, payload,
                                 _placement(elem, para), ctx))
        elif local in FORMAT_REV:
            # Protect the recorded SNAPSHOT (the reject target) so rejecting still restores the
            # author's original properties. We deliberately do NOT protect the CURRENT properties:
            # applying house formatting is the tool's job, and it leaves reject behavior intact.
            snapshot = _sha(_canon(elem))
            revs.append(Revision(part, local, rid, author, date,
                                 (snapshot,), _placement(elem, para), ctx))
        elif local in DETECTED_UNSUPPORTED:
            unsupported.append((part, local, ctx))
    return revs, unsupported


# ---------------------------------------------------------------- comments
def _comment_bodies(parts):
    bodies = {}
    for name in parts:
        if not re.match(r'word/comments\.xml$', name):
            continue
        try:
            root = ET.fromstring(parts[name])
        except ET.ParseError:
            continue
        for c in root.iter(_w('comment')):
            cid = c.get(_w('id'))
            bodies[cid] = _sha(''.join(t.text or '' for t in c.iter(_w('t'))).encode('utf8'))
    return bodies


def _comment_anchors(parts):
    """Per comment id: which markers exist (range start/end + reference) and the anchored text."""
    anchors = {}
    # We track the ANCHOR MARKERS (range start/end + reference), not a hash of the anchored text:
    # conforming may reformat text inside a comment's range (its job), and genuine content deletion
    # inside the range is caught by the revision checks. Losing a marker (the comment's attachment)
    # or the comment body is what must fail.
    for name in parts:
        if not STORY_RE.match(name) or 'comments' in name:
            continue
        try:
            root = ET.fromstring(parts[name])
        except ET.ParseError:
            continue
        for n in root.iter():
            lt = _local(n.tag)
            if lt not in ('commentRangeStart', 'commentRangeEnd', 'commentReference'):
                continue
            cid = n.get(_w('id'))
            a = anchors.setdefault(cid, {'start': False, 'end': False, 'ref': False})
            a['start' if lt == 'commentRangeStart' else 'end' if lt == 'commentRangeEnd' else 'ref'] = True
    return anchors


@dataclass
class Ledger:
    revisions: list = field(default_factory=list)
    unsupported: list = field(default_factory=list)
    comment_bodies: dict = field(default_factory=dict)
    comment_anchors: dict = field(default_factory=dict)
    binaries: dict = field(default_factory=dict)
    rels: dict = field(default_factory=dict)

    @classmethod
    def build(cls, parts):
        revs, unsup = [], []
        for name in sorted(parts):
            if STORY_RE.match(name) and 'comments' not in name:
                r, u = parse_part(parts[name], name, parts)
                revs.extend(r); unsup.extend(u)
        binaries = {n: _sha(parts[n]) for n in parts if BINARY_RE.match(n)}
        rels = {}
        for name in sorted(parts):
            if STORY_RE.match(name):
                rr = _rels_for(parts, name)
                if rr:
                    rels[name] = rr
        return cls(revisions=revs, unsupported=unsup,
                   comment_bodies=_comment_bodies(parts), comment_anchors=_comment_anchors(parts),
                   binaries=binaries, rels=rels)

    def has_revisions(self):
        """Full preflight signal — true if ANY story part carries a revision (GPT amendment 5:
        do not trust a document-only or text-only check to declare a package revision-free)."""
        return bool(self.revisions or self.unsupported)

    def has_content_revisions(self):
        """True when the document carries content/structural revisions the legacy full-conform
        pipeline cannot safely resolve (insertions, deletions, moves, paragraph-mark revisions, or
        any unsupported revision construct). Formatting-only revisions (pPrChange/rPrChange) are
        left to the legacy pipeline, which resolves them, so this routes only the hard cases into
        the review-preserving pipeline."""
        content = CONTENT_REV | {f'{k}-para' for k in CONTENT_REV}
        return any(r.kind in content for r in self.revisions) or bool(self.unsupported)

    def summary(self):
        by_kind = {}
        for r in self.revisions:
            by_kind[r.kind] = by_kind.get(r.kind, 0) + 1
        return {'total': len(self.revisions), 'by_kind': by_kind,
                'authors': sorted({r.author for r in self.revisions if r.author}),
                'comments': len(self.comment_bodies) or len(self.comment_anchors),
                'unsupported': len(self.unsupported),
                'protected_binaries': len(self.binaries)}


def diff(before: 'Ledger', after: 'Ledger'):
    def index(revs):
        idx = {}
        for r in revs:
            idx.setdefault(r.identity(), []).append(r)
        return idx
    bi, ai = index(before.revisions), index(after.revisions)
    lost, payload_altered, placement_altered, metadata_altered = [], [], [], []
    for ident, brevs in bi.items():
        arevs = list(ai.get(ident, []))
        for b in brevs:
            exact = next((a for a in arevs if a.payload == b.payload and a.placement == b.placement
                          and a.author == b.author and a.date == b.date), None)
            if exact:
                arevs.remove(exact); continue
            samep = next((a for a in arevs if a.payload == b.payload), None)
            if samep and samep.placement != b.placement:
                arevs.remove(samep); placement_altered.append((b, samep)); continue
            if samep and (samep.author != b.author or samep.date != b.date):
                arevs.remove(samep); metadata_altered.append((b, samep)); continue
            if arevs:
                payload_altered.append((b, arevs.pop(0))); continue
            lost.append(b)
    introduced = []
    for ident, arevs in ai.items():
        extra = len(arevs) - len(bi.get(ident, []))
        if extra > 0:
            introduced.extend(arevs[-extra:])
    return {
        'lost': lost,
        'payload_altered': payload_altered,
        'placement_altered': placement_altered,
        'metadata_altered': metadata_altered,
        'introduced': introduced,
        'lost_comments': sorted(set(before.comment_anchors) - set(after.comment_anchors)),
        'comment_body_altered': sorted(cid for cid, h in before.comment_bodies.items()
                                       if after.comment_bodies.get(cid) != h),
        'comment_anchor_altered': sorted(cid for cid, a in before.comment_anchors.items()
                                         if after.comment_anchors.get(cid) != a),
        'binary_altered': sorted(n for n, h in before.binaries.items()
                                 if after.binaries.get(n) != h),
        'relationship_altered': sorted(n for n, r in before.rels.items()
                                       if after.rels.get(n) != r),
        'unsupported': after.unsupported,
    }


# ---------------------------------------------------------------- content-stream invariant
# The ordered stream of CURRENT content: text, objects, structural tokens, and every revision /
# comment / bookmark boundary and paragraph/table structure marker — EXCLUDING formatting property
# elements and historical *Change snapshots. A formatting pass must leave this identical; a content
# change (deleted text even inside a comment range, a moved revision, a merged paragraph, a lost
# object) changes it. This is the allowed-change backbone: it does not depend on what the ledger
# happens to record.
_SIMPLE_TEXT = {'t': 'T', 'delText': 'DT', 'instrText': 'IT', 'delInstrText': 'DIT'}

def _stream_emit(elem, out, part, rels, parts):
    tag = elem.tag
    lt = _local(tag)
    if lt in FORMAT_REV:
        return  # historical snapshot — not part of the current content stream
    if tag.endswith('}blip') or tag.endswith('}imagedata') or tag.endswith('}OLEObject'):
        rid = elem.get(_r('embed')) or elem.get(_r('link')) or elem.get(_r('id'))
        typ, target, mode = rels.get(rid, (None, None, None))
        h = None
        if target and mode != 'External':
            res = _resolve(part, target)
            if res in parts:
                h = _sha(parts[res])
        out.append(('OBJ', typ, mode, target, h))
        return
    if not tag.startswith('{' + W + '}'):
        for ch in elem:
            _stream_emit(ch, out, part, rels, parts)
        return
    boundary = lt in CONTENT_REV
    if boundary and len(elem) == 0:
        out.append((f'{lt}-para', elem.get(_w('id'), ''))); return
    if boundary:
        out.append((f'<{lt}', elem.get(_w('id'), '')))
    if lt in _SIMPLE_TEXT and elem.text is not None:
        out.append((_SIMPLE_TEXT[lt], elem.text))
    elif lt == 'tab' and not elem.attrib: out.append(('TAB',))   # run content tab, NOT a tab-STOP
    # a <w:tab w:val=".." w:pos=".."/> inside <w:tabs> is pPr FORMATTING, not content — skip it, so
    # stripping direct tab-stop formatting is not mistaken for deleting a content tab.
    elif lt in ('br', 'cr'): out.append(('BR', elem.get(_w('type')) or ''))
    elif lt == 'noBreakHyphen': out.append(('NBH',))
    elif lt == 'footnoteReference': out.append(('FN', elem.get(_w('id'))))
    elif lt == 'endnoteReference': out.append(('EN', elem.get(_w('id'))))
    elif lt == 'p': out.append(('P',))
    elif lt in ('tbl', 'tr', 'tc'): out.append((lt.upper(),))
    elif lt == 'commentRangeStart': out.append(('CRS', elem.get(_w('id'))))
    elif lt == 'commentRangeEnd': out.append(('CRE', elem.get(_w('id'))))
    elif lt == 'commentReference': out.append(('CREF', elem.get(_w('id'))))
    elif lt == 'bookmarkStart': out.append(('BMS', elem.get(_w('name'))))
    elif lt == 'bookmarkEnd': out.append(('BME', elem.get(_w('id'))))
    for ch in elem:
        _stream_emit(ch, out, part, rels, parts)
    if boundary:
        out.append((f'{lt}>', elem.get(_w('id'), '')))


def content_stream(parts):
    streams = {}
    for name in sorted(parts):
        if not STORY_RE.match(name):
            continue
        try:
            root = ET.fromstring(parts[name])
        except ET.ParseError:
            streams[name] = [('parse-error',)]; continue
        out = []
        _stream_emit(root, out, name, _rels_for(parts, name), parts)
        streams[name] = out
    return streams


_STRUCTURE_TOKENS = {'P', 'TBL', 'TR', 'TC'}

def stream_violations(before, after, text_ok=None, ignore_structure=False):
    """Differences between two content streams that are NOT an authorized change. `text_ok(old,new)`
    permits a text transformation (e.g. typography). `ignore_structure=True` drops paragraph/table
    structure markers before comparing, so an AUTO structural pass may merge/delete/split paragraphs
    while every text token, object, and revision/comment/bookmark boundary must still line up exactly
    (a deleted word or moved boundary is still caught)."""
    def prep(stream):
        return [t for t in stream if t[0] not in _STRUCTURE_TOKENS] if ignore_structure else stream
    viols = []
    for name in sorted(set(before) | set(after)):
        b, a = prep(before.get(name, [])), prep(after.get(name, []))
        if len(b) != len(a):
            viols.append((name, 'token-count', len(b), len(a))); continue
        for i, (x, y) in enumerate(zip(b, a)):
            if x == y:
                continue
            if text_ok and x[0] in _SIMPLE_TEXT.values() and x[0] == y[0] and text_ok(x[1], y[1]):
                continue
            viols.append((name, i, x, y))
    return viols


# ---------------------------------------------------------------- display-preserving invariant
# For the interactive ASK structural changes (#3/#5/#6/#7/#8) the reader's document must be
# IDENTICAL while the underlying structure may change: literal text becomes a field, a wrapper table
# is unwrapped, a floating image is pulled inline, a caption is split from body text. The DISPLAY
# stream captures exactly what a reader sees — consecutive visible-text tokens merged; field
# instruction tokens (IT/DIT) and paragraph/table STRUCTURE tokens dropped; every object and every
# revision / comment / bookmark boundary kept in order. A display-preserving edit leaves this
# identical; a lost/reordered word, a lost object, or a moved tracked/comment boundary changes it.
# Field instruction tokens (IT/DIT), paragraph/table STRUCTURE tokens, and BOOKMARK boundaries are
# dropped from the DISPLAY stream: rebuilding a literal cross-reference as a field ADDS instruction
# text + a new bookmark target, and unwrapping/splitting changes structure — all invisible to the
# reader. Existing bookmarks are guarded separately (no-loss set check) so an ADD is allowed but a
# LOSS is not. Revision, comment and object tokens stay positional (moving/losing one is caught).
_DROP_VIS = {'IT', 'DIT', 'BMS', 'BME'} | _STRUCTURE_TOKENS

def _collapse_visible(stream):
    out, buf = [], None   # buf = (type, text) accumulating consecutive same-type visible text
    for tok in stream:
        t = tok[0]
        if t in _DROP_VIS:
            continue
        if t in ('T', 'DT'):
            if buf and buf[0] == t:
                buf = (t, buf[1] + tok[1])
            else:
                if buf is not None: out.append(('VTEXT', buf[0], buf[1]))
                buf = (t, tok[1])
            continue
        if buf is not None:
            out.append(('VTEXT', buf[0], buf[1])); buf = None
        out.append(tok)
    if buf is not None:
        out.append(('VTEXT', buf[0], buf[1]))
    return out


def visible_stream(parts):
    """Per story part: the display stream (see above). Whole-document form of the display gate."""
    return {name: _collapse_visible(s) for name, s in content_stream(parts).items()}


def visible_violations(before, after):
    """Differences between two DISPLAY streams — anything a display-preserving transform must not do
    (drop/alter visible text, lose an object, move a revision/comment/bookmark boundary)."""
    viols = []
    for name in sorted(set(before) | set(after)):
        b, a = before.get(name, []), after.get(name, [])
        if len(b) != len(a):
            viols.append((name, 'token-count', len(b), len(a))); continue
        for i, (x, y) in enumerate(zip(b, a)):
            if x != y:
                viols.append((name, i, x, y))
    return viols


# Namespaces a body fragment may reference (drawings, VML, compatibility) — declared on the synthetic
# wrapper so region_display parses a fragment whose source declared them on the document ROOT (as real
# Word packages do), including after an anchor->inline conversion drops an element-level declaration.
_FRAG_NS = (
    f'xmlns:w="{W}" xmlns:r="{RNS}" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
    'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
    'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml" '
    'xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:o="urn:schemas-microsoft-com:office:office"')


def region_display(xml_fragment):
    """The display stream of a FRAGMENT of body items (one or more <w:p>/<w:tbl>/markers), for the
    fast LOCAL gate on a single structural edit — no whole-document ledger rebuild. Because the
    display stream carries visible text AND every revision / comment / bookmark boundary AND every
    object, an unchanged fragment display stream proves this one edit disturbed no tracked content,
    lost no object, and left the reader's text identical, in O(fragment) not O(document)."""
    wrapped = (f'<w:document {_FRAG_NS}><w:body>'
               f'{xml_fragment}</w:body></w:document>').encode('utf8')
    try:
        return _collapse_visible(content_stream({'word/document.xml': wrapped})
                                 .get('word/document.xml', []))
    except Exception:
        return [('fragment-parse-error',)]


def region_bookmark_names(xml_fragment):
    """Multiset (name -> count) of bookmark starts in a body fragment. The LOCAL ASK gate uses it to
    forbid LOSING an existing bookmark (a cross-reference target) while allowing new ones to be
    added — bookmarks are dropped from the positional display stream, so this is their guard."""
    from collections import Counter
    return Counter(re.findall(r'<w:bookmarkStart\b[^>]*\bw:name="([^"]*)"', xml_fragment))


def bookmarks_lost(before_fragment, after_fragment):
    """True if any bookmark name present in `before_fragment` occurs FEWER times in `after_fragment`
    (an existing cross-reference anchor was dropped)."""
    b, a = region_bookmark_names(before_fragment), region_bookmark_names(after_fragment)
    return any(a.get(name, 0) < cnt for name, cnt in b.items())


def is_clean(d, allow_introduced=False):
    for key in ('lost', 'payload_altered', 'placement_altered', 'metadata_altered', 'lost_comments',
                'comment_body_altered', 'comment_anchor_altered', 'binary_altered',
                'relationship_altered'):
        if d[key]:
            return False
    if d['introduced'] and not allow_introduced:
        return False
    return True
