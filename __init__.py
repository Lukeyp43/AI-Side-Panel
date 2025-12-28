import aqt
from aqt import mw, gui_hooks
from aqt.qt import *

from .panel import CustomTitleBar, OpenEvidencePanel, OnboardingWidget
from .utils import clean_html_text
from .reviewer_highlight import setup_highlight_hooks

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
        tutorial_complete = config.get("tutorial_completed", False)

        # Create the appropriate widget
        if onboarding_complete:
            panel = OpenEvidencePanel()
            # The panel will automatically start loading OpenEvidence in the background

            # If onboarding is done but tutorial isn't, start tutorial when panel opens
            if not tutorial_complete:
                from aqt.qt import QTimer
                QTimer.singleShot(1000, lambda: start_tutorial_if_panel_visible())
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


def start_tutorial_if_panel_visible():
    """Start tutorial only if panel is visible"""
    global dock_widget
    if dock_widget and dock_widget.isVisible():
        from .tutorial_accordion import show_tutorial_accordion
        show_tutorial_accordion()


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

        # Notify tutorial that panel was opened
        try:
            from .tutorial import tutorial_event
            tutorial_event("panel_opened")
        except:
            pass


def on_webview_did_receive_js_message(handled, message, context):
    """Handle pycmd messages from toolbar and highlight bubble"""
    if message == "openevidence":
        toggle_panel()
        return (True, None)

    # Handle tutorial event messages
    if message.startswith("tutorial:"):
        event_name = message.replace("tutorial:", "", 1)
        try:
            from .tutorial import tutorial_event
            tutorial_event(event_name)
        except:
            pass
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

        # Notify tutorial that text was highlighted
        try:
            from .tutorial import tutorial_event
            tutorial_event("text_highlighted")
        except:
            pass

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
    """Handle 'Add to Chat' action - populate OpenEvidence search with selected text"""
    global dock_widget

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
        js_code = """
        (function() {
            var searchInput = document.querySelector('input[placeholder*="medical"], input[placeholder*="question"], textarea, input[type="text"]');
            if (searchInput) {
                var newText = %s;
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
    """Handle 'Ask Question' action - format and auto-submit to OpenEvidence"""
    global dock_widget

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
# Set up highlight bubble hooks for reviewer
setup_highlight_hooks()
