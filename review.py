"""
Review Request Modal — simple centered popup that asks engaged users to leave
an AnkiWeb review. Triggered after any meaningful AI feature use, not just chat
messages, since users can now generate cards from outside the side panel.
"""

import webbrowser
from datetime import datetime
from aqt import mw

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QCursor
except ImportError:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
    )
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QCursor

from .utils import ADDON_NAME
from .theme_manager import ThemeManager

REVIEW_URL = "https://ankiweb.net/shared/review/1314683963"
FEEDBACK_URL = "https://github.com/Lukeyp43/OpenEvidence-AI/issues/new"

# AI feature counters that count toward "engagement" for review eligibility.
# Side-panel chat messages are also counted (from daily_usage).
_ENGAGEMENT_COUNTERS = (
    "ai_create_count",
    "ai_generate_count",
    "explain_count",
    "ai_answer_count",
)

# Re-prompt backoff schedule (days to wait after show N before showing again).
# Stops entirely after all slots are exhausted or once the user clicks thumbs up/down.
_BACKOFF_SCHEDULE = [7, 21, 45]  # after show 1, 2, 3
_MAX_SHOWS = len(_BACKOFF_SCHEDULE)  # = 3

# Between re-prompts the user must accumulate at least this many new interactions
# (any mix of chat messages, AI Create, AI Generate, Explain, AI Answer).
_FRESH_ENGAGEMENT_MIN = 3


def _total_engagement(analytics: dict) -> int:
    """Sum of chat messages + AI feature usage across all time."""
    total = 0

    # Chat messages live inside daily_usage sessions
    for sessions in analytics.get("daily_usage", {}).values():
        if isinstance(sessions, list):
            for session in sessions:
                total += session.get("messages", 0)

    # Lifetime AI feature counters
    for key in _ENGAGEMENT_COUNTERS:
        total += analytics.get(key, 0)

    return total


def _migrate_legacy_review_state(analytics: dict) -> dict:
    """
    Bring users from the old (single-shot) review schema onto the new
    (re-promptable) schema. Idempotent — safe to call every check.
    """
    if "review_show_count" in analytics:
        return analytics  # already on new schema

    if analytics.get("has_shown_review", False):
        # They've seen the modal under the old code path. Treat that as
        # show #1, and map old status values to the new naming.
        analytics["review_show_count"] = 1
        analytics["review_last_shown_date"] = analytics.get("review_shown_date")
        old_status = analytics.get("review_modal_status")
        # Map old status → new thumb value (or None if they just dismissed)
        if old_status == "clicked_review":
            analytics["review_responded"] = "thumbs_up"
            mapped_status = "thumbs_up"
        elif old_status == "explicit_reject":
            analytics["review_responded"] = "thumbs_down"  # old "No thanks" ≈ thumbs down
            mapped_status = "thumbs_down"
        else:
            analytics["review_responded"] = None
            mapped_status = "dismissed"
        # Seed review_history from the old single-show data
        old_date = analytics.get("review_shown_date", "")
        old_seconds = analytics.get("review_modal_seconds_open", 0)
        analytics["review_history"] = [{
            "show": 1,
            "date": old_date[:10] if old_date else None,
            "status": mapped_status,
            "seconds": old_seconds or 0,
        }]
        # Snapshot current engagement so the fresh-engagement gate starts from here
        analytics["review_engagement_at_last_show"] = _total_engagement(analytics)
    else:
        analytics["review_show_count"] = 0
        analytics["review_last_shown_date"] = None
        analytics["review_responded"] = None
        analytics["review_engagement_at_last_show"] = 0
        analytics["review_history"] = []

    return analytics


def _next_show_wait_days(show_count: int) -> int:
    """Days to wait after `show_count` shows before re-prompting."""
    if show_count <= 0:
        return 0
    idx = show_count - 1
    if idx < len(_BACKOFF_SCHEDULE):
        return _BACKOFF_SCHEDULE[idx]
    return _BACKOFF_SCHEDULE[-1]  # fallback to last value


