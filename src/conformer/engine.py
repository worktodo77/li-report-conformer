"""LI report conformer: repair a damaged report so it conforms to the LI template and guidelines.

Two-pass architecture for interactive review:
  1. analyze() — runs all passes, applies everything, collects enriched judgment info
  2. apply_with_decisions(decisions) — re-runs from the original file, applying only
     accepted/changed judgment calls per user decisions

Original CLI flow (run() + save()) still works unchanged.
"""
import re, os, sys, json, zipfile
from dataclasses import dataclass, field

__all__ = ['Conformer', 'JudgmentCall', 'STYLE_ALTERNATIVES',
           'report_page_size', 'select_template', 'LETTER_TEMPLATE_NAME', 'A4_TEMPLATE_NAME']

# The two authoritative LI templates (23 July 2026). template.dotx is byte-identical (styles/numbering/
# document) to "LI Report Template LTR 23 July 2026.dotx" — the US-Letter variant — so it is the Letter
# template under a stable bundled name. The A4 variant differs by page-size-specific style geometry
# (ListBullet ilvl/indent, Heading 4-6 indents, Heading 6 size), so a report is conformed to whichever
# matches its own page size (GPT audit F7).
LETTER_TEMPLATE_NAME = 'template.dotx'
A4_TEMPLATE_NAME = 'LI Report Template A4 23 July 2026.dotx'


def report_page_size(path):
    """Return 'A4' or 'Letter' for a .docx, from its first section's page height (A4 = 297mm ~= 16839
    twips; US Letter = 11in = 15840 twips; the midpoint 16340 discriminates). Landscape sections are
    de-rotated first. Defaults to Letter when the size cannot be read."""
    try:
        with zipfile.ZipFile(path) as z:
            doc = z.read('word/document.xml').decode('utf8', 'replace')
    except Exception:
        return 'Letter'
    for tag in re.findall(r'<w:pgSz\b[^>]*/>', doc):
        wv = re.search(r'w:w="(\d+)"', tag)
        hv = re.search(r'w:h="(\d+)"', tag)
        if not (wv and hv):
            continue
        w, h = int(wv.group(1)), int(hv.group(1))
        if 'w:orient="landscape"' in tag:
            w, h = h, w
        return 'A4' if h > 16340 else 'Letter'
    return 'Letter'


