import aqt
from aqt import mw, gui_hooks
from aqt.qt import *

from .panel import CustomTitleBar, OpenEvidencePanel, OnboardingWidget
from .utils import clean_html_text

# Global references
dock_widget = None
current_card_question = ""
current_card_answer = ""
is_showing_answer = False


def create_dock_widget():
    """Create the dock widget for OpenEvidence panel and preload content"""
    global dock_widget

    if dock_widget is None:
        # Create the dock widget
        dock_widget = QDockWidget("OpenEvidence", mw)
        dock_widget.setObjectName("OpenEvidenceDock")

        # Check if onboarding is complete
        config = mw.addonManager.getConfig(__name__) or {}
        onboarding_complete = config.get("onboarding_completed", False)

        # Create the appropriate widget
        if onboarding_complete:
            panel = OpenEvidencePanel()
            # The panel will automatically start loading OpenEvidence in the background
        else:
            panel = OnboardingWidget()

        dock_widget.setWidget(panel)

        # Create and set custom title bar
        custom_title = CustomTitleBar(dock_widget)
        dock_widget.setTitleBarWidget(custom_title)

        # Get config for width
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
    """Handle pycmd messages from toolbar"""
    if message == "openevidence":
        toggle_panel()
        return (True, None)
    return handled


def store_current_card_text(card):
    """Store the current card text globally for keybinding access from OpenEvidence panel"""
    global current_card_question, current_card_answer, is_showing_answer, dock_widget

    try:
        # Always get both question and answer
        question_html = card.question()
        answer_html = card.answer()

        # Clean both
        current_card_question = clean_html_text(question_html)
        current_card_answer = clean_html_text(answer_html)

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


def add_toolbar_button(links, toolbar):
    """Add OpenEvidence button to the top toolbar"""
    # Create open book SVG icon (matching Anki's icon size and style)
    open_book_icon = """
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -0.2em;">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
</svg>
"""

    # Add the OpenEvidence panel button
    links.append(
        f'<a class="hitem" href="#" onclick="pycmd(\'openevidence\'); return false;" title="OpenEvidence">{open_book_icon}</a>'
    )


def preload_panel():
    """Preload panel after a short delay to avoid competing with Anki startup"""
    # Wait 500ms after Anki finishes initializing to start preloading
    # This ensures Anki's UI is responsive while OpenEvidence loads in background
    from aqt.qt import QTimer
    QTimer.singleShot(500, create_dock_widget)


# Hook registration
gui_hooks.webview_did_receive_js_message.append(on_webview_did_receive_js_message)
gui_hooks.top_toolbar_did_init_links.append(add_toolbar_button)
# Use delayed preloading for better performance
gui_hooks.main_window_did_init.append(preload_panel)
gui_hooks.reviewer_did_show_question.append(store_current_card_text)
gui_hooks.reviewer_did_show_answer.append(store_current_card_text)
