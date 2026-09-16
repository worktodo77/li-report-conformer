"""Stress tests: generate synthetic .docx files with edge-case structures and
run each through the full engine pipeline (analyze → accept-all → validate).

Every scenario must: not crash, produce valid output, and survive a round-trip
through validate_output(). Scores against golden are NOT checked — these
documents are deliberately adversarial, not conformance targets.
"""
import os, re, tempfile, zipfile, textwrap

from conformer.engine import Conformer

ASSETS = os.path.join(os.path.dirname(__file__), '..', 'src', 'conformer', 'assets')
TEMPLATE = os.path.join(ASSETS, 'template.dotx')
KITCHEN_SINK = os.path.join(ASSETS, 'KITCHEN_SINK.docx')


# ── Synthetic document builder ──────────────────────────────────────────────

def _extract_skeleton(source_docx):
    """Extract XML parts (minus body content) from a real .docx to use as a
    skeleton for synthetic documents."""
    parts = {}
    with zipfile.ZipFile(source_docx) as z:
        for name in z.namelist():
            parts[name] = z.read(name)
    doc = parts['word/document.xml'].decode('utf8')
    m = re.search(r'(.*<w:body>)(.*)(</w:body>.*)', doc, re.S)
    return parts, m.group(1), m.group(3)


def _p(style, text, extra_ppr='', extra_rpr=''):
    """Build a single <w:p> element."""
    rpr = f'<w:rPr>{extra_rpr}</w:rPr>' if extra_rpr else ''
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{extra_ppr}</w:pPr>'
        f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p>'
    )


def _tbl(rows, style='LITable'):
    """Build a <w:tbl> with the given rows (list of lists of strings)."""
    ncols = max(len(r) for r in rows)
    grid = '<w:tblGrid>' + '<w:gridCol w:w="2000"/>' * ncols + '</w:tblGrid>'
    trs = []
    for row in rows:
        cells = []
        for cell in row:
            cells.append(
                f'<w:tc><w:tcPr><w:tcW w:w="2000" w:type="dxa"/></w:tcPr>'
                f'<w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
                f'<w:r><w:t>{_esc(cell)}</w:t></w:r></w:p></w:tc>'
            )
        trs.append('<w:tr>' + ''.join(cells) + '</w:tr>')
    return (
        f'<w:tbl><w:tblPr><w:tblStyle w:val="{style}"/>'
        f'<w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        f'{grid}' + ''.join(trs) + '</w:tbl>'
    )


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _build_docx(path, body_items):
    """Write a synthetic .docx to `path` using KITCHEN_SINK's skeleton with
    the given body XML items replacing its content."""
    parts, head, tail = _extract_skeleton(KITCHEN_SINK)
    body = ''.join(body_items)
    parts['word/document.xml'] = (head + body + tail).encode('utf8')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)


# ── Harness ─────────────────────────────────────────────────────────────────

def _run_scenario(name, body_items):
    """Run one scenario through the full pipeline and return (success, detail)."""
    with tempfile.TemporaryDirectory() as tmp:
        inp = os.path.join(tmp, f'{name}.docx')
        out = os.path.join(tmp, f'{name}_out.docx')
        _build_docx(inp, body_items)

        c = Conformer(TEMPLATE, inp)
        calls = c.analyze()

        decisions = {jc.id: 'accept' for jc in calls}
        fresh = c.apply_with_decisions(decisions)
        fresh.save(out)

        valid, msg = fresh.validate_output()
        assert valid, f'[{name}] validate_output failed: {msg}'

        with zipfile.ZipFile(out) as z:
            z.testzip()

        return len(c.log), len(calls)


# ── Scenarios ───────────────────────────────────────────────────────────────

def test_minimal_body():
    """Just one Heading1 and one paragraph — the smallest possible document."""
    mech, judg = _run_scenario('minimal', [
        _p('Heading1', 'Section One'),
        _p('NumberedParagraph', 'This is the entire document.'),
    ])
    assert mech >= 0


def test_headings_only():
    """Six heading levels with no body text."""
    items = []
    for lvl in range(1, 7):
        items.append(_p(f'Heading{lvl}', f'Heading Level {lvl}'))
    _run_scenario('headings_only', items)


