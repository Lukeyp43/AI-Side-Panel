"""
AI Create - Single card creation from pasted slide/content in the Add dialog.
Adds an "AI Create" button to the editor toolbar. User pastes slide content,
AI generates a single Front/Back card, fills the editor fields.
"""

import sys
import re
import socket
from aqt import mw
from aqt.utils import tooltip


def _has_internet():
    """Quick check for internet connectivity."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2).close()
        return True
    except OSError:
        return False

from .utils import ADDON_NAME
from .theme_manager import ThemeManager

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTextEdit, QSizePolicy, QGraphicsDropShadowEffect
    )
    from PyQt6.QtCore import Qt, QTimer, QEvent
    from PyQt6.QtGui import QCursor, QColor, QPainterPath, QRegion, QPainter
except ImportError:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTextEdit, QSizePolicy, QGraphicsDropShadowEffect
    )
    from PyQt5.QtCore import Qt, QTimer, QEvent
    from PyQt5.QtGui import QCursor, QColor, QPainterPath, QRegion, QPainter

_FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'

SINGLE_CARD_PROMPT = """Create exactly 1 flashcard from the content below. If it's a topic, create a question about it. If it's notes or content, create a question testing a key concept from it.

Be concise and direct in the answer. Scale the answer length to the complexity of the question. Do not ask follow-up questions. Do not add disclaimers, caveats, or unnecessary elaboration.

You MUST format your response EXACTLY like this, with no other text before or after:

<card>
<front>question here</front>
<back>answer here</back>
</card>

Content:
{content}"""


def parse_single_card(response_text):
    """Parse <card> tags from response text (innerText, not HTML)."""
    match = re.search(
        r'<card>\s*<front>(.*?)</front>\s*<back>(.*?)</back>\s*</card>',
        response_text,
        re.DOTALL
    )
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, None


def parse_partial_card(response_text):
    """Parse card content even if tags aren't fully closed yet (for streaming)."""
    front = None
    back = None

    # Extract front content — handle both closed and unclosed tag
    front_match = re.search(r'<front>(.*?)(?:</front>|$)', response_text, re.DOTALL)
    if front_match:
        front = front_match.group(1).strip()

    # Extract back content — handle both closed and unclosed tag
    back_match = re.search(r'<back>(.*?)(?:</back>|$)', response_text, re.DOTALL)
    if back_match:
        back = back_match.group(1).strip()

    return front, back


_ai_create_timer = None


def _get_package():
    return sys.modules.get('the_ai_panel') or sys.modules.get(__name__.rsplit('.', 1)[0])


def _cleanup_create_panel():
    """Hide the hidden OpenEvidence panel after AI Create finishes."""
    pkg = _get_package()
    dock_widget = getattr(pkg, 'dock_widget', None) if pkg else None
    if dock_widget:
        dock_widget.hide()
        dock_widget.setWindowOpacity(1)
        dock_widget.setFloating(False)
        mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)


