"""Unit tests for the numbering/style reference graph (conformer.numbering.NumberingGraph): it must
resolve the list a paragraph ACTUALLY uses (direct or style-based), through basedOn / lvlOverride /
numStyleLink, and by meaning (numFmt) rather than by numeric id."""
from conformer.numbering import NumberingGraph

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _num(*abstracts_and_nums):
    return f'<w:numbering {W}>' + ''.join(abstracts_and_nums) + '</w:numbering>'


def _abs(aid, lvl0_fmt, lvl0_text='%1.', extra=''):
    return (f'<w:abstractNum w:abstractNumId="{aid}">{extra}'
            f'<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="{lvl0_fmt}"/>'
            f'<w:lvlText w:val="{lvl0_text}"/></w:lvl></w:abstractNum>')


def _numinst(nid, aid, overrides=''):
    return f'<w:num w:numId="{nid}"><w:abstractNumId w:val="{aid}"/>{overrides}</w:num>'


def _styles(*styles):
    return f'<w:styles {W}>' + ''.join(styles) + '</w:styles>'


def _style(sid, based=None, numId=None, ilvl='0'):
    b = f'<w:basedOn w:val="{based}"/>' if based else ''
    npr = f'<w:pPr><w:numPr><w:ilvl w:val="{ilvl}"/><w:numId w:val="{numId}"/></w:numPr></w:pPr>' if numId else ''
    return f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{sid}"/>{b}{npr}</w:style>'


def test_direct_numpr_resolves_format():
    g = NumberingGraph(_num(_abs('7', 'decimal'), _numinst('3', '7')), _styles())
    assert g.effective_format('3', '0') == 'decimal'
    assert g.is_bullet('3', '0') is False


def test_style_based_numbering_no_direct_numpr():
    # paragraph carries NO direct numPr; its list comes from the style — the case the old engine missed
    g = NumberingGraph(_num(_abs('7', 'decimal'), _numinst('13', '7')),
                       _styles(_style('NumberedParagraph', numId='13')))
    assert g.style_numpr('NumberedParagraph') == ('13', '0')
    assert g.paragraph_numbering(None, None, 'NumberedParagraph') == ('13', '0')
    assert g.effective_format('13', '0') == 'decimal'


def test_basedon_inheritance():
    g = NumberingGraph(_num(_abs('7', 'decimal'), _numinst('13', '7')),
                       _styles(_style('Base', numId='13'), _style('Child', based='Base')))
    assert g.style_numpr('Child') == ('13', '0')


def test_numid_collision_same_id_different_meaning():
    # THE core insight: numId 18 is a decimal list in one package, a bullet list in another. A name/id
    # comparison would call them equal; resolution by numFmt does not.
    doc = NumberingGraph(_num(_abs('9', 'bullet'), _numinst('18', '9')), _styles())
    tpl = NumberingGraph(_num(_abs('2', 'decimal'), _numinst('18', '2')), _styles())
    assert doc.effective_format('18', '0') == 'bullet'
    assert tpl.effective_format('18', '0') == 'decimal'


def test_lvl_override_changes_format_and_start():
    ov = ('<w:lvlOverride w:ilvl="0"><w:startOverride w:val="5"/>'
          '<w:lvl w:ilvl="0"><w:numFmt w:val="upperRoman"/><w:lvlText w:val="%1)"/></w:lvl></w:lvlOverride>')
    g = NumberingGraph(_num(_abs('7', 'decimal'), _numinst('3', '7', ov)), _styles())
    lv = g.resolve_level('3', '0')
    assert lv['numFmt'] == 'upperRoman'      # override wins over the abstract's decimal
    assert lv['start'] == '5'


def test_num_style_link_chain():
    # abstractNum A has no levels but links to a style whose num points at abstractNum B (with levels)
    a_link = ('<w:abstractNum w:abstractNumId="20"><w:numStyleLink w:val="ListNumber"/></w:abstractNum>')
    b = _abs('21', 'decimal')
    g = NumberingGraph(_num(a_link, b, _numinst('40', '20'), _numinst('9', '21')),
                       _styles(_style('ListNumber', numId='9')))
    assert g.effective_format('40', '0') == 'decimal'


def test_missing_definition_returns_none():
    g = NumberingGraph(_num(), _styles())
    assert g.effective_format('99', '0') is None
    assert g.paragraph_numbering(None, None, 'Nope') is None


def test_raw_blocks_available_for_import():
    g = NumberingGraph(_num(_abs('7', 'decimal'), _numinst('3', '7')), _styles())
    assert 'w:abstractNumId="7"' in g.raw_abstract('7')
    assert 'w:numId="3"' in g.raw_num('3')
    assert g.abstract_of('3') == '7'
    assert 7 in g.used_abstract_ids() and 3 in g.used_num_ids()
