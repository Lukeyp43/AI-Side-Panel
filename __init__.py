import sys
import aqt
from aqt import mw, gui_hooks
from aqt.qt import *

from .panel import CustomTitleBar, OpenEvidencePanel, OnboardingDialog
from .utils import clean_html_text
from .reviewer_highlight import setup_highlight_hooks
from .analytics import init_analytics, try_send_daily_analytics, track_add_to_chat, track_ask_question, track_anki_open
from .utils import ADDON_NAME

try:
    from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect
    from PyQt6.QtCore import Qt, QTimer, QEvent, QPropertyAnimation, QRect, QEasingCurve
    from PyQt6.QtGui import QColor, QFont, QPainter
except ImportError:
    from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect
    from PyQt5.QtCore import Qt, QTimer, QEvent, QPropertyAnimation, QRect, QEasingCurve
    from PyQt5.QtGui import QColor, QFont, QPainter

# Global references
dock_widget = None
_book_icon_overlay = None
current_card_question = ""
current_card_answer = ""
is_showing_answer = False

# Platform detection
IS_MAC = sys.platform == "darwin"


class BookIconOverlay(QWidget):
    """Floating tooltip that points at the book icon in the toolbar.
    Uses JS to find the exact pixel position. Theme-aware.
    On dismiss, triggers the onboarding dialog after a short delay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._positioned = False
        self._setup_ui()

        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._check_panel_visible)
        self._poll_timer.start(250)

        if parent:
            parent.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched == self.parent() and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            QTimer.singleShot(50, self._locate_icon)
        return super().eventFilter(watched, event)

    def _setup_ui(self):
        from .theme_manager import ThemeManager
        c = ThemeManager.get_palette()
        is_dark = ThemeManager.is_night_mode()

        bg = "#1c1c1e" if is_dark else "#ffffff"
        text_primary = "#ffffff" if is_dark else "#1c1c1e"
        text_secondary = "rgba(255,255,255,0.6)" if is_dark else "rgba(0,0,0,0.5)"
        border = "rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.08)"
        shadow_color = QColor(0, 0, 0, 180) if is_dark else QColor(0, 0, 0, 60)
        arrow_color = bg

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 12)
        layout.setSpacing(0)

        # Triangle arrow pointing up
        arrow = QLabel("\u25B2")
        arrow.setFixedHeight(14)
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setStyleSheet(f"color: {bg}; font-size: 16px; background: transparent;")
        layout.addWidget(arrow)

        # Card
        card = QWidget()
        card.setObjectName("bookTooltip")
        card.setStyleSheet(f"""
            QWidget#bookTooltip {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 18)
        cl.setSpacing(6)

        title = QLabel("Click the book icon")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {text_primary}; font-size: 14px; font-weight: 600; background: transparent; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;")
        cl.addWidget(title)

        sub = QLabel("to open your AI panel")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {text_secondary}; font-size: 13px; font-weight: 400; background: transparent; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif;")
        cl.addWidget(sub)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(36)
        shadow.setColor(shadow_color)
        shadow.setOffset(0, 8)
        card.setGraphicsEffect(shadow)

        layout.addWidget(card)
        self.setFixedWidth(220)
        self.adjustSize()

    def show_near_toolbar(self):
        self._locate_icon()

    def _locate_icon(self):
        if not mw or not mw.toolbar or not mw.toolbar.web:
            return
        js = """
        (function() {
            var link = document.querySelector('a[title="AI Side Panel"]');
            if (link) {
                var rect = link.getBoundingClientRect();
                return JSON.stringify({x: rect.left, y: rect.top, w: rect.width, h: rect.height});
            }
            return null;
        })();
        """
        mw.toolbar.web.page().runJavaScript(js, self._on_icon_pos)

    def _on_icon_pos(self, result):
        import json
        if not result:
            QTimer.singleShot(500, self._locate_icon)
            return
        try:
            rect = json.loads(result)
        except Exception:
            return

        toolbar_web = mw.toolbar.web
        icon_center_x = rect["x"] + rect["w"] / 2
        icon_bottom_y = rect["y"] + rect["h"]

        try:
            from PyQt6.QtCore import QPointF
            global_pos = toolbar_web.mapToGlobal(QPointF(icon_center_x, icon_bottom_y)).toPoint()
        except (ImportError, TypeError):
            from PyQt5.QtCore import QPoint
            global_pos = toolbar_web.mapToGlobal(QPoint(int(icon_center_x), int(icon_bottom_y)))

        x = global_pos.x() - self.width() // 2
        y = global_pos.y() + 4
        self.move(x, y)

        if not self._positioned:
            self._positioned = True
            self.show()
            self.raise_()

    def _check_panel_visible(self):
        global dock_widget
        if dock_widget and dock_widget.isVisible():
            self._poll_timer.stop()
            self._dismiss()

    def _dismiss(self):
        try:
            config = mw.addonManager.getConfig(ADDON_NAME) or {}
            config["book_icon_tutorial_done"] = True
            mw.addonManager.writeConfig(ADDON_NAME, config)
        except Exception as e:
            print(f"AI Panel: Error saving book icon flag: {e}")
        self.hide()
        self.deleteLater()

        # After a short delay, show the onboarding dialog
        QTimer.singleShot(600, _show_onboarding_dialog)