class ModalOverlay(QWidget):
    """Dark overlay behind the modal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        if parent:
            self.setGeometry(parent.rect())
            parent.installEventFilter(self)
        self.raise_()

    def eventFilter(self, watched, event):
        if watched == self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))
        p.end()

    def mousePressEvent(self, event):
        event.accept()


class AICreateWindow(QWidget):
    """Modal for pasting slide content and generating a single card."""

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self._editor = editor
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(460, 340)
        self.resize(500, 380)

        self._poll_timer = None
        self._drag_pos = None
        self._overlay = None
        self._spinner_timer = None
        self._spinner_frame = 0

        self._setup_ui()
        self._center_on_screen()

    def _center_on_screen(self):
        if mw:
            geo = mw.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)

    def _setup_ui(self):
        c = ThemeManager.get_palette()

        self.setObjectName("AICreateWindow")
        self.setStyleSheet(f"QWidget#AICreateWindow {{ background: {c['background']}; border: 1px solid {c['border']}; border-radius: 14px; }}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar with X
        header_bar = QWidget()
        header_bar.setFixedHeight(38)
        hb_layout = QHBoxLayout(header_bar)
        hb_layout.setContentsMargins(12, 0, 12, 0)
        hb_layout.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {c['text_secondary']}; border: none; border-radius: 6px; font-size: 18px; }}
            QPushButton:hover {{ background: {c['hover']}; color: {c['text']}; }}
        """)
        close_btn.clicked.connect(self.close)
        hb_layout.addWidget(close_btn)
        header_bar.mousePressEvent = self._title_mouse_press
        header_bar.mouseMoveEvent = self._title_mouse_move
        main_layout.addWidget(header_bar)

        # Divider
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {c['border']};")
        main_layout.addWidget(line)

        # Content
        content = QVBoxLayout()
        content.setContentsMargins(28, 16, 28, 0)
        content.setSpacing(14)

        header = QLabel("What do you want a card about?")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"color: {c['text']}; font-size: 18px; font-weight: 600; font-family: {_FONT};")
        content.addWidget(header)

        is_dark = ThemeManager.is_night_mode()
        input_bg = "#2a2a2e" if is_dark else "#eaeaee"
        input_border = "#3a3a3f" if is_dark else "#d0d0d5"
        scrollbar_bg = c['background']
        scrollbar_handle = c['border']
        scrollbar_hover = c['text_secondary']

        self.content_input = QTextEdit()
        self.content_input.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.content_input.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_input.setPlaceholderText("type a topic, paste a lecture slide, or drop in any content you want turned into a card")
        self.content_input.setStyleSheet(f"""
            QTextEdit {{
                background: {input_bg};
                color: {c['text']};
                border: 1px solid {input_border};
                border-radius: 10px;
                padding: 12px;
                font-size: 13px;
                font-family: {_FONT};
            }}
            QTextEdit:focus {{
                border-color: {c['accent']};
            }}
            QScrollBar:vertical {{
                background: {scrollbar_bg};
                width: 8px;
                margin: 2px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {scrollbar_handle};
                min-height: 30px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {scrollbar_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        content.addWidget(self.content_input, 1)

        # Status label (hidden by default)
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"color: {c['text_secondary']}; font-size: 12px; font-family: {_FONT};")
        self.status_label.hide()
        content.addWidget(self.status_label)

        main_layout.addLayout(content, 1)

        # Bottom button
        bottom = QVBoxLayout()
        bottom.setContentsMargins(28, 8, 28, 20)
        self.generate_btn = QPushButton("Create Card")
        self.generate_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.generate_btn.setFixedHeight(44)
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['accent']};
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 600;
                font-family: {_FONT};
            }}
            QPushButton:hover {{ background: {c['accent_hover']}; }}
        """)
        self.generate_btn.clicked.connect(self._on_generate)
        bottom.addWidget(self.generate_btn)
        main_layout.addLayout(bottom)

    def _title_mouse_press(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        except AttributeError:
            if event.button() == Qt.LeftButton:
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def _title_mouse_move(self, event):
        if self._drag_pos is not None:
            try:
                self.move(event.globalPosition().toPoint() - self._drag_pos)
            except AttributeError:
                self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def resizeEvent(self, event):
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(self.width()), float(self.height()), 14.0, 14.0)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def _on_generate(self):
        content = self.content_input.toPlainText().strip()
        if not content:
            tooltip("Please paste some content first.", period=2000)
            return

        if not _has_internet():
            self._on_error("No internet connection. Check your connection and try again.")
            return

        self._user_content = content  # Store for fallback Front
        prompt = SINGLE_CARD_PROMPT.format(content=content)

        # Show loading state with rolling dots spinner
        c = ThemeManager.get_palette()
        self.generate_btn.setEnabled(False)
        self.content_input.setEnabled(False)
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['surface']};
                color: {c['text_secondary']};
                border: 1px solid {c['border']};
                border-radius: 10px;
                font-size: 15px;
                font-weight: 600;
                font-family: {_FONT};
            }}
        """)
        self.status_label.hide()

        # Animate rolling dots on button
        dot_frames = ["·", "· ·", "· · ·", "· · · ·", "  · · ·", "    · ·", "      ·", ""]
        self._spinner_frame = 0
        def _animate_dots():
            self._spinner_frame = (self._spinner_frame + 1) % len(dot_frames)
            self.generate_btn.setText(dot_frames[self._spinner_frame])
        self.generate_btn.setText(dot_frames[0])
        self._spinner_timer = QTimer()
        self._spinner_timer.timeout.connect(_animate_dots)
        self._spinner_timer.start(200)

        self._start_generation(prompt)

    def _start_generation(self, prompt):
        pkg = _get_package()
        if not pkg:
            self._on_error("Something went wrong. Try again, and if that doesn't work, try again later.")
            return

        dock_widget = getattr(pkg, 'dock_widget', None)
        if dock_widget is None:
            create_fn = getattr(pkg, 'create_dock_widget', None)
            if create_fn:
                create_fn()
            dock_widget = getattr(pkg, 'dock_widget', None)

        if not dock_widget:
            self._on_error("Something went wrong. Try again, and if that doesn't work, try again later.")
            return

        if not dock_widget.isVisible():
            dock_widget.setFloating(True)
            dock_widget.setWindowOpacity(0)
            dock_widget.move(-9999, -9999)
            dock_widget.show()

        panel = dock_widget.widget()
        if not panel or not hasattr(panel, 'web'):
            self._on_error("Something went wrong. Try again, and if that doesn't work, try again later.")
            return

        if hasattr(panel, 'show_web_view'):
            panel.show_web_view()

        # Inject prompt
        js_inject = """
        (function() {
            var searchInput = document.querySelector('input[placeholder*="medical"], input[placeholder*="question"], textarea, input[type="text"]');
            if (searchInput) {
                var text = %s;
                var nativeSetter = Object.getOwnPropertyDescriptor(
                    searchInput.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype,
                    'value'
                ).set;
                nativeSetter.call(searchInput, text);
                searchInput.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, inputType: 'insertText', data: text }));
                searchInput.dispatchEvent(new Event('change', { bubbles: true }));
                searchInput.focus();
                setTimeout(function() {
                    var submitButton = document.querySelector('button[type="submit"]') ||
                                     document.querySelector('button:has(svg)') ||
                                     searchInput.closest('form')?.querySelector('button');
                    if (submitButton) {
                        submitButton.click();
                    } else {
                        searchInput.dispatchEvent(new KeyboardEvent('keydown', {
                            key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
                            bubbles: true, cancelable: true
                        }));
                    }
                }, 100);
            }
        })();
        """ % repr(prompt)

        panel.web.page().runJavaScript(js_inject)

        # Poll JS — use innerText to preserve <card> tags for parsing
        poll_js = """
        (function() {
            window.ankiCreateResult = null;
            window.ankiCreatePartial = null;
            window.ankiCreateError = null;
            var initialCount = document.querySelectorAll('article.MuiBox-root').length;
            var pollCount = 0;
            var maxPolls = 134;
            var lastTextLength = -1;
            var stableCount = 0;

            var pollInterval = setInterval(function() {
                pollCount++;
                if (pollCount > maxPolls) {
                    clearInterval(pollInterval);
                    window.ankiCreateResult = 'ERROR_TIMEOUT';
                    return;
                }

                var errorBanner = document.querySelector('.MuiAlert-root, [role="alert"], .MuiSnackbar-root');
                if (errorBanner) {
                    var errText = errorBanner.innerText || errorBanner.textContent || '';
                    if (errText.length > 5) {
                        window.ankiCreateError = errText.trim();
                    }
                }

                var articles = document.querySelectorAll('article.MuiBox-root');
                if (articles.length <= initialCount) return;

                var lastArticle = articles[articles.length - 1];
                var text = lastArticle.innerText || lastArticle.textContent || '';
                if (text.length === 0) return;

                window.ankiCreatePartial = text;

                if (text.length === lastTextLength) {
                    stableCount++;
                    if (stableCount >= 5) {
                        clearInterval(pollInterval);
                        window.ankiCreateResult = text;
                    }
                } else {
                    lastTextLength = text.length;
                    stableCount = 0;
                }
            }, 300);
        })();
        """

        QTimer.singleShot(1000, lambda: panel.web.page().runJavaScript(poll_js))
        QTimer.singleShot(2000, self._start_python_poll)

    def _start_python_poll(self):
        global _ai_create_timer

        pkg = _get_package()
        dock_widget = getattr(pkg, 'dock_widget', None) if pkg else None
        if not dock_widget:
            self._on_error("Something went wrong. Try again, and if that doesn't work, try again later.")
            return

        panel = dock_widget.widget()
        if not panel or not hasattr(panel, 'web'):
            self._on_error("Something went wrong. Try again, and if that doesn't work, try again later.")
            return

        poll_count = [0]
        last_partial = [None]
        editor = self._editor
        modal = self

        def check_result():
            poll_count[0] += 1
            if poll_count[0] > 80:
                _ai_create_timer.stop()
                _cleanup_create_panel()
                if not _has_internet():
                    tooltip("No internet connection. Check your connection and try again.", period=3000)
                else:
                    tooltip("Something went wrong. Try again, and if that doesn't work, try again later.", period=3000)
                return

            panel.web.page().runJavaScript(
                "[window.ankiCreatePartial, window.ankiCreateResult, window.ankiCreateError]",
                on_poll_result
            )

        def on_poll_result(result):
            if not result or not isinstance(result, list):
                return
            partial = result[0] if len(result) > 0 else None
            final = result[1] if len(result) > 1 else None
            error = result[2] if len(result) > 2 else None

            if error and isinstance(error, str):
                _ai_create_timer.stop()
                _cleanup_create_panel()
                tooltip("Something went wrong. Try again, and if that doesn't work, try again later.", period=3000)
                return

            # Stream partial — parse even incomplete tags and fill editor live
            if partial and isinstance(partial, str) and partial != last_partial[0]:
                last_partial[0] = partial
                front, back = parse_partial_card(partial)
                if front and editor and editor.note:
                    editor.note.fields[0] = front.replace('\n', '<br>')
                    editor.note.fields[1] = (back or '').replace('\n', '<br>')
                    editor.loadNote()
                    # Auto-close modal once content starts streaming
                    try:
                        if modal.isVisible():
                            modal.close()
                    except RuntimeError:
                        pass

            if final and isinstance(final, str):
                _ai_create_timer.stop()
                _cleanup_create_panel()

                if final == 'ERROR_TIMEOUT':
                    tooltip("Something went wrong. Try again, and if that doesn't work, try again later.", period=3000)
                    return

                front, back = parse_single_card(final)
                if front and editor and editor.note:
                    editor.note.fields[0] = front.replace('\n', '<br>')
                    editor.note.fields[1] = (back or '').replace('\n', '<br>')
                    editor.loadNote()
                    tooltip("Card created! Edit if needed, then click Add.", period=3000)

        _ai_create_timer = QTimer()
        _ai_create_timer.timeout.connect(check_result)
        _ai_create_timer.start(500)

    def _cleanup_panel(self):
        pkg = _get_package()
        dock_widget = getattr(pkg, 'dock_widget', None) if pkg else None
        if dock_widget:
            dock_widget.hide()
            dock_widget.setWindowOpacity(1)
            dock_widget.setFloating(False)
            mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)

    def _fill_editor(self, front, back):
        """Fill the editor Front/Back fields and close."""
        if self._editor and self._editor.note:
            self._editor.note.fields[0] = front.replace('\n', '<br>')
            self._editor.note.fields[1] = back.replace('\n', '<br>')
            self._editor.loadNote()
            tooltip("Card created! Edit if needed, then click Add.", period=3000)
        self.close()

    def _on_error(self, message):
        c = ThemeManager.get_palette()
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {c['danger']}; font-size: 12px; font-family: {_FONT};")
        self.status_label.show()
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Try Again")
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['accent']};
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 600;
                font-family: {_FONT};
            }}
            QPushButton:hover {{ background: {c['accent_hover']}; }}
        """)

    def closeEvent(self, event):
        if self._spinner_timer:
            self._spinner_timer.stop()
        if self._overlay:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None
        super().closeEvent(event)


