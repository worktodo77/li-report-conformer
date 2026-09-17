"""Namespace-aware Word numbering / style reference graph.

The engine historically read numbering only as `numId -> ilvl -> numFmt` from a paragraph's DIRECT
`w:numPr`, and merged definitions by "add the template's def when its numeric id is absent". That is
unsound: numbering ids are package-local, so the same id names different lists in two packages, and a
paragraph can be numbered purely through its paragraph style (no direct `numPr`). This module builds the
complete reference graph and RESOLVES the numbering each paragraph actually uses, so numbering can be
repaired and verified by meaning (format / level text / hierarchy / restart) rather than by numeric id.

Read + resolve is namespace-aware (ElementTree). Writes are done by the engine as targeted string edits
using the raw definition blocks kept here, so untouched revision content in the story parts stays
byte-exact and injected definitions keep the document's own `w:` prefixes."""
import re
import xml.etree.ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def _w(tag):
    return '{%s}%s' % (W, tag)


def _val(el, tag, attr='val'):
    if el is None:
        return None
    child = el.find(_w(tag))
    return child.get(_w(attr)) if child is not None else None


class NumberingGraph:
    """Model of one package's numbering.xml + styles.xml: abstract definitions, numbering instances (with
    level overrides), paragraph styles (with basedOn inheritance and style-carried numbering), plus
    resolvers that answer 'what list does this paragraph actually use, and how does it render?'."""

    def __init__(self, numbering_xml, styles_xml):
        self.num_xml = numbering_xml or ''
        self.styles_xml = styles_xml or ''
        self.abstract = {}      # abstractNumId -> {'levels': {ilvl: props}, 'numStyleLink', 'styleLink'}
        self.nums = {}          # numId -> {'aid': abstractNumId, 'overrides': {ilvl: {...}}}
        self.styles = {}        # styleId -> {'basedOn', 'name', 'type', 'numId', 'ilvl'}
        self._abs_raw = {}      # abstractNumId -> exact source <w:abstractNum>…</w:abstractNum>
        self._num_raw = {}      # numId -> exact source <w:num>…</w:num>
        self._parse_numbering()
        self._parse_styles()

    # ---- parsing -------------------------------------------------------------------------------
    def _parse_numbering(self):
        for m in re.finditer(r'<w:abstractNum\b[^>]*w:abstractNumId="([^"]+)".*?</w:abstractNum>',
                             self.num_xml, re.S):
            self._abs_raw[m.group(1)] = m.group(0)
        for m in re.finditer(r'<w:num\b[^>]*w:numId="([^"]+)".*?</w:num>', self.num_xml, re.S):
            self._num_raw[m.group(1)] = m.group(0)
        root = self._root(self.num_xml)
        if root is None:
            return
        for an in root.findall(_w('abstractNum')):
            aid = an.get(_w('abstractNumId'))
            levels = {lvl.get(_w('ilvl')): self._level_props(lvl) for lvl in an.findall(_w('lvl'))}
            self.abstract[aid] = {'levels': levels,
                                  'numStyleLink': _val(an, 'numStyleLink'),
                                  'styleLink': _val(an, 'styleLink')}
        for num in root.findall(_w('num')):
            nid = num.get(_w('numId'))
            ab = num.find(_w('abstractNumId'))
            overrides = {}
            for ov in num.findall(_w('lvlOverride')):
                il = ov.get(_w('ilvl'))
                lv = ov.find(_w('lvl'))
                overrides[il] = {'startOverride': _val(ov, 'startOverride'),
                                 'lvl': self._level_props(lv) if lv is not None else None}
            self.nums[nid] = {'aid': ab.get(_w('val')) if ab is not None else None,
                              'overrides': overrides}

    def _parse_styles(self):
        root = self._root(self.styles_xml)
        if root is None:
            return
        for st in root.findall(_w('style')):
            sid = st.get(_w('styleId'))
            if not sid:
                continue
            numId = ilvl = None
            ppr = st.find(_w('pPr'))
            if ppr is not None:
                npr = ppr.find(_w('numPr'))
                if npr is not None:
                    numId = _val(npr, 'numId')
                    ilvl = _val(npr, 'ilvl')
            self.styles[sid] = {'basedOn': _val(st, 'basedOn'), 'name': _val(st, 'name'),
                                'type': st.get(_w('type')), 'numId': numId, 'ilvl': ilvl}

    @staticmethod
    def _root(xml):
        if not xml or '<' not in xml:
            return None
        try:
            return ET.fromstring(xml)
        except ET.ParseError:
            return None

    @staticmethod
    def _level_props(lvl):
        if lvl is None:
            return {}
        return {'numFmt': _val(lvl, 'numFmt'), 'lvlText': _val(lvl, 'lvlText'),
                'start': _val(lvl, 'start'), 'isLgl': lvl.find(_w('isLgl')) is not None,
                'lvlRestart': _val(lvl, 'lvlRestart'), 'pStyle': _val(lvl, 'pStyle'),
                'suff': _val(lvl, 'suff')}

    # ---- resolution ----------------------------------------------------------------------------
    def style_numpr(self, style_id):
        """(numId, ilvl) a paragraph inherits from its style, following basedOn; None if the style chain
        carries no numbering. Cycle-safe."""
        seen = set()
        sid = style_id
        while sid and sid not in seen:
            seen.add(sid)
            s = self.styles.get(sid)
            if not s:
                return None
            if s['numId'] is not None:
                # numId 0 is an explicit "no numbering" override — it ends the chain with no list
                return None if s['numId'] == '0' else (s['numId'], s['ilvl'] or '0')
            sid = s['basedOn']
        return None

    def paragraph_numbering(self, direct_numId, direct_ilvl, style_id):
        """The list a paragraph ACTUALLY uses: its direct numPr if present, else the style's. This is the
        gap the old engine missed — a paragraph numbered only through its style."""
        if direct_numId is not None:
            return (direct_numId, direct_ilvl or '0')
        return self.style_numpr(style_id)

    def resolve_level(self, numId, ilvl):
        """Effective level record for (numId, ilvl): resolve num->abstractNum, apply lvlOverride and
        startOverride, follow numStyleLink. None if it cannot be resolved."""
        if numId is None:
            return None
        ilvl = ilvl or '0'
        num = self.nums.get(numId)
        if not num:
            return None
        ov = num['overrides'].get(ilvl)
        if ov and ov.get('lvl'):
            base = dict(ov['lvl'])
        else:
            base = self._abstract_level(num['aid'], ilvl)
            base = dict(base) if base else None
        if base is None:
            return None
        if ov and ov.get('startOverride') is not None:
            base['start'] = ov['startOverride']
        return base

    def _abstract_level(self, aid, ilvl, _seen=None):
        seen = _seen if _seen is not None else set()
        while aid is not None and aid not in seen:
            seen.add(aid)
            ab = self.abstract.get(aid)
            if not ab:
                return None
            lv = ab['levels'].get(ilvl)
            if lv is not None:
                return lv
            link = ab.get('numStyleLink')
            if link:
                sp = self.style_numpr(link)
                if sp:
                    aid = self.nums.get(sp[0], {}).get('aid')
                    continue
            return None
        return None

    def effective_format(self, numId, ilvl):
        lv = self.resolve_level(numId, ilvl)
        return lv.get('numFmt') if lv else None

    def is_bullet(self, numId, ilvl):
        """A list level renders as a bullet (vs a number). 'bullet' fmt or a lvlText that is a bullet
        glyph with no placeholder both count."""
        lv = self.resolve_level(numId, ilvl)
        if not lv:
            return None
        if lv.get('numFmt') == 'bullet':
            return True
        if lv.get('numFmt') in ('decimal', 'lowerLetter', 'upperLetter', 'lowerRoman', 'upperRoman',
                                'decimalZero', 'ordinal', 'cardinalText'):
            return False
        return None

    def paragraph_format(self, direct_numId, direct_ilvl, style_id):
        """Full resolved numbering for a paragraph: (numId, ilvl, level-record) or None."""
        pn = self.paragraph_numbering(direct_numId, direct_ilvl, style_id)
        if not pn:
            return None
        lv = self.resolve_level(pn[0], pn[1])
        return (pn[0], pn[1], lv) if lv is not None else (pn[0], pn[1], None)

    # ---- ids / raw blocks (for graph-aware import in the engine) --------------------------------
    def used_num_ids(self):
        return {int(n) for n in self.nums if n and n.isdigit()}

    def used_abstract_ids(self):
        return {int(a) for a in self.abstract if a and a.isdigit()}

    def raw_abstract(self, aid):
        return self._abs_raw.get(aid)

    def raw_num(self, nid):
        return self._num_raw.get(nid)

    def abstract_of(self, numId):
        n = self.nums.get(numId)
        return n['aid'] if n else None

    def resolved_levels_xml(self, aid, _seen=None):
        """The concrete <w:lvl> element XML an abstract ultimately resolves to, following numStyleLink
        RECURSIVELY through the whole chain (cycle- and dead-end-safe). Returns '' when the chain cannot
        be resolved — so an unresolved import is never turned into an apparently-valid empty definition
        (issue #1 R2). This is the dependency-closure resolution."""
        seen = _seen if _seen is not None else set()
        if aid is None or aid in seen:
            return ''
        seen.add(aid)
        ab = self.abstract.get(aid)
        raw = self.raw_abstract(aid)
        if ab is None or raw is None:
            return ''
        if ab.get('levels'):
            return ''.join(re.findall(r'<w:lvl\b.*?</w:lvl>', raw, re.S))
        link = ab.get('numStyleLink')
        if link:
            sp = self.style_numpr(link)
            if sp:
                return self.resolved_levels_xml(self.abstract_of(sp[0]), seen)   # recurse the chain
        return ''

    def resolved_abstract_xml(self, aid, _seen=None):
        """Raw <w:abstractNum> for `aid` with numStyleLink RESOLVED to concrete levels (recursively, via
        resolved_levels_xml), so an import is self-contained and cannot rebind to a same-named destination
        style. Returns None when the chain is unresolved/cyclic (the import must then be treated as
        unresolved, never emitted as an empty definition)."""
        raw = self.raw_abstract(aid)
        if not raw:
            return None
        ab = self.abstract.get(aid, {})
        if ab.get('levels'):
            return raw
        # deferred to a linked style — inline the fully-resolved levels or fail
        lvls = self.resolved_levels_xml(aid)
        if not lvls:
            return None
        raw = re.sub(r'<w:numStyleLink\b[^>]*/>', '', raw)
        return raw.replace('</w:abstractNum>', lvls + '</w:abstractNum>')
