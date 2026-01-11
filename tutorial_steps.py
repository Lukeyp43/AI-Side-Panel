"""
Tutorial Steps - Definition of tutorial sequence

This module defines the complete tutorial flow as a sequence of steps,
each with a target, content, and progression trigger.
"""

from dataclasses import dataclass
from typing import Optional, Callable, Any
from PyQt6.QtCore import QRect, QPoint

from .tutorial_helpers import (
    get_toolbar_icon_rect_async,
    get_reviewer_card_rect,
    get_gear_button_rect,
    get_chat_input_rect_async,
)


@dataclass
class TutorialStep:
    """
    Definition of a single tutorial step.

    Attributes:
        step_id: Unique identifier for this step
        target_type: Type of target ("widget", "coordinates", "html", "none")
        target_ref: Reference to get target location (callable or tuple)
        title: Main message to display
        subtext: Optional secondary message
        advance_on_event: Event name that advances to next step (None = manual button)
        action_button: Text for manual advance button (e.g., "Next", "Finish")
    """
    step_id: str
    target_type: str  # "widget", "coordinates", "html", "none"
    target_ref: Optional[Any]  # Callable returning QRect/QPoint, or tuple for HTML
    title: str
    subtext: Optional[str] = None
    advance_on_event: Optional[str] = None
    action_button: Optional[str] = None


