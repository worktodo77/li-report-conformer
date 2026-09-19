"""Full-pipeline regressions for the GPT audit findings (packages a real document from the bundled
template so the WHOLE Conformer.run() is exercised, not a single helper). No client data."""
import os
import re
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer            # noqa: E402
from conformer import tablespec                    # noqa: E402

_TPL = Path(__file__).resolve().parents[1] / 'src' / 'conformer' / 'assets' / 'template.dotx'

_HEADING = ('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>INTRODUCTION</w:t></w:r></w:p>')


def _table(body_sz='18'):
    """A clean two-row table: a header row + a body row at a smaller (body_sz) font."""
    hdr = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
           '<w:r><w:t>Head</w:t></w:r></w:p></w:tc></w:tr>')
    body = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="{body_sz}"/></w:rPr><w:t>data</w:t></w:r></w:p></w:tc></w:tr>')
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="dxa"/>'
            '<w:tblLook w:val="04A0"/></w:tblPr><w:tblGrid><w:gridCol w:w="5000"/></w:tblGrid>'
            + hdr + body + '</w:tbl>')


def _package(tmp_path, body):
    with ZipFile(_TPL) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts['[Content_Types].xml'] = parts['[Content_Types].xml'].replace(
        b'wordprocessingml.template.main+xml', b'wordprocessingml.document.main+xml')
    xml = parts['word/document.xml'].decode('utf-8')
    sect = re.findall(r'<w:sectPr\b.*?</w:sectPr>', xml, re.S)[-1]
    parts['word/document.xml'] = re.sub(
        r'<w:body>.*</w:body>', lambda _: '<w:body>' + body + sect + '</w:body>', xml, flags=re.S
    ).encode('utf-8')
    src = tmp_path / 'in.docx'
    with ZipFile(src, 'w', ZIP_DEFLATED) as z:
        for n, data in parts.items():
            z.writestr(n, data)
    return str(src), str(_TPL)


def test_f1_clean_path_keeps_table_header_style(tmp_path):
    """F1: the clean pipeline added TableHeader in fix_tables() then replace_parts() wiped it, so the
    output referenced a style it no longer defined (Word rendered 12pt) and still verdicted CLEAN."""
    src, tpl = _package(tmp_path, _HEADING + _table())
    c = Conformer(tpl, src)
    c.run()
    hdr_row = re.search(r'<w:tbl>.*?<w:tr\b.*?</w:tr>', ''.join(c.items), re.S).group(0)
    assert '<w:pStyle w:val="TableHeader"/>' in hdr_row        # header uses the 10pt style
    assert 'w:styleId="TableHeader"' in c.styles               # ...and the style is DEFINED in the output


