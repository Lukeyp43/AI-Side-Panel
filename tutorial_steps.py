"""
Tutorial Steps - Definition of tutorial sequence

This module defines the complete tutorial flow as a sequence of steps,
each with a target, content, and progression trigger.
"""

import sys
from dataclasses import dataclass
from typing import Optional, Callable, Any
from PyQt6.QtCore import QRect, QPoint
from aqt import mw

from .tutorial_helpers import (
    get_toolbar_icon_rect_async,
    get_reviewer_card_rect,
    get_gear_button_rect,
    get_chat_input_rect_async,
)

# Addon name for config
ADDON_NAME = "the_ai_panel"

# Platform detection
IS_MAC = sys.platform == "darwin"


def format_keys(keys: list) -> str:
    """Format a list of keys into a readable shortcut string.

    Mac: Uses ⌘ Cmd for Meta (Command key), ^ Ctrl for Control
    Windows/Linux: Uses Ctrl for both Meta and Control
    Format: "symbol space word" for each modifier (e.g., "⌘ Cmd + Q")
    """
    if IS_MAC:
        key_symbols = {
            "Control": "^\u00A0Ctrl",
            "Shift": "⇧\u00A0Shift",
            "Alt": "⌥\u00A0Alt",
            "Meta": "⌘\u00A0Cmd",  # Command key on Mac (symbol + name)
        }
    else:
        # Windows/Linux
        key_symbols = {
            "Control": "Ctrl",
            "Shift": "Shift",
            "Alt": "Alt",
            "Meta": "Ctrl",  # On Windows, Meta maps to Ctrl for display
        }

    formatted = []
    for key in keys:
        if key in key_symbols:
            formatted.append(key_symbols[key])
        else:
            formatted.append(key)

    return "\u00A0+\u00A0".join(formatted)


def get_quick_action_shortcut(action_name: str) -> str:
    """Get the formatted shortcut for a quick action (add_to_chat or ask_question)"""
    try:
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        quick_actions = config.get("quick_actions", {})
        if action_name in quick_actions:
            keys = quick_actions[action_name].get("keys", [])
            return format_keys(keys)
    except:
        pass
    # Platform-appropriate defaults
    if IS_MAC:
        if action_name == "add_to_chat":
            return "⌘\u00A0Cmd\u00A0+\u00A0F"
        elif action_name == "ask_question":
            return "⌘\u00A0Cmd\u00A0+\u00A0R"
    else:
        if action_name == "add_to_chat":
            return "Ctrl\u00A0+\u00A0F"
        elif action_name == "ask_question":
            return "Ctrl\u00A0+\u00A0R"
    return ""


def get_template_shortcut(template_name: str) -> str:
    """Get the formatted shortcut for a template by name"""
    try:
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        keybindings = config.get("keybindings", [])
        for kb in keybindings:
            if kb.get("name") == template_name:
                keys = kb.get("keys", [])
                return format_keys(keys)
    except:
        pass
    # Platform-appropriate defaults
    if IS_MAC:
        defaults = {
            "Standard Explain": "^\u00A0Ctrl\u00A0+\u00A0⇧\u00A0Shift\u00A0+\u00A0S",
            "Front/Back": "^\u00A0Ctrl\u00A0+\u00A0⇧\u00A0Shift\u00A0+\u00A0Q",
            "Back Only": "^\u00A0Ctrl\u00A0+\u00A0⇧\u00A0Shift\u00A0+\u00A0A",
        }
    else:
        defaults = {
            "Standard Explain": "Ctrl\u00A0+\u00A0Shift\u00A0+\u00A0S",
            "Front/Back": "Ctrl\u00A0+\u00A0Shift\u00A0+\u00A0Q",
            "Back Only": "Ctrl\u00A0+\u00A0Shift\u00A0+\u00A0A",
        }
    return defaults.get(template_name, "")


def get_shortcut_q() -> str:
    """Get the Front/Back (Q) template shortcut"""
    return get_template_shortcut("Front/Back")


def get_shortcut_a() -> str:
    """Get the Back Only (A) template shortcut"""
    return get_template_shortcut("Back Only")


def get_shortcut_s() -> str:
    """Get the Standard Explain (S) template shortcut"""
    return get_template_shortcut("Standard Explain")


def get_shortcut_add_to_chat() -> str:
    """Get the Add to Chat quick action shortcut"""
    return get_quick_action_shortcut("add_to_chat")


def get_shortcut_ask_question() -> str:
    """Get the Ask Question quick action shortcut"""
    return get_quick_action_shortcut("ask_question")


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


