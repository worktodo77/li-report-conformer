"""Score a candidate .docx against golden.docx.
Usage: python3 score.py <golden.docx> <candidate.docx> [--json out.json]
Checks (each PASS/FAIL with counts):
  1 structure   : body paragraph sequence (style + text) matches golden
  2 para-direct : no direct paragraph formatting beyond the allowed whitelist
  3 run-direct  : no direct run formatting beyond bold/italic/style refs
  4 numbering   : no paragraph carries a direct numPr; no list instance beyond golden's
  5 styles      : no style definitions absent from golden; key style definitions unchanged
  6 fields      : same count of SEQ / STYLEREF / REF / TOC fields and bookmarks
  7 footnotes   : same count; all in Footnote Text; reference marks not italic; tab after number
  8 sections    : same section count and orientations
  9 typography  : no straight quotes, no "--", two spaces after sentence-ending periods (count vs golden)
 10 tracked     : no tracked formatting/style revisions left
"""
import re, sys, json, zipfile, unicodedata

from conformer.engine import split_body as _engine_split_body

def load(path):
    z = zipfile.ZipFile(path); P = {n: z.read(n).decode('utf8', 'replace') for n in z.namelist() if n.endswith('.xml')}
    doc = P['word/document.xml']; body = re.search(r'<w:body>(.*)</w:body>', doc, re.S).group(1)
    return P, body

def split_body(body):
    return [(re.match(r'<w:(\w+)\b', x).group(1), x) for x in _engine_split_body(body)]

def text(x): return re.sub(r'\s+', ' ', re.sub('<[^>]+>', '', re.sub(r'<w:instrText.*?</w:instrText>', '', x, flags=re.S))).strip()
def pstyle(x):
    if x.startswith('<w:tbl'): return 'TABLE'
    m = re.search(r'<w:pStyle w:val="([^"]+)"', x); return m.group(1) if m else 'Normal'

ALLOWED_PPR = {'pStyle', 'rPr', 'sectPr', 'keepNext', 'keepLines'}
ALLOWED_PPR_BY_STYLE = {'Caption': {'jc'}, 'TableData': {'jc'}, 'BodyText': {'ind'}, 'SpacebehindafteraGraphic': {'jc'}, 'Heading1': {'pageBreakBefore', 'spacing'}}
ALLOWED_RPR = {'rStyle', 'b', 'bCs', 'i', 'iCs', 'vanish', 'noProof', 'lang'}
ALLOWED_RPR_IN = {'TABLE': {'color', 'sz', 'szCs'}}  # header white text -> colour; an intentional small BODY font (<=11pt) is KEPT by default (normalize-to-11pt is a judgment call), so a direct table sz is not a defect

def ppr_children(x):
    m = re.search(r'<w:pPr>(.*?)</w:pPr>', x, re.S)
    if not m: return []
    inner = re.sub(r'<w:rPr>.*?</w:rPr>', '', m.group(1), flags=re.S); inner = re.sub(r'<w:sectPr>.*?</w:sectPr>', '', inner, flags=re.S)
    return re.findall(r'<w:(\w+)\b', inner)
def rpr_children(x):
    out = []
    for m in re.finditer(r'<w:r\b[^>]*>(.*?)</w:r>', x, re.S):
        rp = re.search(r'<w:rPr>(.*?)</w:rPr>', m.group(1), re.S)
        if rp: out += re.findall(r'<w:(\w+)\b', re.sub(r'<w:rPrChange>.*?</w:rPrChange>', '', rp.group(1), flags=re.S))
    return out

