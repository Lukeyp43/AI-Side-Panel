"""
Settings Quick Actions View - Configure keyboard shortcuts for highlight actions.
"""

import sys
from aqt import mw
from aqt.utils import tooltip

# Addon name for config storage (must match folder name, not __name__)
from aqt.utils import tooltip
from .utils import ADDON_NAME
from .theme_manager import ThemeManager

try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
    from PyQt6.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty
    from PyQt6.QtGui import QCursor, QPainter, QColor
except ImportError:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
    from PyQt5.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty
    from PyQt5.QtGui import QCursor, QPainter, QColor

from .key_recorder import KeyRecorderMixin


class ToggleSwitch(QWidget):
    """A proper iOS-style toggle switch widget."""
    def __init__(self, checked=False, on_color="#4A90D9", off_color="#555555", parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._checked = checked
        self._on_color = on_color
        self._off_color = off_color
        # Knob position: 0.0 = left (off), 1.0 = right (on)
        self._knob_position = 1.0 if checked else 0.0
        self._animation = QPropertyAnimation(self, b"knob_position")
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._toggled_callbacks = []

    def connect_toggled(self, callback):
        self._toggled_callbacks.append(callback)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked == checked:
            return
        self._checked = checked
        self._animate()
        for cb in self._toggled_callbacks:
            cb(checked)

    def _get_knob_position(self):
        return self._knob_position

    def _set_knob_position(self, pos):
        self._knob_position = pos
        self.update()

    knob_position = pyqtProperty(float, _get_knob_position, _set_knob_position)

    def _animate(self):
        self._animation.stop()
        self._animation.setStartValue(self._knob_position)
        self._animation.setEndValue(1.0 if self._checked else 0.0)
        self._animation.start()

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self._animate()
        for cb in self._toggled_callbacks:
            cb(self._checked)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = h / 2

        # Track color - interpolate between off and on
        on = QColor(self._on_color)
        off = QColor(self._off_color)
        t = self._knob_position
        track_color = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        p.setBrush(track_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        # Knob
        knob_diameter = h - 4
        knob_x = 2 + self._knob_position * (w - knob_diameter - 4)
        knob_y = 2
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(knob_x, knob_y, knob_diameter, knob_diameter))
        p.end()


class QuickActionsSettingsView(KeyRecorderMixin, QWidget):
    """View for configuring quick action keyboard shortcuts"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.recording_target = None  # 'add_to_chat' or 'ask_question'

        # Initialize key recorder
        self.setup_key_recorder()

        # Load current shortcuts from config
        self.config = mw.addonManager.getConfig(ADDON_NAME) or {}
        self.shortcuts = self.config.get("quick_actions", {
            "add_to_chat": {"keys": ["Meta", "F"]},
            "ask_question": {"keys": ["Meta", "R"]}
        })
        self.highlight_modifier = self.config.get("highlight_modifier", "none")

        self.setup_ui()

    def setup_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        c = ThemeManager.get_palette()
        
        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(ThemeManager.get_scroll_area_style())

        content = QWidget()
        content.setStyleSheet(f"background: {c['background']};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(24)

        # Header
        header = QLabel("Quick Actions")
        header.setStyleSheet(f"""
            color: {c['text']};
            font-size: 20px;
            font-weight: 700;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        """)
        content_layout.addWidget(header)

        # Description
        desc = QLabel("Configure keyboard shortcuts for text highlighting actions")
        desc.setStyleSheet(f"""
            color: {c['text_secondary']};
            font-size: 13px;
            margin-bottom: 8px;
        """)
        desc.setWordWrap(True)
        content_layout.addWidget(desc)

        # Store initial state early (before toggles trigger _check_for_changes)
        self._initial_state = {
            'add_to_chat': self.shortcuts["add_to_chat"]["keys"].copy(),
            'ask_question': self.shortcuts["ask_question"]["keys"].copy(),
            'explain_enabled': self.config.get('explain_enabled', True),
            'add_to_chat_enabled': self.config.get('add_to_chat_enabled', True),
            'ask_question_enabled': self.config.get('ask_question_enabled', True),
        }

        # --- Feature toggles ---
        self.toggles = {}

        def make_toggle_row(key, title, description):
            row = QWidget()
            row.setStyleSheet(f"background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 10, 14, 10)
            row_layout.setSpacing(10)

            left = QVBoxLayout()
            left.setSpacing(2)
            t = QLabel(title)
            t.setStyleSheet(f"color: {c['text']}; font-size: 13px; font-weight: 600; background: transparent; border: none;")
            d = QLabel(description)
            d.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px; background: transparent; border: none;")
            d.setWordWrap(True)
            left.addWidget(t)
            left.addWidget(d)
            row_layout.addLayout(left, 1)

            toggle = ToggleSwitch(
                checked=self.config.get(key, True),
                on_color=c['accent'],
                off_color=c['border'],
            )
            toggle.connect_toggled(lambda checked: self._check_for_changes())
            self.toggles[key] = toggle
            row_layout.addWidget(toggle)

            return row

        content_layout.addWidget(make_toggle_row(
            "explain_enabled", "Explain",
            "Highlight text to see inline explanation"
        ))
        content_layout.addWidget(make_toggle_row(
            "add_to_chat_enabled", "Add to Chat",
            "\u2318 Cmd + highlight to send text to panel"
        ))
        content_layout.addWidget(make_toggle_row(
            "ask_question_enabled", "Ask Question",
            "\u2318 Cmd + highlight to ask about text"
        ))

        # --- Keyboard Shortcuts ---
        shortcuts_header = QLabel("Keyboard Shortcuts")
        shortcuts_header.setStyleSheet(f"color: {c['text']}; font-size: 14px; font-weight: bold; margin-top: 8px;")
        content_layout.addWidget(shortcuts_header)

        def make_shortcut_row(target_key, title, description):
            row = QWidget()
            row.setStyleSheet(f"background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 10, 14, 10)
            row_layout.setSpacing(10)

            left = QVBoxLayout()
            left.setSpacing(2)
            t = QLabel(title)
            t.setStyleSheet(f"color: {c['text']}; font-size: 13px; font-weight: 600; background: transparent; border: none;")
            d = QLabel(description)
            d.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px; background: transparent; border: none;")
            d.setWordWrap(True)
            left.addWidget(t)
            left.addWidget(d)
            row_layout.addLayout(left, 1)

            shortcut_btn = QPushButton()
            shortcut_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            shortcut_btn.setFixedHeight(32)
            shortcut_btn.setMinimumWidth(80)
            shortcut_btn.clicked.connect(lambda: self.start_recording(target_key))
            row_layout.addWidget(shortcut_btn)

            return row, shortcut_btn

        row1, self.add_to_chat_display = make_shortcut_row(
            "add_to_chat", "Add to Chat", "Tap to change shortcut"
        )
        self._update_shortcut_display(self.add_to_chat_display, self.shortcuts["add_to_chat"]["keys"])
        content_layout.addWidget(row1)

        row2, self.ask_question_display = make_shortcut_row(
            "ask_question", "Ask Question", "Tap to change shortcut"
        )
        self._update_shortcut_display(self.ask_question_display, self.shortcuts["ask_question"]["keys"])
        content_layout.addWidget(row2)

        content_layout.addStretch()


        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Bottom section with Save button
        bottom_section = QWidget()
        bottom_section.setStyleSheet(ThemeManager.get_bottom_section_style())
        bottom_layout = QVBoxLayout(bottom_section)
        bottom_layout.setContentsMargins(16, 12, 16, 12)

        # Save button (disabled by default)
        self.save_btn = QPushButton("Save")
        self.save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.save_btn.setFixedHeight(44)
        self.save_btn.setEnabled(False)  # Disabled by default
        self._update_save_button_style()
        self.save_btn.clicked.connect(self.save_shortcuts)
        bottom_layout.addWidget(self.save_btn)

        layout.addWidget(bottom_section)

    def _update_shortcut_display(self, button, keys):
        """Update a shortcut display button with current keys"""
        from .utils import format_keys_verbose

        c = ThemeManager.get_palette()

        if self.recording_target:
            # During recording
            if keys:
                display_text = format_keys_verbose(keys)
                button.setText(display_text)
            else:
                button.setText("Press keys...")

            button.setStyleSheet(f"""
                QPushButton {{
                    background: {c['accent']};
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 4px 12px;
                }}
            """)
        else:
            # Normal state
            if keys:
                display_text = format_keys_verbose(keys)
                button.setText(display_text)
            else:
                button.setText("Set shortcut")

            button.setStyleSheet(f"""
                QPushButton {{
                    background: {c['background']};
                    color: {c['text_secondary']};
                    border: 1px solid {c['border']};
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 4px 12px;
                }}
                QPushButton:hover {{
                    background: {c['border']};
                    color: {c['text']};
                }}
            """)

    def start_recording(self, target):
        """Start recording keys for a specific shortcut"""
        self.recording_target = target

        if target == 'add_to_chat':
            self._update_shortcut_display(self.add_to_chat_display, [])
        else:
            self._update_shortcut_display(self.ask_question_display, [])

        super().start_recording()

    def _update_recording_display(self, keys):
        """Called by KeyRecorderMixin during recording to update the display"""
        if self.recording_target == 'add_to_chat':
            self._update_shortcut_display(self.add_to_chat_display, keys)
        else:
            self._update_shortcut_display(self.ask_question_display, keys)

    def _on_keys_recorded(self, keys):
        """Called by KeyRecorderMixin when recording is complete"""
        if not self.recording_target:
            return

        if keys:
            self.shortcuts[self.recording_target]["keys"] = keys

        if self.recording_target == 'add_to_chat':
            self._update_shortcut_display(self.add_to_chat_display, self.shortcuts["add_to_chat"]["keys"])
        else:
            self._update_shortcut_display(self.ask_question_display, self.shortcuts["ask_question"]["keys"])

        self.recording_target = None
        self._check_for_changes()

    def _check_for_changes(self):
        """Detect if any changes were made and enable/disable save button"""
        if not hasattr(self, 'save_btn'):
            return
        # Compare current state with initial state
        has_changes = (
            self.shortcuts["add_to_chat"]["keys"] != self._initial_state['add_to_chat'] or
            self.shortcuts["ask_question"]["keys"] != self._initial_state['ask_question'] or
            self.toggles.get('explain_enabled', None) and self.toggles['explain_enabled'].isChecked() != self._initial_state['explain_enabled'] or
            self.toggles.get('add_to_chat_enabled', None) and self.toggles['add_to_chat_enabled'].isChecked() != self._initial_state['add_to_chat_enabled'] or
            self.toggles.get('ask_question_enabled', None) and self.toggles['ask_question_enabled'].isChecked() != self._initial_state['ask_question_enabled']
        )

        # Enable/disable save button
        self.save_btn.setEnabled(has_changes)
        self._update_save_button_style()

    def _update_save_button_style(self):
        """Update save button appearance based on enabled state"""
        c = ThemeManager.get_palette()
        if self.save_btn.isEnabled():
            self.save_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {c['accent']};
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {c['accent_hover']};
                }}
            """)
        else:
            self.save_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {c['surface']};
                    color: {c['text_secondary']};
                    border: 1px solid {c['border']};
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                }}
            """)

    def save_shortcuts(self):
        """Save shortcuts to config"""
        config = mw.addonManager.getConfig(ADDON_NAME)
        config["quick_actions"] = self.shortcuts
        for key, toggle in self.toggles.items():
            config[key] = toggle.isChecked()
        mw.addonManager.writeConfig(ADDON_NAME, config)

        # Update the JavaScript config in the reviewer immediately
        self._update_reviewer_config()

        # Show success message
        tooltip("Quick Actions shortcuts saved!", period=2000)

        # Navigate back to home
        if self.parent_panel and hasattr(self.parent_panel, 'show_home_view'):
            self.parent_panel.show_home_view()

    def _update_reviewer_config(self):
        """Update the quick actions config in the reviewer's JavaScript context"""
        from aqt import mw
        
        # Get the current config
        config = mw.addonManager.getConfig(ADDON_NAME)
        quick_actions = config.get("quick_actions", {
            "add_to_chat": {"keys": ["Meta", "F"]},
            "ask_question": {"keys": ["Meta", "R"]}
        })

        # Format shortcuts for JavaScript
        add_to_chat_keys = quick_actions["add_to_chat"]["keys"]
        ask_question_keys = quick_actions["ask_question"]["keys"]

        # Create display text (e.g., "⌘F" or "Ctrl+Shift+F")
        def format_shortcut_display(keys):
            display_keys = []
            for key in keys:
                if key == "Meta":
                    display_keys.append("⌘")
                elif key == "Control":
                    display_keys.append("Ctrl")
                elif key == "Shift":
                    display_keys.append("Shift")
                elif key == "Alt":
                    display_keys.append("Alt")
                else:
                    display_keys.append(key)
            return "".join(display_keys) if "⌘" in display_keys else "+".join(display_keys)

        add_to_chat_display = format_shortcut_display(add_to_chat_keys)
        ask_question_display = format_shortcut_display(ask_question_keys)

        # Create JavaScript to update the config
        js_code = f"""
        (function() {{
            // Initialize config if it doesn't exist
            if (!window.quickActionsConfig) {{
                window.quickActionsConfig = {{}};
            }}
            
            window.quickActionsConfig.addToChat = {{
                keys: {add_to_chat_keys},
                display: "{add_to_chat_display}"
            }};
            window.quickActionsConfig.askQuestion = {{
                keys: {ask_question_keys},
                display: "{ask_question_display}"
            }};
            window.quickActionsConfig.explainEnabled = {str(config.get('explain_enabled', True)).lower()};
            window.quickActionsConfig.addToChatEnabled = {str(config.get('add_to_chat_enabled', True)).lower()};
            window.quickActionsConfig.askQuestionEnabled = {str(config.get('ask_question_enabled', True)).lower()};

            // If bubble is visible, update the display text in the buttons
            var bubble = document.getElementById('anki-highlight-bubble');
            if (bubble && bubble.style.display !== 'none') {{
                var addToChatSpan = bubble.querySelector('#add-to-chat-btn span:last-child');
                var askQuestionSpan = bubble.querySelector('#ask-question-btn span:last-child');
                if (addToChatSpan) {{
                    addToChatSpan.textContent = '{add_to_chat_display}';
                }}
                if (askQuestionSpan) {{
                    askQuestionSpan.textContent = '{ask_question_display}';
                }}
            }}
            
            console.log('Anki: Quick Actions config updated:', window.quickActionsConfig);
        }})();
        """

        # Try to inject into the reviewer webview
        try:
            if mw.reviewer and hasattr(mw.reviewer, 'web') and mw.reviewer.web:
                # Try eval() first (Anki's webview method)
                if hasattr(mw.reviewer.web, 'eval'):
                    mw.reviewer.web.eval(js_code)
                # Fallback to runJavaScript if available
                elif hasattr(mw.reviewer.web, 'page'):
                    mw.reviewer.web.page().runJavaScript(js_code)
                print("OpenEvidence: Updated quick actions config in reviewer")
        except Exception as e:
            print(f"OpenEvidence: Could not update reviewer config: {e}")
            # Config will be updated on next card review