def test_f1_verifier_flags_header_paragraph_style_missing_from_styles():
    """Defense in depth: a header cell paragraph referencing a style absent from styles.xml is a defect,
    not a silent pass."""
    styles = '<w:styles><w:style w:type="paragraph" w:styleId="TableData"><w:rPr><w:sz w:val="22"/></w:rPr></w:style></w:styles>'
    tbl = ('<w:tbl><w:tblPr><w:tblStyle w:val="GridTable4"/><w:tblLook w:val="04A0" w:firstRow="1"/></w:tblPr>'
           '<w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:tcPr>'
           '<w:shd w:val="clear" w:color="auto" w:fill="B6DDE8"/></w:tcPr>'
           '<w:p><w:pPr><w:pStyle w:val="TableHeader"/></w:pPr><w:r><w:t>H</w:t></w:r></w:p></w:tc></w:tr>'
           '<w:tr><w:tc><w:tcPr/><w:p><w:r><w:t>d</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    kinds = {i['kind'] for i in tablespec.effective_table_issues(tbl, styles_xml=styles)}
    assert 'header-style-missing' in kinds


def test_f5_broken_references_gate_clean():
    """F5: a known broken cross-reference (missing target) is a genuine unresolved defect that a field
    refresh cannot fix, so the verdict must not be CLEAN."""
    c = Conformer.__new__(Conformer)
    c.audit = [('xref-target-missing', '3 cross-reference(s) point to a missing bookmark')]
    empty = {'numbering_flips': [], 'definition_integrity_violations': [],
             'tables_failing_effective_format': [], 'tables_review': []}
    empty_u = {'rolled_back_passes': [], 'tables_needing_review': [], 'tables_unresolved': []}
    c.outcome_report = lambda: {'conformance': empty, 'unresolved': empty_u}
    st = c.conformance_status()
    assert st['clean'] is False
    assert st['reasons']['broken_references']


_FMT_REV = ('<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
            '<w:r><w:rPr><w:b/><w:rPrChange w:id="9" w:author="Rev" w:date="2026-01-01T00:00:00Z">'
            '<w:rPr/></w:rPrChange></w:rPr><w:t xml:space="preserve">a run made bold under review</w:t></w:r></w:p>')


def test_f2_formatting_only_revision_routes_to_preserve_and_is_kept(tmp_path):
    """F2: a document whose ONLY revision is a formatting change (rPrChange, no insert/delete) used to route
    to the clean pipeline, whose revert_tracked_formatting() deleted the record — the review history was
    silently lost and preservation failed. It must now take the single history-preserving path, keep the
    rPrChange, and verify preservation clean."""
    src, tpl = _package(tmp_path, _HEADING + _FMT_REV)
    c = Conformer(tpl, src)
    c.run()
    assert c.disposition == 'preserve'                       # formatting-only revision -> preserving path
    assert '<w:rPrChange' in ''.join(c.items)                # the review record is preserved, not reverted
    clean, disc = c.verify_preservation()
    assert clean, disc


def _combined_text(c):
    return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', ''.join(c.items)))


def test_t1_quote_prefix_inside_insertion_protects_settled_date(tmp_path):
    """GPT re-review T1: an opening quote inside a tracked INSERTION must still protect the adjacent
    SETTLED date — the insertion is read-only context, not erased. The quoted date stays verbatim; the
    insertion text is byte-exact and preservation is clean."""
    body = ('<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
            '<w:ins w:id="88" w:author="Rev" w:date="2026-01-01T00:00:00Z">'
            '<w:r><w:t xml:space="preserve">He said "</w:t></w:r></w:ins>'
            '<w:r><w:t>03 April 2011</w:t></w:r>'
            '<w:r><w:t>".</w:t></w:r></w:p>')
    src, tpl = _package(tmp_path, _HEADING + body)
    c = Conformer(tpl, src)
    c.run()
    assert c.disposition == 'preserve'
    assert '03 April 2011' in _combined_text(c)          # leading zero preserved (date NOT normalized)
    assert 'He said "' in _combined_text(c)              # the inserted prefix is byte-exact
    clean, disc = c.verify_preservation()
    assert clean, disc


def test_t1_from_prefix_inside_insertion_suppresses_range_endash(tmp_path):
    body = ('<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
            '<w:ins w:id="89" w:author="Rev" w:date="2026-01-01T00:00:00Z">'
            '<w:r><w:t xml:space="preserve">the period from  </w:t></w:r></w:ins>'
            '<w:r><w:t>2017-2019</w:t></w:r></w:p>')
    src, tpl = _package(tmp_path, _HEADING + body)
    c = Conformer(tpl, src)
    c.run()
    assert '–' not in ''.join(c.items)               # no en dash: the inserted "from" is context
    assert '2017-2019' in _combined_text(c)


def test_t2_split_sentence_does_not_roll_back_the_typography_pass(tmp_path):
    """GPT re-review T2: a sentence boundary split across runs must NOT make the whole typography pass roll
    back in the preserving pipeline (undoing valid fixes elsewhere). The unrelated date paragraph is still
    normalized and there is no typography exception."""
    body = (_FMT_REV +                                    # selects the preserving pipeline
            '<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
            '<w:r><w:t>First sentence.</w:t></w:r>'
            '<w:r><w:t xml:space="preserve"> Next sentence.</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
            '<w:r><w:t>on 03 April 2011</w:t></w:r></w:p>')
    src, tpl = _package(tmp_path, _HEADING + body)
    c = Conformer(tpl, src)
    c.run()
    assert c.disposition == 'preserve'
    assert 'on 3 April 2011' in _combined_text(c)          # the unrelated date fix survived (no rollback)
    assert not any(name == 'typography' for name, _ in getattr(c, 'exceptions', []))


def test_f4_clean_pipeline_keeps_small_body_font_and_offers_normalization(tmp_path):
    """F4: a clean (untracked) table whose body is an intentional small font (9pt) must SURVIVE the clean
    pipeline — fix_tables used to strip every run size, silently forcing 11pt and never surfacing the
    normalize-to-11pt judgment call. Now the size is kept and the class-level offer appears."""
    src, tpl = _package(tmp_path, _HEADING + _table(body_sz='18'))   # 18 half-points = 9pt body
    c = Conformer(tpl, src)
    c.run()
    assert c.disposition != 'preserve'                               # no revisions -> clean pipeline
    tbl = next(x for x in c.items if x.startswith('<w:tbl'))
    body_row = re.findall(r'<w:tr\b.*?</w:tr>', tbl, re.S)[1]
    assert '<w:sz w:val="18"/>' in body_row                          # small font kept, not force-normalized
    assert any(j.kind == 'table-body-size' for j in c.pending_judgments)   # offered in the clean pipeline


def test_f4_clean_pipeline_strips_oversized_body_font(tmp_path):
    """The same keep must not preserve an OVERSIZED body run — a 14pt (sz 28) body run drops its size so
    Table Data's 11pt applies, and no small-font offer is made."""
    src, tpl = _package(tmp_path, _HEADING + _table(body_sz='28'))   # 28 half-points = 14pt body
    c = Conformer(tpl, src)
    c.run()
    tbl = next(x for x in c.items if x.startswith('<w:tbl'))
    body_row = re.findall(r'<w:tr\b.*?</w:tr>', tbl, re.S)[1]
    assert '<w:sz w:val="28"/>' not in body_row                      # oversized size stripped -> 11pt
    assert not any(j.kind == 'table-body-size' for j in c.pending_judgments)


def _table_header_charstyle():
    """A table whose header run wears a size-bearing character style (rStyle=BigChar, sz 32 = 16pt)."""
    hdr = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
           '<w:r><w:rPr><w:rStyle w:val="BigChar"/><w:sz w:val="32"/></w:rPr><w:t>Head</w:t></w:r></w:p></w:tc></w:tr>')
    body = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
            '<w:r><w:t>data</w:t></w:r></w:p></w:tc></w:tr>')
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="dxa"/>'
            '<w:tblLook w:val="04A0"/></w:tblPr><w:tblGrid><w:gridCol w:w="5000"/></w:tblGrid>'
            + hdr + body + '</w:tbl>')