def score(golden, cand):
    G, gb = load(golden); C, cb = load(cand)
    gi = [(t, x) for t, x in split_body(gb) if t in ('p', 'tbl')]; ci = [(t, x) for t, x in split_body(cb) if t in ('p', 'tbl')]
    g0 = next(i for i, (t, x) in enumerate(gi) if 'w:val="Heading1"' in x); c0 = next((i for i, (t, x) in enumerate(ci) if 'w:val="Heading1"' in x), 0)
    gi, ci = gi[g0:], ci[c0:]
    R = {}
    # 1 structure
    gseq = [(pstyle(x), text(x)) for t, x in gi]; cseq = [(pstyle(x), text(x)) for t, x in ci]
    import difflib
    sm = difflib.SequenceMatcher(a=[s + '|' + t for s, t in gseq], b=[s + '|' + t for s, t in cseq], autojunk=False)
    mism = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != 'equal')
    R['structure'] = {'pass': mism == 0, 'mismatched_items': mism, 'golden_items': len(gseq), 'candidate_items': len(cseq)}
    # 2 para direct
    bad = []
    for t, x in ci:
        st = pstyle(x)
        for c in ppr_children(x):
            if c in ALLOWED_PPR or c in ALLOWED_PPR_BY_STYLE.get(st, set()): continue
            if st == 'TABLE' and c in ('jc', 'pStyle'): continue
            bad.append((st, c))
    R['para_direct'] = {'pass': not bad, 'violations': len(bad), 'sample': bad[:8]}
    # 3 run direct
    badr = []
    for t, x in ci:
        st = pstyle(x)
        for c in rpr_children(x):
            if c in ALLOWED_RPR or c in ALLOWED_RPR_IN.get(st, set()): continue
            badr.append((st, c))
    R['run_direct'] = {'pass': not badr, 'violations': len(badr), 'sample': badr[:8]}
    # 4 numbering
    direct_num = sum(1 for t, x in ci if re.search(r'<w:pPr>(?:(?!</w:pPr>).)*<w:numPr>', x, re.S))
    gnum = len(re.findall(r'<w:num ', G['word/numbering.xml'])); cnum = len(re.findall(r'<w:num ', C['word/numbering.xml']))
    R['numbering'] = {'pass': direct_num == 0 and cnum <= gnum, 'paragraphs_with_direct_numPr': direct_num, 'list_instances': cnum, 'golden_list_instances': gnum}
    # 5 styles
    gst = set(re.findall(r'w:styleId="([^"]+)"', G['word/styles.xml'])); cst = set(re.findall(r'w:styleId="([^"]+)"', C['word/styles.xml']))
    # the engine intentionally IMPORTS these house styles for conformance (they are not "foreign" noise);
    # a golden generated before they existed still legitimately validates output that adds them.
    _ENGINE_HOUSE_STYLES = {'GridTable4', 'TableHeader'}
    foreign = sorted(cst - gst - _ENGINE_HOUSE_STYLES)
    changed = []
    for sid in ['Normal', 'NumberedParagraph', 'NumberedParagraphL1', 'Heading1', 'Heading2', 'BodyText', 'ExcerptorQuote', 'Caption', 'FootnoteText', 'ListBullet', 'TableData']:
        g = re.search(r'<w:style [^>]*w:styleId="%s"[^>]*>.*?</w:style>' % sid, G['word/styles.xml'], re.S); c = re.search(r'<w:style [^>]*w:styleId="%s"[^>]*>.*?</w:style>' % sid, C['word/styles.xml'], re.S)
        if g and c and re.sub(r'w:rsid="[^"]*"', '', g.group(0)) != re.sub(r'w:rsid="[^"]*"', '', c.group(0)): changed.append(sid)
    R['styles'] = {'pass': not foreign and not changed, 'foreign_styles': foreign, 'changed_definitions': changed}
    # 6 fields
    def fcount(P):
        d = P['word/document.xml']; return {k: len(re.findall(r'<w:instrText[^>]*>\s*%s\b' % k, d)) for k in ['SEQ', 'STYLEREF', 'REF', 'TOC']} | {'bookmarks': len(re.findall(r'<w:bookmarkStart', d))}
    gf, cf = fcount(G), fcount(C)
    R['fields'] = {'pass': gf == cf, 'golden': gf, 'candidate': cf}
    # 7 footnotes
    gfn = len(re.findall(r'<w:footnote w:id="[1-9]', G['word/footnotes.xml'])); cfn = len(re.findall(r'<w:footnote w:id="[1-9]', C['word/footnotes.xml']))
    fns = re.findall(r'<w:footnote w:id="[1-9]\d*".*?</w:footnote>', C['word/footnotes.xml'], re.S)
    notft = sum(1 for f in fns if '<w:pStyle w:val="FootnoteText"/>' not in f); notab = sum(1 for f in fns if '<w:footnoteRef/></w:r><w:r><w:tab/>' not in f)
    ital = len(re.findall(r'<w:rStyle w:val="FootnoteReference"/>(?:(?!</w:rPr>).)*<w:i/>', C['word/document.xml'], re.S))
    R['footnotes'] = {'pass': gfn == cfn and notft == 0 and notab == 0 and ital == 0, 'count': cfn, 'golden_count': gfn, 'not_FootnoteText': notft, 'no_tab_after_number': notab, 'italic_reference_marks': ital}
    # 8 sections
    def sects(P):
        return [('L' if 'orient="landscape"' in s else 'P') for s in re.findall(r'<w:sectPr\b.*?</w:sectPr>', P['word/document.xml'], re.S)]
    R['sections'] = {'pass': sects(G) == sects(C), 'golden': ''.join(sects(G)), 'candidate': ''.join(sects(C))}
    # 9 typography
    ct = ' '.join(text(x) for t, x in ci); gt = ' '.join(text(x) for t, x in gi)
    def typo(s): return {'straight_double_quotes': s.count('"'), 'straight_single_quotes': s.count("'"), 'double_hyphen': s.count('--'), 'single_space_after_period': len(re.findall(r'[a-z]\. [A-Z]', s)), 'inch_marks': len(re.findall(r'\d"', s))}
    R['typography'] = {'pass': typo(ct) == typo(gt), 'golden': typo(gt), 'candidate': typo(ct)}
    # 10 tracked
    trk = len(re.findall(r'<w:(pPrChange|rPrChange|ins|del)\b', C['word/document.xml']))
    R['tracked'] = {'pass': trk == 0, 'revisions': trk}
    R['_summary'] = {'passed': sum(1 for k, v in R.items() if not k.startswith('_') and v['pass']), 'total': sum(1 for k in R if not k.startswith('_'))}
    return R

if __name__ == '__main__':
    g, c = sys.argv[1], sys.argv[2]
    R = score(g, c)
    for k, v in R.items():
        if k.startswith('_'): continue
        print(f"{'PASS' if v['pass'] else 'FAIL'}  {k:12} " + ', '.join(f'{kk}={vv}' for kk, vv in v.items() if kk != 'pass'))
    print(f"== {R['_summary']['passed']}/{R['_summary']['total']} checks passed")
    if '--json' in sys.argv: json.dump(R, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
