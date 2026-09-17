"""LI report conformer: repair a damaged report so it conforms to the LI template and guidelines.

Two-pass architecture for interactive review:
  1. analyze() — runs all passes, applies everything, collects enriched judgment info
  2. apply_with_decisions(decisions) — re-runs from the original file, applying only
     accepted/changed judgment calls per user decisions

Original CLI flow (run() + save()) still works unchanged.
"""
import re, os, sys, json, zipfile
from dataclasses import dataclass, field

__all__ = ['Conformer', 'JudgmentCall', 'STYLE_ALTERNATIVES']

STYLE_ALTERNATIVES = [
    'NumberedParagraph', 'NumberedParagraphL1', 'NumberedParagraphL2',
    'ListBullet', 'Listbulletasasentence', 'Listbulletunderanumberedlist',
    'Dashunderabullet', 'ExcerptorQuote', 'BodyText',
]


@dataclass
class JudgmentCall:
    id: str
    kind: str
    item_index: int
    full_text: str
    short_text: str
    message: str
    recommended_action: str
    alternatives: list = field(default_factory=list)
    original_style: str = ''
    needs_review: bool = False   # on/adjacent to a tracked change or comment: review individually

# ---------------------------------------------------------------- shared helpers (same as corrupt.py)
# Empty body-level marker elements (self-closing): bookmarks, comment ranges, tracked move/
# permission/custom-xml ranges. These sit BETWEEN paragraphs in reviewed drafts.
BODY_MARKERS = ('bookmarkStart', 'bookmarkEnd', 'commentRangeStart', 'commentRangeEnd',
                'moveFromRangeStart', 'moveFromRangeEnd', 'moveToRangeStart', 'moveToRangeEnd',
                'permStart', 'permEnd', 'customXmlInsRangeStart', 'customXmlInsRangeEnd',
                'customXmlDelRangeStart', 'customXmlDelRangeEnd',
                'customXmlMoveFromRangeStart', 'customXmlMoveFromRangeEnd',
                'customXmlMoveToRangeStart', 'customXmlMoveToRangeEnd', 'proofErr')

def split_body(body):
    items = []; i = 0
    marker_re = re.compile(r'<w:(%s)\b' % '|'.join(BODY_MARKERS))
    while i < len(body):
        mk = marker_re.match(body, i)
        if mk:
            items.append(body[i:body.index('/>', i) + 2]); i = body.index('/>', i) + 2; continue
        m = re.match(r'<w:(p|tbl|sectPr|sdt)\b', body[i:])
        if not m: raise ValueError(body[i:i+60])
        tag = m.group(1)
        depth = 0; j = i; pat = re.compile(r'<(/?)w:%s\b([^>]*?)(/?)>' % tag)
        while True:
            mm = pat.search(body, j)
            if mm.group(1) == '' and mm.group(3) == '': depth += 1
            elif mm.group(1) == '/': depth -= 1
            j = mm.end()
            if depth == 0: break
        e = j
        items.append(body[i:e]); i = e
    return items
RPR_ORDER=['rStyle','rFonts','b','bCs','i','iCs','caps','smallCaps','strike','dstrike','outline','shadow','emboss','imprint','noProof','snapToGrid','vanish','webHidden','color','spacing','w','kern','position','sz','szCs','highlight','u','effect','bdr','shd','fitText','vertAlign','rtl','cs','em','lang','eastAsianLayout','specVanish','oMath','rPrChange']
PPR_ORDER=['pStyle','keepNext','keepLines','pageBreakBefore','framePr','widowControl','numPr','suppressLineNumbers','pBdr','shd','tabs','suppressAutoHyphens','kinsoku','wordWrap','overflowPunct','topLinePunct','autoSpaceDE','autoSpaceDN','bidi','adjustRightInd','snapToGrid','spacing','ind','contextualSpacing','mirrorIndents','suppressOverlap','jc','textDirection','textAlignment','textboxTightWrap','outlineLvl','divId','cnfStyle','rPr','sectPr','pPrChange']
TBLPR_ORDER=['tblStyle','tblpPr','tblOverlap','bidiVisual','tblStyleRowBandSize','tblStyleColBandSize','tblW','jc','tblCellSpacing','tblInd','tblBorders','shd','tblLayout','tblCellMar','tblLook','tblCaption','tblDescription','tblPrChange']
TCPR_ORDER=['cnfStyle','tcW','gridSpan','hMerge','vMerge','tcBorders','shd','noWrap','tcMar','textDirection','tcFitText','vAlign','hideMark','headers']
def children(inner):
    out=[]; i=0
    while i < len(inner):
        m=re.match(r'<(\w+):(\w+)\b', inner[i:])
        if not m: raise ValueError(inner[i:i+40])
        ns,tag=m.group(1),m.group(2); depth=0; j=i; pat=re.compile(r'<(/?)%s:%s\b([^>]*?)(/?)>' % (ns,tag))
        while True:
            mm=pat.search(inner,j)
            if mm is None: raise ValueError('unbalanced '+tag)
            if mm.group(1)=='' and mm.group(3)=='': depth+=1
            elif mm.group(1)=='/': depth-=1
            j=mm.end()
            if depth==0: break
        out.append((tag if ns=='w' else ns+':'+tag, inner[i:j])); i=j
    return out
def span(xml, tag, start):
    depth=0; j=start; pat=re.compile(r'<(/?)w:%s\b([^>]*?)(/?)>' % tag)
    while True:
        mm=pat.search(xml,j)
        if mm is None: return None
        if mm.group(1)=='' and mm.group(3)=='': depth+=1
        elif mm.group(1)=='/': depth-=1
        j=mm.end()
        if depth==0: return j
def reorder(xml, tag, order):
    out=[]; i=0; opn='<w:%s>'%tag
    while True:
        k=xml.find(opn,i)
        if k<0: out.append(xml[i:]); break
        e=span(xml,tag,k)
        if e is None: out.append(xml[i:]); break
        inner=xml[k+len(opn):e-len(tag)-5]
        inner=reorder(inner,tag,order) if opn in inner else inner
        try:
            ch=children(inner); last={}
            for n,(t,x) in enumerate(ch): last[t]=n
            ch=[c for n,c in enumerate(ch) if last[c[0]]==n or c[0] in ('tab',)]
            ch=sorted(ch, key=lambda c: order.index(c[0]) if c[0] in order else 999)
            inner=''.join(c[1] for c in ch)
        except (ValueError, AttributeError): pass
        out.append(xml[i:k]+opn+inner+'</w:%s>'%tag); i=e
    return ''.join(out)
def normalize(xml):
    for t,o in (('rPr',RPR_ORDER),('pPr',PPR_ORDER),('tblPr',TBLPR_ORDER),('tcPr',TCPR_ORDER)): xml=reorder(xml,t,o)
    return xml
def esc(s): return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

_TYPO_MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December'
# Honorifics/abbreviations that end in a lowercase letter + period but are NOT a sentence boundary, so
# the two-space sentence rule must NOT fire after them (e.g. "Mr. Hall", "vs. The", "Fig. 3-2 ... See").
_SENTENCE_ABBREV = {
    'mr', 'mrs', 'ms', 'dr', 'prof', 'st', 'sr', 'jr', 'rev', 'hon', 'messrs',
    'vs', 'etc', 'al', 'cf', 'viz', 'ibid', 'no', 'nos', 'fig', 'figs', 'tbl',
    'vol', 'vols', 'ltd', 'inc', 'co', 'corp', 'dept', 'div', 'sec', 'art',
    'para', 'pp', 'ref', 'ex', 'app', 'attach', 'ed', 'eds', 'esp', 'approx',
}
def _sentence_space(m):
    """Add the house second space between sentences, but not after a known abbreviation/initial."""
    lead = m.group(1)
    if lead != ')' and (len(lead) == 1 or lead.lower() in _SENTENCE_ABBREV):
        return m.group(0)   # abbreviation or single-letter initial — leave the single space
    return lead + '.  ' + m.group(2)
def typo_text(t):
    """The house typography transform on a single text token (smart quotes, en dashes, sentence
    spacing, date/ligature fixes). Shared by the typography pass AND the content-stream gate as the
    ONLY authorized text change, so any other text edit is caught."""
    t = re.sub(r'(\d)"', r'\1-inch', t)
    t = re.sub(r'(^|[\s(\[])"', '\\1\u201c', t); t = t.replace('"', '\u201d')
    t = re.sub(r"(^|[\s(\[])'", '\\1\u2018', t); t = t.replace("'", '\u2019')
    t = re.sub(r'(\w)--(\w)', '\\1\u2013\\2', t)
    t = re.sub(r'([A-Za-z]*[a-z]|\))\. ([A-Z])', _sentence_space, t)
    t = re.sub(r'\b0(\d) (%s)' % _TYPO_MONTHS, r'\1 \2', t)
    return t.replace('\ufb00', 'ff').replace('\ufb01', 'fi').replace('\ufb02', 'fl')

# ---------------------------------------------------------------- LI house style (deterministic)
# The DETERMINISTIC subset of docs/LI_STYLE_GUIDE.md \u2014 applied like typography, and authorized by the
# preservation gate via house_norm() (the gate confirms the ONLY change is house-style case/spelling/
# terminology, nothing else). Judgment rules (voice, concision, flow) are the separate LLM layer.

# CAP-1/CAP-2: generic party/role and technical terms lowercased in LI prose. Multi-word phrases first
# so the regex prefers the longest match.
HOUSE_LOWER = [
    'Contract Completion Date', 'Commercial Operation Date', 'Differing Site Conditions',
    'Concurrent Delay', 'Extension of Time', 'Liquidated Damages', 'Total Float', 'Free Float',
    'Terminal Float', 'Critical Path', 'Completion Date', 'Change Order', 'Lump-Sum Turnkey',
    'Contractor', 'Owner', 'Employer', 'Engineer', 'Subcontractor', 'Government', 'Party', 'Surety',
    'Claimant', 'Respondent', 'Turnkey', 'Float', 'Delay',
]
_LOWER_ALT = '|'.join(re.escape(w) for w in HOUSE_LOWER)
# a term is lowercased only when it FOLLOWS a determiner/preposition/conjunction \u2014 this catches
# "the Contractor" (Claire's #1 edit) while never lowercasing a genuinely sentence-initial term.
_DET = (r'the|a|an|of|for|to|in|on|by|with|and|or|that|which|this|these|those|its|their|any|each|'
        r'no|between|among|from|at|as|when|where|if|because|per|under|over|such')
# Case-insensitive on the DETERMINER (so "The Contractor" at a sentence start is caught) but
# case-SENSITIVE on the TERM: only a Title-Case term ("Contractor") is lowered, never an ALL-CAPS one
# ("CONTRACTOR"), which is usually intentional emphasis or a heading fragment. This also keeps the pass
# in step with house_norm (which lowercases Title-Case terms only), so the gate authorizes it.
_HOUSE_LOWER_RE = re.compile(r'\b((?i:%s))(\s+)(%s)\b' % (_DET, _LOWER_ALT))
# CAP-5 (expert-report exception): capitalize the specific Report / Project.
_HOUSE_CAP_RE = re.compile(r'\b(the|this|my|our|its|present|entire|whole)(\s+)(report|project)\b', re.I)
# British -> American spelling + the programme->schedule terminology swap (LI prose only).
BRIT_US = {
    'programme': 'schedule', 'programmes': 'schedules', 'analyse': 'analyze', 'analysed': 'analyzed',
    'analysing': 'analyzing', 'analyses': 'analyzes', 'modelling': 'modeling', 'modelled': 'modeled',
    'behaviour': 'behavior', 'behaviours': 'behaviors', 'colour': 'color', 'favour': 'favor',
    'labour': 'labor', 'organisation': 'organization', 'organisations': 'organizations',
    'organise': 'organize', 'organised': 'organized', 'recognise': 'recognize',
    'recognised': 'recognized', 'prioritise': 'prioritize', 'judgement': 'judgment',
    'defence': 'defense', 'centre': 'center', 'metre': 'meter', 'litre': 'liter', 'fibre': 'fiber',
    'matrices': 'matrixes',
}
_BRIT_RE = re.compile(r'\b(%s)\b' % '|'.join(BRIT_US), re.I)
# "USA"/"U.S.A." -> "U.S." — deliberately NOT bare "US" (would corrupt the currency prefix "US$").
_USA_RE = re.compile(r'\bU\.S\.A\.|\bU\.S\.A\b|\bUSA\b')
_ACR_PLURAL_RE = re.compile(r"\b([A-Z]{2,})'s\b")               # EOT's -> EOTs
_EG_RE = re.compile(r'\b(e\.g\.|i\.e\.)(?=\s)')                 # e.g. <space> -> e.g., (skip if already ",")


def _brit_case(m):
    """British->American keeping the leading capitalization of the source word."""
    w = m.group(1); repl = BRIT_US[w.lower()]
    return repl.capitalize() if w[:1].isupper() else repl


def house_norm(t):
    """Canonicalize away exactly the authorized house-style variation, so house_ok can confirm two
    texts differ ONLY by house-style edits. Not the corrective transform \u2014 that is house_style().
    British->American is case-preserving here (as in the pass), so a capitalized 'Analysed'->'Analyzed'
    canonicalizes the same from both sides."""
    t = _BRIT_RE.sub(_brit_case, t)
    t = _USA_RE.sub('U.S.', t)
    t = re.sub(r'\b(%s)\b' % _LOWER_ALT, lambda m: m.group(0).lower(), t)
    t = re.sub(r'\b(report|project)\b', lambda m: m.group(0).lower(), t, flags=re.I)
    t = _ACR_PLURAL_RE.sub(lambda m: m.group(1) + 's', t)
    t = _EG_RE.sub(lambda m: m.group(1) + ',', t)
    return t


def house_ok(old, new):
    return house_norm(old) == house_norm(new)
def text_of(x): return re.sub('<[^>]+>', '', re.sub(r'<w:drawing>.*?</w:drawing>', '', re.sub(r'<w:instrText.*?</w:instrText>', '', x, flags=re.S), flags=re.S))

