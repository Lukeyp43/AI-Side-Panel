"""
Settings Editor View - Editor for a single keybinding.
"""

import sys
from aqt import mw
from aqt.utils import tooltip

# Addon name for config storage (must match folder name, not __name__)
ADDON_NAME = "the_ai_panel"

try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QTextEdit
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QCursor
except ImportError:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QTextEdit
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QCursor

from .settings_utils import ElidedLabel
from .key_recorder import KeyRecorderMixin


class SettingsEditorView(KeyRecorderMixin, QWidget):
    """View B: Editor for a single keybinding - drill-down view"""
    def __init__(self, parent=None, keybinding=None, index=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.index = index  # None for new, number for edit
        self.keybinding = keybinding or {
            "name": "New Shortcut",
            "keys": [],
            "question_template": "Can you explain this to me:\nQuestion:\n{front}",
            "answer_template": "Can you explain this to me:\nQuestion:\n{front}\n\nAnswer:\n{back}"
        }

        # Initialize key recorder
        self.setup_key_recorder()

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
        content_layout.setSpacing(20)

        # Section 1: Key Recorder
        key_label = QLabel("Shortcut Key")
        key_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
        content_layout.addWidget(key_label)

        self.key_display = QPushButton()
        self.key_display.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.key_display.setFixedHeight(60)
        self._update_key_display()
        self.key_display.clicked.connect(self.start_recording)
        content_layout.addWidget(self.key_display)

        # Section 2: Front Side Template
        # Row 1: Header (Label only)
        q_label = QLabel("Front Side Template")
        q_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; margin-top: 12px;")
        content_layout.addWidget(q_label)

        # Row 2: Input
        self.question_template = QTextEdit()
        self.question_template.setPlainText(self.keybinding.get("question_template", ""))
        self.question_template.setStyleSheet("""
            QTextEdit {
                background-color: #2c2c2c;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px;
                color: white;
                font-size: 13px;
                font-family: Menlo, Monaco, 'Courier New', monospace;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #4b5563;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.question_template.setMinimumHeight(100)
        content_layout.addWidget(self.question_template)

        # Row 3: Footer (Helper text left, chips right)
        q_footer_layout = QHBoxLayout()
        q_footer_layout.setSpacing(8)
        q_footer_layout.setContentsMargins(0, 4, 0, 0)

        q_help = ElidedLabel("Only {front} is available.")
        q_help.setStyleSheet("color: #6b7280; font-size: 11px;")
        q_footer_layout.addWidget(q_help, 1)  # Stretch factor 1 to absorb flexible space

        q_front_chip = QPushButton("+ {front}")
        q_front_chip.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        q_front_chip.setFixedHeight(24)
        q_front_chip.setMinimumWidth(75)
        q_front_chip.setStyleSheet("""
            QPushButton {
                background: #374151;
                color: #ffffff;
                border: none;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #4b5563;
            }
        """)
        q_front_chip.clicked.connect(lambda: self.insert_variable(self.question_template, "{front}"))
        q_footer_layout.addWidget(q_front_chip)

        content_layout.addLayout(q_footer_layout)

        # Section 3: Back Side Template
        # Row 1: Header (Label only)
        a_label = QLabel("Back Side Template")
        a_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; margin-top: 12px;")
        content_layout.addWidget(a_label)

        # Row 2: Input
        self.answer_template = QTextEdit()
        self.answer_template.setPlainText(self.keybinding.get("answer_template", ""))
        self.answer_template.setStyleSheet("""
            QTextEdit {
                background-color: #2c2c2c;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px;
                color: white;
                font-size: 13px;
                font-family: Menlo, Monaco, 'Courier New', monospace;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #4b5563;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.answer_template.setMinimumHeight(100)
        content_layout.addWidget(self.answer_template)

        # Row 3: Footer (Helper text left, chips right)
        a_footer_layout = QHBoxLayout()
        a_footer_layout.setSpacing(8)
        a_footer_layout.setContentsMargins(0, 4, 0, 0)

        a_help = ElidedLabel("Both {front} and {back} are available.")
        a_help.setStyleSheet("color: #6b7280; font-size: 11px;")
        a_footer_layout.addWidget(a_help, 1)  # Stretch factor 1 to absorb flexible space

        a_front_chip = QPushButton("+ {front}")
        a_front_chip.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        a_front_chip.setFixedHeight(24)
        a_front_chip.setMinimumWidth(75)
        a_front_chip.setStyleSheet("""
            QPushButton {
                background: #374151;
                color: #ffffff;
                border: none;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #4b5563;
            }
        """)
        a_front_chip.clicked.connect(lambda: self.insert_variable(self.answer_template, "{front}"))
        a_footer_layout.addWidget(a_front_chip)

        a_back_chip = QPushButton("+ {back}")
        a_back_chip.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        a_back_chip.setFixedHeight(24)
        a_back_chip.setMinimumWidth(75)
        a_back_chip.setStyleSheet("""
            QPushButton {
                background: #374151;
                color: #ffffff;
                border: none;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #4b5563;
            }
        """)
        a_back_chip.clicked.connect(lambda: self.insert_variable(self.answer_template, "{back}"))
        a_footer_layout.addWidget(a_back_chip)

        content_layout.addLayout(a_footer_layout)

        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Bottom section with Save button
        bottom_section = QWidget()
        bottom_section.setStyleSheet("background: #1e1e1e; border-top: 1px solid rgba(255, 255, 255, 0.06);")
        bottom_layout = QVBoxLayout(bottom_section)
        bottom_layout.setContentsMargins(16, 12, 16, 12)

        # Save button (disabled by default until changes are made)
        self.save_btn = QPushButton("Save")
        self.save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.save_btn.setFixedHeight(44)
        self.save_btn.setEnabled(False)  # Disabled by default
        self._update_save_button_style()
        self.save_btn.clicked.connect(self.save_and_go_back)
        bottom_layout.addWidget(self.save_btn)

        layout.addWidget(bottom_section)

        # Store initial state to detect changes
        self._initial_state = {
            'keys': self.keybinding.get('keys', []).copy() if self.keybinding.get('keys') else [],
            'question_template': self.keybinding.get('question_template', ''),
            'answer_template': self.keybinding.get('answer_template', '')
        }

        # Connect change signals
        self.question_template.textChanged.connect(self._on_change)
        self.answer_template.textChanged.connect(self._on_change)

    def _update_save_button_style(self):
        """Update save button appearance based on enabled state"""
        if self.save_btn.isEnabled():
            self.save_btn.setStyleSheet("""
                QPushButton {
                    background: #3b82f6;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #2563eb;
                }
            """)
        else:
            self.save_btn.setStyleSheet("""
                QPushButton {
                    background: #333333;
                    color: #666666;
                    border: 1px solid #444444;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                }
            """)

    def insert_variable(self, text_edit, variable):
        """Insert a variable at the current cursor position in a QTextEdit"""
        cursor = text_edit.textCursor()
        cursor.insertText(variable)
        text_edit.setFocus()

    def _on_change(self):
        """Detect if any changes were made and enable/disable save button"""
        # Get current state
        current_keys = self.keybinding.get('keys', [])
        current_question = self.question_template.toPlainText()
        current_answer = self.answer_template.toPlainText()

        # Compare with initial state
        has_changes = (
            current_keys != self._initial_state['keys'] or
            current_question != self._initial_state['question_template'] or
            current_answer != self._initial_state['answer_template']
        )

        # Enable/disable save button
        self.save_btn.setEnabled(has_changes)
        self._update_save_button_style()

    def _update_key_display(self):
        """Update the key display button appearance"""
        from .utils import format_keys_verbose

        keys = self.keybinding.get("keys", [])
        if self.recording_keys:
            text = "Press any key combination..."
            style = """
                QPushButton {
                    background: #2c2c2c;
                    color: #3b82f6;
                    border: 2px solid #3b82f6;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 500;
                }
            """
        elif keys:
            # Display keycaps
            text = format_keys_verbose(keys)
            style = """
                QPushButton {
                    background: #2c2c2c;
                    color: #ffffff;
                    border: 1px solid #374151;
                    border-radius: 8px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    border-color: #4b5563;
                }
            """
        else:
            text = "Click to set shortcut"
            style = """
                QPushButton {
                    background: #2c2c2c;
                    color: #9ca3af;
                    border: 1px dashed #374151;
                    border-radius: 8px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    border-color: #4b5563;
                }
            """

        self.key_display.setText(text)
        self.key_display.setStyleSheet(style)

    def start_recording(self):
        """Start recording key presses"""
        self._update_key_display()
        # Call mixin's start_recording
        super().start_recording()

    def _update_recording_display(self, keys):
        """Called by KeyRecorderMixin during recording to update the display"""
        # Update the display to show current keys being recorded
        from .utils import format_keys_verbose
        if keys:
            self.key_display.setText(format_keys_verbose(keys))
        else:
            self.key_display.setText("Press any key combination...")

    def _on_keys_recorded(self, keys):
        """Called by KeyRecorderMixin when recording is complete"""
        if keys:
            # Keep the original order (don't sort)
            self.keybinding["keys"] = keys
        self._update_key_display()
        self._on_change()  # Check if changes were made

    def discard_and_go_back(self):
        """Discard changes and return to list view without saving"""
        if self.parent_panel and hasattr(self.parent_panel, 'show_list_view'):
            self.parent_panel.show_list_view()

    def save_and_go_back(self):
        """Save changes and return to list view"""
        # Validate
        if not self.keybinding.get("keys"):
            tooltip("Please set a keyboard shortcut")
            return

        question_template = self.question_template.toPlainText().strip()

        # Only validation: {back} cannot be used in Front Side Template (back content isn't available yet)
        if "{back}" in question_template:
            tooltip("Front Side Template cannot use {back} - only {front} is available when viewing the question")
            return

        answer_template = self.answer_template.toPlainText().strip()

        # Check for duplicate keybindings
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        keybindings = config.get("keybindings", [])
        current_keys = self.keybinding.get("keys", [])

        for i, kb in enumerate(keybindings):
            # Skip the current keybinding if we're editing
            if self.index is not None and i == self.index:
                continue

            # Check if keys match
            existing_keys = kb.get("keys", [])
            if existing_keys == current_keys:
                tooltip("This key combination is already in use by another shortcut")
                return

        # Save
        self.keybinding["question_template"] = question_template
        self.keybinding["answer_template"] = answer_template

        # Update config
        if self.index is None:
            # New keybinding
            keybindings.append(self.keybinding)
        else:
            # Edit existing
            keybindings[self.index] = self.keybinding

        config["keybindings"] = keybindings
        mw.addonManager.writeConfig(__name__, config)

        # Refresh JavaScript in panel
        self._refresh_panel_javascript()

        # Go back to list
        if self.parent_panel and hasattr(self.parent_panel, 'show_list_view'):
            self.parent_panel.show_list_view()

    def _refresh_panel_javascript(self):
        """Helper to refresh JavaScript in the main panel"""
        # Import here to avoid circular imports
        from . import dock_widget
        if dock_widget and dock_widget.widget():
            panel = dock_widget.widget()
            # Only update keybindings, don't re-inject the entire listener
            if hasattr(panel, 'update_keybindings_in_js'):
                panel.update_keybindings_in_js()
                # Also update card texts to match new keybindings
                if hasattr(panel, 'update_card_text_in_js'):
                    panel.update_card_text_in_js()
