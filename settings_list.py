"""
Settings List View - List of keybindings with edit/delete functionality.
"""

import sys
from aqt import mw
from aqt.utils import tooltip

try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
    from PyQt6.QtCore import Qt, QTimer, QByteArray, QSize
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QCursor
    from PyQt6.QtSvg import QSvgRenderer
except ImportError:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
    from PyQt5.QtCore import Qt, QTimer, QByteArray, QSize
    from PyQt5.QtGui import QIcon, QPixmap, QPainter, QCursor
    from PyQt5.QtSvg import QSvgRenderer

from .settings_utils import ElidedLabel


class SettingsListView(QWidget):
    """View A: List of keybindings - main settings view"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.revert_timers = {}  # Track revert timers by button
        self.setup_ui()
        self.load_keybindings()

    def setup_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scrollable list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: #1e1e1e; border: none; }")

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: #1e1e1e;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(16, 16, 16, 80)
        self.list_layout.setSpacing(12)

        scroll.setWidget(self.list_container)
        layout.addWidget(scroll)

        # Add button (fixed at bottom)
        add_btn = QPushButton("+ Add Shortcut")
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.setFixedHeight(48)
        add_btn.setStyleSheet("""
            QPushButton {
                background: #2c2c2c;
                color: #ffffff;
                border: 1px solid #374151;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #374151;
                border-color: #4b5563;
            }
        """)
        add_btn.clicked.connect(self.add_keybinding)

        # Position add button at bottom
        add_btn_container = QWidget()
        add_btn_container.setStyleSheet("background: #1e1e1e; border-top: 1px solid rgba(255, 255, 255, 0.06);")
        add_btn_layout = QVBoxLayout(add_btn_container)
        add_btn_layout.setContentsMargins(16, 12, 16, 12)
        add_btn_layout.addWidget(add_btn)

        layout.addWidget(add_btn_container)

    def load_keybindings(self):
        """Load and display keybindings"""
        config = mw.addonManager.getConfig(__name__) or {}
        self.keybindings = config.get("keybindings", [])

        if not self.keybindings:
            self.keybindings = [
                {
                    "name": "Standard Explain",
                    "keys": ["Control", "Shift", "S"],
                    "question_template": "Can you explain this to me:\n\n{front}",
                    "answer_template": "Can you explain this to me:\n\nQuestion:\n{front}\n\nAnswer:\n{back}"
                },
                {
                    "name": "Front/Back",
                    "keys": ["Control", "Shift", "Q"],
                    "question_template": "{front}",
                    "answer_template": "{front}"
                },
                {
                    "name": "Back Only",
                    "keys": ["Control", "Shift", "A"],
                    "question_template": "",
                    "answer_template": "{back}"
                }
            ]
            config["keybindings"] = self.keybindings
            mw.addonManager.writeConfig(__name__, config)

        self.refresh_list()

    def refresh_list(self):
        """Refresh the keybinding cards"""
        # Stop and clear all active revert timers before deleting widgets
        for timer in self.revert_timers.values():
            if timer and timer.isActive():
                timer.stop()
        self.revert_timers.clear()

        # Clear existing cards
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add cards for each keybinding
        for i, kb in enumerate(self.keybindings):
            card = self.create_keybinding_card(kb, i)
            self.list_layout.addWidget(card)

        self.list_layout.addStretch()

    def create_keybinding_card(self, kb, index):
        """Create a card widget for a keybinding"""
        # Main card container (not clickable - buttons handle actions)
        card = QWidget()
        card.setFixedHeight(56)

        # Main horizontal layout
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 8, 16, 8)
        card_layout.setSpacing(12)

        # Left: Keycaps
        keycaps_layout = QHBoxLayout()
        keycaps_layout.setSpacing(4)

        keys = kb.get("keys", [])
        for key in keys:
            # Format key display
            if key == "Control/Meta":
                display = "⌘" if sys.platform == "darwin" else "Ctrl"
            elif key == "Meta":
                display = "⌘"  # Cmd key on macOS
            elif key == "Control":
                display = "⌃" if sys.platform == "darwin" else "Ctrl"  # Control key
            elif key == "Shift":
                display = "⇧"
            elif key == "Alt":
                display = "⌥"
            else:
                display = key

            keycap = QLabel(display)
            keycap.setStyleSheet("""
                QLabel {
                    background: #374151;
                    border: 1px solid #4b5563;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 500;
                }
            """)
            keycaps_layout.addWidget(keycap)

        card_layout.addLayout(keycaps_layout)

        # Middle: Template preview (uses ElidedLabel for responsive text)
        # If front template is empty, use back template for preview
        template = kb.get("question_template", "")
        if not template or not template.strip():
            template = kb.get("answer_template", "")
        preview = template.replace("\n", " ")
        preview_label = ElidedLabel(preview)
        preview_label.setStyleSheet("""
            color: #9ca3af;
            font-size: 12px;
            padding-left: 12px;
        """)
        # Add with stretch factor 1 to absorb flexible space
        card_layout.addWidget(preview_label, 1)

        # Right: Edit button (pencil icon)
        edit_btn = QPushButton()
        edit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        edit_btn.setFixedSize(32, 32)

        # Create high-resolution SVG icon for edit button
        edit_icon_svg = """<?xml version="1.0" encoding="UTF-8"?>
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M38 10L32 4L12 24L10 34L20 32L40 12L38 10Z M32 4L38 10 M16 28L20 32" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """

        # Render SVG at higher resolution for crisp display
        svg_bytes_edit = QByteArray(edit_icon_svg.encode())
        renderer_edit = QSvgRenderer(svg_bytes_edit)
        pixmap_edit = QPixmap(48, 48)
        try:
            pixmap_edit.fill(Qt.GlobalColor.transparent)
        except:
            pixmap_edit.fill(Qt.transparent)
        painter_edit = QPainter(pixmap_edit)
        renderer_edit.render(painter_edit)
        painter_edit.end()

        edit_btn.setIcon(QIcon(pixmap_edit))
        edit_btn.setIconSize(QSize(16, 16))

        edit_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
        """)
        edit_btn.clicked.connect(lambda: self.edit_keybinding(index))
        card_layout.addWidget(edit_btn)

        # Right: Delete button (trash icon with confirm logic)
        delete_btn = QPushButton()
        delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        delete_btn.setFixedSize(32, 32)
        delete_btn.setProperty("state", "normal")
        delete_btn.setProperty("index", index)

        # Create high-resolution SVG icon for delete button
        delete_icon_svg = """<?xml version="1.0" encoding="UTF-8"?>
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M16 10V6h16v4M8 10h32M12 10v28h24V10" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M20 18v14M28 18v14" stroke="white" stroke-width="3" stroke-linecap="round"/>
        </svg>
        """

        # Render SVG at higher resolution for crisp display
        svg_bytes_delete = QByteArray(delete_icon_svg.encode())
        renderer_delete = QSvgRenderer(svg_bytes_delete)
        pixmap_delete = QPixmap(48, 48)
        try:
            pixmap_delete.fill(Qt.GlobalColor.transparent)
        except:
            pixmap_delete.fill(Qt.transparent)
        painter_delete = QPainter(pixmap_delete)
        renderer_delete.render(painter_delete)
        painter_delete.end()

        delete_btn.setIcon(QIcon(pixmap_delete))
        delete_btn.setIconSize(QSize(16, 16))

        delete_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.1);
            }
        """)
        delete_btn.clicked.connect(lambda: self.handle_delete_click(delete_btn, edit_btn, index))
        card_layout.addWidget(delete_btn)

        # Card background
        card.setStyleSheet("""
            QWidget {
                background: #2c2c2c;
                border: 1px solid #374151;
                border-radius: 8px;
            }
        """)

        return card

    def handle_delete_click(self, button, edit_btn, index):
        """Handle delete button click with confirmation"""
        state = button.property("state")

        if state == "normal":
            # First click - show confirm
            button.setIcon(QIcon())  # Remove icon
            button.setText("Confirm?")
            button.setProperty("state", "confirm")
            # Expand button to fit text
            button.setFixedSize(70, 32)
            button.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #dc2626;
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: rgba(220, 38, 38, 0.1);
                }
            """)

            # Hide edit button to prevent card overflow
            if edit_btn:
                edit_btn.hide()

            # Start 3-second timer to revert
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self.revert_delete_button(button, edit_btn))
            timer.start(3000)
            # Store timer reference in instance dict so we can cancel it if user confirms
            self.revert_timers[id(button)] = timer

        elif state == "confirm":
            # Second click - check if this is the last keybinding before attempting delete
            config = mw.addonManager.getConfig(__name__) or {}
            keybindings = config.get("keybindings", [])

            if len(keybindings) <= 1:
                # Cannot delete the last keybinding - show error and revert button
                tooltip("Cannot delete the last keybinding")
                # Revert button state immediately
                self.revert_delete_button(button, edit_btn)
                return

            # Proceed with deletion
            # Cancel the revert timer since we're deleting
            button_id = id(button)
            if button_id in self.revert_timers:
                timer = self.revert_timers[button_id]
                if timer and timer.isActive():
                    timer.stop()
                del self.revert_timers[button_id]

            # Disconnect button to prevent further clicks during deletion
            try:
                button.clicked.disconnect()
            except:
                pass

            # Defer deletion with longer delay to ensure click event fully completes
            QTimer.singleShot(50, lambda: self.delete_keybinding(index))

    def revert_delete_button(self, button, edit_btn):
        """Revert delete button to normal state after timeout"""
        try:
            # Check if button still exists and hasn't been deleted
            if not button or not hasattr(button, 'property'):
                return

            if button.property("state") == "confirm":
                button.setText("")
                button.setProperty("state", "normal")

                # Clean up timer reference
                button_id = id(button)
                if button_id in self.revert_timers:
                    del self.revert_timers[button_id]

                # Show edit button again
                if edit_btn:
                    edit_btn.show()

                # Recreate delete icon
                delete_icon_svg = """<?xml version="1.0" encoding="UTF-8"?>
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M16 10V6h16v4M8 10h32M12 10v28h24V10" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M20 18v14M28 18v14" stroke="white" stroke-width="3" stroke-linecap="round"/>
                </svg>
                """

                svg_bytes_delete = QByteArray(delete_icon_svg.encode())
                renderer_delete = QSvgRenderer(svg_bytes_delete)
                pixmap_delete = QPixmap(48, 48)
                try:
                    pixmap_delete.fill(Qt.GlobalColor.transparent)
                except:
                    pixmap_delete.fill(Qt.transparent)
                painter_delete = QPainter(pixmap_delete)
                renderer_delete.render(painter_delete)
                painter_delete.end()

                button.setIcon(QIcon(pixmap_delete))
                button.setIconSize(QSize(16, 16))
                # Restore original button size
                button.setFixedSize(32, 32)

                button.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: none;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background: rgba(239, 68, 68, 0.1);
                    }
                """)
        except RuntimeError:
            # Button was deleted before timer fired, ignore
            pass

    def delete_keybinding(self, index):
        """Delete a keybinding"""
        config = mw.addonManager.getConfig(__name__) or {}
        keybindings = config.get("keybindings", [])

        if len(keybindings) <= 1:
            tooltip("Cannot delete the last keybinding")
            return

        del keybindings[index]
        config["keybindings"] = keybindings
        mw.addonManager.writeConfig(__name__, config)

        # Refresh the list
        self.load_keybindings()

        # Refresh JavaScript in panel
        self._refresh_panel_javascript()

    def _refresh_panel_javascript(self):
        """Helper to refresh JavaScript in the main panel"""
        from . import dock_widget
        if dock_widget and dock_widget.widget():
            panel = dock_widget.widget()
            # Only update keybindings, don't re-inject the entire listener
            if hasattr(panel, 'update_keybindings_in_js'):
                panel.update_keybindings_in_js()
                # Also update card texts to match new keybindings
                if hasattr(panel, 'update_card_text_in_js'):
                    panel.update_card_text_in_js()

    def add_keybinding(self):
        """Add a new keybinding"""
        if self.parent_panel and hasattr(self.parent_panel, 'show_editor_view'):
            self.parent_panel.show_editor_view(None, None)

    def edit_keybinding(self, index):
        """Edit a keybinding"""
        # Notify tutorial FIRST (before view changes)
        try:
            from .tutorial import tutorial_event
            tutorial_event("template_edit_opened")
        except Exception as e:
            print(f"Tutorial event error: {e}")
        
        if self.parent_panel and hasattr(self.parent_panel, 'show_editor_view'):
            self.parent_panel.show_editor_view(self.keybindings[index].copy(), index)
