"""Package-integrity checks that the revision ledger cannot establish on its own (GPT-6 review).

A matching ledger is a necessary test, not a proof of preservation — a ledger cannot detect what it
never recorded. These independent checks cover:
  * XML outside a pass's declared mutation scope stays byte-identical;
  * namespace / markup-compatibility bindings (mc:Ignorable, mc:Choice/@Requires) stay bound;
  * a pass changes ONLY what it declared (allowed-change), so a faulty legacy pass cannot delete an
    ordinary sentence while the revision ledger stays green.
"""
import re

_NS_DECL = re.compile(r'xmlns:([A-Za-z_][\w.\-]*)\s*=')
_IGNORABLE = re.compile(r'\bmc:Ignorable\s*=\s*"([^"]*)"')
_REQUIRES = re.compile(r'\bRequires\s*=\s*"([^"]*)"')


def out_of_scope_preservation(before_parts, after_parts, scope):
    """Parts NOT named in `scope` must be byte-identical before vs after. Returns the offenders
    (changed, added, or removed out-of-scope parts)."""
    scope = set(scope)
    offenders = []
    for name in set(before_parts) | set(after_parts):
        if name in scope:
            continue
        if before_parts.get(name) != after_parts.get(name):
            offenders.append(name)
    return sorted(offenders)


def namespace_compat_integrity(xml_bytes):
    """Every prefix referenced by mc:Ignorable / Requires must be declared somewhere in the part.
    Returns the list of unbound prefixes (empty == OK). Catches a broken compatibility binding that
    still parses as XML."""
    try:
        text = xml_bytes.decode('utf8', 'replace')
    except Exception:
        return ['<decode-error>']
    declared = set(_NS_DECL.findall(text))
    referenced = set()
    for group in _IGNORABLE.findall(text) + _REQUIRES.findall(text):
        referenced.update(p for p in group.split() if p)
    return sorted(referenced - declared)


def all_namespace_integrity(parts):
    """Run namespace_compat_integrity across every story/xml part; returns {part: [unbound...]}."""
    out = {}
    for name, data in parts.items():
        if name.endswith('.xml'):
            unbound = namespace_compat_integrity(data)
            if unbound:
                out[name] = unbound
    return out


# ---------------------------------------------------------------- allowed-change gate
def paragraph_texts(items, para_style):
    """(style, normalized-text) per body paragraph — the observable a style pass must not change
    except for style. `para_style`/`para_text` are supplied by the caller (engine helpers)."""
    return [(para_style(i), t) for i, t in items]


def allowed_change_style_only(before, after):
    """Gate for a style-assignment pass: the ONLY permitted difference between the before/after
    paragraph views is the style label. `before`/`after` are lists of (style, text) tuples.

    Returns a list of violations: text changes, added/removed paragraphs, or reordering — anything
    a style pass is not allowed to do. An empty list == the pass changed only styles."""
    violations = []
    if len(before) != len(after):
        violations.append(f'paragraph count changed: {len(before)} -> {len(after)}')
        return violations
    for i, ((_, bt), (_, at)) in enumerate(zip(before, after)):
        if bt != at:
            violations.append(f'text changed at paragraph {i}: {bt[:40]!r} -> {at[:40]!r}')
    return violations