def _header_run(tbl):
    row = re.findall(r'<w:tr\b.*?</w:tr>', tbl, re.S)[0]
    return re.search(r'<w:r\b.*?</w:r>', row, re.S).group(0)


def test_r1_header_character_style_size_is_overridden_to_10pt(tmp_path):
    """GPT re-review R1: a header run with a size-bearing character style rendered larger than the house
    10pt while conformance reported CLEAN (the repair stripped the direct size but the rStyle size won).
    The repair now forces an explicit 10pt (sz 20) on header runs, which overrides any character style."""
    src, tpl = _package(tmp_path, _HEADING + _table_header_charstyle() + _FMT_REV)   # _FMT_REV -> preserve path
    c = Conformer(tpl, src)
    c.run()
    tbl = next(x for x in c.items if x.startswith('<w:tbl'))
    hrun = _header_run(tbl)
    assert '<w:sz w:val="20"/>' in hrun          # explicit house 10pt now wins over the character style
    assert '<w:sz w:val="32"/>' not in hrun       # the 16pt override is gone
    assert c.conformance_status()['clean'] is True


def test_r3_normalize_action_forces_11pt_through_a_revised_paragraph(tmp_path):
    """GPT re-review R3: the reviewer-selected 'normalize table bodies to 11pt' action stripped the direct
    size, exposing a revised paragraph's surviving 12pt Body Text style instead of 11pt, yet reported
    CLEAN. It now sets an explicit 11pt (sz 22) that renders regardless of the surviving style."""
    body_ins = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr>'
                '<w:ins w:id="7" w:author="Rev" w:date="2026-01-01T00:00:00Z">'
                '<w:r><w:rPr><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">inserted 9pt data</w:t></w:r></w:ins>'
                '</w:p></w:tc></w:tr>')
    hdr = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
           '<w:r><w:t>Head</w:t></w:r></w:p></w:tc></w:tr>')
    tbl = ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="dxa"/>'
           '<w:tblLook w:val="04A0"/></w:tblPr><w:tblGrid><w:gridCol w:w="5000"/></w:tblGrid>'
           + hdr + body_ins + '</w:tbl>')
    src, tpl = _package(tmp_path, _HEADING + tbl)
    c = Conformer(tpl, src)
    calls = c.analyze()
    tb = next(j for j in calls if j.kind == 'table-body-size')       # the offer is surfaced
    fresh = c.apply_with_decisions({tb.id: 'change:Normalize all table bodies to 11pt'})
    body_row = re.findall(r'<w:tr\b.*?</w:tr>', next(x for x in fresh.items if x.startswith('<w:tbl')), re.S)[1]
    assert '<w:sz w:val="22"/>' in body_row       # explicit 11pt applied to the (still tracked) run
    assert '<w:sz w:val="18"/>' not in body_row    # the 9pt is gone
    assert '<w:ins' in body_row                    # the insertion itself is preserved
    clean, disc = fresh.verify_preservation()
    assert clean, disc


