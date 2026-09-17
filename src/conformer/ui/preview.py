"""Document preview: renders a WINDOW of the .docx body as HTML around the target paragraph, which is
highlighted. Only a window is rendered (not the whole doc) so it is fast and never hits QWebEngine's
setHtml size limit; the HTML is loaded from a temp file for the same reason."""
import os, re, tempfile, zipfile
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QSize, QUrl

from conformer.engine import JudgmentCall, text_of

_WINDOW = 25   # paragraphs of context on each side of the target


def _docx_to_html(path, highlight_index=None):
    with zipfile.ZipFile(path) as z:
        doc = z.read('word/document.xml').decode('utf8')

    body = re.search(r'<w:body>(.*)</w:body>', doc, re.S)
    if not body:
        return '<html><body><p>Could not read document body.</p></body></html>'

    content = body.group(1)
    rows = []            # (body_idx, css_class, text)
    para_idx = 0
    b0 = None
    for m in re.finditer(r'<w:p\b[^>]*>(.*?)</w:p>', content, re.S):
        ppr = m.group(1)
        style_m = re.search(r'<w:pStyle w:val="([^"]+)"', ppr)
        style = style_m.group(1) if style_m else 'Normal'
        text = re.sub(r'<[^>]+>', '', re.sub(r'<w:instrText.*?</w:instrText>', '', m.group(0), flags=re.S)).strip()
        if b0 is None and style == 'Heading1':
            b0 = para_idx
        body_idx = (para_idx - b0) if b0 is not None else para_idx
        if text:
            rows.append((body_idx, _style_to_css(style), text))
        para_idx += 1

    # keep only a window around the target (or the head of the doc if no target)
    if highlight_index is not None:
        rows = [r for r in rows if abs(r[0] - highlight_index) <= _WINDOW]
    else:
        rows = rows[:60]

    items = []
    for body_idx, css_class, text in rows:
        hi = (highlight_index is not None and body_idx == highlight_index)
        hs = (' style="background-color:#fff29a; border-left:3px solid #f59e0b; padding-left:8px;"'
              if hi else '')
        anchor = ' id="target"' if hi else ''
        items.append(f'<div class="{css_class}"{hs}{anchor}>{_html_esc(text)}</div>')

    html_body = '\n'.join(items) or '<div class="normal">(No renderable text near this paragraph.)</div>'
    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
    font-family: "Public Sans", "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
    color: #1c2733;
    background: #faf9f6;
    padding: 20px;
    line-height: 1.5;
    max-width: 700px;
    margin: 0 auto;
}}
.heading1 {{ font-size: 18px; font-weight: 700; margin: 24px 0 8px; color: #1f3a5f; }}
.heading2 {{ font-size: 15px; font-weight: 700; margin: 20px 0 6px; color: #1f3a5f; }}
.heading3 {{ font-size: 14px; font-weight: 600; margin: 16px 0 4px; color: #1f3a5f; }}
.numbered {{ margin: 6px 0; padding-left: 24px; }}
.list {{ margin: 4px 0; padding-left: 40px; }}
.excerpt {{ margin: 8px 0; padding-left: 40px; font-style: italic; color: #66707a; }}
.caption {{ text-align: center; font-size: 12px; font-weight: 600; margin: 8px 0; }}
.normal {{ margin: 6px 0; }}
.footnote {{ font-size: 11px; color: #66707a; }}
</style>
</head>
<body>
{html_body}
<script>
var target = document.getElementById('target');
if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
</script>
</body>
</html>'''


def _style_to_css(style):
    s = style.lower()
    if 'heading1' in s: return 'heading1'
    if 'heading2' in s: return 'heading2'
    if 'heading' in s: return 'heading3'
    if 'numbered' in s: return 'numbered'
    if 'list' in s or 'bullet' in s or 'dash' in s: return 'list'
    if 'excerpt' in s or 'quote' in s: return 'excerpt'
    if 'caption' in s: return 'caption'
    if 'footnote' in s: return 'footnote'
    return 'normal'


def _html_esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


class PreviewDialog(QDialog):
    def __init__(self, docx_path, call: JudgmentCall, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Preview in context')
        self.setMinimumSize(QSize(600, 500))
        self.resize(700, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(12, 8, 12, 8)
        info = QLabel(f'Paragraph {call.item_index + 1} — {call.recommended_action}')
        info.setStyleSheet('font-size: 12px; color: #66707a;')
        close_btn = QPushButton('Close')
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.close)
        top.addWidget(info, 1)
        top.addWidget(close_btn)
        layout.addLayout(top)

        self.web = QWebEngineView()
        html = _docx_to_html(docx_path, call.item_index)
        # Load from a temp file (QWebEngineView.setHtml silently fails past ~2 MB and can render blank
        # in a frozen build); a small windowed HTML from a file is reliable.
        self._tmp = os.path.join(tempfile.mkdtemp(), 'preview.html')
        with open(self._tmp, 'w', encoding='utf8') as fh:
            fh.write(html)
        self.web.load(QUrl.fromLocalFile(self._tmp))
        layout.addWidget(self.web, 1)