def show_ai_create(editor):
    """Show the AI Create modal for the given editor."""
    if not _has_internet():
        tooltip("No internet connection. Check your connection and try again.", period=3000)
        return

    # Create overlay on the editor's parent window
    parent_window = editor.parentWindow
    overlay = ModalOverlay(parent_window)
    overlay.show()
    overlay.raise_()

    window = AICreateWindow(editor, parent_window)
    window._overlay = overlay
    window.show()
    window.raise_()

    # Prevent GC
    mw._ai_create_overlay = overlay
    mw._ai_create_window = window


def setup_editor_button(buttons, editor):
    """Add AI Create button to editor toolbar."""
    button = editor.addButton(
        icon=None,
        cmd="ai_create",
        func=show_ai_create,
        tip="AI Create - Generate a card from pasted content",
        label="AI Create",
    )
    buttons.append(button)


# ─── AI Answer ───────────────────────────────────────────────────────

AI_ANSWER_PROMPT = """Answer the following question for a flashcard. Be concise and direct — answer only what is asked with no extra fluff or filler. Scale your response length to the complexity of the question. Do not ask follow-up questions at the end. Do not add disclaimers, caveats, or unnecessary elaboration.

Question:
{question}"""

# Shared JS for clean text extraction (same as explain feature)
_EXTRACT_TEXT_JS = """
function extractCleanText(article) {
    var paragraphs = article.querySelectorAll('p');
    var html = '';
    paragraphs.forEach(function(p) {
        if (p.closest('.MuiStepper-root')) return;
        if (p.closest('.brandable--references')) return;
        if (p.closest('.MuiCollapse-hidden')) return;
        if (p.classList.contains('MuiTypography-body2')) return;
        var clone = p.cloneNode(true);
        clone.querySelectorAll('.markdown-article-citation-chip').forEach(function(c) { c.remove(); });
        clone.querySelectorAll('[aria-hidden="true"]').forEach(function(c) { c.remove(); });
        var cleaned = clone.innerHTML.trim();
        if (cleaned.length > 0) {
            html += cleaned + '<br><br>';
        }
    });
    return html.replace(/<br><br>$/, '');
}
"""