def test_r5_broken_reference_reaches_export_verdicts():
    """GPT re-review R5: the engine gates 'clean' on broken cross-references, but the export/UI summaries
    counted only tables and rolled-back passes, so a broken-reference-only verdict could read NOT CLEAN with
    'Unresolved / exceptions: None'. outcome_verdicts must surface broken references in BOTH lines."""
    from conformer import audit_export as ax

    class _Fresh:
        def outcome_report(self):
            return {'conformance': {}, 'unresolved': {}}
        def conformance_status(self):
            return {'clean': False, 'blocking': False, 'informational': {},
                    'reasons': {'broken_references': ['REF _Ref1 -> missing', 'REF _Ref2 -> missing'],
                                'tables_needing_review': [], 'tables_unresolved': [],
                                'rolled_back_passes': [], 'unresolved_imports': [],
                                'paragraph_reference_unresolved': []}}

    conf_v, unres_v, clean = ax.outcome_verdicts(_Fresh())
    assert clean is False
    assert 'NOT CLEAN' in conf_v and 'broken cross-reference' in conf_v
    assert unres_v != 'None' and 'broken cross-reference' in unres_v


def test_r5_export_verdicts_fail_closed_on_exception():
    from conformer import audit_export as ax

    class _Boom:
        def outcome_report(self):
            return {}
        def conformance_status(self):
            raise RuntimeError('verifier blew up')

    conf_v, unres_v, clean = ax.outcome_verdicts(_Boom())
    assert clean is None and conf_v.startswith('UNKNOWN')
    assert unres_v.startswith('UNKNOWN')                 # S3: unknown != "None" (empty issue list)


def test_s3_export_verdicts_unknown_when_outcome_report_raises():
    # S3: an exception in outcome_report() (outside the old try) must still yield UNKNOWN, not propagate
    from conformer import audit_export as ax

    class _Boom2:
        def outcome_report(self):
            raise RuntimeError('outcome boom')
        def conformance_status(self):
            return {'clean': True, 'blocking': False, 'informational': {}, 'reasons': {}}

    conf_v, unres_v, clean = ax.outcome_verdicts(_Boom2())
    assert clean is None and conf_v.startswith('UNKNOWN') and unres_v.startswith('UNKNOWN')


def test_s3_export_unresolved_counts_imports_and_paragraphs():
    # S3: the export unresolved line must include unresolved imports and uncorresponded paragraphs
    from conformer import audit_export as ax

    class _Fresh:
        def outcome_report(self):
            return {'conformance': {}}
        def conformance_status(self):
            return {'clean': False, 'blocking': False, 'informational': {},
                    'reasons': {'unresolved_imports': ['imp1'], 'paragraph_reference_unresolved': ['p1', 'p2'],
                                'tables_needing_review': [], 'tables_unresolved': [], 'rolled_back_passes': [],
                                'broken_references': []}}

    conf_v, unres_v, clean = ax.outcome_verdicts(_Fresh())
    assert clean is False
    assert unres_v != 'None' and '3 item(s) unresolved' in unres_v       # 1 import + 2 paragraphs


def test_f5_advisory_audits_do_not_gate_clean():
    # a caption-basis / heading-skip advisory (not a broken ref) stays out of the verdict
    c = Conformer.__new__(Conformer)
    c.audit = [('basis-not-h1h2', 'Table caption uses a Heading 3 basis'), ('heading-skip', 'H4 -> H6')]
    empty = {'numbering_flips': [], 'definition_integrity_violations': [],
             'tables_failing_effective_format': [], 'tables_review': []}
    empty_u = {'rolled_back_passes': [], 'tables_needing_review': [], 'tables_unresolved': []}
    c.outcome_report = lambda: {'conformance': empty, 'unresolved': empty_u}
    assert c.conformance_status()['clean'] is True
