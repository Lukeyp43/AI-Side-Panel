"""
Utility functions for The AI Panel add-on.
"""

import re


def clean_html_text(html_text):
    """Clean HTML text by removing tags and normalizing"""
    # Remove style tags and their contents first
    text = re.sub(r'<style[^>]*>.*?</style>', '', html_text, flags=re.DOTALL | re.IGNORECASE)

    # Remove script tags and their contents
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Strip remaining HTML tags
    text = re.sub('<[^<]+?>', '', text)

    # Decode HTML entities
    try:
        import html
        text = html.unescape(text)
    except:
        pass

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text


def format_keys_display(keys):
    """Format key list to display string with platform-specific symbols"""
    import sys
    if not keys:
        return "No keys"

    keycaps = []
    for key in keys:
        if key == "Control/Meta":
            keycaps.append("⌘" if sys.platform == "darwin" else "Ctrl")
        elif key == "Meta":
            keycaps.append("⌘")  # Cmd key on macOS
        elif key == "Control":
            keycaps.append("⌃" if sys.platform == "darwin" else "Ctrl")  # Control key
        elif key == "Shift":
            keycaps.append("⇧")
        elif key == "Alt":
            keycaps.append("⌥")
        else:
            keycaps.append(key)

    return " + ".join(keycaps)


def format_keys_verbose(keys):
    """Format keys with verbose display (e.g., '⌘ Cmd + ⇧ Shift')"""
    import sys
    display_keys = []
    for key in keys:
        if key == "Control/Meta":
            display_keys.append("⌘ Cmd" if sys.platform == "darwin" else "Ctrl")
        elif key == "Meta":
            display_keys.append("⌘ Cmd")  # Cmd key on macOS
        elif key == "Control":
            display_keys.append("⌃ Control" if sys.platform == "darwin" else "Ctrl")  # Control key
        elif key == "Shift":
            display_keys.append("⇧ Shift")
        elif key == "Alt":
            display_keys.append("⌥ Alt")
        else:
            display_keys.append(key)
    return "  +  ".join(display_keys)
