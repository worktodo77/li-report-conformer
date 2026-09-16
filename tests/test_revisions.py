"""Revision ledger + integrity-gate tests (M1.1).

Synthetic fixtures only (no client data). Every 'challenge' test corrupts an output and asserts the
gate goes RED on exactly the failure GPT-6's review requires — a green result proves nothing until
you have watched the check fail on a real defect.
"""
from conformer import revisions as R
from conformer import integrity as I

WNS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
RNS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
ANS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
MCNS = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
NSMAP = (f'xmlns:w="{WNS}" xmlns:r="{RNS}" xmlns:a="{ANS}" xmlns:mc="{MCNS}"')


def doc(body, root_attrs=''):
    return f'<w:document {NSMAP} {root_attrs}><w:body>{body}</w:body></w:document>'.encode('utf8')


def rels(pairs):
    items = ''.join(f'<Relationship Id="{i}" Type="http://x/image" Target="{t}"/>' for i, t in pairs)
    return f'<Relationships xmlns="{PKG}">{items}</Relationships>'.encode('utf8')


# ---- baseline: one paragraph, an insertion (Ann), a deletion (Bob), a format revision (Cy) ----
BODY = (
    '<w:p>'
    '<w:r><w:rPr><w:b/><w:rPrChange w:id="9" w:author="Cy" w:date="2026-01-01T00:00:00Z">'
    '<w:rPr><w:i/></w:rPr></w:rPrChange></w:rPr><w:t xml:space="preserve">The scope was </w:t></w:r>'
    '<w:ins w:id="1" w:author="Ann" w:date="2026-01-02T00:00:00Z"><w:r><w:t>substantially </w:t></w:r></w:ins>'
    '<w:r><w:t>increased</w:t></w:r>'
    '<w:del w:id="2" w:author="Bob" w:date="2026-01-03T00:00:00Z">'
    '<w:r><w:delText xml:space="preserve"> without notice</w:delText></w:r></w:del>'
    '</w:p>'
)


def parts(body=BODY, extra=None):
    p = {'word/document.xml': doc(body)}
    if extra:
        p.update(extra)
    return p


def test_ledger_inventories_structured_payload():
    led = R.Ledger.build(parts())
    revs = {r.kind: r for r in led.revisions}
    assert revs['ins'].payload == (('text', 'substantially '),)
    assert revs['del'].payload == (('deltext', ' without notice'),)
    assert revs['ins'].author == 'Ann' and revs['del'].author == 'Bob'
    assert revs['rPrChange'].author == 'Cy'
    assert set(led.summary()['authors']) == {'Ann', 'Bob', 'Cy'}


def test_gate_passes_on_noop():
    assert R.is_clean(R.diff(R.Ledger.build(parts()), R.Ledger.build(parts())))


def test_detects_lost_edit():
    before = R.Ledger.build(parts())
    after = R.Ledger.build(parts(BODY.replace(
        '<w:del w:id="2" w:author="Bob" w:date="2026-01-03T00:00:00Z">'
        '<w:r><w:delText xml:space="preserve"> without notice</w:delText></w:r></w:del>', '')))
    d = R.diff(before, after)
    assert not R.is_clean(d)
    assert any(r.author == 'Bob' for r in d['lost'])


def test_detects_altered_payload():
    d = R.diff(R.Ledger.build(parts()),
               R.Ledger.build(parts(BODY.replace('substantially ', 'slightly '))))
    assert d['payload_altered'] and not R.is_clean(d)


def test_detects_reattribution():
    d = R.diff(R.Ledger.build(parts()),
               R.Ledger.build(parts(BODY.replace('w:author="Ann"', 'w:author="Imposter"'))))
    assert d['metadata_altered'] and not R.is_clean(d)


# ---- GPT-6 challenge table ----

IMG_BODY = ('<w:p><w:ins w:id="3" w:author="Ann" w:date="D">'
            '<w:r><w:drawing><a:blip r:embed="rId5"/></w:drawing></w:r></w:ins></w:p>')

def _img_parts(png):
    return {'word/document.xml': doc(IMG_BODY),
            'word/_rels/document.xml.rels': rels([('rId5', 'media/image1.png')]),
            'word/media/image1.png': png}

