"""
Tutorial Manager - Core orchestration for the tutorial system

This module manages the tutorial flow, including step progression,
UI coordination, state persistence, and event handling.
"""

from PyQt6.QtCore import QTimer, QEvent, QObject
from PyQt6.QtWidgets import QApplication
from aqt import mw

from .tutorial_coach_mark import CoachMark
from .tutorial_overlay import TutorialOverlay
from .tutorial_steps import get_tutorial_steps, get_step_target_rect
from . import analytics

# Addon name for config storage (must match folder name, not __name__)
ADDON_NAME = "the_ai_panel"


class TutorialManager(QObject):
    """
    Singleton manager for the interactive tutorial system.

    Orchestrates:
    - Step progression and state management
    - CoachMark and TutorialOverlay display
    - Event routing and handling
    - State persistence to Anki config
    """

    def __init__(self):
        super().__init__()

        # Tutorial state
        self.tutorial_active = False
        self.current_step_index = 0
        self.is_paused = False
        self.tutorial_steps = []  # Will be populated with current shortcuts when tutorial starts

        # UI components
        self.coach_mark = None
        self.overlay = None

        # Retry mechanism for widget availability
        self.retry_timer = QTimer()
        self.retry_timer.timeout.connect(self._retry_show_step)
        self.retry_count = 0
        self.max_retries = 50  # Max 10 seconds (50 * 200ms)

        # Window resize handling
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._update_positions)

        # Periodic position check (for layout changes that don't trigger resize)
        self.position_check_timer = QTimer()
        self.position_check_timer.timeout.connect(self._update_positions)

        # Install event filter for window resize
        if mw:
            mw.installEventFilter(self)

    def start_tutorial(self):
        """
        Start the tutorial from the beginning or resume from saved progress.

        Checks if tutorial is already completed, and if not, loads saved
        progress and displays the appropriate step.
        """
        # Check if tutorial is already completed
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        if config.get("tutorial_completed", False):
            print("Tutorial already completed")
            return

        # Regenerate tutorial steps with current shortcuts from config
        self.tutorial_steps = get_tutorial_steps()

        # Mark tutorial as complete immediately so it won't restart if user closes Anki mid-tutorial
        config["tutorial_completed"] = True
        mw.addonManager.writeConfig(ADDON_NAME, config)

        # Start from step 0 (don't resume mid-tutorial)
        self.current_step_index = 0

        # Initialize UI components
        self._create_ui_components()

        # Activate tutorial
        self.tutorial_active = True
        self.is_paused = False

        # Start periodic position updates (every 500ms)
        self.position_check_timer.start(500)

        # Show first/current step
        self._show_current_step()

    def skip_tutorial(self):
        """
        Skip the tutorial entirely and mark as completed.

        Hides all UI components and saves completion state to config.
        """
        # Track skip status with current progress
        if self.current_step_index == 0:
            analytics.track_tutorial_status("skip")
        else:
            analytics.track_tutorial_status("skipped_midway")
        analytics.track_tutorial_step(self.current_step_index, len(self.tutorial_steps))
        
        self.tutorial_active = False
        self.position_check_timer.stop()
        self._hide_all()
        self._save_completion()

    def restart_tutorial(self):
        """
        Restart the tutorial from the beginning.

        Resets all progress and starts fresh, even if previously completed.
        """
        # Stop any existing tutorial activity
        self.tutorial_active = False
        self.position_check_timer.stop()
        self._hide_all()

        # Regenerate tutorial steps with current shortcuts from config
        self.tutorial_steps = get_tutorial_steps()

        # Reset config to start fresh
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        config["tutorial_completed"] = False
        config["tutorial_step_index"] = 0
        mw.addonManager.writeConfig(ADDON_NAME, config)

        # Reset internal state
        self.current_step_index = 0
        self.is_paused = False

        # Start the tutorial
        self._create_ui_components()
        self.tutorial_active = True
        self.position_check_timer.start(500)
        self._show_current_step()

    def handle_event(self, event_name: str):
        """
        Handle tutorial events and check for step progression.

        Args:
            event_name: Event name (e.g., "panel_opened", "text_highlighted")
        """
        if not self.tutorial_active or self.is_paused:
            return

        # Special handling for panel_closed event
        if event_name == "panel_closed":
            # Pause tutorial if we're on a panel-dependent step
            if self.current_step_index in [3, 4, 5]:  # Steps 4, 5, 6
                self._pause_tutorial()
            return

        # Resume if panel opened
        if event_name == "panel_opened" and self.is_paused:
            self._resume_tutorial()
            # Don't advance yet if we're not on step 1
            if self.current_step_index != 0:
                return

        # Check if this event advances the current step
        current_step = self.tutorial_steps[self.current_step_index]
        if current_step.advance_on_event == event_name:
            self.advance_to_next_step()

    def advance_to_next_step(self):
        """
        Advance to the next tutorial step.

        Increments step index, saves progress, and displays the next step.
        If this was the last step, completes the tutorial.
        """
        self.current_step_index += 1
        
        # Track tutorial progress (e.g., "7/36")
        analytics.track_tutorial_step(self.current_step_index, len(self.tutorial_steps))

        if self.current_step_index >= len(self.tutorial_steps):
            # Tutorial complete!
            self._complete_tutorial()
        else:
            # Save progress and show next step
            self._save_progress()
            self._show_current_step()

    def _create_ui_components(self):
        """Create CoachMark and TutorialOverlay widgets."""
        if self.coach_mark is None:
            self.coach_mark = CoachMark(mw)
            # Connect skip link
            self.coach_mark.skip_link.linkActivated.connect(lambda: self.skip_tutorial())

        if self.overlay is None:
            self.overlay = TutorialOverlay(mw)

    def _show_current_step(self, retry_count=0):
        """
        Display the current tutorial step.

        Handles target resolution, CoachMark positioning, and overlay highlighting.
        Implements retry logic for widgets that may not be available immediately.

        Args:
            retry_count: Number of retries attempted (for internal use)
        """
        if not self.tutorial_active:
            return

        if self.current_step_index >= len(self.tutorial_steps):
            self._complete_tutorial()
            return

        step = self.tutorial_steps[self.current_step_index]

        # Get target rectangle
        def on_target_rect_ready(target_rect):
            # If target is None and step requires a target, retry
            if target_rect is None and step.target_type != "none":
                if retry_count < self.max_retries:
                    # Retry after delay
                    self.retry_count = retry_count
                    QTimer.singleShot(200, lambda: self._show_current_step(retry_count + 1))
                else:
                    # Max retries reached, skip this step
                    print(f"Could not find target for step {step.step_id}, skipping...")
                    self.advance_to_next_step()
                return

            # Display the step
            self._display_step(step, target_rect)

        # Get target rect (may be async for HTML elements)
        get_step_target_rect(step, on_target_rect_ready)

    def _retry_show_step(self):
        """Retry showing current step (used by QTimer)."""
        self._show_current_step(self.retry_count + 1)

    def _display_step(self, step, target_rect):
        """
        Display the coach mark and overlay for a step.

        Args:
            step: TutorialStep to display
            target_rect: QRect for target, or None for center screen
        """
        # Set coach mark content
        self.coach_mark.set_content(
            title=step.title,
            subtext=step.subtext,
            action_button_text=step.action_button
        )

        # Connect action button if present
        if step.action_button:
            try:
                self.coach_mark.action_button.clicked.disconnect()
            except:
                pass

            # Special handling for demo deck creation
            if step.step_id == "create_demo_deck":
                self.coach_mark.action_button.clicked.connect(self._create_demo_deck_and_advance)
            else:
                self.coach_mark.action_button.clicked.connect(self.advance_to_next_step)

        # Don't show overlay - just the floating coach mark
        # User doesn't want the dark backdrop and highlight box

        # Position and show coach mark
        if target_rect:
            self.coach_mark.position_at_target(target_rect)
        else:
            # Center screen positioning
            screen = QApplication.primaryScreen().geometry()
            coach_width = self.coach_mark.width()
            coach_height = self.coach_mark.height()
            x = (screen.width() - coach_width) // 2
            y = (screen.height() - coach_height) // 2
            self.coach_mark.move(x, y)

        self.coach_mark.show()
        self.coach_mark.raise_()

    def _create_demo_deck_and_advance(self):
        """
        Create a demo deck with sample medical flashcards and open it for review.

        This allows users to immediately test AI Panel features without
        needing their own content.
        """
        try:
            import aqt
            from aqt import mw
            from anki.collection import Collection

            # Create or get the demo deck
            deck_name = "The AI Panel Demo"
            deck_id = mw.col.decks.id(deck_name)

            # Check if deck already has cards
            card_count = mw.col.decks.card_count(deck_id, include_subdecks=False)

            if card_count == 0:
                # Add sample medical flashcards
                model = mw.col.models.by_name("Basic")
                if model:
                    mw.col.models.set_current(model)

                    sample_cards = [
                        ("What is the first-line treatment for hypertension in most patients?",
                         "Thiazide diuretics or ACE inhibitors/ARBs"),
                        ("What are the classic signs of sepsis?",
                         "Fever, tachycardia, tachypnea, and altered mental status"),
                    ]

                    for front, back in sample_cards:
                        note = mw.col.new_note(model)
                        note['Front'] = front
                        note['Back'] = back
                        mw.col.add_note(note, deck_id)

            # Save changes
            mw.col.save()

            # Open the deck for review
            mw.col.decks.select(deck_id)
            mw.col.reset()
            mw.moveToState("review")

            # Advance to next step
            self.advance_to_next_step()

        except Exception as e:
            print(f"Error creating demo deck: {e}")
            # Still advance even if deck creation fails
            self.advance_to_next_step()

    def _pause_tutorial(self):
        """
        Pause the tutorial (e.g., when panel is closed mid-tutorial).

        Hides UI but maintains state for later resumption.
        """
        self.is_paused = True
        self._hide_all()

    def _resume_tutorial(self):
        """Resume the tutorial after being paused."""
        self.is_paused = False
        self._show_current_step()

    def _update_positions(self):
        """
        Update positions of coach mark and overlay (e.g., after window resize).

        Re-queries the target location and repositions UI components.
        This forces a fresh JavaScript query for HTML elements to get current coordinates.
        """
        if not self.tutorial_active or self.is_paused:
            return

        if self.current_step_index >= len(self.tutorial_steps):
            return

        step = self.tutorial_steps[self.current_step_index]

        def on_target_rect_ready(target_rect):
            if target_rect:
                # Just update coach mark position, no overlay
                self.coach_mark.position_at_target(target_rect)
            else:
                # If target not found, try again after delay
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(100, self._update_positions)

        # This will re-run JavaScript queries for HTML targets
        get_step_target_rect(step, on_target_rect_ready)

    def _hide_all(self):
        """Hide all tutorial UI components."""
        if self.coach_mark:
            self.coach_mark.hide()
        if self.overlay:
            self.overlay.hide()

    def _save_progress(self):
        """Save current tutorial progress to Anki config."""
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        config["tutorial_step_index"] = self.current_step_index
        mw.addonManager.writeConfig(ADDON_NAME, config)

    def _save_completion(self):
        """Mark tutorial as completed in Anki config."""
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
        config["tutorial_completed"] = True
        config["tutorial_step_index"] = len(self.tutorial_steps)
        mw.addonManager.writeConfig(ADDON_NAME, config)

    def _complete_tutorial(self):
        """
        Complete the tutorial.

        Hides all UI, marks as completed, and deactivates tutorial mode.
        """
        # Track tutorial completion
        analytics.track_tutorial_status("completed")
        
        self.tutorial_active = False
        self.position_check_timer.stop()
        self._hide_all()
        self._save_completion()
        print("Tutorial completed!")

    def eventFilter(self, obj, event):
        """
        Qt event filter to detect window resizes and moves.

        Triggers position update after a short delay to avoid excessive updates.
        """
        if self.tutorial_active:
            if event.type() in [QEvent.Type.Resize, QEvent.Type.Move]:
                # Debounce: wait 50ms after resize/move before updating
                self.resize_timer.start(50)

        return False  # Don't consume the event


# Singleton instance
_tutorial_manager = None


def get_tutorial_manager():
    """
    Get the global TutorialManager singleton.

    Returns:
        TutorialManager instance
    """
    global _tutorial_manager
    if _tutorial_manager is None:
        _tutorial_manager = TutorialManager()
    return _tutorial_manager