def select_template(input_path, assets_dir):
    """Pick the authoritative LI template matching the report's page size: the A4 July 2026 template for
    an A4 report, else the Letter (LTR) July 2026 template bundled as template.dotx. Falls back to the
    Letter template when the A4 asset is absent (GPT audit F7)."""
    if report_page_size(input_path) == 'A4':
        a4 = os.path.join(assets_dir, A4_TEMPLATE_NAME)
        if os.path.exists(a4):
            return a4
    return os.path.join(assets_dir, LETTER_TEMPLATE_NAME)

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
class ReviewOnlyRequired(Exception):
    """Raised by the guarded save entry point when a not-clean/unknown output would be written without an
    explicit review-only opt-in (issue #1 E)."""


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
    ONLY authorized text change, so any other text edit is caught. NOTE: spelling out a measurement
    (2" -> 2-inch) is NOT here — it is a house-style edit (_house_edit), so it applies to body prose
    only and never rewrites a verbatim Excerpt/Quote or Caption (guideline §5, D-2)."""
    t = re.sub(r'(^|[\s(\[])"', '\\1\u201c', t); t = t.replace('"', '\u201d')
    t = re.sub(r"(^|[\s(\[])'", '\\1\u2018', t); t = t.replace("'", '\u2019')
    t = re.sub(r'(\w)--(\w)', '\\1\u2013\\2', t)
    # PUNC-2 / NUM-4: en dash for number/date RANGES, scoped so caption numbers (Table 3-1, 3.6.15-7),
    # activity IDs (A7-14, 2017-2019A, C-MT-MC-2020) and other hyphenated tokens are never touched:
    # ALPHABETIC boundaries both sides; a trailing sentence period is allowed but a decimal is not; and
    # §8.2.1: a range introduced by "from" or "between" is left as-is (no en dash there).
    t = re.sub(r'(?<![Ff]rom )(?<![Bb]etween )(?<!Table )(?<!Figure )(?<!Section )(?<![\d.\-A-Za-z])'
               r'((?:19|20)\d{2})-((?:19|20)\d{2})(?![-\dA-Za-z]|\.\d)', '\\1\u2013\\2', t)
    t = re.sub(r'(?<![Ff]rom )(?<![Bb]etween )(?<![\d.\-A-Za-z])'
               r'(\d+)-(\d+)(\s+(?:calendar days?|working days?|business days?|days?|'
               r'weeks?|months?|years?|CD|WD)\b)', '\\1\u2013\\2\\3', t)
    # PUNC-2: em dash closed up (no surrounding spaces) — only BETWEEN two non-space characters. Use a
    # lookahead for the trailing char (do not consume it) so adjacent em dashes ("a — b — c") both close.
    t = re.sub(r'(\S)\s*\u2014\s*(?=\S)', '\\1\u2014', t)
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
# British -> American spelling (§8.1). GPT audit: 'analyses'->'analyzes' CORRUPTS the noun ("the analyses
# are complete"), so the ambiguous -yses form is removed (the verb forms analyse/analysed/analysing stay);
# 'matrices'->'matrixes' is not required. 'programme'->'schedule' is a TERMINOLOGY swap, not a spelling
# rule, and is not in the template guidelines — removed here (re-add only under a cited house-style authority).
BRIT_US = {
    'analyse': 'analyze', 'analysed': 'analyzed', 'analysing': 'analyzing',
    'modelling': 'modeling', 'modelled': 'modeled',
    'behaviour': 'behavior', 'behaviours': 'behaviors', 'colour': 'color', 'favour': 'favor',
    'labour': 'labor', 'organisation': 'organization', 'organisations': 'organizations',
    'organise': 'organize', 'organised': 'organized', 'recognise': 'recognize',
    'recognised': 'recognized', 'prioritise': 'prioritize', 'judgement': 'judgment',
    'defence': 'defense', 'centre': 'center', 'metre': 'meter', 'litre': 'liter', 'fibre': 'fiber',
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
    t = re.sub(r'(\d)["”]', r'\1-inch', t)    # authorize the body-prose inch spelling-out (D-2)
    t = _BRIT_RE.sub(_brit_case, t)
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
# Property-specific direct run-formatting policy (replaces blanket whitelist stripping). MEANING-BEARING
# formatting (super/subscript, strike, hidden) and REVIEW formatting (highlight, meaningful colour) are
# PRESERVED; only house-controlled appearance (font family, size, spacing, underline, caps, position, …)
# is normalised to the paragraph style. Preserving these needs NO gate change — the content-stream gate is
# formatting-blind — so the effect is purely to stop destroying formatting that carries meaning.
KEEP_RPR = {'rStyle', 'b', 'bCs', 'i', 'iCs',       # character style / emphasis
            'vertAlign',                            # super/subscript — H2S, ordinals (meaning)
            'strike', 'dstrike',                    # strike-through (meaning)
            'vanish', 'specVanish',                 # hidden text (meaning)
            'highlight',                            # review highlight (meaning)
            'noProof', 'lang'}                      # proofing / locale (harmless, carried)
# NOTE colour is handled separately (keep_rpr_children's keep_color): meaningful colour preservation with
# the style-redundancy + conflict-report refinement is a focused follow-up, since it changes output on
# real reports (e.g. coloured headings). Until then colour follows the prior rule (kept for TableData
# header runs, normalised elsewhere) so the golden reference stays valid.
_SYMBOL_FONTS = {'Symbol', 'Wingdings', 'Wingdings 2', 'Wingdings 3', 'Webdings', 'Cambria Math', 'MT Extra'}


_DEFAULT_COLORS = {'000000', 'auto', 'windowtext', 'black'}
_DEFAULT_THEME = {'text1', 'dark1', 'windowtext'}


def _keep_rfonts(cx):
    """Keep an rFonts only when it carries a symbol/math font or a complex-script glyph (its font choice
    IS the glyph — stripping it corrupts the character). Ordinary body fonts are normalised to the style."""
    if 'w:hint="cs"' in cx or 'w:hint="eastAsia"' in cx:
        return True
    return any(m.group(1) in _SYMBOL_FONTS
               for m in re.finditer(r'w:(?:ascii|hAnsi|cs)="([^"]+)"', cx))


def _keep_color(cx):
    """Keep a run colour only when it is MEANINGFUL — genuinely coloured text a reviewer should see.
    Default black/auto (incl. themeColor text1) is the house appearance and is normalised away."""
    val = re.search(r'w:val="([^"]+)"', cx)
    theme = re.search(r'w:themeColor="([^"]+)"', cx)
    v = val.group(1).lower() if val else None
    if v and v not in _DEFAULT_COLORS:
        return True                                   # an explicit non-black colour is meaningful
    if v in _DEFAULT_COLORS or v is None:
        # black/auto (optionally with a text theme) → default appearance, drop it
        if theme is None or theme.group(1).lower() in _DEFAULT_THEME:
            return False
    return True


def keep_rpr_children(rpr_inner, is_fnref=False, keep_color=False):
    """Filter a run's rPr children by the property policy: keep meaning-bearing/review properties and
    symbol fonts, drop house-controlled appearance. Shared by strip_direct and fix_footnotes so the H2S
    subscript, ordinal superscripts and highlights survive in body text AND footnotes alike.

    `keep_color`: keep the colour child (used for TableData header runs, whose white text is house). The
    broader 'preserve meaningful colour everywhere + report conflicts' rule is a focused follow-up."""
    kept = []
    for tag, cx in children(rpr_inner):
        if tag == 'color':
            kept.append(cx)                           # colour is decided by the colour/highlight pass
        elif tag in KEEP_RPR:
            if tag in ('i', 'iCs') and is_fnref:      # the in-text footnote reference stays upright
                continue
            kept.append(cx)
        elif tag == 'rFonts' and _keep_rfonts(cx):
            kept.append(cx)
    return kept
# Fallback house table style (Grid Table 4 / "LI Table"), used ONLY if a template lacks it: teal B6DDE8
# header, black bold Times New Roman Bold 10pt header text, black ½pt grid. Colours are CONCRETE (no
# themeFill) so it renders correctly regardless of the document's theme.
GRIDTABLE4 = ('<w:style w:type="table" w:styleId="GridTable4"><w:name w:val="Grid Table 4"/><w:aliases w:val="LI Table"/><w:basedOn w:val="TableNormal"/><w:uiPriority w:val="49"/>'
  '<w:pPr><w:spacing w:before="60" w:after="60"/></w:pPr><w:rPr><w:sz w:val="22"/></w:rPr>'
  '<w:tblPr><w:tblStyleRowBandSize w:val="1"/><w:tblStyleColBandSize w:val="1"/><w:jc w:val="center"/><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tblBorders></w:tblPr>'
  '<w:trPr><w:cantSplit/><w:jc w:val="center"/></w:trPr>'
  '<w:tblStylePr w:type="firstRow"><w:pPr><w:wordWrap/><w:spacing w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr><w:rPr><w:rFonts w:ascii="Times New Roman Bold" w:hAnsi="Times New Roman Bold"/><w:b/><w:bCs/><w:i w:val="0"/><w:caps w:val="0"/><w:color w:val="auto"/><w:sz w:val="20"/><w:u w:val="none"/><w:vertAlign w:val="baseline"/></w:rPr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr><w:tcPr><w:tcBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideH w:val="nil"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tcBorders><w:shd w:val="clear" w:color="auto" w:fill="B6DDE8"/><w:vAlign w:val="bottom"/></w:tcPr></w:tblStylePr></w:style>')


def _theme_independent_style(style_xml):
    """Strip themeFill/themeFillTint/themeFillShade/themeColor/themeTint/themeShade from a style block so
    its colours are the CONCRETE fallback hex (e.g. header fill B6DDE8), rendering the same regardless of
    the destination document's theme (whose accentN may differ from the LI template's)."""
    s = re.sub(r'\s+w:theme(?:Fill|Color)="[^"]*"', '', style_xml)
    s = re.sub(r'\s+w:theme(?:FillTint|FillShade|Tint|Shade)="[^"]*"', '', s)
    return s

class Conformer:
    def __init__(self, template, path):
        self.template_path = template
        self.input_path = path
        self.parts = {}
        with zipfile.ZipFile(path) as z:
            for n in z.namelist(): self.parts[n] = z.read(n)
        with zipfile.ZipFile(template) as z:
            self.t_styles = z.read('word/styles.xml').decode('utf8'); self.t_num = z.read('word/numbering.xml').decode('utf8')
        # The house table style is Grid Table 4 / "LI Table". Take the template's own definition when it
        # carries one (the bundled template.dotx does), else the fallback constant; make it theme-INDEPENDENT
        # (concrete B6DDE8 teal, not themeFill=accent5) so the header renders teal even in a document whose
        # theme accent5 is a different colour. This is the definition the engine imports/stamps.
        m = re.search(r'<w:style\b[^>]*w:styleId="GridTable4".*?</w:style>', self.t_styles, re.S)
        self._house_table_style = _theme_independent_style(m.group(0) if m else GRIDTABLE4)
        if m:
            self.t_styles = self.t_styles.replace(m.group(0), self._house_table_style)
        else:
            self.t_styles = self.t_styles.replace('</w:styles>', self._house_table_style + '</w:styles>')
        self.doc = self.parts['word/document.xml'].decode('utf8')
        self.styles = self.parts['word/styles.xml'].decode('utf8'); self.num = self.parts['word/numbering.xml'].decode('utf8')
        # Pristine numbering/styles captured for resolution-based verification (numbering_report): passes
        # reassign self.num/self.styles, so holding the original strings costs nothing and lets us prove
        # no list's MEANING (number<->bullet, level) flipped except where a repair rule intended it.
        self._orig_num0 = self.num; self._orig_styles0 = self.styles
        self.fn = self.parts['word/footnotes.xml'].decode('utf8'); self.settings = self.parts['word/settings.xml'].decode('utf8')
        self.head, body, self.tail = re.search(r'(.*<w:body>)(.*)(</w:body>.*)', self.doc, re.S).groups()
        self.items = split_body(body)
        self.b0 = next(i for i, it in enumerate(self.items) if 'w:val="Heading1"' in it)
        # Pristine BODY snapshot for paragraph-reference verification (issue #1 R3): the definitions being
        # unchanged does not prove a paragraph still USES the same list, so we compare each paragraph's
        # actually-resolved numbering before vs after. Holding the original item strings costs nothing.
        self._orig_items0 = list(self.items); self._orig_b0 = self.b0
        self.log = []; self.judgment = []; self.audit = []
        self._table_notes = []       # tables the table pass could not conform reliably (nested/complex)
        self._house_repaired = {}    # styleId -> (before_fmt, after_fmt) for INTENDED house list repairs
        self._unresolved_imports = []  # template numIds whose numbering chain could not be resolved
        self._restyled = {}          # paragraph identity -> engine-assigned style (authorized reclassification)
        self._bullet_restored = {}   # paragraph identity -> style (numId 0 suppression removed to restore bullet)
        self._gen = 0                # mutation generation; a save verdict is tied to the gen it was computed at
        self._save_verdict = 'unset'; self._save_forced_review = False; self._save_gen = -1
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
    def set(self, i, x):
        self.items[self.b0 + i] = x
        self._gen = getattr(self, '_gen', 0) + 1     # a mutation invalidates any finalized save verdict
    def text(self, i): return text_of(self.item(i))
    def style(self, i):
        x = self.item(i)
        if x.startswith('<w:tbl'): return 'TABLE'
        m = re.search(r'<w:pStyle w:val="([^"]+)"', x); return m.group(1) if m else 'Normal'
    def set_style(self, i, st):
        x = self.item(i)
        # Record this engine-made reclassification for reference-verification authorization (issue #1 C): a
        # pStyle change the engine DECIDES is an approved before/after change; an EXTERNAL numbering change
        # (not recorded here) is never authorized by merely following its output style.
        rs = getattr(self, '_restyled', None)
        if rs is not None:
            pid = re.search(r'w14:paraId="([^"]+)"', x[:x.find('>') + 1])
            txt = self._fold_typography(' '.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', x)))
            key = pid.group(1) if pid else ('t:' + txt)
            rs[key] = st
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
            # Preserve a directly-centered, non-numbered line: it is a display element (an equation or a
            # centered note), not numbered body prose. Converting it to Numbered Paragraph would add an
            # unwanted list number AND strip its centering (the "formula added to a numbered list" defect).
            if not st.startswith('Heading') and not self.numpr(i) and '<w:jc w:val="center"/>' in self.ppr(i):
                continue
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

    @staticmethod
    def _is_bullet_fmt(level):
        """The format CATEGORY of a level: True = bullet, False = a number format (issue #1 C). A category
        flip (number<->bullet) is meaning-bearing and never a mere normalization."""
        return (level or {}).get('numFmt') == 'bullet'

    def _functioning_direct_numpr(self, x, st, graph):
        """The paragraph's direct <w:numPr> element to KEEP, or None to strip (issue #1 C). A direct numPr
        is removable ONLY when removal does not change the format CATEGORY: it is stripped for an equivalent
        or same-category (glyph/label) normalization to the style, and KEPT when removing it would leave the
        paragraph unnumbered OR would FLIP number<->bullet (a functioning direct list the style does not
        provide). Meaning-bearing direct instance information is preserved unless a specific repair replaces
        it."""
        pcur = re.sub(r'<w:pPrChange\b.*?</w:pPrChange>', '', x, flags=re.S)  # ignore historical snapshot
        dnpr = re.search(r'<w:numPr>.*?</w:numPr>', pcur, re.S)
        if not dnpr:
            return None
        nid = re.search(r'<w:numId w:val="([^"]+)"', dnpr.group(0))
        il = re.search(r'<w:ilvl w:val="([^"]+)"', dnpr.group(0))
        d_nid = nid.group(1) if nid else None
        d_il = il.group(1) if il else '0'
        style_np = graph.style_numpr(st)
        style_lv = graph.resolve_level(*style_np) if style_np else None
        if d_nid == '0':
            # explicit suppression: MEANINGFUL when the style would otherwise number the paragraph (keep
            # it, or stripping silently ADDS a number); redundant when the style has no list anyway.
            return dnpr.group(0) if style_lv is not None else None
        direct_lv = graph.resolve_level(d_nid, d_il) if d_nid else None
        if direct_lv is None:
            return None                                  # not a functioning list
        if style_lv is None:
            return dnpr.group(0)                          # style supplies no list -> keep (loss prevention)
        if self._is_bullet_fmt(direct_lv) != self._is_bullet_fmt(style_lv):
            return dnpr.group(0)                          # category flip -> keep the functioning direct list
        return None                                      # same category -> normalize to the style

    def _restore_suppressed_bullets(self):
        """Restore bullets on paragraphs styled as a house BULLET style whose bullet is CANCELLED by an
        explicit direct numId=0 (Claire's 'dysfunctional List Bullet' — e.g. a bulletized vessel list that
        renders as plain indented text). The style says 'bullet list item' but the numId=0 override
        suppresses it; strip that override so the style's bullet renders. Recorded for audited, authorized
        verification (`_bullet_restored`), never silent. A numPr that is a tracked change is left for review."""
        from conformer.numbering import NumberingGraph
        graph = NumberingGraph(self.num, self.styles)
        self._bullet_restored = getattr(self, '_bullet_restored', {})
        preserve = self.disposition == 'preserve'
        n = 0
        for i in range(self.n()):
            if not self.is_par(i):
                continue
            x = self.item(i)
            st = self.style(i)
            sr = graph.resolve_style(st)
            if not (sr.resolved and (sr.level or {}).get('numFmt') == 'bullet'):
                continue                                  # style is not a functioning house bullet
            ppr = re.search(r'<w:pPr>.*?</w:pPr>', x, re.S)
            cur = re.sub(r'<w:pPrChange\b.*?</w:pPrChange>', '', ppr.group(0), flags=re.S) if ppr else ''
            npr = re.search(r'<w:numPr>.*?</w:numPr>', cur, re.S)
            nid = re.search(r'<w:numId w:val="([^"]+)"', npr.group(0)) if npr else None
            if not nid or nid.group(1) != '0':
                continue                                  # only an explicit numId=0 suppression
            if preserve and re.search(r'<w:pPrChange|<w:ins\b|<w:del\b', x):
                continue                                  # tracked numbering edit — leave for review
            new = x.replace(npr.group(0), '', 1)          # drop the suppression; the style bullet applies
            if new == x:
                continue
            self.set(i, new)
            pid = re.search(r'w14:paraId="([^"]+)"', x[:x.find('>') + 1])
            key = pid.group(1) if pid else ('t:' + self._fold_typography(
                ' '.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', x))))
            self._bullet_restored[key] = st
            self.say('M', i, f'restored suppressed house bullet ({st}: removed numId 0 so the style bullet renders)')
            n += 1
        if n:
            self.say('M', -1, f'restored {n} suppressed house bullet(s)', 'bullets-restore')

    def strip_direct(self):
        from conformer.numbering import NumberingGraph
        _numgraph = NumberingGraph(self.num, self.styles)
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
                keep_numpr = self._functioning_direct_numpr(x, st, _numgraph)
                keep = []
                for tag, cx in children(m.group(1)):
                    ok = tag in ALLOWED_PPR or tag in ALLOWED_PPR_BY_STYLE.get(st, set())
                    if tag == 'jc' and 'w:val="center"' in cx:
                        ok = True                          # preserve centered display alignment (equations, centered notes)
                    if tag == 'numPr' and keep_numpr is not None:
                        ok = True; cx = keep_numpr        # preserve functioning numbering (e.g. a numbered heading)
                    if tag == 'spacing' and st == 'Heading1' and 'pageBreakBefore' not in m.group(1): ok = False
                    if tag == 'rPr': cx = '<w:rPr>' + ''.join(c for t2, c in children(re.search(r'<w:rPr>(.*?)</w:rPr>', cx, re.S).group(1) or '') if t2 in ('vanish',)) + '</w:rPr>' if re.search(r'<w:rPr>(.+?)</w:rPr>', cx, re.S) else ''
                    if ok: keep.append(cx)
                x = x.replace(m.group(0), '<w:pPr>' + ''.join(keep) + '</w:pPr>', 1)
            def fixrun(rm):
                r = rm.group(0); rp = re.search(r'<w:rPr>(.*?)</w:rPr>', r, re.S)
                if not rp: return r
                kept = keep_rpr_children(rp.group(1), is_fnref='FootnoteReference' in rp.group(1))
                return r.replace(rp.group(0), '<w:rPr>' + ''.join(kept) + '</w:rPr>' if kept else '', 1)
            x = re.sub(r'<w:r\b[^>]*>.*?</w:r>', fixrun, x, flags=re.S)
            if not preserve:   # these change the content stream (tab tokens / nbsp text)
                x = re.sub(r'(</w:pPr>)(?:<w:r>(?:<w:rPr>.*?</w:rPr>)?<w:tab/></w:r>)+', r'\1', x, flags=re.S)
                x = x.replace('\u00a0', ' ')
            self.set(i, x); i += 1

    # ---- colour + highlight (interactive) --------------------------------------------------------
    @staticmethod
    def _norm_color(v):
        """Normalise a run/style colour for comparison; black/auto/windowText all read as 'black'."""
        if v is None:
            return 'black'
        v = v.lower()
        return 'black' if v in ('000000', 'auto', 'windowtext', 'black') else v

    def _style_color_map(self):
        """styleId -> {'color', 'color_xml', 'basedOn'} from the STYLE-LEVEL rPr (the paragraph-mark rPr
        inside pPr is dropped first). color_xml keeps the FULL <w:color/> element so theme/tint/shade
        metadata is not lost when resolving inherited colour."""
        m = {}
        for sm in re.finditer(r'<w:style\b[^>]*w:styleId="([^"]+)".*?</w:style>', self.styles, re.S):
            body = sm.group(0)
            based = re.search(r'<w:basedOn w:val="([^"]+)"', body)
            body2 = re.sub(r'<w:pPr>.*?</w:pPr>', '', body, flags=re.S)
            col = re.search(r'<w:rPr>.*?(<w:color\b[^>]*/>)', body2, re.S)
            col_xml = col.group(1) if col else None
            val = re.search(r'w:val="([^"]+)"', col_xml).group(1) if col_xml else None
            m[sm.group(1)] = {'color': val, 'color_xml': col_xml,
                              'basedOn': based.group(1) if based else None}
        return m

    def _effective_style_color_el(self, style_id, cache):
        """The FULL <w:color/> element a paragraph inherits from its style, following basedOn; None when
        the chain defines none."""
        seen = set()
        sid = style_id
        while sid and sid not in seen:
            seen.add(sid)
            s = cache.get(sid)
            if not s:
                break
            if s.get('color_xml'):
                return s['color_xml']
            sid = s['basedOn']
        return None

    def _effective_style_color(self, style_id, cache):
        """The inherited run colour's w:val (for messages); None = default black."""
        el = self._effective_style_color_el(style_id, cache)
        m = re.search(r'w:val="([^"]+)"', el) if el else None
        return m.group(1) if m else None

    def _doc_default_color_el(self):
        """The FULL <w:color/> from docDefaults/rPrDefault — the lowest-priority inherited run colour. None
        only when docDefaults sets no colour; ONLY then is the effective default Word black. The absence of
        a colour on a style is NOT evidence of black when docDefaults defines one (issue #1 R6)."""
        styles = getattr(self, 'styles', '') or ''
        m = re.search(r'<w:docDefaults>.*?<w:rPrDefault>.*?<w:rPr>(.*?)</w:rPr>', styles, re.S)
        if not m:
            return None
        c = re.search(r'<w:color\b[^>]*/>', m.group(1))
        return c.group(0) if c else None

    @staticmethod
    def _is_theme_color(color_xml):
        return bool(color_xml) and ('themeColor' in color_xml or 'themeTint' in color_xml
                                    or 'themeShade' in color_xml)

    def _color_is_redundant(self, color_xml, rstyle, para_style, scmap):
        """A direct run colour is redundant only if removing it leaves the SAME effective colour. The
        effective-without colour is the character style's (if the run has one) else the paragraph style's,
        resolved through basedOn. A theme-backed colour on EITHER the direct property OR the inherited one
        is never treated as redundant \u2014 its resolved value is uncertain, so removing the direct colour
        could silently change the visible colour (issue #1 R6)."""
        if self._is_theme_color(color_xml):
            return False
        m = re.search(r'w:val="([^"]+)"', color_xml)
        direct = m.group(1) if m else None
        eff_el = self._effective_style_color_el(rstyle, scmap) if rstyle else None
        if eff_el is None:
            eff_el = self._effective_style_color_el(para_style, scmap)
        if eff_el is None:
            eff_el = self._doc_default_color_el()      # docDefaults default colour (issue #1 R6)
        if self._is_theme_color(eff_el):
            return False
        ev = re.search(r'w:val="([^"]+)"', eff_el) if eff_el else None
        return self._norm_color(direct) == self._norm_color(ev.group(1) if ev else None)

    def _color_highlight_calls(self):
        """Colour that leaves the SAME effective colour when removed (redundant) is stripped silently (no
        visible change \u2014 character style and theme dependencies considered). Colour that DEVIATES becomes
        a JUDGMENT CALL: accept \u2192 normalise to the effective style colour, skip/keep \u2192 leave. Each
        HIGHLIGHT is a judgment call: accept \u2192 remove, skip \u2192 keep. Formatting only (the content stream is
        unchanged); revised paragraphs and table cells are left to their own handling."""
        preserve = self.disposition == 'preserve'
        scmap = self._style_color_map()
        for i in range(self.n()):
            if not self.is_par(i):
                continue
            if preserve and self._para_has_revision(i):
                continue
            x = self.item(i)
            if '<w:color' not in x and '<w:highlight' not in x:
                continue
            st = self.style(i)
            if st == 'TableData':
                continue
            style_col = self._effective_style_color(st, scmap)
            sname = self.stname.get(st, st)

            def fix_run(rm):
                r = rm.group(0)
                rp = re.search(r'<w:rPr>(.*?)</w:rPr>', r, re.S)
                if not rp:
                    return r
                inner = rp.group(1)
                new_inner = inner
                rsm = re.search(r'<w:rStyle w:val="([^"]+)"', inner)
                rstyle = rsm.group(1) if rsm else None
                cm = re.search(r'<w:color\b[^>]*/>', new_inner)
                if cm:
                    cv = re.search(r'w:val="([^"]+)"', cm.group(0))
                    cv = cv.group(1) if cv else None
                    if self._color_is_redundant(cm.group(0), rstyle, st, scmap):
                        new_inner = new_inner.replace(cm.group(0), '', 1)         # redundant \u2192 silent strip
                    else:
                        # the colour the run would show if the direct one were removed (char style or para)
                        eff = (self._effective_style_color(rstyle, scmap) if rstyle else None) or style_col
                        jc = self._jcall('color', i,
                                         f'Text colour is #{cv}; the {sname} style is '
                                         f'{("#" + eff) if eff else "black"}.',
                                         'Normalise to the style colour', alternatives=['Keep this colour'])
                        if self._decision_for(jc) == 'accept':
                            new_inner = new_inner.replace(cm.group(0), '', 1)
                hm = re.search(r'<w:highlight\b[^>]*/>', new_inner)
                if hm:
                    hv = re.search(r'w:val="([^"]+)"', hm.group(0))
                    hv = hv.group(1) if hv else 'colour'
                    jc = self._jcall('highlight', i, f'{hv.title()} highlight.', 'Remove the highlight')
                    # A highlight is a REVIEW MARKER: keep it by default; remove ONLY on an explicit accept.
                    # (self.decisions is None during analyze / a direct run — default-accept must not strip it.)
                    if self.decisions is not None and self.decisions.get(jc.id) == 'accept':
                        new_inner = new_inner.replace(hm.group(0), '', 1)
                if new_inner == inner:
                    return r
                return r.replace(rp.group(0), '<w:rPr>' + new_inner + '</w:rPr>' if new_inner else '', 1)

            nx = re.sub(r'<w:r\b[^>]*>.*?</w:r>', fix_run, x, flags=re.S)
            if nx != x:
                self.set(i, nx)

    @staticmethod
    def _filter_table_rpr(inner):
        """Filter a table run's rPr down to the properties the house style permits: keep style/bold/italic/
        colour, and keep a DIRECT size only when it is <= 11pt (sz 22). An intentional small body font is
        preserved so the reviewer gets the normalize-to-11pt judgment call (GPT audit F4: the clean pipeline
        used to strip every size, so a small-font table silently became 11pt and was never offered); an
        oversized run drops its size so Table Data's 11pt applies. The header row's size is stripped
        separately (hr2 below), so this keep never blocks the 10pt header."""
        if not inner:
            return ''
        keep = []
        for t2, cx in children(inner):
            if t2 in ('rStyle', 'b', 'bCs', 'i', 'iCs', 'color'):
                keep.append(cx)
            elif t2 in ('sz', 'szCs'):
                m = re.search(r'w:val="(\d+)"', cx)
                if m and int(m.group(1)) <= 22:
                    keep.append(cx)
        return '<w:rPr>' + ''.join(keep) + '</w:rPr>'

    def fix_tables(self):
        self._ensure_table_header_style()
        for i in range(self.n()):
            x = self.item(i)
            if not x.startswith('<w:tbl'): continue
            x = re.sub(r'<w:tblBorders>.*?</w:tblBorders>|<w:tcBorders>.*?</w:tcBorders>|<w:shd [^>]*/>', '', x, flags=re.S)
            if '<w:tblStyle' not in x: x = x.replace('<w:tblPr>', '<w:tblPr><w:tblStyle w:val="GridTable4"/>', 1)
            else: x = re.sub(r'<w:tblStyle w:val="[^"]+"/>', '<w:tblStyle w:val="GridTable4"/>', x)
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
            x = re.sub(r'<w:rPr>(.*?)</w:rPr>', lambda r: self._filter_table_rpr(r.group(1)), x, flags=re.S)
            first_row = re.search(r'<w:tr\b.*?</w:tr>', x, re.S).group(0)
            if '<w:tblHeader/>' not in first_row:
                nfr = (first_row.replace('<w:trPr>', '<w:trPr><w:tblHeader/>', 1) if '<w:trPr>' in first_row
                       else re.sub(r'(<w:tr\b[^>]*>)', r'\1<w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>', first_row, count=1))
                x = x.replace(first_row, nfr, 1)
            # Header row -> 10pt bold Table Header style (a paragraph style overrides the Grid Table 4
            # firstRow size, so header cells cannot get 10pt from the table-style conditional alone).
            hr = re.search(r'<w:tr\b.*?</w:tr>', x, re.S).group(0)
            hr2 = hr.replace('<w:pStyle w:val="TableData"/>', '<w:pStyle w:val="TableHeader"/>')
            hr2 = re.sub(r'<w:szCs w:val="\d+"/>', '', hr2)
            hr2 = re.sub(r'<w:sz w:val="\d+"/>', '', hr2)
            if hr2 != hr:
                x = x.replace(hr, hr2, 1)
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
            # Property policy: normalise house-controlled appearance but PRESERVE meaning-bearing/review
            # formatting so a subscript (e.g. H2S), an ordinal superscript or a highlight in a footnote
            # survives — matching the body-text policy via the shared filter.
            f = re.sub(r'<w:rPr>(.*?)</w:rPr>',
                       lambda r: '<w:rPr>' + ''.join(keep_rpr_children(r.group(1))) + '</w:rPr>', f, flags=re.S)
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
            # An Excerpt/Quote is VERBATIM (§6) — typography must not alter its interior characters
            # (e.g. an en dash in a quoted "2017-2019") (GPT audit F3).
            if self.style(i) == 'ExcerptorQuote': continue
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
            seg = re.sub(r'(\d)["”]', r'\1-inch', seg)   # spell out a body-prose inch measurement (D-2)
            seg = _HOUSE_LOWER_RE.sub(lambda m: m.group(1) + m.group(2) + m.group(3).lower(), seg)
            seg = _HOUSE_CAP_RE.sub(lambda m: m.group(1) + m.group(2) + m.group(3).capitalize(), seg)
            seg = _BRIT_RE.sub(_brit_case, seg)
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
        if self._skip('update-fields'):
            return
        if not self.audit:
            return
        if '<w:updateFields' in self.settings:
            self.settings = re.sub(r'<w:updateFields[^>]*/>', '<w:updateFields w:val="true"/>', self.settings, count=1)
        else:
            self.settings = re.sub(r'(<w:settings\b[^>]*>)', r'\1<w:updateFields w:val="true"/>', self.settings, count=1)
        self.say('M', -1, f'updateFields=true (audit found {len(self.audit)} issue(s)): Word will refresh numbering and the Table of Figures on open', 'update-fields')

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

    _HEADING_LEVEL = {f'Heading{n}': n for n in range(1, 7)}
    _NP_SUBLEVEL = {'NumberedParagraphL1': 1, 'NumberedParagraphL2': 2,
                    'NumberedParagraphL3': 3, 'NumberedParagraphL4': 4}

    def audit_headings(self):
        """§3/§4 numbering STRUCTURE (advisory; Word computes the actual 1 / 1.1 / 1.1.1 digits from the
        linked heading list, so this catches the structural CAUSE of a wrong/duplicated section number):
          - a heading that SKIPS a level (e.g. a Heading 3 directly under a Heading 1, with no Heading 2
            between) — the sub-numbering then can't increment correctly (§3);
          - a numbered-paragraph sublist that starts above L1 or jumps a sublevel ("do not start with 'a'
            rather than '1'", §4).
        Findings append to self.audit."""
        findings = []
        last_h = 0
        for i in range(self.n()):
            if not self.is_par(i):
                continue
            st = self.style(i)
            if st in self._HEADING_LEVEL:
                lvl = self._HEADING_LEVEL[st]
                if last_h and lvl > last_h + 1:
                    findings.append(('heading-skip', f'{st} follows a Heading {last_h}: heading level(s) '
                                     f'{last_h + 1}..{lvl - 1} are skipped, so §3 sub-numbering will be off: '
                                     f'{self.text(i).strip()[:40]!r}'))
                last_h = lvl
        prev_sub = 0
        for i in range(self.n()):
            if not self.is_par(i):
                continue
            st = self.style(i)
            if st in self._NP_SUBLEVEL:
                cur = self._NP_SUBLEVEL[st]
                if cur > prev_sub + 1:
                    findings.append(('sublevel-skip', f'{st} starts a numbered-paragraph sublist above L1 or '
                                     f'skips a level (§4: do not start at "a" rather than "1"): '
                                     f'{self.text(i).strip()[:40]!r}'))
                prev_sub = cur
            elif st == 'NumberedParagraph' or st in self._HEADING_LEVEL:
                prev_sub = 0
        self.audit = (self.audit or []) + findings
        if findings:
            for lvl, msg in findings:
                self.say('J', -1, f'HEADING AUDIT [{lvl}]: {msg}')
        else:
            self.say('M', -1, 'heading audit OK: heading levels and numbered-paragraph sublevels are '
                     'sequential (no skipped levels)')
        return findings

    @staticmethod
    def _caption_basis(x):
        """The heading level a caption's numbering is based on = the STYLEREF field's level. None if the
        caption is not an auto-number (STYLEREF/SEQ) field."""
        m = re.search(r'STYLEREF\s+(\d+)', x)
        return int(m.group(1)) if m else None

    def audit_captions(self):
        """Verify Table AND Figure captions against guideline §8.6 (advisory; feeds the field refresh):
          (a) each kind's numbering BASIS is a single, consistent Heading level, and that level is Heading 1
              or Heading 2 (the only sanctioned bases) — flagged, never auto-renumbered (D-1);
          (b) the two kinds do not use different bases;
          (c) per-section cached SEQ results are sequential (1,2,3,…) — a gap/duplicate is a STALE field
              that will renumber on update.
        audit_figures already covers Figure sequence + Table-of-Figures matching; this adds the Table
        captions (which audit_figures skips) and the basis checks, and APPENDS to self.audit so the field
        refresh (force_field_update) is armed when anything drifted."""
        from collections import defaultdict
        caps = {'Table': [], 'Figure': []}
        for i in range(self.n()):
            if not self.is_par(i) or self.style(i) != 'Caption':
                continue
            x = self.item(i); t = self.text(i).strip()
            m = re.match(r'(Table|Figure)\b', t)
            if not m:
                continue
            kind = m.group(1)
            res = self._field_results(x)
            caps[kind].append({'i': i, 'text': t, 'basis': self._caption_basis(x),
                               'fielded': 'SEQ ' in x, 'csec': res[0] if res else '',
                               'cseq': res[1] if len(res) > 1 else ''})
        findings = []
        kind_basis = {}
        for kind, lst in caps.items():
            if not lst:
                continue
            static = [c for c in lst if not c['fielded']]
            if static:
                findings.append(('not-fielded', f'{len(static)} {kind} caption(s) are not auto-number fields '
                                 '(they will not renumber): e.g. ' + repr(static[0]['text'][:40])))
            bases = sorted({c['basis'] for c in lst if c['basis'] is not None})
            kind_basis[kind] = bases
            if len(bases) > 1:
                findings.append(('basis-inconsistent', f'{kind} captions use MULTIPLE numbering bases '
                                 f'(Heading levels {bases}); §8.6 requires ONE consistent basis — review'))
            for b in bases:
                if b not in (1, 2):
                    findings.append(('basis-not-h1h2', f'{kind} captions are based on Heading {b}; §8.6 '
                                     'sanctions only Heading 1 or Heading 2 — review/re-base (not auto-changed)'))
            bysec = defaultdict(list)
            for c in lst:
                if c['fielded'] and c['csec']:
                    bysec[c['csec']].append(c['cseq'])
            for sec, seqs in bysec.items():
                nums = [int(s) for s in seqs if s.isdigit()]
                if nums and nums != list(range(1, len(nums) + 1)):
                    findings.append(('seq-stale', f'{kind} numbers in section {sec} are not sequential '
                                     f'(cached {nums}) — stale field(s); will renumber on update'))
        allb = sorted({b for bs in kind_basis.values() for b in bs})
        if len(kind_basis) > 1 and len(allb) > 1:
            findings.append(('basis-cross-kind', f'Table and Figure captions use DIFFERENT bases '
                             f'({kind_basis}); §8.6 wants a consistent basis — review'))
        self.audit = (self.audit or []) + findings
        if findings:
            for lvl, msg in findings:
                self.say('J', -1, f'CAPTION AUDIT [{lvl}]: {msg}')
        else:
            self.say('M', -1, 'caption audit OK: Table/Figure numbering bases consistent (Heading 1/2) and '
                     'per-section numbering sequential')
        return findings

    def _ensure_crossref_style(self):
        """Import the 'Cross Reference' character style if the document lacks it (so the applied rStyle
        resolves)."""
        if re.search(r'<w:style\b[^>]*w:styleId="CrossReference"', self.styles):
            return
        m = re.search(r'<w:style\b[^>]*w:styleId="CrossReference".*?</w:style>', self.t_styles, re.S)
        style = m.group(0) if m else ('<w:style w:type="character" w:customStyle="1" '
                                      'w:styleId="CrossReference"><w:name w:val="Cross Reference"/></w:style>')
        self.styles = self.styles.replace('</w:styles>', style + '</w:styles>', 1)

    _CROSSREF_FIELD = re.compile(
        r'(<w:instrText[^>]*>\s*REF\b.*?<w:fldChar w:fldCharType="separate"/>\s*</w:r>)'
        r'(.*?)(<w:r\b[^>]*>\s*<w:fldChar w:fldCharType="end"/>\s*</w:r>)', re.S)

    def _apply_crossref_style(self, x):
        """Add the 'Cross Reference' character style to the DISPLAY runs of each REF (cross-reference)
        field in x. Formatting only — the display TEXT is unchanged. Returns (xml, styled_runs, broken)."""
        styled = [0]; broken = [0]

        def one_run(rm):
            r = rm.group(0)
            if '<w:t' not in r or 'w:val="CrossReference"' in r:
                return r
            styled[0] += 1
            if '<w:rPr>' in r:
                return r.replace('<w:rPr>', '<w:rPr><w:rStyle w:val="CrossReference"/>', 1)
            return re.sub(r'(<w:r\b[^>]*>)',
                          lambda m: m.group(1) + '<w:rPr><w:rStyle w:val="CrossReference"/></w:rPr>', r, count=1)

        def one_field(fm):
            pre, disp, post = fm.group(1), fm.group(2), fm.group(3)
            if 'Reference source not found' in disp:
                broken[0] += 1
            return pre + re.sub(r'<w:r\b[^>]*>.*?</w:r>', one_run, disp, flags=re.S) + post

        return self._CROSSREF_FIELD.sub(one_field, x), styled[0], broken[0]

    def _style_crossreferences(self):
        """§9 (P1): give every cross-reference (REF) field's display runs the 'Cross Reference' character
        style — applied to EXISTING fields, not only ones the engine builds from literal text (Warhoe:
        515/515 REF fields lacked it though the style is defined). A broken reference (cached "Error!
        Reference source not found") is flagged. Formatting-only: the display text is unchanged, revision
        content is masked, so the content-stream gate holds."""
        if self._skip('crossref'):
            return 0, 0
        self._ensure_crossref_style()
        styled = broken = 0
        for i in range(self.n()):
            x = self.item(i)
            if 'REF ' not in x or 'fldChar' not in x:
                continue
            masked, masks = self._mask_revisions(x) if self.disposition == 'preserve' else (x, {})
            nx, s, b = self._apply_crossref_style(masked)
            nx = self._unmask(nx, masks)
            if nx != x:
                self.set(i, nx)
            styled += s; broken += b
        if broken:
            self.audit = (self.audit or []) + [('xref-broken', f'{broken} cross-reference(s) display '
                          '"Error! Reference source not found" (broken target) — review')]
            self.say('J', -1, f'CROSS-REF AUDIT: {broken} broken cross-reference(s)')
        if styled:
            self.say('M', -1, f'applied the Cross Reference character style to {styled} cross-reference run(s)', 'crossref')
        return styled, broken

    def audit_crossref_targets(self):
        """§9 verification: flag a REF cross-reference whose target bookmark is not present in the document
        (a broken reference — it may not yet display the 'Error!' text if its cache is stale). Advisory."""
        # scan the body AND the footnotes so a reference to a footnote bookmark is not a false positive
        joined = ''.join(self.items) + getattr(self, 'fn', '') + getattr(self, 'head', '') + getattr(self, 'tail', '')
        names = set(re.findall(r'<w:bookmarkStart[^>]*w:name="([^"]+)"', joined))
        targets = re.findall(r'<w:instrText[^>]*>\s*REF\s+(\S+)', joined)
        missing = sorted({t for t in targets if t not in names})
        if missing:
            self.audit = (self.audit or []) + [('xref-target-missing', f'{len(missing)} cross-reference(s) '
                          f'point to a bookmark not in the document (broken): e.g. {missing[0]} — review')]
            self.say('J', -1, f'CROSS-REF AUDIT: {len(missing)} reference(s) target a missing bookmark')
        return missing

    def _finalize_verdict(self, force=False):
        """Compute (or reuse) the conformance verdict tied to the CURRENT mutation generation (issue #1 E).
        A later edit bumps self._gen and invalidates a stale verdict. A verification exception is UNKNOWN
        (None), never an inherited clean claim. Returns the verdict (dict or None)."""
        if (not force and self._save_verdict != 'unset' and self._save_gen == getattr(self, '_gen', 0)):
            return self._save_verdict
        try:
            self._save_verdict = self.conformance_status()
        except Exception:
            self._save_verdict = None                # unknown / unverified
        self._save_forced_review = (self._save_verdict is None
                                    or not self._save_verdict.get('clean', False))
        self._save_gen = getattr(self, '_gen', 0)
        return self._save_verdict

    def finalize_save(self, review_only=False):
        """The guarded save entry point (issue #1 E): finalize the verdict for the current state and REQUIRE
        an explicit review-only opt-in to proceed when it is not clean or is unknown. Returns the verdict."""
        v = self._finalize_verdict(force=True)
        if self._save_forced_review and not review_only:
            raise ReviewOnlyRequired(self._artifact_label(v, True))
        return v

    def save(self, path):
        # Every save path stamps the artifact's document-status from the ACTUAL verdict for the CURRENT state
        # (issue #1 E): a direct run();save() no longer inherits a stale 'conformed & verified' label; a
        # verification exception yields an unknown/unverified label, never a clean claim.
        self._finalize_verdict()
        self._stamp_status(self._artifact_label(self._save_verdict, self._save_forced_review))
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
        led = self.revision_ledger
        # F2: ONE history-preserving path handles EVERY kind of tracked revision — content revisions
        # (insert/delete/move) AND formatting-only revisions (pPrChange/rPrChange). The legacy clean path
        # REVERTS formatting revisions (revert_tracked_formatting), silently destroying that review history,
        # so it now runs only for a genuinely revision-free document. (Comments do not force this path: the
        # clean path preserves comment anchors, and routing comment-only reports here would skip content-
        # stream fixes like the footnote tab; the preservation gate still governs any doc that does land in
        # the preserving path.)
        if led.has_revisions() and self.disposition in (None, 'preserve'):
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
        self.fix_headings(); self.fix_levels(); self._restore_suppressed_bullets(); self.strip_direct(); self.fix_tables(); self.fix_figures()
        self.fix_footnotes(); self.rebuild_fields(); self._style_crossreferences()
        self._emit('type')
        self.typography(); self.house_style(); self.fix_sections(); self.replace_parts()
        # replace_parts() reset styles to the template, which does NOT define the engine-added TableHeader
        # style that fix_tables() stamped on header cells — re-inject it so header paragraphs do not
        # reference a missing style (which Word renders at the default 12pt) (GPT audit F1).
        self._ensure_table_header_style()
        # the excerpt-quote and table-body offers run in BOTH pipelines, not only the preserving one, so the
        # same report gets the same feature offers regardless of whether an unrelated revision exists (F2/F4).
        self._strip_excerpt_quotes_preserving()
        self._offer_table_body_normalization()
        # colour/highlight AFTER replace_parts so redundancy is judged against the FINAL (template) styles
        self._color_highlight_calls()
        self.audit_figures(); self.audit_captions(); self.audit_headings()
        self.audit_crossref_targets(); self.force_field_update()

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
            (self._restore_suppressed_bullets, 'stream', 'structure'),
            (self._heading_caps_preserving, 'stream', 'structure'), (self.strip_direct, 'stream', 'structure'),
            (self.fix_footnotes, 'stream', 'structure'), (self.fix_sections, 'stream', 'structure'),
            (self._color_highlight_calls, 'stream', 'structure'),
            (self._style_crossreferences, 'stream', 'structure'),
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
        self._strip_excerpt_quotes_preserving()   # §5 remove redundant surrounding quotes (judgment call)
        self._offer_table_body_normalization()     # small table body fonts: keep by default, offer 11pt
        # Interactive ASK structural changes (display-preserving, per-instance JudgmentCalls).
        # #8 first (Claire's explicit need): caption fielding then cross-reference rebuild.
        self._emit('refs')
        self._caption_fields_preserving()   # #8a
        self._xrefs_preserving()            # #8b
        self._split_headings_preserving()   # #6
        self._extract_images_preserving()   # #5
        self._drop_empty_columns_preserving()  # #7
        self.audit_figures()
        self.audit_captions()               # §8.6 Table+Figure basis + per-section sequence (P1)
        self.audit_headings()               # §3/§4 heading + sublevel level-skip structure (P1)
        self.audit_crossref_targets()       # §9 flag REF fields whose target bookmark is missing (P1)
        self.force_field_update()           # arm Word's refresh when the audit found caption/figure drift
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

    @staticmethod
    def _single_enclosing_double_quote(text):
        """True only when a DOUBLE quotation mark opens the excerpt, its MATCHING close ends it, and the
        pair encloses the WHOLE text (the outer quote never closes early and re-opens). Rejects an
        opens-only quote (nested inner close at the end), two separate quotations, and single-quote pairs
        (left alone). Prevents mangling mismatched/multi-quote excerpts (GPT audit F8)."""
        t = text.strip()
        if len(t) < 3:
            return False
        if t[0] == '"' and t[-1] == '"':
            return t.count('"') == 2                     # straight: exactly the one enclosing pair
        if t[0] == '“' and t[-1] == '”':       # smart: the outer pair must span the whole text
            depth = 0
            for idx, ch in enumerate(t):
                if ch == '“':
                    depth += 1
                elif ch == '”':
                    depth -= 1
                    if depth < 0 or (depth == 0 and idx != len(t) - 1):
                        return False                     # closed before the end -> not a single enclosure
            return depth == 0
        return False

    @staticmethod
    def _boundary_strip_ok(before, after):
        """The accepted output must equal the input minus EXACTLY the two outer boundary characters (the
        first and last non-space characters). Guards against empty leading/trailing runs or fields causing
        only one boundary to be removed (GPT audit F8)."""
        l = len(before) - len(before.lstrip())
        r = len(before.rstrip()) - 1
        if r <= l:
            return False
        return after == before[:l] + before[l + 1:r] + before[r + 1:]

    def _strip_excerpt_quotes_preserving(self):
        """§6: an excerpt (block quote) is set off by its own style, so surrounding quotation marks are
        redundant and are removed. A self-contained excerpt whose outer DOUBLE-quote pair encloses the
        whole text is offered as a JUDGMENT CALL (default: remove the outer pair). Only CLEAN excerpts
        (no tracked change, comment or bookmark) are touched; only the two outer boundary characters are
        removed and the result is checked against that exact invariant (else that paragraph is reverted).
        An opens-only quote, two separate quotations, or a single-quote pair are left alone. A ledger
        backstop rolls the whole pass back if preservation slips."""
        snap = self._snapshot()
        changed = 0
        for i in range(self.n()):
            if not (self.is_par(i) and self.style(i) == 'ExcerptorQuote'):
                continue
            if self._para_has_marker(i):
                continue
            before = self.text(i) or ''
            if self._single_enclosing_double_quote(before):
                msg = 'excerpt wrapped in quotation marks — remove them (block quote sets off the quote, §6)'
                jc = self._jcall('excerpt-quotes', i, msg, 'Remove surrounding quotation marks')
                self.say('J', i, msg)
                if self._decision_for(jc) == 'accept':
                    before_item = self.item(i)
                    self._strip_leading_quote(i)
                    self._strip_trailing_quote(i)
                    if self._boundary_strip_ok(before, self.text(i) or ''):
                        changed += 1
                    else:
                        self.set(i, before_item)         # strip did not match the invariant — revert this para
        if changed:
            clean, _ = self.verify_preservation()
            if not clean:
                self._restore(snap)
                self.exceptions.append(('strip_excerpt_quotes', 'ledger backstop tripped (rolled back)'))

    def _table_body_is_small(self, tbl_xml):
        """True when a table's BODY is UNIFORMLY smaller than the house 11pt: every body text run carries a
        direct size below sz 22, and none inherits 11pt or is >= 22 (GPT audit F4: one small run among many
        11pt-inheriting runs is NOT a small table). Header row excluded."""
        rows = re.findall(r'<w:tr\b.*?</w:tr>', tbl_xml, re.S)
        if len(rows) < 2:
            return False
        small = other = 0
        for r in rows[1:]:
            r = re.sub(r'<w:rPrChange\b.*?</w:rPrChange>', '', r, flags=re.S)   # current formatting only
            for run in re.findall(r'<w:r\b.*?</w:r>', r, re.S):
                if '<w:t' not in run:
                    continue                                                    # only text-bearing runs
                m = re.search(r'<w:sz w:val="(\d+)"/>', run)
                if m and int(m.group(1)) < 22:
                    small += 1
                else:
                    other += 1                                                  # sz>=22 or inherits 11pt
        return small > 0 and other == 0

    def _normalize_table_body_to_11pt(self, i):
        """Strip direct run sizes from a table's BODY rows so the Table Data 11pt applies — reaching THROUGH
        tracked wrappers (content=False masks only the *Change records, so each old snapshot stays
        byte-exact) so the normalization also covers sizes inside a tracked insertion (GPT audit F4). Header
        row (Table Header 10pt) is left untouched."""
        x = self.item(i)
        rows = re.findall(r'<w:tr\b.*?</w:tr>', x, re.S)
        for r in rows[1:]:
            masked, masks = self._mask_revisions(r, content=False)
            masked = re.sub(r'<w:sz w:val="\d+"/>', '', masked)
            masked = re.sub(r'<w:szCs w:val="\d+"/>', '', masked)
            nr = self._unmask(masked, masks)
            if nr != r:
                x = x.replace(r, nr, 1)
        if x != self.item(i):
            self.set(i, x)

    def _offer_table_body_normalization(self):
        """§ tables: a table whose BODY text is a smaller font (8–10.5pt) is usually intentional — dense
        schedule data fit to the page — so it is KEPT by default. Surface ONE class-level judgment call so
        the reviewer can choose to normalize all such tables to the house 11pt if they prefer. Default:
        keep. Only clean (untracked) cells are normalized on accept; a ledger backstop rolls back."""
        small = [i for i in range(self.n())
                 if self.item(i).startswith('<w:tbl') and self._table_body_is_small(self.item(i))]
        if not small:
            return
        msg = (f'{len(small)} table(s) use a smaller body font (8–10.5pt) — likely intentional to fit dense '
               'data. Kept as-is by default; choose to normalize them all to the house 11pt.')
        jc = self._jcall('table-body-size', small[0], msg, 'Keep the smaller table fonts',
                         alternatives=['Normalize all table bodies to 11pt'])
        self.say('J', small[0], msg)
        if self._decision_for(jc).startswith('change:'):
            snap = self._snapshot()
            for i in small:
                self._normalize_table_body_to_11pt(i)
            clean, _ = self.verify_preservation()
            if not clean:
                self._restore(snap)
                self.exceptions.append(('normalize_table_body', 'ledger backstop tripped (rolled back)'))

    def _strip_leading_quote(self, i):
        """Remove one leading quotation mark (after any leading whitespace) from the paragraph's first text run."""
        x = self.item(i)
        m = re.search(r'(<w:t[^>]*>)([^<]*)(</w:t>)', x)
        if not m:
            return
        new = re.sub(r'^(\s*)["“‘]', r'\1', m.group(2), count=1)
        if new != m.group(2):
            self.set(i, x[:m.start()] + m.group(1) + new + m.group(3) + x[m.end():])

    def _strip_trailing_quote(self, i):
        """Remove one trailing quotation mark (before any trailing whitespace) from the paragraph's last text run."""
        x = self.item(i)
        ms = list(re.finditer(r'(<w:t[^>]*>)([^<]*)(</w:t>)', x))
        if not ms:
            return
        m = ms[-1]
        new = re.sub(r'["”’](\s*)$', r'\1', m.group(2), count=1)
        if new != m.group(2):
            self.set(i, x[:m.start()] + m.group(1) + new + m.group(3) + x[m.end():])

    @staticmethod
    def _text_is_upper(t):
        letters = [c for c in t if c.isalpha()]
        return bool(letters) and all(c.isupper() for c in letters)

    def _heading_caps_preserving(self):
        """Heading capitalization policy (guideline §3, P0-2): H1 & H2 are ALL CAPS via TRUE typed capitals,
        with the documented exception that H2 may use initial caps when applied CONSISTENTLY (a long-title
        report-wide choice). The engine NEVER adds a display <w:caps/> attribute: §3 warns it does not
        propagate to the Table of Contents or PDF bookmarks, so it would desync the body from the TOC. In
        the review-preserving pipeline this pass does not force a text change (a heading recasing would alter
        the content stream); it FLAGS non-conforming casing for human correction:
          - a Heading 1 not in ALL CAPS;
          - Heading 2 casing that is INCONSISTENT (some all-caps, some initial-caps) — the exception has to
            be applied consistently. Consistently-initial-caps H2s are the honored exception (no flag)."""
        h2 = [(i, self.text(i).strip()) for i in range(self.n())
              if self.is_par(i) and self.style(i) == 'Heading2' and self.text(i).strip()]
        h2_caps = [i for i, t in h2 if self._text_is_upper(t)]
        h2_initial = [i for i, t in h2 if not self._text_is_upper(t)]
        if h2_caps and h2_initial:
            self.say('J', h2_initial[0], f'Heading 2 capitalization is INCONSISTENT ({len(h2_caps)} all '
                     f'caps, {len(h2_initial)} initial caps): the initial-caps exception must be applied '
                     'consistently throughout (guideline §3) — review')
        for i in range(self.n()):
            if self.is_par(i) and self.style(i) == 'Heading1':
                t = self.text(i).strip()
                if t and not self._text_is_upper(t):
                    self.say('J', i, 'Heading 1 is not in ALL CAPS (guideline §3: Headings 1 and 2 in all '
                             'caps) — review')

    @staticmethod
    def _keep_numpr(old, new):
        """Return the template style `new` but carrying the document style `old`'s own <w:numPr> (its
        list-numbering association). numId values are document-local, so importing the template's numPr
        would point the style at a different (often bullet) list. If the doc style had no numbering, the
        template's numPr is dropped so a non-list style is never turned into a list."""
        om = re.search(r'<w:numPr>.*?</w:numPr>', old, re.S)
        nm = re.search(r'<w:numPr>.*?</w:numPr>', new, re.S)
        if nm:
            return new[:nm.start()] + (om.group(0) if om else '') + new[nm.end():]
        if om:
            if '<w:pPr>' in new:
                return new.replace('<w:pPr>', '<w:pPr>' + om.group(0), 1)
            # no pPr in the template def — insert one carrying the doc's numbering
            sm = re.search(r'<w:style\b[^>]*>', new)
            if sm:
                return new[:sm.end()] + '<w:pPr>' + om.group(0) + '</w:pPr>' + new[sm.end():]
        return new

    def _set_style_numpr(self, sid, numId, ilvl):
        """Set/replace a style's numbering association (its <w:numPr>) in self.styles."""
        npr = f'<w:numPr><w:ilvl w:val="{ilvl}"/><w:numId w:val="{numId}"/></w:numPr>'
        def repl(m):
            body = m.group(0)
            if '<w:numPr>' in body:
                return re.sub(r'<w:numPr>.*?</w:numPr>', npr, body, count=1, flags=re.S)
            if '<w:pPr>' in body:
                return body.replace('<w:pPr>', '<w:pPr>' + npr, 1)
            sm = re.search(r'<w:style\b[^>]*>', body)
            return (body[:sm.end()] + '<w:pPr>' + npr + '</w:pPr>' + body[sm.end():]) if sm else body
        self.styles = re.sub(r'<w:style\b[^>]*w:styleId="%s".*?</w:style>' % re.escape(sid),
                             repl, self.styles, count=1, flags=re.S)

    @staticmethod
    def _esc_attr(s):
        return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

    @classmethod
    def _overlay_level(cls, lvl, numFmt, lvlText, rfonts):
        """Overlay the approved house numFmt / lvlText (and the glyph's symbol rFonts) onto one <w:lvl>,
        replacing those children in place and leaving start / lvlRestart / pStyle / overrides intact (B)."""
        if numFmt is not None:
            el = f'<w:numFmt w:val="{cls._esc_attr(numFmt)}"/>'
            if re.search(r'<w:numFmt\b[^>]*/>', lvl):
                lvl = re.sub(r'<w:numFmt\b[^>]*/>', el, lvl, count=1)
            else:
                m = re.search(r'<w:start\b[^>]*/>', lvl) or re.search(r'<w:lvl\b[^>]*>', lvl)
                lvl = lvl[:m.end()] + el + lvl[m.end():]
        if lvlText is not None:
            el = f'<w:lvlText w:val="{cls._esc_attr(lvlText)}"/>'
            if re.search(r'<w:lvlText\b[^>]*/>', lvl):
                lvl = re.sub(r'<w:lvlText\b[^>]*/>', el, lvl, count=1)
            else:
                m = re.search(r'<w:numFmt\b[^>]*/>', lvl) or re.search(r'<w:lvl\b[^>]*>', lvl)
                lvl = lvl[:m.end()] + el + lvl[m.end():]
        if rfonts:
            rpr = re.search(r'<w:rPr>.*?</w:rPr>', lvl, re.S)
            if rpr:
                body = rpr.group(0)
                nb = (re.sub(r'<w:rFonts\b[^>]*/>', rfonts, body, count=1)
                      if re.search(r'<w:rFonts\b[^>]*/>', body) else body.replace('<w:rPr>', '<w:rPr>' + rfonts, 1))
                lvl = lvl.replace(body, nb, 1)
            else:
                lvl = lvl.replace('</w:lvl>', f'<w:rPr>{rfonts}</w:rPr></w:lvl>', 1)
        return lvl

    def _repair_styles(self):
        """Fix corrupt LI style definitions (Claire's 'List Bullet dysfunctional' / 'table style
        corrupted'): overwrite the document's definition of any style the template defines with the
        template's correct definition, and add template styles the document lacks. Keep doc-only
        styles so revised paragraphs still resolve, and never touch docDefaults/theme. This is
        styles.xml only — orthogonal to every tracked change in the body."""
        if self._skip('styles-repair'):
            return
        from collections import defaultdict
        from conformer.numbering import NumberingGraph
        tgraph = NumberingGraph(self.t_num, self.t_styles)
        tmpl = {m.group(1): m.group(0) for m in
                re.finditer(r'<w:style\b[^>]*w:styleId="([^"]+)".*?</w:style>', self.t_styles, re.S)}
        fixed = [0]
        def repl(m):
            orig = m.group(0)
            sid = re.search(r'w:styleId="([^"]+)"', orig).group(1)
            if sid in tmpl and tmpl[sid] != orig:
                fixed[0] += 1
                # Repair the style's FORMATTING from the template, but keep the document's own numbering
                # association (containment): template numIds index the template's numbering.xml.
                return self._keep_numpr(orig, tmpl[sid])
            return orig
        self.styles = re.sub(r'<w:style\b[^>]*w:styleId="([^"]+)".*?</w:style>', repl,
                             self.styles, flags=re.S)

        # Graph-aware numbering IMPORT (replaces the old "append every template def whose numeric id is
        # missing" merge — the collision that reformatted decimal lists as bullets). We import a template
        # list ONLY as a dependency of a style we are adding, and we import its COMPLETE definition under
        # FRESHLY ALLOCATED ids, rewriting exactly that import's references. Existing document lists keep
        # their own ids and meaning untouched.
        dgraph = NumberingGraph(self.num, self.styles)
        alloc = {'num': max(dgraph.used_num_ids() | {0}) + 1,
                 'abs': max(dgraph.used_abstract_ids() | {0}) + 1}
        imported = {}          # template numId -> new document numId (import each list once)
        new_defs = []

        def _lvl_set(lvl, tag, value):
            """Set/replace/remove a simple <w:tag w:val=…/> child inside one <w:lvl>. Used to carry an
            ORIGINAL list-instance property (start/lvlRestart) onto an imported house definition."""
            cur = re.search(r'<w:%s\b[^>]*/>' % tag, lvl)
            if value is None:
                return lvl.replace(cur.group(0), '', 1) if cur else lvl
            el = f'<w:{tag} w:val="{value}"/>'
            if cur:
                return lvl.replace(cur.group(0), el, 1)
            if tag == 'start':          # start is the first lvl child
                m = re.search(r'<w:lvl\b[^>]*>', lvl)
            else:                        # lvlRestart follows numFmt/start
                m = (re.search(r'<w:numFmt\b[^>]*/>', lvl) or re.search(r'<w:start\b[^>]*/>', lvl)
                     or re.search(r'<w:lvl\b[^>]*>', lvl))
            return lvl[:m.end()] + el + lvl[m.end():] if m else lvl

        def _emit_import(raw_num, raw_abs, preserve=None):
            """Emit a fresh dedicated copy of a template list under newly allocated ids, returning the new
            numId. `preserve`=(graph, numId) copies that original list's per-level start/lvlRestart onto the
            imported definition so a house repair fixes format/glyph WITHOUT resetting the instance's
            start/restart (issue #1 R1). Returns None if the template blocks are missing."""
            if not raw_num or not raw_abs:
                return None
            new_nid = str(alloc['num']); alloc['num'] += 1
            new_aid = str(alloc['abs']); alloc['abs'] += 1
            abs_xml = re.sub(r'(<w:abstractNum\b[^>]*w:abstractNumId=")[^"]+(")',
                             lambda mm: mm.group(1) + new_aid + mm.group(2), raw_abs, count=1)
            if preserve:
                og, onid = preserve
                def _fix_lvl(lm):
                    lvl = lm.group(0)
                    ilm = re.search(r'w:ilvl="([^"]+)"', lvl)
                    o_lv = og.resolve_level(onid, ilm.group(1) if ilm else '0')
                    if not o_lv:
                        return lvl
                    lvl = _lvl_set(lvl, 'start', o_lv.get('start'))
                    return _lvl_set(lvl, 'lvlRestart', o_lv.get('lvlRestart'))
                abs_xml = re.sub(r'<w:lvl\b.*?</w:lvl>', _fix_lvl, abs_xml, flags=re.S)
            new_defs.append(abs_xml)
            nn = re.sub(r'(<w:num\b[^>]*w:numId=")[^"]+(")',
                        lambda mm: mm.group(1) + new_nid + mm.group(2), raw_num, count=1)
            nn = re.sub(r'(<w:abstractNumId w:val=")[^"]+(")',
                        lambda mm: mm.group(1) + new_aid + mm.group(2), nn, count=1)
            if preserve:
                # drop the template instance's level overrides so the PRESERVED original start/restart on the
                # abstract level is authoritative (handle template instance overrides consistently, R1).
                nn = re.sub(r'<w:lvlOverride\b.*?</w:lvlOverride>', '', nn, flags=re.S)
                nn = re.sub(r'<w:lvlOverride\b[^>]*/>', '', nn)
            new_defs.append(nn)
            return new_nid

        def _resolved_tpl_blocks(tpl_nid):
            """(raw_num, resolved_abstract) for a template list, or (raw_num, None) when the dependency
            chain cannot be resolved — an unresolvable import is NEVER emitted as an empty definition (R2)."""
            raw_num = tgraph.raw_num(tpl_nid)
            tpl_aid = tgraph.abstract_of(tpl_nid)
            raw_abs = tgraph.resolved_abstract_xml(tpl_aid) if tpl_aid else None
            return raw_num, raw_abs

        def _import_tpl_list(tpl_nid):
            """Import a shared (cached) copy of a template list for an ADDED style. Returns the new numId,
            or None if unresolved (caller must then refuse to add/rewire the dependent style — R2)."""
            if tpl_nid in imported:
                return imported[tpl_nid]
            raw_num, raw_abs = _resolved_tpl_blocks(tpl_nid)
            if not raw_num or not raw_abs:
                return None
            new_nid = _emit_import(raw_num, raw_abs)
            if new_nid:
                imported[tpl_nid] = new_nid
            return new_nid

        existing = set(re.findall(r'<w:style [^>]*w:styleId="([^"]+)"', self.styles))
        added = []
        for sid, d in tmpl.items():
            if sid in existing:
                continue
            # the numId the template DECLARES for this style (raw numPr), even if its list does not resolve
            # — so an unresolvable template list is caught by the import (R2), not skipped and added raw.
            raw_np = tgraph._style_numpr_raw(sid)
            tpl_numid = raw_np[0]
            if tpl_numid and tpl_numid != '0' and '<w:numPr>' in d:
                new_nid = _import_tpl_list(tpl_numid)
                if not new_nid:
                    # ATOMIC import (R2): the dependency could not be resolved, so we must NOT add the style
                    # carrying the template's numId — that id names an unrelated list in THIS document and
                    # would silently rebind the style to it. Skip the style and surface it as unresolved.
                    self._unresolved_imports.append(
                        {'style': sid, 'numId': tpl_numid, 'context': 'add-missing-style',
                         'detail': f'template style {sid} needs numbering {tpl_numid} whose definition '
                                   f'could not be resolved; style not added rather than rebound'})
                    continue
                d = re.sub(r'(<w:numPr>.*?<w:numId w:val=")[^"]+(")',
                           lambda mm: mm.group(1) + new_nid + mm.group(2), d, count=1, flags=re.S)
            added.append(d)
        if added:
            self.styles = self.styles.replace('</w:styles>', ''.join(added) + '</w:styles>', 1)

        # HOUSE REPAIR of dysfunctional house LIST styles (R1): a house-controlled list style is repaired
        # when its resolved house PROPERTIES (list format AND the level label/glyph `lvlText`) differ from
        # the template's approved definition — not only when the numFmt enum differs. So a bullet style
        # whose glyph is corrupt (numFmt still 'bullet', lvlText='BROKEN') is repaired, and a functional
        # list with a merely different START/restart (its instance semantics, not authorised to change) is
        # NOT repaired — its label/format already match, so the trigger does not fire. The template's list
        # is imported (dependency closure, fresh ids) and the style rewired. Headings are excluded
        # (ambiguous intent). Each repair is RECORDED with its expected before→after so verification and the
        # audit distinguish it from an accidental flip.
        ograph = NumberingGraph(self._orig_num0, self._orig_styles0)
        _HOUSE_LEVEL_KEYS = ('numFmt', 'lvlText')

        def _house_list_target(sid, name):
            nm = (name or '').lower()
            if sid.startswith('Heading') or nm.startswith('heading'):
                return False
            if tgraph.style_numpr(sid) is None:
                return False
            return (sid in NUMBERED or sid in LISTS or 'list' in nm
                    or sid.startswith(('ListNumber', 'ListBullet', 'NumberedParagraph')))

        self._house_repaired = {}

        def _lvl_xml(graph, numId, ilvl):
            aid = graph.abstract_of(numId)
            raw = graph.raw_abstract(aid) if aid else None
            if not raw:
                return None
            for lm in re.finditer(r'<w:lvl\b[^>]*?w:ilvl="([^"]+)".*?</w:lvl>', raw, re.S):
                if lm.group(1) == ilvl:
                    return lm.group(0)
            return None

        def _lvl_rfonts(lvl_xml):
            rpr = re.search(r'<w:rPr>.*?</w:rPr>', lvl_xml or '', re.S)
            f = re.search(r'<w:rFonts\b[^>]*/>', rpr.group(0)) if rpr else None
            return f.group(0) if f else None

        def _build_repaired_instance(src_numId, overlays):
            """Import a FRESH copy of the SOURCE instance and overlay the approved house numFmt/lvlText (and
            the glyph's symbol font) on ONLY the affected levels — retaining healthy levels, starts, restarts
            and instance overrides (issue #1 B)."""
            src_aid = ograph.abstract_of(src_numId)
            raw_abs = ograph.raw_abstract(src_aid)
            raw_num = ograph.raw_num(src_numId)
            if not raw_abs or not raw_num:
                return None
            new_nid = str(alloc['num']); alloc['num'] += 1
            new_aid = str(alloc['abs']); alloc['abs'] += 1
            abs_xml = re.sub(r'(<w:abstractNum\b[^>]*w:abstractNumId=")[^"]+(")',
                             lambda mm: mm.group(1) + new_aid + mm.group(2), raw_abs, count=1)

            present = set()

            def _ov(lm):
                lvl = lm.group(0)
                ilm = re.search(r'w:ilvl="([^"]+)"', lvl)
                il = ilm.group(1) if ilm else '0'
                present.add(il)
                ov = overlays.get(il)
                if not ov:
                    return lvl
                return self._overlay_level(lvl, ov['numFmt'], ov['lvlText'], ov['rfonts'])
            abs_xml = re.sub(r'<w:lvl\b.*?</w:lvl>', _ov, abs_xml, flags=re.S)
            # a USED level the source lacks entirely (a dysfunctional style pointing past its definition) is
            # ADDED from the template's approved level, so the repair completes rather than staying broken.
            add = ''
            for il, ov in sorted(overlays.items()):
                if il in present or not ov.get('t_lvl_xml'):
                    continue
                lvl = re.sub(r'(<w:lvl\b[^>]*?w:ilvl=")[^"]+(")', lambda mm: mm.group(1) + il + mm.group(2),
                             ov['t_lvl_xml'], count=1)
                add += lvl
            abs_xml = abs_xml.replace('</w:abstractNum>', add + '</w:abstractNum>', 1) if add else abs_xml
            new_defs.append(abs_xml)
            nn = re.sub(r'(<w:num\b[^>]*w:numId=")[^"]+(")',
                        lambda mm: mm.group(1) + new_nid + mm.group(2), raw_num, count=1)
            nn = re.sub(r'(<w:abstractNumId w:val=")[^"]+(")',
                        lambda mm: mm.group(1) + new_aid + mm.group(2), nn, count=1)
            new_defs.append(nn)
            return new_nid

        # Reverse-use index over the ORIGINAL graph, built BEFORE any mutation (issue #1 B): every current
        # STYLE user of each source instance (numId), plus DIRECT paragraph users in the body. A whole
        # instance is repaired and ALL its users rebound together — never only the broken candidate styles.
        style_users = defaultdict(list)          # src_numId -> [{'sid','ilvl'}]
        for sid in ograph.styles:
            r = ograph.resolve_style(sid)
            if r.resolved:
                style_users[r.numId].append({'sid': sid, 'ilvl': r.ilvl})
            elif r.state == 'unresolved' and r.numId is not None:
                # a DYSFUNCTIONAL house style declares an instance but its level does not resolve — it is
                # still a user of that instance and is exactly what needs repair (must not be dropped).
                style_users[r.numId].append({'sid': sid, 'ilvl': r.ilvl or '0'})
        direct_users = defaultdict(list)         # src_numId -> [{'item','ilvl','tracked'}]
        body_n = self.n() if getattr(self, 'items', None) is not None and hasattr(self, 'b0') else 0
        for idx in range(body_n):
            it = self.item(idx)
            if not it.startswith('<w:p'):
                continue
            ppr = re.search(r'<w:pPr>.*?</w:pPr>', it, re.S)
            cur = re.sub(r'<w:pPrChange\b.*?</w:pPrChange>', '', ppr.group(0), flags=re.S) if ppr else ''
            npr = re.search(r'<w:numPr>.*?</w:numPr>', cur, re.S)
            nm = re.search(r'<w:numId w:val="([^"]+)"', npr.group(0)) if npr else None
            if not nm:
                continue
            im = re.search(r'<w:ilvl w:val="([^"]+)"', npr.group(0))
            direct_users[nm.group(1)].append(
                {'item': idx, 'ilvl': im.group(1) if im else None,
                 'tracked': bool(re.search(r'<w:pPrChange|<w:ins\b|<w:del\b', it))})

        def _house_target_style(sid):
            return sid in tmpl and _house_list_target(sid, ograph.styles.get(sid, {}).get('name'))

        for src_numId in list(style_users):
            users = style_users[src_numId]
            tnums = set(); overlays = {}
            for u in users:
                if not _house_target_style(u['sid']):
                    continue
                traw = tgraph._style_numpr_raw(u['sid'])
                if not traw[0] or traw[0] == '0':
                    continue
                ilvl = u['ilvl']
                t_lv = tgraph.resolve_level(traw[0], ilvl)
                if not t_lv:
                    continue
                o_lv = ograph.resolve_level(src_numId, ilvl)
                if tuple((o_lv or {}).get(k) for k in _HOUSE_LEVEL_KEYS) != tuple(t_lv.get(k) for k in _HOUSE_LEVEL_KEYS):
                    tnums.add(traw[0])
                    t_lvl_xml = _lvl_xml(tgraph, traw[0], ilvl)
                    overlays[ilvl] = {'t_lv': t_lv, 'rfonts': _lvl_rfonts(t_lvl_xml), 't_lvl_xml': t_lvl_xml,
                                      'numFmt': t_lv.get('numFmt'), 'lvlText': t_lv.get('lvlText')}
            if not overlays:
                continue                             # this instance's used levels already match house
            if len(tnums) > 1:                       # conflicting house targets -> report, do not split
                for u in users:
                    self._unresolved_imports.append(
                        {'style': u['sid'], 'numId': src_numId, 'context': 'house-repair-conflict',
                         'detail': f'source instance {src_numId} maps to multiple template targets '
                                   f'{sorted(tnums)}; reported, not split'})
                continue
            new_nid = _build_repaired_instance(src_numId, overlays)
            if not new_nid:
                for u in users:
                    self._unresolved_imports.append(
                        {'style': u['sid'], 'numId': src_numId, 'context': 'house-repair',
                         'detail': f'source instance {src_numId} could not be repaired (definition unresolved)'})
                continue
            for u in users:                          # rebind EVERY style user (broken + healthy siblings)
                self._set_style_numpr(u['sid'], new_nid, u['ilvl'])
                o_lv = ograph.resolve_level(src_numId, u['ilvl'])
                ov = overlays.get(u['ilvl'])
                if ov:
                    after = {'numFmt': ov['t_lv'].get('numFmt'), 'lvlText': ov['t_lv'].get('lvlText'),
                             'isLgl': (o_lv or {}).get('isLgl'), 'start': (o_lv or {}).get('start'),
                             'lvlRestart': (o_lv or {}).get('lvlRestart')}
                else:
                    after = {k: (o_lv or {}).get(k) for k in self._LEVEL_KEYS}
                self._house_repaired[u['sid']] = {
                    'ilvl': u['ilvl'], 'shared_new_numId': new_nid,
                    'before': {k: (o_lv or {}).get(k) for k in self._LEVEL_KEYS}, 'after_expected': after}
            for du in direct_users.get(src_numId, []):   # rebind direct users; report tracked ones
                if du['tracked']:
                    self._unresolved_imports.append(
                        {'style': None, 'numId': src_numId, 'context': 'house-repair-direct-tracked',
                         'item': du['item'], 'detail': f'direct numbering reference to repaired instance '
                         f'{src_numId} at item {du["item"]} is a tracked change; left for review'})
                    continue
                self.set(du['item'], re.sub(
                    r'(<w:numPr>(?:(?!</w:numPr>).)*?<w:numId w:val=")[^"]+(")',
                    lambda mm: mm.group(1) + new_nid + mm.group(2), self.item(du['item']), count=1, flags=re.S))

        # ORPHAN house styles that LOST their numbering entirely (resolve to NONE in the original, but the
        # template numbers them) have no source instance to preserve — give each a FRESH imported template
        # instance and an explicit numPr. This is the dysfunctional-style repair (Claire's 'List Bullet
        # dysfunctional') for styles whose list association was removed, not merely mis-formatted.
        for sid in ograph.styles:
            if sid in self._house_repaired or not _house_target_style(sid):
                continue
            if ograph.resolve_style(sid).state != 'none':
                continue                              # resolved / unresolved handled by the instance loop
            traw = tgraph._style_numpr_raw(sid)
            if not traw[0] or traw[0] == '0':
                continue
            t_ilvl = traw[1] or '0'
            t_lv = tgraph.resolve_level(traw[0], t_ilvl)
            raw_num, raw_abs = _resolved_tpl_blocks(traw[0])
            new_nid = _emit_import(raw_num, raw_abs) if t_lv else None
            if not new_nid:
                self._unresolved_imports.append(
                    {'style': sid, 'numId': traw[0], 'context': 'house-repair',
                     'detail': f'{sid} lost its numbering and the template list {traw[0]} did not resolve'})
                continue
            self._set_style_numpr(sid, new_nid, t_ilvl)
            self._house_repaired[sid] = {
                'ilvl': t_ilvl, 'shared_new_numId': new_nid,
                'before': {k: None for k in self._LEVEL_KEYS},
                'after_expected': {'numFmt': t_lv.get('numFmt'), 'lvlText': t_lv.get('lvlText'),
                                   'isLgl': t_lv.get('isLgl'), 'start': t_lv.get('start'),
                                   'lvlRestart': t_lv.get('lvlRestart')}}

        if new_defs:
            # CT_Numbering REQUIRES every <w:abstractNum> BEFORE every <w:num> (Word drops ALL numbering
            # when they interleave). Insert new abstractNums before the first existing <w:num>, and new
            # <w:num> instances before </w:numbering> — never appended after the existing nums.
            new_abs = ''.join(d for d in new_defs if d.lstrip().startswith('<w:abstractNum'))
            new_num = ''.join(d for d in new_defs if d.lstrip().startswith('<w:num '))
            if new_abs:
                m = re.search(r'<w:num\b(?![a-zA-Z])', self.num)
                if m:
                    self.num = self.num[:m.start()] + new_abs + self.num[m.start():]
                else:
                    self.num = self.num.replace('</w:numbering>', new_abs + '</w:numbering>', 1)
            if new_num:
                self.num = self.num.replace('</w:numbering>', new_num + '</w:numbering>', 1)

        pinned = self._preserve_inherited_numbering(ograph)

        self.say('M', -1, f'preserve mode: repaired {fixed[0]} corrupt style definitions + added '
                          f'{len(added)} missing styles / imported {len(imported)} numbering defs with fresh '
                          f'ids; repaired {len(self._house_repaired)} dysfunctional house list style(s), '
                          f'preserved {pinned} inherited list(s) (docDefaults untouched)', 'styles-repair')

    def _preserve_inherited_numbering(self, ograph):
        """Pin back the ORIGINAL resolved numbering of any style whose resolved FORMAT changed WITHOUT an
        intended house repair — covering styles numbered only through basedOn inheritance (which
        _keep_numpr, local-numPr-only, cannot protect; issue #1 R2 counterexample 2). A style whose
        original basedOn chain reaches a house-repaired style is intentionally following that repair and
        is NOT pinned. Returns the number of styles pinned."""
        from conformer.numbering import NumberingGraph
        ngraph = NumberingGraph(self.num, self.styles)

        def chain_repaired(sid):
            seen = set(); s = sid
            while s and s not in seen:
                seen.add(s)
                if s in self._house_repaired:
                    return True
                st = ograph.styles.get(s)
                if not st or st.get('numId'):     # local numbering ends the inheritance chain
                    return False
                s = st.get('basedOn')
            return False

        pinned = 0
        for sid in ograph.styles:
            if sid in self._house_repaired or chain_repaired(sid):
                continue
            o_np = ograph.style_numpr(sid)
            n_np = ngraph.style_numpr(sid)
            if not o_np:
                # the style had NO numbering; if it GAINED some (e.g. a template basedOn change made it
                # inherit a list, as a TOC style would), suppress it with an explicit numId 0 override
                if n_np:
                    self._set_style_numpr(sid, '0', '0'); pinned += 1
                continue
            o_sig = self._level_signature(ograph, o_np)
            n_sig = self._level_signature(ngraph, n_np)
            if o_sig and o_sig != 'UNRESOLVED' and o_sig != n_sig:
                self._set_style_numpr(sid, o_np[0], o_np[1]); pinned += 1
        return pinned

    _LEVEL_KEYS = ('numFmt', 'lvlText', 'start', 'isLgl', 'lvlRestart')

    @classmethod
    def _level_signature(cls, graph, numpr):
        """The full resolved level record a style uses, or None. Compares by MEANING (format, label,
        start, restart), not by numeric id — so a style REASSIGNED to a same-format list with a different
        start/restart is still detected (issue #1 R3)."""
        if not numpr:
            return None
        lv = graph.resolve_level(*numpr)
        return tuple(lv.get(k) for k in cls._LEVEL_KEYS) if lv else 'UNRESOLVED'

    def numbering_report(self):
        """Resolution-based numbering verification (the gate is blind to numbering.xml/styles.xml). For
        every paragraph style, RESOLVE the list it uses before vs after and compare the FULL level record
        (format, label, start, isLgl, restart) — not just numFmt — so reassignment to a different list and
        start/restart changes are caught, not only decimal↔bullet flips. Returns a change record per style
        whose resolved numbering changed (with 'intended' set for recorded house repairs)."""
        from conformer.numbering import NumberingGraph
        before = NumberingGraph(self._orig_num0, self._orig_styles0)
        after = NumberingGraph(self.num, self.styles)
        repaired = getattr(self, '_house_repaired', {})

        def _repair_expected(sid):
            """The FULL level a style is AUTHORIZED to resolve to after a house repair — its own recorded
            expected delta, or (through basedOn) the repaired ancestor's, since it inherits that same
            imported list. None if no repair authorizes this style. Membership in a repair is NOT itself
            permission for an arbitrary numbering change (issue #1 R1): the actual after-state must equal
            this expected delta."""
            seen = set(); s = sid
            while s and s not in seen:
                seen.add(s)
                if s in repaired:
                    ae = repaired[s].get('after_expected')
                    return tuple(ae.get(k) for k in self._LEVEL_KEYS) if ae else None
                st = before.styles.get(s)
                if not st or st.get('numId'):     # local numbering ends the inheritance chain
                    return None
                s = st.get('basedOn')
            return None

        changes = []
        for sid in before.styles:
            bp = before.style_numpr(sid)
            ap = after.style_numpr(sid)
            bsig = self._level_signature(before, bp)
            asig = self._level_signature(after, ap)
            if bool(bp) != bool(ap) or (bp and ap and bsig != asig):
                bf = before.effective_format(*bp) if bp else None
                af = after.effective_format(*ap) if ap else None
                exp = _repair_expected(sid)
                # INTENDED only when a repair authorized this style AND the actual resolved after-level
                # matches exactly the recorded expected delta (so a repair that also reset start/restart is
                # caught as an unauthorized flip, not rubber-stamped by mere repair membership).
                intended = exp is not None and asig == exp
                changes.append({'style': sid, 'before': bf, 'after': af,
                                'before_level': bsig, 'after_level': asig, 'expected_level': exp,
                                'meaning_flip': (bf == 'bullet') != (af == 'bullet'),
                                'intended': intended})
        return changes

    def definition_integrity_report(self):
        """Protect historical interpretation: every PRE-EXISTING numbering definition must still resolve
        to the same format after conforming, so a snapshot/reference that depends on it is not silently
        redirected to a new meaning. We only import NEW definitions under fresh ids, so this must be empty.
        Returns [{numId, ilvl, before, after}] for any existing numId whose resolved format changed."""
        from conformer.numbering import NumberingGraph
        before = NumberingGraph(self._orig_num0, self._orig_styles0)
        after = NumberingGraph(self.num, self.styles)
        viol = []
        _keys = self._LEVEL_KEYS      # numFmt, lvlText, start, isLgl, lvlRestart
        for nid in before.nums:
            aid = before.abstract_of(nid)
            levels = set((before.abstract.get(aid, {}) or {}).get('levels', {}) or {})
            levels |= set((before.nums[nid].get('overrides') or {}))
            levels |= {'0'}
            for ilvl in levels:
                b = before.resolve_level(nid, ilvl)
                if b is None:
                    continue
                a = after.resolve_level(nid, ilvl)
                if a is None:
                    viol.append({'numId': nid, 'ilvl': ilvl, 'issue': 'definition removed or unresolvable'})
                elif tuple(b.get(k) for k in _keys) != tuple(a.get(k) for k in _keys):
                    viol.append({'numId': nid, 'ilvl': ilvl, 'issue': 'definition meaning changed',
                                 'before': {k: b.get(k) for k in _keys}, 'after': {k: a.get(k) for k in _keys}})
        return viol

    @staticmethod
    def _fold_typography(t):
        """Fold the characters the engine's own typography pass rewrites (curly quotes/apostrophes, en/em
        dashes, nbsp) so a paragraph's IDENTITY survives authorized typography and is not silently dropped
        from reference verification (issue #1 R3)."""
        return (t.replace('’', "'").replace('‘', "'").replace('“', '"')
                 .replace('”', '"').replace('–', '-').replace('—', '-')
                 .replace(' ', ' '))

    def _paragraph_reference_scan(self):
        """Resolve each paragraph's ACTUAL numbering (direct numPr else style; current AND historical
        snapshot) before vs after, across the whole body INCLUDING table cells (issue #1 R3). Correspondence
        is by stable w14:paraId first (so authorized typography does not drop a paragraph), then same-style
        typography-folded text; an original content paragraph with numbering that has NO stable match is
        surfaced as UNRESOLVED, never silently unchecked. A current-reference change is authorized only when
        the paragraph's style follows a recorded house repair to its expected delta. Returns
        {'flips': [...unauthorized changes...], 'unresolved': [...uncorresponded numbered paragraphs...]}."""
        from conformer.numbering import NumberingGraph
        from collections import defaultdict
        before = NumberingGraph(self._orig_num0, self._orig_styles0)
        after = NumberingGraph(self.num, self.styles)
        repaired = getattr(self, '_house_repaired', {})

        def _repair_expected(sid):
            seen = set(); s = sid
            while s and s not in seen:
                seen.add(s)
                if s in repaired:
                    ae = repaired[s].get('after_expected')
                    return tuple(ae.get(k) for k in self._LEVEL_KEYS) if ae else None
                st = before.styles.get(s)
                if not st or st.get('numId'):
                    return None
                s = st.get('basedOn')
            return None

        def _numref(frag):
            npr = re.search(r'<w:numPr>.*?</w:numPr>', frag, re.S)
            if not npr:
                return (None, None)
            nm = re.search(r'<w:numId w:val="([^"]+)"', npr.group(0))
            im = re.search(r'<w:ilvl w:val="([^"]+)"', npr.group(0))
            return (nm.group(1) if nm else None, im.group(1) if im else None)

        def _info(p):
            open_tag = p[:p.find('>') + 1]
            pid = re.search(r'w14:paraId="([^"]+)"', open_tag)
            ppr = re.search(r'<w:pPr>.*?</w:pPr>', p, re.S)
            pxml = ppr.group(0) if ppr else ''
            cur = re.sub(r'<w:pPrChange\b.*?</w:pPrChange>', '', pxml, flags=re.S)   # current props
            histm = re.search(r'<w:pPrChange\b.*?</w:pPrChange>', pxml, re.S)         # historical snapshot
            st = re.search(r'<w:pStyle w:val="([^"]+)"', cur)
            text = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p))
            return {'id': pid.group(1) if pid else None,
                    'style': st.group(1) if st else None,
                    'cur': _numref(cur), 'hist': _numref(histm.group(0)) if histm else (None, None),
                    'text': self._fold_typography(' '.join(text.split()))}

        def _paras(items, b0):
            # every <w:p> in the body, INCLUDING those inside table cells (paragraphs do not nest)
            return re.findall(r'<w:p(?: [^>]*)?>.*?</w:p>', ''.join(items[b0:]), re.S)

        def _res(graph, info, ref):
            nid, il = info[ref]
            if ref == 'hist' and nid is None:
                return None
            return graph.resolve_paragraph(nid, il, info['style'])

        def _sig_of(res):
            return res.signature(self._LEVEL_KEYS) if res is not None else None

        def _inst_of(res):
            return res.numId if (res is not None and res.resolved) else None

        def _strip_authorized(bi, ai, a_res):
            """A policy-approved SAME-CATEGORY strip (issue #1 C): the paragraph's style is UNCHANGED, its
            direct numPr existed before and is gone now, removing it did not FLIP number<->bullet, and it now
            resolves through that style. Two different instances or a category flip are NOT interchangeable."""
            if bi['style'] != ai['style'] or bi['cur'][0] is None or ai['cur'][0] is not None:
                return False
            bd = before.resolve_paragraph(bi['cur'][0], bi['cur'][1], bi['style'])
            bs = before.resolve_style(bi['style'])
            if not (bd.resolved and bs.resolved) or a_res is None or not a_res.resolved:
                return False
            return self._is_bullet_fmt(bd.level) == self._is_bullet_fmt(bs.level)

        restyled = getattr(self, '_restyled', {})
        bullet_restored = getattr(self, '_bullet_restored', {})

        def _bullet_restore_authorized(bi, ai, a_res):
            """An audited bullet restore: a paragraph styled as a house bullet had its numId=0 suppression
            removed so the style's bullet renders. Authorized only when it was recorded AND now resolves to
            a bullet via its (unchanged) style."""
            key = ai['id'] or ('t:' + ai['text'])
            if key not in bullet_restored or bullet_restored[key] != ai['style'] or bi['style'] != ai['style']:
                return False
            return a_res is not None and a_res.resolved and self._is_bullet_fmt(a_res.level)

        def _restyle_authorized(bi, ai, a_res):
            """A pStyle change the ENGINE recorded (classify / level promotion): an approved reclassification
            where the paragraph correctly follows its newly-assigned style. An EXTERNAL pStyle change is not
            recorded and is never authorized this way (issue #1 C)."""
            if bi['style'] == ai['style']:
                return False
            key = ai['id'] or ('t:' + ai['text'])
            if restyled.get(key) != ai['style']:
                return False
            return a_res is not None and a_res.resolved

        b_list = [_info(p) for p in _paras(self._orig_items0, self._orig_b0)]
        a_list = [_info(p) for p in _paras(self.items, self.b0)]
        a_by_id = defaultdict(list); a_by_txt = defaultdict(list)
        for j, ai in enumerate(a_list):
            if ai['id']:
                a_by_id[ai['id']].append(j)
            if ai['text']:                         # empty-text paragraphs correspond ONLY by paraId
                a_by_txt[(ai['style'], ai['text'])].append(j)

        used, pairs, unmatched = set(), [], []
        for bi in b_list:
            j = None
            if bi['id']:
                cand = [k for k in a_by_id.get(bi['id'], []) if k not in used]
                if len(cand) == 1:
                    j = cand[0]
            if j is None and bi['text']:           # fallback: same-style, typography-folded NON-empty text
                cand = [k for k in a_by_txt.get((bi['style'], bi['text']), []) if k not in used]
                if cand:
                    j = cand[0]
            if j is None:
                unmatched.append(bi)
            else:
                used.add(j); pairs.append((bi, a_list[j]))

        flips, unresolved = [], []
        for bi, ai in pairs:
            b_res = _res(before, bi, 'cur'); a_res = _res(after, ai, 'cur')
            bsig = _sig_of(b_res); asig = _sig_of(a_res)
            # Unchanged semantic resolution AND instance relationship passes. A changed level OR a changed
            # INSTANCE (two lists with identical level properties are NOT interchangeable — continuation
            # differs) requires EXACT authorization: a recorded house-repair delta, or a policy-approved
            # same-category strip. The blanket "follows its output style" exemption is removed (issue #1 C).
            if not (bsig == asig and _inst_of(b_res) == _inst_of(a_res)):
                exp = _repair_expected(ai['style'])
                authorized = ((exp is not None and asig == exp) or _strip_authorized(bi, ai, a_res)
                              or _restyle_authorized(bi, ai, a_res)
                              or _bullet_restore_authorized(bi, ai, a_res))
                if not authorized:
                    flips.append({'scope': 'current', 'text': (ai['text'] or bi['text'])[:60],
                                  'before_style': bi['style'], 'style': ai['style'],
                                  'before_level': bsig, 'after_level': asig,
                                  'before_instance': _inst_of(b_res), 'after_instance': _inst_of(a_res)})
            hb_res = _res(before, bi, 'hist'); ha_res = _res(after, ai, 'hist')
            hb = _sig_of(hb_res); ha = _sig_of(ha_res)
            if (bi['hist'][0] or ai['hist'][0]) and not (hb == ha and _inst_of(hb_res) == _inst_of(ha_res)):
                flips.append({'scope': 'historical', 'text': (ai['text'] or bi['text'])[:60],
                              'style': ai['style'], 'before_level': hb, 'after_level': ha})
        for bi in unmatched:                       # a content paragraph that carried numbering must not vanish
            if bi['text'] and (_inst_of(_res(before, bi, 'cur')) is not None or bi['hist'][0]):
                unresolved.append({'text': bi['text'][:60], 'style': bi['style'],
                                   'reason': 'numbered paragraph has no stable correspondence in the output '
                                             '(merged/split/removed or identity lost); numbering not verified'})
        return {'flips': flips, 'unresolved': unresolved}

    def paragraph_reference_report(self):
        """Unauthorized paragraph-numbering reference changes (issue #1 R3). See _paragraph_reference_scan."""
        return self._paragraph_reference_scan()['flips']

    def conformance_status(self):
        """The single authoritative verdict consumed by production save, UI and audit (issue #1 R3).
        - blocking = unauthorized SEMANTIC damage that must not pass as normal output (unintended
          numbering flips, definition-integrity violations, tables failing effective formatting).
        - clean = blocking is empty AND nothing is unadjudicated (no review deviations, no unresolved
          tables/passes). An unadjudicated review deviation is never silently treated as approved.
        Returns {'clean', 'blocking', 'reasons': {...}}."""
        rep = self.outcome_report()
        conf, unres = rep['conformance'], rep['unresolved']
        blocking_reasons = {
            'numbering_flips': conf['numbering_flips'],
            'definition_integrity_violations': conf['definition_integrity_violations'],
            'paragraph_reference_flips': conf.get('paragraph_reference_flips') or [],
            'tables_failing_effective_format': conf['tables_failing_effective_format'],
        }
        # A table note is a genuine unresolved item only when it is a NESTED table left untouched; a
        # "tracked header-fill corrected, record preserved" note records a COMPLETED action. Match the
        # exact engine phrase, not the bare word 'nested' (a locator/heading could contain it) (F5).
        table_notes = unres.get('tables_needing_review') or []
        nested_notes = [n for n in table_notes if 'nested table left untouched' in n]
        info_notes = [n for n in table_notes if 'nested table left untouched' not in n]
        # Broken cross-references (missing/erroring targets) are a genuine unresolved defect a field
        # refresh cannot fix — they gate 'clean' (GPT audit F5). Advisory audits (caption basis, heading
        # level skips) stay out of the verdict per D-1/D-4.
        broken_refs = [a for a in (getattr(self, 'audit', []) or [])
                       if a and a[0] in ('xref-broken', 'xref-target-missing')]
        # Genuinely unadjudicated / unresolved — these DO gate 'clean' (the user must look).
        unresolved_reasons = {
            'tables_unresolved': unres.get('tables_unresolved') or [],
            'tables_needing_review': nested_notes,
            'broken_references': broken_refs,
            'unresolved_imports': unres.get('unresolved_imports') or [],
            'paragraph_reference_unresolved': unres.get('paragraph_reference_unresolved') or [],
            'rolled_back_passes': unres.get('rolled_back_passes') or [],
        }
        # Informational: legitimate, intentional table variation the engine correctly PRESERVED (small
        # data fonts, right-aligned numbers, subtotal shading) and completed-correction notes. Surfaced
        # for the reviewer but requiring no decision, so they do NOT gate 'clean' — otherwise no real
        # report is ever clean and the warning becomes noise the reviewer learns to ignore.
        informational_reasons = {
            'tables_review': conf.get('tables_review') or [],
            'tables_notes_informational': info_notes,
        }
        blocking = any(blocking_reasons.values())
        clean = not (blocking or any(unresolved_reasons.values()))
        return {'clean': clean, 'blocking': blocking,
                'reasons': {**blocking_reasons, **unresolved_reasons, **informational_reasons},
                'informational': informational_reasons}

    def conformance_clean(self):
        """True only when the authoritative verdict is clean: no blocking semantic damage AND nothing
        genuinely unresolved (unresolved/nested tables, unresolved imports, uncorresponded numbered
        paragraphs, rolled-back passes). Informational surfacings — legitimate variation the engine
        correctly PRESERVED (small data fonts, right-aligned numbers, subtotal shading) and
        completed-correction notes — are reported but do not gate cleanliness. Callers gate the 'conforms'
        claim on this, not on ZIP/XML validity."""
        return self.conformance_status()['clean']

    def outcome_report(self):
        """The three outcomes reported SEPARATELY (a clean preservation result never stands in for
        conformance verification): (1) review-history preservation, (2) formatting conformance,
        (3) unresolved exceptions."""
        try:
            clean, _disc = self.verify_preservation()
        except Exception:
            clean = None
        s = self.revision_ledger.summary() if getattr(self, 'revision_ledger', None) else {}
        preservation = {'clean': clean, 'tracked_changes': s.get('total', 0),
                        'comments': s.get('comments', 0), 'authors': len(s.get('authors', []) or [])}

        from conformer import tablespec
        ns = self._doc_nsdecls()
        table_fails, table_unresolved, table_review = [], [], []
        for i in range(self.n()):
            it = self.item(i)
            if not it.startswith('<w:tbl'):
                continue
            loc = self._locator(i)
            issues = tablespec.effective_table_issues(it, nsdecls=ns, styles_xml=self.styles)
            f = [x for x in issues if x['severity'] == 'fail']
            u = [x for x in issues if x['severity'] == 'unresolved']
            rv = [x for x in issues if x['severity'] == 'review']
            if f:
                table_fails.append({'item': i, 'locator': loc, 'issues': f})
            if u:
                table_unresolved.append({'item': i, 'locator': loc, 'issues': u})
            if rv:
                table_review.append({'item': i, 'locator': loc, 'issues': rv})
        num_changes = self.numbering_report()
        pref = self._paragraph_reference_scan()
        conformance = {'numbering_flips': [c for c in num_changes if not c.get('intended')],
                       'numbering_intended_repairs': [c for c in num_changes if c.get('intended')],
                       'definition_integrity_violations': self.definition_integrity_report(),
                       'paragraph_reference_flips': pref['flips'],
                       'tables_failing_effective_format': table_fails,
                       'tables_review': table_review}

        unresolved = {'rolled_back_passes': list(getattr(self, 'exceptions', []) or []),
                      'tables_needing_review': list(getattr(self, '_table_notes', []) or []),
                      'unresolved_imports': list(getattr(self, '_unresolved_imports', []) or []),
                      'paragraph_reference_unresolved': pref['unresolved'],
                      'tables_unresolved': table_unresolved}
        return {'preservation': preservation, 'conformance': conformance, 'unresolved': unresolved}

    def _doc_nsdecls(self):
        """The document root's namespace declarations, so a table fragment with inherited prefixes
        (w14, r, drawing, …) parses in its real namespace context rather than failing."""
        m = re.search(r'<w:document\b([^>]*)>', self.head)
        if not m:
            return None
        return ' '.join(re.findall(r'xmlns(?::[\w-]+)?="[^"]+"', m.group(1))) or None

    def _locator(self, i):
        """A stable, human locator for a body item: nearest preceding Heading1/2 text + paragraph index."""
        sec = ''
        for j in range(i, -1, -1):
            if self.is_par(j) and self.style(j) in ('Heading1', 'Heading2'):
                sec = (self.text(j) or '').strip()[:50]
                break
        return f'{sec} · ¶{i + 1}' if sec else f'¶{i + 1}'

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

    HOUSE_HEADER_SHD = '<w:shd w:val="clear" w:color="auto" w:fill="B6DDE8"/>'

    # A 10pt-bold centered header PARAGRAPH style. Header cells cannot rely on the Grid Table 4 firstRow
    # rPr for their size: a paragraph style (Table Data = 11pt) overrides the table-style conditional, so
    # the header would render 11pt. Giving header cells this paragraph style makes them render the house
    # 10pt bold (matching the firstRow), which a table-style conditional alone cannot guarantee.
    TABLE_HEADER_STYLE = (
        '<w:style w:type="paragraph" w:customStyle="1" w:styleId="TableHeader">'
        '<w:name w:val="Table Header"/><w:basedOn w:val="TableData"/><w:uiPriority w:val="99"/>'
        '<w:pPr><w:spacing w:before="60" w:after="60"/><w:jc w:val="center"/></w:pPr>'
        '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:b/><w:bCs/>'
        '<w:color w:val="auto"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style>')

    @classmethod
    def _correct_current_header_fill(cls, tc):
        """Normalize a header cell's CURRENT background to the CONCRETE house teal B6DDE8 (Grid Table 4): the
        direct <w:shd> in the current tcPr (the region BEFORE any <w:tcPrChange> snapshot) is replaced with
        clear/B6DDE8/auto with any conflicting themeFill/themeColor/tint/shade removed — covering white,
        automatic and theme fills (incl. a theme accent that would resolve to the wrong colour), not just a
        non-house hex. A concrete B6DDE8 (with no theme reference) is theme-independent, so the teal renders
        correctly regardless of the document's accent5. The historical tcPrChange snapshot is left
        byte-identical, so the tracked-change RECORD is preserved. Returns (xml, changed)."""
        o = tc.find('<w:tcPr>')
        if o < 0:
            return tc, False
        ch = tc.find('<w:tcPrChange')
        end = ch if ch >= 0 else tc.find('</w:tcPr>', o)
        if end < 0:
            end = len(tc)
        region = tc[o:end]
        m = re.search(r'<w:shd\b[^>]*/>', region)
        if not m:
            return tc, False                          # no direct current fill -> rely on the conditional
        shd = m.group(0)
        fill = re.search(r'w:fill="([^"]+)"', shd)
        already_teal = (fill and fill.group(1).upper() == 'B6DDE8' and 'theme' not in shd)
        if already_teal:
            return tc, False
        new_region = region.replace(shd, cls.HOUSE_HEADER_SHD, 1)
        return tc[:o] + new_region + tc[end:], True

    # Header-cell body paragraph styles that may be normalised to Table Header. A heading, numbered or
    # bulleted paragraph is NEVER reclassified here — that would strip its numbering (an unauthorized
    # reference flip); such a paragraph in a header cell is left exactly as authored.
    _HEADER_BODY_STYLES = {'TableData', 'TableHeader', 'Normal', 'TableParagraph', 'TableText'}

    @classmethod
    def _force_header_paragraph_style(cls, xml):
        """Give each header-cell BODY paragraph the 10pt-bold Table Header style (replace its current
        pStyle, else insert one for a plain default paragraph). Operates on text whose tracked-change
        RECORDS are masked, so a pPrChange's recorded old pStyle is never touched — only the CURRENT
        paragraph style is set. Headings/numbered/bulleted paragraphs are left as-is (see above)."""
        def fixp(pm):
            p = pm.group(0)
            # a paragraph carrying a DIRECT numPr is a numbered/bulleted list item — never reclassify it,
            # regardless of its pStyle. Reclassifying to Table Header would silently strip its list
            # association (an unauthorized reference flip); such a list in a header cell is left as authored
            # (GPT audit F9). Only the current pPr is inspected — a pPrChange record is masked upstream.
            ppr = re.search(r'<w:pPr\b.*?</w:pPr>', p, re.S)
            if ppr and '<w:numPr>' in ppr.group(0):
                return p
            cur = re.search(r'<w:pStyle w:val="([^"]+)"', p)
            if cur:
                if cur.group(1) in cls._HEADER_BODY_STYLES:
                    return re.sub(r'<w:pStyle w:val="[^"]+"/>', '<w:pStyle w:val="TableHeader"/>', p, count=1)
                return p                                  # heading / other deliberate style — leave
            # no explicit pStyle = a plain (default) header paragraph — give it Table Header. Handle a full
            # <w:pPr>...</w:pPr> AND a self-closing <w:pPr/> (inserting a second pPr would be invalid
            # paragraph structure — GPT audit F9 double-pPr).
            if '<w:pPr>' in p:
                return p.replace('<w:pPr>', '<w:pPr><w:pStyle w:val="TableHeader"/>', 1)
            if '<w:pPr/>' in p:
                return p.replace('<w:pPr/>', '<w:pPr><w:pStyle w:val="TableHeader"/></w:pPr>', 1)
            return re.sub(r'(<w:p\b[^>]*>)', r'\1<w:pPr><w:pStyle w:val="TableHeader"/></w:pPr>', p, count=1)
        return re.sub(r'<w:p\b.*?</w:p>', fixp, xml, flags=re.S)

    def _repair_stray_header_formatting(self, tbl_xml, locator):
        """Correct the header row to the house style so the Grid Table 4 teal/black-bold header renders
        (issue #1 R5). Per the maintainer ruling, a WRONG header FILL is corrected to the house colour even
        when it is a tracked formatting change — the tracked-change RECORD (the <w:tcPrChange> snapshot and
        every ins/del text mark) is preserved, only the CURRENT wrong fill is normalised so the house teal
        wins. Direct run size/colour are stripped on cells with no run-level tracked change so the header
        inherits the style's black 10pt bold text (a tracked inserted run's own formatting is left intact).
        Returns (xml, corrected_cells, tracked_fills_corrected)."""
        m = re.search(r'<w:tr\b.*?</w:tr>', tbl_xml, re.S)
        if not m or '<w:tblHeader' not in m.group(0):
            return tbl_xml, 0, 0
        row = m.group(0)
        rep = [0]; tracked_fixed = [0]

        def _fix_cell(cm):
            tc = cm.group(0)
            run_tracked = re.search(r'<w:rPrChange|<w:pPrChange|<w:ins\b|<w:del\b', tc)
            cell_tracked = run_tracked or ('<w:tcPrChange' in tc)
            # ALWAYS correct a wrong header fill to the house colour, even under a tracked change.
            tc2, fill_fixed = self._correct_current_header_fill(tc)
            # Header text must render at the house 10pt bold. A paragraph style overrides the Grid Table 4
            # firstRow rPr, so give EVERY header paragraph the 10pt Table Header style and strip the direct
            # run sizes/colours that would override it — INCLUDING inside a tracked insertion (D-A3: conform
            # formatting regardless of tracked state). content=False masks only the tracked-change RECORDS
            # (rPrChange/pPrChange/tcPrChange), so each record's old snapshot stays byte-exact for
            # accept/reject while the CURRENT (incl. inserted/deleted) formatting is conformed. The text of
            # every ins/del run is untouched — only formatting elements are removed.
            masked, masks = self._mask_revisions(tc2, content=False)
            masked = self._force_header_paragraph_style(masked)
            masked = re.sub(r'<w:szCs w:val="\d+"/>', '', masked)
            masked = re.sub(r'<w:sz w:val="\d+"/>', '', masked)
            masked = re.sub(r'<w:color w:val="[^"]+"/>', '', masked)
            tc2 = self._unmask(masked, masks)
            if fill_fixed and cell_tracked:
                tracked_fixed[0] += 1
            if tc2 != tc:
                rep[0] += 1
            return tc2

        newrow = re.sub(r'<w:tc\b.*?</w:tc>', _fix_cell, row, flags=re.S)
        out = tbl_xml.replace(row, newrow, 1) if newrow != row else tbl_xml
        if tracked_fixed[0]:
            self._table_notes.append(f'{locator}: {tracked_fixed[0]} header cell(s) had a non-house fill '
                                     'that was a TRACKED change — corrected to the house colour; the '
                                     'tracked-change record is preserved')
        return out, rep[0], tracked_fixed[0]

    def _ensure_house_table_style(self):
        """Import the house table style (Grid Table 4 / "LI Table") into the document's own styles.xml if it
        is missing (the Warhoe report lacks it entirely), so a stamped tblStyle="GridTable4" resolves to the
        real teal/black/grid definition instead of Word's default. The imported definition is theme-
        independent (concrete B6DDE8), so it renders teal regardless of the document's accent5."""
        if re.search(r'<w:style\b[^>]*w:styleId="GridTable4"', self.styles):
            return
        self.styles = self.styles.replace('</w:styles>', self._house_table_style + '</w:styles>', 1)
        # internal prerequisite of the tables fix (runs only past the 'tables' skip gate) — not a separate
        # ledger row; the "tables set to the LI table style" row and its Skip cover it.

    def _ensure_table_header_style(self):
        """Ensure the 10pt-bold 'Table Header' paragraph style exists so header cells render at the house
        10pt. A paragraph style overrides the Grid Table 4 firstRow rPr, so header cells cannot get their
        size from the table-style conditional alone. Imported once."""
        if re.search(r'<w:style\b[^>]*w:styleId="TableHeader"', self.styles):
            return
        self.styles = self.styles.replace('</w:styles>', self.TABLE_HEADER_STYLE + '</w:styles>', 1)
        # internal prerequisite of the tables fix — not a separate ledger row (the 'tables' Skip covers it).

    def _conform_tables_preserving(self):
        """Make every table USE the (now-repaired) LI table style so its built-in settings apply
        (Claire's 'tables not using the table style' / 'settings not used'). Table-level properties
        only, and tracked-formatting snapshots are masked out first, so no cell content and no reject
        target is touched."""
        if self._skip('tables'):
            return
        self._ensure_house_table_style()
        self._ensure_table_header_style()
        cnt = 0
        for i in range(self.n()):
            x = self.item(i)
            if not x.startswith('<w:tbl'):
                continue
            masked, masks = self._mask_revisions(x)   # protect snapshots AND cell revision content
            # a nested table adds another <w:tbl> ELEMENT (not a <w:tblPr>/<w:tblGrid>/… property, which
            # also start with '<w:tbl'); match the element start only
            nested = len(re.findall(r'<w:tbl[ >]', masked)) > 1
            if nested:
                # do NOT speculatively edit a table containing a nested table with flat regexes — leave it
                # untouched and report it (with a locator) for independent review (issue #1 R5).
                self._table_notes.append(f'{self._locator(i)}: nested table left untouched for independent '
                                         'review')
                continue
            # Remove direct table AND cell borders that would override the Grid Table 4 black grid (a
            # correct style name does not conform if a direct <w:tcBorders> defeats it). Masked revision
            # content is untouched (its borders are behind sentinels).
            nx = re.sub(r'<w:tblBorders>.*?</w:tblBorders>', '', masked, flags=re.S)
            nx = re.sub(r'<w:tcBorders>.*?</w:tcBorders>', '', nx, flags=re.S)
            # REPAIR (not only detect) known house-controlled conflicts: remove direct cell margins and
            # direct run sizes that conflict with the house body 11pt, so the Grid Table 4 style supplies
            # them. Masked revision content is untouched (behind sentinels).
            nx = re.sub(r'<w:tcMar>.*?</w:tcMar>', '', nx, flags=re.S)
            # Remove a direct run size only when it is LARGER than the house 11pt (a stray oversize cell),
            # so the Grid Table 4 body 11pt applies. A SMALLER size (8-10pt dense data) is kept by default
            # (intentional) and offered for normalization separately (GPT audit F4). Header sizes are
            # conformed to 10pt by the header repair regardless.
            nx = re.sub(r'<w:sz w:val="(\d+)"/>', lambda mm: '' if int(mm.group(1)) > 22 else mm.group(0), nx)
            if '<w:tblStyle' in nx:
                nx = re.sub(r'<w:tblStyle w:val="[^"]+"/>', '<w:tblStyle w:val="GridTable4"/>', nx, count=1)
            else:
                nx = nx.replace('<w:tblPr>', '<w:tblPr><w:tblStyle w:val="GridTable4"/>', 1)
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
            # Conform each NON-revised table run's direct formatting to the house table style the same way
            # the clean pipeline does (drop a stray rFonts/spacing/oversize that fights Table Data; keep
            # style/bold/italic/colour and an intentional small size). A run holding masked revision content
            # (a sentinel) is left exactly as authored — its formatting is review history (GPT audit F2).
            def _conform_run_rpr(rm):
                if '\x00' in rm.group(1):
                    return rm.group(0)
                return self._filter_table_rpr(rm.group(1))
            nx = re.sub(r'<w:rPr>(.*?)</w:rPr>', _conform_run_rpr, nx, flags=re.S)
            # First (flat) table row repeats as a header. Nested tables never reach here (handled above).
            fr = re.search(r'<w:tr\b.*?</w:tr>', nx, re.S)
            if fr and '<w:tblHeader' not in fr.group(0):
                row = fr.group(0)
                # insert into an existing trPr, else after the <w:tr ...> open tag (which may carry
                # attributes like w:rsidR — a bare '<w:tr>' replace would silently miss those rows).
                hdr = (row.replace('<w:trPr>', '<w:trPr><w:tblHeader/>', 1) if '<w:trPr>' in row
                       else re.sub(r'(<w:tr\b[^>]*>)', r'\1<w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>', row, count=1))
                nx = nx.replace(row, hdr, 1)
            nx = self._unmask(nx, masks)
            # R5 header repair: on the header row, strip a NON-house direct fill / run size / colour so the
            # Grid Table 4 teal + black-bold header renders — but ONLY on cells with NO tracked change. A header
            # fill that is itself a tracked formatting edit (tcPrChange/ins/del) is a reviewer's in-progress
            # decision: it is PRESERVED and flagged for human review, never silently rewritten.
            nx, hrep, hflag = self._repair_stray_header_formatting(nx, self._locator(i))
            if nx != x:
                self.set(i, nx); cnt += 1
        if cnt:
            self.say('M', -1, f'preserve mode: {cnt} tables set to the LI table style', 'tables')
        if self._table_notes:
            # These notes are a mix: nested tables left untouched AND header cells whose fill was a tracked
            # change (corrected, record preserved). Do not mislabel them all "nested"; each note states why.
            nested = sum(1 for n in self._table_notes if 'nested' in n)
            reasons = (f'{nested} nested, {len(self._table_notes) - nested} tracked header-fill'
                       if nested else 'tracked header-fill corrected, record preserved')
            self.say('M', -1, f'{len(self._table_notes)} table note(s) flagged for human review '
                              f'({reasons}) — see the per-table notes', 'tables-unresolved')

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
            # accept a single- OR multi-level caption number (Table 3-1, Table 3.4.2-1, …); the caption's
            # own text carries the number, so no heading-number simulation is needed to build the key.
            m = re.match(r'(Table|Figure) (\d+(?:\.\d+)*)[-‑‐–](\d+)', t)
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

    # A literal cross-reference: a single- or multi-level Table/Figure number (groups 2 num + 3 seq), or a
    # bare-integer Section reference (groups 4/5). A multi-level "Section 3.4.2" is intentionally NOT matched
    # here — mapping its number to a heading bookmark needs the heading-number simulation (deferred).
    _XREF_RE = re.compile(r'(Table|Figure) (\d+(?:\.\d+)*)[-‑‐–](\d+)|Sections? (\d+)(?!\.\d)(?: and (\d+)(?!\.\d))?')

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
                if mm.group(1):                                   # Figure/Table N-M (single or multi level)
                    key = f'{mm.group(1)} {mm.group(2)}-{mm.group(3)}'
                    if key in caps:
                        out += self._fld(f'REF {caps[key]} \\h', key, 'CrossReference'); count[0] += 1
                    else:
                        out += f'<w:r><w:t xml:space="preserve">{esc(mm.group(0))}</w:t></w:r>'
                else:                                             # Section(s) N [and M]
                    word = 'Sections' if mm.group(0).startswith('Sections') else 'Section'
                    out += f'<w:r><w:t xml:space="preserve">{word} </w:t></w:r>'
                    g3, g4 = mm.group(4), mm.group(5)
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

    @staticmethod
    def verdict_label(status, forced_review=False):
        """An HONEST document-status label for the artifact based on the ACTUAL conformance verdict (issue
        #1 R3): a confirmation to save does not complete verification, so a not-clean/unknown copy is
        labelled UNVERIFIED, never 'conformed and verified'."""
        if status is None:
            return ('UNVERIFIED review copy — conformance verification did NOT complete; this file is NOT a '
                    'verified conformed document.')
        if status.get('blocking'):
            return ('UNVERIFIED review copy — contains formatting changes (numbering, paragraph references, '
                    'definitions or tables) that could not be verified as authorized; NOT a conformed '
                    'reading copy.')
        if not status.get('clean', False):
            return ('Review copy — conforms except for unresolved items that still need a manual look; not '
                    'certified fully clean.')
        return 'Conformed copy — conformance verified clean.'

    def _artifact_label(self, verdict, forced=False):
        """The artifact's document-status: the verdict-based honesty label, with the review-preserving
        framing kept for preserve-mode output (it is a review copy regardless of the conformance verdict)."""
        label = self.verdict_label(verdict, forced)
        if getattr(self, 'disposition', None) == 'preserve':
            return ('Normalized-formatting review copy — tracked changes, comments and authorship '
                    'preserved. ' + label)
        return label

    def _label_review_copy(self):
        """GPT-6 2a: stamp the output as a normalized-formatting review copy (default, pre-verdict)."""
        self._stamp_status(self.REVIEW_COPY_LABEL)

    def _stamp_status(self, label):
        """Write `label` to docProps/core.xml <cp:contentStatus> — the schema's own document-status field,
        shown in Word's file properties — so the file's true status travels with it. core.xml is not a
        story part, so this never affects the preservation gate."""
        core = self.parts.get('docProps/core.xml')
        if not core:
            return
        text = core.decode('utf8')
        status = esc(label)
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
        # the ACTUAL conformance verdict (issue #1 R3): recorded for this save if set, else computed now
        verdict = getattr(self, '_save_verdict', 'unset')
        if verdict == 'unset':
            try:
                verdict = self.conformance_status()
            except Exception:
                verdict = None
        forced = getattr(self, '_save_forced_review', False)
        conformance = None
        if verdict is not None:
            conformance = {'clean': verdict.get('clean'), 'blocking': verdict.get('blocking'),
                           'reason_counts': {k: len(v) for k, v in (verdict.get('reasons') or {}).items() if v}}
        return {
            'tool': 'LI Report Conformer',
            'disposition': self.disposition or 'clean',
            'label': self._artifact_label(verdict, forced),
            'conformance_verdict': conformance,
            'verification_completed': verdict is not None,
            'saved_as_review_only': bool(forced),
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
                # CT_Numbering schema order: every <w:abstractNum> must precede every <w:num>. Word drops
                # ALL numbering when they interleave, so this is an output-invalidating structural error
                # even though the XML is well-formed (the resolver is blind to order).
                if 'word/numbering.xml' in names:
                    num = z.read('word/numbering.xml').decode('utf8', 'replace')
                    abs_last = max([m.start() for m in re.finditer(r'<w:abstractNum\b', num)] or [-1])
                    num_first = min([m.start() for m in re.finditer(r'<w:num\b(?![a-zA-Z])', num)] or [1 << 62])
                    if abs_last > num_first:
                        return False, ('numbering.xml order invalid: an <w:abstractNum> appears after a '
                                       '<w:num> (Word would drop all numbering)')
            return True, 'Output validated'
        except Exception as e:
            return False, str(e)


if __name__ == '__main__':
    tpl, src, dst = sys.argv[1:4]
    c = Conformer(tpl, src); c.run(); c.save(dst)
    if '--log' in sys.argv: json.dump({'mechanical': c.log, 'judgment': c.judgment}, open(sys.argv[sys.argv.index('--log') + 1], 'w'), indent=1)
    print(f'{os.path.basename(src)}: {len(c.log)} mechanical actions, {len(c.judgment)} judgment calls')
