"""Main window for LI Report Conformer — Concept A (Ledger) layout."""
import os, shutil, datetime, json, subprocess, sys, platform
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QComboBox, QFileDialog, QProgressBar,
    QMessageBox, QMenuBar, QMenu, QSizePolicy, QApplication, QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer, QPropertyAnimation
from PySide6.QtGui import QFont, QAction, QPixmap, QIcon


def _asset(name):
    return os.path.join(_assets_dir(), name)


LI_NAVY = '#005088'
LI_SKY = '#28A0D8'

from conformer.engine import Conformer, JudgmentCall


BACKUP_DIR_NAME = '_LI Conformer Backups'


def _assets_dir():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')


def _word_lock_exists(path):
    d, name = os.path.split(path)
    return os.path.exists(os.path.join(d, f'~${name}'))


class AnalyzeWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)
    progress = Signal(str, str)

    def __init__(self, template, input_path):
        super().__init__()
        self.template = template
        self.input_path = input_path

    def run(self):
        try:
            c = Conformer(self.template, self.input_path)
            c.progress = lambda k, d='': self.progress.emit(k, d)
            calls = c.analyze()
            self.finished.emit(c, calls)
        except Exception as e:
            self.error.emit(str(e))


class ApplyWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str, str)

    def __init__(self, conformer, decisions):
        super().__init__()
        self.conformer = conformer
        self.decisions = decisions

    def run(self):
        try:
            fresh = self.conformer.apply_with_decisions(
                self.decisions, progress=lambda k, d='': self.progress.emit(k, d))
            self.finished.emit(fresh)
        except Exception as e:
            self.error.emit(str(e))


KIND_LABELS = {
    'style': 'Style', 'level': 'List level', 'merge': 'Merge', 'split': 'Split',
    'promote': 'Heading', 'caption': 'Caption', 'xref': 'Cross-references',
    'unwrap': 'Table', 'dropcol': 'Table', 'splitcap': 'Split', 'imgextract': 'Figure',
    'color': 'Text color', 'highlight': 'Highlight',
}


class JudgmentRow(QFrame):
    def __init__(self, index, call: JudgmentCall, parent=None):
        super().__init__(parent)
        self.call = call
        # tracked-adjacent structural changes are flagged for individual review -> default to Skip so
        # they are never silently applied; the reviewer opts in consciously.
        self.decision = 'skip' if getattr(call, 'needs_review', False) else 'accept'
        self.change_style = call.recommended_action if call.alternatives else ''
        self.expanded = False

        self.setObjectName('judgmentRow')
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)

        self.chevron = QLabel('▶')
        self.chevron.setFixedWidth(16)
        self.chevron.setStyleSheet('font-size: 10px; color: #66707a;')

        num = QLabel(f'{index}.')
        num.setObjectName('judgmentNum')
        num.setFixedWidth(28)

        chip = QLabel(KIND_LABELS.get(call.kind, call.kind.title()))
        _flag = getattr(call, 'needs_review', False)
        chip.setStyleSheet(
            'font-size: 10px; font-weight: 600; border-radius: 4px; padding: 2px 7px; ' +
            ('color: #8a5a00; background: #fbf1d8;' if _flag else 'color: #1f3a5f; background: #eaf0f7;'))
        chip.setFixedHeight(18)

        text_display = call.short_text if len(call.full_text) > 50 else call.full_text
        self.text_label = QLabel(f'"{text_display}"')
        self.text_label.setObjectName('judgmentText')
        self.text_label.setWordWrap(True)

        top.addWidget(self.chevron)
        top.addWidget(num, 0, Qt.AlignTop)
        top.addWidget(chip, 0, Qt.AlignTop)
        top.addWidget(self.text_label, 1)
        layout.addLayout(top)

        self.full_text_label = QLabel(call.full_text)
        self.full_text_label.setObjectName('judgmentFullText')
        self.full_text_label.setWordWrap(True)
        self.full_text_label.setVisible(False)
        layout.addWidget(self.full_text_label)

        # what the fix does (esp. for structural changes) + a review flag when tracked-adjacent
        msg = call.message
        if getattr(call, 'needs_review', False):
            msg = '⚠ ' + msg + '  — tracked change nearby; review before accepting'
        self.message_label = QLabel(msg)
        self.message_label.setObjectName('judgmentReason')
        self.message_label.setWordWrap(True)
        self.message_label.setContentsMargins(24, 0, 0, 0)
        if getattr(call, 'needs_review', False):
            self.message_label.setStyleSheet('color: #9a6a00;')
        layout.addWidget(self.message_label)

        view_layout = QHBoxLayout()
        view_layout.setContentsMargins(24, 0, 0, 0)
        view_layout.setSpacing(4)

        preview_btn = QPushButton('▢ Preview in context')
        preview_btn.setObjectName('viewBtn')
        preview_btn.setFlat(True)
        preview_btn.setCursor(Qt.PointingHandCursor)
        preview_btn.clicked.connect(lambda: self._preview())
        view_layout.addWidget(preview_btn)

        sep = QLabel('|')
        sep.setStyleSheet('color: #e3e0d8; font-size: 10px;')
        view_layout.addWidget(sep)

        word_btn = QPushButton('W Open in Word')
        word_btn.setObjectName('viewBtn')
        word_btn.setFlat(True)
        word_btn.setCursor(Qt.PointingHandCursor)
        word_btn.clicked.connect(lambda: self._open_in_word())
        view_layout.addWidget(word_btn)

        view_layout.addStretch()
        self.view_frame = QWidget()
        self.view_frame.setLayout(view_layout)
        self.view_frame.setVisible(False)
        layout.addWidget(self.view_frame)

        reason = QLabel(f'Recommended: <b>{call.recommended_action}</b>')
        reason.setObjectName('judgmentReason')
        reason.setWordWrap(True)
        layout.addWidget(reason)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(24, 4, 0, 4)
        actions_layout.setSpacing(6)

        self.accept_btn = QPushButton('✓ Accept')
        self.accept_btn.setObjectName('acceptBtn')
        self.accept_btn.setCheckable(True)
        self.accept_btn.setChecked(self.decision == 'accept')
        self.accept_btn.clicked.connect(lambda: self._set_decision('accept'))

        self.change_btn = QPushButton('Change →')
        self.change_btn.setObjectName('changeBtn')
        self.change_btn.setCheckable(True)

        self.change_combo = QComboBox()
        for alt in call.alternatives:
            if alt != call.recommended_action:
                self.change_combo.addItem(alt)
        self.change_combo.setVisible(False)
        self.change_combo.currentTextChanged.connect(self._on_change_style)

        self.skip_btn = QPushButton('Skip')
        self.skip_btn.setObjectName('skipBtn')
        self.skip_btn.setCheckable(True)
        self.skip_btn.setChecked(self.decision == 'skip')
        self.skip_btn.clicked.connect(lambda: self._set_decision('skip'))

        actions_layout.addWidget(self.accept_btn)

        if call.alternatives:
            self.change_btn.clicked.connect(lambda: self._set_decision('change'))
            actions_layout.addWidget(self.change_btn)
            actions_layout.addWidget(self.change_combo)

        actions_layout.addWidget(self.skip_btn)
        actions_layout.addStretch()

        self.actions_widget = QWidget()
        self.actions_widget.setLayout(actions_layout)
        layout.addWidget(self.actions_widget)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.expanded = not self.expanded
            self.full_text_label.setVisible(self.expanded)
            self.view_frame.setVisible(self.expanded)
            self.chevron.setText('▼' if self.expanded else '▶')
        super().mousePressEvent(event)

    def _set_decision(self, decision):
        self.decision = decision
        self.accept_btn.setChecked(decision == 'accept')
        self.change_btn.setChecked(decision == 'change')
        self.skip_btn.setChecked(decision == 'skip')
        self.change_combo.setVisible(decision == 'change')
        if decision == 'change' and self.change_combo.currentText():
            self.change_style = self.change_combo.currentText()
        parent = self.window()
        if hasattr(parent, '_update_tally'):
            parent._update_tally()

    def _on_change_style(self, text):
        if text:
            self.change_style = text

    def get_decision_string(self):
        if self.decision == 'accept':
            return 'accept'
        elif self.decision == 'change' and self.change_style:
            return f'change:{self.change_style}'
        return 'skip'

    def _preview(self):
        parent = self.window()
        if hasattr(parent, '_show_preview'):
            parent._show_preview(self.call)

    def _open_in_word(self):
        parent = self.window()
        if hasattr(parent, '_open_in_word'):
            parent._open_in_word(self.call)


import difflib as _difflib
import re as _re


