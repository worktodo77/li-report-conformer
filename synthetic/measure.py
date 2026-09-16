"""Score a conformed synthetic report against its per-instance ground-truth manifest.

For each report this:
  1. runs analyze() -> JudgmentCalls (by kind), mechanical actions, figure-audit findings, and any
     rolled-back passes (analyze-stage exceptions);
  2. runs apply_with_decisions(ACCEPT ALL CONFORMANCE SUGGESTIONS) -> the conformed output, and
     captures the fresh conformer's apply-stage exceptions;
  3. SAVES and RE-OPENS the conformed .docx (proves the serialized package round-trips);
  4. checks the two hard guarantees: the engine's preservation gate AND an INDEPENDENT reconciliation
     that every recorded revision id is present in the re-opened output with matching author, plus
     output validity;
  5. scores EACH manifest defect at its locator bookmark against its expected_disposition, assigning
     one of: resolved / expected_hold / missed / incorrectly_changed / unexpected_hold / indeterminate.

It then evaluates the plan's pass criteria P1-P5, prints and writes a per-report scorecard, and exits
non-zero if any report fails. `python synthetic/measure.py`  (or name specific tiers).
"""
import os
import re
import sys
import json
import zipfile
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
from conformer.engine import Conformer, split_body, RECOMMENDED

TEMPLATE = os.path.join(HERE, '..', 'src', 'conformer', 'assets', 'template.dotx')
OUT = os.path.join(HERE, 'out')

# manifest class -> JudgmentCall kind that should register a NON-tracked instance (for P2 detection).
DETECT_KIND = {'classify_body': 'style', 'classify_bullet': 'style', 'level_fix': 'level',
               'caption_literal': 'caption', 'xref_literal': 'xref', 'wrapper_table': 'unwrap',
               'table_empty_col': 'dropcol', 'floating_image': 'imgextract',
               'heading_body_merge': 'splitcap'}


def _reopen(applied):
    path = os.path.join(tempfile.mkdtemp(), 'conformed.docx')
    applied.save(path)
    z = zipfile.ZipFile(path)
    doc = z.read('word/document.xml').decode('utf8')
    fns = z.read('word/footnotes.xml').decode('utf8') if 'word/footnotes.xml' in z.namelist() else ''
    body = re.search(r'<w:body>(.*)</w:body>', doc, re.S).group(1)
    items = split_body(body)
    bm = {}
    for it in items:
        for name in re.findall(r'<w:bookmarkStart[^>]*w:name="([^"]*)"', it):
            bm[name] = it
    return path, doc, fns, items, bm


def _text(item):
    return re.sub(r'<[^>]+>', '', re.sub(r'<w:instrText.*?</w:instrText>', '', item, flags=re.S))


def _fn_style(fns, fid):
    m = re.search(r'<w:footnote w:id="%s">.*?<w:pStyle w:val="([^"]+)"' % fid, fns, re.S)
    return m.group(1) if m else None


def _find_item(loc, bm, items):
    """Locate an instance by its bookmark, or — for a 'text:snippet' locator (used where a bookmark
    would itself change the outcome, e.g. the merge pass) — by the paragraph containing the text."""
    if loc.startswith('text:'):
        snip = loc[5:]
        for it in items:
            if snip in _text(it):
                return it
        return None
    return bm.get(loc)