def should_show_review() -> bool:
    """
    Eligible if all of:
      1. User hasn't permanently responded (no thumbs up/down click yet)
      2. We're under the max-shows cap (3)
      3. Active on >= review_days_threshold distinct days
      4. Total engagement (messages + AI feature uses) >= review_message_threshold
      5. Enough time has passed since the last show (7 → 21 → 45 day backoff)
      6. User has accumulated >= _FRESH_ENGAGEMENT_MIN new interactions since last show
    """
    config = mw.addonManager.getConfig(ADDON_NAME) or {}
    analytics = _migrate_legacy_review_state(config.get("analytics", {}))

    if analytics.get("review_responded") is not None:
        return False

    show_count = analytics.get("review_show_count", 0)
    if show_count >= _MAX_SHOWS:
        return False

    days_active = len(analytics.get("daily_usage", {}).keys())
    if days_active < config.get("review_days_threshold", 3):
        return False

    current_engagement = _total_engagement(analytics)

    if current_engagement < config.get("review_message_threshold", 5):
        return False

    if show_count > 0:
        # Backoff: must wait N days since last show before re-prompting
        last_shown = analytics.get("review_last_shown_date")
        if last_shown:
            try:
                last_dt = datetime.fromisoformat(last_shown)
                days_since = (datetime.now() - last_dt).days
                if days_since < _next_show_wait_days(show_count):
                    return False
            except (ValueError, TypeError):
                pass  # Bad date — fall through and allow show

        # Fresh engagement gate: user must have done at least N new
        # interactions since the last time we showed the modal.
        engagement_at_last_show = analytics.get("review_engagement_at_last_show", 0)
        if current_engagement - engagement_at_last_show < _FRESH_ENGAGEMENT_MIN:
            return False

    return True


def mark_review_shown():
    """Record that the modal was just shown (increments count + bumps last-shown date)."""
    config = mw.addonManager.getConfig(ADDON_NAME) or {}
    analytics = _migrate_legacy_review_state(config.get("analytics", {}))
    analytics["review_show_count"] = analytics.get("review_show_count", 0) + 1
    analytics["review_last_shown_date"] = datetime.now().isoformat()
    # Snapshot engagement so we can enforce the fresh-engagement gate later
    analytics["review_engagement_at_last_show"] = _total_engagement(analytics)
    # Keep legacy field updated for any code/server still reading it
    analytics["has_shown_review"] = True
    analytics["review_shown_date"] = analytics["review_last_shown_date"]
    config["analytics"] = analytics
    mw.addonManager.writeConfig(ADDON_NAME, config)


def mark_review_responded(response: str):
    """
    Permanently stop showing the modal. Stores which thumb was clicked.

    Args:
        response: "thumbs_up" or "thumbs_down"
    """
    config = mw.addonManager.getConfig(ADDON_NAME) or {}
    analytics = _migrate_legacy_review_state(config.get("analytics", {}))
    analytics["review_responded"] = response  # "thumbs_up" or "thumbs_down"
    config["analytics"] = analytics
    mw.addonManager.writeConfig(ADDON_NAME, config)


def track_review_modal(status: str, seconds_open: float):
    """
    Append an entry to review_history — one per show, never overwritten.

    status one of:
      - "thumbs_up"   — clicked 👍 (routed to AnkiWeb review)
      - "thumbs_down" — clicked 👎 (routed to GitHub issues)
      - "dismissed"   — closed via X or ignored
    """
    config = mw.addonManager.getConfig(ADDON_NAME) or {}
    analytics = config.get("analytics", {})

    history = analytics.get("review_history", [])
    history.append({
        "show": len(history) + 1,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": status,
        "seconds": round(seconds_open, 1),
    })
    analytics["review_history"] = history

    # Keep legacy fields in sync for any server code still reading them
    analytics["review_modal_status"] = status
    analytics["review_modal_seconds_open"] = round(seconds_open, 1)

    config["analytics"] = analytics
    mw.addonManager.writeConfig(ADDON_NAME, config)
    print(f"AI Panel: Review modal tracked - show #{len(history)} {status} ({seconds_open:.1f}s)")


