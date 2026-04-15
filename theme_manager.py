"""
Theme Manager - Centralized handling of UI colors and styles for Light/Dark mode.
"""

from aqt import mw
from aqt.qt import QColor

try:
    from PyQt6.QtWidgets import QPushButton
    from PyQt6.QtGui import QPainter, QPen, QCursor
    from PyQt6.QtCore import Qt, QPointF
except ImportError:
    from PyQt5.QtWidgets import QPushButton
    from PyQt5.QtGui import QPainter, QPen, QCursor
    from PyQt5.QtCore import Qt, QPointF


class CloseButton(QPushButton):
    """Close button that paints its X with QPainter so it renders identically
    on every platform. The text-based approach (QPushButton("×")) depends on
    the default Qt font actually rendering U+00D7 at a small size — on Windows
    the stroke collapses into nothing in a 24px button, leaving the button
    visibly empty. Drawing two lines directly avoids the font entirely."""

    def __init__(self, parent=None, size=24, color=None, hover_color=None, hover_bg=None):
        super().__init__(parent)
        self.setText("")
        self.setFixedSize(size, size)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        palette = ThemeManager.get_palette()
        self._color = QColor(color or palette['text_secondary'])
        self._hover_color = QColor(hover_color or palette['text'])

        # NOTE: palette['hover'] is a CSS rgba(...) string that QColor cannot
        # parse — passing it to QColor() silently produces OPAQUE black, which
        # covers the whole button on hover. Build the hover fill from explicit
        # integer RGBA so it stays subtly translucent on both themes.
        if hover_bg is not None:
            self._hover_bg = QColor(hover_bg) if isinstance(hover_bg, str) else hover_bg
        elif ThemeManager.is_night_mode():
            self._hover_bg = QColor(255, 255, 255, 31)  # ~12% white
        else:
            self._hover_bg = QColor(0, 0, 0, 20)        # ~8% black

        self._hover = False

        radius = max(4, size // 4)
        self.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; border-radius: {radius}px; }}"
        )

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Hover background fill
        if self._hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._hover_bg)
            radius = max(4, self.width() // 4)
            p.drawRoundedRect(0, 0, self.width(), self.height(), radius, radius)

        # Two diagonal lines forming the X
        stroke_color = self._hover_color if self._hover else self._color
        pen = QPen(stroke_color)
        pen.setWidthF(max(1.4, self.width() / 16))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)

        w = self.width()
        h = self.height()
        # Inset the X by ~32% of the width so it sits nicely inside the button
        inset = w * 0.32
        p.drawLine(QPointF(inset, inset), QPointF(w - inset, h - inset))
        p.drawLine(QPointF(w - inset, inset), QPointF(inset, h - inset))
        p.end()