def score_instance(d, bm, items, fns, applied):
    """Return a verdict for one defect instance at its locator."""
    disp = d['expected_disposition']
    loc = d['locator']
    item = _find_item(loc, bm, items)
    data = d.get('data', {})

    def present(pred):
        return 'resolved' if pred else 'missed'

    # audit classes are advisory findings, handled by the caller (need the audit list)
    if disp == 'audit_flag':
        return 'audit'   # resolved/missed decided by caller from the audit findings

    if disp == 'removed':                      # non-tracked prune: the paragraph should be gone
        return 'resolved' if loc not in bm else 'missed'

    if disp == 'footnote_restyled':
        return present(_fn_style(fns, data.get('fid')) == 'FootnoteText')

    if disp == 'portrait_restored':
        return 'resolved' if any('section break' in e.get('msg', '') or 'landscape' in e.get('msg', '')
                                 for e in applied.log) else 'missed'

    if item is None:
        return 'indeterminate'                 # locator vanished unexpectedly

    if disp == 'hold':
        # the protected instance must be UNCHANGED; check the class-specific property still holds
        held = _hold_intact(d, item, fns)
        return 'expected_hold' if held else 'incorrectly_changed'

    # change dispositions -----------------------------------------------------
    if disp == 'restyle_to_LI':
        m = re.search(r'<w:pStyle w:val="([^"]+)"', item)
        return present(m and m.group(1) not in ('Normal', 'FirmBody', 'ListParagraph'))
    if disp == 'strip_direct_formatting':
        return present(data.get('gone_marker', '') not in item)
    if disp == 'set_LITable':
        return present('w:tblStyle w:val="LITable"' in item)
    if disp == 'columns_dropped':
        return present(len(re.findall(r'<w:gridCol', item)) < 5)
    if disp == 'unwrapped':
        return present(not item.startswith('<w:tbl'))
    if disp == 'inline':
        return present('<wp:anchor' not in item)
    if disp == 'fielded':
        return present('SEQ ' in item)
    if disp == 'split':
        return present(data.get('body_marker', 'ZZZ') not in item)
    if disp == 'merged':
        return present(len(_text(item)) >= data.get('min_len', 10 ** 9))
    if disp == 'typography_applied':
        return present('"' not in _text(item))
    return 'indeterminate'


def _hold_intact(d, item, fns):
    cls = d['cls']; data = d.get('data', {})
    if cls == 'strip_direct':
        return 'Calibri' in item or 'FF0000' in item
    if cls == 'typography':
        return '"' in _text(item)
    if cls in ('empty_para', 'page_break'):
        return True                             # the paragraph is still present (locator found)
    if cls == 'heading_body_merge':
        return 'must be split out' in item
    if cls == 'wrapper_table':
        return item.startswith('<w:tbl')
    if cls == 'floating_image':
        return '<wp:anchor' in item
    if cls == 'caption_literal':
        return 'SEQ ' not in item
    if cls == 'table_empty_col':
        return len(re.findall(r'<w:gridCol', item)) == 5
    if cls == 'pdf_linesplit':
        return len(_text(item)) < data.get('first_half_len', 0) + 20   # not merged into a longer para
    if cls == 'footnote_style':
        return _fn_style(fns, data.get('fid')) != 'FootnoteText'
    return True