# ---------------------------------------------------------------- LI style knowledge
NUMBERED = {'NumberedParagraph','NumberedParagraphL1','NumberedParagraphL2','NumberedParagraphL3','NumberedParagraphL4'}
LISTS = {'ListBullet','Listbulletasasentence','Listbulletunderanumberedlist','Dashunderabullet'}
HEADINGS = {f'Heading{i}' for i in range(1,7)}
STYLE_NUMBERED = NUMBERED | LISTS | HEADINGS
RECOMMENDED = NUMBERED | LISTS | HEADINGS | {'BodyText','Caption','ExcerptorQuote','TableorFigureSubtitle','SpacebehindafteraGraphic','TableData','TableofFigures','TOCListTitle','Title','TitleofProject','FootnoteText','Footer','Header','PRIVCONFSTATEMENT'} | {f'TOC{i}' for i in range(1,10)}
ALLOWED_PPR = {'pStyle','rPr','sectPr','keepNext','keepLines'}
ALLOWED_PPR_BY_STYLE = {'Caption':{'jc'},'TableData':{'jc'},'BodyText':{'ind'},'SpacebehindafteraGraphic':{'jc'},'Heading1':{'pageBreakBefore','spacing'}}
ALLOWED_RPR = {'rStyle','b','bCs','i','iCs','vanish','noProof','lang'}
LITABLE = ('<w:style w:type="table" w:customStyle="1" w:styleId="LITable"><w:name w:val="LI Table"/><w:basedOn w:val="TableNormal"/><w:uiPriority w:val="1"/><w:qFormat/>'
  '<w:pPr><w:spacing w:before="60" w:after="60" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr><w:rPr><w:color w:val="000000"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>'
  '<w:tblPr><w:jc w:val="center"/><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:left w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:right w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="808080"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="808080"/></w:tblBorders><w:tblCellMar><w:left w:w="72" w:type="dxa"/><w:right w:w="72" w:type="dxa"/></w:tblCellMar></w:tblPr>'
  '<w:tcPr><w:vAlign w:val="center"/></w:tcPr><w:tblStylePr w:type="firstRow"><w:pPr><w:keepNext/><w:jc w:val="center"/></w:pPr><w:rPr><w:b/><w:bCs/><w:color w:val="FFFFFF"/></w:rPr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr><w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="054F8A"/><w:vAlign w:val="center"/></w:tcPr></w:tblStylePr></w:style>')

