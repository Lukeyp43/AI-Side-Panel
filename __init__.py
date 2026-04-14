import sys
import socket
from datetime import datetime
import aqt
from aqt import mw, gui_hooks
from aqt.qt import *

from .panel import CustomTitleBar, OpenEvidencePanel, OnboardingDialog
from .utils import clean_html_text
from .reviewer_highlight import setup_highlight_hooks
from .analytics import init_analytics, try_send_daily_analytics, track_anki_open
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

        sub = QLabel("to open Anki Copilot")
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
            var link = document.querySelector('a[title="Anki Copilot"]');
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
            # Onboarding = user clicked the book icon (first interaction)
            config["onboarding_completed"] = True
            mw.addonManager.writeConfig(ADDON_NAME, config)
        except Exception as e:
            print(f"AI Panel: Error saving book icon flag: {e}")

        try:
            from .analytics import track_onboarding_completed
            track_onboarding_completed()
        except Exception:
            pass

        self.hide()
        self.deleteLater()

        # After a short delay, show the onboarding dialog
        QTimer.singleShot(600, _show_onboarding_dialog)


def _show_onboarding_dialog():
    """Show the centered onboarding dialog over the main window."""
    config = mw.addonManager.getConfig(ADDON_NAME) or {}
    analytics = config.get("analytics", {})
    # Don't show again if user already completed the tutorial
    if analytics.get("tutorial_status") == "completed":
        return

    # Record when the tutorial started so we can measure duration on completion
    analytics["tutorial_start_time"] = datetime.now().isoformat()
    config["analytics"] = analytics
    mw.addonManager.writeConfig(ADDON_NAME, config)

    dialog = OnboardingDialog(mw)
    dialog.show_animated()
    mw._onboarding_dialog = dialog  # prevent GC


def create_dock_widget():
    """Create the dock widget for OpenEvidence panel and preload content"""
    global dock_widget

    if dock_widget is None:
        # Create the dock widget
        dock_widget = QDockWidget("Anki Copilot", mw)
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


def _has_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2).close()
        return True
    except OSError:
        return False


def toggle_panel():
    """Toggle the OpenEvidence dock widget visibility"""
    global dock_widget

    if dock_widget is None:
        create_dock_widget()

    if dock_widget.isVisible():
        dock_widget.hide()
    else:
        if not _has_internet():
            from aqt.utils import tooltip
            tooltip("No internet connection. Check your connection and try again.", period=3000)
            return

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

    if message == "openevidence:clear_chat":
        # User dismissed inline explain without "Continue in chat" — clear the conversation
        if dock_widget:
            panel = dock_widget.widget()
            if panel and hasattr(panel, 'web'):
                from .ai_create import _delete_latest_oe_conversation
                _delete_latest_oe_conversation(panel)
        return (True, None)

    if message == "ai_generate":
        if not _has_internet():
            from aqt.utils import tooltip
            tooltip("No internet connection. Check your connection and try again.", period=3000)
            return (True, None)
        from .analytics import is_user_logged_in
        if not is_user_logged_in():
            from .ai_create import show_login_modal
            show_login_modal()
            return (True, None)
        from .ai_generate import show_ai_generate_dialog
        show_ai_generate_dialog()
        return (True, None)

    if message == "ai_create":
        from .ai_create import show_ai_create
        if hasattr(mw, 'app'):
            from aqt.editcurrent import EditCurrent
            from aqt.addcards import AddCards
            for widget in mw.app.topLevelWidgets():
                if isinstance(widget, (AddCards, EditCurrent)) and hasattr(widget, 'editor'):
                    show_ai_create(widget.editor)
                    return (True, None)
        return (True, None)

    if message == "ai_answer":
        from .ai_create import _handle_ai_answer
        # Find the active editor
        if hasattr(mw, 'app'):
            from aqt.editcurrent import EditCurrent
            from aqt.addcards import AddCards
            for widget in mw.app.topLevelWidgets():
                if isinstance(widget, (AddCards, EditCurrent)) and hasattr(widget, 'editor'):
                    _handle_ai_answer(widget.editor)
                    return (True, None)
        return (True, None)

    # Handle opening a URL in the system browser
    if message.startswith("openurl:"):
        url = message.replace("openurl:", "", 1)
        try:
            from urllib.parse import unquote
            url = unquote(url)
            from aqt.qt import QDesktopServices, QUrl
            QDesktopServices.openUrl(QUrl(url))
        except Exception as e:
            print(f"OpenEvidence: Could not open URL: {e}")
        return (True, None)

    # Handle inline explain request
    if message.startswith("openevidence:inline_explain:"):
        text = message.replace("openevidence:inline_explain:", "", 1)
        try:
            from urllib.parse import unquote
            text = unquote(text)
        except:
            pass
        handle_inline_explain(text)
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