_ai_answer_timer = None


def _handle_ai_answer(editor):
    """Read Front field, generate answer, stream into Back field."""
    global _ai_answer_timer

    if not editor.note:
        return

    question = editor.note.fields[0].strip()
    if not question:
        tooltip("Type a question in the Front field first.", period=2000)
        return

    import re as _re
    clean_q = _re.sub(r'<[^>]+>', '', question).strip()
    if not clean_q:
        tooltip("Type a question in the Front field first.", period=2000)
        return

    if not _has_internet():
        tooltip("No internet connection. Check your connection and try again.", period=3000)
        return

    prompt = AI_ANSWER_PROMPT.format(question=clean_q)

    # Show loading state with spinner dots
    editor.web.eval("""
    (function() {
        var btn = document.getElementById('ai-answer-btn');
        if (btn) {
            btn.dataset.generating = 'true';
            btn.style.pointerEvents = 'none';
            btn.style.cursor = 'default';
            btn.innerHTML = '<span style="display:inline-flex;gap:2px;align-items:center;">' +
                '<span style="width:3px;height:3px;border-radius:50%;background:currentColor;animation:aiBounce 1.4s infinite ease-in-out both;animation-delay:-0.32s;"></span>' +
                '<span style="width:3px;height:3px;border-radius:50%;background:currentColor;animation:aiBounce 1.4s infinite ease-in-out both;animation-delay:-0.16s;"></span>' +
                '<span style="width:3px;height:3px;border-radius:50%;background:currentColor;animation:aiBounce 1.4s infinite ease-in-out both;"></span>' +
                '</span>';
        }
    })();
    """)

    pkg = _get_package()
    if not pkg:
        _reset_btn(editor)
        tooltip("Something went wrong. Try again, and if that doesn't work, try again later.", period=3000)
        return

    dock_widget = getattr(pkg, 'dock_widget', None)
    if dock_widget is None:
        create_fn = getattr(pkg, 'create_dock_widget', None)
        if create_fn:
            create_fn()
        dock_widget = getattr(pkg, 'dock_widget', None)

    if not dock_widget:
        _reset_btn(editor)
        tooltip("Something went wrong. Try again, and if that doesn't work, try again later.", period=3000)
        return

    if not dock_widget.isVisible():
        dock_widget.setFloating(True)
        dock_widget.setWindowOpacity(0)
        dock_widget.move(-9999, -9999)
        dock_widget.show()

    panel = dock_widget.widget()
    if not panel or not hasattr(panel, 'web'):
        _reset_btn(editor)
        tooltip("Something went wrong. Try again, and if that doesn't work, try again later.", period=3000)
        return

    if hasattr(panel, 'show_web_view'):
        panel.show_web_view()

    # Inject prompt
    js_inject = """
    (function() {
        var searchInput = document.querySelector('input[placeholder*="medical"], input[placeholder*="question"], textarea, input[type="text"]');
        if (searchInput) {
            var text = %s;
            var nativeSetter = Object.getOwnPropertyDescriptor(
                searchInput.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype,
                'value'
            ).set;
            nativeSetter.call(searchInput, text);
            searchInput.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, inputType: 'insertText', data: text }));
            searchInput.dispatchEvent(new Event('change', { bubbles: true }));
            searchInput.focus();
            setTimeout(function() {
                var submitButton = document.querySelector('button[type="submit"]') ||
                                 document.querySelector('button:has(svg)') ||
                                 searchInput.closest('form')?.querySelector('button');
                if (submitButton) { submitButton.click(); }
                else { searchInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true })); }
            }, 100);
        }
    })();
    """ % repr(prompt)

    panel.web.page().runJavaScript(js_inject)

    # Poll with clean extraction (same as explain feature)
    poll_js = _EXTRACT_TEXT_JS + """
    (function() {
        window.ankiAnswerResult = null;
        window.ankiAnswerPartial = null;
        var initialCount = document.querySelectorAll('article.MuiBox-root').length;
        var pollCount = 0;
        var maxPolls = 134;
        var lastTextLength = -1;
        var stableCount = 0;

        var pollInterval = setInterval(function() {
            pollCount++;
            if (pollCount > maxPolls) {
                clearInterval(pollInterval);
                window.ankiAnswerResult = 'ERROR_TIMEOUT';
                return;
            }
            var articles = document.querySelectorAll('article.MuiBox-root');
            if (articles.length <= initialCount) return;
            var lastArticle = articles[articles.length - 1];
            var text = extractCleanText(lastArticle);
            if (text.length === 0) return;

            window.ankiAnswerPartial = text;

            if (text.length === lastTextLength) {
                stableCount++;
                if (stableCount >= 5) {
                    clearInterval(pollInterval);
                    window.ankiAnswerResult = text;
                }
            } else {
                lastTextLength = text.length;
                stableCount = 0;
            }
        }, 300);
    })();
    """

    QTimer.singleShot(1000, lambda: panel.web.page().runJavaScript(poll_js))

    # Python poll — stream partial results into Back field
    def start_poll():
        global _ai_answer_timer
        poll_count = [0]
        last_sent = [None]

        def check():
            poll_count[0] += 1
            if poll_count[0] > 80:
                _ai_answer_timer.stop()
                _cleanup()
                _reset_btn(editor)
                if not _has_internet():
                    tooltip("No internet connection. Check your connection and try again.", period=3000)
                else:
                    tooltip("Something went wrong. Try again, and if that doesn't work, try again later.", period=3000)
                return

            panel.web.page().runJavaScript(
                "[window.ankiAnswerPartial, window.ankiAnswerResult]",
                lambda result: on_result(result)
            )

        def on_result(result):
            if not result or not isinstance(result, list):
                return
            partial = result[0] if len(result) > 0 else None
            final = result[1] if len(result) > 1 else None

            # Stream partial into Back field
            if partial and isinstance(partial, str) and partial != last_sent[0]:
                last_sent[0] = partial
                if editor.note:
                    editor.note.fields[1] = partial
                    editor.loadNote()

            if final and isinstance(final, str):
                _ai_answer_timer.stop()
                _cleanup()

                if final == 'ERROR_TIMEOUT':
                    _reset_btn(editor)
                    tooltip("Something went wrong. Try again, and if that doesn't work, try again later.", period=3000)
                    return

                if editor.note:
                    editor.note.fields[1] = final
                    editor.loadNote()
                _reset_btn(editor)

        def _cleanup():
            pkg2 = _get_package()
            dw = getattr(pkg2, 'dock_widget', None) if pkg2 else None
            if dw:
                dw.hide()
                dw.setWindowOpacity(1)
                dw.setFloating(False)
                mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dw)

        _ai_answer_timer = QTimer()
        _ai_answer_timer.timeout.connect(check)
        _ai_answer_timer.start(500)

    QTimer.singleShot(2000, start_poll)


