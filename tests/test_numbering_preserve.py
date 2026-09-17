"""Regression guard for the numId-collision bug: repairing a style from the template must NOT import
the template's numbering association, or decimal lists silently become bullets (Warhoe 'all numbered
lists are now round bullets')."""
import re
from conformer.engine import Conformer


def test_keep_numpr_preserves_document_numbering():
    # doc style points at numId 13 (its decimal list); template version points at numId 18 (a bullet
    # list in the doc's numbering). The repaired style must keep numId 13.
    old = ('<w:style w:type="paragraph" w:styleId="NumberedParagraph"><w:name w:val="Numbered Paragraph"/>'
           '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="13"/></w:numPr><w:spacing w:after="0"/></w:pPr>'
           '<w:rPr><w:sz w:val="20"/></w:rPr></w:style>')
    new = ('<w:style w:type="paragraph" w:styleId="NumberedParagraph"><w:name w:val="Numbered Paragraph"/>'
           '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="18"/></w:numPr><w:spacing w:after="120"/></w:pPr>'
           '<w:rPr><w:sz w:val="22"/></w:rPr></w:style>')
    out = Conformer._keep_numpr(old, new)
    assert 'w:numId w:val="13"' in out          # document's numbering association kept
    assert 'w:numId w:val="18"' not in out       # template's colliding numId not imported
    assert 'w:after="120"' in out                # other formatting IS repaired from the template
    assert 'w:sz w:val="22"' in out


def test_keep_numpr_drops_template_numbering_when_doc_style_has_none():
    # A non-list style (e.g. Heading1) must not gain a bullet just because the template lists one.
    old = '<w:style w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:keepNext/></w:pPr></w:style>'
    new = ('<w:style w:styleId="Heading1"><w:name w:val="heading 1"/>'
           '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="16"/></w:numPr><w:keepNext/></w:pPr></w:style>')
    out = Conformer._keep_numpr(old, new)
    assert '<w:numPr>' not in out                 # no numbering introduced onto a non-list style
    assert '<w:keepNext/>' in out


def test_keep_numpr_restores_numbering_when_template_def_lacks_ppr():
    old = ('<w:style w:styleId="ListNumber"><w:name w:val="List Number"/>'
           '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="3"/></w:numPr></w:pPr></w:style>')
    new = '<w:style w:styleId="ListNumber"><w:name w:val="List Number"/><w:rPr><w:sz w:val="20"/></w:rPr></w:style>'
    out = Conformer._keep_numpr(old, new)
    assert 'w:numId w:val="3"' in out
    assert '<w:pPr>' in out
