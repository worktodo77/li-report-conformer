"""Document preview: renders the .docx body as HTML with the target paragraph highlighted."""
import re, zipfile
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QSize

from conformer.engine import JudgmentCall, text_of


def _docx_to_html(path, highlight_index=None):
    with zipfile.ZipFile(path) as z:
        doc = z.read('word/document.xml').decode('utf8')

    body = re.search(r'<w:body>(.*)</w:body>', doc, re.S)
    if not body:
        return '<html><body><p>Could not read document body.</p></body></html>'

    items = []
    i = 0
    content = body.group(1)
    para_idx = 0
    b0 = None

    for m in re.finditer(r'<w:p\b[^>]*>(.*?)</w:p>', content, re.S):
        ppr = m.group(1)
        style_m = re.search(r'<w:pStyle w:val="([^"]+)"', ppr)
        style = style_m.group(1) if style_m else 'Normal'
        text = re.sub(r'<[^>]+>', '', re.sub(r'<w:instrText.*?</w:instrText>', '', m.group(0), flags=re.S))
        text = text.strip()

        if b0 is None and style == 'Heading1':
            b0 = para_idx

        if b0 is not None:
            body_idx = para_idx - b0
        else:
            body_idx = para_idx

        is_highlighted = (highlight_index is not None and b0 is not None
                          and body_idx == highlight_index)

        css_class = _style_to_css(style)
        highlight_style = ' style="background-color: #fff3cd; border-left: 3px solid #f59e0b; padding-left: 8px;"' if is_highlighted else ''
        anchor = f' id="target"' if is_highlighted else ''

        if text:
            items.append(f'<div class="{css_class}"{highlight_style}{anchor}>{_html_esc(text)}</div>')

        para_idx += 1

    html_body = '\n'.join(items)
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
        self.web.setHtml(html)
        layout.addWidget(self.web, 1)