class ReviewModal(QWidget):
    """Full-screen review modal styled like the onboarding tutorial overlay."""

    FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.open_time = datetime.now()
        self.exit_method = None
        self._backdrop_opacity = 0

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._build_ui()

        if parent:
            parent.installEventFilter(self)

    def eventFilter(self, watched, event):
        try:
            from aqt.qt import QEvent
        except ImportError:
            from PyQt5.QtCore import QEvent
        if watched == self.parent() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(30, self._sync_geometry)
        return super().eventFilter(watched, event)

    def _sync_geometry(self):
        p = self.parent()
        if p and p.isVisible():
            frame = p.frameGeometry()
            self.setGeometry(frame)

    def paintEvent(self, event):
        try:
            from PyQt6.QtGui import QPainter, QColor
        except ImportError:
            from PyQt5.QtGui import QPainter, QColor
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, int(self._backdrop_opacity * 255)))
        painter.end()
        super().paintEvent(event)

    def show_animated(self):
        self._sync_geometry()
        self.show()
        self.raise_()
        self.activateWindow()
        self._fade_step = 0
        self._fade_timer = QTimer()
        self._fade_timer.timeout.connect(self._do_fade)
        self._fade_timer.start(16)

    def _do_fade(self):
        self._fade_step += 1
        self._backdrop_opacity = min(self._fade_step / 20.0 * 0.75, 0.75)
        self.update()
        if self._fade_step >= 20:
            self._fade_timer.stop()

    def _build_ui(self):
        c = ThemeManager.get_palette()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Center the card
        outer.addStretch(2)

        card = QWidget()
        card.setFixedSize(580, 420)
        card.setObjectName("reviewCard")
        card.setStyleSheet(f"""
            QWidget#reviewCard {{
                background: {c['background']};
                border: 1px solid {c['border']};
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
                color: {c['text']};
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar with X button
        header_bar = QWidget()
        header_bar.setFixedHeight(44)
        header_bar.setStyleSheet(f"""
            background: transparent;
            border-bottom: 1px solid {c['border']};
        """)
        hb_layout = QHBoxLayout(header_bar)
        hb_layout.setContentsMargins(16, 0, 16, 0)

        hb_layout.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 8px;
                color: {c['text_secondary']};
                font-size: 18px;
            }}
            QPushButton:hover {{
                background: {c['hover']};
                color: {c['text']};
            }}
        """)
        close_btn.clicked.connect(self._on_close_clicked)
        hb_layout.addWidget(close_btn)

        layout.addWidget(header_bar)

        # Content area
        content = QVBoxLayout()
        content.setContentsMargins(50, 0, 50, 36)
        content.setSpacing(0)

        content.addStretch(2)

        # Title — big, centered
        title = QLabel("Enjoying AI Side Panel?")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            font-size: 26px;
            font-weight: 700;
            font-family: {self.FONT};
            color: {c['text']};
        """)
        content.addWidget(title)
        content.addSpacing(44)

        # Two big circular thumb buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(50)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch()

        circle_size = 100
        circle_style = f"""
            QPushButton {{
                background: {c['surface']};
                border: 2px solid {c['border']};
                border-radius: {circle_size // 2}px;
                font-size: 44px;
            }}
            QPushButton:hover {{
                background: {c['hover']};
                border-color: {c['accent']};
            }}
        """

        thumbs_up = QPushButton("\U0001f44d")
        thumbs_up.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        thumbs_up.setFixedSize(circle_size, circle_size)
        thumbs_up.setStyleSheet(circle_style)
        thumbs_up.clicked.connect(self._on_thumbs_up_clicked)
        btn_row.addWidget(thumbs_up)

        thumbs_down = QPushButton("\U0001f44e")
        thumbs_down.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        thumbs_down.setFixedSize(circle_size, circle_size)
        thumbs_down.setStyleSheet(circle_style)
        thumbs_down.clicked.connect(self._on_thumbs_down_clicked)
        btn_row.addWidget(thumbs_down)

        btn_row.addStretch()
        content.addLayout(btn_row)

        content.addStretch(3)

        # Subtle footer
        caption = QLabel("If you don't respond, we'll ask again later.")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setStyleSheet(f"""
            font-size: 12px;
            color: {c['text_secondary']};
        """)
        content.addWidget(caption)

        layout.addLayout(content, 1)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(3)

    def _on_thumbs_up_clicked(self):
        webbrowser.open(REVIEW_URL)
        self.exit_method = "thumbs_up"
        mark_review_responded("thumbs_up")
        QTimer.singleShot(800, self._close_modal)

    def _on_thumbs_down_clicked(self):
        webbrowser.open(FEEDBACK_URL)
        self.exit_method = "thumbs_down"
        mark_review_responded("thumbs_down")
        QTimer.singleShot(800, self._close_modal)

    def _on_close_clicked(self):
        self.exit_method = "dismissed"
        self._close_modal()

    def _close_modal(self):
        self._record_outcome()
        parent = self.parent()
        if parent is not None:
            try:
                parent.removeEventFilter(self)
            except Exception:
                pass
        self.hide()
        QTimer.singleShot(0, self.deleteLater)

    def _record_outcome(self):
        duration = (datetime.now() - self.open_time).total_seconds()

        if self.exit_method in ("thumbs_up", "thumbs_down"):
            status = self.exit_method
        else:
            status = "dismissed"

        track_review_modal(status, duration)


# Keep a strong reference so the modal isn't garbage-collected mid-show
_active_review_modal = None


def show_review_modal_if_eligible(parent=None):
    """
    Check eligibility and pop the review modal over the given parent window.
    Defaults to Anki's main window. Pass a different parent (e.g. Add Cards dialog)
    so the modal appears above that window instead.
    Returns the modal if shown (caller should bail), or None if not shown.
    """
    global _active_review_modal

    if not should_show_review():
        return None

    # Don't show if no internet — thumbs would open a browser to a dead page
    import socket
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2).close()
    except OSError:
        return None

    # Mark immediately so concurrent triggers don't double-show
    mark_review_shown()

    modal = ReviewModal(parent=parent or mw)
    _active_review_modal = modal
    # Defer slightly so the triggering action's UI settles first
    QTimer.singleShot(600, modal.show_animated)
    return modal
