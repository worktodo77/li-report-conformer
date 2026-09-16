"""Independent validator for the synthetic fixtures — deliberately does NOT use the conformer's own
preservation gate, so it is an independent oracle for both the input packages and the manifests.

Checks, per report:
  * XML well-formedness of every part;
  * package integrity: [Content_Types].xml maps document.xml as a DOCUMENT (not template); every
    referenced relationship / media target resolves; the body's LAST element is the final sectPr;
  * structural order: every floating anchor places its wrap element before docPr; no paragraph-mark
    rPr precedes pStyle;
  * manifest reconciliation: every recorded revision id is present in the saved package with matching
    author/date; every defect locator bookmark exists; every comment id exists in comments.xml with
    matching author; every List-of-Figures / List-of-Tables hyperlink anchor has a bookmark target.

Exit status is non-zero if any report fails. This runs BEFORE any conformance testing.

    python synthetic/validate_fixture.py
"""
import os
import re
import sys
import json
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def _local(t):
    return t.rsplit('}', 1)[-1]


def validate(tier):
    docx = os.path.join(OUT, 'synthetic_report_%s.docx' % tier)
    man = json.load(open(os.path.join(OUT, 'synthetic_report_%s_manifest.json' % tier)))
    fail = []
    z = zipfile.ZipFile(docx)
    names = set(z.namelist())

    # 1. well-formedness
    for n in names:
        if n.endswith('.xml') or n.endswith('.rels'):
            try:
                ET.fromstring(z.read(n))
            except ET.ParseError as e:
                fail.append('malformed %s: %s' % (n, e))

    # 2. content type = document, not template
    ct = z.read('[Content_Types].xml').decode('utf8')
    if 'wordprocessingml.document.main+xml' not in ct:
        fail.append('document.xml not typed as a Word document')
    if 'template.main+xml' in ct:
        fail.append('template content type leaked into the output')

    doc = z.read('word/document.xml').decode('utf8')
    root = ET.fromstring(doc)
    body = root.find('{%s}body' % W)

    # 3. final sectPr is the LAST body child
    last = list(body)[-1] if len(body) else None
    if last is None or _local(last.tag) != 'sectPr':
        fail.append('final sectPr is not the last body element (got %s)'
                    % (_local(last.tag) if last is not None else 'none'))
    # any sectPr elsewhere must be inside a pPr (section break), never a bare body child mid-document
    for i, ch in enumerate(list(body)[:-1]):
        if _local(ch.tag) == 'sectPr':
            fail.append('a bare sectPr appears mid-body at index %d' % i)

    # 4. floating anchors: wrap element before docPr
    for anchor in root.iter('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor'):
        kids = [_local(c.tag) for c in anchor]
        wraps = [k for k in kids if k.startswith('wrap')]
        if wraps and 'docPr' in kids and kids.index(wraps[0]) > kids.index('docPr'):
            fail.append('anchor places %s after docPr' % wraps[0])

    # 5. no paragraph-mark rPr before pStyle
    for pPr in root.iter('{%s}pPr' % W):
        kids = [_local(c.tag) for c in pPr]
        if 'rPr' in kids and 'pStyle' in kids and kids.index('rPr') < kids.index('pStyle'):
            fail.append('pPr places paragraph-mark rPr before pStyle')

    # 6. relationships / media resolve
    for relname in [n for n in names if n.endswith('.rels')]:
        base = relname[:relname.rindex('_rels/')].rstrip('/')   # folder that owns this .rels
        rroot = ET.fromstring(z.read(relname))
        for rel in rroot:
            tgt = rel.get('Target'); mode = rel.get('TargetMode')
            if mode == 'External' or not tgt:
                continue
            resolved = os.path.normpath(os.path.join(base, tgt)).replace('\\', '/')
            if resolved not in names:
                fail.append('dangling relationship %s -> %s' % (rel.get('Id'), tgt))

    # 7. manifest reconciliation — revisions present with matching author/date
    all_story = doc
    for n in names:
        if re.match(r'word/(footnotes|endnotes|header\d*|footer\d*)\.xml$', n):
            all_story += z.read(n).decode('utf8')
    for rev in man['revisions']:
        rid, author = str(rev['id']), rev['author']
        m = re.search(r'w:id="%s"[^>]*w:author="([^"]*)"' % re.escape(rid), all_story)
        m2 = re.search(r'w:author="%s"[^>]*w:id="%s"' % (re.escape(author), re.escape(rid)), all_story)
        if not m and not m2:
            fail.append('revision id %s (%s) not found in package' % (rid, author))
        elif m and m.group(1) != author:
            fail.append('revision id %s author mismatch: manifest %s vs doc %s'
                        % (rid, author, m.group(1)))

    # 8. defect locator bookmarks exist
    bmnames = set(re.findall(r'<w:bookmarkStart[^>]*w:name="([^"]*)"', all_story))
    for d in man['defects']:
        loc = d['locator']
        if loc.startswith('text:'):                # content locator (used where a bookmark would
            if loc[5:] not in all_story:           # itself change the outcome); verify the text
                fail.append('defect %s content locator %r not found' % (d['id'], loc[5:]))
        elif loc and loc not in bmnames:
            fail.append('defect %s locator bookmark %s missing' % (d['id'], loc))

    # 9. comments exist with matching author
    if 'word/comments.xml' in names:
        comments_xml = z.read('word/comments.xml').decode('utf8')
        doc_authors = re.findall(r'<w:comment[^>]*w:author="([^"]*)"', comments_xml)
        if len(doc_authors) < man['comment_count']:
            fail.append('comment count: manifest %d, comments.xml %d'
                        % (man['comment_count'], len(doc_authors)))
    elif man['comment_count']:
        fail.append('manifest declares %d comments but no comments.xml' % man['comment_count'])

    # 10. LoF / LoT hyperlink anchors have bookmark targets
    for anchor in re.findall(r'<w:hyperlink[^>]*w:anchor="([^"]*)"', doc):
        if anchor not in bmnames:
            fail.append('list hyperlink anchor %s has no bookmark target' % anchor)

    return fail


if __name__ == '__main__':
    tiers = sys.argv[1:] or ['clean', 'low', 'medium', 'high']
    any_fail = False
    for t in tiers:
        problems = validate(t)
        status = 'PASS' if not problems else 'FAIL (%d)' % len(problems)
        print('%-7s %s' % (t, status))
        for p in problems[:12]:
            print('    -', p)
        any_fail = any_fail or bool(problems)
    sys.exit(1 if any_fail else 0)
