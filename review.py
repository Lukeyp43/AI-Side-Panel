"""
Review Request Modal - Shows to engaged users to ask for AnkiWeb review.
Triggers for users with 3+ active days and 5+ total messages.
"""

from datetime import datetime
from aqt import mw

try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect
    from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve
    from PyQt6.QtGui import QCursor, QColor
except ImportError:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect
    from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve
    from PyQt5.QtGui import QCursor, QColor

from .utils import ADDON_NAME
from .theme_manager import ThemeManager

# AnkiWeb review page for the addon
REVIEW_URL = "https://ankiweb.net/shared/review/1314683963"


def should_show_review() -> bool:
    """
    Check if we should show the review modal.
    Trigger IF AND ONLY IF:
    1. Review modal not yet shown (!has_shown_review)
    2. Days active >= 3
    3. Total messages across all time >= 5
    """
    config = mw.addonManager.getConfig(ADDON_NAME) or {}
    analytics = config.get("analytics", {})

    # Check if already shown review
    if analytics.get("has_shown_review", False):
        return False

    # Check days active
    daily_usage = analytics.get("daily_usage", {})
    days_active = len(daily_usage.keys())

    if days_active < config.get("review_days_threshold", 3):
        return False

    # Check total messages across all time
    total_messages = 0
    for day, sessions in daily_usage.items():
        if isinstance(sessions, list):
            for session in sessions:
                total_messages += session.get("messages", 0)

    if total_messages < config.get("review_message_threshold", 5):
        return False

    return True


def mark_review_shown():
    """Mark that the review modal has been shown."""
    config = mw.addonManager.getConfig(ADDON_NAME) or {}
    analytics = config.get("analytics", {})
    analytics["has_shown_review"] = True
    analytics["review_shown_date"] = datetime.now().isoformat()
    config["analytics"] = analytics
    mw.addonManager.writeConfig(ADDON_NAME, config)


def track_review_modal(status: str, seconds_open: float):
    """
    Track review modal interaction.
    
    Status can be:
    - "clicked_review": Clicked the review button
    - "explicit_reject": Clicked skip button
    - "ignored_quickly": Closed in < 10 seconds without action
    """
    config = mw.addonManager.getConfig(ADDON_NAME) or {}
    analytics = config.get("analytics", {})
    analytics["review_modal_status"] = status
    analytics["review_modal_seconds_open"] = round(seconds_open, 1)
    config["analytics"] = analytics
    mw.addonManager.writeConfig(ADDON_NAME, config)
    print(f"AI Panel: Review modal tracked - {status} ({seconds_open:.1f}s)")