def test_challenge_image_bytes_change_same_target():
    before = R.Ledger.build(_img_parts(b'PNG-v1'))
    after = R.Ledger.build(_img_parts(b'PNG-v2-different-bytes'))
    d = R.diff(before, after)
    assert 'word/media/image1.png' in d['binary_altered']
    assert d['payload_altered']            # the revision's drawing content-hash also moved
    assert not R.is_clean(d)


def test_placement_detects_revision_reorder():
    # Two insertions swapped -> each one's sequence context changes -> placement flagged.
    p1 = ('<w:p><w:ins w:id="1" w:author="A" w:date="D"><w:r><w:t>X</w:t></w:r></w:ins>'
          '<w:ins w:id="2" w:author="A" w:date="D"><w:r><w:t>Y</w:t></w:r></w:ins></w:p>')
    p2 = ('<w:p><w:ins w:id="2" w:author="A" w:date="D"><w:r><w:t>Y</w:t></w:r></w:ins>'
          '<w:ins w:id="1" w:author="A" w:date="D"><w:r><w:t>X</w:t></w:r></w:ins></w:p>')
    d = R.diff(R.Ledger.build(parts(p1)), R.Ledger.build(parts(p2)))
    assert d['placement_altered'] and not R.is_clean(d)


def test_placement_is_robust_to_surrounding_text_conformance():
    # Conforming the prose AROUND a revision (typography, styles) must NOT flag it as moved.
    p1 = ('<w:p><w:r><w:t>He said</w:t></w:r>'
          '<w:ins w:id="1" w:author="A" w:date="D"><w:r><w:t>X</w:t></w:r></w:ins></w:p>')
    p2 = ('<w:p><w:r><w:t xml:space="preserve">He said,  </w:t></w:r>'
          '<w:ins w:id="1" w:author="A" w:date="D"><w:r><w:t>X</w:t></w:r></w:ins></w:p>')
    d = R.diff(R.Ledger.build(parts(p1)), R.Ledger.build(parts(p2)))
    assert R.is_clean(d)
    # KNOWN LIMITATION: a LONE revision relocating within reformattable prose (no sibling revisions
    # or bookmarks) is not detected by sequence-based placement; robustly detecting it needs
    # pre-mutation content ids (deferred). Cross-context and reorder moves ARE detected.


def test_current_props_may_change_when_snapshot_preserved():
    # Applying house formatting changes the CURRENT props (b -> i) while the rPrChange snapshot (the
    # reject target) is untouched. That is the tool's job and must NOT trip the gate.
    after = BODY.replace('<w:rPr><w:b/><w:rPrChange', '<w:rPr><w:i/><w:rPrChange')
    d = R.diff(R.Ledger.build(parts()), R.Ledger.build(parts(after)))
    assert R.is_clean(d), d


def test_challenge_altering_the_reject_snapshot_fails():
    # But changing the RECORDED original (the snapshot inside rPrChange) breaks reject behavior.
    after = BODY.replace('<w:rPrChange w:id="9" w:author="Cy" w:date="2026-01-01T00:00:00Z">'
                         '<w:rPr><w:i/></w:rPr>',
                         '<w:rPrChange w:id="9" w:author="Cy" w:date="2026-01-01T00:00:00Z">'
                         '<w:rPr><w:strike/></w:rPr>')
    d = R.diff(R.Ledger.build(parts()), R.Ledger.build(parts(after)))
    assert d['payload_altered'] and not R.is_clean(d)


def test_challenge_delete_text_during_style_assignment():
    before = [('Normal', 'hello'), ('Normal', 'world')]
    after_ok = [('BodyText', 'hello'), ('BodyText', 'world')]
    after_bad = [('BodyText', 'hello'), ('BodyText', '')]  # text deleted
    assert I.allowed_change_style_only(before, after_ok) == []
    assert I.allowed_change_style_only(before, after_bad)


def test_challenge_broken_namespace_binding():
    W14 = 'http://schemas.microsoft.com/office/word/2010/wordml'
    ok = doc('<w:p/>', root_attrs=f'xmlns:w14="{W14}" mc:Ignorable="w14"')
    broken = ok.replace(f' xmlns:w14="{W14}"'.encode(), b'')  # drop the binding, keep mc:Ignorable
    assert I.namespace_compat_integrity(ok) == []
    assert 'w14' in I.namespace_compat_integrity(broken)