def _show_onboarding_dialog():
    """Show the centered onboarding dialog over the main window."""
    config = mw.addonManager.getConfig(ADDON_NAME) or {}
    if config.get("onboarding_completed", False):
        return
    # Mark onboarding done now (panel is already loaded)
    config["onboarding_completed"] = True
    mw.addonManager.writeConfig(ADDON_NAME, config)
    try:
        from .analytics import track_onboarding_completed
        track_onboarding_completed()
    except Exception:
        pass

    dialog = OnboardingDialog(mw)
    dialog.show_animated()
    mw._onboarding_dialog = dialog  # prevent GC


def ensure_platform_defaults():
    """
    Ensure quick_actions have platform-appropriate defaults.
    On Mac: Meta (⌘) + F/R
    On Windows/Linux: Control + F/R
    """
    config = mw.addonManager.getConfig(ADDON_NAME) or {}

    # Check if quick_actions needs platform-specific defaults
    quick_actions = config.get("quick_actions", {})
    needs_update = False

    # If no quick_actions config exists, or it's using the wrong modifier for this platform
    if not quick_actions:
        needs_update = True
    else:
        # Check if the modifiers match the platform
        add_keys = quick_actions.get("add_to_chat", {}).get("keys", [])
        if IS_MAC and "Control" in add_keys and "Meta" not in add_keys:
            # Mac but using Control - switch to Meta
            needs_update = True
        elif not IS_MAC and "Meta" in add_keys and "Control" not in add_keys:
            # Windows/Linux but using Meta - switch to Control
            needs_update = True

    if needs_update:
        if IS_MAC:
            config["quick_actions"] = {
                "add_to_chat": {"keys": ["Meta", "F"]},
                "ask_question": {"keys": ["Meta", "R"]}
            }
        else:
            config["quick_actions"] = {
                "add_to_chat": {"keys": ["Control", "F"]},
                "ask_question": {"keys": ["Control", "R"]}
            }
        mw.addonManager.writeConfig(ADDON_NAME, config)
        print(f"OpenEvidence: Set platform-appropriate quick action defaults for {'Mac' if IS_MAC else 'Windows/Linux'}")


def create_dock_widget():
    """Create the dock widget for OpenEvidence panel and preload content"""
    global dock_widget

    if dock_widget is None:
        # Create the dock widget
        dock_widget = QDockWidget("AI Side Panel", mw)
        dock_widget.setObjectName("AIPanelDock")

        # Always create the real panel — onboarding is now a separate dialog
        panel = OpenEvidencePanel()
        dock_widget.setWidget(panel)

        # Create and set custom title bar
        custom_title = CustomTitleBar(dock_widget)
        dock_widget.setTitleBarWidget(custom_title)

        # Get config for width
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        panel_width = config.get("width", 500)

        # Set initial size
        dock_widget.setMinimumWidth(300)
        dock_widget.resize(panel_width, mw.height())

        # Add the dock widget to the right side of the main window
        mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)

        # Hide by default - but the web content is already loading in the background!
        dock_widget.hide()

        # Store reference to prevent garbage collection
        mw.openevidence_dock = dock_widget

    return dock_widget


def toggle_panel():
    """Toggle the OpenEvidence dock widget visibility"""
    global dock_widget

    if dock_widget is None:
        create_dock_widget()

    if dock_widget.isVisible():
        dock_widget.hide()
    else:
        # If the dock is floating, dock it back to the right side
        if dock_widget.isFloating():
            dock_widget.setFloating(False)
            mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)

        dock_widget.show()
        dock_widget.raise_()


def on_webview_did_receive_js_message(handled, message, context):
    """Handle pycmd messages from toolbar and highlight bubble"""
    if message == "openevidence":
        toggle_panel()
        return (True, None)

    # Handle highlight bubble messages
    if message.startswith("openevidence:add_context:"):
        # Extract the selected text
        selected_text = message.replace("openevidence:add_context:", "", 1)
        try:
            from urllib.parse import unquote
            selected_text = unquote(selected_text)
        except:
            pass
        handle_add_context(selected_text)
        return (True, None)

    if message.startswith("openevidence:ask_query:"):
        # Extract query and context
        data = message.replace("openevidence:ask_query:", "", 1)
        try:
            from urllib.parse import unquote
            parts = data.split("|", 1)
            if len(parts) == 2:
                query = unquote(parts[0])
                context = unquote(parts[1])
                handle_ask_query(query, context)
        except:
            pass
        return (True, None)

    return handled