class Conformer:
    def __init__(self, template, path):
        self.template_path = template
        self.input_path = path
        self.parts = {}
        with zipfile.ZipFile(path) as z:
            for n in z.namelist(): self.parts[n] = z.read(n)
        with zipfile.ZipFile(template) as z:
            self.t_styles = z.read('word/styles.xml').decode('utf8'); self.t_num = z.read('word/numbering.xml').decode('utf8')
        if 'w:styleId="LITable"' not in self.t_styles: self.t_styles = self.t_styles.replace('</w:styles>', LITABLE + '</w:styles>')
        self.doc = self.parts['word/document.xml'].decode('utf8')
        self.styles = self.parts['word/styles.xml'].decode('utf8'); self.num = self.parts['word/numbering.xml'].decode('utf8')
        self.fn = self.parts['word/footnotes.xml'].decode('utf8'); self.settings = self.parts['word/settings.xml'].decode('utf8')
        self.head, body, self.tail = re.search(r'(.*<w:body>)(.*)(</w:body>.*)', self.doc, re.S).groups()
        self.items = split_body(body)
        self.b0 = next(i for i, it in enumerate(self.items) if 'w:val="Heading1"' in it)
        self.log = []; self.judgment = []; self.audit = []
        self.pending_judgments = []
        self.decisions = None
        from conformer import revisions as _rev
        # Per-part parse cache (bytes-keyed) shared by every verify/content-stream call this run, so
        # unchanged parts are parsed once. Seed it by building the original ledger through it.
        self._verify_cache = {}
        self.revision_ledger = _rev.Ledger.build(self.parts, cache=self._verify_cache)
        self.disposition = None      # None/clean → legacy pipeline; 'preserve' → review-preserving
        self.progress = None         # optional fn(phase_key, detail) for live UI progress; see _emit
        self.exceptions = []         # (pass_name, reason) for passes rolled back in preserve mode
        self._jcall_counter = 0
        self.pending_edits = []      # mechanical TEXT edits (before/after) for the UI, per-fix skippable
        self._edit_counter = {}
        self.stname = dict(re.findall(r'<w:style [^>]*w:styleId="([^"]+)"[^>]*><w:name w:val="([^"]+)"', self.styles))
        self.numfmt = {}
        abs_fmt = {}
        for m in re.finditer(r'<w:abstractNum w:abstractNumId="(\d+)"[^>]*>(.*?)</w:abstractNum>', self.num, re.S):
            abs_fmt[m.group(1)] = {l: f for l, f in re.findall(r'<w:lvl w:ilvl="(\d)"[^>]*>.*?<w:numFmt w:val="(\w+)"', m.group(2), re.S)}
        for nid, aid in re.findall(r'<w:num w:numId="(\d+)"[^>]*><w:abstractNumId w:val="(\d+)"/>', self.num): self.numfmt[nid] = abs_fmt.get(aid, {})
        self.template_style_ids = set(re.findall(r'w:styleId="([^"]+)"', self.t_styles))
    # ---- item access (body indices)
    def n(self): return len(self.items) - self.b0
    def item(self, i): return self.items[self.b0 + i]
    def set(self, i, x): self.items[self.b0 + i] = x
    def text(self, i): return text_of(self.item(i))
    def style(self, i):
        x = self.item(i)
        if x.startswith('<w:tbl'): return 'TABLE'
        m = re.search(r'<w:pStyle w:val="([^"]+)"', x); return m.group(1) if m else 'Normal'
    def set_style(self, i, st):
        x = self.item(i)
        if '<w:pStyle' in x: x = re.sub(r'<w:pStyle w:val="[^"]+"/>', f'<w:pStyle w:val="{st}"/>', x, count=1)
        elif '<w:pPr>' in x: x = x.replace('<w:pPr>', f'<w:pPr><w:pStyle w:val="{st}"/>', 1)
        else: x = re.sub(r'<w:p\b[^>]*>', lambda m: m.group(0) + f'<w:pPr><w:pStyle w:val="{st}"/></w:pPr>', x, count=1)
        self.set(i, x)
    def ppr(self, i):
        m = re.search(r'<w:pPr>(.*?)</w:pPr>', self.item(i), re.S); return m.group(1) if m else ''
    def numpr(self, i):
        m = re.search(r'<w:numPr>.*?</w:numPr>', self.ppr(i), re.S)
        if not m: return None
        lvl = re.search(r'<w:ilvl w:val="(\d+)"', m.group(0)); nid = re.search(r'<w:numId w:val="(\d+)"', m.group(0))
        return (nid.group(1) if nid else '0', lvl.group(1) if lvl else '0')
    def is_par(self, i): return self.item(i).startswith('<w:p')
    def prev_par(self, i):
        j = i - 1
        while j >= 0 and not self.is_par(j): j -= 1
        return j
    def say(self, kind, i, msg, cat=None):
        (self.judgment if kind == 'J' else self.log).append(
            {'item': i, 'text': self.text(i)[:50] if 0 <= i < self.n() else '', 'msg': msg, 'cat': cat})

    def _skip(self, cat):
        """True when the user chose to skip a whole conformance-fix category on Apply. During analyze
        self.decisions is None, so every fix is shown; the skip only takes effect on the apply re-run."""
        d = self.decisions
        return bool(d) and d.get('conf:' + cat) == 'skip'

    def _jcall(self, kind, i, msg, recommended, alternatives=None):
        self._jcall_counter += 1
        call_id = f'{kind}_{self._jcall_counter}'
        full = self.text(i) if 0 <= i < self.n() else ''
        short = full[:50] + ('...' if len(full) > 50 else '')
        orig_style = self.style(i) if 0 <= i < self.n() and self.is_par(i) else ''
        jc = JudgmentCall(
            id=call_id, kind=kind, item_index=i, full_text=full,
            short_text=short, message=msg, recommended_action=recommended,
            alternatives=alternatives or [], original_style=orig_style,
        )
        self.pending_judgments.append(jc)
        return jc

    def _decision_for(self, jc):
        if self.decisions is None:
            return 'accept'
        return self.decisions.get(jc.id, 'skip')

    def _next_edit_id(self, kind):
        self._edit_counter[kind] = self._edit_counter.get(kind, 0) + 1
        return f'{kind}_{self._edit_counter[kind]}'

    def _edit_skipped(self, eid):
        return self.decisions is not None and self.decisions.get(eid) == 'skip'

    def _apply_text_edit(self, kind, label, i, before_xml, after_xml):
        """Apply a per-paragraph mechanical TEXT edit unless the user skipped it, and record it
        (before/after visible text) so the UI can show a before→after with the change highlighted and
        offer a per-fix Skip. Deterministic id ('house_3'), so a skip survives the analyze→apply round
        trip. Returns True if the edit was applied."""
        eid = self._next_edit_id(kind)
        before_t = text_of(before_xml)
        after_t = text_of(after_xml)
        skipped = self._edit_skipped(eid)
        self.pending_edits.append({'id': eid, 'kind': kind, 'label': label, 'item': i,
                                   'before': before_t, 'after': after_t, 'skipped': skipped})
        if skipped:
            return False
        self.set(i, after_xml)
        return True

    # ================================================================ passes
    def revert_tracked_formatting(self):
        cnt = 0
        for i in range(self.n()):
            x = self.item(i)
            if '<w:pPrChange' not in x and '<w:rPrChange' not in x: continue
            k = x.find('<w:pPr>')
            if k >= 0 and '<w:pPrChange' in x:
                e = span(x, 'pPr', k); blk = x[k:e]
                orig = re.search(r'<w:pPrChange[^>]*><w:pPr>(.*?)</w:pPr></w:pPrChange>', blk, re.S)
                if orig: x = x[:k] + '<w:pPr>' + orig.group(1) + '</w:pPr>' + x[e:]
            def rpc(m):
                orig = re.search(r'<w:rPrChange[^>]*>(?:<w:rPr>(.*?)</w:rPr>|<w:rPr/>)</w:rPrChange>', m.group(0), re.S)
                return '<w:rPr>' + (orig.group(1) or '' if orig else '') + '</w:rPr>'
            x = re.sub(r'<w:rPr>(?:(?!</w:rPr>).)*?<w:rPrChange.*?</w:rPrChange></w:rPr>', rpc, x, flags=re.S)
            self.set(i, x); cnt += 1
        if cnt: self.say('M', -1, f'reverted tracked formatting/style changes on {cnt} paragraphs')

    def unwrap_and_prune(self):
        i = 0
        while i < self.n():
            x = self.item(i)
            if x.startswith('<w:tbl') and '<w:tblStyle' not in x and len(re.findall(r'<w:tc>', x)) == 1 and len(re.findall(r'<w:tr\b', x)) == 1:
                inner = re.search(r'<w:tc>.*?</w:tcPr>(.*)</w:tc>', x, re.S).group(1)
                paras = split_body(inner)
                self.items[self.b0 + i:self.b0 + i + 1] = paras; self.say('M', i, f'unwrapped one-cell wrapper table into {len(paras)} paragraphs'); continue
            if self.is_par(i) and re.fullmatch(r'<w:p\b[^>]*>(<w:pPr>.*?</w:pPr>)?<w:r><w:br w:type="page"/></w:r></w:p>', x, re.S):
                del self.items[self.b0 + i]; self.say('M', i, 'removed manual page-break paragraph'); continue
            if self.is_par(i) and '<w:sectPr' not in x and '<w:drawing>' not in x and not text_of(x).strip() and self.style(i) in (NUMBERED | {'Normal', 'ListParagraph'}):
                del self.items[self.b0 + i]; self.say('M', i, 'deleted empty numbered/Normal paragraph'); continue
            i += 1

    _REV_RE = re.compile(r'<w:(ins|del|moveFrom|moveTo|pPrChange|rPrChange)\b'
                         r'|<w:commentRangeStart\b|<w:commentReference\b')
    def _para_has_revision(self, i):
        return bool(self._REV_RE.search(self.item(i)))

    def classify(self):
        """Map non-LI paragraph styles to LI styles using numbering, context and text. Changing a
        paragraph's style is orthogonal to the tracked content inside it, so this runs on revised
        paragraphs too; the preservation gate verifies nothing was disturbed."""
        for i in range(self.n()):
            if not self.is_par(i): continue
            st = self.style(i); x = self.item(i); t = self.text(i).strip()
            if not t and '<w:drawing>' in x and st in (NUMBERED | LISTS):
                self.set_style(i, 'SpacebehindafteraGraphic')
                self.say('M', i, f'{st} figure container -> SpacebehindafteraGraphic (image should not be numbered)')
                continue
            if st in RECOMMENDED: continue
            if '<w:sectPr' in x: continue
            if not t and '<w:drawing>' not in x:
                if st not in self.template_style_ids:
                    self.set_style(i, 'SpacebehindafteraGraphic')
                    self.say('M', i, f'empty {st} paragraph -> SpacebehindafteraGraphic (foreign style)')
                continue
            has_drawing = '<w:drawing>' in x
            if has_drawing and not t:
                new = 'SpacebehindafteraGraphic'; msg = f'{st} figure/graphic container -> Space behind after a Graphic'
                jc = self._jcall('style', i, msg, new, alternatives=STYLE_ALTERNATIVES)
                self.say('J', i, msg)
                decision = self._decision_for(jc)
                if decision == 'accept':
                    self.set_style(i, new)
                elif decision.startswith('change:'):
                    self.set_style(i, decision.split(':', 1)[1])
                continue
            np_ = self.numpr(i); fmt = self.numfmt.get(np_[0], {}).get(np_[1]) if np_ else None
            prev = self.prev_par(i); pst = self.style(prev) if prev >= 0 else ''; ptxt = self.text(prev).strip() if prev >= 0 else ''
            runs_i = all('<w:i/>' in r for r in re.findall(r'<w:r\b.*?</w:r>', x, re.S) if '<w:t' in r) and '<w:i/>' in x
            ind = re.search(r'<w:ind [^>]*w:left="(\d+)"', self.ppr(i))
            if fmt == 'bullet' or (st == 'ListParagraph' and np_):
                lvl = int(np_[1]) if np_ else 0
                if lvl >= 1: new = 'Dashunderabullet'
                elif pst in ('NumberedParagraphL1', 'Listbulletunderanumberedlist') and not ptxt.endswith(':'): new = 'Listbulletunderanumberedlist'
                elif len(t) > 45 or t.endswith((';', '.', ':')): new = 'Listbulletasasentence'
                else: new = 'ListBullet'
                msg = f'{st} bulleted paragraph -> {new} (level {lvl}, length {len(t)}, follows {pst})'
            elif runs_i and ind and int(ind.group(1)) >= 700 and not np_:
                new = 'ExcerptorQuote'; msg = f'{st} italic indented paragraph -> Excerpt or Quote'
            elif not np_ and ((ptxt.endswith(':') and (t.endswith(';') or t.endswith('; and'))) or (pst == 'Listbulletasasentence' and (t.endswith(';') or t.endswith('; and') or (ptxt.endswith('; and') and t.endswith('.'))))):
                new = 'Listbulletasasentence'; msg = f'{st} item after a colon lead-in ending with ";" -> List bullet as a sentence'
            else:
                new = 'NumberedParagraph'; msg = f'{st} body paragraph -> Numbered Paragraph'
            jc = self._jcall('style', i, msg, new, alternatives=STYLE_ALTERNATIVES)
            self.say('J', i, msg)
            decision = self._decision_for(jc)
            if decision == 'accept':
                self.set_style(i, new)
            elif decision.startswith('change:'):
                self.set_style(i, decision.split(':', 1)[1])

    def merge_pdf_lines(self):
        i = 0
        while i < self.n() - 1:
            if self.is_par(i) and self.style(i) == 'ExcerptorQuote' and self.is_par(i + 1) and self.style(i + 1) == 'ExcerptorQuote':
                a, b = self.text(i).rstrip(), self.text(i + 1).strip()
                if not re.search(r'[.!?:;"\u201d]$', a) or a.endswith('-'):
                    msg = 'joined PDF line-break paragraphs into one excerpt'
                    jc = self._jcall('merge', i, msg, 'Merge paragraphs')
                    self.say('J', i, msg)
                    if self._decision_for(jc) == 'accept':
                        joined = (a[:-1] + b) if a.endswith('-') and b[:1].islower() else (a + ' ' + b)
                        self.set(i, re.sub(r'(<w:r\b.*)</w:p>', '', self.item(i), flags=re.S).split('</w:pPr>')[0] + '</w:pPr>' + f'<w:r><w:t xml:space="preserve">{esc(joined)}</w:t></w:r></w:p>')
                        del self.items[self.b0 + i + 1]; continue
            i += 1

    def fix_headings(self):
        for i in range(self.n()):
            if not self.is_par(i): continue
            st = self.style(i); t = self.text(i)
            if st in ('Heading1', 'Heading2') and '<w:caps/>' in self.item(i):
                x = re.sub(r'<w:t( xml:space="preserve")?>([^<]*)</w:t>', lambda m: f'<w:t{m.group(1) or ""}>{m.group(2).upper()}</w:t>', self.item(i))
                self.set(i, x.replace('<w:caps/>', '')); self.say('M', i, 'All Caps attribute replaced by true capitals')
            if st in HEADINGS and '  ' in t.strip() and len(t) > 80:
                m = re.search(r'<w:r>(?:<w:rPr>.*?</w:rPr>)?<w:t xml:space="preserve">  </w:t></w:r>', self.item(i))
                if m:
                    msg = 'split body text that had been merged into a heading paragraph'
                    jc = self._jcall('split', i, msg, 'Split heading from body text')
                    self.say('J', i, msg)
                    if self._decision_for(jc) == 'accept':
                        head_x = self.item(i)[:m.start()] + '</w:p>'; rest = self.item(i)[m.end():]
                        body_x = '<w:p><w:pPr><w:pStyle w:val="NumberedParagraph"/></w:pPr>' + rest
                        self.set(i, head_x); self.items.insert(self.b0 + i + 1, body_x)
        for i in range(self.n()):
            if not self.is_par(i) or self.style(i) != 'NumberedParagraph': continue
            t = self.text(i).strip(); words = t.split()
            if 1 <= len(words) <= 6 and not re.search(r'[.;:,!?]$', t) and all(w[:1].isupper() or w.lower() in ('the', 'of', 'and', 'a', 'an', 'in', 'to', 'for', 'or') for w in words) and not re.search(r'\d', t):
                j = self.prev_par(i)
                while j >= 0 and self.style(j) not in HEADINGS: j = self.prev_par(j)
                lvl = self.style(j) if j >= 0 else 'Heading2'
                if lvl == 'Heading1': lvl = 'Heading2'
                msg = f'short title-case numbered paragraph promoted to {lvl}'
                jc = self._jcall('promote', i, msg, f'Promote to {lvl}')
                self.say('J', i, msg)
                if self._decision_for(jc) == 'accept':
                    self.set_style(i, lvl)

    def fix_levels(self):
        for i in range(self.n()):
            if not self.is_par(i): continue
            st = self.style(i)
            if st == 'NumberedParagraphL2':
                p = self.prev_par(i)
                if p >= 0 and self.style(p) == 'NumberedParagraph':
                    msg = 'sub-level list started at L2 under a numbered paragraph; promoted run to L1'
                    jc = self._jcall('level', i, msg, 'Promote L2 to L1')
                    self.say('J', i, msg)
                    if self._decision_for(jc) == 'accept':
                        k = i
                        while k < self.n() and self.style(k) == 'NumberedParagraphL2': self.set_style(k, 'NumberedParagraphL1'); k += 1
            if st == 'NumberedParagraphL1' and self.text(i).strip().endswith(':') and i + 1 < self.n() and self.style(i + 1) in ('ListBullet', 'Listbulletasasentence'):
                msg = 'L1 lead-in followed by List Bullet items promoted to Numbered Paragraph'
                jc = self._jcall('level', i, msg, 'Promote L1 to Numbered Paragraph')
                self.say('J', i, msg)
                if self._decision_for(jc) == 'accept':
                    self.set_style(i, 'NumberedParagraph')

    def strip_direct(self):
        i = 0
        while i < self.n():
            x = self.item(i)
            if not self.is_par(i): i += 1; continue
            # Preserve mode: skip revised paragraphs (stripping their rPr/pPr would drop a mark or
            # snapshot) and never delete paragraphs here (that is the AUTO structural prune pass).
            preserve = self.disposition == 'preserve'
            if preserve and self._para_has_revision(i): i += 1; continue
            st = self.style(i)
            if not preserve and '<w:sectPr' not in x and st in NUMBERED and not self.text(i).strip() and '<w:drawing>' not in x:
                del self.items[self.b0 + i]; self.say('M', i, 'deleted empty numbered paragraph'); continue
            m = re.search(r'<w:pPr>(.*?)</w:pPr>', x, re.S)
            if m:
                keep = []
                for tag, cx in children(m.group(1)):
                    ok = tag in ALLOWED_PPR or tag in ALLOWED_PPR_BY_STYLE.get(st, set())
                    if tag == 'spacing' and st == 'Heading1' and 'pageBreakBefore' not in m.group(1): ok = False
                    if tag == 'rPr': cx = '<w:rPr>' + ''.join(c for t2, c in children(re.search(r'<w:rPr>(.*?)</w:rPr>', cx, re.S).group(1) or '') if t2 in ('vanish',)) + '</w:rPr>' if re.search(r'<w:rPr>(.+?)</w:rPr>', cx, re.S) else ''
                    if ok: keep.append(cx)
                x = x.replace(m.group(0), '<w:pPr>' + ''.join(keep) + '</w:pPr>', 1)
            def fixrun(rm):
                r = rm.group(0); rp = re.search(r'<w:rPr>(.*?)</w:rPr>', r, re.S)
                if not rp: return r
                kept = []
                for tag, cx in children(rp.group(1)):
                    if tag in ALLOWED_RPR:
                        if tag in ('i', 'iCs') and 'FootnoteReference' in rp.group(1): continue
                        kept.append(cx)
                    elif tag == 'color' and st == 'TableData': kept.append(cx)
                return r.replace(rp.group(0), '<w:rPr>' + ''.join(kept) + '</w:rPr>' if kept else '', 1)
            x = re.sub(r'<w:r\b[^>]*>.*?</w:r>', fixrun, x, flags=re.S)
            if not preserve:   # these change the content stream (tab tokens / nbsp text)
                x = re.sub(r'(</w:pPr>)(?:<w:r>(?:<w:rPr>.*?</w:rPr>)?<w:tab/></w:r>)+', r'\1', x, flags=re.S)
                x = x.replace('\u00a0', ' ')
            self.set(i, x); i += 1

    def fix_tables(self):
        for i in range(self.n()):
            x = self.item(i)
            if not x.startswith('<w:tbl'): continue
            x = re.sub(r'<w:tblBorders>.*?</w:tblBorders>|<w:shd [^>]*/>', '', x, flags=re.S)
            if '<w:tblStyle' not in x: x = x.replace('<w:tblPr>', '<w:tblPr><w:tblStyle w:val="LITable"/>', 1)
            else: x = re.sub(r'<w:tblStyle w:val="[^"]+"/>', '<w:tblStyle w:val="LITable"/>', x)
            x = re.sub(r'<w:tblLook [^>]*/>', '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>', x)
            # drop empty columns
            rows = re.findall(r'<w:tr\b.*?</w:tr>', x, re.S)
            cells = [re.findall(r'<w:tc>.*?</w:tc>', r, re.S) for r in rows]
            ncol = max(len(c) for c in cells)
            empty = [k for k in range(ncol) if all(len(c) > k and not text_of(c[k]).strip() for c in cells)]
            if empty:
                for r, cs in zip(rows, cells):
                    nr = r
                    for k in sorted(empty, reverse=True):
                        if len(cs) > k: nr = nr.replace(cs[k], '', 1)
                    x = x.replace(r, nr, 1)
                grid = re.findall(r'<w:gridCol w:w="\d+"/>', x)
                for k in sorted(empty, reverse=True):
                    if len(grid) > k: x = x.replace(grid[k], '', 1)
                self.say('M', i, f'removed {len(empty)} empty column(s)')
            width = sum(int(w) for w in re.findall(r'<w:gridCol w:w="(\d+)"/>', x))
            x = re.sub(r'<w:tblW [^>]*/>', f'<w:tblW w:w="{width}" w:type="dxa"/>', x)
            x = re.sub(r'<w:tblInd [^>]*/>', '', x)
            if width <= 8640: x = x.replace('<w:tblW', '<w:tblInd w:w="720" w:type="dxa"/><w:tblW', 1)
            # cell paragraphs -> Table Data, keep alignment
            def fixcell(m):
                c = m.group(0)
                c = re.sub(r'<w:p\b[^>]*>(<w:pPr>(.*?)</w:pPr>)?', lambda pm: '<w:p><w:pPr><w:pStyle w:val="TableData"/>' + ''.join(cx for t2, cx in children(pm.group(2) or '') if t2 == 'jc') + '</w:pPr>', c)
                return c
            x = re.sub(r'<w:tc>.*?</w:tc>', fixcell, x, flags=re.S)
            x = re.sub(r'<w:rPr>(.*?)</w:rPr>', lambda r: ('<w:rPr>' + ''.join(cx for t2, cx in children(r.group(1)) if t2 in ('rStyle','b','bCs','i','iCs','color')) + '</w:rPr>') if r.group(1) else '', x, flags=re.S)
            first_row = re.search(r'<w:tr\b.*?</w:tr>', x, re.S).group(0)
            if '<w:tblHeader/>' not in first_row:
                nfr = first_row.replace('<w:tr>', '<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>', 1) if '<w:trPr>' not in first_row else first_row.replace('<w:trPr>', '<w:trPr><w:tblHeader/>', 1)
                x = x.replace(first_row, nfr, 1)
            self.set(i, x)
        # header-row run colour is provided by the table style; ensure explicit white bold header runs are allowed (kept by strip_direct for TableData)

    @staticmethod
    def _anchor_to_inline(xml):
        xml = re.sub(r'<wp:anchor[^>]*>', '<wp:inline distT="0" distB="0" distL="0" distR="0">', xml)
        xml = xml.replace('</wp:anchor>', '</wp:inline>')
        xml = re.sub(r'<wp:simplePos[^/]*/>', '', xml)
        xml = re.sub(r'<wp:positionH\b.*?</wp:positionH>', '', xml, flags=re.S)
        xml = re.sub(r'<wp:positionV\b.*?</wp:positionV>', '', xml, flags=re.S)
        xml = re.sub(r'<wp:wrap\w+[^/]*/>', '', xml)
        xml = re.sub(r'<wp14:sizeRel\w+\b.*?</wp14:sizeRel\w+>', '', xml, flags=re.S)
        return xml

    @staticmethod
    def _run_bounds(xml, start, end):
        """Return (open, close) offsets of the <w:r>...</w:r> directly enclosing xml[start:end],
        or None if start/end are not cleanly inside a single run."""
        ro = max(xml.rfind('<w:r>', 0, start), xml.rfind('<w:r ', 0, start))
        if ro < 0 or '</w:r>' in xml[ro:start]:
            return None
        rc = xml.find('</w:r>', end)
        if rc < 0 or re.search(r'<w:r\b', xml[end:rc]):
            return None
        return ro, rc + len('</w:r>')

    @staticmethod
    def _textbox_caption_runs(xml):
        """If xml holds a floating text box, return the inline caption content (runs, fields,
        bookmarks) from its first txbxContent paragraph(s), lifted out of the box. Else None."""
        m = re.search(r'<w:txbxContent>(.*?)</w:txbxContent>', xml, re.S)
        if not m:
            return None
        parts = [pm.group(1) for pm in re.finditer(
            r'<w:p\b[^>]*>(?:<w:pPr>.*?</w:pPr>)?(.*?)</w:p>', m.group(1), re.S)]
        return ''.join(parts)

    def fix_figures(self):
        i = 0
        while i < self.n():
            x = self.item(i)
            if '<wp:anchor' not in x:
                i += 1; continue
            has_text = bool(text_of(x).strip())
            if not has_text:
                x = self._anchor_to_inline(x)
                self.set(i, x); self.say('M', i, 'floating picture converted to inline')
            else:
                drawings = list(re.finditer(r'<w:drawing><wp:anchor[^>]*>.*?</wp:anchor></w:drawing>', x, flags=re.S))
                pic_drawings = [dm for dm in drawings if '<a:blip' in dm.group(0)]
                if pic_drawings:
                    extracted = []
                    clean = x
                    first_bounds = self._run_bounds(x, pic_drawings[0].start(), pic_drawings[0].end())
                    split_pos = first_bounds[0] if first_bounds else pic_drawings[0].start()
                    for dm in reversed(pic_drawings):
                        inline_xml = self._anchor_to_inline(dm.group(0))
                        new_p = f'<w:p><w:pPr><w:pStyle w:val="SpacebehindafteraGraphic"/><w:keepNext/></w:pPr><w:r>{inline_xml}</w:r></w:p>'
                        extracted.insert(0, new_p)
                        bounds = self._run_bounds(clean, dm.start(), dm.end())
                        if bounds:
                            clean = clean[:bounds[0]] + clean[bounds[1]:]
                        else:
                            clean = clean[:dm.start()] + clean[dm.end():]
                    before = clean[:split_pos]
                    after = clean[split_pos:]
                    before_txt = text_of(before).strip()
                    after_txt = text_of(after).strip()
                    if before_txt and after_txt and re.match(r'Figure \d', before_txt):
                        ppr_m = re.match(r'(<w:p\b[^>]*>(?:<w:pPr>.*?</w:pPr>)?)', clean, re.S)
                        orig_ppr = ppr_m.group(1) if ppr_m else '<w:p>'
                        cap_runs = before[ppr_m.end():]
                        tb_runs = self._textbox_caption_runs(cap_runs)
                        if tb_runs is not None:
                            cap_runs = tb_runs
                        else:
                            cap_runs = re.sub(r'<w:r\b[^>]*><w:drawing>.*?</w:drawing></w:r>', '', cap_runs, flags=re.S)
                            cap_runs = re.sub(r'<w:r\b[^>]*>\s*</w:r>', '', cap_runs)
                        caption_p = f'<w:p><w:pPr><w:pStyle w:val="Caption"/><w:jc w:val="center"/></w:pPr>{cap_runs.strip()}</w:p>'
                        body_runs = re.sub(r'<w:r\b[^>]*>\s*</w:r>', '', after).strip()
                        if body_runs.endswith('</w:p>'):
                            body_runs = body_runs[:-6].strip()
                        body_p = f'{orig_ppr}{body_runs}</w:p>'
                        self.set(i, body_p)
                        self.items.insert(self.b0 + i, caption_p)
                        for ep in reversed(extracted):
                            self.items.insert(self.b0 + i, ep)
                        self.say('M', i + len(extracted) + 1, f'split caption + body text and extracted {len(pic_drawings)} floating picture(s)')
                    else:
                        self.set(i, clean)
                        for ep in reversed(extracted):
                            self.items.insert(self.b0 + i, ep)
                        self.say('M', i + len(extracted), f'extracted {len(pic_drawings)} floating picture(s) from text paragraph into dedicated paragraphs')
            i += 1
        self._normalize_figure_image_style()
        self._keep_figures_with_captions()
        self._space_after_figure_captions()

    def _normalize_figure_image_style(self):
        """Standard figure style: every picture-only paragraph uses 'Space behind/after a
        Graphic' (centered), so all figure blocks look identical regardless of the source style."""
        for i in range(self.n()):
            x = self.item(i)
            if not self.is_par(i) or '<a:blip' not in x or self.text(i).strip():
                continue
            if self.style(i) != 'SpacebehindafteraGraphic':
                self.set_style(i, 'SpacebehindafteraGraphic')
                self.say('M', i, 'figure image paragraph -> SpacebehindafteraGraphic (standard figure style)')

    def _space_after_figure_captions(self):
        """Template clear-space rule: a figure block (image followed by its caption) is
        separated from the next figure or block of text by one empty 'Space behind/after a
        Graphic' paragraph. Insert it where the source lacked it."""
        SPACER = ('<w:p><w:pPr><w:pStyle w:val="SpacebehindafteraGraphic"/></w:pPr>'
                  '<w:r><w:t xml:space="preserve"></w:t></w:r></w:p>')
        i = 0
        while i < self.n():
            if (self.is_par(i) and self.style(i) == 'Caption' and '<w:drawing>' not in self.item(i)
                    and i > 0 and '<w:drawing>' in self.item(i - 1)):
                nxt = i + 1
                if nxt < self.n():
                    nst = self.style(nxt)
                    nempty = not self.text(nxt).strip() and '<w:drawing>' not in self.item(nxt)
                    if not (nst == 'SpacebehindafteraGraphic' and nempty):
                        self.items.insert(self.b0 + nxt, SPACER)
                        i = nxt + 1
                        continue
            i += 1

    def _keep_figures_with_captions(self):
        for i in range(self.n() - 1):
            x = self.item(i)
            if '<w:drawing>' not in x or '<w:keepNext/>' in x:
                continue
            st = self.style(i)
            if st not in ('SpacebehindafteraGraphic', 'Caption'):
                continue
            for j in range(i + 1, min(i + 3, self.n())):
                nst = self.style(j)
                if nst == 'Caption':
                    ppr = re.search(r'<w:pPr>(.*?)</w:pPr>', x, re.S)
                    if ppr:
                        x = x.replace(ppr.group(0), ppr.group(0).replace('</w:pPr>', '<w:keepNext/></w:pPr>'), 1)
                    self.set(i, x)
                    break
                ntxt = text_of(self.item(j)).strip()
                if ntxt:
                    break

    def fix_footnotes(self):
        if self._skip('footnotes'):
            return
        preserve = self.disposition == 'preserve'
        def fix(m):
            f = m.group(0)
            # Skip footnotes carrying tracked changes in preserve mode: normalising their rPr/pPr
            # would drop a revision marker or snapshot (and the children() rebuild crashes on them).
            if preserve and (self._REV_CONTENT_RE.search(f) or self._CHANGE_RE.search(f)):
                return f
            f = re.sub(r'<w:p\b[^>]*>(<w:pPr>.*?</w:pPr>)?', '<w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>', f, count=1, flags=re.S)
            if not preserve:
                # Inserting / substituting a run-level <w:tab/> after the footnote number is a
                # CONTENT change (a new tab token). In preserve mode we keep the footnote's original
                # number->text separator and conform only its style + direct run formatting, so the
                # content-stream gate stays green and footnote FORMATTING still gets fixed.
                f = re.sub(r'(<w:footnoteRef/></w:r>)<w:r>(?:<w:rPr>.*?</w:rPr>)?<w:t xml:space="preserve"> +</w:t></w:r>', r'\1<w:r><w:tab/></w:r>', f, flags=re.S)
                if '<w:footnoteRef/></w:r><w:r><w:tab/>' not in f: f = f.replace('<w:footnoteRef/></w:r>', '<w:footnoteRef/></w:r><w:r><w:tab/></w:r>', 1)
            f = re.sub(r'<w:rPr>(.*?)</w:rPr>', lambda r: '<w:rPr>' + ''.join(cx for t2, cx in children(r.group(1)) if t2 in ('rStyle', 'i', 'b')) + '</w:rPr>', f, flags=re.S)
            return f
        self.fn = re.sub(r'<w:footnote w:id="[1-9]\d*".*?</w:footnote>', fix, self.fn, flags=re.S)
        self.say('M', -1, 'footnotes normalised (Footnote Text, tab after number, direct formatting removed)',
                 'footnotes')

    def rebuild_fields(self):
        bm_id = [900]
        def bm(name, inner): bm_id[0] += 1; return f'<w:bookmarkStart w:id="{bm_id[0]}" w:name="{name}"/>{inner}<w:bookmarkEnd w:id="{bm_id[0]}"/>'
        def fld(instr, result, rstyle=None):
            rp = f'<w:rPr><w:rStyle w:val="{rstyle}"/></w:rPr>' if rstyle else ''
            return (f'<w:r>{rp}<w:fldChar w:fldCharType="begin"/></w:r><w:r>{rp}<w:instrText xml:space="preserve"> {instr} </w:instrText></w:r><w:r>{rp}<w:fldChar w:fldCharType="separate"/></w:r><w:r>{rp}<w:t xml:space="preserve">{esc(result)}</w:t></w:r><w:r>{rp}<w:fldChar w:fldCharType="end"/></w:r>')
        caps = {}   # 'Table 3-1' -> bookmark name
        # captions
        for i in range(self.n()):
            if self.style(i) != 'Caption': continue
            x = self.item(i); t = self.text(i)
            m = re.match(r'(Table|Figure) (\d+)[-\u2011\u2010](\d+): (.*)', t.strip())
            if not m: continue
            label, a, b, title = m.groups(); name = f'_Ref_{label[0]}{a}{b}'
            if 'SEQ' not in x:
                inner = f'<w:r><w:t xml:space="preserve">{label} </w:t></w:r>' + fld('STYLEREF 1 \\s', a) + '<w:r><w:noBreakHyphen/></w:r>' + fld(f'SEQ {label} \\* ARABIC \\s 1', b) + f'<w:r><w:t xml:space="preserve">: {esc(title)}</w:t></w:r>'
                self.set(i, '<w:p><w:pPr><w:pStyle w:val="Caption"/><w:jc w:val="center"/></w:pPr>' + bm(name, inner) + '</w:p>'); self.say('M', i, 'caption rebuilt as STYLEREF/SEQ fields with bookmark')
            elif '<w:bookmarkStart' not in x:
                x = re.sub(r'(</w:pPr>)(.*)(</w:p>)', lambda mm: mm.group(1) + bm(name, mm.group(2)) + mm.group(3), x, flags=re.S); self.set(i, x); self.say('M', i, 'missing caption bookmark restored')
            existing = re.search(r'<w:bookmarkStart w:id="\d+" w:name="([^"]+)"', self.item(i))
            caps[f'{label} {a}-{b}'] = existing.group(1) if existing else name
        # headings
        heads = {}; hnum = 0
        for i in range(self.n()):
            if self.style(i) == 'Heading1':
                hnum += 1; x = self.item(i); existing = re.search(r'<w:bookmarkStart w:id="\d+" w:name="([^"]+)"', x)
                heads[str(hnum)] = existing.group(1) if existing else ('LAZY', i)
        # numbered paragraph ordinals
        nps = {}; k = 0
        for i in range(self.n()):
            if self.style(i) == 'NumberedParagraph': k += 1; nps[str(k)] = i
        # literal references -> REF fields
        for i in range(self.n()):
            if not self.is_par(i) or self.style(i) in ('Caption',) or self.style(i) in HEADINGS: continue
            x = self.item(i)
            if 'REF ' in x and 'instrText' in x: pass
            def sub_runs(x):
                def repl_text(m):
                    t = m.group(2); out = ''; pos = 0
                    for mm in re.finditer(r'(Table|Figure) (\d+-\d+)|Sections? (\d+)(?!\.\d)(?: and (\d+)(?!\.\d))?|, (\d+) below', t):
                        pre = t[pos:mm.start()]; out += f'<w:r><w:t xml:space="preserve">{esc(pre)}</w:t></w:r>' if pre else ''
                        if mm.group(1):
                            key = f'{mm.group(1)} {mm.group(2)}'
                            if key in caps: out += fld(f'REF {caps[key]} \\h', key, 'CrossReference')
                            else: out += f'<w:r><w:t xml:space="preserve">{esc(mm.group(0))}</w:t></w:r>'
                        elif mm.group(3):
                            word = 'Sections' if mm.group(0).startswith('Sections') else 'Section'
                            for g in (mm.group(3), mm.group(4)):
                                if g in heads and isinstance(heads[g], tuple):
                                    hi = heads[g][1]; nm = f'_Ref_S{g}'
                                    self.set(hi, re.sub(r'(</w:pPr>)(.*)(</w:p>)', lambda q: q.group(1) + bm(nm, q.group(2)) + q.group(3), self.item(hi), flags=re.S)); heads[g] = nm
                            out += f'<w:r><w:t xml:space="preserve">{word} </w:t></w:r>' + (fld(f'REF {heads[mm.group(3)]} \\r \\h', mm.group(3), 'CrossReference') if mm.group(3) in heads else f'<w:r><w:t>{mm.group(3)}</w:t></w:r>')
                            if mm.group(4): out += '<w:r><w:t xml:space="preserve"> and </w:t></w:r>' + (fld(f'REF {heads[mm.group(4)]} \\r \\h', mm.group(4), 'CrossReference') if mm.group(4) in heads else f'<w:r><w:t>{mm.group(4)}</w:t></w:r>')
                        elif mm.group(5):
                            n_ = mm.group(5)
                            if n_ in nps:
                                j = nps[n_]; y = self.item(j)
                                if '<w:bookmarkStart' not in y:
                                    nm = f'_Ref_NP{n_}'; y = re.sub(r'(</w:pPr>)(.*)(</w:p>)', lambda q: q.group(1) + bm(nm, q.group(2)) + q.group(3), y, flags=re.S); self.set(j, y)
                                nm = re.search(r'<w:bookmarkStart w:id="\d+" w:name="([^"]+)"', self.item(j)).group(1)
                                out += '<w:r><w:t xml:space="preserve">, </w:t></w:r>' + fld(f'REF {nm} \\r \\h', n_, 'CrossReference') + '<w:r><w:t xml:space="preserve"> below</w:t></w:r>'
                            else: out += f'<w:r><w:t xml:space="preserve">{esc(mm.group(0))}</w:t></w:r>'
                        pos = mm.end()
                    if pos == 0: return m.group(0)
                    rest = t[pos:]; out += f'<w:r><w:t xml:space="preserve">{esc(rest)}</w:t></w:r>' if rest else ''
                    return out
                # only plain runs (no rPr with rStyle CrossReference, not inside fields)
                return re.sub(r'<w:r>(<w:rPr>(?:(?!CrossReference)(?!</w:rPr>).)*</w:rPr>)?<w:t xml:space="preserve">([^<]*)</w:t></w:r>', lambda m: repl_text(m) if not m.group(1) else m.group(0), x)
            x = re.sub(r'</w:t></w:r><w:r><w:t xml:space="preserve">', '', x)
            nx = sub_runs(x)
            if nx != x: self.set(i, nx); self.say('M', i, 'literal cross-reference(s) rebuilt as REF fields')
        # REF fields whose bookmark is missing -> restore bookmark on the caption with matching cached result
        names = set(re.findall(r'<w:bookmarkStart w:id="\d+" w:name="([^"]+)"', ''.join(self.items)))
        for i in range(self.n()):
            for name, result in re.findall(r'REF (_\w+) \\h </w:instrText></w:r><w:r>(?:<w:rPr>.*?</w:rPr>)?<w:fldChar w:fldCharType="separate"/></w:r><w:r>(?:<w:rPr>.*?</w:rPr>)?<w:t xml:space="preserve">([^<]*)</w:t>', self.item(i)):
                if name in names: continue
                for j in range(self.n()):
                    if self.style(j) == 'Caption' and re.sub(r'[-\u2011\u2010]', '', self.text(j).strip()).startswith(re.sub(r'[-\u2011\u2010]', '', result)):
                        y = self.item(j)
                        if '<w:bookmarkStart' in y: y = re.sub(r'<w:bookmarkStart w:id="\d+" w:name="[^"]+"/>', lambda q: q.group(0).replace(q.group(0), f'<w:bookmarkStart w:id="{bm_id[0]+1}" w:name="{name}"/>'), y, count=1)
                        else: y = re.sub(r'(</w:pPr>)(.*)(</w:p>)', lambda q: q.group(1) + bm(name, q.group(2)) + q.group(3), y, flags=re.S)
                        self.set(j, y); names.add(name); self.say('M', j, f'restored missing bookmark {name}'); break

    def typography(self):
        for i in range(self.n()):
            if not self.is_par(i): continue
            x = self.item(i)
            def fix(m):
                return m.group(1) + typo_text(m.group(2)) + m.group(3)
            # In preserve mode, mask revision content so typography never rewrites the characters of
            # an inserted/deleted payload (which must stay byte-exact); it still fixes settled text.
            masked, masks = self._mask_revisions(x) if self.disposition == 'preserve' else (x, {})
            nx = re.sub(r'(<w:t(?: xml:space="preserve")?>)([^<]*)(</w:t>)', fix, masked)
            nx = self._unmask(nx, masks)
            if nx != x: self._apply_text_edit('typo', 'Typography', i, x, nx)
        self.say('M', -1, 'typography normalised (smart quotes, en dashes, sentence spacing, dates, ligatures)')

    _HOUSE_SKIP_STYLES = {'ExcerptorQuote', 'Caption', 'TableofFigures', 'Title', 'TitleofProject',
                          'PRIVCONFSTATEMENT', 'TOCListTitle'}

    @staticmethod
    def _house_edit(t):
        """Apply the deterministic LI house-style edits to one run's visible text (see house_norm):
        lowercase a generic term when it follows a determiner (CAP-1/2); capitalize the Report /
        Project (CAP-5); British->American spelling + programme->schedule (TERM); acronym plural;
        e.g./i.e. Text inside a double-quote span is left untouched (HC-1)."""
        out = []
        for seg in re.split(r'("[^"]*"|“[^”]*”)', t):
            if seg[:1] in ('"', '“'):
                out.append(seg); continue          # a quotation span — never edited
            seg = _HOUSE_LOWER_RE.sub(lambda m: m.group(1) + m.group(2) + m.group(3).lower(), seg)
            seg = _HOUSE_CAP_RE.sub(lambda m: m.group(1) + m.group(2) + m.group(3).capitalize(), seg)
            seg = _BRIT_RE.sub(_brit_case, seg)
            seg = _USA_RE.sub('U.S.', seg)
            seg = _ACR_PLURAL_RE.sub(lambda m: m.group(1) + 's', seg)
            seg = _EG_RE.sub(lambda m: m.group(1) + ',', seg)
            out.append(seg)
        return ''.join(out)

    def house_style(self):
        """LI house style (deterministic subset of docs/LI_STYLE_GUIDE.md): capitalization,
        terminology, and American spelling on LI prose. Skips block quotes, captions, headings, and
        title/front-matter styles; in preserve mode revision content is masked and the change is
        authorized by the content-stream gate via house_ok (only house-style variation permitted)."""
        n = 0
        for i in range(self.n()):
            if not self.is_par(i):
                continue
            st = self.style(i)
            if st in self._HOUSE_SKIP_STYLES or st in HEADINGS:
                continue
            x = self.item(i)
            masked, masks = self._mask_revisions(x) if self.disposition == 'preserve' else (x, {})
            nx = re.sub(r'(<w:t(?: xml:space="preserve")?>)([^<]*)(</w:t>)',
                        lambda m: m.group(1) + self._house_edit(m.group(2)) + m.group(3), masked)
            nx = self._unmask(nx, masks)
            if nx != x and self._apply_text_edit('house', 'House style', i, x, nx):
                n += 1
        if n:
            self.say('M', -1, f'LI house style applied to {n} paragraphs (capitalization, '
                              f'terminology, American spelling)')

    def fix_sections(self):
        final = self.items[-1]
        if 'orient="landscape"' not in final: return
        # find the paragraph that ends the portrait section before the landscape block
        marks = [i for i in range(self.n()) if self.is_par(i) and '<w:sectPr' in self.item(i)]
        start = marks[-1] if marks else 0
        # landscape content runs until the next Heading1; attach a landscape sectPr to the paragraph before it
        j = start + 1
        while j < self.n() and self.style(j) != 'Heading1': j += 1
        k = j - 1
        while k > start and not self.is_par(k): k -= 1
        land = re.sub(r'<w:sectPr\b[^>]*>', '<w:sectPr>', re.search(r'<w:sectPr\b.*?</w:sectPr>', final, re.S).group(0), 1)
        x = self.item(k); x = x.replace('</w:pPr>', land + '</w:pPr>', 1) if '<w:pPr>' in x else x.replace('<w:p>', '<w:p><w:pPr>' + land + '</w:pPr>', 1)
        self.set(k, x)
        portrait = re.sub(r'<w:pgSz [^>]*/>', '<w:pgSz w:w="12240" w:h="15840" w:code="9"/>', final)
        portrait = re.sub(r'<w:pgMar [^>]*/>', '<w:pgMar w:top="2160" w:right="1440" w:bottom="1440" w:left="1440" w:header="1872" w:footer="720" w:gutter="0"/>', portrait)
        self.items[-1] = portrait; self.say('M', k, 'restored the section break ending the landscape block; final section back to portrait')

    def replace_parts(self):
        self.styles = self.t_styles; self.num = self.t_num
        self.say('M', -1, 'styles and numbering parts replaced from the template (foreign styles and extra list instances removed)')

    def force_field_update(self):
        """Arm Word's on-open field refresh ONLY when the figure audit found numbering/TOC drift.
        A clean report opens with no prompt (nothing needs updating); a drifted one prompts the user
        to update so the numbering and Table of Figures self-correct. Runs after audit_figures()."""
        if not self.audit:
            return
        if '<w:updateFields' in self.settings:
            self.settings = re.sub(r'<w:updateFields[^>]*/>', '<w:updateFields w:val="true"/>', self.settings, count=1)
        else:
            self.settings = re.sub(r'(<w:settings\b[^>]*>)', r'\1<w:updateFields w:val="true"/>', self.settings, count=1)
        self.say('M', -1, f'updateFields=true (audit found {len(self.audit)} issue(s)): Word will refresh numbering and the Table of Figures on open')

    # ---------------------------------------------------------------- figure integrity audit
    @staticmethod
    def _field_results(x):
        """Cached results of each field in x, in order (STYLEREF then SEQ for a caption)."""
        out = []
        for m in re.finditer(r'<w:fldChar w:fldCharType="separate"/>(.*?)<w:fldChar w:fldCharType="end"/>', x, re.S):
            out.append(''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', m.group(1))).strip())
        return out

    @staticmethod
    def _fig_title(text):
        m = re.match(r'(?:Figure|Table)\b.*?:\s*(.*)', text.strip(), re.S)
        return re.sub(r'\s+', ' ', (m.group(1) if m else text)).strip()

    def _toc_figure_entries(self):
        """Table-of-Figures entries keyed by bookmark anchor -> displayed title (page ref stripped).
        Scans ALL items because the Table of Figures lives in the front matter, before b0."""
        entries = {}
        for it in self.items:
            if not it.startswith('<w:p') or '<w:pStyle w:val="TableofFigures"' not in it:
                continue
            for hm in re.finditer(r'<w:hyperlink w:anchor="([^"]+)"[^>]*>(.*?)</w:hyperlink>', it, re.S):
                before_tab = re.split(r'<w:tab/>', hm.group(2))[0]
                txt = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', before_tab)).strip()
                if txt.startswith('Figure'):
                    entries[hm.group(1)] = self._fig_title(txt)
        return entries

    def audit_figures(self):
        """Verify figure numbering is sequential + section-matched and that body captions match the
        Table of Figures. Findings are advisory (do not alter output); stored on self.audit."""
        findings = []
        sec = 0; seqmap = {}; caps = []
        for i in range(self.n()):
            if not self.is_par(i):
                continue
            st = self.style(i); x = self.item(i)
            if st == 'Heading1':
                sec += 1
            if st != 'Caption':
                continue
            t = self.text(i).strip()
            if not re.match(r'Figure\b', t):
                continue
            if 'SEQ Figure' not in x:
                findings.append(('not-fielded', f'Figure caption is not an auto-number field (will not renumber): {t[:45]!r}'))
                continue
            seqmap[sec] = seqmap.get(sec, 0) + 1
            res = self._field_results(x)
            caps.append({'sec': sec, 'seq': seqmap[sec],
                         'csec': res[0] if len(res) > 0 else '', 'cseq': res[1] if len(res) > 1 else '',
                         'bms': re.findall(r'<w:bookmarkStart w:id="\d+" w:name="([^"]+)"', x),
                         'title': self._fig_title(t)})
        for c in caps:
            want = f"{c['sec']}-{c['seq']}"
            if c['csec'] and f"{c['csec']}-{c['cseq']}" != want:
                findings.append(('numbering', f"caption reads {c['csec']}-{c['cseq']} but is figure #{c['seq']} of section {c['sec']} (should be {want}): {c['title'][:35]!r}"))
        toc = self._toc_figure_entries()
        if toc:
            body_anchors = {b for c in caps for b in c['bms']}
            for c in caps:
                match = next((b for b in c['bms'] if b in toc), None)
                if not c['bms'] or match is None:
                    findings.append(('toc-missing', f"Figure {c['sec']}-{c['seq']} has no Table-of-Figures entry: {c['title'][:35]!r}"))
                elif re.sub(r'\s+', ' ', toc[match]).strip().lower() != c['title'].lower():
                    findings.append(('toc-title', f"Figure {c['sec']}-{c['seq']} caption {c['title'][:28]!r} != Table of Figures {toc[match][:28]!r}"))
            for anchor, title in toc.items():
                if anchor not in body_anchors:
                    findings.append(('toc-orphan', f'Table of Figures lists {title[:35]!r} but no matching caption is in the body'))
        self.audit = findings
        if findings:
            for lvl, msg in findings:
                self.say('J', -1, f'FIGURE AUDIT [{lvl}]: {msg}')
        else:
            tof = 'captions match the Table of Figures' if toc else 'no Table of Figures present'
            self.say('M', -1, f'figure audit OK: {len(caps)} figures numbered sequentially per section; {tof}')
        return findings

    def save(self, path):
        parts = self._output_parts()
        if os.path.exists(path): os.remove(path)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            for n_, b in parts.items(): z.writestr(n_, b)

    # Ordered progress phases the UI can render. The engine emits these keys as it works; the '__mode__'
    # event fires first so the UI knows whether to show the preserve (8-step + shield) or clean checklist.
    PROGRESS_PHASES_PRESERVE = ['read', 'track', 'styles', 'tables', 'structure', 'type', 'refs', 'save']
    PROGRESS_PHASES_CLEAN = ['read', 'structure', 'type', 'save']

    def _emit(self, phase, detail=''):
        """Report progress to an optional UI callback (fn(phase_key, detail)). Never lets a UI error
        break conforming."""
        cb = getattr(self, 'progress', None)
        if cb:
            try:
                cb(phase, detail)
            except Exception:
                pass

    def _run_passes(self):
        if self.revision_ledger.has_content_revisions() and self.disposition in (None, 'preserve'):
            self.disposition = 'preserve'
            s = self.revision_ledger.summary()
            self._emit('__mode__', 'preserve')
            self._emit('read')
            self._emit('track', f"{s['total']:,} tracked changes · {s['comments']} comments "
                                f"· {len(s['authors'])} authors")
            self._run_passes_preserving()
            self._emit('save')
        else:
            self._emit('__mode__', 'clean')
            self._emit('read')
            self._run_passes_clean()
            self._emit('save')

    def _run_passes_clean(self):
        self.revert_tracked_formatting(); self.unwrap_and_prune()
        self._emit('structure')
        self.classify(); self.merge_pdf_lines()
        self.fix_headings(); self.fix_levels(); self.strip_direct(); self.fix_tables(); self.fix_figures()
        self.fix_footnotes(); self.rebuild_fields()
        self._emit('type')
        self.typography(); self.house_style(); self.fix_sections(); self.replace_parts()
        self.audit_figures(); self.force_field_update()

    # ---------------------------------------------------------------- review-preserving pipeline
    def _snapshot(self):
        return (list(self.items), self.styles, self.num, self.fn, self.settings,
                self.head, self.tail, self.b0)

    def _restore(self, s):
        self.items, self.styles, self.num, self.fn, self.settings, self.head, self.tail, self.b0 = \
            list(s[0]), s[1], s[2], s[3], s[4], s[5], s[6], s[7]

    @staticmethod
    def _summarize_disc(d):
        bits = []
        for k in ('lost', 'payload_altered', 'placement_altered', 'metadata_altered',
                  'lost_comments', 'comment_body_altered', 'comment_anchor_altered',
                  'binary_altered', 'relationship_altered', 'introduced'):
            n = len(d.get(k, []))
            if n: bits.append(f'{k}={n}')
        return 'would disturb ' + ', '.join(bits) if bits else 'unknown discrepancy'

    def _run_passes_preserving(self):
        """Each pass runs in a transaction: snapshot the package, apply, verify preservation, and
        roll the WHOLE pass back if it would disturb any tracked change / comment / dependency
        (GPT-6: whole-pass rollback, not per-paragraph). Conservative style/level changes skip
        revised paragraphs and survive; conflicting passes that touch a revision are rolled back
        and recorded as exceptions. Correctness is guaranteed by the gate, not by pass ordering."""
        self.exceptions = []
        from conformer import revisions as _rev
        typo_ok = lambda old, new: typo_text(old) == new
        # (pass, gate): 'stream' = strict content stream (formatting only); 'text' = typography's
        # authorized text edit; 'struct' = AUTO structural change (paragraph structure may change,
        # every text token / object / revision-comment-bookmark boundary must still line up); 'prune' =
        # like 'struct' but ALSO tolerates the loss of an eligible manual page-break token ('BR','page')
        # — the prune pass (#4) removes page-break-ONLY paragraphs, which are layout, not reading
        # content (CAP-1). Column breaks, line breaks, and every other token stay protected.
        ordered = [
            (self._repair_styles, 'stream', 'styles'), (self._conform_tables_preserving, 'stream', 'tables'),
            (self.classify, 'stream', 'structure'), (self.fix_levels, 'stream', 'structure'),
            (self._caps_headings_preserving, 'stream', 'structure'), (self.strip_direct, 'stream', 'structure'),
            (self.fix_footnotes, 'stream', 'structure'), (self.fix_sections, 'stream', 'structure'),
            (self.typography, 'text', 'type'), (self.house_style, 'house', 'type'),
            (self._prune_preserving, 'prune', 'type'),
        ]
        # #3 unwrap wrapper tables runs FIRST (before formatting): the extracted paragraphs then
        # flow through classify/strip_direct and get properly conformed, instead of keeping the
        # TableData styling a later table pass would wrongly stamp on a layout wrapper.
        self._unwrap_tables_preserving()    # #3
        prev_stream = _rev.content_stream(self._output_parts(), cache=self._verify_cache)
        _phase = None
        for fn, gate, phase in ordered:
            if phase != _phase:
                self._emit(phase); _phase = phase
            snap = self._snapshot()
            try:
                fn()
            except Exception as e:
                self._restore(snap)
                self.exceptions.append((fn.__name__, f'pass error: {str(e)[:100]}'))
                continue
            clean, disc = self.verify_preservation()
            after_stream = _rev.content_stream(self._output_parts(), cache=self._verify_cache)
            sviol = _rev.stream_violations(prev_stream, after_stream,
                                           text_ok=(typo_ok if gate == 'text'
                                                    else house_ok if gate == 'house' else None),
                                           ignore_structure=(gate in ('struct', 'prune')),
                                           ignore_page_breaks=(gate == 'prune'))
            if not clean or sviol:
                self._restore(snap)
                reason = self._summarize_disc(disc) if not clean else f'unauthorized content change ({len(sviol)})'
                self.exceptions.append((fn.__name__, reason))
                continue
            prev_stream = after_stream
        self._merge_pdf_lines_preserving()   # #1 AUTO authorized text edit (clean excerpts only)
        # Interactive ASK structural changes (display-preserving, per-instance JudgmentCalls).
        # #8 first (Claire's explicit need): caption fielding then cross-reference rebuild.
        self._emit('refs')
        self._caption_fields_preserving()   # #8a
        self._xrefs_preserving()            # #8b
        self._split_headings_preserving()   # #6
        self._extract_images_preserving()   # #5
        self._drop_empty_columns_preserving()  # #7
        self.audit_figures()
        self._label_review_copy()           # GPT-6 2a: stamp as a normalized-formatting review copy

    def _prune_preserving(self):
        """AUTO structural: remove eligible manual PAGE-break paragraphs (#4) and TRULY-empty
        numbered/Normal paragraphs (#2). Skips any paragraph carrying a tracked change so review
        content is untouched. The empty-paragraph branch requires no text AND no drawing AND no break
        AND no field, so a paragraph whose only content is a COLUMN or LINE break (or a field) is left
        alone — only the page-break branch removes a break, and only a page break (CAP-1)."""
        drop_breaks = not self._skip('page-breaks')
        drop_empty = not self._skip('empty-paras')
        i = 0
        while i < self.n():
            x = self.item(i)
            if self.is_par(i) and not self._para_has_revision(i) and '<w:sectPr' not in x:
                if drop_breaks and re.fullmatch(r'<w:p\b[^>]*>(<w:pPr>.*?</w:pPr>)?<w:r>(<w:rPr>.*?</w:rPr>)?'
                                r'<w:br w:type="page"/></w:r></w:p>', x, re.S):
                    del self.items[self.b0 + i]; self.say('M', i, 'removed manual page break', 'page-breaks'); continue
                if (drop_empty and self.style(i) in (NUMBERED | {'Normal', 'ListParagraph'})
                        and not self.text(i).strip() and '<w:drawing>' not in x
                        and '<w:br' not in x and '<w:fldChar' not in x and '<w:object' not in x):
                    del self.items[self.b0 + i]; self.say('M', i, 'deleted empty paragraph', 'empty-paras'); continue
            i += 1

    _MARKER_RE = re.compile(r'<w:(ins|del|moveFrom|moveTo|pPrChange|rPrChange|commentRangeStart'
                            r'|commentRangeEnd|commentReference|bookmarkStart)\b')

    def _para_has_marker(self, i):
        return bool(self._MARKER_RE.search(self.item(i)))

    @staticmethod
    def _pdf_join(a, b):
        return (a[:-1] + b) if a.endswith('-') and b[:1].islower() else (a + ' ' + b)

    def _merge_pdf_lines_preserving(self):
        """#1 as an AUTHORIZED text edit: join two consecutive block-quote (Excerpt or Quote)
        paragraphs that a PDF paste split mid-sentence — remove a trailing soft hyphen or insert the
        missing space. AUTO (per the structural-change policy) but only on CLEAN excerpts: a merge is
        skipped if EITHER paragraph carries any tracked change, comment or bookmark, so it can never
        disturb reviewed content; the merged text is BUILT as exactly the house join (the authorized
        edit, nothing else), and the ledger backstops the whole pass."""
        if self._skip('pdf-merge'):
            return
        snap = self._snapshot()
        merged = 0
        i = 0
        while i < self.n() - 1:
            if (self.is_par(i) and self.style(i) == 'ExcerptorQuote'
                    and self.is_par(i + 1) and self.style(i + 1) == 'ExcerptorQuote'
                    and not self._para_has_marker(i) and not self._para_has_marker(i + 1)):
                a, b = self.text(i).rstrip(), self.text(i + 1).strip()
                if a and b and (not re.search(r'[.!?:;"”]$', a) or a.endswith('-')):
                    joined = self._pdf_join(a, b)
                    head = re.match(r'(<w:p\b[^>]*>(?:<w:pPr>.*?</w:pPr>)?)', self.item(i), re.S).group(1)
                    self.set(i, head + f'<w:r><w:t xml:space="preserve">{esc(joined)}</w:t></w:r></w:p>')
                    del self.items[self.b0 + i + 1]
                    merged += 1
                    self.say('M', i, 'merged PDF line-break split excerpt (authorized text edit)', 'pdf-merge')
                    continue
            i += 1
        if merged:
            clean, _ = self.verify_preservation()
            if not clean:
                self._restore(snap)
                self.exceptions.append(('merge_pdf_lines', 'ledger backstop tripped (rolled back)'))

    def _caps_headings_preserving(self):
        """#9 as FORMATTING: display Heading1/2 uppercase via <w:caps/> on their runs, leaving the
        letters exactly as typed (content-safe)."""
        for i in range(self.n()):
            if not self.is_par(i) or self.style(i) not in ('Heading1', 'Heading2'):
                continue
            x = self.item(i)
            if '<w:caps/>' in x:
                continue
            def add_caps(rm):
                r = rm.group(0)
                if '<w:t' not in r:
                    return r
                if '<w:rPr>' in r:
                    return r.replace('<w:rPr>', '<w:rPr><w:caps/>', 1)
                return re.sub(r'(<w:r\b[^>]*>)', lambda m: m.group(1) + '<w:rPr><w:caps/></w:rPr>', r, count=1)
            nx = re.sub(r'<w:r\b[^>]*>.*?</w:r>', add_caps, x, flags=re.S)
            if nx != x:
                self.set(i, nx)

    def _repair_styles(self):
        """Fix corrupt LI style definitions (Claire's 'List Bullet dysfunctional' / 'table style
        corrupted'): overwrite the document's definition of any style the template defines with the
        template's correct definition, and add template styles the document lacks. Keep doc-only
        styles so revised paragraphs still resolve, and never touch docDefaults/theme. This is
        styles.xml only — orthogonal to every tracked change in the body."""
        if self._skip('styles-repair'):
            return
        tmpl = {m.group(1): m.group(0) for m in
                re.finditer(r'<w:style\b[^>]*w:styleId="([^"]+)".*?</w:style>', self.t_styles, re.S)}
        fixed = [0]
        def repl(m):
            sid = re.search(r'w:styleId="([^"]+)"', m.group(0)).group(1)
            if sid in tmpl and tmpl[sid] != m.group(0):
                fixed[0] += 1; return tmpl[sid]
            return m.group(0)
        self.styles = re.sub(r'<w:style\b[^>]*w:styleId="([^"]+)".*?</w:style>', repl,
                             self.styles, flags=re.S)
        existing = set(re.findall(r'<w:style [^>]*w:styleId="([^"]+)"', self.styles))
        add = [d for sid, d in tmpl.items() if sid not in existing]
        if add:
            self.styles = self.styles.replace('</w:styles>', ''.join(add) + '</w:styles>', 1)
        # add numbering definitions the doc lacks so repaired list styles resolve
        have_abs = set(re.findall(r'<w:abstractNum w:abstractNumId="(\d+)"', self.num))
        have_num = set(re.findall(r'<w:num w:numId="(\d+)"', self.num))
        addnum = [m.group(0) for m in re.finditer(r'<w:abstractNum w:abstractNumId="(\d+)".*?</w:abstractNum>',
                                                  self.t_num, re.S) if m.group(1) not in have_abs]
        addnum += [m.group(0) for m in re.finditer(r'<w:num w:numId="(\d+)"[^>]*>.*?</w:num>',
                                                   self.t_num, re.S) if m.group(1) not in have_num]
        if addnum:
            self.num = self.num.replace('</w:numbering>', ''.join(addnum) + '</w:numbering>', 1)
        self.say('M', -1, f'preserve mode: repaired {fixed[0]} corrupt style definitions + added '
                          f'{len(add)} missing styles / {len(addnum)} numbering defs (docDefaults untouched)',
                 'styles-repair')

    _CHANGE_RE = re.compile(
        r'<w:(tblPrChange|trPrChange|tcPrChange|pPrChange|rPrChange|sectPrChange|tblPrExChange'
        r'|tblGridChange|numberingChange)\b[^>]*>.*?</w:\1>', re.S)
    # wrapping (non-self-closing) content revisions — the inserted/deleted payload to protect
    _REV_CONTENT_RE = re.compile(r'<w:(ins|del|moveFrom|moveTo)\b[^>]*?(?<!/)>.*?</w:\1>', re.S)

    @classmethod
    def _mask_revisions(cls, xml, content=True):
        """Replace tracked-formatting snapshot blocks (always) and, when content=True, the
        inserted/deleted CONTENT of wrapping revisions, with sentinels — so a regex pass edits only
        non-revision material and can never touch a reject target or a tracked payload. Returns
        (masked_xml, restore_map)."""
        masks = {}
        def sub(m):
            tok = f'\x00R{len(masks)}\x00'; masks[tok] = m.group(0); return tok
        xml = cls._CHANGE_RE.sub(sub, xml)
        if content:
            xml = cls._REV_CONTENT_RE.sub(sub, xml)
        return xml, masks

    # kept for callers that only need snapshot protection
    @classmethod
    def _mask_changes(cls, xml):
        return cls._mask_revisions(xml, content=False)

    @staticmethod
    def _unmask(xml, masks):
        for tok in reversed(list(masks)):   # reverse so nested sentinels restore correctly
            xml = xml.replace(tok, masks[tok])
        return xml

    def _conform_tables_preserving(self):
        """Make every table USE the (now-repaired) LI table style so its built-in settings apply
        (Claire's 'tables not using the table style' / 'settings not used'). Table-level properties
        only, and tracked-formatting snapshots are masked out first, so no cell content and no reject
        target is touched."""
        if self._skip('tables'):
            return
        cnt = 0
        for i in range(self.n()):
            x = self.item(i)
            if not x.startswith('<w:tbl'):
                continue
            masked, masks = self._mask_revisions(x)   # protect snapshots AND cell revision content
            nx = re.sub(r'<w:tblBorders>.*?</w:tblBorders>', '', masked, flags=re.S)
            if '<w:tblStyle' in nx:
                nx = re.sub(r'<w:tblStyle w:val="[^"]+"/>', '<w:tblStyle w:val="LITable"/>', nx, count=1)
            else:
                nx = nx.replace('<w:tblPr>', '<w:tblPr><w:tblStyle w:val="LITable"/>', 1)
            nx = re.sub(r'<w:tblLook [^>]*/>',
                        '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" '
                        'w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>', nx)
            # cell paragraphs -> TableData (keep alignment); skip any paragraph holding a masked
            # revision (sentinel) so revised cells are left exactly as authored.
            def cell_para(pm):
                p = pm.group(0)
                if '\x00' in p:                       # masked content revision -> leave the cell
                    return p
                # set ONLY pStyle=TableData; keep the rest of pPr (jc, and any paragraph-mark
                # revision markers in the mark's rPr) so nothing tracked is dropped.
                if '<w:pStyle' in p:
                    return re.sub(r'<w:pStyle w:val="[^"]+"/>', '<w:pStyle w:val="TableData"/>', p, count=1)
                if '<w:pPr>' in p:
                    return p.replace('<w:pPr>', '<w:pPr><w:pStyle w:val="TableData"/>', 1)
                return re.sub(r'(<w:p\b[^>]*>)',
                              lambda mm: mm.group(1) + '<w:pPr><w:pStyle w:val="TableData"/></w:pPr>',
                              p, count=1)
            nx = re.sub(r'<w:p\b.*?</w:p>', cell_para, nx, flags=re.S)
            # first row repeats as a header
            fr = re.search(r'<w:tr\b.*?</w:tr>', nx, re.S)
            if fr and '<w:tblHeader' not in fr.group(0):
                hdr = (fr.group(0).replace('<w:tr>', '<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>', 1)
                       if '<w:trPr>' not in fr.group(0)
                       else fr.group(0).replace('<w:trPr>', '<w:trPr><w:tblHeader/>', 1))
                nx = nx.replace(fr.group(0), hdr, 1)
            nx = self._unmask(nx, masks)
            if nx != x:
                self.set(i, nx); cnt += 1
        if cnt:
            self.say('M', -1, f'preserve mode: {cnt} tables set to the LI table style', 'tables')

    # ================================================================ interactive ASK structural
    # The five ASK structural changes (#3 unwrap wrapper table, #5 extract floating image, #6 split
    # caption/heading from body, #7 drop empty columns, #8 rebuild caption/cross-references as
    # fields) each emit ONE JudgmentCall per instance through the existing analyze/apply mechanism.
    # They are DISPLAY-PRESERVING: the reader sees the same document; only the structure/machinery
    # changes. Each accepted instance is applied behind a fast LOCAL display gate (region signature,
    # O(instance) not O(document)); the whole pass then confirms with the ledger + whole-document
    # display gate. Instances on/adjacent to a tracked change or comment are flagged for individual
    # review (recommended action = review, not accept) but still protected by the gate if accepted.

    @staticmethod
    def _fld(instr, result, rstyle=None):
        rp = f'<w:rPr><w:rStyle w:val="{rstyle}"/></w:rPr>' if rstyle else ''
        return (f'<w:r>{rp}<w:fldChar w:fldCharType="begin"/></w:r>'
                f'<w:r>{rp}<w:instrText xml:space="preserve"> {instr} </w:instrText></w:r>'
                f'<w:r>{rp}<w:fldChar w:fldCharType="separate"/></w:r>'
                f'<w:r>{rp}<w:t xml:space="preserve">{esc(result)}</w:t></w:r>'
                f'<w:r>{rp}<w:fldChar w:fldCharType="end"/></w:r>')

    def _next_bm_id(self):
        ids = [int(x) for x in re.findall(r'<w:bookmarkStart w:id="(\d+)"', ''.join(self.items))]
        return max(ids + [900]) + 1

    def _ask_pass(self, kind, detect):
        """Generic interactive ASK structural pass. `detect()` returns candidate dicts WITHOUT
        mutating — {index, message, recommended, apply, tracked_adjacent?, span?, alternatives?,
        ...op data}. Detection runs first so JudgmentCall ids match between analyze() and
        apply_with_decisions(); accepted instances are applied in REVERSE index order (so earlier
        indices stay valid) each behind a fast local display gate; a whole-document backstop rolls
        the pass back if anything slipped through the local gates."""
        from conformer import revisions as _rev
        cands = detect()
        plan = []
        for cand in cands:
            i = cand['index']
            adj = cand.get('tracked_adjacent', False)
            rec = 'Review individually (tracked change nearby)' if adj else cand['recommended']
            jc = self._jcall(kind, i, cand['message'], rec, cand.get('alternatives'))
            jc.needs_review = adj
            self.say('J', i, cand['message'])
            dec = self._decision_for(jc)
            if dec == 'accept' or dec.startswith('change'):
                plan.append(cand)
        if not plan:
            return
        pass_snap = self._snapshot()
        before_disp = _rev.visible_stream(self._output_parts(), cache=self._verify_cache)
        applied = 0
        for cand in sorted(plan, key=lambda c: c['index'], reverse=True):
            if self._apply_ask_instance(kind, cand):
                applied += 1
        if not applied:
            return
        clean, _ = self.verify_preservation()
        after_disp = _rev.visible_stream(self._output_parts(), cache=self._verify_cache)
        if not clean or _rev.visible_violations(before_disp, after_disp):
            self._restore(pass_snap)
            self.exceptions.append((kind, f'whole-pass backstop tripped ({applied} instance(s) '
                                          f'rolled back)'))

    def _apply_ask_instance(self, kind, cand):
        """Apply ONE ASK instance behind a local display gate: the fragment of items it touches must
        keep an identical display stream (visible text + objects + revision/comment boundaries) and
        lose no existing bookmark. On any disturbance, roll the single instance back and record an
        exception — one risky instance never poisons the batch."""
        from conformer import revisions as _rev
        i = cand['index']; span = cand.get('span', 1)
        lo = max(0, i - 1)
        hi = min(self.n(), i + span + 1)
        before_frag = ''.join(self.item(j) for j in range(lo, hi))
        n_before = self.n()
        snap = self._snapshot()
        try:
            cand['apply'](cand)
        except Exception as e:
            self._restore(snap)
            self.exceptions.append((f'{kind}[{i}]', f'apply error: {str(e)[:80]}'))
            return False
        hi_after = hi + (self.n() - n_before)
        after_frag = ''.join(self.item(j) for j in range(lo, min(self.n(), hi_after)))
        if (_rev.visible_violations({'d': _rev.region_display(before_frag)},
                                    {'d': _rev.region_display(after_frag)})
                or _rev.bookmarks_lost(before_frag, after_frag)):
            self._restore(snap)
            self.exceptions.append((f'{kind}[{i}]', 'local display gate tripped (not applied)'))
            return False
        return True

    # ---------------------------------------------------------------- #8 captions + cross-references
    _CAP_RE = re.compile(r'^(Table|Figure) (\d+)([-‑‐–])(\d+)(:.*)$', re.S)

    def _caption_fields_preserving(self):
        """#8a: rebuild a literal 'Table 3-1: Title' / 'Figure 3-1: Title' caption as
        STYLEREF/SEQ auto-number fields anchored by a bookmark, so cross-references can target it and
        Word can renumber. Display-preserving: the caption reads identically (cached field results =
        the current numbers, separator kept verbatim). Skips captions already fielded+bookmarked and
        flags tracked-adjacent captions for review."""
        def detect():
            out = []
            for i in range(self.n()):
                if not self.is_par(i) or self.style(i) != 'Caption':
                    continue
                x = self.item(i); t = self.text(i).strip()
                m = self._CAP_RE.match(t)
                if not m:
                    continue
                has_seq = 'SEQ ' in x and '<w:bookmarkStart' in x
                if has_seq:
                    continue
                label, a, sep, b, rest = m.groups()
                existing = re.search(r'<w:bookmarkStart w:id="\d+" w:name="([^"]+)"', x)
                name = existing.group(1) if existing else f'_Ref_{label[0]}{a}{b}'
                bid = self._next_bm_id()
                inner = (f'<w:r><w:t xml:space="preserve">{label} </w:t></w:r>'
                         + self._fld('STYLEREF 1 \\s', a)
                         + f'<w:r><w:t xml:space="preserve">{esc(sep)}</w:t></w:r>'
                         + self._fld(f'SEQ {label} \\* ARABIC \\s 1', b)
                         + f'<w:r><w:t xml:space="preserve">{esc(rest)}</w:t></w:r>')
                bm = f'<w:bookmarkStart w:id="{bid}" w:name="{name}"/>{inner}<w:bookmarkEnd w:id="{bid}"/>'
                newx = '<w:p><w:pPr><w:pStyle w:val="Caption"/><w:jc w:val="center"/></w:pPr>' + bm + '</w:p>'
                out.append({'index': i, 'newxml': newx, 'apply': self._apply_setitem,
                            'recommended': 'Accept (display unchanged; enables auto-numbering)',
                            'tracked_adjacent': self._para_has_revision(i),
                            'message': f'rebuild caption {t[:40]!r} as STYLEREF/SEQ fields + bookmark'})
            return out
        self._ask_pass('caption', detect)

    def _apply_setitem(self, cand):
        self.set(cand['index'], cand['newxml'])

    def _xrefs_preserving(self):
        """#8b (Claire's explicit need): rebuild literal cross-references — 'Figure 3-1', 'Table
        3-1', 'Section 5', 'Sections 5 and 7' — as live REF fields pointing at the caption/heading
        bookmark, so they update with the document. Display-preserving (the field's cached result IS
        the original literal text). Only rewrites PLAIN runs (revision content is masked out), only
        when the target bookmark exists, and one JudgmentCall per paragraph."""
        caps, heads = self._xref_targets()
        def detect():
            out = []
            for i in range(self.n()):
                if not self.is_par(i) or self.style(i) == 'Caption' or self.style(i) in HEADINGS:
                    continue
                newx, refs = self._rebuild_xrefs_in(self.item(i), caps, heads)
                if refs:
                    out.append({'index': i, 'newxml': newx, 'apply': self._apply_setitem,
                                'recommended': 'Accept (displayed text unchanged)',
                                'tracked_adjacent': self._para_has_revision(i),
                                'message': f'rebuild {refs} literal cross-reference(s) as REF field(s)'})
            return out
        self._ask_pass('xref', detect)

    def _xref_targets(self):
        """caps: 'Figure 3-1' -> bookmark name (from a bookmarked caption); heads: section ordinal
        -> bookmark name (from a bookmarked Heading1). Only targets that ALREADY have a bookmark are
        offered, so #8b never has to mutate a second paragraph to create one."""
        caps = {}
        for i in range(self.n()):
            if self.style(i) != 'Caption':
                continue
            t = self.text(i).strip()
            m = re.match(r'(Table|Figure) (\d+)[-‑‐–](\d+)', t)
            bm = re.search(r'<w:bookmarkStart w:id="\d+" w:name="([^"]+)"', self.item(i))
            if m and bm:
                caps[f'{m.group(1)} {m.group(2)}-{m.group(3)}'] = bm.group(1)
        heads = {}; hn = 0
        for i in range(self.n()):
            if self.style(i) == 'Heading1':
                hn += 1
                bm = re.search(r'<w:bookmarkStart w:id="\d+" w:name="([^"]+)"', self.item(i))
                if bm:
                    heads[str(hn)] = bm.group(1)
        return caps, heads

    _XREF_RE = re.compile(r'(Table|Figure) (\d+-\d+)|Sections? (\d+)(?!\.\d)(?: and (\d+)(?!\.\d))?')

    def _rebuild_xrefs_in(self, xml, caps, heads):
        """Return (new_xml, count) with literal cross-references in PLAIN runs rewritten as REF
        fields. Revision content is masked first, so tracked insertions/deletions are never edited;
        runs already carrying a CrossReference style or field are left alone."""
        masked, masks = self._mask_revisions(xml)
        count = [0]
        def repl_text(seg):
            out = ''; pos = 0
            for mm in self._XREF_RE.finditer(seg):
                pre = seg[pos:mm.start()]
                if pre:
                    out += f'<w:r><w:t xml:space="preserve">{esc(pre)}</w:t></w:r>'
                if mm.group(1):                                   # Figure/Table N-M
                    key = f'{mm.group(1)} {mm.group(2)}'
                    if key in caps:
                        out += self._fld(f'REF {caps[key]} \\h', key, 'CrossReference'); count[0] += 1
                    else:
                        out += f'<w:r><w:t xml:space="preserve">{esc(mm.group(0))}</w:t></w:r>'
                else:                                             # Section(s) N [and M]
                    word = 'Sections' if mm.group(0).startswith('Sections') else 'Section'
                    out += f'<w:r><w:t xml:space="preserve">{word} </w:t></w:r>'
                    g3, g4 = mm.group(3), mm.group(4)
                    out += (self._fld(f'REF {heads[g3]} \\r \\h', g3, 'CrossReference')
                            if g3 in heads else f'<w:r><w:t xml:space="preserve">{esc(g3)}</w:t></w:r>')
                    if g3 in heads:
                        count[0] += 1
                    if g4:
                        out += '<w:r><w:t xml:space="preserve"> and </w:t></w:r>'
                        out += (self._fld(f'REF {heads[g4]} \\r \\h', g4, 'CrossReference')
                                if g4 in heads else f'<w:r><w:t xml:space="preserve">{esc(g4)}</w:t></w:r>')
                        if g4 in heads:
                            count[0] += 1
                pos = mm.end()
            if pos == 0:
                return None
            rest = seg[pos:]
            if rest:
                out += f'<w:r><w:t xml:space="preserve">{esc(rest)}</w:t></w:r>'
            return out
        # rewrite only plain text runs (no rStyle, not sentinels): <w:r>[<w:rPr>..</w:rPr>]<w:t>..</w:t></w:r>
        def run_sub(rm):
            r = rm.group(0)
            if 'CrossReference' in r or '\x00' in r:
                return r
            tm = re.search(r'<w:t(?: xml:space="preserve")?>([^<]*)</w:t>', r)
            if not tm:
                return r
            rebuilt = repl_text(tm.group(1))
            return rebuilt if rebuilt is not None else r
        new_masked = re.sub(r'<w:r\b[^>]*>(?:<w:rPr>.*?</w:rPr>)?<w:t(?: xml:space="preserve")?>[^<]*</w:t></w:r>',
                            run_sub, masked, flags=re.S)
        return self._unmask(new_masked, masks), count[0]

    # ---------------------------------------------------------------- #3 unwrap wrapper tables
    _CELL_MARKER_RE = re.compile(r'<w:(ins|del|moveFrom|moveTo|bookmarkStart|commentRangeStart'
                                 r'|commentReference|pPrChange|rPrChange)\b')

    def _unwrap_tables_preserving(self):
        """#3: a single-cell (1 row x 1 cell) table with no table style is a layout WRAPPER — unwrap
        it, replacing the table with the cell's own paragraphs. Display-preserving (only the table
        shell, invisible to the reader, is removed). Tracked-adjacent wrapper tables are flagged for
        review; the gate protects any revision/comment/bookmark inside either way."""
        def detect():
            out = []
            for i in range(self.n()):
                x = self.item(i)
                if not x.startswith('<w:tbl'):
                    continue
                if '<w:tblStyle' in x:
                    continue
                if len(re.findall(r'<w:tr\b', x)) != 1 or len(re.findall(r'<w:tc>', x)) != 1:
                    continue
                paras = self._wrapper_cell_items(x)
                if paras is None or not paras:
                    continue
                out.append({'index': i, 'paras': paras, 'apply': self._apply_unwrap, 'span': 1,
                            'recommended': 'Accept (removes an invisible layout wrapper)',
                            'tracked_adjacent': bool(self._CELL_MARKER_RE.search(x)),
                            'message': f'unwrap single-cell wrapper table into {len(paras)} paragraph(s)'})
            return out
        self._ask_pass('unwrap', detect)

    @staticmethod
    def _wrapper_cell_items(tbl_xml):
        """Body items inside the single cell of a wrapper table, or None if it can't be parsed."""
        tc = tbl_xml.find('<w:tc>')
        if tc < 0:
            return None
        end = span(tbl_xml, 'tc', tc)
        if end is None:
            return None
        inner = tbl_xml[tc + len('<w:tc>'):end - len('</w:tc>')]
        if inner.startswith('<w:tcPr>'):
            tcend = span(inner, 'tcPr', 0)
            if tcend is not None:
                inner = inner[tcend:]
        try:
            return split_body(inner)
        except ValueError:
            return None

    def _apply_unwrap(self, cand):
        i = cand['index']
        self.items[self.b0 + i:self.b0 + i + 1] = cand['paras']
        self.say('M', i, f"unwrapped wrapper table into {len(cand['paras'])} paragraph(s)")

    # ---------------------------------------------------------------- #7 drop empty table columns
    def _drop_empty_columns_preserving(self):
        """#7: drop table columns that are empty in every row (no text, object, bookmark, comment or
        tracked change) from a simple (un-merged) grid. Display-preserving: only empty structure is
        removed. One JudgmentCall per table; tables with merged cells are skipped (too ambiguous to
        touch safely) and the gate backstops."""
        def detect():
            out = []
            for i in range(self.n()):
                x = self.item(i)
                if not x.startswith('<w:tbl'):
                    continue
                if re.search(r'<w:(gridSpan|vMerge|hMerge)\b', x):
                    continue
                rows = re.findall(r'<w:tr\b.*?</w:tr>', x, re.S)
                cells = [re.findall(r'<w:tc>.*?</w:tc>', r, re.S) for r in rows]
                if not cells or not any(cells):
                    continue
                ncol = max(len(c) for c in cells)
                empty = [k for k in range(ncol)
                         if all(len(c) > k and self._cell_is_empty(c[k]) for c in cells)]
                if not empty:
                    continue
                out.append({'index': i, 'empty': empty, 'apply': self._apply_drop_cols, 'span': 1,
                            'recommended': 'Accept (empty columns only)',
                            'tracked_adjacent': bool(self._CELL_MARKER_RE.search(x)),
                            'message': f'drop {len(empty)} empty table column(s)'})
            return out
        self._ask_pass('dropcol', detect)

    @classmethod
    def _cell_is_empty(cls, cell):
        return (not text_of(cell).strip() and '<w:drawing' not in cell
                and not cls._CELL_MARKER_RE.search(cell))

    def _apply_drop_cols(self, cand):
        i = cand['index']; x = self.item(i); empty = cand['empty']
        rows = re.findall(r'<w:tr\b.*?</w:tr>', x, re.S)
        cells = [re.findall(r'<w:tc>.*?</w:tc>', r, re.S) for r in rows]
        for r, cs in zip(rows, cells):
            nr = r
            for k in sorted(empty, reverse=True):
                if len(cs) > k:
                    nr = nr.replace(cs[k], '', 1)
            x = x.replace(r, nr, 1)
        grid = re.findall(r'<w:gridCol w:w="\d+"/>', x)
        for k in sorted(empty, reverse=True):
            if len(grid) > k:
                x = x.replace(grid[k], '', 1)
        width = sum(int(w) for w in re.findall(r'<w:gridCol w:w="(\d+)"/>', x))
        if width:
            x = re.sub(r'<w:tblW [^>]*/>', f'<w:tblW w:w="{width}" w:type="dxa"/>', x)
        self.set(i, x); self.say('M', i, f'removed {len(empty)} empty column(s)')

    # ---------------------------------------------------------------- #6 split caption/heading + body
    _SPLIT_SEP_RE = re.compile(r'<w:r\b[^>]*>(?:<w:rPr>.*?</w:rPr>)?'
                               r'<w:t xml:space="preserve">(?: {2,}|\t)</w:t></w:r>', re.S)

    def _split_headings_preserving(self):
        """#6: a heading or caption paragraph with body text mashed onto the end (separated by a
        double space or tab run) is split into two paragraphs. Display-preserving: the separator run
        is KEPT on the heading side (invisible trailing whitespace) so not a single character is
        lost — the split only inserts a paragraph break where a run boundary already was. Skips /
        flags tracked-adjacent instances."""
        def detect():
            out = []
            for i in range(self.n()):
                if not self.is_par(i) or self.style(i) not in (HEADINGS | {'Caption'}):
                    continue
                x = self.item(i)
                m = self._SPLIT_SEP_RE.search(x)
                if not m:
                    continue
                before = text_of(x[:m.start()]).strip()
                after = text_of(x[m.end():]).strip()
                if not before or not after:
                    continue
                body_style = 'BodyText' if self.style(i) == 'Caption' else 'NumberedParagraph'
                out.append({'index': i, 'sep_end': m.end(), 'body_style': body_style,
                            'apply': self._apply_split, 'span': 1,
                            'recommended': 'Accept (separates merged heading and body text)',
                            'tracked_adjacent': self._para_has_revision(i),
                            'message': f'split body text off the {self.style(i)} paragraph {before[:35]!r}'})
            return out
        self._ask_pass('splitcap', detect)

    def _apply_split(self, cand):
        i = cand['index']; x = self.item(i)
        head_x = x[:cand['sep_end']] + '</w:p>'            # keep the separator run on the heading
        body_x = (f'<w:p><w:pPr><w:pStyle w:val="{cand["body_style"]}"/></w:pPr>'
                  + x[cand['sep_end']:])
        self.set(i, head_x)
        self.items.insert(self.b0 + i + 1, body_x)
        self.say('M', i, f'split merged {cand["body_style"]} body text into its own paragraph')

    # ---------------------------------------------------------------- #5 extract floating image inline
    def _extract_images_preserving(self):
        """#5: a paragraph whose only content is a FLOATING (anchored) picture is converted to an
        INLINE picture in the same paragraph (LI figures are inline). Display-preserving: the image
        object stays in the same paragraph and stream position; only its float/anchor wrapper — never
        visible to the reader as text — becomes inline. The mixed image+caption+body case (which
        would relocate the object) is intentionally left to a future looser-gate op. Flags
        tracked-adjacent instances."""
        def detect():
            out = []
            for i in range(self.n()):
                if not self.is_par(i):
                    continue
                x = self.item(i)
                if '<wp:anchor' not in x or text_of(x).strip():
                    continue
                out.append({'index': i, 'apply': self._apply_extract_image, 'span': 1,
                            'recommended': 'Accept (float -> inline; image unchanged)',
                            'tracked_adjacent': self._para_has_revision(i),
                            'message': 'convert floating picture to an inline figure'})
            return out
        self._ask_pass('imgextract', detect)

    def _apply_extract_image(self, cand):
        i = cand['index']
        x = self._anchor_to_inline(self.item(i))
        self.set(i, x)
        if self.style(i) != 'SpacebehindafteraGraphic':
            self.set_style(i, 'SpacebehindafteraGraphic')
        self.say('M', i, 'converted floating picture to inline figure')

    def run(self):
        self._run_passes()

    def analyze(self):
        self.decisions = None
        self._run_passes()
        return list(self.pending_judgments)

    def apply_with_decisions(self, decisions, progress=None):
        fresh = Conformer(self.template_path, self.input_path)
        fresh.decisions = decisions
        fresh.progress = progress
        fresh._run_passes()
        return fresh

    def _output_parts(self):
        """The package parts as they would be written by save(), for validation/verification.
        In preserve mode we DO NOT run normalize(): reordering rPr/pPr children is benign for a
        clean doc but rewrites the canonical form of revision snapshots, so untouched revision
        content must stay byte-identical for the preservation gate to mean anything."""
        body = self.head + ''.join(self.items) + self.tail
        preserve = self.disposition == 'preserve'
        doc = body if preserve else normalize(body)
        fn = self.fn if preserve else normalize(self.fn)
        parts = dict(self.parts)
        parts['word/document.xml'] = doc.encode('utf8')
        parts['word/styles.xml'] = self.styles.encode('utf8')
        parts['word/numbering.xml'] = self.num.encode('utf8')
        parts['word/footnotes.xml'] = fn.encode('utf8')
        parts['word/settings.xml'] = self.settings.encode('utf8')
        return parts

    def verify_preservation(self, allow_introduced=False):
        """Rebuild the revision ledger from the conformed output and diff it against the original.
        Returns (clean: bool, discrepancies: dict). A preservation gate for review-preserving
        conformance: refuse delivery when a tracked change was silently lost, altered, or
        re-attributed. NOTE: for ACCEPT/REJECT dispositions revisions are intentionally resolved,
        so this gate applies to preservation modes, not to accept/reject projections."""
        from conformer import revisions as _rev
        after = _rev.Ledger.build(self._output_parts(), cache=self._verify_cache)
        d = _rev.diff(self.revision_ledger, after)
        return _rev.is_clean(d, allow_introduced=allow_introduced), d

    # ---------------------------------------------------------------- normalized-copy label + audit
    REVIEW_COPY_LABEL = ('Normalized-formatting review copy — formatting conformed to the LI '
                         'template; tracked changes, comments and authorship preserved and verified. '
                         'Not a fully-conformed reading copy.')

    def _label_review_copy(self):
        """GPT-6 2a: stamp the output as a normalized-formatting review copy. Written to the
        docProps/core.xml <cp:contentStatus> — the schema's own document-status field, shown in
        Word's file properties — so the file is never mistaken for a fully-conformed reading copy.
        core.xml is not a story part, so this never affects the preservation gate."""
        core = self.parts.get('docProps/core.xml')
        if not core:
            return
        text = core.decode('utf8')
        status = esc(self.REVIEW_COPY_LABEL)
        if '<cp:contentStatus>' in text:
            text = re.sub(r'<cp:contentStatus>.*?</cp:contentStatus>',
                          f'<cp:contentStatus>{status}</cp:contentStatus>', text, flags=re.S)
        elif '</cp:coreProperties>' in text:
            text = text.replace('</cp:coreProperties>',
                                f'<cp:contentStatus>{status}</cp:contentStatus></cp:coreProperties>', 1)
        else:
            return
        self.parts['docProps/core.xml'] = text.encode('utf8')

    def build_audit(self):
        """Machine-readable audit record for a review-preserving output (GPT-6 2a): the disposition
        and its honest label, the original package SHA-256 (the byte-exact fidelity anchor), the
        revision inventory, the preservation-gate verdict, every pass rolled back and why, and the
        judgment calls surfaced. Written beside the output by write_audit()."""
        import hashlib
        import datetime
        from collections import Counter
        clean, disc = self.verify_preservation()
        try:
            with open(self.input_path, 'rb') as fh:
                src_sha = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            src_sha = None
        return {
            'tool': 'LI Report Conformer',
            'disposition': self.disposition or 'clean',
            'label': self.REVIEW_COPY_LABEL if self.disposition == 'preserve' else 'Conformed copy',
            'generated': datetime.datetime.now().isoformat(timespec='seconds'),
            'source_file': os.path.basename(self.input_path),
            'source_sha256': src_sha,
            'revision_summary': self.revision_ledger.summary(),
            'preservation_verified': clean,
            'preservation_discrepancies': {k: len(v) for k, v in disc.items()
                                           if isinstance(v, list) and v},
            'passes_rolled_back': [{'pass': n, 'reason': r} for n, r in self.exceptions],
            'judgment_calls': {'total': len(self.pending_judgments),
                               'by_kind': dict(Counter(jc.kind for jc in self.pending_judgments))},
            'mechanical_actions': len(self.log),
            'figure_audit': [{'level': lvl, 'detail': msg} for lvl, msg in self.audit],
        }

    def write_audit(self, docx_path):
        """Write <stem>_conform_audit.json next to the output. Returns its path."""
        stem, _ = os.path.splitext(docx_path)
        audit_path = stem + '_conform_audit.json'
        with open(audit_path, 'w', encoding='utf8') as fh:
            json.dump(self.build_audit(), fh, indent=2)
        return audit_path

    def validate_output(self):
        parts = self._output_parts()
        import io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            for n_, b in parts.items(): z.writestr(n_, b)
        buf.seek(0)
        import xml.etree.ElementTree as ET
        try:
            with zipfile.ZipFile(buf) as z:
                names = z.namelist()
                for required in ('[Content_Types].xml', 'word/document.xml'):
                    if required not in names:
                        return False, f'Missing required part {required}'
                for name in names:
                    if name.endswith('.xml') or name.endswith('.rels'):
                        try:
                            ET.fromstring(z.read(name))
                        except ET.ParseError as e:
                            return False, f'Malformed XML in {name}: {e}'
            return True, 'Output validated'
        except Exception as e:
            return False, str(e)


if __name__ == '__main__':
    tpl, src, dst = sys.argv[1:4]
    c = Conformer(tpl, src); c.run(); c.save(dst)
    if '--log' in sys.argv: json.dump({'mechanical': c.log, 'judgment': c.judgment}, open(sys.argv[sys.argv.index('--log') + 1], 'w'), indent=1)
    print(f'{os.path.basename(src)}: {len(c.log)} mechanical actions, {len(c.judgment)} judgment calls')
