"""
Quick Actions Settings View - Toggle switches for reviewer features
like the inline Explain bubble.
"""

from aqt import mw

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame
    )
    from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF
    from PyQt6.QtGui import QCursor, QPainter, QColor, QBrush, QPen
except ImportError:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame
    )
    from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF
    from PyQt5.QtGui import QCursor, QPainter, QColor, QBrush, QPen

from .theme_manager import ThemeManager
from .utils import ADDON_NAME


class ToggleSwitch(QWidget):
    """Animated iOS-style toggle switch. Emits toggled state on click."""

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._offset = 1.0 if checked else 0.0
        self._on_toggled = None

        self.setFixedSize(46, 26)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._anim = QPropertyAnimation(self, b"offset")
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked == checked:
            return
        self._checked = checked
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def connect(self, callback):
        """Set a callback that fires when the user toggles the switch."""
        self._on_toggled = callback

    def mousePressEvent(self, event):
        self.setChecked(not self._checked)
        if self._on_toggled:
            self._on_toggled(self._checked)
        super().mousePressEvent(event)

    # Animated offset property (0.0 = off, 1.0 = on)
    def _get_offset(self):
        return self._offset

    def _set_offset(self, value):
        self._offset = value
        self.update()

    offset = pyqtProperty(float, _get_offset, _set_offset)

    def paintEvent(self, event):
        c = ThemeManager.get_palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track background — interpolate between surface and accent
        off_color = QColor(c['border'])
        on_color = QColor(c['accent'])
        r = off_color.red() + (on_color.red() - off_color.red()) * self._offset
        g = off_color.green() + (on_color.green() - off_color.green()) * self._offset
        b = off_color.blue() + (on_color.blue() - off_color.blue()) * self._offset
        track_color = QColor(int(r), int(g), int(b))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(track_color))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 13, 13)

        # Knob
        knob_size = 20
        knob_y = (self.height() - knob_size) / 2
        knob_x_off = 3
        knob_x_on = self.width() - knob_size - 3
        knob_x = knob_x_off + (knob_x_on - knob_x_off) * self._offset

        p.setBrush(QBrush(QColor(255, 255, 255)))
        p.drawEllipse(QRectF(knob_x, knob_y, knob_size, knob_size))
        p.end()


class QuickActionsSettingsView(QWidget):
    """Settings view with toggle switches for reviewer features."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.setup_ui()

    def setup_ui(self):
        c = ThemeManager.get_palette()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(ThemeManager.get_scroll_area_style())

        content = QWidget()
        content.setStyleSheet(f"background: {c['background']};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(20)

        # Header
        header = QLabel("Quick Actions")
        header.setStyleSheet(f"""
            color: {c['text']};
            font-size: 24px;
            font-weight: 700;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        """)
        content_layout.addWidget(header)

        subtitle = QLabel("Control which features appear when reviewing cards.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"""
            color: {c['text_secondary']};
            font-size: 13px;
        """)
        content_layout.addWidget(subtitle)

        content_layout.addSpacing(4)

        # Explain toggle row
        explain_enabled = self._get_config_value("explain_enabled", True)
        explain_row = self._create_toggle_row(
            title="AI Explain",
            description="Show the Explain bubble when you highlight text on a flashcard.",
            checked=explain_enabled,
            on_change=self._on_explain_toggled,
            c=c,
        )
        content_layout.addWidget(explain_row)

        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _create_toggle_row(self, title, description, checked, on_change, c):
        """Create a row with a title, description, and toggle switch."""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: {c['surface']};
                border: 1px solid {c['border']};
                border-radius: 12px;
            }}
        """)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(20, 16, 20, 16)
        row_layout.setSpacing(16)

        # Left: text block
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {c['text']};
            font-size: 15px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        text_col.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"""
            color: {c['text_secondary']};
            font-size: 12px;
            background: transparent;
            border: none;
        """)
        text_col.addWidget(desc_label)

        row_layout.addLayout(text_col, 1)

        # Right: toggle
        toggle = ToggleSwitch(checked=checked)
        toggle.connect(on_change)
        row_layout.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)

        return row

    def _get_config_value(self, key, default):
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        return config.get(key, default)

    def _set_config_value(self, key, value):
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        config[key] = value
        mw.addonManager.writeConfig(ADDON_NAME, config)

    def _on_explain_toggled(self, checked):
        self._set_config_value("explain_enabled", checked)