def test_deep_nesting():
    """NumberedParagraph → L1 → L2 chain, exercising fix_levels logic."""
    items = [
        _p('Heading1', 'Deep Nesting Test'),
        _p('NumberedParagraph', 'Top-level numbered paragraph:'),
        _p('NumberedParagraphL1', 'Sub-level one'),
        _p('NumberedParagraphL1', 'Sub-level one continued'),
        _p('NumberedParagraphL2', 'Sub-sub-level'),
        _p('NumberedParagraphL2', 'Sub-sub-level continued'),
        _p('NumberedParagraph', 'Back to top level.'),
        _p('NumberedParagraphL2', 'L2 directly under NP — should trigger fix_levels'),
        _p('NumberedParagraphL2', 'L2 continued'),
    ]
    _run_scenario('deep_nesting', items)


def test_long_paragraph():
    """Single paragraph with 10,000 characters."""
    text = 'The quick brown fox jumps over the lazy dog. ' * 222  # ~9,990 chars
    items = [
        _p('Heading1', 'Long Paragraph Test'),
        _p('NumberedParagraph', text),
    ]
    _run_scenario('long_paragraph', items)


def test_many_paragraphs():
    """500 numbered paragraphs — tests performance and correctness at scale."""
    items = [_p('Heading1', 'Scale Test')]
    for i in range(500):
        items.append(_p('NumberedParagraph', f'Paragraph number {i + 1} with some filler text to make it realistic.'))
    _run_scenario('many_paragraphs', items)


def test_unknown_styles():
    """Paragraphs with non-LI styles — should trigger classify judgments."""
    items = [
        _p('Heading1', 'Unknown Styles Test'),
        _p('BodyTextIndent', 'This style is not in the LI template.'),
        _p('ListParagraph', 'ListParagraph without numbering.'),
        _p('Normal', 'Normal paragraph that should be reclassified.'),
        _p('Quote', 'A quote in an unknown style.'),
        _p('IntenseQuote', 'An intense quote.'),
    ]
    _, judg = _run_scenario('unknown_styles', items)
    assert judg > 0, 'Unknown styles should produce judgment calls'


def test_many_tables():
    """Multiple tables with varying column counts."""
    items = [_p('Heading1', 'Tables Test')]
    items.append(_tbl([['A', 'B'], ['1', '2'], ['3', '4']]))
    items.append(_p('NumberedParagraph', 'Between tables.'))
    items.append(_tbl([['X', 'Y', 'Z'], ['a', 'b', 'c']]))
    items.append(_p('NumberedParagraph', 'After tables.'))
    items.append(_tbl([['Solo']]))
    _run_scenario('many_tables', items)


def test_table_with_empty_columns():
    """Table where one column is entirely empty — engine should drop it."""
    items = [
        _p('Heading1', 'Empty Column Test'),
        _tbl([['Header', '', 'Data'], ['Row 1', '', 'Val 1'], ['Row 2', '', 'Val 2']]),
    ]
    mech, _ = _run_scenario('empty_columns', items)


def test_tracked_changes():
    """Paragraphs with tracked formatting changes — should be reverted."""
    tracked_p = (
        '<w:p><w:pPr><w:pStyle w:val="NumberedParagraph"/>'
        '<w:pPrChange w:id="100" w:author="Test"><w:pPr>'
        '<w:pStyle w:val="BodyText"/></w:pPr></w:pPrChange>'
        '</w:pPr><w:r><w:t>Paragraph with tracked style change.</w:t></w:r></w:p>'
    )
    items = [
        _p('Heading1', 'Tracked Changes Test'),
        tracked_p,
        _p('NumberedParagraph', 'Normal paragraph after tracked change.'),
    ]
    mech, _ = _run_scenario('tracked_changes', items)
    assert mech > 0, 'Tracked changes should produce mechanical fixes'


def test_manual_page_breaks():
    """Paragraphs that are just manual page breaks — should be removed."""
    break_p = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    items = [
        _p('Heading1', 'Page Break Test'),
        _p('NumberedParagraph', 'Before break.'),
        break_p,
        _p('NumberedParagraph', 'After break.'),
        break_p,
        break_p,
        _p('NumberedParagraph', 'After two breaks.'),
    ]
    mech, _ = _run_scenario('page_breaks', items)
    assert mech > 0, 'Page breaks should be removed'


def test_empty_paragraphs():
    """Empty numbered/Normal paragraphs interspersed — should be pruned."""
    items = [
        _p('Heading1', 'Empty Paragraphs Test'),
        _p('NumberedParagraph', 'Content.'),
        _p('NumberedParagraph', ''),
        _p('Normal', ''),
        _p('NumberedParagraph', ''),
        _p('NumberedParagraph', 'More content.'),
        _p('Normal', ''),
    ]
    mech, _ = _run_scenario('empty_paragraphs', items)
    assert mech > 0, 'Empty paragraphs should be pruned'


