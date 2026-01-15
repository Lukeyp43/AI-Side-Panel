"""
Settings UI for The AI Panel add-on.
Contains the drill-down settings interface with list and editor views.

This module re-exports all settings components from their individual modules
for backward compatibility.
"""

# Import all settings components from their individual modules
from .settings_utils import ElidedLabel
from .settings_home import SettingsHomeView
from .settings_editor import SettingsEditorView
from .settings_list import SettingsListView

# Export all components for backward compatibility
__all__ = [
    'ElidedLabel',
    'SettingsHomeView',
    'SettingsEditorView',
    'SettingsListView',
]