def test_challenge_revisions_only_in_header_block_bypass():
    p = {'word/document.xml': doc('<w:p><w:r><w:t>clean body</w:t></w:r></w:p>'),
         'word/header1.xml': doc('<w:p><w:ins w:id="7" w:author="Ann" w:date="D">'
                                 '<w:r><w:t>edited header</w:t></w:r></w:ins></w:p>')}
    led = R.Ledger.build(p)
    assert led.has_revisions()             # clean-document bypass must be prevented
    assert any(r.part == 'word/header1.xml' for r in led.revisions)


def test_challenge_conflicting_style_import_out_of_scope():
    before = {'word/document.xml': doc('<w:p/>'), 'word/styles.xml': b'<styles>orig</styles>'}
    after = {'word/document.xml': doc('<w:p/>'), 'word/styles.xml': b'<styles>OVERWRITTEN</styles>'}
    # A style pass that declared only document.xml must not have rewritten styles.xml wholesale.
    offenders = I.out_of_scope_preservation(before, after, scope={'word/document.xml'})
    assert 'word/styles.xml' in offenders


# ---- comments & unsupported features ----

def test_detects_lost_comment_and_body_change():
    with_c = {'word/document.xml': doc(
        '<w:p><w:commentRangeStart w:id="5"/><w:r><w:t>x</w:t></w:r>'
        '<w:commentRangeEnd w:id="5"/><w:r><w:commentReference w:id="5"/></w:r></w:p>'),
        'word/comments.xml': (f'<w:comments xmlns:w="{WNS}"><w:comment w:id="5">'
                              '<w:p><w:r><w:t>original note</w:t></w:r></w:p></w:comment></w:comments>').encode()}
    before = R.Ledger.build(with_c)
    lost = R.Ledger.build({'word/document.xml': doc('<w:p><w:r><w:t>x</w:t></w:r></w:p>')})
    assert '5' in R.diff(before, lost)['lost_comments']
    edited = {'word/document.xml': with_c['word/document.xml'],
              'word/comments.xml': with_c['word/comments.xml'].replace(b'original note', b'TAMPERED note')}
    assert '5' in R.diff(before, R.Ledger.build(edited))['comment_body_altered']


# ---- content-stream (allowed-change) adversarial tests, per GPT-6 ----

def _streams(body_a, body_b):
    return R.content_stream(parts(body_a)), R.content_stream(parts(body_b))


def test_stream_catches_lone_revision_move_within_paragraph():
    p1 = ('<w:p><w:r><w:t xml:space="preserve">A </w:t></w:r>'
          '<w:ins w:id="1" w:author="X" w:date="D"><w:r><w:t>Z</w:t></w:r></w:ins>'
          '<w:r><w:t xml:space="preserve"> B</w:t></w:r></w:p>')
    p2 = ('<w:p><w:r><w:t xml:space="preserve">A </w:t></w:r>'
          '<w:r><w:t xml:space="preserve"> B</w:t></w:r>'
          '<w:ins w:id="1" w:author="X" w:date="D"><w:r><w:t>Z</w:t></w:r></w:ins></w:p>')
    assert R.stream_violations(*_streams(p1, p2))   # the placement gap is now closed


def test_stream_catches_untracked_text_deletion_in_comment_range():
    body = ('<w:p><w:commentRangeStart w:id="5"/>'
            '<w:r><w:t xml:space="preserve">The exposure was not material</w:t></w:r>'
            '<w:commentRangeEnd w:id="5"/><w:r><w:commentReference w:id="5"/></w:r></w:p>')
    deleted = body.replace('was not material', 'was material')
    assert R.stream_violations(*_streams(body, deleted))   # the "not" example is caught