def store_current_card_text(card):
    """Store the current card text globally for keybinding access from OpenEvidence panel"""
    global current_card_question, current_card_answer, is_showing_answer, dock_widget

    try:
        # Always get both question and answer
        question_html = card.question()
        answer_html = card.answer()

        # Clean the question
        current_card_question = clean_html_text(question_html)

        # For answer, we need to extract just the back content
        # In Anki, answer_html includes the question, so we need to get only the back part
        full_answer_text = clean_html_text(answer_html)

        # Remove the question portion from the answer to get just the back
        # This handles cases where the answer includes the question
        if current_card_question and current_card_question in full_answer_text:
            # Find where the question ends in the answer and take everything after
            question_end = full_answer_text.find(current_card_question) + len(current_card_question)
            current_card_answer = full_answer_text[question_end:].strip()
        else:
            # If we can't find the question in the answer, just use the full answer
            current_card_answer = full_answer_text

        # Check which side is showing
        if mw.reviewer and mw.reviewer.state == "answer":
            is_showing_answer = True
        else:
            is_showing_answer = False

        # Update the JavaScript context with new card texts (using templates)
        if dock_widget and dock_widget.widget():
            panel = dock_widget.widget()
            if hasattr(panel, 'update_card_text_in_js'):
                panel.update_card_text_in_js()

    except:
        current_card_question = ""
        current_card_answer = ""
        is_showing_answer = False


def handle_add_context(selected_text):
    """Handle 'Add to Chat' action - populate AI Panel search with selected text"""
    global dock_widget

    # Track Add to Chat usage
    track_add_to_chat()

    # Make sure the panel is created and visible
    if dock_widget is None:
        create_dock_widget()

    # Show the panel if hidden
    if not dock_widget.isVisible():
        dock_widget.show()
        dock_widget.raise_()

    # Get the panel widget
    panel = dock_widget.widget()
    if panel and hasattr(panel, 'web'):
        # Ensure we're on the web view (not settings)
        if hasattr(panel, 'show_web_view'):
            panel.show_web_view()

        # Inject the text into the OpenEvidence search box
        # Priority: 1) Follow-up input (if active conversation), 2) Main search input
        js_code = """
        (function() {
            var newText = %s;
            var searchInput = null;

            // First, check for follow-up input (indicates active conversation)
            // Look for input with "follow-up" in placeholder
            var followUpInput = document.querySelector('input[placeholder*="follow-up"], input[placeholder*="Follow-up"], textarea[placeholder*="follow-up"]');

            if (followUpInput) {
                // Active conversation - use follow-up input
                searchInput = followUpInput;
                console.log('Anki: Found follow-up input, using that');
            } else {
                // No active conversation - use main search input
                searchInput = document.querySelector('input[placeholder*="medical"], input[placeholder*="question"], textarea, input[type="text"]');
                console.log('Anki: No follow-up input, using main search');
            }

            if (searchInput) {
                var existingText = searchInput.value.trim();

                // Append to existing text if present, otherwise just set new text
                var finalText = existingText ? existingText + ' ' + newText : newText;

                // Use native setter for React compatibility
                var nativeSetter = Object.getOwnPropertyDescriptor(
                    searchInput.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype,
                    'value'
                ).set;
                nativeSetter.call(searchInput, finalText);

                // Dispatch events
                searchInput.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, inputType: 'insertText', data: finalText }));
                searchInput.dispatchEvent(new Event('change', { bubbles: true }));

                // Focus the input
                searchInput.focus();

                console.log('Anki: Added context to search box');
            } else {
                console.log('Anki: Could not find search input');
            }
        })();
        """ % repr(selected_text)

        panel.web.page().runJavaScript(js_code)