def test_excerpt_merge():
    """Adjacent ExcerptorQuote paragraphs that look like PDF line breaks."""
    items = [
        _p('Heading1', 'Excerpt Merge Test'),
        _p('NumberedParagraph', 'The contract states:'),
        _p('ExcerptorQuote', 'The contractor shall provide all labor and materials necessary for the'),
        _p('ExcerptorQuote', 'completion of the work described herein.'),
        _p('ExcerptorQuote', 'Any deviation from the specifications must be approved in writing.'),
        _p('NumberedParagraph', 'End of excerpt.'),
    ]
    _, judg = _run_scenario('excerpt_merge', items)


def test_short_titlecase_promotion():
    """Short title-case NumberedParagraphs that should be promoted to headings."""
    items = [
        _p('Heading1', 'Introduction'),
        _p('NumberedParagraph', 'Some content here.'),
        _p('NumberedParagraph', 'Delay Analysis'),
        _p('NumberedParagraph', 'More content here about delays.'),
        _p('NumberedParagraph', 'Cost Impacts'),
        _p('NumberedParagraph', 'The cost impacts are as follows.'),
    ]
    _, judg = _run_scenario('titlecase_promotion', items)


def test_unicode_typography():
    """Content with straight quotes, ligatures, and double hyphens that the
    typography pass should normalize."""
    items = [
        _p('Heading1', 'Typography Test'),
        _p('NumberedParagraph', 'He said "hello" and she said "goodbye". That\'s fine.'),
        _p('NumberedParagraph', 'The date was 05 January 2024 and the measurement was 6".'),
        _p('NumberedParagraph', 'The range is 10--20 and the ﬁrst item is ﬀective.'),
        _p('NumberedParagraph', 'Mr. Smith arrived. Dr. Jones left. The end.'),
    ]
    _run_scenario('typography', items)


def test_caption_fields():
    """Captions that should get SEQ/STYLEREF field rebuilding."""
    items = [
        _p('Heading1', 'Figures and Tables'),
        _p('Caption', 'Table 1-1: Summary of Delays'),
        _tbl([['Item', 'Days'], ['Rain', '15'], ['Material', '30']]),
        _p('NumberedParagraph', 'As shown in Table 1-1 above.'),
        _p('Caption', 'Figure 1-1: Project Timeline'),
        _p('NumberedParagraph', 'See Figure 1-1 for the timeline.'),
    ]
    mech, _ = _run_scenario('caption_fields', items)
    assert mech > 0, 'Captions should be rebuilt with fields'


def test_cross_section_references():
    """Text referencing Section numbers — should become REF fields."""
    items = [
        _p('Heading1', 'Background'),
        _p('NumberedParagraph', 'This is discussed in Section 2 below.'),
        _p('Heading1', 'Analysis'),
        _p('NumberedParagraph', 'As noted in Section 1, the background is important.'),
        _p('NumberedParagraph', 'See Sections 1 and 2 for context.'),
    ]
    _run_scenario('cross_section_refs', items)


def test_one_cell_wrapper_table():
    """A table with a single cell wrapping paragraphs — should be unwrapped."""
    wrapper = (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="9000"/></w:tblGrid>'
        '<w:tr><w:tc><w:tcPr><w:tcW w:w="9000" w:type="dxa"/></w:tcPr>'
        '<w:p><w:pPr><w:pStyle w:val="NumberedParagraph"/></w:pPr>'
        '<w:r><w:t>Wrapped paragraph one.</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:pStyle w:val="NumberedParagraph"/></w:pPr>'
        '<w:r><w:t>Wrapped paragraph two.</w:t></w:r></w:p>'
        '</w:tc></w:tr></w:tbl>'
    )
    items = [
        _p('Heading1', 'Wrapper Table Test'),
        wrapper,
        _p('NumberedParagraph', 'After the wrapper.'),
    ]
    mech, _ = _run_scenario('wrapper_table', items)
    assert mech > 0, 'Single-cell wrapper table should be unwrapped'


