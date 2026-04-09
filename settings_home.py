"""
Settings Home View - Main hub for all settings categories.
"""

import webbrowser

try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame
    from PyQt6.QtCore import Qt, QByteArray, QSize
    from PyQt6.QtGui import QPixmap, QPainter, QCursor
    from PyQt6.QtSvg import QSvgRenderer
except ImportError:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame
    from PyQt5.QtCore import Qt, QByteArray, QSize
    from PyQt5.QtGui import QPixmap, QPainter, QCursor
    from PyQt5.QtSvg import QSvgRenderer

from .theme_manager import ThemeManager


REVIEW_URL = "https://ankiweb.net/shared/review/1314683963"
FEATURE_REQUEST_URL = "https://github.com/Lukeyp43/OpenEvidence-AI/issues/new?labels=feature%20request"
BUG_REPORT_URL = "https://github.com/Lukeyp43/OpenEvidence-AI/issues/new?labels=bug"


class SettingsHomeView(QWidget):
    """Settings Home - Main hub for all settings categories"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.setup_ui()

    def setup_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Get common palette
        c = ThemeManager.get_palette()
        icon_color = c['icon_color']

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(ThemeManager.get_scroll_area_style())

        content = QWidget()
        content.setStyleSheet(f"background: {c['background']};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)

        # Header
        header = QLabel("Settings")
        header.setStyleSheet(f"""
            color: {c['text']};
            font-size: 24px;
            font-weight: 700;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        """)
        content_layout.addWidget(header)

        # Navigation Cards Container
        cards_container = QWidget()
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)

        # Card 1: Quick Actions
        quick_actions_card = self.create_nav_card(
            title="Quick Actions",
            icon_svg=f"""<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M13 24L17 14L24 4L31 14L35 24L31 34L24 44L17 34L13 24Z" stroke="{icon_color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                <circle cx="24" cy="24" r="4" stroke="{icon_color}" stroke-width="3"/>
            </svg>""",
            on_click=self.open_quick_actions
        )
        cards_layout.addWidget(quick_actions_card)

        # Card 2: Replay Tutorial
        replay_tutorial_card = self.create_nav_card(
            title="Replay Tutorial",
            icon_svg=f"""<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="24" cy="24" r="19" stroke="{icon_color}" stroke-width="3"/>
                <path d="M20 16L32 24L20 32V16Z" stroke="{icon_color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>""",
            on_click=self.replay_tutorial
        )
        cards_layout.addWidget(replay_tutorial_card)

        # Card 3: Leave a Review
        leave_review_card = self.create_nav_card(
            title="Leave a Review",
            icon_svg=f"""<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M24 5L29.5 16.5L42 18.5L33 27.5L35.5 40L24 34L12.5 40L15 27.5L6 18.5L18.5 16.5L24 5Z" stroke="{icon_color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>""",
            on_click=self.leave_review
        )
        cards_layout.addWidget(leave_review_card)

        content_layout.addWidget(cards_container)
        content_layout.addStretch()

        # Footer section - stacked layout
        footer_wrapper = QWidget()
        footer_wrapper.setStyleSheet("background: transparent;")
        footer_wrapper_layout = QVBoxLayout(footer_wrapper)
        footer_wrapper_layout.setContentsMargins(0, 24, 0, 15)
        footer_wrapper_layout.setSpacing(12)

        # Row 1: Request Feature | Report Bug (centered together)
        feedback_row = QWidget()
        feedback_row.setStyleSheet("background: transparent;")
        feedback_row_layout = QHBoxLayout(feedback_row)
        feedback_row_layout.setContentsMargins(0, 0, 0, 0)
        feedback_row_layout.setSpacing(0)
        feedback_row_layout.addStretch()

        # Request Feature Button
        request_btn = self.create_footer_link(
            text="Request a Feature",
            icon_svg=f"""<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="{c['text_secondary']}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/>
                <path d="M9 18h6"/>
                <path d="M10 22h4"/>
            </svg>""",
            on_click=self.request_feature
        )
        feedback_row_layout.addWidget(request_btn)

        # Separator
        separator_container = QWidget()
        separator_layout = QHBoxLayout(separator_container)
        separator_layout.setContentsMargins(16, 0, 16, 0)

        separator = QLabel()
        separator.setFixedSize(1, 12)
        separator.setStyleSheet(f"background: {c['border']};")
        separator_layout.addWidget(separator)

        feedback_row_layout.addWidget(separator_container)

        # Report Bug Button
        bug_btn = self.create_footer_link(
            text="Report a Bug",
            icon_svg=f"""<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="{c['text_secondary']}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="m8 2 1.88 1.88"/>
                <path d="M14.12 3.88 16 2"/>
                <path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/>
                <path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"/>
                <path d="M12 20v-9"/>
                <path d="M6.53 9C4.6 8.8 3 7.1 3 5"/>
                <path d="M6 13H2"/>
                <path d="M3 21c0-2.1 1.7-3.9 3.8-4"/>
                <path d="M20.97 5c0 2.1-1.6 3.8-3.5 4"/>
                <path d="M22 13h-4"/>
                <path d="M17.2 17c2.1.1 3.8 1.9 3.8 4"/>
            </svg>""",
            on_click=self.report_bug
        )
        feedback_row_layout.addWidget(bug_btn)

        feedback_row_layout.addStretch()
        footer_wrapper_layout.addWidget(feedback_row)

        content_layout.addWidget(footer_wrapper)

        # Set the scrollable content
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def create_nav_card(self, title, icon_svg, on_click):
        """Create a navigation card with icon, title, description"""
        card = QPushButton()
        card.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        card.setFixedHeight(80)
        card.clicked.connect(on_click)

        # Card layout
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(16)

        # Icon
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        icon_label.setStyleSheet("background: transparent; border: none;")

        # Render SVG
        svg_bytes = QByteArray(icon_svg.encode())
        renderer = QSvgRenderer(svg_bytes)
        pixmap = QPixmap(48, 48)
        try:
            pixmap.fill(Qt.GlobalColor.transparent)
        except:
            pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        icon_label.setPixmap(pixmap)
        icon_label.setScaledContents(True)
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(icon_label)

        c = ThemeManager.get_palette()

        # Title only (no description)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {c['text']};
            font-size: 15px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(title_label, 1)

        # Arrow icon
        arrow_label = QLabel("→")
        arrow_label.setStyleSheet(f"""
            color: {c['text_secondary']};
            font-size: 20px;
            background: transparent;
            border: none;
        """)
        arrow_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(arrow_label)

        # Card styling
        card.setStyleSheet(f"""
            QPushButton {{
                background: {c['surface']};
                border: 1px solid {c['border']};
                border-radius: 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {c['border']};
                border-color: {c['accent']};
            }}
        """)

        return card

    def create_footer_link(self, text, icon_svg, on_click):
        """Creates a clickable text+icon link using QFrame instead of QPushButton"""
        # Use QFrame as the container (stable layout behavior)
        container = QFrame()
        container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Set styling to mimic a hoverable button
        c = ThemeManager.get_palette()

        # Set styling to mimic a hoverable button
        # Using a subtle background change and text color change on hover
        container.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border-radius: 6px;
            }}
            QFrame QLabel {{
                color: {c['text_secondary']};
            }}
            QFrame:hover {{
                background: {c['hover']};
            }}
            QFrame:hover QLabel {{
                color: {c['text']};
            }}
        """)

        # Layout for the container
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Render SVG Icon at high resolution for crisp display
        icon_label = QLabel()
        icon_label.setFixedSize(14, 14)
        icon_label.setStyleSheet("background: transparent; border: none;")

        # Render at 4x resolution (56x56) for better quality when scaled down
        svg_bytes = QByteArray(icon_svg.encode())
        renderer = QSvgRenderer(svg_bytes)
        pixmap = QPixmap(56, 56)  # High resolution
        try:
            pixmap.fill(Qt.GlobalColor.transparent)
        except AttributeError:
            pixmap.fill(Qt.transparent)  # PyQt5 fallback

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        # Scale down smoothly to 14x14
        icon_label.setPixmap(pixmap)
        icon_label.setScaledContents(True)  # Enable smooth scaling
        layout.addWidget(icon_label)

        # Text Label
        text_label = QLabel(text)
        text_label.setStyleSheet("background: transparent; border: none; font-size: 13px;")
        layout.addWidget(text_label)

        # Make the QFrame clickable by overriding mouseReleaseEvent
        def mouse_release_handler(event):
            try:
                if event.button() == Qt.MouseButton.LeftButton:
                    on_click()
            except AttributeError:
                # PyQt5 fallback
                if event.button() == Qt.LeftButton:
                    on_click()

        # Assign the custom click handler to this specific instance
        container.mouseReleaseEvent = mouse_release_handler

        return container

    def open_quick_actions(self):
        """Navigate to Quick Actions view"""
        if self.parent_panel and hasattr(self.parent_panel, 'show_quick_actions_view'):
            self.parent_panel.show_quick_actions_view()

    def replay_tutorial(self):
        """Re-show the onboarding dialog (3-slide tutorial)."""
        try:
            from aqt import mw
            from .panel import OnboardingDialog
            dialog = OnboardingDialog(mw)
            dialog.show_animated()
            mw._onboarding_dialog = dialog  # prevent GC
        except Exception as e:
            print(f"[the_ai_panel] Failed to replay tutorial: {e}")

    def leave_review(self):
        """Open AnkiWeb review page"""
        webbrowser.open(REVIEW_URL)

    def request_feature(self):
        """Open feature request URL"""
        webbrowser.open(FEATURE_REQUEST_URL)

    def report_bug(self):
        """Open bug report URL"""
        webbrowser.open(BUG_REPORT_URL)
