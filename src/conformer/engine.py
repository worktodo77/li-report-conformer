"""LI report conformer: repair a damaged report so it conforms to the LI template and guidelines.
Usage: python3 conform.py <template.dotx> <input.docx> <output.docx> [--log log.json]

Mechanical repairs (deterministic): style/numbering parts restored from the template; foreign
styles mapped to LI styles; direct paragraph/run formatting stripped except a whitelist;
duplicate list instances removed; wrapper tables unwrapped; tables restyled to LI Table; floating
pictures made inline; footnotes normalised; tracked formatting revisions reverted; typography
(smart quotes, en dashes, sentence spacing, dates); section orientation repaired; captions and
cross-references rebuilt as fields; missing bookmarks restored.
Judgment repairs (heuristic, logged with reason): unstyled paragraph classification
(numbered paragraph / list / excerpt), PDF line-merge, merged or demoted headings, list levels
out of sequence.
"""
import re, os, sys, json, zipfile

# ---------------------------------------------------------------- shared helpers (same as corrupt.py)
def split_body(body):
    items = []; i = 0
    while i < len(body):
        m = re.match(r'<w:(p|tbl|sectPr|bookmarkStart|bookmarkEnd|sdt)\b', body[i:])
        if not m: raise ValueError(body[i:i+60])
        tag = m.group(1)
        if tag in ('bookmarkStart', 'bookmarkEnd'): e = body.index('/>', i) + 2
        else:
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
def text_of(x): return re.sub('<[^>]+>', '', re.sub(r'<w:instrText.*?</w:instrText>', '', x, flags=re.S))

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
        self.log = []; self.judgment = []
        # candidate style names and numbering formats (needed before we replace the parts)
        self.stname = dict(re.findall(r'<w:style [^>]*w:styleId="([^"]+)"[^>]*><w:name w:val="([^"]+)"', self.styles))
        self.numfmt = {}
        abs_fmt = {}
        for a in re.findall(r'<w:abstractNum w:abstractNumId="(\d+)".*?</w:abstractNum>', self.num, re.S): pass
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
    def say(self, kind, i, msg):
        (self.judgment if kind == 'J' else self.log).append({'item': i, 'text': self.text(i)[:50] if 0 <= i < self.n() else '', 'msg': msg})

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

    def classify(self):
        """Map non-LI paragraph styles to LI styles using numbering, context and text."""
        for i in range(self.n()):
            if not self.is_par(i): continue
            st = self.style(i); x = self.item(i); t = self.text(i).strip()
            if st in RECOMMENDED: continue
            if '<w:sectPr' in x: continue
            if not t and '<w:drawing>' not in x: continue
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
                self.say('J', i, f'{st} bulleted paragraph -> {new} (level {lvl}, length {len(t)}, follows {pst})')
            elif runs_i and ind and int(ind.group(1)) >= 700 and not np_:
                new = 'ExcerptorQuote'; self.say('J', i, f'{st} italic indented paragraph -> Excerpt or Quote')
            elif not np_ and ((ptxt.endswith(':') and (t.endswith(';') or t.endswith('; and'))) or (pst == 'Listbulletasasentence' and (t.endswith(';') or t.endswith('; and') or (ptxt.endswith('; and') and t.endswith('.'))))):
                new = 'Listbulletasasentence'; self.say('J', i, f'{st} item after a colon lead-in ending with ";" -> List bullet as a sentence')
            else:
                new = 'NumberedParagraph'; self.say('J', i, f'{st} body paragraph -> Numbered Paragraph')
            self.set_style(i, new)

    def merge_pdf_lines(self):
        i = 0
        while i < self.n() - 1:
            if self.is_par(i) and self.style(i) == 'ExcerptorQuote' and self.is_par(i + 1) and self.style(i + 1) == 'ExcerptorQuote':
                a, b = self.text(i).rstrip(), self.text(i + 1).strip()
                if not re.search(r'[.!?:;"\u201d]$', a) or a.endswith('-'):
                    joined = (a[:-1] + b) if a.endswith('-') and b[:1].islower() else (a + ' ' + b)
                    self.set(i, re.sub(r'(<w:r\b.*)</w:p>', '', self.item(i), flags=re.S).split('</w:pPr>')[0] + '</w:pPr>' + f'<w:r><w:t xml:space="preserve">{esc(joined)}</w:t></w:r></w:p>')
                    del self.items[self.b0 + i + 1]; self.say('J', i, 'joined PDF line-break paragraphs into one excerpt'); continue
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
                    head_x = self.item(i)[:m.start()] + '</w:p>'; rest = self.item(i)[m.end():]
                    body_x = '<w:p><w:pPr><w:pStyle w:val="NumberedParagraph"/></w:pPr>' + rest
                    self.set(i, head_x); self.items.insert(self.b0 + i + 1, body_x); self.say('J', i, 'split body text that had been merged into a heading paragraph')
        for i in range(self.n()):
            if not self.is_par(i) or self.style(i) != 'NumberedParagraph': continue
            t = self.text(i).strip(); words = t.split()
            if 1 <= len(words) <= 6 and not re.search(r'[.;:,!?]$', t) and all(w[:1].isupper() or w.lower() in ('the', 'of', 'and', 'a', 'an', 'in', 'to', 'for', 'or') for w in words) and not re.search(r'\d', t):
                j = self.prev_par(i)
                while j >= 0 and self.style(j) not in HEADINGS: j = self.prev_par(j)
                lvl = self.style(j) if j >= 0 else 'Heading2'
                if lvl == 'Heading1': lvl = 'Heading2'
                self.set_style(i, lvl); self.say('J', i, f'short title-case numbered paragraph promoted to {lvl}')

    def fix_levels(self):
        for i in range(self.n()):
            if not self.is_par(i): continue
            st = self.style(i)
            if st == 'NumberedParagraphL2':
                p = self.prev_par(i)
                if p >= 0 and self.style(p) == 'NumberedParagraph':
                    k = i
                    while k < self.n() and self.style(k) == 'NumberedParagraphL2': self.set_style(k, 'NumberedParagraphL1'); k += 1
                    self.say('J', i, 'sub-level list started at L2 under a numbered paragraph; promoted run to L1')
            if st == 'NumberedParagraphL1' and self.text(i).strip().endswith(':') and i + 1 < self.n() and self.style(i + 1) in ('ListBullet', 'Listbulletasasentence'):
                self.set_style(i, 'NumberedParagraph'); self.say('J', i, 'L1 lead-in followed by List Bullet items promoted to Numbered Paragraph')

    def strip_direct(self):
        i = 0
        while i < self.n():
            x = self.item(i)
            if not self.is_par(i): i += 1; continue
            st = self.style(i)
            if '<w:sectPr' not in x and st in NUMBERED and not self.text(i).strip() and '<w:drawing>' not in x:
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
            # leading tabs / nbsp / empty runs
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

    def fix_figures(self):
        for i in range(self.n()):
            x = self.item(i)
            if '<wp:anchor' not in x: continue
            x = re.sub(r'<wp:anchor[^>]*>.*?(<wp:extent[^>]*/>)(?:.*?)(<wp:docPr[^>]*/>)(?:.*?)(<a:graphic .*?</a:graphic>)</wp:anchor>', r'<wp:inline distT="0" distB="0" distL="0" distR="0">\1\2\3</wp:inline>', x, flags=re.S)
            self.set(i, x); self.say('M', i, 'floating picture converted to inline')

    def fix_footnotes(self):
        def fix(m):
            f = m.group(0)
            f = re.sub(r'<w:p\b[^>]*>(<w:pPr>.*?</w:pPr>)?', '<w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>', f, count=1, flags=re.S)
            f = re.sub(r'(<w:footnoteRef/></w:r>)<w:r>(?:<w:rPr>.*?</w:rPr>)?<w:t xml:space="preserve"> +</w:t></w:r>', r'\1<w:r><w:tab/></w:r>', f, flags=re.S)
            if '<w:footnoteRef/></w:r><w:r><w:tab/>' not in f: f = f.replace('<w:footnoteRef/></w:r>', '<w:footnoteRef/></w:r><w:r><w:tab/></w:r>', 1)
            f = re.sub(r'<w:rPr>(.*?)</w:rPr>', lambda r: '<w:rPr>' + ''.join(cx for t2, cx in children(r.group(1)) if t2 in ('rStyle', 'i', 'b')) + '</w:rPr>', f, flags=re.S)
            return f
        self.fn = re.sub(r'<w:footnote w:id="[1-9]\d*".*?</w:footnote>', fix, self.fn, flags=re.S)
        self.say('M', -1, 'footnotes normalised (Footnote Text, tab after number, direct formatting removed)')

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
        MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December'
        for i in range(self.n()):
            if not self.is_par(i): continue
            x = self.item(i)
            def fix(m):
                t = m.group(2)
                t = re.sub(r'(\d)"', r'\1-inch', t)
                t = re.sub(r'(^|[\s(\[])"', '\\1\u201c', t); t = t.replace('"', '\u201d')
                t = re.sub(r"(^|[\s(\[])'", '\\1\u2018', t); t = t.replace("'", '\u2019')
                t = re.sub(r'(\w)--(\w)', '\\1\u2013\\2', t)
                t = re.sub(r'([a-z\)])\. ([A-Z])', r'\1.  \2', t)
                t = re.sub(r'\b0(\d) (%s)' % MONTHS, r'\1 \2', t)
                t = t.replace('\ufb00', 'ff').replace('\ufb01', 'fi').replace('\ufb02', 'fl')
                return m.group(1) + t + m.group(3)
            nx = re.sub(r'(<w:t(?: xml:space="preserve")?>)([^<]*)(</w:t>)', fix, x)
            if nx != x: self.set(i, nx)
        self.say('M', -1, 'typography normalised (smart quotes, en dashes, sentence spacing, dates, ligatures)')

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

    def save(self, path):
        doc = normalize(self.head + ''.join(self.items) + self.tail)
        self.parts['word/document.xml'] = doc.encode('utf8'); self.parts['word/styles.xml'] = self.styles.encode('utf8')
        self.parts['word/numbering.xml'] = self.num.encode('utf8'); self.parts['word/footnotes.xml'] = normalize(self.fn).encode('utf8')
        self.parts['word/settings.xml'] = self.settings.encode('utf8')
        if os.path.exists(path): os.remove(path)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            for n_, b in self.parts.items(): z.writestr(n_, b)

    def run(self):
        self.revert_tracked_formatting(); self.unwrap_and_prune(); self.classify(); self.merge_pdf_lines()
        self.fix_headings(); self.fix_levels(); self.strip_direct(); self.fix_tables(); self.fix_figures()
        self.fix_footnotes(); self.rebuild_fields(); self.typography(); self.fix_sections(); self.replace_parts()

if __name__ == '__main__':
    tpl, src, dst = sys.argv[1:4]
    c = Conformer(tpl, src); c.run(); c.save(dst)
    if '--log' in sys.argv: json.dump({'mechanical': c.log, 'judgment': c.judgment}, open(sys.argv[sys.argv.index('--log') + 1], 'w'), indent=1)
    print(f'{os.path.basename(src)}: {len(c.log)} mechanical actions, {len(c.judgment)} judgment calls')