class ReviewOverlay(QWidget):
    """Review request overlay that covers the panel content."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.open_time = datetime.now()
        self.animation = None
        self._bg_color = ThemeManager.get_qcolor('background')
        
        self.setAutoFillBackground(True)
        
        if parent:
            parent.installEventFilter(self)
        
        self.setup_ui()
    
    def eventFilter(self, watched, event):
        """Resize overlay when parent is resized."""
        try:
            from PyQt6.QtCore import QEvent
        except ImportError:
            from PyQt5.QtCore import QEvent
        
        if watched == self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
        return super().eventFilter(watched, event)
        
    def paintEvent(self, event):
        """Override paint to guarantee solid dark background."""
        try:
            from PyQt6.QtGui import QPainter
        except ImportError:
            from PyQt5.QtGui import QPainter
        
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._bg_color)
        painter.end()
        super().paintEvent(event)
        
    def showEvent(self, event):
        """Animate slide down when shown."""
        super().showEvent(event)
        self.animate_entry()

    def animate_entry(self):
        """Animate the overlay sliding down from the top."""
        try:
            from PyQt6.QtCore import QPropertyAnimation, QRect, QEasingCurve
        except ImportError:
            from PyQt5.QtCore import QPropertyAnimation, QRect, QEasingCurve
            
        parent = self.parent()
        if not parent:
            return
            
        end_rect = parent.rect()
        start_rect = QRect(end_rect.x(), -end_rect.height(), end_rect.width(), end_rect.height())
        
        self.setGeometry(start_rect)
        
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(1600)
        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        self.animation.setEasingCurve(QEasingCurve.Type.OutExpo)
        self.animation.start()
        
    def setup_ui(self):
        c = ThemeManager.get_palette()
        self.setStyleSheet(f"""
            QWidget {{
                background: {c['background']};
            }}
            QLabel {{
                color: {c['text']};
                background: transparent;
            }}
        """)
        
        self.exit_method = None
        self.typing_index = 0
        self.current_text = ""
        self.is_deleting = False
        self.current_phase = 0
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        main_layout.addStretch()
        
        # Content container - responsive width
        container = QWidget()
        container.setMinimumWidth(280)
        container.setMaximumWidth(480)
        container.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(28, 0, 28, 0)
        content_layout.setSpacing(0)
        
        # === ANIMATED TEXT LABELS ===
        # All labels need adjustSize() called when text changes to prevent cutoff
        
        # Phase 1 label (types then deletes) - "I know... Not this shit again."
        self.phase1_label = QLabel("")
        self.phase1_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 500;
            color: {c['text_secondary']};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: transparent;
        """)
        self.phase1_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.phase1_label.setWordWrap(True)
        self.phase1_label.setSizePolicy(self.phase1_label.sizePolicy().horizontalPolicy(), 
                                         self.phase1_label.sizePolicy().verticalPolicy())
        content_layout.addWidget(self.phase1_label)
        
        # Phase 2 label (types then deletes) - "I swear this is the last time..."
        self.phase2_label = QLabel("")
        self.phase2_label.setMinimumHeight(50)  # Allow for 2 lines
        self.phase2_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 500;
            color: {c['text_secondary']};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: transparent;
        """)
        self.phase2_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.phase2_label.setWordWrap(True)
        self.phase2_label.hide()
        content_layout.addWidget(self.phase2_label)
        
        # Main content label (stays visible) - "So..... this add on took me..."
        self.main_label = QLabel("")
        self.main_label.setMinimumHeight(60)  # Allow for 2-3 lines
        self.main_label.setStyleSheet(f"""
            font-size: 15px;
            font-weight: 600;
            color: {c['text']};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: transparent;
        """)
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.main_label.setWordWrap(True)
        self.main_label.hide()
        content_layout.addWidget(self.main_label)
        
        # Motivation label - "The main way I stay motivated..."
        self.motivation_label = QLabel("")
        self.motivation_label.setMinimumHeight(40)
        self.motivation_label.setStyleSheet(f"""
            font-size: 14px;
            color: {c['text_secondary']};
            background: transparent;
        """)
        self.motivation_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.motivation_label.setWordWrap(True)
        self.motivation_label.hide()
        content_layout.addWidget(self.motivation_label)
        
        # Please label - "So.... Can you please..."
        self.please_label = QLabel("")
        self.please_label.setMinimumHeight(50)
        self.please_label.setStyleSheet(f"""
            font-size: 14px;
            color: {c['text_secondary']};
            background: transparent;
        """)
        self.please_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.please_label.setWordWrap(True)
        self.please_label.hide()
        content_layout.addWidget(self.please_label)
        
        # Final ask label - "Leave a positive review..."
        self.final_label = QLabel("")
        self.final_label.setMinimumHeight(50)
        self.final_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {c['text']};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: transparent;
        """)
        self.final_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.final_label.setWordWrap(True)
        self.final_label.hide()
        content_layout.addWidget(self.final_label)
        
        content_layout.addSpacing(20)
        
        # === BUTTONS (hidden initially) ===
        self.btn_container = QWidget()
        self.btn_container.hide()
        btn_layout = QVBoxLayout(self.btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(12)
        
        # Review button - GitHub star button style
        self.review_btn = QPushButton()
        self.review_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # Create button layout with icon + text + arrow
        review_btn_inner = QHBoxLayout(self.review_btn)
        review_btn_inner.setContentsMargins(16, 12, 16, 12)
        review_btn_inner.setSpacing(12)
        
        # Star icon (checkbox style like GitHub)
        star_label = QLabel("⭐")
        star_label.setStyleSheet(f"font-size: 18px; background: transparent;")
        review_btn_inner.addWidget(star_label)
        
        # Button text
        text_label = QLabel("Leave a Review")
        text_label.setStyleSheet(f"""
            font-size: 15px;
            font-weight: 500;
            color: {c['text']};
            background: transparent;
        """)
        review_btn_inner.addWidget(text_label)
        
        review_btn_inner.addStretch()
        
        # Arrow icon
        arrow_label = QLabel("↗")
        arrow_label.setStyleSheet(f"font-size: 14px; color: {c['text_secondary']}; background: transparent;")
        review_btn_inner.addWidget(arrow_label)
        
        self.review_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['surface']};
                border: 1px solid {c['border']};
                border-radius: 10px;
                min-height: 48px;
            }}
            QPushButton:hover {{
                background: {c['hover']};
                border-color: {c['text_secondary']};
            }}
        """)
        self.review_btn.clicked.connect(self.on_review_clicked)
        btn_layout.addWidget(self.review_btn)
        
        btn_layout.addSpacing(8)
        
        # Skip button - guilt-inducing, very subtle
        self.skip_btn = QPushButton("No thanks, I'm mean")
        self.skip_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {c['text_secondary']};
                border: none;
                font-size: 11px;
                padding: 8px;
            }}
            QPushButton:hover {{
                color: {c['text_secondary']};
            }}
        """)
        self.skip_btn.clicked.connect(self.on_skip_clicked)
        btn_layout.addWidget(self.skip_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        
        content_layout.addWidget(self.btn_container)
        
        main_layout.addWidget(container, 0, Qt.AlignmentFlag.AlignHCenter)
        main_layout.addStretch()
        
        # Start animation sequence after slide-down
        QTimer.singleShot(1200, self.start_typing_sequence)
    
    def start_typing_sequence(self):
        """Begin the animated typing sequence."""
        # Define all text phases
        self.texts = [
            ("phase1", "I know... Not this shit again.", True),  # (label_name, text, should_delete)
            ("phase2", "I swear this is the last time I do this", True),
            ("main", "So..... this add on took me fucking forever to build and I am updating it constantly.", False),
            ("motivation", "The main way I stay motivated is if you do this", False),
            ("please", "So.... Can you please and I mean pretty please with a giant cherry on top.", False),
            ("final", "Leave a positive review on Anki about this add on. You are my only Hope.", False),
        ]
        
        self.current_phase = 0
        self.start_phase()
    
    def start_phase(self):
        """Start typing the current phase."""
        if self.current_phase >= len(self.texts):
            # All done, show buttons
            self.show_buttons()
            return
        
        label_name, text, should_delete = self.texts[self.current_phase]
        
        # Get the label for this phase
        label_map = {
            "phase1": self.phase1_label,
            "phase2": self.phase2_label,
            "main": self.main_label,
            "motivation": self.motivation_label,
            "please": self.please_label,
            "final": self.final_label,
        }
        
        self.current_label = label_map[label_name]
        self.current_target = text
        self.current_should_delete = should_delete
        self.typing_index = 0
        self.is_deleting = False
        
        # Show the label
        self.current_label.show()
        
        # Start typing
        self.typing_timer = QTimer()
        self.typing_timer.timeout.connect(self.type_character)
        self.typing_timer.start(70)
    
    def type_character(self):
        """Type or delete one character at a time."""
        if self.is_deleting:
            current = self.current_label.text()
            if len(current) > 0:
                self.current_label.setText(current[:-1])
            else:
                self.typing_timer.stop()
                self.is_deleting = False
                self.current_label.hide()
                self.current_phase += 1
                QTimer.singleShot(300, self.start_phase)
        else:
            if self.typing_index < len(self.current_target):
                self.current_label.setText(self.current_target[:self.typing_index + 1])
                self.current_label.adjustSize()  # Resize to fit wrapped text
                self.current_label.raise_()  # Ensure label is on top
                self.typing_index += 1
            else:
                self.typing_timer.stop()
                if self.current_should_delete:
                    # Pause then delete
                    QTimer.singleShot(1200, self.start_backspace)
                else:
                    # Move to next phase
                    self.current_phase += 1
                    QTimer.singleShot(600, self.start_phase)
    
    def start_backspace(self):
        """Start deleting the current text."""
        self.is_deleting = True
        self.typing_timer = QTimer()
        self.typing_timer.timeout.connect(self.type_character)
        self.typing_timer.start(40)
    
    def show_buttons(self):
        """Show the action buttons."""
        self.btn_container.show()
    
    def on_review_clicked(self):
        """Handle review button click."""
        import webbrowser
        webbrowser.open(REVIEW_URL)
        self.exit_method = "clicked_review"
        # Wait 2 seconds before closing to let user focus on the browser
        QTimer.singleShot(2000, self.close_overlay)
        
    def on_skip_clicked(self):
        """Handle skip button click."""
        self.exit_method = "explicit_reject"
        self.close_overlay()
    
    def close_overlay(self):
        """Close the overlay and track interaction."""
        duration = (datetime.now() - self.open_time).total_seconds()
        
        status = "ignored_quickly"
        
        if self.exit_method == "clicked_review":
            status = "clicked_review"
        elif self.exit_method == "explicit_reject":
            status = "explicit_reject"
        elif duration > 10:
            status = "viewed_long"
            
        track_review_modal(status, duration)
        
        self.hide()
        self.deleteLater()


def show_review_overlay_if_eligible(panel_widget):
    """Check eligibility and show overlay on the panel if appropriate."""
    if should_show_review():
        # Mark as shown immediately to prevent re-triggers
        mark_review_shown()
        
        # Create overlay as child of panel
        overlay = ReviewOverlay(panel_widget)
        overlay.resize(panel_widget.size())
        overlay.show()
        overlay.raise_()
        return overlay
    return None