def test_stream_catches_moved_comment_boundary():
    body = ('<w:p><w:commentRangeStart w:id="5"/><w:r><w:t>alpha</w:t></w:r>'
            '<w:commentRangeEnd w:id="5"/><w:r><w:t>beta</w:t></w:r>'
            '<w:r><w:commentReference w:id="5"/></w:r></w:p>')
    moved = ('<w:p><w:commentRangeStart w:id="5"/><w:r><w:t>alpha</w:t></w:r>'
             '<w:r><w:t>beta</w:t></w:r><w:commentRangeEnd w:id="5"/>'
             '<w:r><w:commentReference w:id="5"/></w:r></w:p>')
    assert R.stream_violations(*_streams(body, moved))   # end marker moved past 'beta'


def test_stream_allows_typography_but_catches_deletion():
    from conformer.engine import typo_text
    ok = lambda o, n: typo_text(o) == n
    body = '<w:p><w:r><w:t>He said "hi" to not everyone</w:t></w:r></w:p>'
    typo = body.replace('"hi"', '“hi”')
    assert not R.stream_violations(*_streams(body, typo), text_ok=ok)        # authorized edit
    deleted = body.replace('not ', '')
    assert R.stream_violations(*_streams(body, deleted), text_ok=ok)         # deletion still caught


def test_stream_allows_current_formatting_change_under_revision():
    # Normalizing current formatting beneath an unchanged rPrChange is a formatting change: the
    # content stream is identical, so it is permitted (the explicit normalized-copy contract).
    after = BODY.replace('<w:rPr><w:b/><w:rPrChange', '<w:rPr><w:i/><w:rPrChange')
    assert not R.stream_violations(*_streams(BODY, after))


def test_prune_gate_tolerates_page_break_only_protects_column_and_line_breaks():
    # CAP-1: with ignore_page_breaks, removing a manual PAGE break is authorized; a COLUMN break and
    # a LINE break are still protected (their loss is a violation).
    base = ('<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
            '<w:p><w:r><w:br w:type="column"/></w:r></w:p>'
            '<w:p><w:r><w:t>x</w:t><w:br/></w:r></w:p>')
    drop_page = ('<w:p><w:r><w:br w:type="column"/></w:r></w:p>'
                 '<w:p><w:r><w:t>x</w:t><w:br/></w:r></w:p>')
    drop_col = ('<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
                '<w:p><w:r><w:t>x</w:t><w:br/></w:r></w:p>')
    drop_line = ('<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
                 '<w:p><w:r><w:br w:type="column"/></w:r></w:p>'
                 '<w:p><w:r><w:t>x</w:t></w:r></w:p>')
    kw = dict(ignore_structure=True, ignore_page_breaks=True)
    assert not R.stream_violations(*_streams(base, drop_page), **kw)     # page break removal allowed
    assert R.stream_violations(*_streams(base, drop_col), **kw)          # column break protected
    assert R.stream_violations(*_streams(base, drop_line), **kw)         # line break protected
    # and without the flag, even the page break is protected
    assert R.stream_violations(*_streams(base, drop_page), ignore_structure=True)


def test_content_stream_ignores_tab_stops_keeps_content_tabs():
    # A run-level content <w:tab/> IS in the stream; a <w:tabs> tab-STOP definition (pPr formatting)
    # is NOT — so stripping direct tab-stop formatting must not look like deleting a content tab.
    with_stops = ('<w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="900"/>'
                  '<w:tab w:val="left" w:pos="4500"/></w:tabs></w:pPr>'
                  '<w:r><w:tab/><w:t>Signed:</w:t></w:r></w:p>')
    stripped = '<w:p><w:pPr></w:pPr><w:r><w:tab/><w:t>Signed:</w:t></w:r></w:p>'
    assert not R.stream_violations(*_streams(with_stops, stripped))   # tab-stops removed -> allowed
    # but deleting the run-level content tab IS caught
    no_tab = '<w:p><w:pPr></w:pPr><w:r><w:t>Signed:</w:t></w:r></w:p>'
    assert R.stream_violations(*_streams(with_stops, no_tab))


def test_unsupported_revision_is_surfaced_not_dropped():
    body = ('<w:tbl><w:tr><w:tc><w:tcPr>'
            '<w:cellDel w:id="4" w:author="Ann" w:date="D"/></w:tcPr>'
            '<w:p><w:r><w:t>cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    led = R.Ledger.build(parts(body))
    assert led.unsupported and any(u[1] == 'cellDel' for u in led.unsupported)
    assert led.has_revisions()
