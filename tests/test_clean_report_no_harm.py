"""Do-no-harm regressions from a beta run on a nearly-conformed, revision-free report: the engine flattened
bulleted lists inside quotations into one paragraph (deleting footnote references with them), and dropped the
document-local list instances those bullets used. All fixtures here are synthetic."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402

PPR = '<w:pPr><w:pStyle w:val="ExcerptorQuote"/></w:pPr>'


def _ex(runs, ppr=PPR):
    return '<w:p>' + ppr + runs + '</w:p>'


def _r(t, rpr=''):
    return f'<w:r>{rpr}<w:t xml:space="preserve">{t}</w:t></w:r>'


# ------------------------------------------------------------------ what is (not) a PDF line split
def test_lowercase_continuation_is_a_pdf_split():
    assert Conformer._is_pdf_split_pair(_ex(_r('The contractor shall complete the works')),
                                        _ex(_r('within the time stated.')))


def test_short_title_like_lines_are_not_merged():
    # no terminal punctuation is NOT evidence: list items / titles inside a quotation lack it too
    assert not Conformer._is_pdf_split_pair(_ex(_r('Basic Design')), _ex(_r('Detailed Design')))


def test_list_items_are_never_merged():
    num = '<w:pPr><w:pStyle w:val="ExcerptorQuote"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="55"/></w:numPr></w:pPr>'
    assert not Conformer._is_pdf_split_pair(_ex(_r('minimise changes to the layout'), num),
                                            _ex(_r('and keep the footprint'), num))


def test_a_footnote_field_or_break_vetoes_the_merge():
    a = _ex(_r('the works shall be completed'))
    for extra in ('<w:r><w:footnoteReference w:id="3"/></w:r>', '<w:r><w:fldChar w:fldCharType="begin"/></w:r>',
                  '<w:r><w:br/></w:r>', '<w:bookmarkStart w:id="1" w:name="x"/>'):
        assert not Conformer._is_pdf_split_pair(_ex(_r('the works shall be completed') + extra),
                                                _ex(_r('within the time stated.')))
        assert not Conformer._is_pdf_split_pair(a, _ex(extra + _r('within the time stated.')))


def test_different_paragraph_properties_veto_the_merge():
    ind = '<w:pPr><w:pStyle w:val="ExcerptorQuote"/><w:ind w:left="1440"/></w:pPr>'
    assert not Conformer._is_pdf_split_pair(_ex(_r('the works shall be completed')),
                                            _ex(_r('within the time stated.'), ind))


# ------------------------------------------------------------------ the join keeps every run
def test_join_preserves_runs_and_inserts_one_space():
    a = _ex(_r('The contractor ') + _r('shall', '<w:rPr><w:b/></w:rPr>') + _r(' complete the works  '))
    b = _ex(_r(' within the ') + _r('time', '<w:rPr><w:u w:val="single"/></w:rPr>') + _r(' stated.'))
    out = Conformer._join_split_paragraphs(a, b)
    assert Conformer._para_plain_text(out) == 'The contractor shall complete the works within the time stated.'
    assert '<w:b/>' in out and '<w:u w:val="single"/>' in out      # emphasis survives
    assert out.count('<w:p>') == 1 and out.count('</w:p>') == 1 and out.count('<w:pPr>') == 1


def test_join_removes_a_line_wrap_hyphen():
    out = Conformer._join_split_paragraphs(_ex(_r('the sub-con-')), _ex(_r('tractor shall proceed.')))
    assert Conformer._para_plain_text(out) == 'the sub-contractor shall proceed.'


# ------------------------------------------------------------------ direct list instances survive the part swap
OLD_NUM = ('<w:numbering>'
           '<w:abstractNum w:abstractNumId="7"><w:nsid w:val="AA"/><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/>'
           '<w:lvlText w:val="o"/></w:lvl></w:abstractNum>'
           '<w:num w:numId="1"><w:abstractNumId w:val="7"/></w:num>'
           '<w:num w:numId="55"><w:abstractNumId w:val="7"/></w:num></w:numbering>')
TPL_NUM = ('<w:numbering>'
           '<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/>'
           '<w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
           '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
           '<w:num w:numId="2"><w:abstractNumId w:val="0"/></w:num></w:numbering>')


def _para(numid):
    return ('<w:p><w:pPr><w:pStyle w:val="ExcerptorQuote"/><w:numPr><w:ilvl w:val="0"/>'
            f'<w:numId w:val="{numid}"/></w:numPr></w:pPr><w:r><w:t>item</w:t></w:r></w:p>')


def test_dangling_direct_list_instance_is_reimported_under_a_fresh_id():
    c = Conformer.__new__(Conformer)
    c.items = [_para(55), _para(55), _para(1)]
    c.fn = '<w:footnotes/>'
    c.num = TPL_NUM
    c.say = lambda *a, **k: None
    c._carry_direct_list_instances(OLD_NUM)
    # numId 55 did not exist in the template part -> re-imported as a NEW instance (3), both paragraphs
    # repointed together (one list stays one list); numId 1 exists in the template and is left alone
    assert c._carried_instances == {'55': '3'}
    assert c.items[0].count('<w:numId w:val="3"/>') == 1 and c.items[1].count('<w:numId w:val="3"/>') == 1
    assert '<w:numId w:val="1"/>' in c.items[2]
    new_num = re.search(r'<w:num w:numId="3">.*?</w:num>', c.num, re.S).group(0)
    aid = re.search(r'<w:abstractNumId w:val="(\d+)"', new_num).group(1)
    assert aid == '1'                                           # fresh abstract id, not the old 7
    ab = re.search(r'<w:abstractNum w:abstractNumId="1">.*?</w:abstractNum>', c.num, re.S).group(0)
    assert 'w:val="bullet"' in ab and '<w:nsid' not in ab
    # CT_Numbering order: every abstractNum precedes every num (Word drops ALL numbering otherwise)
    assert c.num.rindex('<w:abstractNum ') < c.num.index('<w:num ')


def test_nothing_is_imported_when_every_reference_resolves():
    c = Conformer.__new__(Conformer)
    c.items = [_para(1), _para(2)]
    c.fn = '<w:footnotes/>'
    c.num = TPL_NUM
    c.say = lambda *a, **k: None
    c._carry_direct_list_instances(OLD_NUM)
    assert c.num == TPL_NUM and not getattr(c, '_carried_instances', None)