def handle_inline_explain(selected_text):
    """Handle inline explain — query OpenEvidence in hidden panel, extract response."""
    global dock_widget

    from .analytics import track_explain
    track_explain()

    from .review import show_review_modal_if_eligible
    show_review_modal_if_eligible()

    # Ensure panel is created and visible (React needs visible DOM to render)
    if dock_widget is None:
        create_dock_widget()

    # Always float the panel off-screen with 0 opacity so the webview stays
    # active but the user sees nothing — even if they had the panel open.
    # The cleanup on completion will re-dock it hidden.
    if dock_widget.isVisible():
        dock_widget.hide()
    dock_widget.setFloating(True)
    dock_widget.setWindowOpacity(0)
    dock_widget.move(-9999, -9999)
    dock_widget.show()

    panel = dock_widget.widget()
    if not panel or not hasattr(panel, 'web'):
        print("AI Panel: inline explain — no panel/web found")
        return

    if hasattr(panel, 'show_web_view'):
        panel.show_web_view()

    query = f"Explain this in 2 sentences or less. Do not ask a follow-up question: {selected_text}"

    # Use the exact same injection pattern as handle_ask_query (proven to work)
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
                    console.log('Anki: Inline explain — auto-submitted query');
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
                    console.log('Anki: Inline explain — simulated Enter key');
                }
            }, 100);

            console.log('Anki: Inline explain — injected query');
        } else {
            console.log('Anki: Inline explain — could not find search input');
            console.log('ANKI_INLINE_RESPONSE:ERROR_TIMEOUT');
        }
    })();
    """ % repr(query)

    panel.web.page().runJavaScript(js_code)

    # After submitting, inject JS that polls for the response and stores it in a global var.
    # Then Python polls that var using runJavaScript callbacks (no console.log length limits).
    poll_js = """
    (function() {
        window.ankiInlineResult = null;
        window.ankiInlinePartial = null;
        var initialCount = document.querySelectorAll('article.MuiBox-root').length;
        var pollCount = 0;
        var maxPolls = 120;
        var lastTextLength = -1;
        var stableCount = 0;

        function extractText(article) {
            var paragraphs = article.querySelectorAll('p');
            var html = '';

            paragraphs.forEach(function(p) {
                if (p.closest('.MuiStepper-root')) return;
                if (p.closest('.brandable--references')) return;
                if (p.closest('.MuiCollapse-hidden')) return;
                if (p.classList.contains('MuiTypography-body2')) return;

                var clone = p.cloneNode(true);
                clone.querySelectorAll('.markdown-article-citation-chip').forEach(function(c) { c.remove(); });
                clone.querySelectorAll('[aria-hidden="true"]').forEach(function(c) { c.remove(); });

                var cleaned = clone.innerHTML.trim();
                if (cleaned.length > 0) {
                    html += cleaned + '<br><br>';
                }
            });

            return html.replace(/<br><br>$/, '');
        }

        var pollInterval = setInterval(function() {
            pollCount++;
            if (pollCount > maxPolls) {
                clearInterval(pollInterval);
                window.ankiInlineResult = 'ERROR_TIMEOUT';
                return;
            }

            // Check for out-of-scope warning
            var warning = document.querySelector('.MuiAlert-standardWarning, .MuiAlert-colorWarning');
            if (warning && warning.textContent.indexOf('outside the scope') !== -1) {
                clearInterval(pollInterval);
                window.ankiInlineResult = 'OUT_OF_SCOPE';
                return;
            }

            // Check for rate limit / login popup
            var dlg = document.querySelector('[role="dialog"]');
            if (dlg) {
                var dlgText = dlg.innerText || '';
                if (dlgText.indexOf('question limit') !== -1 || dlgText.indexOf('unverified users') !== -1 || dlgText.indexOf('Sign Up') !== -1) {
                    clearInterval(pollInterval);
                    window.ankiInlineResult = 'NEEDS_LOGIN';
                    return;
                }
            }

            var articles = document.querySelectorAll('article.MuiBox-root');
            if (articles.length <= initialCount) return;

            var lastArticle = articles[articles.length - 1];
            var text = extractText(lastArticle);
            if (text.length === 0) return;

            // Always expose partial text for streaming
            window.ankiInlinePartial = text;

            // Wait for text to stabilize — same length for 3 consecutive checks (1.5s)
            if (text.length === lastTextLength) {
                stableCount++;
                if (stableCount >= 3) {
                    clearInterval(pollInterval);
                    window.ankiInlineResult = text;
                }
            } else {
                lastTextLength = text.length;
                stableCount = 0;
            }
        }, 300);
    })();
    """

    from aqt.qt import QTimer

    # Start the JS-side polling after a delay
    QTimer.singleShot(1000, lambda: panel.web.page().runJavaScript(poll_js))

    # Python-side: poll the JS variable and stream partial updates to reviewer
    def _start_python_poll():
        _py_poll_count = [0]
        _last_sent = [None]  # Track last sent text to avoid duplicates

        def _check_result():
            _py_poll_count[0] += 1
            if _py_poll_count[0] > 70:  # 35 seconds max
                _py_timer.stop()
                # Dismiss the explain bubble on timeout
                if mw.reviewer and hasattr(mw.reviewer, 'web') and mw.reviewer.web:
                    mw.reviewer.web.eval("if(window.ankiDismissExplain) window.ankiDismissExplain();")
                _cleanup_panel()
                return

            panel.web.page().runJavaScript(
                "[window.ankiInlinePartial, window.ankiInlineResult]",
                _on_poll_result
            )

        def _on_poll_result(result):
            if not result or not isinstance(result, list):
                return
            partial = result[0] if len(result) > 0 else None
            final = result[1] if len(result) > 1 else None

            if final and isinstance(final, str):
                _py_timer.stop()
                if final == 'NEEDS_LOGIN':
                    _cleanup_panel(clear_chat=True)
                    # Dismiss the explain bubble/spinner
                    if mw.reviewer and hasattr(mw.reviewer, 'web') and mw.reviewer.web:
                        mw.reviewer.web.eval("if(window.ankiDismissExplain) window.ankiDismissExplain();")
                    from .ai_create import show_login_modal
                    show_login_modal()
                    return
                _send_to_reviewer(final, True)
                _cleanup_panel(clear_chat=False)
            elif partial and isinstance(partial, str) and partial != _last_sent[0]:
                _last_sent[0] = partial
                _send_to_reviewer(partial, False)

        def _send_to_reviewer(text, is_done):
            import json
            escaped = json.dumps(text)
            done_str = 'true' if is_done else 'false'
            if mw.reviewer and hasattr(mw.reviewer, 'web') and mw.reviewer.web:
                mw.reviewer.web.eval(
                    f"if(window.ankiStreamExplainText) window.ankiStreamExplainText({escaped}, {done_str});"
                )

        def _cleanup_panel(clear_chat=True):
            if dock_widget:
                if clear_chat:
                    p = dock_widget.widget()
                    if p and hasattr(p, 'web'):
                        from .ai_create import _delete_latest_oe_conversation
                        _delete_latest_oe_conversation(p)
                dock_widget.hide()
                dock_widget.setWindowOpacity(1)
                dock_widget.setFloating(False)
                mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)

        _py_timer = QTimer()
        _py_timer.timeout.connect(_check_result)
        _py_timer.start(300)
        # Keep reference
        mw._inline_explain_timer = _py_timer

    QTimer.singleShot(1500, _start_python_poll)


def add_deck_browser_button():
    """Add AI Generate button to the deck browser bottom bar by monkey-patching"""
    from aqt.deckbrowser import DeckBrowser

    original_drawLinks = DeckBrowser._drawButtons

    def patched_drawButtons(self):
        original_drawLinks(self)
        # Inject our button into the bottom bar via JS
        js = """
        (function() {
            if (document.getElementById('ai-generate-btn')) return;
            var buttons = document.querySelectorAll('button');
            var importBtn = null;
            for (var i = 0; i < buttons.length; i++) {
                if (buttons[i].textContent.trim() === 'Import File') {
                    importBtn = buttons[i];
                    break;
                }
            }
            var btn = document.createElement('button');
            btn.id = 'ai-generate-btn';
            btn.textContent = 'AI Generate';
            btn.onclick = function() { pycmd('ai_generate'); return false; };
            if (importBtn) {
                importBtn.parentNode.insertBefore(btn, importBtn);
            } else {
                var lastBtn = buttons[buttons.length - 1];
                if (lastBtn) lastBtn.parentNode.insertBefore(btn, lastBtn.nextSibling);
            }
        })();
        """
        self.bottom.web.eval(js)

    DeckBrowser._drawButtons = patched_drawButtons


def add_toolbar_button(links, toolbar):
    """Add OpenEvidence button to the top toolbar"""
    # Create open book SVG icon (matching Anki's icon size and style)
    open_book_icon = """
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -0.2em;">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
</svg>
"""

    # Add Anki Copilot panel button
    links.append(
        f'<a class="hitem" href="#" onclick="pycmd(\'openevidence\'); return false;" title="Anki Copilot">{open_book_icon}</a>'
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

    # Migration: existing users who completed onboarding before tutorial tracking
    # was added have onboarding_completed=True but tutorial_status=None.
    # Backfill tutorial_status so the onboarding dialog doesn't re-show for them.
    # Only applies to true legacy users (no tutorial_start_time — new code always sets it).
    try:
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        analytics = config.get("analytics", {})
        if (config.get("onboarding_completed", False)
                and analytics.get("tutorial_status") is None
                and analytics.get("tutorial_start_time") is None):
            analytics["tutorial_status"] = "completed"
            config["analytics"] = analytics
            mw.addonManager.writeConfig(ADDON_NAME, config)
    except Exception:
        pass

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
    # Skip preload if no internet to avoid unnecessary network errors
    from aqt.qt import QTimer
    def _maybe_preload():
        if _has_internet():
            create_dock_widget()
    QTimer.singleShot(500, _maybe_preload)

    # On first install, show the book icon overlay to guide user
    if is_fresh_install:
        def _show_book_overlay():
            global _book_icon_overlay
            config = mw.addonManager.getConfig(ADDON_NAME) or {}
            if not config.get("book_icon_tutorial_done", False):
                _book_icon_overlay = BookIconOverlay(mw)
                _book_icon_overlay.show_near_toolbar()
        QTimer.singleShot(2000, _show_book_overlay)
    else:
        def _show_returning_user_dialog():
            config = mw.addonManager.getConfig(ADDON_NAME) or {}
            analytics = config.get("analytics", {})
            tutorial = analytics.get("tutorial_status")

            if tutorial == "completed" and not analytics.get("update_v2_shown", False):
                # Completed tutorial before — show update dialog for new features
                dialog = OnboardingDialog(mw, is_update=True)
                dialog.show_animated()
                mw._update_dialog = dialog
            elif tutorial in ("skipped_midway", None) and config.get("onboarding_completed", False):
                # Quit mid-tutorial last time (or force-quit before closeEvent) —
                # re-show the normal tutorial
                _show_onboarding_dialog()

        QTimer.singleShot(2000, _show_returning_user_dialog)


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
add_deck_browser_button()  # Monkey-patch deck browser bottom bar
# Use delayed preloading for better performance
gui_hooks.main_window_did_init.append(preload_panel)
gui_hooks.reviewer_did_show_question.append(store_current_card_text)
gui_hooks.reviewer_did_show_answer.append(store_current_card_text)
# Set up highlight bubble hooks for reviewer
setup_highlight_hooks()
# Send analytics when Anki closes — always send (not gated by once-per-day)
# since this is the last chance to capture this session's data
from .analytics import send_analytics_background as _send_analytics_on_close
gui_hooks.profile_will_close.append(lambda: _send_analytics_on_close())
# Add AI Create button to editor toolbar + AI Answer to Back field
from .ai_create import setup_editor_button, on_editor_load_note
gui_hooks.editor_did_init_buttons.append(setup_editor_button)
gui_hooks.editor_did_load_note.append(on_editor_load_note)