class ThemeManager:
    """Manages colors and styles based on Anki's night mode setting."""
    
    @staticmethod
    def is_night_mode():
        """Check if Anki is currently showing night mode.

        Prefer aqt.theme.theme_manager.night_mode — it reflects the *current*
        effective theme including "follow system" mode. Falls back to the
        stored preference for older Anki versions that don't have theme_manager.
        """
        try:
            from aqt.theme import theme_manager
            return theme_manager.night_mode
        except Exception:
            pass
        if hasattr(mw, "pm"):
            try:
                return mw.pm.night_mode()
            except Exception:
                pass
        return False

    @classmethod
    def get_palette(cls):
        """Get the color palette for current mode."""
        return cls.DARK_PALETTE if cls.is_night_mode() else cls.LIGHT_PALETTE

    # Dark Mode Palette (Current behavior)
    DARK_PALETTE = {
        "background": "#1e1e1e",
        "surface": "#2c2c2c", 
        "text": "#ffffff",
        "text_secondary": "#d1d5db", # gray-300
        "border": "#374151", # gray-700
        "border_subtle": "rgba(255, 255, 255, 0.06)",
        "hover": "rgba(255, 255, 255, 0.12)",
        "accent": "#3b82f6", # blue-500
        "accent_hover": "#2563eb", # blue-600
        "danger": "#ef4444", # red-500
        "danger_hover": "rgba(239, 68, 68, 0.2)",
        "scroll_bg": "#1e1e1e",
        "icon_color": "white",
        "shadow": "rgba(0, 0, 0, 0.3)"
    }

    # Light Mode Palette (New)
    LIGHT_PALETTE = {
        "background": "#ffffff",
        "surface": "#f3f4f6", # gray-100
        "text": "#111827", # gray-900
        "text_secondary": "#6b7280", # gray-500
        "border": "#e5e7eb", # gray-200
        "border_subtle": "rgba(0, 0, 0, 0.06)",
        "hover": "rgba(0, 0, 0, 0.05)",
        "accent": "#3b82f6", # blue-500 (keep same accent usually)
        "accent_hover": "#2563eb",
        "danger": "#ef4444",
        "danger_hover": "rgba(239, 68, 68, 0.1)",
        "scroll_bg": "#ffffff",
        "icon_color": "#374151", # gray-700
        "shadow": "rgba(0, 0, 0, 0.1)"
    }

    @classmethod
    def get_color(cls, key):
        """Get a specific color by key."""
        return cls.get_palette().get(key, "#ff00ff") # Magenta default if missing

    @classmethod
    def get_qcolor(cls, key):
        """Get a QColor object for a specific key."""
        return QColor(cls.get_color(key))

    # --- Stylesheet Generators ---

    @classmethod
    def get_scroll_area_style(cls):
        c = cls.get_palette()
        return f"QScrollArea {{ background: {c['scroll_bg']}; border: none; }}"

    @classmethod
    def get_panel_style(cls):
        c = cls.get_palette()
        return f"background: {c['background']};"
        
    @classmethod
    def get_button_style(cls, variant="primary"):
        c = cls.get_palette()
        if variant == "primary":
            # Just a standard button in list
            return f"""
                QPushButton {{
                    background: {c['surface']};
                    color: {c['text']};
                    border: 1px solid {c['border']};
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {c['border']}; 
                    border-color: {c['text_secondary']};
                }}
            """
        elif variant == "transparent":
            return f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background: {c['hover']};
                }}
            """
        return ""

    @classmethod
    def get_card_style(cls):
        c = cls.get_palette()
        return f"""
            QWidget {{
                background: {c['surface']};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
        """

    @classmethod
    def get_keycap_style(cls):
        c = cls.get_palette()
        is_dark = cls.is_night_mode()
        # For light mode, keycaps should be darker than surface but not too dark
        bg = "#374151" if is_dark else "#e5e7eb"
        border = "#4b5563" if is_dark else "#d1d5db"
        text = "#ffffff" if is_dark else "#374151"
        
        return f"""
            QLabel {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 4px 8px;
                color: {text};
                font-size: 12px;
                font-weight: 500;
            }}
        """

    @classmethod
    def get_bottom_section_style(cls):
        c = cls.get_palette()
        return f"background: {c['background']}; border-top: 1px solid {c['border_subtle']};"
    
    @classmethod
    def get_loading_html(cls):
        """Get the HTML for the loading spinner with correct colors."""
        c = cls.get_palette()
        bg = c['background']
        dot_color = c['text'] # Use text color for dots so they are visible on white
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background: {bg};
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    overflow: hidden;
                }}
                .loader {{
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    display: block;
                    position: relative;
                    color: {dot_color};
                    left: -100px;
                    box-sizing: border-box;
                    animation: shadowRolling 2s linear infinite;
                }}
                @keyframes shadowRolling {{
                    0% {{
                        box-shadow: 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0);
                    }}
                    12% {{
                        box-shadow: 100px 0 {dot_color}, 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0);
                    }}
                    25% {{
                        box-shadow: 110px 0 {dot_color}, 100px 0 {dot_color}, 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0);
                    }}
                    36% {{
                        box-shadow: 120px 0 {dot_color}, 110px 0 {dot_color}, 100px 0 {dot_color}, 0px 0 rgba(255, 255, 255, 0);
                    }}
                    50% {{
                        box-shadow: 130px 0 {dot_color}, 120px 0 {dot_color}, 110px 0 {dot_color}, 100px 0 {dot_color};
                    }}
                    62% {{
                        box-shadow: 200px 0 rgba(255, 255, 255, 0), 130px 0 {dot_color}, 120px 0 {dot_color}, 110px 0 {dot_color};
                    }}
                    75% {{
                        box-shadow: 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0), 130px 0 {dot_color}, 120px 0 {dot_color};
                    }}
                    87% {{
                        box-shadow: 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0), 130px 0 {dot_color};
                    }}
                    100% {{
                        box-shadow: 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0);
                    }}
                }}
            </style>
        </head>
        <body>
            <span class="loader"></span>
        </body>
        </html>
        """

    @classmethod
    def get_css_variables(cls):
        """Get CSS variables block for current theme."""
        c = cls.get_palette()
        return f"""
        <style>
            :root {{
                --oa-background: {c['background']};
                --oa-surface: {c['surface']};
                --oa-text: {c['text']};
                --oa-text-secondary: {c['text_secondary']};
                --oa-border: {c['border']};
                --oa-accent: {c['accent']};
                --oa-accent-hover: {c['accent_hover']};
                --oa-shadow: {c['shadow']};
                --oa-hover: {c['hover']};
            }}
        </style>
        """
