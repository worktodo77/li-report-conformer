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


class Resolution:
    """A three-state numbering resolution (issue #1 A): RESOLVED with a concrete instance+level, NONE
    (the style/paragraph carries no numbering), or UNRESOLVED (a missing definition, a cycle, or an
    AMBIGUOUS instance selection). Unresolved is never silently treated as no-numbering or as a resolved
    list — it is surfaced. `level` is the effective level-property record for a resolved result."""
    __slots__ = ('state', 'numId', 'aid', 'ilvl', 'level', 'reason', 'provenance')
    RESOLVED = 'resolved'
    NONE = 'none'
    UNRESOLVED = 'unresolved'

    def __init__(self, state, numId=None, aid=None, ilvl=None, level=None, reason=None, provenance=None):
        self.state = state
        self.numId = numId
        self.aid = aid
        self.ilvl = ilvl
        self.level = level
        self.reason = reason
        self.provenance = provenance

    @property
    def resolved(self):
        return self.state == self.RESOLVED

    def as_tuple(self):
        """(numId, ilvl) for a resolved result, else None (backward-compatible with style_numpr callers)."""
        return (self.numId, self.ilvl) if self.resolved else None

    def signature(self, keys):
        """A comparable meaning signature: the level record for a resolved result, else a state marker so
        NONE and UNRESOLVED are distinguished from each other and from any resolved level."""
        if self.resolved and self.level is not None:
            return tuple(self.level.get(k) for k in keys)
        return self.state.upper()

    def __repr__(self):
        return 'Resolution(%s, numId=%s, ilvl=%s, reason=%s)' % (self.state, self.numId, self.ilvl, self.reason)


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
        self.pstyle_link = {}   # styleId -> (numId, ilvl) via a level's <w:pStyle> back-linkage
        self._parse_numbering()
        self._parse_styles()
        self._build_pstyle_links()

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

    def _build_pstyle_links(self):
        """Word links a multilevel list to paragraph styles: a level carrying <w:pStyle w:val="HeadingN"/>
        means paragraphs of that style are ASSOCIATED with this list at this level. Build a MULTIMAP
        styleId -> {(numId, ilvl), ...} across EVERY instance (issue #1 A): keeping all associations lets
        resolution detect an ambiguous instance selection instead of silently picking the first numId."""
        self.pstyle_link = {}
        for nid, num in self.nums.items():
            ab = self.abstract.get(num.get('aid'))
            if not ab:
                continue
            for ilvl, lv in (ab.get('levels') or {}).items():
                ps = lv.get('pStyle')
                if ps:
                    self.pstyle_link.setdefault(ps, set()).add((nid, ilvl))

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
    def _style_chain(self, style_id):
        """The style's basedOn chain (self first), cycle-safe."""
        chain = []
        seen = set()
        sid = style_id
        while sid and sid not in seen:
            seen.add(sid)
            chain.append(sid)
            s = self.styles.get(sid)
            if not s:
                break
            sid = s.get('basedOn')
        return chain

    def _style_numpr_raw(self, style_id):
        """(numId, ilvl, defining_style) from the FIRST explicit numPr in the basedOn chain; numId may be
        '0' (explicit suppression). (None, None, None) if the chain carries no explicit numPr."""
        for sid in self._style_chain(style_id):
            s = self.styles.get(sid)
            if s and s['numId'] is not None:
                return (s['numId'], s['ilvl'], sid)
        return (None, None, None)

    def _associated_level_ilvl(self, numId, style_ids):
        """Within the instance `numId`'s abstract, the ilvl of the level whose <w:pStyle> names one of
        `style_ids` (prefer the earliest style in the chain). None if no level is associated."""
        aid = self.abstract_of(numId)
        ab = self.abstract.get(aid)
        if not ab:
            return None
        levels = ab.get('levels') or {}
        for want in style_ids:                       # chain order: exact style first, then ancestors
            for ilvl, lv in levels.items():
                if lv.get('pStyle') == want:
                    return ilvl
        return None

    def resolve_style(self, style_id):
        """Three-state resolution of the numbering a STYLE carries (issue #1 A). Instance selection and
        level selection are separate: the explicit numPr (through basedOn) selects the INSTANCE; the level
        is the style's explicit ilvl, else the pStyle-associated level within that instance, else 0. A
        style with no explicit numPr resolves only through its pStyle association, and ONLY when that names
        a single instance — multiple candidate instances are UNRESOLVED, never a first-wins guess."""
        chain = self._style_chain(style_id)
        numId, ilvl, _def = self._style_numpr_raw(style_id)
        if numId == '0':
            return Resolution(Resolution.NONE, provenance='style-numId0')
        if numId is not None:
            if numId not in self.nums:
                return Resolution(Resolution.UNRESOLVED, numId=numId, reason='missing instance',
                                  provenance='style-numId')
            sel_ilvl = ilvl if ilvl is not None else self._associated_level_ilvl(numId, chain)
            if sel_ilvl is None:
                sel_ilvl = '0'
            lvl = self.resolve_level(numId, sel_ilvl)
            if lvl is None:
                return Resolution(Resolution.UNRESOLVED, numId=numId, ilvl=sel_ilvl,
                                  reason='level not resolvable in instance', provenance='style-numId')
            return Resolution(Resolution.RESOLVED, numId=numId, aid=self.abstract_of(numId),
                              ilvl=sel_ilvl, level=lvl, provenance='style-numId')
        # no explicit numPr in the chain -> reverse pStyle association
        cands = set()
        for sid in chain:
            cands |= self.pstyle_link.get(sid, set())
        numids = {c[0] for c in cands}
        if not numids:
            return Resolution(Resolution.NONE, provenance='no-association')
        if len(numids) > 1:
            return Resolution(Resolution.UNRESOLVED, reason='ambiguous instance selection (%d candidates)'
                              % len(numids), provenance='pstyle-ambiguous')
        nid = next(iter(numids))
        il = next((l for (n, l) in cands if n == nid), '0')
        lvl = self.resolve_level(nid, il)
        if lvl is None:
            return Resolution(Resolution.UNRESOLVED, numId=nid, ilvl=il, reason='linked level unresolvable',
                              provenance='pstyle-link')
        return Resolution(Resolution.RESOLVED, numId=nid, aid=self.abstract_of(nid), ilvl=il, level=lvl,
                          provenance='pstyle-link')

    def resolve_paragraph(self, direct_numId, direct_ilvl, style_id):
        """Three-state resolution of the numbering a PARAGRAPH actually uses. A direct numId selects the
        instance (its level is the direct ilvl, else the pStyle-associated level, else 0). A PARTIAL direct
        numPr (an ilvl with no numId) merges with the inherited instance rather than being discarded. With
        no direct numPr, resolution defers to the style."""
        if direct_numId == '0':
            return Resolution(Resolution.NONE, provenance='direct-numId0')
        if direct_numId is not None:
            if direct_numId not in self.nums:
                return Resolution(Resolution.UNRESOLVED, numId=direct_numId, reason='missing instance',
                                  provenance='direct')
            sel_ilvl = direct_ilvl
            if sel_ilvl is None:
                sel_ilvl = self._associated_level_ilvl(direct_numId, self._style_chain(style_id)) or '0'
            lvl = self.resolve_level(direct_numId, sel_ilvl)
            if lvl is None:
                return Resolution(Resolution.UNRESOLVED, numId=direct_numId, ilvl=sel_ilvl,
                                  reason='level not resolvable in instance', provenance='direct')
            return Resolution(Resolution.RESOLVED, numId=direct_numId, aid=self.abstract_of(direct_numId),
                              ilvl=sel_ilvl, level=lvl, provenance='direct')
        if direct_ilvl is not None:
            base = self.resolve_style(style_id)          # instance from the style, level from the direct ilvl
            if not base.resolved:
                return base
            lvl = self.resolve_level(base.numId, direct_ilvl)
            if lvl is None:
                return Resolution(Resolution.UNRESOLVED, numId=base.numId, ilvl=direct_ilvl,
                                  reason='level not resolvable in instance', provenance='direct-ilvl+style')
            return Resolution(Resolution.RESOLVED, numId=base.numId, aid=base.aid, ilvl=direct_ilvl,
                              level=lvl, provenance='direct-ilvl+style')
        return self.resolve_style(style_id)

    def style_numpr(self, style_id):
        """(numId, ilvl) a paragraph inherits from its style; None for no-numbering OR unresolved (callers
        needing the distinction use resolve_style). Backward-compatible shape."""
        return self.resolve_style(style_id).as_tuple()

    def paragraph_numbering(self, direct_numId, direct_ilvl, style_id):
        """(numId, ilvl) the paragraph actually uses; None for no-numbering OR unresolved."""
        return self.resolve_paragraph(direct_numId, direct_ilvl, style_id).as_tuple()

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
                raw = self._style_numpr_raw(link)     # explicit numPr only (avoids resolve recursion)
                if raw[0] and raw[0] != '0':
                    aid = self.nums.get(raw[0], {}).get('aid')
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
            raw = self._style_numpr_raw(link)         # explicit numPr only (avoids resolve recursion)
            if raw[0] and raw[0] != '0':
                return self.resolved_levels_xml(self.abstract_of(raw[0]), seen)   # recurse the chain
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
