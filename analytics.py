from datetime import datetime, timedelta
from typing import Dict, Optional
from aqt import mw
import sys
import json
import threading
from urllib import request, error


ADDON_NAME = "the_ai_panel"


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
    """Initialize analytics on first run."""
    analytics = get_analytics_data()

    if not analytics.get("first_install_date"):
        # Get locale info
        locale_info = get_locale_info()

        analytics["first_install_date"] = datetime.now().isoformat()
        analytics["platform"] = sys.platform  # darwin, win32, linux
        analytics["locale"] = locale_info.get("locale")  # e.g., "en_US"
        analytics["timezone"] = locale_info.get("timezone")  # e.g., "PST"
        analytics["total_uses"] = 0
        analytics["daily_usage"] = {}  # Format: {"2026-01-14": count}
        analytics["last_used_date"] = None
        analytics["signup_method"] = None  # "sidebar_button" or "organic"
        analytics["has_logged_in"] = False
        analytics["auth_button_clicked"] = None  # "signup" or "login"

        # Onboarding & Tutorial tracking
        analytics["onboarding_completed"] = False
        analytics["tutorial_status"] = None  # null/true/"skip"/"skipped_midway"
        analytics["tutorial_current_step"] = None  # e.g., "1/36"

        # Usage tracking
        analytics["quick_action_usage_count"] = 0
        analytics["shortcut_usage_count"] = 0

        save_analytics_data(analytics)


def track_usage():
    """Track a usage event (called when panel is opened or template used)."""
    analytics = get_analytics_data()
    today = datetime.now().strftime("%Y-%m-%d")

    # Increment total uses
    analytics["total_uses"] = analytics.get("total_uses", 0) + 1

    # Increment daily count
    daily_usage = analytics.get("daily_usage", {})
    daily_usage[today] = daily_usage.get(today, 0) + 1
    analytics["daily_usage"] = daily_usage

    # Update last used date
    analytics["last_used_date"] = today

    # Clean up old daily data (keep last 90 days for retention analysis)
    cleanup_old_daily_data(analytics)

    save_analytics_data(analytics)


def track_signup_click(method: str = "sidebar_button"):
    """
    Track when user clicks signup/login.

    Args:
        method: "sidebar_button" if they clicked the button, "organic" if navigated on their own
    """
    analytics = get_analytics_data()

    if not analytics.get("signup_method"):
        analytics["signup_method"] = method
        analytics["signup_date"] = datetime.now().isoformat()

    save_analytics_data(analytics)


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


def track_quick_action_used():
    """Track when user uses a quick action (Meta+F or Meta+R)."""
    analytics = get_analytics_data()
    analytics["quick_action_usage_count"] = analytics.get("quick_action_usage_count", 0) + 1
    save_analytics_data(analytics)


def track_shortcut_used():
    """Track when user uses a shortcut (Ctrl+Shift+S/Q/A)."""
    analytics = get_analytics_data()
    analytics["shortcut_usage_count"] = analytics.get("shortcut_usage_count", 0) + 1
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


def get_retention_metrics() -> Dict:
    """
    Calculate retention metrics.

    Returns:
        Dict with retention stats like days_since_install, active_days, etc.
    """
    analytics = get_analytics_data()

    if not analytics.get("first_install_date"):
        return {}

    first_install = datetime.fromisoformat(analytics["first_install_date"])
    days_since_install = (datetime.now() - first_install).days

    daily_usage = analytics.get("daily_usage", {})
    active_days = len(daily_usage)

    # Calculate retention rate
    retention_rate = (active_days / max(days_since_install, 1)) * 100 if days_since_install > 0 else 0

    return {
        "days_since_install": days_since_install,
        "active_days": active_days,
        "total_uses": analytics.get("total_uses", 0),
        "retention_rate": round(retention_rate, 2),
        "last_used": analytics.get("last_used_date"),
        "has_logged_in": analytics.get("has_logged_in", False),
        "signup_method": analytics.get("signup_method"),
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
            # Get config for endpoint URL
            config = mw.addonManager.getConfig(ADDON_NAME) or {}
            endpoint_url = config.get("analytics_endpoint")

            # Skip if no endpoint configured
            if not endpoint_url:
                return

            # Get analytics data
            analytics = get_analytics_data()

            # Note: Server now calculates retention from active_dates array
            payload = {
                "first_install_date": analytics.get("first_install_date"),
                "platform": analytics.get("platform"),
                "locale": analytics.get("locale"),
                "timezone": analytics.get("timezone"),
                "total_uses": analytics.get("total_uses", 0),
                "has_logged_in": analytics.get("has_logged_in", False),
                "signup_method": analytics.get("signup_method"),
                "auth_button_clicked": analytics.get("auth_button_clicked"),
                "last_used_date": analytics.get("last_used_date"),
                # Onboarding & Tutorial
                "onboarding_completed": analytics.get("onboarding_completed", False),
                "tutorial_status": analytics.get("tutorial_status"),
                "tutorial_current_step": analytics.get("tutorial_current_step"),
                # Usage tracking
                "quick_action_usage_count": analytics.get("quick_action_usage_count", 0),
                "shortcut_usage_count": analytics.get("shortcut_usage_count", 0),
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


def try_send_daily_analytics():
    """Attempt to send analytics once per day (non-blocking)."""
    if should_send_analytics():
        send_analytics_background()