def test_direct_formatting_strip():
    """Paragraphs with direct formatting that should be stripped."""
    items = [
        _p('Heading1', 'Direct Formatting Test'),
        _p('NumberedParagraph', 'Bold and italic text.',
           extra_rpr='<w:b/><w:i/>'),
        _p('NumberedParagraph', 'Text with forbidden color.',
           extra_rpr='<w:color w:val="FF0000"/>'),
        _p('NumberedParagraph', 'Text with extra spacing.',
           extra_ppr='<w:spacing w:before="240" w:after="240"/>'),
    ]
    _run_scenario('direct_formatting', items)


def test_all_bullet_variants():
    """All LI bullet styles in sequence."""
    items = [
        _p('Heading1', 'Bullet Variants Test'),
        _p('NumberedParagraph', 'The items are:'),
        _p('ListBullet', 'Top-level bullet'),
        _p('Listbulletasasentence', 'This is a bullet as a sentence with more detail;'),
        _p('Listbulletasasentence', 'and this continues the list; and'),
        _p('Listbulletasasentence', 'this is the final item.'),
        _p('Listbulletunderanumberedlist', 'Bullet under a numbered list'),
        _p('Dashunderabullet', 'Dash under a bullet'),
        _p('NumberedParagraph', 'Back to numbered.'),
    ]
    _run_scenario('bullet_variants', items)


def test_mixed_adversarial():
    """Combines multiple edge cases in a single document — the ultimate
    stress test for interaction between passes."""
    break_p = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    tracked_p = (
        '<w:p><w:pPr><w:pStyle w:val="BodyText"/>'
        '<w:pPrChange w:id="200" w:author="Reviewer"><w:pPr>'
        '<w:pStyle w:val="Normal"/></w:pPr></w:pPrChange>'
        '</w:pPr><w:r><w:t>Tracked change paragraph.</w:t></w:r></w:p>'
    )
    items = [
        _p('Heading1', 'Introduction'),
        tracked_p,
        _p('Normal', 'A normal paragraph that should be reclassified.'),
        _p('NumberedParagraph', ''),
        break_p,
        _p('NumberedParagraph', 'The following table summarizes the data:'),
        _p('Caption', 'Table 1-1: Summary Data'),
        _tbl([['Item', '', 'Value'], ['Alpha', '', '100'], ['Beta', '', '200']]),
        _p('NumberedParagraph', 'As shown in Table 1-1, the values are significant.'),
        _p('Heading2', 'Sub-Analysis'),
        _p('ExcerptorQuote', 'The specification states that the contractor shall provide all'),
        _p('ExcerptorQuote', 'materials and labor as described in the contract documents.'),
        _p('ListParagraph', 'An unknown-style list item.'),
        _p('NumberedParagraph', 'Cost Impacts'),
        _p('NumberedParagraphL1', 'Lead-in for bullets:'),
        _p('ListBullet', 'First bullet'),
        _p('ListBullet', 'Second bullet'),
        _p('NumberedParagraphL2', 'L2 under NP — should promote'),
        _p('NumberedParagraphL2', 'L2 continued'),
        _p('NumberedParagraph', 'He said "we need to finish by 05 January 2025" and the cost was 6".'),
        _p('Heading1', 'Conclusion'),
        _p('NumberedParagraph', 'See Section 1 for background. The delays are summarized in Table 1-1.'),
    ]
    mech, judg = _run_scenario('mixed_adversarial', items)
    assert mech > 0, 'Mixed scenario should produce mechanical fixes'
    assert judg > 0, 'Mixed scenario should produce judgment calls'


def test_footnotes_stress():
    """Document with footnotes in the footnotes.xml part."""
    items = [
        _p('Heading1', 'Footnote Stress Test'),
        _p('NumberedParagraph', 'Text with a footnote reference.'),
        _p('NumberedParagraph', 'More text with another footnote.'),
    ]
    _run_scenario('footnotes', items)


def test_heading_with_body_merged():
    """A heading paragraph with double-space then body text merged in —
    the engine should split it."""
    merged = (
        '<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
        '<w:r><w:t xml:space="preserve">Delay Analysis</w:t></w:r>'
        '<w:r><w:t xml:space="preserve">  </w:t></w:r>'
        '<w:r><w:t xml:space="preserve">The contractor experienced significant delays during the project '
        'due to unforeseen site conditions that were not identified during the pre-construction phase of the work.</w:t></w:r></w:p>'
    )
    items = [
        _p('Heading1', 'Introduction'),
        _p('NumberedParagraph', 'Background.'),
        merged,
        _p('NumberedParagraph', 'After the merged heading.'),
    ]
    _, judg = _run_scenario('heading_body_merged', items)
    assert judg > 0, 'Merged heading+body should produce a split judgment'