def _reset_btn(editor):
    """Reset the AI Answer button to normal state."""
    editor.web.eval("""
    (function() {
        var btn = document.getElementById('ai-answer-btn');
        if (btn) {
            btn.textContent = 'AI Answer';
            btn.style.opacity = '1';
            btn.style.pointerEvents = 'auto';
            btn.style.cursor = 'pointer';
            delete btn.dataset.generating;
        }
    })();
    """)


def on_editor_load_note(editor):
    """Inject AI Answer button into the Back field header, left of pin icon."""
    c = ThemeManager.get_palette()
    is_dark = ThemeManager.is_night_mode()
    btn_color_active = c['text_secondary']
    btn_hover = c['accent']
    disabled_color = "#666" if is_dark else "#bbb"

    js = f"""
    (function() {{
        // Don't inject twice
        if (document.getElementById('ai-answer-btn')) return;

        // Inject spinner keyframes once
        if (!document.getElementById('ai-answer-spinner-style')) {{
            var style = document.createElement('style');
            style.id = 'ai-answer-spinner-style';
            style.textContent = '@keyframes aiBounce {{ 0%, 80%, 100% {{ transform: scale(0); }} 40% {{ transform: scale(1); }} }}';
            document.head.appendChild(style);
        }}

        // Find the Back field's label-container using Anki's Svelte class structure
        var labelContainers = document.querySelectorAll('.label-container');
        var fieldState = null;
        for (var i = 0; i < labelContainers.length; i++) {{
            var labelName = labelContainers[i].querySelector('.label-name');
            if (labelName && labelName.textContent.trim() === 'Back') {{
                fieldState = labelContainers[i].querySelector('.field-state');
                break;
            }}
        }}

        if (!fieldState) return;

        var btn = document.createElement('button');
        btn.id = 'ai-answer-btn';
        btn.textContent = 'AI Answer';
        btn.style.cssText = 'background: transparent; color: {disabled_color}; border: none; border-radius: 4px; padding: 0 1px; margin: 0 -4px 0 0; font-size: 11px; cursor: default; font-family: -apple-system, sans-serif; transition: color 0.15s; pointer-events: none; line-height: 1;';

        btn.onclick = function(e) {{
            e.preventDefault();
            e.stopPropagation();
            pycmd('ai_answer');
        }};

        // Insert as first child of field-state (left of pin icon)
        fieldState.insertBefore(btn, fieldState.firstChild);

        // Watch Front field for changes to enable/disable
        function getFrontText() {{
            // Method 1: Shadow DOM (modern Anki with Svelte components)
            var fields = document.querySelectorAll('.field-container');
            if (fields.length > 0) {{
                var allEls = fields[0].querySelectorAll('*');
                for (var k = 0; k < allEls.length; k++) {{
                    if (allEls[k].shadowRoot) {{
                        var ce = allEls[k].shadowRoot.querySelector('[contenteditable]');
                        if (ce) return (ce.innerText || '').trim();
                    }}
                }}
            }}
            // Method 2: Direct contenteditable (older Anki)
            var editables = document.querySelectorAll('[contenteditable="true"]');
            if (editables.length > 0) return (editables[0].innerText || '').trim();
            return '';
        }}

        var _btnEnabled = false;
        function checkFrontField() {{
            // Skip check while generating
            if (btn.dataset.generating === 'true') return;
            var text = getFrontText();
            var shouldEnable = text.length > 0;
            if (shouldEnable === _btnEnabled) return;
            _btnEnabled = shouldEnable;
            if (shouldEnable) {{
                btn.style.color = '{btn_color_active}';
                btn.style.cursor = 'pointer';
                btn.style.pointerEvents = 'auto';
                btn.onmouseenter = function() {{ btn.style.color = '{btn_hover}'; }};
                btn.onmouseleave = function() {{ btn.style.color = '{btn_color_active}'; }};
            }} else {{
                btn.style.color = '{disabled_color}';
                btn.style.cursor = 'default';
                btn.style.pointerEvents = 'none';
                btn.onmouseenter = null;
                btn.onmouseleave = null;
            }}
        }}

        setInterval(checkFrontField, 500);
        checkFrontField();
    }})();
    """

    # Move AI Create button next to Cards... in the notetypeButtons group
    # Hide AI Create button immediately so it's not visible in wrong position
    hide_js = """
    (function() {
        var aiBtn = document.querySelector('button[title*="AI Create"]');
        if (aiBtn && !aiBtn.dataset.moved) {
            var el = aiBtn.parentElement || aiBtn;
            el.style.display = 'none';
        }
    })();
    """

    move_js = """
    (function() {
        // Find the AI Create button (added by addButton to the right-side toolbar)
        var aiBtn = document.querySelector('button[title*="AI Create"]');
        if (!aiBtn || aiBtn.dataset.moved) return;

        // Find the "Cards..." button text in the notetypeButtons group
        var allBtns = document.querySelectorAll('button');
        var cardsBtn = null;
        for (var i = 0; i < allBtns.length; i++) {
            if (allBtns[i].textContent.trim() === 'Cards...') {
                cardsBtn = allBtns[i];
                break;
            }
        }
        if (!cardsBtn) return;

        // Move AI Create button right after Cards... button
        var cardsParent = cardsBtn.parentElement;
        if (cardsParent && cardsParent.parentElement) {
            var cardsWrapper = cardsParent;
            var moveEl = aiBtn.parentElement || aiBtn;
            cardsWrapper.parentElement.insertBefore(moveEl, cardsWrapper.nextSibling);
            moveEl.style.display = '';
            aiBtn.dataset.moved = 'true';
        }

        // Keep AI Create always active (Anki disables toolbar buttons when no field focused)
        function keepActive() {
            if (aiBtn.disabled) aiBtn.disabled = false;
            aiBtn.style.opacity = '1';
            aiBtn.style.pointerEvents = 'auto';
        }
        keepActive();
        new MutationObserver(keepActive).observe(aiBtn, { attributes: true, attributeFilter: ['disabled', 'style'] });
    })();
    """

    # Hide immediately so button is never visible in wrong position
    editor.web.eval(hide_js)

    def _inject():
        editor.web.eval(hide_js)
        editor.web.eval(js)
        editor.web.eval(move_js)

    QTimer.singleShot(300, _inject)