def measure(tier):
    docx = os.path.join(OUT, 'synthetic_report_%s.docx' % tier)
    man = json.load(open(os.path.join(OUT, 'synthetic_report_%s_manifest.json' % tier)))

    c = Conformer(TEMPLATE, docx)
    calls = c.analyze()
    jc_kinds = Counter(jc.kind for jc in calls)
    audit_levels = Counter(lvl for lvl, _ in c.audit)
    analyze_exc = list(c.exceptions)

    applied = c.apply_with_decisions({jc.id: 'accept' for jc in calls})
    apply_exc = list(applied.exceptions)
    pres_clean, disc = applied.verify_preservation()
    valid, valid_msg = applied.validate_output()
    path, doc, fns, items, bm = _reopen(applied)

    # independent preservation reconciliation (not the engine's own gate)
    story = doc + fns
    missing_revs = []
    for rev in man['revisions']:
        rid, author = str(rev['id']), rev['author']
        if not (re.search(r'w:id="%s"[^>]*w:author="%s"' % (re.escape(rid), re.escape(author)), story)
                or re.search(r'w:author="%s"[^>]*w:id="%s"' % (re.escape(author), re.escape(rid)), story)):
            missing_revs.append(rid)

    # per-instance scoring
    verdicts = Counter()
    per_class = {}
    audit_class_seen = {'figure_numbering': audit_levels.get('numbering', 0) > 0,
                        'tof_mismatch': audit_levels.get('toc-title', 0) > 0
                                        or audit_levels.get('toc-orphan', 0) > 0}
    incorrectly_changed = []
    for d in man['defects']:
        v = score_instance(d, bm, items, fns, applied)
        if v == 'audit':
            v = 'resolved' if audit_class_seen.get(d['cls']) else 'missed'
        verdicts[v] += 1
        per_class.setdefault(d['cls'], Counter())[v] += 1
        if v == 'incorrectly_changed':
            incorrectly_changed.append(d['id'])

    # criteria ---------------------------------------------------------------
    non_tracked_detected = {}
    for cls, kind in DETECT_KIND.items():
        injected = sum(1 for d in man['defects']
                       if d['cls'] == cls and d['revision_relation'] == 'unrelated')
        non_tracked_detected[cls] = {'injected': injected, 'detected': jc_kinds.get(kind, 0),
                                     'ok': jc_kinds.get(kind, 0) >= injected}
    p1 = pres_clean and valid and not missing_revs
    p2 = all(v['ok'] for v in non_tracked_detected.values())
    p3 = verdicts['missed'] == 0
    p5 = (audit_class_seen['figure_numbering'] and audit_class_seen['tof_mismatch']) \
        if any(d['cls'] in ('figure_numbering', 'tof_mismatch') for d in man['defects']) else True
    # P4: every rolled-back pass is explained (a known expected-hold class or an RCA note)
    p4_unexplained = [e for e in analyze_exc + apply_exc
                      if not ('_prune_preserving' in e[0] or 'caption' in e[0] or 'xref' in e[0]
                              or 'unwrap' in e[0] or 'dropcol' in e[0])]

    if not p1:
        verdict = 'FAIL'
    elif p2 and p3 and p5 and not p4_unexplained and not incorrectly_changed:
        verdict = 'PASS'
    else:
        verdict = 'PARTIAL'

    scorecard = {
        'tier': tier, 'verdict': verdict, 'quality': man['computed_quality'],
        'guarantees': {'preservation_clean': pres_clean, 'output_valid': valid,
                       'independent_reconciliation_missing_revisions': missing_revs,
                       'preservation_discrepancies': {k: len(v) for k, v in disc.items()
                                                      if isinstance(v, list) and v}},
        'analyze': {'judgment_calls': dict(jc_kinds), 'mechanical_actions': len(c.log),
                    'audit_findings': dict(audit_levels)},
        'exceptions': {'analyze_stage': analyze_exc, 'apply_stage': apply_exc,
                       'unexplained': p4_unexplained},
        'per_instance_verdicts': dict(verdicts),
        'per_class': {k: dict(v) for k, v in per_class.items()},
        'incorrectly_changed': incorrectly_changed,
        'criteria': {'P1_guarantees': p1, 'P2_detection': p2, 'P3_no_missed': p3,
                     'P4_exceptions_explained': not p4_unexplained, 'P5_audit': p5},
        'detection': non_tracked_detected,
    }
    with open(os.path.join(OUT, 'synthetic_report_%s_scorecard.json' % tier), 'w') as fh:
        json.dump(scorecard, fh, indent=2)
    return scorecard


def _fmt(sc):
    print('=== %-7s  %s  (quality %.3f) ===' % (sc['tier'], sc['verdict'], sc['quality']))
    g = sc['guarantees']
    print('  P1 guarantees: preservation=%s valid=%s indep_recon_missing=%d'
          % (g['preservation_clean'], g['output_valid'],
             len(g['independent_reconciliation_missing_revisions'])))
    print('  per-instance verdicts:', sc['per_instance_verdicts'])
    if sc['incorrectly_changed']:
        print('  !! INCORRECTLY CHANGED (protected content modified):', sc['incorrectly_changed'])
    print('  criteria:', sc['criteria'])
    if sc['exceptions']['unexplained']:
        print('  !! unexplained rolled-back passes:', sc['exceptions']['unexplained'])
    miss = {k: v for k, v in sc['per_class'].items() if v.get('missed')}
    if miss:
        print('  missed by class:', miss)


if __name__ == '__main__':
    tiers = sys.argv[1:] or ['clean', 'low', 'medium', 'high']
    fail = False
    for t in tiers:
        sc = measure(t)
        _fmt(sc)
        fail = fail or sc['verdict'] == 'FAIL'
    sys.exit(1 if fail else 0)
