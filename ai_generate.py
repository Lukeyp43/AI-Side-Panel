"""
AI Generate - Multi-step wizard for generating flashcards using OpenEvidence AI.
Custom frameless window with step-by-step flow and auto-generation via hidden panel.
"""

import re
import sys
import socket
from aqt import mw
from aqt.utils import tooltip


def _has_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2).close()
        return True
    except OSError:
        return False

from .utils import ADDON_NAME
from .theme_manager import ThemeManager, CloseButton

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTextEdit, QScrollArea, QCheckBox, QLineEdit, QStackedWidget,
        QSizePolicy, QGraphicsDropShadowEffect, QSpacerItem
    )
    from PyQt6.QtCore import Qt, QTimer, QPoint, QEvent
    from PyQt6.QtGui import QCursor, QColor, QPainterPath, QRegion, QPainter
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTextEdit, QScrollArea, QCheckBox, QLineEdit, QStackedWidget,
        QSizePolicy, QGraphicsDropShadowEffect, QSpacerItem
    )
    from PyQt5.QtCore import Qt, QTimer, QPoint, QEvent
    from PyQt5.QtGui import QCursor, QColor, QPainterPath, QRegion, QPainter
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        from aqt.qt import QWebEngineView

IS_MAC = sys.platform == "darwin"

# ─── Prompt Templates ───────────────────────────────────────────────

PROMPTS = {
    ("topic", "normal"): """Create exactly {count} flashcards about the topic below. Each flashcard should test ONE concept. Keep questions clear and specific. Keep answers concise (1-3 sentences max).

You MUST format your response EXACTLY like this, with no other text before or after:

<card>
<front>question here</front>
<back>answer here</back>
</card>

Topic:
{content}""",

    ("topic", "mc"): """Create exactly {count} multiple choice flashcards about the topic below. Each card should have 4 options (A, B, C, D) with one correct answer.

You MUST format your response EXACTLY like this, with no other text before or after:

<card>
<front>What is the primary function of X?
A) Option one
B) Option two
C) Option three
D) Option four</front>
<back>B) Option two - brief explanation why this is correct.</back>
</card>

Topic:
{content}""",

    ("topic", "tf"): """Create exactly {count} true or false flashcards about the topic below. Each card should have a clear statement that is either true or false.

You MUST format your response EXACTLY like this, with no other text before or after:

<card>
<front>True or False: Statement about a concept here.</front>
<back>True - brief explanation of why.</back>
</card>

Topic:
{content}""",

    ("topic", "mix"): """Create exactly {count} flashcards about the topic below using a MIX of formats: some normal Q&A, some multiple choice (4 options A-D), and some true/false. Vary the format across cards.

You MUST format your response EXACTLY like this, with no other text before or after:

<card>
<front>question or statement here</front>
<back>answer here</back>
</card>

Topic:
{content}""",

    ("notes", "normal"): """Create exactly {count} flashcards from the student notes below. Each flashcard should test ONE key concept from the notes. Keep questions clear and specific. Keep answers concise (1-3 sentences max).

You MUST format your response EXACTLY like this, with no other text before or after:

<card>
<front>question here</front>
<back>answer here</back>
</card>

Student Notes:
{content}""",

    ("notes", "mc"): """Create exactly {count} multiple choice flashcards from the student notes below. Each card should have 4 options (A, B, C, D) with one correct answer. Test key concepts from the notes.

You MUST format your response EXACTLY like this, with no other text before or after:

<card>
<front>What is the primary function of X?
A) Option one
B) Option two
C) Option three
D) Option four</front>
<back>B) Option two - brief explanation why this is correct.</back>
</card>

Student Notes:
{content}""",

    ("notes", "tf"): """Create exactly {count} true or false flashcards from the student notes below. Each card should have a clear statement that is either true or false, testing key concepts.

You MUST format your response EXACTLY like this, with no other text before or after:

<card>
<front>True or False: Statement about a concept here.</front>
<back>True - brief explanation of why.</back>
</card>

Student Notes:
{content}""",

    ("notes", "mix"): """Create exactly {count} flashcards from the student notes below using a MIX of formats: some normal Q&A, some multiple choice (4 options A-D), and some true/false. Vary the format across cards.

You MUST format your response EXACTLY like this, with no other text before or after:

<card>
<front>question or statement here</front>
<back>answer here</back>
</card>

Student Notes:
{content}""",
}


# ─── Helpers ─────────────────────────────────────────────────────────

def parse_cards(response_text):
    """Parse <card><front>...</front><back>...</back></card> tags from response."""
    cards = re.findall(
        r'<card>\s*<front>(.*?)</front>\s*<back>(.*?)</back>\s*</card>',
        response_text,
        re.DOTALL
    )
    return [(front.strip(), back.strip()) for front, back in cards]


def get_deck_names():
    """Get all deck names from the collection."""
    if not mw.col:
        return []
    return [d.name for d in mw.col.decks.all_names_and_ids()]


def create_cards_in_deck(cards, deck_name):
    """Create Basic notes in the specified deck. Returns count of cards created."""
    if not mw.col:
        return 0
    deck_id = mw.col.decks.id(deck_name)
    model = mw.col.models.by_name('Basic')
    if not model:
        return 0
    count = 0
    for front, back in cards:
        note = mw.col.new_note(model)
        note['Front'] = str(front).replace('\n', '<br>')
        note['Back'] = str(back).replace('\n', '<br>')
        mw.col.add_note(note, deck_id)
        count += 1
    mw.reset()
    return count


def _get_package():
    """Get the package module to access dock_widget and create_dock_widget.
    Uses the dynamic package name so it works no matter what folder the
    addon is installed as."""
    return sys.modules.get(__name__.rsplit('.', 1)[0]) or sys.modules.get('anki_copilot') or sys.modules.get('the_ai_panel')


# ─── Font constant ───────────────────────────────────────────────────

_FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'


