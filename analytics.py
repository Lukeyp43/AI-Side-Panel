from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from aqt import mw
import sys
import json
import threading
import uuid
from urllib import request, error


from urllib import request, error
from .utils import ADDON_NAME

# Runtime state to track if we've recorded usage for this session
_session_usage_tracked = False
_current_session_index = -1  # Index of current session in today's daily_usage list


def get_analytics_data() -> Dict:
    """Get current analytics data from config."""
    config = mw.addonManager.getConfig(ADDON_NAME) or {}
    return config.get("analytics", {})


def save_analytics_data(analytics: Dict):
    """Save analytics data to config."""
    config = mw.addonManager.getConfig(ADDON_NAME) or {}
    config["analytics"] = analytics
    mw.addonManager.writeConfig(ADDON_NAME, config)


def init_analytics():
    """Initialize analytics on first run. Returns True if this was a fresh install."""
    global _current_session_index
    analytics = get_analytics_data()

    if not analytics.get("first_install_date"):
        # Get locale info
        locale_info = get_locale_info()
        
        # Get current date/time for first session
        today = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M:%S")

        # Core metadata
        analytics["first_install_date"] = datetime.now(timezone.utc).isoformat()
        analytics["user_id"] = str(uuid.uuid4())
        analytics["platform"] = sys.platform  # darwin, win32, linux
        analytics["locale"] = locale_info.get("locale")  # e.g., "en_US"
        analytics["timezone"] = locale_info.get("timezone")  # e.g., "PST"
        
        # Auth tracking
        analytics["has_logged_in"] = False
        analytics["auth_button_clicked"] = None  # "signup" or "login"

        # Onboarding & Tutorial tracking
        analytics["onboarding_completed"] = False
        analytics["tutorial_status"] = None  # null/true/"skip"/"skipped_midway"
        analytics["tutorial_current_step"] = None  # e.g., "1/36"

        # Granular usage tracking

        # AI feature usage (lifetime totals — per-session counts also live in daily_usage)
        analytics["ai_create_count"] = 0
        analytics["ai_generate_count"] = 0
        analytics["ai_generate_cards_count"] = 0  # total cards actually saved to a deck
        analytics["explain_count"] = 0
        analytics["ai_answer_count"] = 0

        # Session-based daily usage (ONLY field needed for engagement metrics)
        # Server can calculate: total sessions, sessions with messages, etc.
        analytics["daily_usage"] = {
            today: [{"time": current_time, "messages": 0}]
        }
        _current_session_index = 0

        save_analytics_data(analytics)
        return True  # Fresh install
    
    return False  # Not a fresh install







def track_auth_button_click(button_type: str):
    """
    Track when user clicks Sign up or Log in button.

    Args:
        button_type: "signup" or "login"
    """
    analytics = get_analytics_data()

    # Only track the first click (whichever comes first)
    if not analytics.get("auth_button_clicked"):
        analytics["auth_button_clicked"] = button_type  # "signup" or "login"
        analytics["auth_button_click_date"] = datetime.now().isoformat()
        save_analytics_data(analytics)


def track_login_detected():
    """Track when we detect user has logged in."""
    analytics = get_analytics_data()

    if not analytics.get("has_logged_in"):
        analytics["has_logged_in"] = True
        analytics["first_login_date"] = datetime.now().isoformat()
        save_analytics_data(analytics)


def is_user_logged_in() -> bool:
    """Check if user is already logged in (based on analytics)."""
    analytics = get_analytics_data()
    return analytics.get("has_logged_in", False)


def track_onboarding_completed():
    """Track when user completes onboarding."""
    analytics = get_analytics_data()
    if not analytics.get("onboarding_completed"):
        analytics["onboarding_completed"] = True
        save_analytics_data(analytics)


def track_tutorial_status(status: str):
    """
    Track tutorial status.

    Args:
        status: "completed", "skip", or "skipped_midway"
    """
    analytics = get_analytics_data()

    # Only update if going from less complete to more complete state
    # null -> skip/skipped_midway/completed
    # skip/skipped_midway -> completed
    current = analytics.get("tutorial_status")

    if current != "completed":  # Don't downgrade from completed
        analytics["tutorial_status"] = status
        save_analytics_data(analytics)


def track_tutorial_step(current: int, total: int):
    """
    Track current tutorial step.

    Args:
        current: Current step number (e.g., 1)
        total: Total number of steps (e.g., 36)
    """
    analytics = get_analytics_data()
    analytics["tutorial_current_step"] = f"{current}/{total}"
    save_analytics_data(analytics)


