"""
Settings UI for the OpenEvidence add-on.
Contains the drill-down settings interface with list and editor views.
"""

import sys
from aqt import mw
from aqt.qt import *
from aqt.utils import tooltip

try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QTextEdit
    from PyQt6.QtCore import Qt, QTimer, QByteArray, QSize
    from PyQt6.QtGui import QIcon, QPixmap, QPainter
    from PyQt6.QtSvg import QSvgRenderer
except ImportError:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QTextEdit
    from PyQt5.QtCore import Qt, QTimer, QByteArray, QSize
    from PyQt5.QtGui import QIcon, QPixmap, QPainter
    from PyQt5.QtSvg import QSvgRenderer

from .utils import format_keys_display, format_keys_verbose


class ElidedLabel(QLabel):
    """QLabel that automatically elides text with ... when space is tight"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        try:
            self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        except:
            # PyQt5 fallback
            self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def paintEvent(self, event):
        """Draw elided text"""
        painter = QPainter(self)
        metrics = painter.fontMetrics()

        # Get elide mode based on PyQt version
        try:
            elide_mode = Qt.TextElideMode.ElideRight
        except AttributeError:
            elide_mode = Qt.ElideRight

        # Use contentsRect to respect margins/padding from stylesheet
        rect = self.contentsRect()

        # Get elided text that fits in current width (accounting for padding)
        elided = metrics.elidedText(
            self.text(),
            elide_mode,
            rect.width()
        )

        # Draw the elided text within the content rect
        painter.drawText(rect, self.alignment(), elided)


class SettingsEditorView(QWidget):
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
        self.recording_keys = False
        self.pressed_keys = []  # Use list to preserve key press order
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
        self.recording_keys = True
        self.pressed_keys = []  # Use list to preserve key press order
        self._update_key_display()
        self.setFocus()

    def stop_recording(self):
        """Stop recording and save keys"""
        self.recording_keys = False
        if self.pressed_keys:
            # Keep the original order (don't sort)
            self.keybinding["keys"] = self.pressed_keys.copy()
        self._update_key_display()
        self._on_change()  # Check if changes were made

    def keyPressEvent(self, event):
        """Capture key presses when recording (max 3 keys)"""
        if self.recording_keys:
            import sys
            key = event.key()
            
            # On macOS, Qt has a quirk where Control and Meta are swapped:
            # - Qt.Key_Control is actually triggered by the Cmd key (⌘)
            # - Qt.Key_Meta is actually triggered by the Control key (⌃)
            # So we need to swap them in our mapping to match user expectations
            if sys.platform == "darwin":
                key_map = {
                    Qt.Key.Key_Control if hasattr(Qt.Key, 'Key_Control') else Qt.Key_Control: "Meta",  # Cmd key
                    Qt.Key.Key_Meta if hasattr(Qt.Key, 'Key_Meta') else Qt.Key_Meta: "Control",  # Control key
                    Qt.Key.Key_Shift if hasattr(Qt.Key, 'Key_Shift') else Qt.Key_Shift: "Shift",
                    Qt.Key.Key_Alt if hasattr(Qt.Key, 'Key_Alt') else Qt.Key_Alt: "Alt",
                }
            else:
                key_map = {
                    Qt.Key.Key_Control if hasattr(Qt.Key, 'Key_Control') else Qt.Key_Control: "Control/Meta",
                    Qt.Key.Key_Meta if hasattr(Qt.Key, 'Key_Meta') else Qt.Key_Meta: "Control/Meta",
                    Qt.Key.Key_Shift if hasattr(Qt.Key, 'Key_Shift') else Qt.Key_Shift: "Shift",
                    Qt.Key.Key_Alt if hasattr(Qt.Key, 'Key_Alt') else Qt.Key_Alt: "Alt",
                }

            # Check if this is a valid key press (not just a modifier being held)
            is_valid_key = key in key_map or (event.text() and event.text().isprintable())

            # Maximum of 3 keys allowed - show error if trying to add more
            if len(self.pressed_keys) >= 3 and is_valid_key:
                tooltip("Maximum of 3 keys allowed for shortcuts")
                return

            # Add key to list if not already present (preserves order)
            if key in key_map:
                key_name = key_map[key]
                if key_name not in self.pressed_keys:
                    self.pressed_keys.append(key_name)
            elif event.text() and event.text().isprintable():
                key_name = event.text().upper()
                if key_name not in self.pressed_keys:
                    self.pressed_keys.append(key_name)

            # Auto-stop after 500ms, or immediately if we hit 3 keys
            if len(self.pressed_keys) > 0:
                if len(self.pressed_keys) >= 3:
                    # Stop immediately when we reach 3 keys
                    QTimer.singleShot(100, self.stop_recording)
                else:
                    # Otherwise wait 500ms for more keys
                    QTimer.singleShot(500, self.stop_recording)
        else:
            super().keyPressEvent(event)

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
        config = mw.addonManager.getConfig(__name__) or {}
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
        template = kb.get("question_template", "")
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
        if self.parent_panel and hasattr(self.parent_panel, 'show_editor_view'):
            self.parent_panel.show_editor_view(self.keybindings[index].copy(), index)