def get_tutorial_steps():
    """
    Generate tutorial steps with dynamic shortcuts from user config.
    This is called when the tutorial starts so shortcuts reflect current settings.
    """
    # Get current shortcuts from config
    shortcut_q = get_shortcut_q()
    shortcut_a = get_shortcut_a()
    shortcut_s = get_shortcut_s()
    shortcut_add = get_shortcut_add_to_chat()
    shortcut_ask = get_shortcut_ask_question()
    
    return [
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
        title="Let's create a practice deck to test The AI Panel features.",
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
        title="Great! The AI Panel is generating a response.",
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
        subtext="This adds your highlighted text directly to the chat input.",
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
        subtext=f"Instead of ⌘ Cmd + highlight and clicking, just highlight any text and use:\n\n{shortcut_add} → Add to Chat\n{shortcut_ask} → Ask Question",
        advance_on_event=None,
        action_button="Show Me"
    ),

    # Step 13: Use shortcut
    TutorialStep(
        step_id="use_shortcut",
        target_type="coordinates",
        target_ref=get_reviewer_card_rect,
        title=f"Try it! Highlight any text, then press {shortcut_add}\u00A0or\u00A0{shortcut_ask}.",
        subtext=f"{shortcut_add} → Add to Chat\n{shortcut_ask} → Ask Question\n\nNo ⌘ Cmd + highlight needed — just highlight and use the shortcut.",
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
        subtext="Click The AI Panel logo in the top left of the sidebar to go back to the home screen.",
        advance_on_event=None,
        action_button="Done"
    ),

    # Step 16: Templates intro
    TutorialStep(
        step_id="templates_intro",
        target_type="none",
        target_ref=None,
        title="Next up: Templates",
        subtext="Templates let you send your flashcard to The AI Panel with a simple keyboard shortcut.\n\nNo highlighting needed — just press a key combo!",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 17: Template shortcuts explained
    TutorialStep(
        step_id="template_shortcuts",
        target_type="none",
        target_ref=None,
        title="Here are the template shortcuts:",
        subtext=f"{shortcut_q} → Send the front (question)\n{shortcut_a} → Send the back (answer)\n{shortcut_s} → Send front & back\n\n⚠️ Click inside the sidebar's text box first!",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 18: Try template Q (front only) - FIRST
    TutorialStep(
        step_id="try_template_q",
        target_type="coordinates",
        target_ref=get_reviewer_card_rect,
        title=f"Click in the sidebar's text box, then press {shortcut_q}.",
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
        subtext="Now let's clear the sidebar and try the next shortcut.",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 20: Clear chat after Q
    TutorialStep(
        step_id="clear_chat_after_q",
        target_type="none",
        target_ref=None,
        title="Clear the sidebar's text box.",
        subtext="Select all the text and delete it.",
        advance_on_event=None,
        action_button="Done"
    ),

    # Step 21: Show answer
    TutorialStep(
        step_id="show_answer",
        target_type="none",
        target_ref=None,
        title="Please reveal the answer on your current card.",
        subtext="Click \"Show Answer\" below or press Space to reveal the answer.\n\nThis is important for the next shortcut.",
        advance_on_event="answer_shown",
        action_button=None
    ),

    # Step 22: Try template A (back only) - SECOND
    TutorialStep(
        step_id="try_template_a",
        target_type="coordinates",
        target_ref=get_reviewer_card_rect,
        title=f"Click in the sidebar, then press {shortcut_a}.",
        subtext="This sends only the back (answer) of the card.",
        advance_on_event="shortcut_used",
        action_button=None
    ),

    # Step 23: Template A success
    TutorialStep(
        step_id="template_a_success",
        target_type="none",
        target_ref=None,
        title="Great! You sent just the answer.",
        subtext="One more shortcut to go — this one sends both sides together.",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 24: Clear chat after A
    TutorialStep(
        step_id="clear_chat_after_a",
        target_type="none",
        target_ref=None,
        title="Clear the sidebar's text box again.",
        subtext="Select all the text and delete it.",
        advance_on_event=None,
        action_button="Done"
    ),

    # Step 25: Try template S (front & back) - LAST
    TutorialStep(
        step_id="try_template_s",
        target_type="coordinates",
        target_ref=get_reviewer_card_rect,
        title=f"Click in the sidebar, then press {shortcut_s}.",
        subtext="This sends both the question AND answer to The AI Panel.",
        advance_on_event="shortcut_used",
        action_button=None
    ),

    # Step 26: Template S explanation
    TutorialStep(
        step_id="template_s_success",
        target_type="none",
        target_ref=None,
        title="Nice! You sent both sides of the card.",
        subtext="This is the most useful template. It sends the full flashcard to The AI Panel so you can ask for help understanding it.",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 27: Templates complete
    TutorialStep(
        step_id="templates_complete",
        target_type="none",
        target_ref=None,
        title="You've learned all the templates! 🎉",
        subtext=f"Remember: Click in the sidebar first, then:\n\n{shortcut_q} → Front only\n{shortcut_a} → Back only\n{shortcut_s} → Front & Back",
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
        subtext="• Change the keyboard shortcut\n• Edit the text that gets sent to The AI Panel\n• Delete templates you don't need",
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
        subtext=f"Remember:\n\n{shortcut_add} → Add to Chat\n{shortcut_ask} → Ask Question\n\nYou can change these shortcuts here if you'd like.",
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

    # Step 28: Go back to AI Panel
    TutorialStep(
        step_id="go_back_to_ai_panel",
        target_type="none",
        target_ref=None,
        title="Click the back arrow one more time to return to The AI Panel.",
        subtext=None,
        advance_on_event="panel_web_view",
        action_button=None
    ),

    # Step 29: Recommendation to sign up
    TutorialStep(
        step_id="signup_recommendation",
        target_type="none",
        target_ref=None,
        title="Important: Create an account or log in!",
        subtext="Without an account, you'll get blocked after a few questions.\n\nIf you already have one, just log in. If not, signing up is 100% free and takes 30 seconds.\n\n(I'm not affiliated with them — it's just really good!)",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 30: Don't worry - it's free!
    TutorialStep(
        step_id="its_free_forever",
        target_type="none",
        target_ref=None,
        title="Don't worry — it's 100% free forever!",
        subtext="Creating an account is completely free and always will be. The AI Panel is free for medical students and MDs when you sign up.",
        advance_on_event=None,
        action_button="Next"
    ),

    # Step 31: How to sign in
    TutorialStep(
        step_id="how_to_signin",
        target_type="none",
        target_ref=None,
        title="How to sign in:",
        subtext="Click the hamburger menu (☰) in the top right of the sidebar, then tap \"Log in\" or \"Sign up\".",
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


# For backwards compatibility - generate steps on first import
TUTORIAL_STEPS = get_tutorial_steps()


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
