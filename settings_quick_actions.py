"""
Settings Quick Actions View - Configure keyboard shortcuts for highlight actions.
"""

import sys
from aqt import mw
from aqt.utils import tooltip

try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QCursor
except ImportError:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QCursor


class QuickActionsSettingsView(QWidget):
    """View for configuring quick action keyboard shortcuts"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.recording_target = None  # 'add_to_chat' or 'ask_question'
        self.pressed_keys = []

        # Load current shortcuts from config
        config = mw.addonManager.getConfig(__name__)
        self.shortcuts = config.get("quick_actions", {
            "add_to_chat": {"keys": ["Meta", "F"]},
            "ask_question": {"keys": ["Meta", "R"]}
        })

        self.setup_ui()

    def setup_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: #1e1e1e; border: none; }")

        content = QWidget()
        content.setStyleSheet("background: #1e1e1e;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(24)

        # Header
        header = QLabel("Quick Actions")
        header.setStyleSheet("""
            color: #ffffff;
            font-size: 20px;
            font-weight: 700;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        """)
        content_layout.addWidget(header)

        # Description
        desc = QLabel("Configure keyboard shortcuts for text highlighting actions")
        desc.setStyleSheet("""
            color: #9ca3af;
            font-size: 13px;
            margin-bottom: 8px;
        """)
        desc.setWordWrap(True)
        content_layout.addWidget(desc)

        # Add to Chat shortcut
        add_to_chat_label = QLabel("Add to Chat")
        add_to_chat_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; margin-top: 12px;")
        content_layout.addWidget(add_to_chat_label)

        self.add_to_chat_display = QPushButton()
        self.add_to_chat_display.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_to_chat_display.setFixedHeight(60)
        self._update_shortcut_display(self.add_to_chat_display, self.shortcuts["add_to_chat"]["keys"])
        self.add_to_chat_display.clicked.connect(lambda: self.start_recording('add_to_chat'))
        content_layout.addWidget(self.add_to_chat_display)

        add_to_chat_desc = QLabel("Directly add highlighted text to OpenEvidence chat")
        add_to_chat_desc.setStyleSheet("color: #6b7280; font-size: 11px; margin-bottom: 8px;")
        content_layout.addWidget(add_to_chat_desc)

        # Ask Question shortcut
        ask_question_label = QLabel("Ask Question")
        ask_question_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; margin-top: 12px;")
        content_layout.addWidget(ask_question_label)

        self.ask_question_display = QPushButton()
        self.ask_question_display.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ask_question_display.setFixedHeight(60)
        self._update_shortcut_display(self.ask_question_display, self.shortcuts["ask_question"]["keys"])
        self.ask_question_display.clicked.connect(lambda: self.start_recording('ask_question'))
        content_layout.addWidget(self.ask_question_display)

        ask_question_desc = QLabel("Open question input with highlighted text as context")
        ask_question_desc.setStyleSheet("color: #6b7280; font-size: 11px; margin-bottom: 8px;")
        content_layout.addWidget(ask_question_desc)

        content_layout.addStretch()

        # Save button at bottom
        save_btn = QPushButton("Save")
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn.setFixedHeight(44)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        save_btn.clicked.connect(self.save_shortcuts)
        content_layout.addWidget(save_btn)

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _update_shortcut_display(self, button, keys):
        """Update a shortcut display button with current keys"""
        if self.recording_target:
            # During recording
            if keys:
                display_text = " + ".join(keys)
                button.setText(display_text)
                button.setStyleSheet("""
                    QPushButton {
                        background: #3b82f6;
                        color: white;
                        border: 2px solid #3b82f6;
                        border-radius: 8px;
                        font-size: 14px;
                        font-weight: 600;
                    }
                """)
            else:
                button.setText("Press keys...")
                button.setStyleSheet("""
                    QPushButton {
                        background: #2c2c2c;
                        color: #9ca3af;
                        border: 2px dashed #3b82f6;
                        border-radius: 8px;
                        font-size: 14px;
                        font-weight: 500;
                    }
                """)
        else:
            # Normal state
            if keys:
                display_text = " + ".join(keys)
                button.setText(display_text)
            else:
                button.setText("Click to set shortcut")

            button.setStyleSheet("""
                QPushButton {
                    background: #2c2c2c;
                    color: #ffffff;
                    border: 1px solid #374151;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #333333;
                    border-color: #3b82f6;
                }
            """)

    def start_recording(self, target):
        """Start recording keys for a specific shortcut"""
        self.recording_target = target
        self.pressed_keys = []

        # Update display
        if target == 'add_to_chat':
            self._update_shortcut_display(self.add_to_chat_display, [])
        else:
            self._update_shortcut_display(self.ask_question_display, [])

        # Grab keyboard focus
        self.grabKeyboard()

    def keyPressEvent(self, event):
        """Handle key press during recording"""
        if not self.recording_target:
            return super().keyPressEvent(event)

        # Map Qt keys to config format
        key_map = {
            Qt.Key.Key_Control if hasattr(Qt.Key, 'Key_Control') else Qt.Key_Control: "Control",
            Qt.Key.Key_Shift if hasattr(Qt.Key, 'Key_Shift') else Qt.Key_Shift: "Shift",
            Qt.Key.Key_Alt if hasattr(Qt.Key, 'Key_Alt') else Qt.Key_Alt: "Alt",
            Qt.Key.Key_Meta if hasattr(Qt.Key, 'Key_Meta') else Qt.Key_Meta: "Meta",
        }

        key = event.key()

        # Check for modifier keys
        if key in key_map:
            key_name = key_map[key]
            if key_name not in self.pressed_keys:
                self.pressed_keys.append(key_name)
        else:
            # Regular key
            key_text = event.text().upper()
            if key_text and key_text not in self.pressed_keys:
                self.pressed_keys.append(key_text)

        # Update display
        if self.recording_target == 'add_to_chat':
            self._update_shortcut_display(self.add_to_chat_display, self.pressed_keys)
        else:
            self._update_shortcut_display(self.ask_question_display, self.pressed_keys)

    def keyReleaseEvent(self, event):
        """Handle key release during recording"""
        if not self.recording_target:
            return super().keyReleaseEvent(event)

        # Stop recording when all keys are released
        QTimer.singleShot(100, self.check_recording_complete)

    def check_recording_complete(self):
        """Check if recording is complete and finalize"""
        if not self.recording_target:
            return

        # Save the recorded keys
        if self.pressed_keys:
            self.shortcuts[self.recording_target]["keys"] = self.pressed_keys.copy()

        # Release keyboard
        self.releaseKeyboard()

        # Update displays
        if self.recording_target == 'add_to_chat':
            self._update_shortcut_display(self.add_to_chat_display, self.shortcuts["add_to_chat"]["keys"])
        else:
            self._update_shortcut_display(self.ask_question_display, self.shortcuts["ask_question"]["keys"])

        self.recording_target = None

    def save_shortcuts(self):
        """Save shortcuts to config"""
        config = mw.addonManager.getConfig(__name__)
        config["quick_actions"] = self.shortcuts
        mw.addonManager.writeConfig(__name__, config)
        tooltip("Quick Actions shortcuts saved!")

        # Navigate back to home
        if self.parent_panel and hasattr(self.parent_panel, 'show_home_view'):
            self.parent_panel.show_home_view()