class CheckmarkWidget(QWidget):
    """A small custom-painted checkmark toggle (no Qt stylesheet leaking)."""

    def __init__(self, checked=True, check_color="#3b82f6", border_color="#3a3a3f", bg_color="#2a2a2e", parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._checked = checked
        self._check_color = check_color
        self._border_color = border_color
        self._bg_color = bg_color
        self._callbacks = []

    def isChecked(self):
        return self._checked

    def setChecked(self, val):
        if self._checked != val:
            self._checked = val
            self.update()
            for cb in self._callbacks:
                cb(val)

    def toggled_connect(self, fn):
        self._callbacks.append(fn)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()
        for cb in self._callbacks:
            cb(self._checked)

    def paintEvent(self, event):
        try:
            from PyQt6.QtCore import QRectF, QPointF
            from PyQt6.QtGui import QPen
        except ImportError:
            from PyQt5.QtCore import QRectF, QPointF
            from PyQt5.QtGui import QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(1, 1, 16, 16)

        if self._checked:
            # Filled rounded rect
            p.setPen(QPen(QColor(self._check_color), 1.5))
            p.setBrush(QColor(self._check_color))
            p.drawRoundedRect(rect, 4, 4)
            # White checkmark
            pen = QPen(QColor("#ffffff"), 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(QPointF(4.5, 9.5), QPointF(7.5, 12.5))
            p.drawLine(QPointF(7.5, 12.5), QPointF(13.5, 5.5))
        else:
            # Empty rounded rect
            p.setPen(QPen(QColor(self._border_color), 1.5))
            p.setBrush(QColor(self._bg_color))
            p.drawRoundedRect(rect, 4, 4)

        p.end()


# ─── Main Window ─────────────────────────────────────────────────────

class ModalOverlay(QWidget):
    """Dark overlay that covers the Anki main window behind the modal.
    Uses a stylesheet rgba background with WA_StyledBackground — the naive
    paintEvent+fillRect(alpha) approach doesn't composite on Windows for a
    child QWidget, leaving the backdrop fully transparent."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(0, 0, 0, 120);")
        if parent:
            self.setGeometry(parent.rect())
            parent.installEventFilter(self)
        self.raise_()

    def eventFilter(self, watched, event):
        if watched == self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event):
        event.accept()


class AIGenerateWindow(QWidget):
    """Custom frameless wizard window for AI card generation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Qt.Dialog + parent = stays above parent window but NOT above other
        # OS windows. Keeps the wizard above Anki without staying on top of
        # Chrome/other apps when the user switches focus.
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(460, 340)
        self.resize(500, 380)

        # State
        self._mode = None        # "topic" or "notes"
        self._deck_name = None
        self._card_count = 10
        self._card_type = "normal"  # "normal", "mc", "tf", "mix"
        self._parsed_cards = []
        self._card_checkboxes = []
        self._drag_pos = None
        self._poll_timer = None
        self._dot_timer = None
        self._overlay = None

        self._setup_ui()
        self._center_on_screen()

    def _center_on_screen(self):
        if mw:
            geo = mw.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)

    # ─── UI Setup ────────────────────────────────────────────────

    def _setup_ui(self):
        c = ThemeManager.get_palette()

        self.setObjectName("AIGenWindow")
        self.setStyleSheet(f"QWidget#AIGenWindow {{ background: {c['background']}; border: 1px solid {c['border']}; border-radius: 14px; }}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        self._build_mode_page(c)        # 0
        self._build_deck_page(c)        # 1
        self._build_count_page(c)       # 2
        self._build_type_page(c)        # 3
        self._build_content_page(c)     # 4
        self._build_generating_page(c)  # 5
        self._build_preview_page(c)     # 6

    # ─── Title Bar ───────────────────────────────────────────────

    def _build_title_bar(self, c, parent_layout):
        bar = QWidget()
        bar.setFixedHeight(38)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 12, 0)

        layout.addStretch()

        close_btn = CloseButton(size=24)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        bar.mousePressEvent = self._title_mouse_press
        bar.mouseMoveEvent = self._title_mouse_move
        parent_layout.addWidget(bar)

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
        """Apply rounded corner mask to clip the window edges."""
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(self.width()), float(self.height()), 14.0, 14.0)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    # ═══════════════════════════════════════════════════════════════
    # Page 0: Mode Selection
    # ═══════════════════════════════════════════════════════════════

    def _build_mode_page(self, c):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(0)

        # Header bar with just X
        header_bar = QWidget()
        header_bar.setFixedHeight(38)
        hb_layout = QHBoxLayout(header_bar)
        hb_layout.setContentsMargins(12, 0, 12, 0)
        hb_layout.addStretch()
        close_btn = CloseButton(size=24)
        close_btn.clicked.connect(self.close)
        hb_layout.addWidget(close_btn)
        header_bar.mousePressEvent = self._title_mouse_press
        header_bar.mouseMoveEvent = self._title_mouse_move
        layout.addWidget(header_bar)

        # Full-width divider line
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {c['border']};")
        layout.addWidget(line)

        # Content area with padding
        content = QVBoxLayout()
        content.setContentsMargins(28, 16, 28, 0)
        content.setSpacing(16)

        header = QLabel("What would you like to create cards from?")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"color: {c['text']}; font-size: 18px; font-weight: 600; font-family: {_FONT};")
        header.setWordWrap(True)
        content.addWidget(header)

        # Two big vertical cards side by side
        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)

        cards_row.addWidget(self._make_mode_card(
            "Describe", "Tell AI what you\nwant cards about",
            lambda: self._select_mode("topic"), c
        ))
        cards_row.addWidget(self._make_mode_card(
            "Notes Dump", "Generate from\nyour notes",
            lambda: self._select_mode("notes"), c
        ))

        content.addLayout(cards_row, 1)
        layout.addLayout(content, 1)
        self.stack.addWidget(page)

    def _make_mode_card(self, title, description, on_click, c):
        is_dark = ThemeManager.is_night_mode()
        card_bg = "#2a2a2e" if is_dark else "#eaeaee"
        card_border = "#3a3a3f" if is_dark else "#d0d0d5"
        hover_border = "rgba(120, 180, 255, 0.7)" if is_dark else "rgba(59, 130, 246, 0.5)"
        hover_bg = "rgba(120, 180, 255, 0.06)" if is_dark else "rgba(59, 130, 246, 0.04)"

        card = QPushButton()
        card.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card.clicked.connect(on_click)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 0, 20, 0)
        card_layout.setSpacing(6)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {c['text']}; font-size: 24px; font-weight: 700; font-family: {_FONT}; background: transparent; border: none;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"color: {c['text_secondary']}; font-size: 14px; background: transparent; border: none;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(desc_label)

        card.setStyleSheet(f"""
            QPushButton {{
                background: {card_bg};
                border: 1px solid {card_border};
                border-radius: 12px;
            }}
            QPushButton:hover {{
                border-color: {hover_border};
                background: {hover_bg};
            }}
        """)
        return card

    def _select_mode(self, mode):
        self._mode = mode
        self.stack.setCurrentIndex(1)

    # ═══════════════════════════════════════════════════════════════
    # Page 1: Deck Selection
    # ═══════════════════════════════════════════════════════════════

    def _build_deck_page(self, c):
        is_dark = ThemeManager.is_night_mode()
        card_bg = "#2a2a2e" if is_dark else "#eaeaee"
        card_border = "#3a3a3f" if is_dark else "#d0d0d5"
        hover_border = "rgba(120, 180, 255, 0.7)" if is_dark else "rgba(59, 130, 246, 0.5)"
        hover_bg = "rgba(120, 180, 255, 0.06)" if is_dark else "rgba(59, 130, 246, 0.04)"
        selected_border = c['accent']
        selected_bg = "rgba(59, 130, 246, 0.12)" if is_dark else "rgba(59, 130, 246, 0.08)"

        page = QWidget()
        page.setStyleSheet("border: none;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar: back + X
        header_bar = QWidget()
        header_bar.setFixedHeight(38)
        hb_layout = QHBoxLayout(header_bar)
        hb_layout.setContentsMargins(12, 0, 12, 0)

        back_btn = QPushButton("\u2190")
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.setFixedSize(24, 24)
        back_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {c['text_secondary']}; border: none; border-radius: 6px; font-size: 18px; }}
            QPushButton:hover {{ background: {c['hover']}; color: {c['text']}; }}
        """)
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        hb_layout.addWidget(back_btn)

        hb_layout.addStretch()

        close_btn = CloseButton(size=24)
        close_btn.clicked.connect(self.close)
        hb_layout.addWidget(close_btn)
        header_bar.mousePressEvent = self._title_mouse_press
        header_bar.mouseMoveEvent = self._title_mouse_move
        layout.addWidget(header_bar)

        # Full-width divider
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {c['border']};")
        layout.addWidget(line)

        # Content area
        content = QVBoxLayout()
        content.setContentsMargins(28, 16, 28, 20)
        content.setSpacing(14)

        header = QLabel("Choose a deck")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"color: {c['text']}; font-size: 18px; font-weight: 600; font-family: {_FONT};")
        content.addWidget(header)

        # Two toggle cards side by side
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(12)

        self.existing_deck_btn = QPushButton("Existing Deck")
        self.new_deck_btn = QPushButton("New Deck")
        self._deck_toggle = "existing"

        for btn in (self.existing_deck_btn, self.new_deck_btn):
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFixedHeight(48)

        self.existing_deck_btn.clicked.connect(lambda: self._set_deck_toggle("existing"))
        self.new_deck_btn.clicked.connect(lambda: self._set_deck_toggle("new"))
        toggle_row.addWidget(self.existing_deck_btn)
        toggle_row.addWidget(self.new_deck_btn)
        content.addLayout(toggle_row)

        self._deck_card_bg = card_bg
        self._deck_card_border = card_border
        self._deck_hover_border = hover_border
        self._deck_hover_bg = hover_bg
        self._deck_selected_border = selected_border
        self._deck_selected_bg = selected_bg
        self._update_deck_toggle(c)

        # Deck list (scrollable, custom scrollbar)
        self.deck_scroll = QScrollArea()
        self.deck_scroll.setWidgetResizable(True)
        scrollbar_bg = c['background']
        scrollbar_handle = c['border']
        scrollbar_hover = c['text_secondary']
        self.deck_scroll.setStyleSheet(f"""
            QScrollArea {{ background: {c['background']}; border: none; }}
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

        self.deck_list_widget = QWidget()
        self.deck_list_widget.setStyleSheet(f"background: {c['background']};")
        self.deck_list_layout = QVBoxLayout(self.deck_list_widget)
        self.deck_list_layout.setContentsMargins(0, 4, 0, 4)
        self.deck_list_layout.setSpacing(6)
        # Create Next button early (before _populate_deck_list triggers _update_deck_next_btn)
        self.deck_next_btn = QPushButton("Next")
        self.deck_next_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.deck_next_btn.setFixedHeight(44)
        self.deck_next_btn.clicked.connect(self._on_deck_next)

        # New deck input (hidden, modern style) — also created early
        self.new_deck_input = QLineEdit()
        self.new_deck_input.setPlaceholderText("Enter new deck name...")
        self.new_deck_input.setFixedHeight(44)
        self.new_deck_input.setStyleSheet(f"""
            QLineEdit {{
                background: {card_bg};
                color: {c['text']};
                border: 1px solid {card_border};
                border-radius: 10px;
                padding: 6px 16px;
                font-size: 14px;
                font-family: {_FONT};
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
            }}
        """)
        self.new_deck_input.textChanged.connect(self._on_deck_input_changed)
        self.new_deck_input.hide()

        self._deck_buttons = []
        self._selected_deck_idx = -1
        self._populate_deck_list(c)
        self.deck_scroll.setWidget(self.deck_list_widget)
        content.addWidget(self.deck_scroll, 1)

        # New deck container (input + helper text, fills the space)
        self.new_deck_container = QWidget()
        nd_layout = QVBoxLayout(self.new_deck_container)
        nd_layout.setContentsMargins(0, 0, 0, 0)
        nd_layout.setSpacing(12)
        nd_layout.addWidget(self.new_deck_input)

        helper = QLabel("Your new deck will be created\nwhen cards are generated.")
        helper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        helper.setStyleSheet(f"color: {c['text_secondary']}; font-size: 12px; font-family: {_FONT};")
        nd_layout.addWidget(helper)
        nd_layout.addStretch()
        self.new_deck_container.hide()
        content.addWidget(self.new_deck_container, 1)

        layout.addLayout(content, 1)

        # Bottom: Next button
        bottom = QVBoxLayout()
        bottom.setContentsMargins(28, 0, 28, 20)
        self._update_deck_next_btn(c)
        bottom.addWidget(self.deck_next_btn)
        layout.addLayout(bottom)

        self.stack.addWidget(page)

    def _populate_deck_list(self, c):
        is_dark = ThemeManager.is_night_mode()
        item_bg = "#2a2a2e" if is_dark else "#eaeaee"
        item_border = "#3a3a3f" if is_dark else "#d0d0d5"

        decks = get_deck_names()
        for i, name in enumerate(decks):
            btn = QPushButton(name)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFixedHeight(42)
            btn.clicked.connect(lambda checked, idx=i: self._select_deck(idx))
            self._deck_buttons.append((name, btn))
            self.deck_list_layout.addWidget(btn)
        self.deck_list_layout.addStretch()
        if decks:
            self._select_deck(0)
        else:
            self._update_all_deck_styles(c)

    def _select_deck(self, idx):
        c = ThemeManager.get_palette()
        self._selected_deck_idx = idx
        self._update_all_deck_styles(c)
        self._update_deck_next_btn(c)

    def _update_all_deck_styles(self, c):
        is_dark = ThemeManager.is_night_mode()
        item_bg = "#2a2a2e" if is_dark else "#eaeaee"
        item_border = "#3a3a3f" if is_dark else "#d0d0d5"

        for i, (name, btn) in enumerate(self._deck_buttons):
            if i == self._selected_deck_idx:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {self._deck_selected_bg};
                        color: {c['text']};
                        border: 1.5px solid {self._deck_selected_border};
                        border-radius: 8px;
                        font-size: 13px;
                        font-weight: 600;
                        text-align: left;
                        padding-left: 14px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {item_bg};
                        color: {c['text']};
                        border: 1px solid {item_border};
                        border-radius: 8px;
                        font-size: 13px;
                        text-align: left;
                        padding-left: 14px;
                    }}
                    QPushButton:hover {{
                        border-color: {self._deck_hover_border};
                        background: {self._deck_hover_bg};
                    }}
                """)

    def _set_deck_toggle(self, mode):
        self._deck_toggle = mode
        c = ThemeManager.get_palette()
        self._update_deck_toggle(c)
        if mode == "existing":
            self.deck_scroll.show()
            self.new_deck_container.hide()
            self._selected_deck_idx = -1
            self._update_all_deck_styles(c)
        else:
            self.deck_scroll.hide()
            self.new_deck_container.show()
            self.new_deck_input.show()
            self.new_deck_input.setFocus()
            self.new_deck_input.clear()
        self._update_deck_next_btn(c)

    def _update_deck_toggle(self, c):
        is_dark = ThemeManager.is_night_mode()
        card_bg = "#2a2a2e" if is_dark else "#eaeaee"
        card_border = "#3a3a3f" if is_dark else "#d0d0d5"
        sel_border = c['accent']
        sel_bg = "rgba(59, 130, 246, 0.12)" if is_dark else "rgba(59, 130, 246, 0.08)"
        hover_border = "rgba(120, 180, 255, 0.7)" if is_dark else "rgba(59, 130, 246, 0.5)"
        hover_bg = "rgba(120, 180, 255, 0.06)" if is_dark else "rgba(59, 130, 246, 0.04)"

        for btn, active in [(self.existing_deck_btn, self._deck_toggle == "existing"),
                            (self.new_deck_btn, self._deck_toggle == "new")]:
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {sel_bg};
                        color: {c['text']};
                        border: 1.5px solid {sel_border};
                        border-radius: 10px;
                        font-size: 14px;
                        font-weight: 600;
                        font-family: {_FONT};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {card_bg};
                        color: {c['text_secondary']};
                        border: 1px solid {card_border};
                        border-radius: 10px;
                        font-size: 14px;
                        font-family: {_FONT};
                    }}
                    QPushButton:hover {{
                        border-color: {hover_border};
                        background: {hover_bg};
                    }}
                """)

    def _on_deck_input_changed(self, text):
        c = ThemeManager.get_palette()
        self._update_deck_next_btn(c)

    def _update_deck_next_btn(self, c):
        """Enable/disable and style the Next button based on valid selection."""
        enabled = False
        if self._deck_toggle == "existing":
            enabled = self._selected_deck_idx >= 0 and self._selected_deck_idx < len(self._deck_buttons)
        else:
            enabled = bool(self.new_deck_input.text().strip())

        self.deck_next_btn.setEnabled(enabled)
        if enabled:
            self.deck_next_btn.setStyleSheet(f"""
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
        else:
            self.deck_next_btn.setStyleSheet(f"""
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

    def _on_deck_next(self):
        if self._deck_toggle == "existing":
            if self._selected_deck_idx < 0 or self._selected_deck_idx >= len(self._deck_buttons):
                return
            self._deck_name = self._deck_buttons[self._selected_deck_idx][0]
        else:
            name = self.new_deck_input.text().strip()
            if not name:
                return
            self._deck_name = name
        self.stack.setCurrentIndex(2)

    # ═══════════════════════════════════════════════════════════════
    # Page 2: Number of cards
    # ═══════════════════════════════════════════════════════════════

    def _build_count_page(self, c):
        page = QWidget()
        page.setStyleSheet("border: none;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._make_page_header(c, back_page=1))

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {c['border']};")
        layout.addWidget(line)

        content = QVBoxLayout()
        content.setContentsMargins(28, 16, 28, 0)
        content.setSpacing(20)

        header = QLabel("How many cards?")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"color: {c['text']}; font-size: 18px; font-weight: 600; font-family: {_FONT};")
        content.addWidget(header)

        # 2x2 grid of count buttons
        self._count_buttons = []

        row1 = QHBoxLayout()
        row1.setSpacing(14)
        row2 = QHBoxLayout()
        row2.setSpacing(14)

        for i, n in enumerate([5, 10, 15, 20]):
            btn = QPushButton(str(n))
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFixedHeight(70)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda checked, num=n: self._set_count(num))
            self._count_buttons.append((n, btn))
            if i < 2:
                row1.addWidget(btn)
            else:
                row2.addWidget(btn)

        content.addLayout(row1)
        content.addLayout(row2)
        self._update_count_buttons(c)
        content.addStretch()

        layout.addLayout(content, 1)

        bottom = QVBoxLayout()
        bottom.setContentsMargins(28, 0, 28, 20)
        next_btn = self._make_primary_btn("Next", c)
        next_btn.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        bottom.addWidget(next_btn)
        layout.addLayout(bottom)

        self.stack.addWidget(page)

    # ═══════════════════════════════════════════════════════════════
    # Page 3: Card type (2x2 grid)
    # ═══════════════════════════════════════════════════════════════

    def _build_type_page(self, c):
        page = QWidget()
        page.setStyleSheet("border: none;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._make_page_header(c, back_page=2))

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {c['border']};")
        layout.addWidget(line)

        content = QVBoxLayout()
        content.setContentsMargins(28, 16, 28, 0)
        content.setSpacing(14)

        header = QLabel("What type of cards?")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"color: {c['text']}; font-size: 18px; font-weight: 600; font-family: {_FONT};")
        content.addWidget(header)

        # 2x2 grid of type cards
        self._type_buttons = []
        types = [
            ("normal", "Normal", "Standard Q&A"),
            ("mc", "Multiple Choice", "4 options A-D"),
            ("tf", "True / False", "Statement + answer"),
            ("mix", "Mix", "All types combined"),
        ]

        row1 = QHBoxLayout()
        row1.setSpacing(14)
        row2 = QHBoxLayout()
        row2.setSpacing(14)

        for i, (key, title, desc) in enumerate(types):
            card = self._make_type_card(key, title, desc, c)
            if i < 2:
                row1.addWidget(card)
            else:
                row2.addWidget(card)

        content.addLayout(row1)
        content.addLayout(row2)
        self._update_type_buttons(c)
        content.addStretch()

        layout.addLayout(content, 1)

        bottom = QVBoxLayout()
        bottom.setContentsMargins(28, 0, 28, 20)
        next_btn = self._make_primary_btn("Next", c)
        next_btn.clicked.connect(self._go_to_content)
        bottom.addWidget(next_btn)
        layout.addLayout(bottom)

        self.stack.addWidget(page)

    def _make_type_card(self, key, title, desc, c):
        card = QPushButton()
        card.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        card.setFixedHeight(80)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.clicked.connect(lambda checked, k=key: self._set_card_type(k))

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 0, 12, 0)
        card_layout.setSpacing(3)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        t = QLabel(title)
        t.setStyleSheet(f"color: {c['text']}; font-size: 15px; font-weight: 700; font-family: {_FONT}; background: transparent; border: none;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(t)

        d = QLabel(desc)
        d.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px; font-family: {_FONT}; background: transparent; border: none;")
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(d)

        self._type_buttons.append((key, card, t, d))
        return card

    def _set_count(self, n):
        self._card_count = n
        self._update_count_buttons(ThemeManager.get_palette())

    def _update_count_buttons(self, c):
        is_dark = ThemeManager.is_night_mode()
        card_bg = "#2a2a2e" if is_dark else "#eaeaee"
        card_border = "#3a3a3f" if is_dark else "#d0d0d5"
        sel_border = c['accent']
        sel_bg = "rgba(59, 130, 246, 0.12)" if is_dark else "rgba(59, 130, 246, 0.08)"
        hover_border = "rgba(120, 180, 255, 0.7)" if is_dark else "rgba(59, 130, 246, 0.5)"
        hover_bg = "rgba(120, 180, 255, 0.06)" if is_dark else "rgba(59, 130, 246, 0.04)"

        for n, btn in self._count_buttons:
            if n == self._card_count:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {sel_bg};
                        color: {c['text']};
                        border: 1.5px solid {sel_border};
                        border-radius: 12px;
                        font-size: 22px;
                        font-weight: 700;
                        font-family: {_FONT};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {card_bg};
                        color: {c['text_secondary']};
                        border: 1px solid {card_border};
                        border-radius: 12px;
                        font-size: 22px;
                        font-family: {_FONT};
                    }}
                    QPushButton:hover {{
                        border-color: {hover_border};
                        background: {hover_bg};
                    }}
                """)

    def _set_card_type(self, key):
        self._card_type = key
        self._update_type_buttons(ThemeManager.get_palette())

    def _update_type_buttons(self, c):
        is_dark = ThemeManager.is_night_mode()
        card_bg = "#2a2a2e" if is_dark else "#eaeaee"
        card_border = "#3a3a3f" if is_dark else "#d0d0d5"
        sel_border = c['accent']
        sel_bg = "rgba(59, 130, 246, 0.12)" if is_dark else "rgba(59, 130, 246, 0.08)"
        hover_border = "rgba(120, 180, 255, 0.7)" if is_dark else "rgba(59, 130, 246, 0.5)"
        hover_bg = "rgba(120, 180, 255, 0.06)" if is_dark else "rgba(59, 130, 246, 0.04)"

        for key, btn, title_lbl, desc_lbl in self._type_buttons:
            if key == self._card_type:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {sel_bg};
                        border: 1.5px solid {sel_border};
                        border-radius: 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {card_bg};
                        border: 1px solid {card_border};
                        border-radius: 12px;
                    }}
                    QPushButton:hover {{
                        border-color: {hover_border};
                        background: {hover_bg};
                    }}
                """)

    def _go_to_content(self):
        """Navigate to content page with mode-appropriate text."""
        if self._mode == "topic":
            self.content_header.setText("Describe your topic")
            self.content_input.setPlaceholderText("cardiac stuff like heart failure, the different types, what symptoms to look for, and the main drugs they use to treat it")
        else:
            self.content_header.setText("Paste your notes")
            self.content_input.setPlaceholderText("Paste your lecture notes, class slides, or textbook sections here (must be text — images and file uploads won't work)")
        self.stack.setCurrentIndex(4)

    # ═══════════════════════════════════════════════════════════════
    # Page 4: Content Input
    # ═══════════════════════════════════════════════════════════════

    def _build_content_page(self, c):
        is_dark = ThemeManager.is_night_mode()
        input_bg = "#2a2a2e" if is_dark else "#eaeaee"
        input_border = "#3a3a3f" if is_dark else "#d0d0d5"

        page = QWidget()
        page.setStyleSheet("border: none;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._make_page_header(c, back_page=3))

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {c['border']};")
        layout.addWidget(line)

        content = QVBoxLayout()
        content.setContentsMargins(28, 16, 28, 0)
        content.setSpacing(14)

        self.content_header = QLabel("Describe your topic")
        self.content_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_header.setStyleSheet(f"color: {c['text']}; font-size: 18px; font-weight: 600; font-family: {_FONT};")
        content.addWidget(self.content_header)

        scrollbar_bg = c['background']
        scrollbar_handle = c['border']
        scrollbar_hover = c['text_secondary']

        self.content_input = QTextEdit()
        self.content_input.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.content_input.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_input.setPlaceholderText("cardiac stuff like heart failure, the different types, what symptoms to look for, and the main drugs they use to treat it")
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

        layout.addLayout(content, 1)

        bottom = QVBoxLayout()
        bottom.setContentsMargins(28, 8, 28, 20)
        gen_btn = self._make_primary_btn("Generate Cards", c)
        gen_btn.clicked.connect(self._on_generate)
        bottom.addWidget(gen_btn)
        layout.addLayout(bottom)

        self.stack.addWidget(page)

    def _on_generate(self):
        content = self.content_input.toPlainText().strip()
        if not content:
            tooltip("Please enter content.", period=2000)
            return

        if not _has_internet():
            tooltip("No internet connection. Check your connection and try again.", period=3000)
            return

        template = PROMPTS.get((self._mode, self._card_type), PROMPTS[("topic", "normal")])
        prompt = template.format(count=self._card_count, content=content)

        # Reset generating page state
        c = ThemeManager.get_palette()
        self.gen_loader.setHtml(ThemeManager.get_loading_html())
        self.gen_loader.show()
        self.gen_status.setText("Generating cards")
        self.gen_status.setStyleSheet(f"color: {c['text']}; font-size: 16px; font-weight: 600; font-family: {_FONT};")
        self.gen_sub.setText("Cards will appear as they're created")
        self.gen_sub.setStyleSheet(f"color: {c['text_secondary']}; font-size: 13px; font-family: {_FONT};")
        self.gen_retry_btn.hide()

        self.stack.setCurrentIndex(5)
        self._start_generation(prompt)

    # ═══════════════════════════════════════════════════════════════
    # Page 5: Generating (loading)
    # ═══════════════════════════════════════════════════════════════

    def _build_generating_page(self, c):
        page = QWidget()
        page.setStyleSheet("border: none;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar with X to cancel
        header_bar = QWidget()
        header_bar.setFixedHeight(38)
        hb_layout = QHBoxLayout(header_bar)
        hb_layout.setContentsMargins(12, 0, 12, 0)
        hb_layout.addStretch()

        close_btn = CloseButton(size=24)
        close_btn.clicked.connect(self.close)
        hb_layout.addWidget(close_btn)

        header_bar.mousePressEvent = self._title_mouse_press
        header_bar.mouseMoveEvent = self._title_mouse_move
        layout.addWidget(header_bar)

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {c['border']};")
        layout.addWidget(line)

        # Center everything vertically
        layout.addStretch()

        # Loader webview (same as OpenEvidence loading spinner)
        self.gen_loader = QWebEngineView()
        self.gen_loader.setFixedSize(250, 60)
        self.gen_loader.setStyleSheet("background: transparent; border: none;")
        loader_wrapper = QHBoxLayout()
        loader_wrapper.addStretch()
        loader_wrapper.addWidget(self.gen_loader)
        loader_wrapper.addStretch()
        layout.addLayout(loader_wrapper)

        self.gen_status = QLabel("Generating cards")
        self.gen_status.setStyleSheet(f"color: {c['text']}; font-size: 16px; font-weight: 600; font-family: {_FONT};")
        self.gen_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gen_status.setContentsMargins(28, 12, 28, 0)
        layout.addWidget(self.gen_status)

        self.gen_sub = QLabel("Cards will appear as they're created")
        self.gen_sub.setStyleSheet(f"color: {c['text_secondary']}; font-size: 13px; font-family: {_FONT};")
        self.gen_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gen_sub.setContentsMargins(28, 4, 28, 0)
        layout.addWidget(self.gen_sub)

        # Retry button (hidden by default)
        self.gen_retry_btn = self._make_primary_btn("Go Back", c)
        self.gen_retry_btn.clicked.connect(lambda: self.stack.setCurrentIndex(4))
        self.gen_retry_btn.hide()
        retry_wrapper = QHBoxLayout()
        retry_wrapper.setContentsMargins(28, 12, 28, 0)
        retry_wrapper.addWidget(self.gen_retry_btn)
        layout.addLayout(retry_wrapper)

        layout.addStretch()

        self.stack.addWidget(page)

    # ─── Auto-generation via hidden panel ────────────────────────

    def _start_generation(self, prompt):

        from .analytics import track_ai_generate
        track_ai_generate()

        # Arm the login modal safety gate — user is actively submitting a
        # real query to OE, so a NEEDS_LOGIN polling response is legitimate.
        from .ai_create import mark_user_query
        mark_user_query()

        pkg = _get_package()
        if not pkg:
            self._on_generation_error("Something went wrong. Try again, and if that doesn't work, try again later.")
            return

        dock_widget = getattr(pkg, 'dock_widget', None)
        if dock_widget is None:
            create_fn = getattr(pkg, 'create_dock_widget', None)
            if create_fn:
                create_fn()
            dock_widget = getattr(pkg, 'dock_widget', None)

        if not dock_widget:
            self._on_generation_error("Something went wrong. Try again, and if that doesn't work, try again later.")
            return

        # Always float panel off-screen invisibly — hide it first if the user
        # had it open so the generation isn't visible in their chat view.
        if dock_widget.isVisible():
            dock_widget.hide()
        dock_widget.setFloating(True)
        dock_widget.setWindowOpacity(0)
        dock_widget.move(-9999, -9999)
        dock_widget.show()

        panel = dock_widget.widget()
        if not panel or not hasattr(panel, 'web'):
            self._on_generation_error("Something went wrong. Try again, and if that doesn't work, try again later.")
            return

        if hasattr(panel, 'show_web_view'):
            panel.show_web_view()

        # Inject prompt into OpenEvidence search input (React-compatible)
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
                        console.log('Anki: AI Generate - submitted prompt');
                    } else {
                        searchInput.dispatchEvent(new KeyboardEvent('keydown', {
                            key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
                            bubbles: true, cancelable: true
                        }));
                    }
                }, 100);
            } else {
                console.log('Anki: AI Generate - could not find search input');
            }
        })();
        """ % repr(prompt)

        panel.web.page().runJavaScript(js_inject)

        # After submitting, inject JS that polls for the response in article elements
        poll_js = """
        (function() {
            window.ankiGenerateResult = null;
            window.ankiGeneratePartial = null;
            window.ankiGenerateError = null;
            var initialCount = document.querySelectorAll('article.MuiBox-root').length;
            var pollCount = 0;
            var maxPolls = 134;
            var lastTextLength = -1;
            var stableCount = 0;

            var pollInterval = setInterval(function() {
                pollCount++;
                if (pollCount > maxPolls) {
                    clearInterval(pollInterval);
                    window.ankiGenerateResult = 'ERROR_TIMEOUT';
                    return;
                }

                // Check for rate limit / login popup
                var dlg = document.querySelector('[role="dialog"]');
                if (dlg) {
                    var dlgText = dlg.innerText || '';
                    if (dlgText.indexOf('question limit') !== -1 || dlgText.indexOf('unverified users') !== -1 || dlgText.indexOf('Sign Up') !== -1) {
                        clearInterval(pollInterval);
                        window.ankiGenerateError = 'NEEDS_LOGIN';
                        return;
                    }
                }

                // Check for error banners/alerts on the page
                var errorBanner = document.querySelector('.MuiAlert-root, [role="alert"]:not([role="dialog"]), .MuiSnackbar-root');
                if (errorBanner) {
                    var errText = errorBanner.innerText || errorBanner.textContent || '';
                    if (errText.length > 5) {
                        window.ankiGenerateError = errText.trim();
                    }
                }

                var articles = document.querySelectorAll('article.MuiBox-root');
                if (articles.length <= initialCount) return;

                var lastArticle = articles[articles.length - 1];
                var text = lastArticle.innerText || lastArticle.textContent || '';
                if (text.length === 0) return;

                window.ankiGeneratePartial = text;

                if (text.length === lastTextLength) {
                    stableCount++;
                    if (stableCount >= 5) {
                        clearInterval(pollInterval);
                        window.ankiGenerateResult = text;
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
        pkg = _get_package()
        dock_widget = getattr(pkg, 'dock_widget', None) if pkg else None
        if not dock_widget:
            self._on_generation_error("Something went wrong. Try again, and if that doesn't work, try again later.")
            return

        panel = dock_widget.widget()
        if not panel or not hasattr(panel, 'web'):
            self._on_generation_error("Something went wrong. Try again, and if that doesn't work, try again later.")
            return

        self._py_poll_count = 0
        self._last_card_count = 0
        self._streamed_to_preview = False

        # Prepare preview page for streaming
        self._clear_preview()

        def check_result():
            self._py_poll_count += 1
            if self._py_poll_count > 80:  # ~40 seconds
                if self._poll_timer:
                    self._poll_timer.stop()
                self._cleanup_panel()
                if not self._parsed_cards:
                    if not _has_internet():
                        self._on_generation_error("No internet connection. Check your connection and try again.")
                    else:
                        self._on_generation_error("Something went wrong. Try again, and if that doesn't work, try again later.")
                else:
                    # We got some cards, finalize
                    self._finalize_preview()
                return

            panel.web.page().runJavaScript(
                "[window.ankiGeneratePartial, window.ankiGenerateResult, window.ankiGenerateError]",
                on_poll_result
            )

        def on_poll_result(result):
            if not result or not isinstance(result, list):
                return
            partial = result[0] if len(result) > 0 else None
            final = result[1] if len(result) > 1 else None
            error = result[2] if len(result) > 2 else None

            # If OpenEvidence shows an error banner, surface it
            if error and isinstance(error, str) and not self._parsed_cards:
                if self._poll_timer:
                    self._poll_timer.stop()
                self._cleanup_panel()
                if error == 'NEEDS_LOGIN':
                    self.close()
                    from .ai_create import show_login_modal
                    QTimer.singleShot(300, show_login_modal)
                elif 'outside the scope' in error.lower() or 'not within' in error.lower() or 'not medical' in error.lower():
                    # Close the wizard first, then show the out-of-scope modal on mw
                    self.close()
                    from .ai_create import show_out_of_scope_modal
                    QTimer.singleShot(300, lambda: show_out_of_scope_modal(parent=mw))
                else:
                    self._on_generation_error(error)
                return

            # Stream partial cards as they arrive
            text_to_parse = final if (final and isinstance(final, str) and final not in ('ERROR_TIMEOUT',)) else partial
            if text_to_parse and isinstance(text_to_parse, str):
                cards = parse_cards(text_to_parse)
                if len(cards) > self._last_card_count:
                    # New cards found — add them to preview
                    new_cards = cards[self._last_card_count:]
                    self._last_card_count = len(cards)
                    self._parsed_cards = cards
                    self._stream_cards(new_cards)

            if final and isinstance(final, str):
                if self._poll_timer:
                    self._poll_timer.stop()
                self._cleanup_panel()

                if final == 'ERROR_TIMEOUT':
                    if not self._parsed_cards:
                        self._on_generation_error("Something went wrong. Try again, and if that doesn't work, try again later.")
                    else:
                        self._finalize_preview()
                    return

                # Final parse
                cards = parse_cards(final)
                if not cards:
                    if not self._parsed_cards:
                        self._on_generation_error(f"Couldn't parse cards. Got {len(final)} chars but no <card> tags found.")
                    return

                # Add any remaining cards
                if len(cards) > self._last_card_count:
                    new_cards = cards[self._last_card_count:]
                    self._parsed_cards = cards
                    self._stream_cards(new_cards)

                self._finalize_preview()

        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(check_result)
        self._poll_timer.start(500)

    def _cleanup_panel(self):
        pkg = _get_package()
        dock_widget = getattr(pkg, 'dock_widget', None) if pkg else None
        if dock_widget:
            panel = dock_widget.widget()
            if panel and hasattr(panel, 'web'):
                from .ai_create import _delete_latest_oe_conversation
                _delete_latest_oe_conversation(panel)
            dock_widget.hide()
            dock_widget.setWindowOpacity(1)
            dock_widget.setFloating(False)
            mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)

    def _on_generation_error(self, message):
        c = ThemeManager.get_palette()
        self.gen_loader.hide()
        self.gen_status.setText("Generation failed")
        self.gen_status.setStyleSheet(f"color: {c['danger']}; font-size: 16px; font-weight: 600; font-family: {_FONT};")
        self.gen_sub.setText(message)
        self.gen_retry_btn.show()

    # ═══════════════════════════════════════════════════════════════
    # Page 6: Preview
    # ═══════════════════════════════════════════════════════════════

    def _build_preview_page(self, c):
        is_dark = ThemeManager.is_night_mode()
        scrollbar_bg = c['background']
        scrollbar_handle = c['border']
        scrollbar_hover = c['text_secondary']

        page = QWidget()
        page.setStyleSheet("border: none;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header_bar = QWidget()
        header_bar.setFixedHeight(38)
        hb_layout = QHBoxLayout(header_bar)
        hb_layout.setContentsMargins(12, 0, 12, 0)
        hb_layout.addStretch()

        self.select_all_cb = QCheckBox("Select All")
        self.select_all_cb.setChecked(True)
        self.select_all_cb.setStyleSheet(f"color: {c['text_secondary']}; font-size: 12px; font-family: {_FONT};")
        self.select_all_cb.toggled.connect(self._toggle_select_all)
        hb_layout.addWidget(self.select_all_cb)

        close_btn = CloseButton(size=24)
        close_btn.clicked.connect(self.close)
        hb_layout.addWidget(close_btn)
        header_bar.mousePressEvent = self._title_mouse_press
        header_bar.mouseMoveEvent = self._title_mouse_move
        layout.addWidget(header_bar)

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {c['border']};")
        layout.addWidget(line)

        # Content
        content = QVBoxLayout()
        content.setContentsMargins(28, 12, 28, 0)
        content.setSpacing(10)

        self.preview_header = QLabel("Generating cards...")
        self.preview_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_header.setStyleSheet(f"color: {c['text']}; font-size: 16px; font-weight: 600; font-family: {_FONT};")
        content.addWidget(self.preview_header)

        # Card list with custom scrollbar
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setStyleSheet(f"""
            QScrollArea {{ background: {c['background']}; border: none; }}
            QScrollBar:vertical {{
                background: {scrollbar_bg}; width: 8px; margin: 2px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {scrollbar_handle}; min-height: 30px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {scrollbar_hover}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet(f"background: {c['background']};")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.preview_scroll.setWidget(self.cards_container)
        content.addWidget(self.preview_scroll, 1)

        layout.addLayout(content, 1)

        # Bottom button
        bottom = QVBoxLayout()
        bottom.setContentsMargins(28, 8, 28, 20)
        self.create_btn = self._make_primary_btn("Create Cards", c)
        self.create_btn.clicked.connect(self._on_create)
        bottom.addWidget(self.create_btn)
        layout.addLayout(bottom)

        self.stack.addWidget(page)

    def _clear_preview(self):
        """Clear the preview page for fresh streaming."""
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._card_checkboxes = []
        self._parsed_cards = []
        self.preview_header.setText("Generating cards...")
        self._update_create_btn_text()

    def _stream_cards(self, new_cards):
        """Add newly parsed cards to the preview page in real-time."""
        c = ThemeManager.get_palette()

        # Switch to preview page on first card
        if not self._streamed_to_preview:
            self._streamed_to_preview = True
            self.stack.setCurrentIndex(6)

        # Save scroll position before adding widgets
        scrollbar = self.preview_scroll.verticalScrollBar()
        old_pos = scrollbar.value()

        for front, back in new_cards:
            num = len(self._card_checkboxes) + 1
            self.cards_layout.addWidget(self._make_card_preview(num, front, back, c))

        # Restore scroll position so it doesn't jump
        QTimer.singleShot(0, lambda: scrollbar.setValue(old_pos))

        self.preview_header.setText(f"{len(self._card_checkboxes)} cards \u2192 {self._deck_name}")
        self._update_create_btn_text()


    def _finalize_preview(self):
        """Called when generation is complete."""
        self.preview_header.setText(f"{len(self._parsed_cards)} cards \u2192 {self._deck_name}")
        self.select_all_cb.setChecked(True)
        self._update_create_btn_text()

    def _show_preview(self, cards):
        """Legacy — show all cards at once (fallback)."""
        self._clear_preview()
        self._parsed_cards = cards
        c = ThemeManager.get_palette()
        for i, (front, back) in enumerate(cards):
            self.cards_layout.addWidget(self._make_card_preview(i + 1, front, back, c))
        self.preview_header.setText(f"{len(cards)} cards \u2192 {self._deck_name}")
        self.select_all_cb.setChecked(True)
        self._update_create_btn_text()
        self.stack.setCurrentIndex(6)

    def _make_card_preview(self, num, front, back, c):
        is_dark = ThemeManager.is_night_mode()
        card_bg = "#2a2a2e" if is_dark else "#eaeaee"
        card_border = "#3a3a3f" if is_dark else "#d0d0d5"
        sel_border = c['accent']
        sel_bg = "rgba(59, 130, 246, 0.12)" if is_dark else "rgba(59, 130, 246, 0.08)"

        card = QWidget()

        # Use object name to scope styles and avoid child bleed
        card.setObjectName(f"cardPreview{num}")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(4)

        # Top row: small checkbox + card number
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        cb = CheckmarkWidget(
            checked=True,
            check_color=sel_border,
            border_color=card_border,
            bg_color=card_bg,
        )
        cb.toggled_connect(lambda checked, w=card, n=num: self._update_card_style(w, n, checked))
        cb.toggled_connect(lambda checked: self._update_create_btn_text())
        self._card_checkboxes.append(cb)
        top_row.addWidget(cb)

        num_label = QLabel(f"Card {num}")
        num_label.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px; font-family: {_FONT}; background: transparent; border: none;")
        top_row.addWidget(num_label)
        top_row.addStretch()
        layout.addLayout(top_row)

        front_label = QLabel(f"Q: {front}")
        front_label.setStyleSheet(f"color: {c['text']}; font-size: 12px; font-weight: 600; background: transparent; border: none; font-family: {_FONT};")
        front_label.setWordWrap(True)
        layout.addWidget(front_label)

        back_label = QLabel(f"A: {back}")
        back_label.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px; background: transparent; border: none; font-family: {_FONT};")
        back_label.setWordWrap(True)
        layout.addWidget(back_label)

        # Default: selected style
        card.setStyleSheet(f"QWidget#{card.objectName()} {{ background: {sel_bg}; border: 1.5px solid {sel_border}; border-radius: 10px; }}")
        # Store style info for toggling
        card.setProperty("card_bg", card_bg)
        card.setProperty("card_border", card_border)
        card.setProperty("sel_bg", sel_bg)
        card.setProperty("sel_border", sel_border)

        return card

    def _update_card_style(self, card, num, checked):
        """Toggle card border style based on checkbox state."""
        obj = card.objectName()
        if checked:
            sel_bg = card.property("sel_bg")
            sel_border = card.property("sel_border")
            card.setStyleSheet(f"QWidget#{obj} {{ background: {sel_bg}; border: 1.5px solid {sel_border}; border-radius: 10px; }}")
        else:
            card_bg = card.property("card_bg")
            card_border = card.property("card_border")
            card.setStyleSheet(f"QWidget#{obj} {{ background: {card_bg}; border: 1px solid {card_border}; border-radius: 10px; }}")

    def _toggle_select_all(self, checked):
        for cb in self._card_checkboxes:
            cb.setChecked(checked)

    def _update_create_btn_text(self):
        selected = sum(1 for cb in self._card_checkboxes if cb.isChecked())
        self.create_btn.setText(f"Create {selected} Cards")
        self.create_btn.setEnabled(selected > 0)

    def _on_create(self):
        if not self._deck_name:
            tooltip("No deck selected.", period=2000)
            return

        selected_cards = []
        for i, cb in enumerate(self._card_checkboxes):
            if cb.isChecked() and i < len(self._parsed_cards):
                selected_cards.append(self._parsed_cards[i])

        if not selected_cards:
            tooltip("No cards selected.", period=2000)
            return

        count = create_cards_in_deck(selected_cards, self._deck_name)

        from .analytics import track_ai_generate_cards_created
        track_ai_generate_cards_created(count)

        tooltip(f"Created {count} cards in '{self._deck_name}'!", period=3000)
        self.close()

    # ─── Shared Helpers ──────────────────────────────────────────

    def _make_page_header(self, c, back_page):
        """Create a standard page header bar with back arrow + X button."""
        header_bar = QWidget()
        header_bar.setFixedHeight(38)
        hb_layout = QHBoxLayout(header_bar)
        hb_layout.setContentsMargins(12, 0, 12, 0)

        back_btn = QPushButton("\u2190")
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.setFixedSize(24, 24)
        back_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {c['text_secondary']}; border: none; border-radius: 6px; font-size: 18px; }}
            QPushButton:hover {{ background: {c['hover']}; color: {c['text']}; }}
        """)
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(back_page))
        hb_layout.addWidget(back_btn)
        hb_layout.addStretch()

        close_btn = CloseButton(size=24)
        close_btn.clicked.connect(self.close)
        hb_layout.addWidget(close_btn)
        header_bar.mousePressEvent = self._title_mouse_press
        header_bar.mouseMoveEvent = self._title_mouse_move
        return header_bar

    def _make_back_btn(self, c, on_click):
        btn = QPushButton("\u2190 Back")
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setFixedWidth(60)
        btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {c['accent']}; border: none; font-size: 13px; font-weight: 600; padding: 4px 0; }}
            QPushButton:hover {{ color: {c['accent_hover']}; }}
        """)
        btn.clicked.connect(on_click)
        return btn

    def _make_primary_btn(self, text, c):
        btn = QPushButton(text)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setFixedHeight(44)
        btn.setStyleSheet(f"""
            QPushButton {{ background: {c['accent']}; color: #ffffff; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; }}
            QPushButton:hover {{ background: {c['accent_hover']}; }}
        """)
        return btn

    def closeEvent(self, event):
        """Clean up timers and overlay on close."""
        if self._poll_timer:
            self._poll_timer.stop()
        if self._dot_timer:
            self._dot_timer.stop()
        if self._overlay:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None
        super().closeEvent(event)


# ─── Public API ──────────────────────────────────────────────────────

def show_ai_generate_dialog():
    """Show the AI Generate wizard window with dark overlay."""
    from .review import show_review_modal_if_eligible
    if show_review_modal_if_eligible():
        return  # Review modal shown instead — user can retry after dismissing

    # Create overlay on Anki's central widget
    overlay = ModalOverlay(mw)
    overlay.show()
    overlay.raise_()

    window = AIGenerateWindow(mw)
    window._overlay = overlay
    window.show()
    window.raise_()

    # Prevent GC
    mw._ai_generate_overlay = overlay
    mw._ai_generate_window = window