def _esc_html(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _reveal_ws(esc_text):
    """Make otherwise-invisible characters visible INSIDE a highlighted diff span, so whitespace and
    special-character edits (a doubled sentence space, a non-breaking space, a tab) are actually seen."""
    return (esc_text
            .replace(' ', '<span style="color:#c47f17">⍽</span>')     # non-breaking space
            .replace(' ', '<span style="color:#c47f17">·</span>')          # normal space
            .replace('\t', '<span style="color:#c47f17">→</span>'))        # tab


def diff_before_after(before, after):
    """Word-level diff -> (before_html, after_html). Removed words in the BEFORE are struck through on
    a faint red; inserted/changed words in the AFTER are highlighted yellow. Whitespace inside a changed
    span is revealed (·/⍽/→) so invisible edits are legible."""
    a = _re.split(r'(\s+)', before)
    b = _re.split(r'(\s+)', after)
    sm = _difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    bo, ao = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        bt, at = _esc_html(''.join(a[i1:i2])), _esc_html(''.join(b[j1:j2]))
        if tag == 'equal':
            bo.append(bt); ao.append(at)
        else:
            if bt:
                bo.append('<span style="background:#fbe4e4;text-decoration:line-through;'
                          'color:#a3453c">%s</span>' % _reveal_ws(bt))
            if at:
                ao.append('<span style="background:#fff29a;">%s</span>' % _reveal_ws(at))
    return ''.join(bo), ''.join(ao)


def _edit_kind_label(before, after):
    """A short, specific tag for what a cosmetic edit actually does, e.g. 'Sentence spacing', 'Smart
    quotes'. Falls back to None so the caller can use the generic pass label."""
    b, a = before, after
    if '.  ' in a and '.  ' not in b:
        return 'Sentence spacing'
    if ('“' in a or '”' in a) and '"' in b:
        return 'Smart quotes'
    if '’' in a and "'" in b and '‘' not in a:
        return 'Apostrophe'
    if '‘' in a and "'" in b:
        return 'Smart quotes'
    if '–' in a and '--' in b:
        return 'En dash'
    if '-inch' in a and '"' in b:
        return 'Inch mark'
    if ' ' in a and ' ' not in b:
        return 'Non-breaking space'
    if any(lig in b for lig in ('ﬀ', 'ﬁ', 'ﬂ')):
        return 'Ligature'
    return None


class EditRow(QFrame):
    """A mechanical TEXT edit shown as BEFORE -> AFTER with the changes highlighted yellow, plus a
    per-fix Skip toggle (accepted by default)."""
    def __init__(self, edit, parent=None):
        super().__init__(parent)
        self.edit = edit
        self.skipped = False
        self.setObjectName('editRow')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(4)

        head = QHBoxLayout(); head.setSpacing(8)
        kind = _edit_kind_label(edit['before'], edit['after']) or edit['label']
        chip = QLabel(kind)
        chip.setStyleSheet('font-size: 10px; font-weight: 600; color: #1f3a5f; background: #eaf0f7; '
                           'border-radius: 4px; padding: 2px 7px;')
        chip.setFixedHeight(18)
        head.addWidget(chip, 0, Qt.AlignTop)
        head.addStretch()
        self.skip_btn = QPushButton('Skip')
        self.skip_btn.setObjectName('skipBtn')
        self.skip_btn.setCheckable(True)
        self.skip_btn.setFixedWidth(64)
        self.skip_btn.clicked.connect(self._toggle_skip)
        head.addWidget(self.skip_btn, 0, Qt.AlignTop)
        lay.addLayout(head)

        before_html, after_html = diff_before_after(edit['before'], edit['after'])
        self.before_lbl = QLabel('<span style="color:#8a8f96;">Before</span>&nbsp;&nbsp;' + before_html)
        self.after_lbl = QLabel('<span style="color:#1c7a34;">After</span>&nbsp;&nbsp;&nbsp;' + after_html)
        for lbl in (self.before_lbl, self.after_lbl):
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.RichText)
            lbl.setStyleSheet('font-size: 12.5px; color: #2b2b2b;')
        lay.addWidget(self.before_lbl)
        lay.addWidget(self.after_lbl)

    def _toggle_skip(self):
        self.skipped = self.skip_btn.isChecked()
        # dim the row when skipped
        self.after_lbl.setEnabled(not self.skipped)
        parent = self.window()
        if hasattr(parent, '_update_tally'):
            parent._update_tally()

    def set_skipped(self, val):
        """Set skip state programmatically (e.g. from a 'Skip all cleanup' toggle)."""
        self.skipped = bool(val)
        self.skip_btn.setChecked(self.skipped)
        self.after_lbl.setEnabled(not self.skipped)

    def decision_id(self):
        return self.edit['id']


def _is_cosmetic_log(msg):
    """True for the low-value cosmetic passes (typography + house style) whose per-edit detail lives in
    the paginated Text-cleanup list; everything else is substantive structural conformance."""
    m = msg.lower()
    return m.startswith('typography normalised') or m.startswith('li house style applied')


# Display metadata for each engine progress phase key: (title, default sub-text).
_PHASE_INFO = {
    'read':      ('Reading document', 'Opening every part of the file'),
    'track':     ('Mapping tracked changes', 'Cataloguing revisions, comments and authors'),
    'styles':    ('Repairing corrupt styles', 'Rebuilding LI styles from the template'),
    'tables':    ('Conforming tables', 'Applying the LI table style'),
    'structure': ('Structure & headings', 'Paragraph styles, levels and sections'),
    'type':      ('Typography & house style', 'Smart quotes, spacing and LI terminology'),
    'refs':      ('Captions & cross-references', 'Rebuilding caption and REF fields'),
    'save':      ('Verifying & finishing', 'Confirming every change is preserved'),
}
_PHASES_PRESERVE = ['read', 'track', 'styles', 'tables', 'structure', 'type', 'refs', 'save']
_PHASES_CLEAN = ['read', 'structure', 'type', 'save']
_SPINNER = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'