# Define the complete tutorial sequence
TUTORIAL_STEPS = [
    # ===== SECTION 1: SETUP =====
    
    # Step 1: Click toolbar book icon to toggle panel
    TutorialStep(
        step_id="toggle_panel",
        target_type="html",
        target_ref=("toolbar", "openevidence_button"),
        title="Click the book icon to toggle the sidebar.",
        subtext="Clicking it opens or closes the sidebar.",
        advance_on_event="panel_toggled",
        action_button=None
    ),

    # Step 2: Auto-create demo deck and start reviewing
    TutorialStep(
        step_id="create_demo_deck",
        target_type="none",
        target_ref=None,
        title="Let's create a practice deck to test OpenEvidence features.",
        subtext="This will add sample medical flashcards for you to try.",
        advance_on_event=None,
        action_button="Create Practice Deck"
    ),

    # ===== SECTION 2: QUICK ACTIONS - ASK QUESTION =====
    
    # Step 3: Intro to first feature
    TutorialStep(
        step_id="feature_intro",
        target_type="none",
        target_ref=None,
        title="Let's show you the main feature called Quick Actions and how to use it.",
        subtext=None,
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 4: Highlight text with Cmd held
    TutorialStep(
        step_id="highlight_text",
        target_type="coordinates",
        target_ref=get_reviewer_card_rect,
        title="Hold down ⌘ Cmd while highlighting the word \"hypertension\".",
        subtext=None,
        advance_on_event="text_highlighted",
        action_button=None
    ),

    # Step 5: Quick Action bar intro
    TutorialStep(
        step_id="quick_action_intro",
        target_type="none",
        target_ref=None,
        title="This is the Quick Action bar!",
        subtext="It appears whenever you ⌘ Cmd + highlight text.",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 6: Click Ask Question
    TutorialStep(
        step_id="ask_question",
        target_type="none",
        target_ref=None,
        title="Now click \"Ask Question\" on the Quick Action bar.",
        subtext="Type something like \"What does this mean?\" then press Enter or click the arrow.",
        advance_on_event="ask_question_submitted",
        action_button=None
    ),

    # Step 7: Ask Question success
    TutorialStep(
        step_id="ask_question_success",
        target_type="none",
        target_ref=None,
        title="Great! OpenEvidence is generating a response.",
        subtext="This is the fastest way to get answers — just highlight and ask!",
        advance_on_event=None,
        action_button="Next"
    ),

    # ===== SECTION 3: QUICK ACTIONS - ADD TO CHAT =====
    
    # Step 8: Add to Chat intro
    TutorialStep(
        step_id="add_to_chat_intro",
        target_type="none",
        target_ref=None,
        title="Now let's try \"Add to Chat\".",
        subtext="This adds your highlighted text directly to the chat input.\n\nClick Next, then ⌘ Cmd + highlight some text.",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 9: Highlight again for Add to Chat
    TutorialStep(
        step_id="highlight_for_add_to_chat",
        target_type="coordinates",
        target_ref=get_reviewer_card_rect,
        title="⌘ Cmd + highlight some text.",
        subtext="Hold ⌘ Cmd while selecting text to bring up the Quick Action bar.",
        advance_on_event="text_highlighted",
        action_button=None
    ),

    # Step 10: Click Add to Chat
    TutorialStep(
        step_id="add_to_chat",
        target_type="none",
        target_ref=None,
        title="Now click \"Add to Chat\" on the Quick Action bar.",
        subtext="Your highlighted text will be added to the chat input.",
        advance_on_event="add_to_chat",
        action_button=None
    ),

    # Step 11: Add to Chat success
    TutorialStep(
        step_id="add_to_chat_success",
        target_type="none",
        target_ref=None,
        title="Your highlighted text has been added to the chat!",
        subtext="You can now type additional context or just press Enter to send.",
        advance_on_event=None,
        action_button="Next"
    ),

    # ===== SECTION 4: KEYBOARD SHORTCUTS =====
    
    # Step 12: Shortcuts intro
    TutorialStep(
        step_id="shortcuts_intro",
        target_type="none",
        target_ref=None,
        title="There's an even faster way — keyboard shortcuts!",
        subtext="Instead of ⌘ Cmd + highlight and clicking, just highlight any text and use:\n\n⌘F = Add to Chat\n⌘R = Ask Question",
        advance_on_event=None,
        action_button="Show Me"
    ),

    # Step 13: Use shortcut
    TutorialStep(
        step_id="use_shortcut",
        target_type="coordinates",
        target_ref=get_reviewer_card_rect,
        title="Try it! Highlight any text, then press ⌘F or ⌘R.",
        subtext="⌘F = Add to Chat    ⌘R = Ask Question\n\nNo ⌘ Cmd + highlight needed — just highlight and use the shortcut.",
        advance_on_event="shortcut_used",
        action_button=None
    ),

    # ===== SECTION 5: TEMPLATES =====
    
    # Step 14: Quick Actions complete
    TutorialStep(
        step_id="quick_actions_complete",
        target_type="none",
        target_ref=None,
        title="Congrats! You've learned Quick Actions. 🎉",
        subtext="Now let's show you the other major feature: Templates.",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 15: Start new chat
    TutorialStep(
        step_id="start_new_chat",
        target_type="none",
        target_ref=None,
        title="First, let's start fresh.",
        subtext="Click the OpenEvidence logo in the top left of the sidebar to go back to the home screen.",
        advance_on_event=None,
        action_button="Done"
    ),

    # Step 16: Templates intro
    TutorialStep(
        step_id="templates_intro",
        target_type="none",
        target_ref=None,
        title="Next up: Templates",
        subtext="Templates let you send your flashcard to OpenEvidence with a simple keyboard shortcut.\n\nNo highlighting needed — just press a key combo!",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 17: Template shortcuts explained
    TutorialStep(
        step_id="template_shortcuts",
        target_type="none",
        target_ref=None,
        title="Here are the template shortcuts:",
        subtext="Ctrl+Shift+Q → Send just the front (question)\nCtrl+Shift+A → Send just the back (answer)\nCtrl+Shift+S → Send front & back (\"Explain this\")\n\n⚠️ Click inside the sidebar's text box first!",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 18: Try Ctrl+Shift+Q (front only) - FIRST
    TutorialStep(
        step_id="try_template_q",
        target_type="coordinates",
        target_ref=get_reviewer_card_rect,
        title="Click in the sidebar's text box, then press Ctrl+Shift+Q.",
        subtext="This sends only the front (question) of the card.",
        advance_on_event="shortcut_used",
        action_button=None
    ),

    # Step 19: Template Q success
    TutorialStep(
        step_id="template_q_success",
        target_type="none",
        target_ref=None,
        title="Nice! You sent just the question.",
        subtext="Clear the text in the sidebar, then let's try the answer shortcut.",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 20: Show answer
    TutorialStep(
        step_id="show_answer",
        target_type="none",
        target_ref=None,
        title="Please reveal the answer on your current card.",
        subtext="Click \"Show Answer\" below. The next shortcut (Ctrl+Shift+A) sends the back of the card, so both sides need to be visible.",
        advance_on_event="answer_shown",
        action_button=None
    ),

    # Step 21: Try Ctrl+Shift+A (back only) - SECOND
    TutorialStep(
        step_id="try_template_a",
        target_type="coordinates",
        target_ref=get_reviewer_card_rect,
        title="Click in the sidebar, then press Ctrl+Shift+A.",
        subtext="This sends only the back (answer) of the card.",
        advance_on_event="shortcut_used",
        action_button=None
    ),

    # Step 22: Template A success
    TutorialStep(
        step_id="template_a_success",
        target_type="none",
        target_ref=None,
        title="Great! You sent just the answer.",
        subtext="Clear the text in the sidebar. One more — this one sends both the question AND answer together.",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 23: Try Ctrl+Shift+S (front & back) - LAST
    TutorialStep(
        step_id="try_template_s",
        target_type="coordinates",
        target_ref=get_reviewer_card_rect,
        title="Click in the sidebar, then press Ctrl+Shift+S.",
        subtext="This sends both the question AND answer to OpenEvidence.",
        advance_on_event="shortcut_used",
        action_button=None
    ),

    # Step 24: Templates complete
    TutorialStep(
        step_id="templates_complete",
        target_type="none",
        target_ref=None,
        title="You've learned all the templates! 🎉",
        subtext="Remember: Click in the sidebar first, then:\n\nCtrl+Shift+Q = Front only\nCtrl+Shift+A = Back only\nCtrl+Shift+S = Front & Back",
        advance_on_event=None,
        action_button="Next"
    ),

    # ===== SECTION 6: SETTINGS =====

    # Step 19: Open settings
    TutorialStep(
        step_id="open_settings",
        target_type="widget",
        target_ref=get_gear_button_rect,
        title="Click the gear icon to open Settings.",
        subtext="You can customize templates and shortcuts here.",
        advance_on_event="settings_opened",
        action_button=None
    ),

    # Step 20: Settings overview
    TutorialStep(
        step_id="settings_overview",
        target_type="none",
        target_ref=None,
        title="Welcome to Settings!",
        subtext="Let's take a quick look around. You'll see two sections: Templates and Quick Actions.",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 21: Click Templates
    TutorialStep(
        step_id="click_templates",
        target_type="none",
        target_ref=None,
        title="Click on \"Templates\" to see your shortcuts.",
        subtext=None,
        advance_on_event="templates_opened",
        action_button=None
    ),

    # Step 22: Templates list overview - click edit
    TutorialStep(
        step_id="templates_list_overview",
        target_type="none",
        target_ref=None,
        title="Here are your template shortcuts.",
        subtext="Click the pencil icon on any template to edit it.",
        advance_on_event="template_edit_opened",
        action_button=None
    ),

    # Step 23: Templates edit explanation
    TutorialStep(
        step_id="templates_edit_explain",
        target_type="none",
        target_ref=None,
        title="When you edit a template, you can:",
        subtext="• Change the keyboard shortcut\n• Edit the text that gets sent to OpenEvidence\n• Delete templates you don't need",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 24: Go back to templates list
    TutorialStep(
        step_id="templates_go_back_to_list",
        target_type="none",
        target_ref=None,
        title="Click the back arrow to return to the templates list.",
        subtext=None,
        advance_on_event="settings_back_to_templates",
        action_button=None
    ),

    # Step 25: Go back to settings home
    TutorialStep(
        step_id="templates_go_back_to_home",
        target_type="none",
        target_ref=None,
        title="Click the back arrow one more time to return to Settings.",
        subtext=None,
        advance_on_event="settings_back_to_home",
        action_button=None
    ),

    # Step 25: Click Quick Actions
    TutorialStep(
        step_id="click_quick_actions",
        target_type="none",
        target_ref=None,
        title="Now click on \"Quick Actions\".",
        subtext=None,
        advance_on_event="quick_actions_opened",
        action_button=None
    ),

    # Step 26: Quick Actions overview
    TutorialStep(
        step_id="quick_actions_overview",
        target_type="none",
        target_ref=None,
        title="These are your Quick Action shortcuts.",
        subtext="Remember ⌘F (Add to Chat) and ⌘R (Ask Question)? You can change these shortcuts here if you'd like.",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 27: Go back to settings home from Quick Actions
    TutorialStep(
        step_id="quick_actions_go_back",
        target_type="none",
        target_ref=None,
        title="Click the back arrow to return to Settings.",
        subtext=None,
        advance_on_event="settings_back_to_home",
        action_button=None
    ),

    # Step 28: Go back to OpenEvidence
    TutorialStep(
        step_id="go_back_to_openevidence",
        target_type="none",
        target_ref=None,
        title="Click the back arrow one more time to return to OpenEvidence.",
        subtext=None,
        advance_on_event="panel_web_view",
        action_button=None
    ),

    # Step 29: Recommendation to sign up
    TutorialStep(
        step_id="signup_recommendation",
        target_type="none",
        target_ref=None,
        title="One last tip!",
        subtext="We recommend signing in or creating a free OpenEvidence account to save your chat history.\n\nDon't worry — we store cookies so you'll stay logged in automatically!",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 30: How to sign in
    TutorialStep(
        step_id="how_to_signin",
        target_type="none",
        target_ref=None,
        title="How to sign in:",
        subtext="Click the hamburger menu (☰) in the top right of the sidebar, then tap \"Log in\" or \"Sign up\".",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 31: Why I built this
    TutorialStep(
        step_id="why_i_built_this",
        target_type="none",
        target_ref=None,
        title="Why I built this:",
        subtext="I built this add-on to help bring AI to studying. I chose OpenEvidence because the AI is based on medical journal research, it's 100% free for medical students/MDs, and it's awesome!",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 32: Finish
    TutorialStep(
        step_id="finish",
        target_type="none",
        target_ref=None,
        title="You're all set! 🎉",
        subtext="You now know Quick Actions, Templates, and Settings. Happy studying!",
        advance_on_event=None,
        action_button="Finish"
    ),
]


def get_step_target_rect(step: TutorialStep, callback: Callable[[Optional[QRect]], None]):
    """
    Get the target rectangle for a tutorial step.

    Handles different target types:
    - "widget": Directly calls target_ref() to get QRect
    - "coordinates": Calls target_ref() to get QRect
    - "html": Asynchronously queries HTML element via JavaScript
    - "none": Returns None (center screen, no target)

    Args:
        step: The tutorial step to get target for
        callback: Function to call with QRect result (or None)
    """
    if step.target_type == "none":
        callback(None)
        return

    elif step.target_type in ["widget", "coordinates"]:
        # Directly call the target_ref function
        try:
            rect = step.target_ref()
            callback(rect)
        except Exception as e:
            print(f"Error getting target rect for step {step.step_id}: {e}")
            callback(None)

    elif step.target_type == "html":
        # Asynchronous HTML element query
        try:
            # target_ref is a tuple: (web_view_attr, selector)
            web_view_attr, selector = step.target_ref

            # Special handling for toolbar
            if web_view_attr == "toolbar":
                get_toolbar_icon_rect_async(callback)
            else:
                # Panel input box
                get_chat_input_rect_async(callback)
        except Exception as e:
            print(f"Error getting HTML target for step {step.step_id}: {e}")
            callback(None)

    else:
        # Unknown target type
        print(f"Unknown target type: {step.target_type}")
        callback(None)


def get_total_steps():
    """Get the total number of tutorial steps."""
    return len(TUTORIAL_STEPS)


def get_step_by_index(index: int) -> Optional[TutorialStep]:
    """
    Get a tutorial step by its index.

    Args:
        index: 0-based step index

    Returns:
        TutorialStep or None if index out of range
    """
    if 0 <= index < len(TUTORIAL_STEPS):
        return TUTORIAL_STEPS[index]
    return None


def get_step_by_id(step_id: str) -> Optional[TutorialStep]:
    """
    Get a tutorial step by its ID.

    Args:
        step_id: The step's unique identifier

    Returns:
        TutorialStep or None if not found
    """
    for step in TUTORIAL_STEPS:
        if step.step_id == step_id:
            return step
    return None


def find_step_index_for_event(event_name: str) -> Optional[int]:
    """
    Find the step index that advances on a specific event.

    Args:
        event_name: Event name to search for

    Returns:
        0-based step index, or None if no step uses this event
    """
    for i, step in enumerate(TUTORIAL_STEPS):
        if step.advance_on_event == event_name:
            return i
    return None