def _track_feature_usage(feature_key: str, increment: int = 1):
    """
    Increment the lifetime counter and the current session counter for an AI feature.

    Lifetime counter: top-level field "<feature_key>_count".
    Per-session counter: "<feature_key>" inside the current session entry of daily_usage,
    so the server can correlate feature usage with messages on the same day/session.
    """
    global _current_session_index
    analytics = get_analytics_data()

    # Lifetime total
    lifetime_key = f"{feature_key}_count"
    analytics[lifetime_key] = analytics.get(lifetime_key, 0) + increment

    # Per-session counter (mirrors track_message_sent's session-recovery logic)
    today = datetime.now().strftime("%Y-%m-%d")
    daily_usage = analytics.get("daily_usage", {})
    todays_sessions = daily_usage.get(today, [])

    if isinstance(todays_sessions, dict) or isinstance(todays_sessions, int):
        todays_sessions = []

    if _current_session_index < 0 or _current_session_index >= len(todays_sessions):
        if len(todays_sessions) > 0:
            _current_session_index = len(todays_sessions) - 1
        else:
            current_time = datetime.now().strftime("%H:%M:%S")
            todays_sessions.append({"time": current_time, "messages": 0})
            _current_session_index = 0
            daily_usage[today] = todays_sessions

    if 0 <= _current_session_index < len(todays_sessions):
        session = todays_sessions[_current_session_index]
        session[feature_key] = session.get(feature_key, 0) + increment
        daily_usage[today] = todays_sessions
        analytics["daily_usage"] = daily_usage

    save_analytics_data(analytics)


def track_ai_create():
    """Track when user triggers AI Create (single-card generation in editor)."""
    _track_feature_usage("ai_create")


def track_ai_generate():
    """Track when user triggers AI Generate (multi-card wizard generation)."""
    _track_feature_usage("ai_generate")


def track_ai_generate_cards_created(count: int):
    """Track number of cards actually saved to a deck from AI Generate."""
    if count > 0:
        _track_feature_usage("ai_generate_cards", count)


def track_explain():
    """Track when user uses inline Explain on highlighted reviewer text."""
    _track_feature_usage("explain")


def track_ai_answer():
    """Track when user clicks AI Answer to fill the Back field of a card."""
    _track_feature_usage("ai_answer")


def track_message_sent():
    """Track when user sends a message in the chat (per-session)."""
    global _current_session_index
    analytics = get_analytics_data()
    today = datetime.now().strftime("%Y-%m-%d")
    
    daily_usage = analytics.get("daily_usage", {})
    todays_sessions = daily_usage.get(today, [])
    
    # Handle legacy/invalid formats
    if isinstance(todays_sessions, dict) or isinstance(todays_sessions, int):
        todays_sessions = []
    
    # If session index is invalid, try to recover
    if _current_session_index < 0 or _current_session_index >= len(todays_sessions):
        if len(todays_sessions) > 0:
            # Use the last session for today
            _current_session_index = len(todays_sessions) - 1
        else:
            # No sessions today - create one
            current_time = datetime.now().strftime("%H:%M:%S")
            todays_sessions.append({"time": current_time, "messages": 0})
            _current_session_index = 0
            daily_usage[today] = todays_sessions
    
    # Now update the message count
    if _current_session_index >= 0 and _current_session_index < len(todays_sessions):
        todays_sessions[_current_session_index]["messages"] = todays_sessions[_current_session_index].get("messages", 0) + 1
        daily_usage[today] = todays_sessions
        analytics["daily_usage"] = daily_usage
        save_analytics_data(analytics)
        print(f"AI Panel: Tracked message - session {_current_session_index}, total messages: {todays_sessions[_current_session_index]['messages']}")


def track_anki_open():
    """Create a new session for this Anki launch."""
    global _current_session_index
    analytics = get_analytics_data()
    
    # Track new session for today
    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    daily_usage = analytics.get("daily_usage", {})
    
    # Get or initialize today's session list
    todays_sessions = daily_usage.get(today, [])
    # Migration: If it's the old dict format, convert/reset it
    if isinstance(todays_sessions, dict) or isinstance(todays_sessions, int):
        todays_sessions = []
        
    # Start new session (messages only - granular actions tracked separately)
    new_session = {"time": current_time, "messages": 0}
    todays_sessions.append(new_session)
    
    daily_usage[today] = todays_sessions
    analytics["daily_usage"] = daily_usage
    
    # Update global index to point to this new session
    global _current_session_index
    _current_session_index = len(todays_sessions) - 1
    
    save_analytics_data(analytics)


def cleanup_old_daily_data(analytics: Dict):
    """Keep only last 90 days of daily usage data."""
    if "daily_usage" not in analytics:
        return

    cutoff_date = datetime.now() - timedelta(days=90)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    # Filter out dates older than 90 days
    daily_usage = analytics["daily_usage"]
    analytics["daily_usage"] = {
        date: count
        for date, count in daily_usage.items()
        if date >= cutoff_str
    }


def get_locale_info() -> Dict:
    """
    Get user locale information (for detecting US users).

    Note: This is not 100% accurate but can give hints about location.
    """
    import locale
    import platform

    try:
        user_locale = locale.getdefaultlocale()
        return {
            "locale": user_locale[0] if user_locale else None,
            "encoding": user_locale[1] if user_locale else None,
            "platform": platform.system(),
            "timezone": datetime.now().astimezone().tzinfo.tzname(None) if hasattr(datetime.now().astimezone().tzinfo, 'tzname') else None,
        }
    except:
        return {}


