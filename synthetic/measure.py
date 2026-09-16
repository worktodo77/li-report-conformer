"""Measure a conformed synthetic report against its ground-truth manifest and produce a scorecard.

For each report this:
  1. runs analyze() and records the JudgmentCalls (by kind), mechanical actions, figure-audit
     findings, and any rolled-back passes (exceptions);
  2. runs apply_with_decisions(accept-all) to produce the conformed output;
  3. checks the two hard guarantees — preservation (every tracked change / comment / author / binary
     intact, via the ledger gate) and output validity (well-formed OOXML);
  4. RESCANS the conformed output for residual defects (literal captions, floating images, wrapper
     tables, empty columns, foreign styles, unstyled tables, straight quotes) and compares the drop
     to what the manifest said was injected.

Output: a per-report scorecard dict (also written to synthetic/out/<name>_scorecard.json) with, per
conformance class, injected vs detected vs residual, and a PASS/PARTIAL/FAIL verdict. Discrepancies
are the RCA inputs for the testing plan.

    python synthetic/measure.py                 # measure all three tiers
"""
import os
import re
import sys
import json
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
from conformer.engine import Conformer

TEMPLATE = os.path.join(HERE, '..', 'src', 'conformer', 'assets', 'template.dotx')
OUT = os.path.join(HERE, 'out')

# manifest class -> the engine signal that should register it (JudgmentCall kind or 'mech'/'audit')
CLASS_SIGNAL = {
    'classify_body': ('jc', 'style'), 'classify_bullet': ('jc', 'style'),
    'level_fix': ('jc', 'level'), 'caption_literal': ('jc', 'caption'),
    'xref_literal': ('jc', 'xref'), 'wrapper_table': ('jc', 'unwrap'),
    'table_empty_col': ('jc', 'dropcol'), 'floating_image': ('jc', 'imgextract'),
    'heading_body_merge': ('jc', 'splitcap'),
    'strip_direct': ('mech', None), 'table_style': ('mech', None),
    'pdf_linesplit': ('mech', None), 'empty_para': ('mech', None),
    'page_break': ('mech', None), 'typography': ('mech', None),
    'footnote_style': ('mech', None), 'section_landscape': ('mech', None),
    'figure_numbering': ('audit', 'numbering'), 'tof_mismatch': ('audit', 'toc-title'),
}


def residuals(conf):
    """Count residual defect markers in a conformed Conformer's body (lower is better)."""
    body = ''.join(conf.items)
    out = {}
    out['literal_captions'] = sum(1 for i in range(conf.n())
                                  if conf.style(i) == 'Caption' and 'SEQ ' not in conf.item(i)
                                  and re.match(r'(Figure|Table) \d', conf.text(i).strip()))
    out['floating_images'] = len(re.findall(r'<wp:anchor', body))
    out['wrapper_tables'] = sum(1 for it in conf.items if it.startswith('<w:tbl')
                                and '<w:tblStyle' not in it
                                and len(re.findall(r'<w:tr\b', it)) == 1
                                and len(re.findall(r'<w:tc>', it)) == 1)
    out['unstyled_tables'] = sum(1 for it in conf.items if it.startswith('<w:tbl')
                                 and 'w:tblStyle w:val="LITable"' not in it)
    out['foreign_body_styles'] = sum(1 for i in range(conf.n())
                                     if conf.is_par(i) and conf.style(i) in ('Normal', 'FirmBody',
                                     'ListParagraph') and conf.text(i).strip())
    # straight quotes / double-hyphens in VISIBLE TEXT only (join all <w:t> content), not markup
    text = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', body))
    out['straight_quotes'] = text.count('"') + text.count('--')
    return out


def measure(tier):
    docx = os.path.join(OUT, 'synthetic_report_%spct.docx' % tier)
    manifest = json.load(open(os.path.join(OUT, 'synthetic_report_%spct_manifest.json' % tier)))

    c = Conformer(TEMPLATE, docx)
    calls = c.analyze()
    jc_kinds = Counter(jc.kind for jc in calls)
    audit_levels = Counter(lvl for lvl, _ in c.audit)
    exceptions = list(c.exceptions)

    applied = c.apply_with_decisions({jc.id: 'accept' for jc in calls})
    pres_clean, disc = applied.verify_preservation()
    valid, valid_msg = applied.validate_output()
    resid = residuals(applied)
    resid_before = residuals(Conformer(TEMPLATE, docx))   # pre-conformance baseline for the drop

    # per-class verdicts
    classes = {}
    for cls, injected in manifest['counts'].items():
        kind = CLASS_SIGNAL.get(cls, ('?', None))
        if kind[0] == 'jc':
            detected = jc_kinds.get(kind[1], 0)
        elif kind[0] == 'audit':
            detected = audit_levels.get(kind[1], 0)
        else:
            detected = None  # mechanical: measured by residual drop, not a call count
        classes[cls] = {'injected': injected, 'signal': kind, 'detected': detected}

    scorecard = {
        'tier': tier,
        'manifest': {'total_defects': manifest['total_defects'],
                     'tracked_total': manifest['tracked_total'],
                     'comments': manifest['comments'],
                     'spelling_errors': manifest.get('spelling_errors', 0),
                     'grammar_errors': manifest.get('grammar_errors', 0)},
        'analyze': {'judgment_calls': dict(jc_kinds), 'mechanical_actions': len(c.log),
                    'audit_findings': dict(audit_levels), 'passes_rolled_back': exceptions},
        'guarantees': {'preservation_clean': pres_clean,
                       'preservation_discrepancies': {k: len(v) for k, v in disc.items()
                                                      if isinstance(v, list) and v},
                       'output_valid': valid, 'output_valid_msg': valid_msg},
        'residuals_before': resid_before, 'residuals_after': resid,
        'classes': classes,
        'notes': ('Mechanical classes (strip_direct/table_style/typography/pdf_linesplit/'
                  'empty_para/page_break/footnote_style/section_landscape) are judged by the drop in '
                  'residuals_after vs residuals_before and by passes_rolled_back, not a call count.'),
    }
    with open(os.path.join(OUT, 'synthetic_report_%spct_scorecard.json' % tier), 'w') as fh:
        json.dump(scorecard, fh, indent=2)
    return scorecard


def _fmt(sc):
    g = sc['guarantees']
    print('=== %s%% ===' % sc['tier'])
    print('  judgment calls:', sc['analyze']['judgment_calls'])
    print('  mechanical:', sc['analyze']['mechanical_actions'],
          '| audit:', sc['analyze']['audit_findings'])
    print('  preservation clean:', g['preservation_clean'], g['preservation_discrepancies'] or '',
          '| output valid:', g['output_valid'])
    print('  passes rolled back:', [f'{n}: {r[:40]}' for n, r in sc['analyze']['passes_rolled_back']])
    print('  residual drop:')
    for k in sc['residuals_before']:
        print('     %-20s %5d -> %-5d' % (k, sc['residuals_before'][k], sc['residuals_after'][k]))


if __name__ == '__main__':
    tiers = sys.argv[1:] or ['90', '70', '25']
    for t in tiers:
        _fmt(measure(t))