def handle_ask_query(query, context):
    """Handle 'Ask Question' action - format and auto-submit to AI Panel"""
    global dock_widget

    # Track Ask Question usage
    track_ask_question()

    # Make sure the panel is created and visible
    if dock_widget is None:
        create_dock_widget()

    # Show the panel if hidden
    if not dock_widget.isVisible():
        dock_widget.show()
        dock_widget.raise_()

    # Get the panel widget
    panel = dock_widget.widget()
    if panel and hasattr(panel, 'web'):
        # Ensure we're on the web view (not settings)
        if hasattr(panel, 'show_web_view'):
            panel.show_web_view()

        # Format the message with query and context
        formatted_message = f"{query}\n\nContext:\n{context}"

        # Inject the formatted message and trigger submit
        js_code = """
        (function() {
            var searchInput = document.querySelector('input[placeholder*="medical"], input[placeholder*="question"], textarea, input[type="text"]');
            if (searchInput) {
                var text = %s;

                // Use native setter for React compatibility
                var nativeSetter = Object.getOwnPropertyDescriptor(
                    searchInput.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype,
                    'value'
                ).set;
                nativeSetter.call(searchInput, text);

                // Dispatch events
                searchInput.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, inputType: 'insertText', data: text }));
                searchInput.dispatchEvent(new Event('change', { bubbles: true }));

                // Focus the input
                searchInput.focus();

                // Try to find and click the submit button after a short delay
                setTimeout(function() {
                    // Look for common submit button patterns
                    var submitButton = document.querySelector('button[type="submit"]') ||
                                     document.querySelector('button:has(svg)') ||
                                     searchInput.closest('form')?.querySelector('button');

                    if (submitButton) {
                        submitButton.click();
                        console.log('Anki: Auto-submitted query');
                    } else {
                        // Try simulating Enter key press
                        var enterEvent = new KeyboardEvent('keydown', {
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            which: 13,
                            bubbles: true,
                            cancelable: true
                        });
                        searchInput.dispatchEvent(enterEvent);
                        console.log('Anki: Simulated Enter key');
                    }
                }, 100);

                console.log('Anki: Added query with context to search box');
            } else {
                console.log('Anki: Could not find search input');
            }
        })();
        """ % repr(formatted_message)

        panel.web.page().runJavaScript(js_code)


def add_toolbar_button(links, toolbar):
    """Add OpenEvidence button to the top toolbar"""
    # Create open book SVG icon (matching Anki's icon size and style)
    open_book_icon = """
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -0.2em;">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
</svg>
"""

    # Add AI Side Panel panel button
    links.append(
        f'<a class="hitem" href="#" onclick="pycmd(\'openevidence\'); return false;" title="AI Side Panel">{open_book_icon}</a>'
    )


def preload_panel():
    """Preload panel after a short delay to avoid competing with Anki startup"""
    print(f"{ADDON_NAME}: Starting preload_panel...")

    # Initialize analytics on first run (returns True if fresh install)
    is_fresh_install = False
    try:
        is_fresh_install = init_analytics()
    except Exception as e:
        print(f"{ADDON_NAME}: Error in init_analytics: {e}")

    # Ensure platform-appropriate defaults are set
    try:
        ensure_platform_defaults()
    except Exception as e:
        print(f"{ADDON_NAME}: Error in ensure_platform_defaults: {e}")

    # Try to send analytics once per day (non-blocking)
    try:
        try_send_daily_analytics()
    except Exception as e:
        print(f"{ADDON_NAME}: Error in try_send_daily_analytics: {e}")

    # Track that Anki was opened (skip if fresh install, since init_analytics already counted it)
    if not is_fresh_install:
        try:
            track_anki_open()
            print(f"{ADDON_NAME}: Tracked Anki open")
        except Exception as e:
            print(f"{ADDON_NAME}: Error in track_anki_open: {e}")

    # Start hourly periodic check for analytics
    # This catches users who leave Anki open for multiple days
    try:
        start_periodic_analytics_check()
    except Exception as e:
        print(f"{ADDON_NAME}: Error starting periodic check: {e}")

    # Wait 500ms after Anki finishes initializing to start preloading
    # This ensures Anki's UI is responsive while OpenEvidence loads in background
    from aqt.qt import QTimer
    QTimer.singleShot(500, create_dock_widget)

    # On first install, show the book icon overlay to guide user
    if is_fresh_install:
        def _show_book_overlay():
            global _book_icon_overlay
            config = mw.addonManager.getConfig(ADDON_NAME) or {}
            if not config.get("book_icon_tutorial_done", False):
                _book_icon_overlay = BookIconOverlay(mw)
                _book_icon_overlay.show_near_toolbar()
        QTimer.singleShot(2000, _show_book_overlay)


# Global timer for periodic analytics check
_analytics_timer = None

def start_periodic_analytics_check():
    """Start a timer that checks every hour if we need to send analytics."""
    global _analytics_timer
    from aqt.qt import QTimer

    _analytics_timer = QTimer()
    _analytics_timer.timeout.connect(try_send_daily_analytics)
    # Check every hour (3600000 ms) - very lightweight, just a date comparison
    _analytics_timer.start(3600000)


# Hook registration
gui_hooks.webview_did_receive_js_message.append(on_webview_did_receive_js_message)
gui_hooks.top_toolbar_did_init_links.append(add_toolbar_button)
# Use delayed preloading for better performance
gui_hooks.main_window_did_init.append(preload_panel)
gui_hooks.reviewer_did_show_question.append(store_current_card_text)
gui_hooks.reviewer_did_show_answer.append(store_current_card_text)
# Set up highlight bubble hooks for reviewer
setup_highlight_hooks()
