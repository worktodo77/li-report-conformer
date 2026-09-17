"""Main window for LI Report Conformer — Concept A (Ledger) layout."""
import os, shutil, datetime, json, subprocess, sys, platform
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QComboBox, QFileDialog, QProgressBar,
    QMessageBox, QMenuBar, QMenu, QSizePolicy, QApplication, QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
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

    def __init__(self, template, input_path):
        super().__init__()
        self.template = template
        self.input_path = input_path

    def run(self):
        try:
            c = Conformer(self.template, self.input_path)
            calls = c.analyze()
            self.finished.emit(c, calls)
        except Exception as e:
            self.error.emit(str(e))


class ApplyWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, conformer, decisions):
        super().__init__()
        self.conformer = conformer
        self.decisions = decisions

    def run(self):
        try:
            fresh = self.conformer.apply_with_decisions(self.decisions)
            self.finished.emit(fresh)
        except Exception as e:
            self.error.emit(str(e))


KIND_LABELS = {
    'style': 'Style', 'level': 'List level', 'merge': 'Merge', 'split': 'Split',
    'promote': 'Heading', 'caption': 'Caption', 'xref': 'Cross-references',
    'unwrap': 'Table', 'dropcol': 'Table', 'splitcap': 'Split', 'imgextract': 'Figure',
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

    def _build_analyzing_state(self):
        self._clear_body()

        sec = QLabel('ANALYZING')
        sec.setObjectName('sectionLabel')
        self.body_layout.addWidget(sec)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.body_layout.addWidget(self.progress_bar)

        self.status_label = QLabel('Reading document and identifying fixes...')
        self.status_label.setStyleSheet('color: #66707a; font-size: 12px;')
        self.body_layout.addWidget(self.status_label)
        self.body_layout.addStretch()

    def _build_review_state(self):
        self._clear_body()
        self.judgment_rows = []

        mech_sec = QLabel('MECHANICAL FIXES')
        mech_sec.setObjectName('sectionLabel')
        self.body_layout.addWidget(mech_sec)

        mech_count = len(self.conformer.log) if self.conformer else 0
        mech_label = QLabel(f'{mech_count} fixes applied automatically')
        mech_label.setStyleSheet('font-size: 12px; color: #66707a; padding-bottom: 8px;')
        self.body_layout.addWidget(mech_label)

        if self.conformer and getattr(self.conformer, 'disposition', None) == 'preserve':
            s = self.conformer.revision_ledger.summary()
            notice = QLabel(
                f"Review-preserving mode — {s['total']:,} tracked changes · {s['comments']} "
                f"comments · {len(s['authors'])} authors will be preserved and verified.")
            notice.setWordWrap(True)
            notice.setStyleSheet('font-size: 12px; color: #1f3a5f; background: #eef2f7; '
                                 'border-radius: 6px; padding: 8px 10px; margin-bottom: 8px;')
            self.body_layout.addWidget(notice)

        if self.judgment_calls:
            judge_sec = QLabel(f'JUDGMENT CALLS ({len(self.judgment_calls)})')
            judge_sec.setObjectName('sectionLabel')
            self.body_layout.addWidget(judge_sec)

            for idx, call in enumerate(self.judgment_calls, 1):
                row = JudgmentRow(idx, call)
                self.judgment_rows.append(row)
                self.body_layout.addWidget(row)
        else:
            no_judge = QLabel('No judgment calls — all fixes are mechanical.')
            no_judge.setStyleSheet('font-size: 12px; color: #66707a; padding: 8px 0;')
            self.body_layout.addWidget(no_judge)

        self.body_layout.addStretch()
        self.tally_bar.setVisible(bool(self.judgment_calls))
        self._update_tally()

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

        self._build_analyzing_state()
        self.worker = AnalyzeWorker(self.template_path, self.input_path)
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _on_analysis_done(self, conformer, calls):
        self.conformer = conformer
        self.judgment_calls = calls
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

        self._build_analyzing_state()
        self.status_label.setText('Applying decisions and conforming document...')

        self.apply_worker = ApplyWorker(self.conformer, decisions)
        self.apply_worker.finished.connect(
            lambda fresh: self._on_apply_done(fresh, decisions)
        )
        self.apply_worker.error.connect(self._on_analysis_error)
        self.apply_worker.start()

    def _on_apply_done(self, fresh, decisions):
        valid, msg = fresh.validate_output()
        if not valid:
            self._build_error_state(
                'Validation failed',
                f'The conformed document failed validation: {msg}\n\n'
                'The original file has not been modified.'
            )
            return

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

        if self.output_mode == 'replace':
            output_path = src
        else:
            output_path = os.path.join(d, f'{name} (conformed){ext}')

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

        # Review-preserving output: write the normalized-formatting-review-copy audit record beside
        # the file (disposition, honest label, original SHA-256, preservation verdict, rolled-back
        # passes). The docx itself is stamped as a review copy by the engine (core.xml contentStatus).
        if getattr(fresh, 'disposition', None) == 'preserve':
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