def should_send_analytics() -> bool:
    """Check if we should send analytics today (once per day)."""
    analytics = get_analytics_data()
    last_sent = analytics.get("last_analytics_sent")

    if not last_sent:
        return True

    try:
        last_sent_date = datetime.fromisoformat(last_sent).date()
        today = datetime.now().date()
        return today > last_sent_date
    except:
        return True


def send_analytics_background():
    """Send analytics to Supabase in background thread (non-blocking)."""
    def _send():
        try:
            # Quick internet check before attempting
            import socket
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=2).close()
            except OSError:
                return

            # Get config for endpoint URL
            config = mw.addonManager.getConfig(ADDON_NAME) or {}
            endpoint_url = config.get("analytics_endpoint")

            # Skip if no endpoint configured
            if not endpoint_url:
                return

            # Get analytics data
            analytics = get_analytics_data()

            # Ensure user_id exists (migration for existing users)
            if not analytics.get("user_id"):
                analytics["user_id"] = str(uuid.uuid4())
                save_analytics_data(analytics)

            # Sync onboarding_completed from config (source of truth) to analytics
            config_onboarding = config.get("onboarding_completed", False)
            if config_onboarding and not analytics.get("onboarding_completed", False):
                analytics["onboarding_completed"] = True
                save_analytics_data(analytics)

            # Note: Server calculates engagement metrics from daily_usage
            # (total_sessions, sessions_with_messages, etc.)
            payload = {
                # Core metadata
                "user_id": analytics.get("user_id"),
                "first_install_date": analytics.get("first_install_date"),
                "platform": analytics.get("platform"),
                "locale": analytics.get("locale"),
                "timezone": analytics.get("timezone"),
                # Auth
                "has_logged_in": analytics.get("has_logged_in", False),
                "auth_button_clicked": analytics.get("auth_button_clicked"),
                # Onboarding & Tutorial
                "onboarding_completed": analytics.get("onboarding_completed", False),
                "tutorial_status": analytics.get("tutorial_status"),
                "tutorial_current_step": analytics.get("tutorial_current_step"),
                "tutorial_duration_seconds": analytics.get("tutorial_duration_seconds"),
                # AI feature usage (lifetime totals; per-session counts live in daily_usage)
                "ai_create_count": analytics.get("ai_create_count", 0),
                "ai_generate_count": analytics.get("ai_generate_count", 0),
                "ai_generate_cards_count": analytics.get("ai_generate_cards_count", 0),
                "explain_count": analytics.get("explain_count", 0),
                "ai_answer_count": analytics.get("ai_answer_count", 0),
                # Review tracking
                "has_shown_review": analytics.get("has_shown_review", False),
                "review_modal_status": analytics.get("review_modal_status"),
                "review_modal_seconds_open": analytics.get("review_modal_seconds_open"),
                "review_show_count": analytics.get("review_show_count", 0),
                "review_last_shown_date": analytics.get("review_last_shown_date"),
                "review_responded": analytics.get("review_responded"),  # "thumbs_up" / "thumbs_down" / null
                "review_engagement_at_last_show": analytics.get("review_engagement_at_last_show", 0),
                "review_history": analytics.get("review_history", []),  # [{show, date, status, seconds}, ...]
                # Session-based engagement (server calculates totals)
                "daily_usage": analytics.get("daily_usage", {}),
            }

            # Obfuscated API key (decode at runtime)
            import base64
            _k = 'YWlfcGFuZWxfYW5hbHl0aWNzX3NlY3VyZV9rZXlfMjAyNl9wcm9kX3Yx'
            decoded_key = base64.b64decode(_k).decode()

            # Send POST request with API key
            req = request.Request(
                endpoint_url,
                data=json.dumps(payload).encode('utf-8'),
                method='POST'
            )

            # Add headers explicitly (urllib can be finicky with custom headers)
            req.add_header('Content-Type', 'application/json')
            req.add_header('User-Agent', 'AI-Panel-Anki-Addon/1.0')
            req.add_header('Authorization', f'Bearer {decoded_key}')

            # Send with 10 second timeout
            with request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    # Update last sent timestamp
                    analytics["last_analytics_sent"] = datetime.now().isoformat()
                    save_analytics_data(analytics)

        except (error.URLError, error.HTTPError, Exception):
            # Silently fail on any error
            pass

    # Run in background thread
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


def ensure_today_tracked():
    """If Anki has been open across midnight, create a session entry for today."""
    global _current_session_index
    analytics = get_analytics_data()
    today = datetime.now().strftime("%Y-%m-%d")
    daily_usage = analytics.get("daily_usage", {})

    if today not in daily_usage:
        current_time = datetime.now().strftime("%H:%M:%S")
        daily_usage[today] = [{"time": current_time, "messages": 0}]
        _current_session_index = 0
        analytics["daily_usage"] = daily_usage
        save_analytics_data(analytics)


def try_send_daily_analytics():
    """Attempt to send analytics once per day (non-blocking)."""
    ensure_today_tracked()
    if should_send_analytics():
        send_analytics_background()