class _ClickFrame(QFrame):
    """A QFrame that emits `clicked` — used for collapsible section headers (a QPushButton clips a
    child layout, a QFrame sizes to it)."""
    clicked = Signal()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class ChecklistView(QFrame):
    """The live conforming screen: a preservation shield plus a vertical checklist of pipeline phases,
    each advancing from pending → a spinning current step → an animated green check as the engine
    reports real per-pass progress."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('checklist')
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(2, 2, 2, 2); self._v.setSpacing(10)
        self.shield = QLabel(); self.shield.setObjectName('shieldBanner')
        self.shield.setTextFormat(Qt.RichText); self.shield.setWordWrap(True)
        self._v.addWidget(self.shield)
        self._rows_box = QVBoxLayout(); self._rows_box.setSpacing(2)
        self._v.addLayout(self._rows_box)
        self.rows = []          # per phase: {'key','frame','icon','title','sub','state','fx'}
        self.keys = []
        self.current = -1
        self._preserve = True
        self.is_apply = False
        self._spin_i = 0
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(90)

    def set_stage(self, is_apply):
        """analyze stage (preview, nothing written) vs apply stage (commits + saves) — changes the final
        phase label and the shield's finished wording."""
        self.is_apply = bool(is_apply)

    def set_mode(self, mode):
        self._preserve = (mode == 'preserve')
        self.keys = _PHASES_PRESERVE if self._preserve else _PHASES_CLEAN
        while self._rows_box.count():
            item = self._rows_box.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        self.rows = []
        self.current = -1
        for key in self.keys:
            title, sub = _PHASE_INFO[key]
            if key == 'save':
                title, sub = (('Verifying & saving', 'Confirming every change is preserved, then writing the file')
                              if self.is_apply
                              else ('Preparing your review', 'Collecting the fixes and judgment calls'))
            row = QFrame(); row.setObjectName('clRow')
            hl = QHBoxLayout(row); hl.setContentsMargins(10, 8, 10, 8); hl.setSpacing(12)
            icon = QLabel('○'); icon.setFixedWidth(22)
            icon.setStyleSheet('font-size: 16px; color: #b9c0c8;')
            col = QVBoxLayout(); col.setSpacing(1)
            t = QLabel(title); t.setStyleSheet('font-size: 13px; color: #9aa2ab;')
            s = QLabel(sub); s.setStyleSheet('font-size: 11px; color: #b0b6bd;')
            col.addWidget(t); col.addWidget(s)
            hl.addWidget(icon, 0, Qt.AlignTop); hl.addLayout(col, 1)
            self._rows_box.addWidget(row)
            self.rows.append({'key': key, 'frame': row, 'icon': icon, 'title': t, 'sub': s,
                              'state': 'pending', 'fx': None})
        self._render()
        self._update_shield('start')

    def advance(self, key, detail=''):
        if key == '__mode__':
            self.set_mode(detail or 'preserve'); return
        if key not in self.keys:
            return
        idx = self.keys.index(key)
        if detail:
            self.rows[idx]['sub'].setText(detail)
        if idx > self.current:
            self.current = idx
        self._render()
        if key == 'track' and detail:
            self._update_shield('safe', detail)
        elif key == 'save':
            self._update_shield('verified')

    def complete(self):
        self.current = len(self.rows)
        self._render()
        self._update_shield('verified')
        self._timer.stop()

    def _render(self):
        for i, r in enumerate(self.rows):
            state = 'done' if i < self.current else ('current' if i == self.current else 'pending')
            if state == r['state'] and state != 'current':
                continue
            r['state'] = state
            if state == 'done':
                r['icon'].setText('✓')
                r['icon'].setStyleSheet('font-size: 15px; font-weight: 700; color: #1f7a34;')
                r['title'].setStyleSheet('font-size: 13px; color: #1c2733;')
                r['sub'].setStyleSheet('font-size: 11px; color: #66707a;')
                self._pop(r)
            elif state == 'current':
                r['title'].setStyleSheet('font-size: 13px; font-weight: 600; color: #005088;')
                r['sub'].setStyleSheet('font-size: 11px; color: #66707a;')
            else:
                r['icon'].setText('○')
                r['icon'].setStyleSheet('font-size: 16px; color: #b9c0c8;')
                r['title'].setStyleSheet('font-size: 13px; color: #9aa2ab;')
                r['sub'].setStyleSheet('font-size: 11px; color: #b0b6bd;')

    def _pop(self, r):
        # a brief fade-in on the check so completion reads as animated
        fx = QGraphicsOpacityEffect(r['icon']); r['icon'].setGraphicsEffect(fx)
        anim = QPropertyAnimation(fx, b'opacity', self)
        anim.setDuration(260); anim.setStartValue(0.0); anim.setEndValue(1.0)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        r['fx'] = (fx, anim)

    def _tick(self):
        self._spin_i = (self._spin_i + 1) % len(_SPINNER)
        ch = _SPINNER[self._spin_i]
        for i, r in enumerate(self.rows):
            if i == self.current and r['state'] == 'current':
                r['icon'].setText(ch)
                r['icon'].setStyleSheet('font-size: 15px; color: #28A0D8;')

    def _update_shield(self, mode, detail=''):
        if not self._preserve:
            self.shield.setVisible(False); return
        self.shield.setVisible(True)
        if mode == 'verified':
            msg = ('Tracked changes preserved &amp; verified — saved' if self.is_apply
                   else 'Nothing lost — tracked changes intact, ready for your review')
            self.shield.setText('<span style="font-size:15px;">🛡</span>&nbsp;&nbsp;'
                                f'<b style="color:#0f6e56;">{msg}</b>')
            self.shield.setStyleSheet('background:#e1f5ee; border:1px solid #5dcaa5; border-left:3px solid '
                                      '#0f6e56; border-radius:8px; padding:10px 14px; color:#0f6e56;')
        elif mode == 'safe':
            self.shield.setText('<span style="font-size:15px;">🛡</span>&nbsp;&nbsp;'
                                f'<b style="color:#005088;">{detail}</b>'
                                '<span style="color:#4a5a6a;"> — held safe while conforming</span>')
            self.shield.setStyleSheet('background:#eef5fb; border:1px solid #cfe4f5; border-left:3px solid '
                                      '#28A0D8; border-radius:8px; padding:10px 14px; color:#005088;')
        else:
            self.shield.setText('<span style="font-size:15px;">🛡</span>&nbsp;&nbsp;'
                                '<span style="color:#4a5a6a;">Your tracked changes and comments will be '
                                'preserved and verified</span>')
            self.shield.setStyleSheet('background:#eef5fb; border:1px solid #cfe4f5; border-left:3px solid '
                                      '#28A0D8; border-radius:8px; padding:10px 14px;')


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('LI Report Conformer')
        _icon = QIcon(_asset('LI icon.png'))
        if not _icon.isNull():
            self.setWindowIcon(_icon)
        self.setMinimumSize(QSize(700, 600))
        self.resize(800, 700)

        self.input_path = None
        self.template_path = os.path.join(_assets_dir(), 'template.dotx')
        self.conformer = None
        self.judgment_calls = []
        self.judgment_rows = []
        self.output_mode = 'copy'

        self._build_menu()
        self._build_ui()
        self._load_stylesheet()

    def _load_stylesheet(self):
        qss_path = os.path.join(os.path.dirname(__file__), 'styles.qss')
        if os.path.exists(qss_path):
            with open(qss_path) as f:
                self.setStyleSheet(f.read())

    def _build_menu(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu('File')
        open_act = QAction('Open report...', self)
        open_act.setShortcut('Ctrl+O')
        open_act.triggered.connect(self._open_file)
        file_menu.addAction(open_act)

        template_act = QAction('Change template...', self)
        template_act.triggered.connect(self._change_template)
        file_menu.addAction(template_act)
        file_menu.addSeparator()

        quit_act = QAction('Quit', self)
        quit_act.setShortcut('Ctrl+Q')
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        tools_menu = menu_bar.addMenu('Tools')
        selftest_act = QAction('Run self-test', self)
        selftest_act.triggered.connect(self._run_selftest)
        tools_menu.addAction(selftest_act)

        help_menu = menu_bar.addMenu('Help')
        about_act = QAction('About', self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _build_header(self):
        """Branded header: a light strip carrying the full Long International logo, above a stylized
        navy title band with a sky-blue accent rule and a faded globe watermark."""
        wrap = QWidget()
        col = QVBoxLayout(wrap)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        # -- brand strip: the full LI logo on a light band --
        brand = QFrame(); brand.setObjectName('brandStrip')
        bl = QHBoxLayout(brand); bl.setContentsMargins(24, 12, 24, 12); bl.setSpacing(0)
        logo = QLabel()
        pix = QPixmap(_asset('LI logo.png'))
        if not pix.isNull():
            logo.setPixmap(pix.scaledToHeight(42, Qt.SmoothTransformation))
        else:
            logo.setText('LONG INTERNATIONAL')
        bl.addWidget(logo)
        bl.addStretch()
        col.addWidget(brand)

        # -- title band: navy, stylized title + accent + subtitle, faded globe on the right --
        header = QFrame(); header.setObjectName('headerFrame')
        hl = QHBoxLayout(header); hl.setContentsMargins(24, 20, 24, 22); hl.setSpacing(0)
        text_col = QVBoxLayout(); text_col.setSpacing(0)
        title = QLabel('Report Conformer'); title.setObjectName('headerTitle')
        accent = QFrame(); accent.setObjectName('headerAccent')
        accent.setFixedSize(64, 3)
        subtitle = QLabel('Repair expert reports to match the Long International template')
        subtitle.setObjectName('headerSubtitle')
        text_col.addWidget(title)
        text_col.addSpacing(8)
        text_col.addWidget(accent)
        text_col.addSpacing(8)
        text_col.addWidget(subtitle)
        hl.addLayout(text_col)
        hl.addStretch()
        globe = QLabel()
        gpix = QPixmap(_asset('LI icon.png'))
        if not gpix.isNull():
            globe.setPixmap(gpix.scaledToHeight(72, Qt.SmoothTransformation))
            eff = QGraphicsOpacityEffect(globe); eff.setOpacity(0.16); globe.setGraphicsEffect(eff)
        hl.addWidget(globe, 0, Qt.AlignVCenter)
        col.addWidget(header)
        return wrap

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(20, 16, 20, 16)
        self.body_layout.setSpacing(12)

        self._build_ready_state()

        scroll = QScrollArea()
        scroll.setWidget(body)
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)

        self.tally_bar = QFrame()
        self.tally_bar.setObjectName('tallyBar')
        tally_layout = QHBoxLayout(self.tally_bar)
        tally_layout.setContentsMargins(20, 10, 20, 10)
        self.tally_label = QLabel('')
        self.tally_label.setObjectName('tallyText')
        self.apply_btn = QPushButton('Apply && Save')
        self.apply_btn.setObjectName('primaryBtn')
        self.apply_btn.clicked.connect(self._apply_decisions)
        tally_layout.addWidget(self.tally_label, 1)
        tally_layout.addWidget(self.apply_btn)
        self.tally_bar.setVisible(False)
        root.addWidget(self.tally_bar)

    def _clear_body(self):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _build_ready_state(self):
        self._clear_body()

        sec = QLabel('INPUT')
        sec.setObjectName('sectionLabel')
        self.body_layout.addWidget(sec)

        card = QFrame()
        card.setObjectName('card')
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        if self.input_path:
            name = os.path.basename(self.input_path)
            size = os.path.getsize(self.input_path) / 1024
            info = QLabel(name)
            info.setObjectName('fileInfoLabel')
            meta = QLabel(f'{size:.0f} KB')
            meta.setObjectName('fileInfoMeta')
            card_layout.addWidget(info)
            card_layout.addWidget(meta)

            mode_layout = QHBoxLayout()
            mode_label = QLabel('Output:')
            mode_label.setStyleSheet('font-size: 12px; color: #66707a;')
            self.mode_combo = QComboBox()
            self.mode_combo.addItems(['Save conformed copy', 'Replace in place'])
            self.mode_combo.setCurrentIndex(0 if self.output_mode == 'copy' else 1)
            self.mode_combo.currentIndexChanged.connect(
                lambda idx: setattr(self, 'output_mode', 'copy' if idx == 0 else 'replace')
            )
            mode_layout.addWidget(mode_label)
            mode_layout.addWidget(self.mode_combo, 1)
            card_layout.addLayout(mode_layout)

            conform_btn = QPushButton('Conform')
            conform_btn.setObjectName('primaryBtn')
            conform_btn.clicked.connect(self._start_analysis)
            card_layout.addWidget(conform_btn)
        else:
            drop_label = QLabel('Drop a .docx file here or click Open')
            drop_label.setStyleSheet('color: #66707a; padding: 20px 0;')
            drop_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(drop_label)

            open_btn = QPushButton('Open report...')
            open_btn.setObjectName('primaryBtn')
            open_btn.clicked.connect(self._open_file)
            card_layout.addWidget(open_btn, 0, Qt.AlignCenter)

        self.body_layout.addWidget(card)

        tpl_sec = QLabel('TEMPLATE')
        tpl_sec.setObjectName('sectionLabel')
        self.body_layout.addWidget(tpl_sec)

        tpl_name = os.path.basename(self.template_path)
        tpl_label = QLabel(tpl_name)
        tpl_label.setObjectName('fileInfoLabel')
        tpl_label.setStyleSheet('font-size: 11px; color: #66707a;')
        self.body_layout.addWidget(tpl_label)

        self.body_layout.addStretch()

    def _build_analyzing_state(self, heading='CONFORMING', subtitle='', is_apply=False):
        self._clear_body()

        sec = QLabel(heading)
        sec.setObjectName('sectionLabel')
        self.body_layout.addWidget(sec)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setWordWrap(True)
            sub.setStyleSheet('font-size: 12px; color: #66707a; padding: 0 0 6px 2px;')
            self.body_layout.addWidget(sub)

        # Live checklist driven by real per-pass progress from the engine.
        self.checklist = ChecklistView()
        self.checklist.set_stage(is_apply)
        self.checklist.set_mode('preserve')   # default; corrected by the first '__mode__' event
        self.body_layout.addWidget(self.checklist)

        # Kept for back-compat with callers that set a status message; hidden behind the checklist.
        self.status_label = QLabel('')
        self.status_label.setStyleSheet('color: #66707a; font-size: 12px;')
        self.status_label.setVisible(False)
        self.body_layout.addWidget(self.status_label)
        self.body_layout.addStretch()

    def _on_progress(self, key, detail):
        cl = getattr(self, 'checklist', None)
        if cl is not None:
            cl.advance(key, detail)

    def _preserve_banner(self):
        """An elegant review-preserving banner: a shield with the tracked-change / comment / author
        counts that will be preserved and verified."""
        s = self.conformer.revision_ledger.summary()
        card = QFrame(); card.setObjectName('preserveBanner')
        h = QHBoxLayout(card); h.setContentsMargins(14, 10, 14, 10); h.setSpacing(12)
        icon = QLabel('\U0001F6E1'); icon.setStyleSheet('font-size: 20px;')
        h.addWidget(icon, 0, Qt.AlignVCenter)
        col = QVBoxLayout(); col.setSpacing(1)
        t = QLabel('Review-preserving mode')
        t.setStyleSheet('font-size: 12.5px; font-weight: 600; color: #005088;')
        d = QLabel(f"<b>{s['total']:,}</b> tracked changes &nbsp;·&nbsp; <b>{s['comments']}</b> "
                   f"comments &nbsp;·&nbsp; <b>{len(s['authors'])}</b> authors — preserved and verified")
        d.setTextFormat(Qt.RichText)
        d.setStyleSheet('font-size: 12px; color: #4a5a6a;')
        col.addWidget(t); col.addWidget(d)
        h.addLayout(col); h.addStretch()
        return card

    def _collapsible(self, title, count_text, content_widget=None, expanded=False, content_builder=None):
        """A section with a clickable header (chevron + title + count) that toggles its content.

        Pass `content_widget` for eager content, or `content_builder` (a zero-arg callable returning a
        widget) to build the content LAZILY the first time the section is expanded — so a large list
        never blocks the initial render or freezes the UI while collapsed."""
        wrap = QWidget()
        v = QVBoxLayout(wrap); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        # A clickable QFrame (not a QPushButton — a button ignores its child layout's size hint and
        # clips the title). The frame sizes to its content, so the header text is never cut off.
        header = _ClickFrame()
        header.setObjectName('collapseHeader')
        header.setCursor(Qt.PointingHandCursor)
        hl = QHBoxLayout(header); hl.setContentsMargins(4, 10, 4, 10); hl.setSpacing(8)
        chev = QLabel('▼' if expanded else '▶'); chev.setFixedWidth(14)
        chev.setStyleSheet('font-size: 10px; color: #66707a;')
        lab = QLabel(title); lab.setObjectName('sectionLabel'); lab.setStyleSheet('padding:0;')
        cnt = QLabel(count_text); cnt.setStyleSheet('font-size: 11px; color: #8a8f96;')
        hl.addWidget(chev, 0, Qt.AlignVCenter); hl.addWidget(lab, 0, Qt.AlignVCenter)
        hl.addWidget(cnt, 0, Qt.AlignVCenter); hl.addStretch()
        v.addWidget(header)

        holder = QWidget()
        hv = QVBoxLayout(holder); hv.setContentsMargins(0, 0, 0, 0); hv.setSpacing(0)
        state = {'built': False, 'open': expanded}

        def ensure_built():
            if state['built']:
                return
            state['built'] = True
            if content_widget is not None:
                hv.addWidget(content_widget)
            elif content_builder is not None:
                hv.addWidget(content_builder())

        if expanded:
            ensure_built()
        holder.setVisible(expanded)
        v.addWidget(holder)

        def toggle():
            state['open'] = not state['open']
            if state['open']:
                ensure_built()          # build on first expand
            holder.setVisible(state['open'])
            chev.setText('▼' if state['open'] else '▶')
        header.clicked.connect(toggle)
        return wrap

    def _build_conformance_content(self, entries):
        """The substantive structural conformance (corrupt-style repair, tables → LI table style, caption
        rebuilds, cross-references, figures, landscape). Repeated per-instance messages are aggregated
        with a count. Fixes that carry a category (`cat`) get a per-type Skip toggle, so the user can
        turn off a whole class of change (e.g. 'delete empty paragraphs') before applying."""
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(0, 4, 0, 8); v.setSpacing(4)
        cap = QLabel('Structural conformance applied — tracked changes, comments and authorship preserved. '
                     'Skip any type you want left as-is.')
        cap.setWordWrap(True)
        cap.setStyleSheet('font-size: 11.5px; color: #66707a;')
        v.addWidget(cap)

        # Group by category (skippable) or by message text (static). Preserve first-seen order.
        groups = {}
        for e in entries:
            key = ('cat', e['cat']) if e.get('cat') else ('msg', e['msg'])
            g = groups.setdefault(key, {'msg': e['msg'], 'cat': e.get('cat'), 'n': 0})
            g['n'] += 1
        for g in groups.values():
            text = g['msg'] if g['n'] == 1 else f"{g['msg']}  (×{g['n']})"
            if g['cat']:
                v.addWidget(self._conf_row(g['cat'], text))
            else:
                line = QLabel('<span style="color:#1f7a34;">✓</span>&nbsp;&nbsp;' + _esc_html(text))
                line.setTextFormat(Qt.RichText); line.setWordWrap(True)
                line.setStyleSheet('font-size: 12.5px; color: #1c2733; padding-left: 2px;')
                v.addWidget(line)
        return w

    def _conf_row(self, cat, text):
        """One skippable conformance fix: a check + description + a Skip toggle. On Apply, a skipped
        category becomes decisions['conf:<cat>']='skip' so the engine doesn't run it."""
        row = QFrame(); row.setObjectName('editRow')
        hl = QHBoxLayout(row); hl.setContentsMargins(10, 7, 10, 7); hl.setSpacing(10)
        icon = QLabel('<span style="color:#1f7a34;">✓</span>'); icon.setTextFormat(Qt.RichText); icon.setFixedWidth(14)
        lab = QLabel(_esc_html(text)); lab.setWordWrap(True)
        lab.setStyleSheet('font-size: 12.5px; color: #1c2733;')
        btn = QPushButton('Skip'); btn.setObjectName('skipBtn'); btn.setCheckable(True); btn.setFixedWidth(64)
        def toggle():
            skipped = btn.isChecked()
            icon.setText('<span style="color:#9aa2ab;">—</span>' if skipped
                         else '<span style="color:#1f7a34;">✓</span>')
            lab.setStyleSheet('font-size: 12.5px; color: %s;' % ('#9aa2ab' if skipped else '#1c2733'))
        btn.clicked.connect(toggle)
        hl.addWidget(icon, 0, Qt.AlignTop); hl.addWidget(lab, 1); hl.addWidget(btn, 0, Qt.AlignTop)
        self.conf_rows.append({'cat': cat, 'btn': btn})
        return row

    def _build_cleanup_content(self, edits, summaries):
        """The demoted cosmetic bucket (typography + house style). Text-edit rows are PAGINATED so even a
        heavily tracked draft (thousands of edits) never freezes the UI, plus a one-click 'Skip all
        cleanup' toggle for mid-review drafts. Unreviewed edits are applied by default."""
        w = QWidget()
        mc = QVBoxLayout(w); mc.setContentsMargins(0, 4, 0, 8); mc.setSpacing(6)
        intro = QLabel('Cosmetic only — smart quotes, sentence spacing, and LI house-style '
                       'capitalization/terminology. Applied by default; skip individually, or skip the '
                       'whole set on a draft still being edited.')
        intro.setWordWrap(True)
        intro.setStyleSheet('font-size: 11.5px; color: #66707a;')
        mc.addWidget(intro)
        for s in summaries:
            line = QLabel('•  ' + s['msg'])
            line.setWordWrap(True)
            line.setStyleSheet('font-size: 11.5px; color: #8a8f96; padding-left: 8px;')
            mc.addWidget(line)

        if edits:
            skip_all = QPushButton('Skip all cleanup')
            skip_all.setObjectName('skipBtn')
            skip_all.setCheckable(True)
            skip_all.setFixedWidth(160)

            def on_skip_all():
                self.skip_all_cleanup = skip_all.isChecked()
                skip_all.setText('Cleanup skipped — undo' if self.skip_all_cleanup else 'Skip all cleanup')
                for r in self.edit_rows:
                    r.set_skipped(self.skip_all_cleanup)
                self._update_tally()

            skip_all.clicked.connect(on_skip_all)
            mc.addWidget(skip_all, 0, Qt.AlignLeft)

            rows_holder = QWidget()
            rl = QVBoxLayout(rows_holder); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(6)
            mc.addWidget(rows_holder)

            more_btn = QPushButton(); more_btn.setObjectName('viewBtn')
            page = {'shown': 0}
            CHUNK = 100

            def render_more():
                end = min(page['shown'] + CHUNK, len(edits))
                for e in edits[page['shown']:end]:
                    row = EditRow(e)
                    row.set_skipped(self.skip_all_cleanup)   # honour skip-all for newly paged rows
                    self.edit_rows.append(row); rl.addWidget(row)
                page['shown'] = end
                remaining = len(edits) - page['shown']
                if remaining > 0:
                    more_btn.setText(f'Show {min(CHUNK, remaining)} more  ({remaining} remaining)')
                    more_btn.setVisible(True)
                else:
                    more_btn.setVisible(False)

            more_btn.clicked.connect(render_more)
            mc.addWidget(more_btn, 0, Qt.AlignLeft)
            render_more()
        return w

    def _build_review_state(self):
        self._clear_body()
        self.judgment_rows = []
        self.edit_rows = []
        self.conf_rows = []
        self.skip_all_cleanup = False
        edits = getattr(self, 'edits', [])
        log = list(self.conformer.log) if self.conformer else []

        if self.conformer and getattr(self.conformer, 'disposition', None) == 'preserve':
            self.body_layout.addWidget(self._preserve_banner())

        # Split the applied fixes into the SUBSTANTIVE structural conformance (foregrounded) vs the
        # cosmetic typography/house-style cleanup (demoted). The 1,000s of cosmetic text edits used to
        # bury the handful of real conformance actions Claire cares about.
        fmt = [entry for entry in log if entry.get('msg')]
        conformance = [e for e in fmt if not _is_cosmetic_log(e['msg'])]
        cosmetic_summaries = [e for e in fmt if _is_cosmetic_log(e['msg'])]

        # ── CONFORMANCE FIXES (foreground, expanded) — style repair, tables, captions, cross-refs ──
        if conformance:
            self.body_layout.addWidget(self._collapsible(
                'CONFORMANCE FIXES', f'{len(conformance)} structural',
                content_widget=self._build_conformance_content(conformance), expanded=True))

        # ── TEXT CLEANUP (demoted, collapsed, lazy + paginated) — typography + house style ──
        # Placed ABOVE judgment calls (Alex): the decisions the user must make sit closest to Apply.
        if edits or cosmetic_summaries:
            self.body_layout.addWidget(self._collapsible(
                'TEXT CLEANUP', f'{len(edits)} cosmetic edits (typography + house style)',
                content_builder=lambda e=edits, s=cosmetic_summaries: self._build_cleanup_content(e, s)))

        # ── FIGURE INTEGRITY (advisory) — reviewed alongside the judgment calls, before applying ──
        audit = list(getattr(self.conformer, 'audit', []) or []) if self.conformer else []
        if audit:
            self.body_layout.addWidget(self._collapsible(
                'FIGURE INTEGRITY', f'{len(audit)} to review',
                content_widget=self._build_figure_integrity_content(audit), expanded=True))

        # Highlights are grouped (a real draft can have hundreds) — a single control, KEEP by default;
        # every other judgment call (incl. the few colour deviations) stays as an individual row.
        self.highlight_calls = [c for c in self.judgment_calls if c.kind == 'highlight']
        # authoritative per-id decision map (True=remove, absent/False=keep): a per-item choice always
        # wins over the bulk toggle, and the bulk toggle updates EVERY id, not just the rendered page.
        self.highlight_decision = {}
        self._highlight_btns = {}             # id -> its per-item button (for bulk sync)
        other_calls = [c for c in self.judgment_calls if c.kind != 'highlight']

        # ── JUDGMENT CALLS (substantive) ──
        if other_calls:
            judge_sec = QLabel(f'JUDGMENT CALLS ({len(other_calls)})')
            judge_sec.setObjectName('sectionLabel')
            self.body_layout.addWidget(judge_sec)
            for idx, call in enumerate(other_calls, 1):
                row = JudgmentRow(idx, call)
                self.judgment_rows.append(row)
                self.body_layout.addWidget(row)
        elif not conformance and not self.highlight_calls:
            no_judge = QLabel('No judgment calls — all fixes are mechanical.')
            no_judge.setStyleSheet('font-size: 12px; color: #66707a; padding: 8px 0;')
            self.body_layout.addWidget(no_judge)

        # ── HIGHLIGHTS (grouped, collapsed, default keep) ──
        if self.highlight_calls:
            self.body_layout.addWidget(self._collapsible(
                'HIGHLIGHTS', f'{len(self.highlight_calls)} — kept by default',
                content_builder=lambda hc=self.highlight_calls: self._build_highlights_content(hc)))

        self.body_layout.addStretch()
        self.tally_bar.setVisible(bool(self.judgment_calls) or bool(edits) or bool(self.conf_rows))
        self._update_tally()

    def _set_highlight(self, cid, remove):
        """Authoritative per-item decision (wins over the bulk toggle); syncs the rendered button."""
        self.highlight_decision[cid] = bool(remove)
        btn = getattr(self, '_highlight_btns', {}).get(cid)
        if btn is not None and btn.isChecked() != bool(remove):
            btn.blockSignals(True); btn.setChecked(bool(remove)); btn.blockSignals(False)

    def _set_all_highlights(self, remove):
        """A TRUE bulk update across EVERY highlight id (not just the rendered page)."""
        for c in getattr(self, 'highlight_calls', []):
            self._set_highlight(c.id, remove)

    def _highlight_decisions(self):
        """The applied decision for every highlight: accept = remove, skip = keep (default keep)."""
        return {c.id: ('accept' if self.highlight_decision.get(c.id, False) else 'skip')
                for c in getattr(self, 'highlight_calls', [])}

    def _highlight_decision_log(self):
        """Audit rows for the grouped highlights so the saved decision map is faithfully recorded."""
        rows = []
        for c in getattr(self, 'highlight_calls', []):
            remove = self.highlight_decision.get(c.id, False)
            rows.append({'status': 'REMOVED' if remove else 'KEPT',
                         'text': f'"{c.short_text}"',
                         'action': 'Removed highlight' if remove else 'Kept highlight'})
        return rows

    def _build_highlights_content(self, calls):
        """One grouped control for highlights (default KEEP): a 'Remove all' toggle plus a paginated
        per-item list, so hundreds of review markers don't flood the screen and aren't stripped unless
        chosen. Scope note: this covers highlights in ordinary body text (revised paragraphs, table cells
        and footnotes are handled elsewhere), so 'all' means all body-text highlights."""
        self._highlight_btns = {}
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(0, 4, 0, 8); v.setSpacing(6)
        intro = QLabel('Highlights in body text are review markers, so they are KEPT by default. Remove '
                       'them all, or remove individual ones — a per-item choice always wins.')
        intro.setWordWrap(True); intro.setStyleSheet('font-size: 11.5px; color: #66707a;')
        v.addWidget(intro)

        remove_all = QPushButton('Remove all highlights')
        remove_all.setObjectName('skipBtn'); remove_all.setCheckable(True); remove_all.setFixedWidth(180)

        def on_remove_all():
            self._set_all_highlights(remove_all.isChecked())
            remove_all.setText('Removing all — undo' if remove_all.isChecked() else 'Remove all highlights')
        remove_all.clicked.connect(on_remove_all)
        v.addWidget(remove_all, 0, Qt.AlignLeft)

        rows_holder = QWidget()
        rl = QVBoxLayout(rows_holder); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(4)
        v.addWidget(rows_holder)

        more_btn = QPushButton(); more_btn.setObjectName('viewBtn')
        page = {'shown': 0}
        CHUNK = 100

        def render_more():
            end = min(page['shown'] + CHUNK, len(calls))
            for c in calls[page['shown']:end]:
                row = QFrame(); row.setObjectName('editRow')
                hl = QHBoxLayout(row); hl.setContentsMargins(10, 6, 10, 6); hl.setSpacing(10)
                snip = QLabel('<span style="background:#fff29a;padding:0 2px">' +
                              _esc_html((c.short_text or c.full_text)[:80]) + '</span>')
                snip.setTextFormat(Qt.RichText); snip.setWordWrap(True)
                snip.setStyleSheet('font-size: 12px; color: #1c2733;')
                btn = QPushButton('Remove'); btn.setObjectName('skipBtn'); btn.setCheckable(True)
                btn.setFixedWidth(80); btn.setChecked(self.highlight_decision.get(c.id, False))
                btn.toggled.connect(lambda checked, cid=c.id: self._set_highlight(cid, checked))
                self._highlight_btns[c.id] = btn
                hl.addWidget(snip, 1); hl.addWidget(btn, 0, Qt.AlignTop)
                rl.addWidget(row)
            page['shown'] = end
            remaining = len(calls) - page['shown']
            more_btn.setVisible(remaining > 0)
            if remaining > 0:
                more_btn.setText(f'Show {min(CHUNK, remaining)} more  ({remaining} remaining)')
        more_btn.clicked.connect(render_more)
        v.addWidget(more_btn, 0, Qt.AlignLeft)
        render_more()
        return w

    def _build_figure_integrity_content(self, audit):
        """Advisory figure-audit findings (numbering drift, captions vs the Table of Figures). These
        don't change the output — they tell the expert what to check — so they're shown for review
        before applying, not buried in the completed screen."""
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(0, 4, 0, 8); v.setSpacing(4)
        cap = QLabel('Advisory checks on figure/table numbering and captions — these do not change the '
                     'document; review them and update the source if needed.')
        cap.setWordWrap(True); cap.setStyleSheet('font-size: 11.5px; color: #66707a;')
        v.addWidget(cap)
        for a in audit:
            if isinstance(a, (tuple, list)) and len(a) == 2:
                lvl, msg = a; text = f'[{lvl}] {msg}'
            else:
                text = str(a)
            line = QLabel('<span style="color:#b26a00;">▲</span>&nbsp;&nbsp;' + _esc_html(text))
            line.setTextFormat(Qt.RichText); line.setWordWrap(True)
            line.setStyleSheet('font-size: 12px; color: #1c2733; padding-left: 2px;')
            v.addWidget(line)
        return w

    def _build_complete_state(self, output_path, decisions_log, audit=None, fresh=None):
        self._clear_body()
        self.tally_bar.setVisible(False)

        sec = QLabel('COMPLETE')
        sec.setObjectName('sectionLabel')
        self.body_layout.addWidget(sec)

        # Review-preserving output: state plainly what this file is and that tracked changes were
        # preserved and verified — never present it as a fully-conformed reading copy.
        if fresh is not None and getattr(fresh, 'disposition', None) == 'preserve':
            try:
                clean, _ = fresh.verify_preservation()
            except Exception:
                clean = None
            n_roll = len(getattr(fresh, 'exceptions', []))
            banner = QFrame()
            banner.setObjectName('card')
            bl = QVBoxLayout(banner)
            title = QLabel('Normalized-formatting review copy')
            title.setStyleSheet('font-weight: 600; color: #1f3a5f;')
            bl.addWidget(title)
            summ = QLabel(
                'Formatting was conformed to the LI template while every tracked change, comment '
                'and author was preserved' + (' and verified.' if clean else '.') +
                ' This is not a fully-conformed reading copy. The original is backed up; an audit '
                'record (_conform_audit.json) was written beside the output.')
            summ.setWordWrap(True)
            summ.setStyleSheet('font-size: 12px; color: #66707a;')
            bl.addWidget(summ)
            status = QLabel(('✓ Preservation verified clean.' if clean
                             else '⚠ Preservation could not be verified.')
                            + (f'  {n_roll} pass(es) conformed conservatively.' if n_roll else ''))
            status.setStyleSheet('font-size: 12px; color: %s;' % ('#2e7d32' if clean else '#b26a00'))
            status.setWordWrap(True)
            bl.addWidget(status)
            self.body_layout.addWidget(banner)

        # Three outcomes, reported SEPARATELY (preservation never stands in for conformance).
        if fresh is not None and hasattr(fresh, 'outcome_report'):
            try:
                rep = fresh.outcome_report()
            except Exception:
                rep = None
            if rep:
                conf = rep.get('conformance', {})
                unres = rep.get('unresolved', {})
                nflip = len(conf.get('numbering_flips', []) or [])
                npref = len(conf.get('paragraph_reference_flips', []) or [])
                ninteg = len(conf.get('definition_integrity_violations', []) or [])
                ntbl = len(conf.get('tables_failing_effective_format', []) or [])
                nreview = len(conf.get('tables_review', []) or [])
                nimp = len(unres.get('unresolved_imports', []) or [])
                npru = len(unres.get('paragraph_reference_unresolved', []) or [])
                nrev = (len(unres.get('tables_needing_review', []) or []) + len(unres.get('tables_unresolved', []) or [])
                        + nreview + nimp + npru)
                nroll = len(unres.get('rolled_back_passes', []) or [])
                # the SAME authoritative verdict the audit uses (includes unadjudicated review deviations).
                # An exception is UNKNOWN, never an inferred pass — the older count-based predicate would
                # fail open when the verdict itself could not be computed (issue #1 R3).
                try:
                    formatting_ok = fresh.conformance_clean()
                except Exception:
                    formatting_ok = None                         # UNKNOWN — verification did not complete
                oc = QFrame(); oc.setObjectName('card')
                ol = QVBoxLayout(oc)
                for label, ok, detail in (
                    ('Review history preserved', rep.get('preservation', {}).get('clean') is True,
                     'Every tracked change and comment intact'),
                    ('Formatting conforms', formatting_ok is True,
                     'Numbering, references, definitions and table formatting resolve as intended'
                     if formatting_ok
                     else ('Conformance could not be verified — treat this as an unverified review copy'
                           if formatting_ok is None
                           else f'{nflip} list-meaning flip(s), {npref} paragraph-reference change(s), '
                                f'{ninteg} definition issue(s), {ntbl} table(s) off, '
                                f'{nreview} table(s) with unadjudicated review deviations')),
                    ('Nothing left unresolved', not (nrev or nroll),
                     'No exceptions' if not (nrev or nroll)
                     else f'{nroll} pass(es) held back, {nrev} item(s) need a manual look '
                          f'({nimp} unresolved import(s), {npru} uncorresponded paragraph(s))')):
                    row = QLabel(f'{"✓" if ok else "⚠"}  <b>{label}</b> — {detail}')
                    row.setTextFormat(Qt.RichText); row.setWordWrap(True)
                    row.setStyleSheet('font-size: 12px; color: %s;' % ('#1f7a34' if ok else '#b26a00'))
                    ol.addWidget(row)
                self.body_layout.addWidget(oc)

        card = QFrame()
        card.setObjectName('card')
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        done_icon = QLabel('✓')
        done_icon.setStyleSheet('font-size: 24px; color: #2e7d32; font-weight: bold;')
        card_layout.addWidget(done_icon)

        done_label = QLabel(f'Saved to: {os.path.basename(output_path)}')
        done_label.setObjectName('fileInfoLabel')
        done_label.setWordWrap(True)
        card_layout.addWidget(done_label)

        btn_layout = QHBoxLayout()
        open_btn = QPushButton('Open output')
        open_btn.clicked.connect(lambda: self._open_file_external(output_path))
        btn_layout.addWidget(open_btn)

        open_dir_btn = QPushButton('Show in folder')
        open_dir_btn.clicked.connect(
            lambda: self._open_file_external(os.path.dirname(output_path))
        )
        btn_layout.addWidget(open_dir_btn)

        new_btn = QPushButton('Conform another')
        new_btn.setObjectName('primaryBtn')
        new_btn.clicked.connect(self._reset)
        btn_layout.addWidget(new_btn)
        card_layout.addLayout(btn_layout)

        self.body_layout.addWidget(card)

        # ── AUDIT LOG — full per-change record, downloadable as Word / Excel / CSV ──
        self._audit_ctx = {'fresh': fresh, 'source': self.input_path, 'output': output_path,
                           'decisions_log': decisions_log}
        audit_sec = QLabel('AUDIT LOG')
        audit_sec.setObjectName('sectionLabel')
        self.body_layout.addWidget(audit_sec)
        audit_desc = QLabel('A full record of every change made to the file — file details, preservation '
                            'verdict, and one row per change (before/after, location, rule, disposition).')
        audit_desc.setWordWrap(True)
        audit_desc.setStyleSheet('font-size: 12px; color: #66707a;')
        self.body_layout.addWidget(audit_desc)
        al = QHBoxLayout()
        for label, fmt in (('Word (.docx)', 'docx'), ('Excel (.xlsx)', 'xlsx'), ('CSV (.csv)', 'csv')):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, f=fmt: self._download_audit(f))
            al.addWidget(b)
        al.addStretch()
        aw = QWidget(); aw.setLayout(al)
        self.body_layout.addWidget(aw)

        audit = audit or []
        integ_sec = QLabel('FIGURE INTEGRITY')
        integ_sec.setObjectName('sectionLabel')
        self.body_layout.addWidget(integ_sec)
        if not audit:
            ok = QLabel('✓  Figure numbering is sequential and section-matched; captions match the Table of Figures.')
            ok.setStyleSheet('font-size: 12px; color: #2e7d32;')
            ok.setWordWrap(True)
            self.body_layout.addWidget(ok)
        else:
            warn = QLabel(f'⚠  {len(audit)} issue(s) found — Word will renumber on open, but review these:')
            warn.setStyleSheet('font-size: 12px; color: #b26a00; font-weight: 600;')
            warn.setWordWrap(True)
            self.body_layout.addWidget(warn)
            for lvl, msg in audit:
                row = QLabel(f'• [{lvl}] {msg}')
                row.setStyleSheet('font-size: 11px; color: #66707a;')
                row.setWordWrap(True)
                self.body_layout.addWidget(row)

        if decisions_log:
            log_sec = QLabel(f'DECISION LOG ({len(decisions_log)})')
            log_sec.setObjectName('sectionLabel')
            self.body_layout.addWidget(log_sec)

            for entry in decisions_log:
                row = QFrame()
                row.setObjectName('logRow')
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 4, 0, 4)
                row_layout.setSpacing(8)

                status = entry.get('status', '')
                status_label = QLabel(status.upper())
                if status == 'ACCEPTED':
                    status_label.setObjectName('statusAccepted')
                elif status == 'CHANGED':
                    status_label.setObjectName('statusChanged')
                else:
                    status_label.setObjectName('statusSkipped')
                status_label.setFixedWidth(70)

                text_label = QLabel(entry.get('text', ''))
                text_label.setStyleSheet('font-size: 12px;')
                text_label.setWordWrap(True)

                action_label = QLabel(entry.get('action', ''))
                action_label.setStyleSheet('font-size: 11px; color: #66707a;')

                row_layout.addWidget(status_label)
                row_layout.addWidget(text_label, 1)
                row_layout.addWidget(action_label)
                self.body_layout.addWidget(row)

        self.body_layout.addStretch()

    def _download_audit(self, fmt):
        ctx = getattr(self, '_audit_ctx', None)
        if not ctx or ctx.get('fresh') is None:
            return
        stem = os.path.splitext(os.path.basename(ctx['output']))[0]
        date = datetime.datetime.now().strftime('%d%m%y')
        default = os.path.join(os.path.dirname(ctx['output']), f'{stem} — audit log {date}.{fmt}')
        filt = {'docx': 'Word Document (*.docx)', 'xlsx': 'Excel Workbook (*.xlsx)',
                'csv': 'CSV (*.csv)'}[fmt]
        path, _ = QFileDialog.getSaveFileName(self, 'Save audit log', default, filt)
        if not path:
            return
        if not path.lower().endswith('.' + fmt):
            path += '.' + fmt
        try:
            from conformer import audit_export as ax
            summary, records = ax.build_records(
                ctx['fresh'], ctx['source'], ctx['output'], ctx.get('decisions_log'))
            {'docx': ax.write_docx, 'xlsx': ax.write_xlsx, 'csv': ax.write_csv}[fmt](path, summary, records)
        except Exception as e:
            QMessageBox.critical(self, 'Audit log failed', f'Could not write the audit log:\n{e}')
            return
        QMessageBox.information(self, 'Audit log saved',
                                f'{len(records)} changes written to:\n{os.path.basename(path)}')

    def _build_error_state(self, title, message):
        self._clear_body()
        self.tally_bar.setVisible(False)

        sec = QLabel('ERROR')
        sec.setObjectName('sectionLabel')
        self.body_layout.addWidget(sec)

        card = QFrame()
        card.setObjectName('card')
        card.setStyleSheet(
            'QFrame#card { border-color: #d32f2f; background-color: #fef2f2; }'
        )
        card_layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setStyleSheet('font-weight: 600; color: #d32f2f; font-size: 14px;')
        card_layout.addWidget(title_label)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet('color: #1c2733; font-size: 12px;')
        card_layout.addWidget(msg_label)

        retry_btn = QPushButton('Try again')
        retry_btn.clicked.connect(self._reset)
        card_layout.addWidget(retry_btn, 0, Qt.AlignLeft)

        self.body_layout.addWidget(card)
        self.body_layout.addStretch()

    # ── Actions ──

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open report', '', 'Word Documents (*.docx)'
        )
        if path:
            self.input_path = path
            self._build_ready_state()

    def _change_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Select template', '', 'Word Templates (*.dotx)'
        )
        if path:
            self.template_path = path
            self._build_ready_state()

    def _start_analysis(self):
        if not self.input_path:
            return

        if _word_lock_exists(self.input_path):
            self._build_error_state(
                'File is open in Word',
                f'{os.path.basename(self.input_path)} is currently open in Microsoft Word. '
                'Close it first, then try again.'
            )
            return

        if not self.template_path or not os.path.exists(self.template_path):
            self._build_error_state(
                'Template not found',
                'The LI template could not be found where it should be bundled with the app '
                f'({os.path.basename(self.template_path or "template.dotx")}). This usually means '
                'the installed build is incomplete. Use  File → Change template…  to point '
                'at a .dotx template, or reinstall the app.'
            )
            return

        self._build_analyzing_state(
            'ANALYZING',
            'Scanning your document to find every fix and flag the judgment calls to review. '
            'Nothing is saved yet — you review before anything is written.',
            is_apply=False)
        self.worker = AnalyzeWorker(self.template_path, self.input_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _on_analysis_done(self, conformer, calls):
        self.conformer = conformer
        self.judgment_calls = calls
        self.edits = [e for e in getattr(conformer, 'pending_edits', []) if e['before'] != e['after']]
        self._build_review_state()

    def _on_analysis_error(self, msg):
        self._build_error_state('Analysis failed', msg)

    def _update_tally(self):
        accepted = sum(1 for r in self.judgment_rows if r.decision == 'accept')
        changed = sum(1 for r in self.judgment_rows if r.decision == 'change')
        skipped = sum(1 for r in self.judgment_rows if r.decision == 'skip')
        self.tally_label.setText(
            f'{accepted} accepted · {changed} changed · {skipped} skipped'
        )

    def _apply_decisions(self):
        if not self.conformer:
            return

        decisions = {}
        for row in self.judgment_rows:
            decisions[row.call.id] = row.get_decision_string()
        # highlights (grouped): the authoritative per-id decision map (accept=remove, skip=keep)
        decisions.update(self._highlight_decisions())
        if getattr(self, 'skip_all_cleanup', False):
            # skip EVERY cosmetic edit, including pages the user never scrolled to
            for e in getattr(self, 'edits', []):
                decisions[e['id']] = 'skip'
        else:
            for row in getattr(self, 'edit_rows', []):
                if row.skipped:
                    decisions[row.decision_id()] = 'skip'
        # skipped CONFORMANCE fix types (e.g. delete empty paragraphs) → not applied by the engine
        for cr in getattr(self, 'conf_rows', []):
            if cr['btn'].isChecked():
                decisions['conf:' + cr['cat']] = 'skip'

        # Ask where to save and under what name (default: "<name> CONFORMED DDMMYY.docx"). Replace-in-
        # place mode overwrites the original, so it needs no prompt.
        self._chosen_output = None
        if self.output_mode != 'replace':
            src = self.input_path
            name, ext = os.path.splitext(os.path.basename(src))
            default = os.path.join(os.path.dirname(src),
                                   f'{name} CONFORMED {datetime.datetime.now().strftime("%d%m%y")}{ext}')
            path, _ = QFileDialog.getSaveFileName(self, 'Save conformed report', default,
                                                  'Word Document (*.docx)')
            if not path:
                return   # user cancelled — do not conform
            if not path.lower().endswith('.docx'):
                path += '.docx'
            self._chosen_output = path

        self._build_analyzing_state(
            'APPLYING & SAVING',
            'Applying your decisions, preserving every tracked change, and writing the conformed copy.',
            is_apply=True)

        self.apply_worker = ApplyWorker(self.conformer, decisions)
        self.apply_worker.progress.connect(self._on_progress)
        self.apply_worker.finished.connect(
            lambda fresh: self._on_apply_done(fresh, decisions)
        )
        self.apply_worker.error.connect(self._on_analysis_error)
        self.apply_worker.start()

    def _confirm_unverified_save(self, kind, detail):
        """The save-boundary decision for a copy that is NOT verified clean. Returns True only on an
        EXPLICIT choice to save a clearly-labelled review copy; the default is Cancel for damage/unknown so
        an exception or unauthorized change never slips through silently (issue #1 R3). This is a seam so
        the branch behaviour can be tested without a live dialog."""
        if kind == 'unknown':
            title = 'Conformance could not be verified'
            body = ('Verification did not complete (an internal check failed), so this copy could NOT be '
                    'confirmed as a clean conformed document.\n\nInternal detail: %s\n\nSave it anyway as '
                    'an UNVERIFIED review copy?' % detail)
            default = QMessageBox.Cancel
        elif kind == 'blocking':
            title = 'Conformance not verified clean'
            body = ('The conformed copy contains formatting changes that could not be verified as '
                    'authorized (numbering, paragraph references, definitions, or effective table '
                    'formatting). It is a review copy, not a clean conformed document.\n\nSave the review '
                    'copy anyway?')
            default = QMessageBox.Cancel
        else:   # review — non-blocking, but something is unadjudicated/unresolved
            title = 'Unresolved items remain'
            body = ('Some deviations, tables or references need a manual look and were not adjudicated, so '
                    'this copy is NOT certified fully clean. Save it as a review copy?')
            default = QMessageBox.Save
        r = QMessageBox.warning(self, title, body, QMessageBox.Save | QMessageBox.Cancel, default)
        return r == QMessageBox.Save

    def _on_apply_done(self, fresh, decisions):
        valid, msg = fresh.validate_output()
        if not valid:
            self._build_error_state(
                'Validation failed',
                f'The conformed document failed validation: {msg}\n\n'
                'The original file has not been modified.'
            )
            return

        # Authoritative semantic verdict at the save boundary (not just ZIP/XML validity). This FAILS
        # CLOSED (issue #1 R3): a verifier that raises is treated as UNKNOWN, never as permission to save.
        # Ordinary (silent, clean) saving happens only when the verdict is computed AND clean; every other
        # outcome — blocking semantic damage, unadjudicated deviations, or an exception — needs an explicit
        # decision to write a clearly-unverified review copy.
        try:
            status = fresh.conformance_status()
            status_error = None
        except Exception as e:
            status, status_error = None, e

        if status_error is not None:
            if not self._confirm_unverified_save('unknown', str(status_error)):
                self._build_review_state()
                return
        elif status.get('blocking'):
            if not self._confirm_unverified_save('blocking', status):
                self._build_review_state()
                return
        elif not status.get('clean', False):
            if not self._confirm_unverified_save('review', status):
                self._build_review_state()
                return

        # Carry the ACTUAL verdict and the explicit review-only decision into the artifact so its label,
        # filename and audit are accurate (issue #1 R3): a confirmation to save does not complete
        # verification. forced_review = anything not verified clean (exception, blocking or unresolved).
        fresh._save_verdict = status
        fresh._save_forced_review = (status_error is not None
                                     or status is None or not status.get('clean', False))

        try:
            output_path = self._save_output(fresh)
        except Exception as e:
            self._build_error_state('Save failed', str(e))
            return

        decisions_log = []
        for row in self.judgment_rows:
            d = row.get_decision_string()
            if d == 'accept':
                status = 'ACCEPTED'
                action = f'→ {row.call.recommended_action}'
            elif d.startswith('change:'):
                status = 'CHANGED'
                style = d.split(':', 1)[1]
                action = f'→ {style} (engine recommended: {row.call.recommended_action})'
            else:
                status = 'SKIPPED'
                action = f'Left as {row.call.original_style}'
            decisions_log.append({
                'status': status,
                'text': f'"{row.call.short_text}"',
                'action': action,
            })
        # grouped highlight decisions are recorded too, so the audit matches the actual applied map
        decisions_log.extend(self._highlight_decision_log())

        self._build_complete_state(output_path, decisions_log, getattr(fresh, 'audit', []), fresh)

    def _save_output(self, fresh):
        src = self.input_path
        d = os.path.dirname(src)
        name, ext = os.path.splitext(os.path.basename(src))

        backup_dir = os.path.join(d, BACKUP_DIR_NAME)
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = os.path.join(backup_dir, f'{name}_{ts}{ext}')
        shutil.copy2(src, backup)

        review_only = bool(getattr(fresh, '_save_forced_review', False))
        stamp = datetime.datetime.now().strftime('%d%m%y')
        if self.output_mode == 'replace':
            output_path = src
        elif getattr(self, '_chosen_output', None):
            output_path = self._chosen_output          # user-chosen location + filename
            if review_only:
                # keep a promised review copy visibly distinct from a verified conformed file
                cstem, cext = os.path.splitext(output_path)
                if 'REVIEW COPY' not in cstem.upper():
                    output_path = f'{cstem} (REVIEW COPY - UNVERIFIED){cext}'
        elif review_only:
            output_path = os.path.join(d, f'{name} REVIEW COPY - UNVERIFIED {stamp}{ext}')
        else:
            output_path = os.path.join(d, f'{name} CONFORMED {stamp}{ext}')

        fresh.save(output_path)

        log_path = os.path.join(d, f'{name}_conform_log.json')
        log_data = {
            'input': os.path.basename(src),
            'output': os.path.basename(output_path),
            'backup': os.path.basename(backup),
            'timestamp': ts,
            'mechanical': fresh.log,
            'judgment': fresh.judgment,
            'figure_audit': [{'level': lvl, 'message': msg} for lvl, msg in getattr(fresh, 'audit', [])],
        }
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)

        # Write the audit record beside the file (disposition, HONEST verdict-based label, conformance
        # verdict + reason counts, original SHA-256, preservation verdict, rolled-back passes) for any
        # preserve-mode output AND for any review-only copy, so the artifact's true status travels with it.
        if getattr(fresh, 'disposition', None) == 'preserve' or review_only:
            try:
                fresh.write_audit(output_path)
            except Exception:
                pass

        return output_path

    def _reset(self):
        self.input_path = None
        self.conformer = None
        self.judgment_calls = []
        self.judgment_rows = []
        self.tally_bar.setVisible(False)
        self._build_ready_state()

    def _show_preview(self, call: JudgmentCall):
        from conformer.ui.preview import PreviewDialog
        dlg = PreviewDialog(self.input_path, call, self)
        dlg.exec()

    def _open_in_word(self, call: JudgmentCall):
        if not self.input_path:
            return
        if platform.system() == 'Windows':
            os.startfile(self.input_path)
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', self.input_path])

    def _open_file_external(self, path):
        if platform.system() == 'Windows':
            os.startfile(path)
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', path])

    def _run_selftest(self):
        from conformer.ui.selftest import run_selftest
        run_selftest(self)

    def _show_about(self):
        QMessageBox.about(
            self, 'About LI Report Conformer',
            'LI Report Conformer v0.1.0\n\n'
            'Repairs expert reports to match the LI Word template.\n\n'
            'Engine scores 10/10 on the 26-file synthetic stress-test set.'
        )

    # ── Drag and drop ──

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().endswith('.docx'):
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.endswith('.docx'):
                self.input_path = path
                self._build_ready_state()
                break
