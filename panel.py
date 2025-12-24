"""
Main panel components for the OpenEvidence add-on.
Contains the CustomTitleBar, OpenEvidencePanel, and OnboardingWidget.
"""

import json
import webbrowser
from aqt import mw
from aqt.qt import *

try:
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                  QDockWidget, QStackedWidget)
    from PyQt6.QtCore import Qt, QUrl, QTimer, QByteArray, QSize
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QCursor, QColor
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile, QWebEnginePage
except ImportError:
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                  QDockWidget, QStackedWidget)
    from PyQt5.QtCore import Qt, QUrl, QTimer, QByteArray, QSize
    from PyQt5.QtGui import QIcon, QPixmap, QPainter, QCursor, QColor
    from PyQt5.QtSvg import QSvgRenderer
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage
        try:
            from PyQt5.QtWebEngineCore import QWebEngineProfile
        except ImportError:
            try:
                from PyQt5.QtWebEngineWidgets import QWebEngineProfile
            except:
                QWebEngineProfile = None
    except ImportError:
        from aqt.qt import QWebEngineView
        try:
            from aqt.qt import QWebEngineSettings, QWebEnginePage, QWebEngineProfile
        except:
            QWebEngineSettings = None
            QWebEnginePage = None
            QWebEngineProfile = None

from .settings import SettingsHomeView, SettingsListView, SettingsEditorView
import os


# Global persistent profile - must be kept alive for the entire session
_persistent_profile = None

def get_persistent_profile():
    """Get or create a persistent QWebEngineProfile for storing cookies/sessions"""
    global _persistent_profile

    if QWebEngineProfile is None:
        return None

    # Return existing profile if already created
    if _persistent_profile is not None:
        return _persistent_profile

    try:
        # Create a named profile to avoid off-the-record mode
        # Store in global to keep it alive for the entire session
        _persistent_profile = QWebEngineProfile("openevidence")

        # Set persistent cookies policy - saves both session and persistent cookies
        try:
            _persistent_profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        except:
            # Fallback for different Qt versions
            try:
                _persistent_profile.setPersistentCookiesPolicy(2)  # ForcePersistentCookies = 2
            except:
                pass

        # Set explicit storage paths to ensure persistence
        try:
            addon_dir = os.path.dirname(os.path.abspath(__file__))
            storage_path = os.path.join(addon_dir, "webengine_data")
            os.makedirs(storage_path, exist_ok=True)

            # Set persistent storage path for cookies and other data
            _persistent_profile.setPersistentStoragePath(storage_path)
            _persistent_profile.setCachePath(os.path.join(storage_path, "cache"))
        except:
            # If setting custom paths fails, continue with default paths
            pass

        return _persistent_profile
    except Exception as e:
        # If anything fails, return None and use default behavior
        print(f"OpenEvidence: Failed to create persistent profile: {e}")
        return None


class CustomTitleBar(QWidget):
    """Custom title bar with pointer cursor on buttons"""
    def __init__(self, dock_widget, parent=None):
        super().__init__(parent)
        self.dock_widget = dock_widget
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 4, 4)
        layout.setSpacing(2)

        # Back button with arrow icon (hidden by default)
        self.back_button = QPushButton()
        self.back_button.setFixedSize(24, 24)
        self.back_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_button.setVisible(False)  # Hidden by default

        # Create high-resolution SVG icon for back button
        back_icon_svg = """<?xml version="1.0" encoding="UTF-8"?>
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M30 12 L18 24 L30 36" stroke="white" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """

        # Render SVG at higher resolution for crisp display
        svg_bytes_back = QByteArray(back_icon_svg.encode())
        renderer_back = QSvgRenderer(svg_bytes_back)
        pixmap_back = QPixmap(48, 48)
        try:
            pixmap_back.fill(Qt.GlobalColor.transparent)
        except:
            pixmap_back.fill(Qt.transparent)
        painter_back = QPainter(pixmap_back)
        renderer_back.render(painter_back)
        painter_back.end()

        self.back_button.setIcon(QIcon(pixmap_back))
        self.back_button.setIconSize(QSize(14, 14))

        self.back_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.12);
            }
        """)
        self.back_button.clicked.connect(self.go_back)
        layout.addWidget(self.back_button)

        # Title label
        self.title_label = QLabel("OpenEvidence")
        self.title_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 13px; font-weight: 500;")
        layout.addWidget(self.title_label)

        # Add stretch to push buttons to the right
        layout.addStretch()

        # Float/Undock button with high-quality SVG icon
        self.float_button = QPushButton()
        self.float_button.setFixedSize(24, 24)
        self.float_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Create high-resolution SVG icon for float button
        float_icon_svg = """<?xml version="1.0" encoding="UTF-8"?>
        <svg width="48" height="48" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
            <path d="m22 7c0-.478-.379-1-1-1h-14c-.62 0-1 .519-1 1v14c0 .621.52 1 1 1h14c.478 0 1-.379 1-1zm-14.5.5h13v13h-13zm-5.5 7.5v2c0 .621.52 1 1 1h2v-1.5h-1.5v-1.5zm1.5-4.363v3.363h-1.5v-3.363zm0-4.637v3.637h-1.5v-3.637zm11.5-4v1.5h1.5v1.5h1.5v-2c0-.478-.379-1-1-1zm-10 0h-2c-.62 0-1 .519-1 1v2h1.5v-1.5h1.5zm4.5 1.5h-3.5v-1.5h3.5zm4.5 0h-3.5v-1.5h3.5z" fill-rule="nonzero"/>
        </svg>
        """

        # Render SVG at higher resolution for crisp display
        svg_bytes = QByteArray(float_icon_svg.encode())
        renderer = QSvgRenderer(svg_bytes)
        pixmap = QPixmap(48, 48)
        try:
            pixmap.fill(Qt.GlobalColor.transparent)
        except:
            pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        self.float_button.setIcon(QIcon(pixmap))
        self.float_button.setIconSize(QSize(14, 14))

        self.float_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.12);
            }
        """)
        self.float_button.clicked.connect(self.toggle_floating)
        layout.addWidget(self.float_button)

        # Settings/Gear button with high-quality SVG icon
        self.settings_button = QPushButton()
        self.settings_button.setFixedSize(24, 24)
        self.settings_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Create high-resolution minimalistic SVG icon for settings button
        settings_icon_svg = """<?xml version="1.0" encoding="UTF-8"?>
        <svg width="48" height="48" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill-rule="evenodd" clip-rule="evenodd">
            <path d="M12 8.666c-1.838 0-3.333 1.496-3.333 3.334s1.495 3.333 3.333 3.333 3.333-1.495 3.333-3.333-1.495-3.334-3.333-3.334m0 7.667c-2.39 0-4.333-1.943-4.333-4.333s1.943-4.334 4.333-4.334 4.333 1.944 4.333 4.334c0 2.39-1.943 4.333-4.333 4.333m-1.193 6.667h2.386c.379-1.104.668-2.451 2.107-3.05 1.496-.617 2.666.196 3.635.672l1.686-1.688c-.508-1.047-1.266-2.199-.669-3.641.567-1.369 1.739-1.663 3.048-2.099v-2.388c-1.235-.421-2.471-.708-3.047-2.098-.572-1.38.057-2.395.669-3.643l-1.687-1.686c-1.117.547-2.221 1.257-3.642.668-1.374-.571-1.656-1.734-2.1-3.047h-2.386c-.424 1.231-.704 2.468-2.099 3.046-.365.153-.718.226-1.077.226-.843 0-1.539-.392-2.566-.893l-1.687 1.686c.574 1.175 1.251 2.237.669 3.643-.571 1.375-1.734 1.654-3.047 2.098v2.388c1.226.418 2.468.705 3.047 2.098.581 1.403-.075 2.432-.669 3.643l1.687 1.687c1.45-.725 2.355-1.204 3.642-.669 1.378.572 1.655 1.738 2.1 3.047m3.094 1h-3.803c-.681-1.918-.785-2.713-1.773-3.123-1.005-.419-1.731.132-3.466.952l-2.689-2.689c.873-1.837 1.367-2.465.953-3.465-.412-.991-1.192-1.087-3.123-1.773v-3.804c1.906-.678 2.712-.782 3.123-1.773.411-.991-.071-1.613-.953-3.466l2.689-2.688c1.741.828 2.466 1.365 3.465.953.992-.412 1.082-1.185 1.775-3.124h3.802c.682 1.918.788 2.714 1.774 3.123 1.001.416 1.709-.119 3.467-.952l2.687 2.688c-.878 1.847-1.361 2.477-.952 3.465.411.992 1.192 1.087 3.123 1.774v3.805c-1.906.677-2.713.782-3.124 1.773-.403.975.044 1.561.954 3.464l-2.688 2.689c-1.728-.82-2.467-1.37-3.456-.955-.988.41-1.08 1.146-1.785 3.126" fill="white"/>
        </svg>
        """

        # Render SVG at higher resolution for crisp display
        svg_bytes_settings = QByteArray(settings_icon_svg.encode())
        renderer_settings = QSvgRenderer(svg_bytes_settings)
        pixmap_settings = QPixmap(48, 48)
        try:
            pixmap_settings.fill(Qt.GlobalColor.transparent)
        except:
            pixmap_settings.fill(Qt.transparent)
        painter_settings = QPainter(pixmap_settings)
        renderer_settings.render(painter_settings)
        painter_settings.end()

        self.settings_button.setIcon(QIcon(pixmap_settings))
        self.settings_button.setIconSize(QSize(14, 14))

        self.settings_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.12);
            }
        """)
        self.settings_button.clicked.connect(self.toggle_settings)
        layout.addWidget(self.settings_button)

        # Close button with high-quality SVG icon
        self.close_button = QPushButton()
        self.close_button.setFixedSize(24, 24)
        self.close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Create high-resolution SVG icon for close button
        close_icon_svg = """<?xml version="1.0" encoding="UTF-8"?>
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 8 L40 40 M40 8 L8 40" stroke="white" stroke-width="4" stroke-linecap="round"/>
        </svg>
        """

        # Render SVG at higher resolution for crisp display
        svg_bytes_close = QByteArray(close_icon_svg.encode())
        renderer_close = QSvgRenderer(svg_bytes_close)
        pixmap_close = QPixmap(48, 48)
        try:
            pixmap_close.fill(Qt.GlobalColor.transparent)
        except:
            pixmap_close.fill(Qt.transparent)
        painter_close = QPainter(pixmap_close)
        renderer_close.render(painter_close)
        painter_close.end()

        self.close_button.setIcon(QIcon(pixmap_close))
        self.close_button.setIconSize(QSize(14, 14))

        self.close_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.2);
            }
        """)
        self.close_button.clicked.connect(self.dock_widget.hide)
        layout.addWidget(self.close_button)

        # Set background color for title bar - modern dark gray
        self.setStyleSheet("background: #2a2a2a; border-bottom: 1px solid rgba(255, 255, 255, 0.06);")

    def toggle_floating(self):
        self.dock_widget.setFloating(not self.dock_widget.isFloating())

    def toggle_settings(self):
        """Toggle between web view and settings view"""
        panel = self.dock_widget.widget()
        if panel and hasattr(panel, 'toggle_settings_view'):
            panel.toggle_settings_view()

    def go_back(self):
        """Context-aware back navigation"""
        panel = self.dock_widget.widget()
        if panel and hasattr(panel, 'go_back'):
            panel.go_back()

    def set_state(self, is_settings):
        """Update title bar state based on current view

        Args:
            is_settings: True for settings view, False for web view
        """
        if is_settings:
            # Settings mode
            self.title_label.setText("Settings")
            self.back_button.setVisible(True)
            self.settings_button.setVisible(False)
        else:
            # Web view mode
            self.title_label.setText("OpenEvidence")
            self.back_button.setVisible(False)
            self.settings_button.setVisible(True)


class OpenEvidencePanel(QWidget):
    """Main panel containing the web view and settings views"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Set minimum width to prevent panel from becoming too narrow
        self.setMinimumWidth(280)

        # Create stacked widget to switch between views
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        # Create web view container with loading overlay
        self.web_container = QWidget()
        web_layout = QVBoxLayout(self.web_container)
        web_layout.setContentsMargins(0, 0, 0, 0)

        # Create loading overlay first (so it's on top in z-order)
        self.loading_overlay = QWebEngineView(self.web_container)
        self.loading_overlay.setStyleSheet("QWebEngineView { background: #1e1e1e; }")
        
        # Loading HTML with rolling dots animation
        loading_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    background: #1e1e1e;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    overflow: hidden;
                }
                .loader {
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    display: block;
                    position: relative;
                    color: #FFF;
                    left: -100px;
                    box-sizing: border-box;
                    animation: shadowRolling 2s linear infinite;
                }
                @keyframes shadowRolling {
                    0% {
                        box-shadow: 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0);
                    }
                    12% {
                        box-shadow: 100px 0 white, 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0);
                    }
                    25% {
                        box-shadow: 110px 0 white, 100px 0 white, 0px 0 rgba(255, 255, 255, 0), 0px 0 rgba(255, 255, 255, 0);
                    }
                    36% {
                        box-shadow: 120px 0 white, 110px 0 white, 100px 0 white, 0px 0 rgba(255, 255, 255, 0);
                    }
                    50% {
                        box-shadow: 130px 0 white, 120px 0 white, 110px 0 white, 100px 0 white;
                    }
                    62% {
                        box-shadow: 200px 0 rgba(255, 255, 255, 0), 130px 0 white, 120px 0 white, 110px 0 white;
                    }
                    75% {
                        box-shadow: 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0), 130px 0 white, 120px 0 white;
                    }
                    87% {
                        box-shadow: 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0), 130px 0 white;
                    }
                    100% {
                        box-shadow: 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0), 200px 0 rgba(255, 255, 255, 0);
                    }
                }
            </style>
        </head>
        <body>
            <span class="loader"></span>
        </body>
        </html>
        """
        self.loading_overlay.setHtml(loading_html)
        
        # Create web view for OpenEvidence
        self.web = QWebEngineView(self.web_container)

        # Set up persistent profile for cookies/session storage
        persistent_profile = get_persistent_profile()
        if persistent_profile and QWebEnginePage:
            # Create a page with the persistent profile
            page = QWebEnginePage(persistent_profile, self.web)
            self.web.setPage(page)

        # Configure settings for faster loading and better preloading
        if QWebEngineSettings:
            try:
                # Prevent stealing focus
                self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, False)
                # Enable features that speed up loading
                self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
                self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            except:
                pass

        self.web.setStyleSheet("QWebEngineView { background: #1e1e1e; }")
        
        # Set explicit size to ensure Qt allocates resources and starts loading immediately
        self.web.setMinimumSize(300, 400)
        
        # Add both to layout - stacked on top of each other
        web_layout.addWidget(self.web)
        web_layout.addWidget(self.loading_overlay)
        
        # Initially show only the loader
        self.web.hide()
        self.loading_overlay.show()
        self.loading_overlay.raise_()

        # Connect to load finished to check if page is ready
        self.web.loadFinished.connect(self.on_page_load_finished)
        
        # Start loading OpenEvidence immediately (even though panel is hidden)
        # This enables preloading: the page loads in the background while Anki starts,
        # so it's ready instantly when the user clicks the book icon
        self.web.load(QUrl("https://www.openevidence.com/"))

        # Create settings home view (main settings hub)
        self.settings_view = SettingsHomeView(self)

        # Add views to stacked widget
        self.stacked_widget.addWidget(self.web_container)  # Index 0
        self.stacked_widget.addWidget(self.settings_view)  # Index 1

        # Start with web view
        self.stacked_widget.setCurrentIndex(0)

    def on_page_load_finished(self, ok):
        """Called when page HTML is loaded - check if fully ready"""
        if not ok:
            # Load failed, hide overlay anyway
            if hasattr(self, 'loading_overlay'):
                self.loading_overlay.hide()
            return

        # Add a small delay before first JavaScript call to ensure profile is initialized
        # This prevents crashes with custom profiles
        QTimer.singleShot(100, self._check_page_ready)

    def _check_page_ready(self):
        """Check if page is ready (called after small delay)"""
        # Check if page is truly ready (all resources loaded)
        check_ready_js = """
        (function() {
            // Check if document is fully loaded and OpenEvidence elements exist
            if (document.readyState === 'complete') {
                // Check for OpenEvidence specific elements that indicate page is ready
                var searchInput = document.querySelector('input[placeholder*="medical"], input[placeholder*="question"], textarea');
                var logo = document.querySelector('img, svg');

                // If we found key elements, page is ready
                if (searchInput || logo) {
                    return true;
                }
            }
            return false;
        })();
        """

        # Check if page is ready with error handling
        try:
            self.web.page().runJavaScript(check_ready_js, self.handle_ready_check)
        except Exception as e:
            print(f"OpenEvidence: Error checking page ready: {e}")
            # Fallback - just hide loader and show web view
            if hasattr(self, 'loading_overlay'):
                self.loading_overlay.hide()
            self.web.show()
    
    def handle_ready_check(self, is_ready):
        """Handle the result of page ready check"""
        if is_ready:
            # Page is ready - hide loader, show web view
            if hasattr(self, 'loading_overlay'):
                self.loading_overlay.hide()
            self.web.show()
            self.inject_shift_key_listener()
        else:
            # Not ready yet, check again after a short delay
            QTimer.singleShot(200, lambda: self.web.page().runJavaScript(
                """
                (function() {
                    if (document.readyState === 'complete') {
                        var searchInput = document.querySelector('input[placeholder*="medical"], input[placeholder*="question"], textarea');
                        var logo = document.querySelector('img, svg');
                        if (searchInput || logo) return true;
                    }
                    return false;
                })();
                """,
                self.handle_ready_check
            ))

    def _update_title_bar(self, is_settings):
        """Update title bar state"""
        # Access parent dock widget's title bar
        dock = self.parent()
        if dock:
            title_bar = dock.titleBarWidget()
            if title_bar and hasattr(title_bar, 'set_state'):
                title_bar.set_state(is_settings)

    def go_back(self):
        """Context-aware back navigation"""
        current_index = self.stacked_widget.currentIndex()
        if current_index == 1:
            # We're in a settings view, check which one
            current_widget = self.stacked_widget.widget(1)
            # Import here to avoid circular import at module level
            from .settings import SettingsEditorView, SettingsListView, SettingsHomeView

            if isinstance(current_widget, SettingsEditorView):
                # In editor view, discard changes and go back to templates list view
                if hasattr(current_widget, 'discard_and_go_back'):
                    current_widget.discard_and_go_back()
                else:
                    self.show_templates_view()
            elif isinstance(current_widget, SettingsListView):
                # In templates list view, go back to settings home
                self.show_home_view()
            elif isinstance(current_widget, SettingsHomeView):
                # In settings home, go back to web view
                self.show_web_view()
            else:
                # Default: go to web view
                self.show_web_view()
        else:
            # Default: go to web view
            self.show_web_view()

    def toggle_settings_view(self):
        """Toggle between web view and settings home view"""
        current = self.stacked_widget.currentIndex()
        if current == 0:
            # Switch to settings home
            self.show_home_view()
        else:
            # Switch back to web
            self.show_web_view()

    def show_web_view(self):
        """Show the web view"""
        self.stacked_widget.setCurrentIndex(0)
        self._update_title_bar(False)

    def show_home_view(self):
        """Show the settings home view"""
        # Get current widget at index 1
        current_widget = self.stacked_widget.widget(1)

        # Import here to avoid circular import at module level
        from .settings import SettingsHomeView

        # If it's already a SettingsHomeView, just show it
        if current_widget and isinstance(current_widget, SettingsHomeView):
            self.stacked_widget.setCurrentIndex(1)
            self._update_title_bar(True)
            return

        # Otherwise, remove whatever is there and create new home view
        if current_widget:
            self.stacked_widget.removeWidget(current_widget)
            current_widget.deleteLater()

        # Create new home view
        self.settings_view = SettingsHomeView(self)
        self.stacked_widget.addWidget(self.settings_view)
        self.stacked_widget.setCurrentIndex(1)
        self._update_title_bar(True)

    def show_templates_view(self):
        """Show the templates list view"""
        # Get current widget at index 1
        current_widget = self.stacked_widget.widget(1)

        # Import here to avoid circular import at module level
        from .settings import SettingsListView

        # If it's already a SettingsListView, just refresh it and show it
        if current_widget and isinstance(current_widget, SettingsListView):
            current_widget.load_keybindings()
            self.stacked_widget.setCurrentIndex(1)
            self._update_title_bar(True)
            return

        # Otherwise, remove whatever is there and create new templates list view
        if current_widget:
            self.stacked_widget.removeWidget(current_widget)
            current_widget.deleteLater()

        # Create new templates list view
        self.settings_view = SettingsListView(self)
        self.stacked_widget.addWidget(self.settings_view)
        self.stacked_widget.setCurrentIndex(1)
        self._update_title_bar(True)

    def show_quick_actions_view(self):
        """Show the quick actions settings view"""
        # Get current widget at index 1
        current_widget = self.stacked_widget.widget(1)

        # Import here to avoid circular import at module level
        from .settings_quick_actions import QuickActionsSettingsView

        # If it's already a QuickActionsSettingsView, just show it
        if current_widget and isinstance(current_widget, QuickActionsSettingsView):
            self.stacked_widget.setCurrentIndex(1)
            self._update_title_bar(True)
            return

        # Otherwise, remove whatever is there and create new quick actions view
        if current_widget:
            self.stacked_widget.removeWidget(current_widget)
            current_widget.deleteLater()

        # Create new quick actions view
        self.settings_view = QuickActionsSettingsView(self)
        self.stacked_widget.addWidget(self.settings_view)
        self.stacked_widget.setCurrentIndex(1)
        self._update_title_bar(True)

    def show_list_view(self):
        """Show the settings list view (alias for show_templates_view for backward compatibility)"""
        self.show_templates_view()

    def show_editor_view(self, keybinding, index):
        """Show the settings editor view"""
        editor_view = SettingsEditorView(self, keybinding, index)
        # Remove settings list and add editor
        old_settings = self.settings_view
        self.stacked_widget.removeWidget(old_settings)
        old_settings.deleteLater()
        self.stacked_widget.addWidget(editor_view)
        self.stacked_widget.setCurrentIndex(1)
        self._update_title_bar(True)

    def inject_shift_key_listener(self):
        """Inject JavaScript to listen for custom keybindings"""
        # First, update the keybindings in the global variable
        self.update_keybindings_in_js()

        # Only inject the listener once - it will read from window.ankiKeybindings
        listener_js = """
        (function() {
            // Only inject if not already injected
            if (window.ankiKeybindingListenerInjected) {
                console.log('Anki: Keybinding listener already exists, skipping injection');
                return;
            }

            console.log('Anki: Injecting custom keybinding listener for OpenEvidence');
            window.ankiKeybindingListenerInjected = true;

            // Helper to check if pressed keys match keybinding
            function keysMatch(event, requiredKeys) {
                var pressedKeys = {};

                if (event.shiftKey) pressedKeys['Shift'] = true;
                
                // On macOS, browser events have the keys correct:
                // - event.metaKey = Cmd key (⌘) → should match "Meta"
                // - event.ctrlKey = Control key (⌃) → should match "Control"
                // On other platforms, treat them the same for cross-platform compatibility
                var isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
                if (isMac) {
                    if (event.ctrlKey) pressedKeys['Control'] = true;
                    if (event.metaKey) pressedKeys['Meta'] = true;
                } else {
                    if (event.ctrlKey || event.metaKey) pressedKeys['Control/Meta'] = true;
                }
                
                if (event.altKey) pressedKeys['Alt'] = true;

                // Add regular key if present
                if (event.key && event.key.length === 1) {
                    pressedKeys[event.key.toUpperCase()] = true;
                }

                // Check if all required keys are pressed
                for (var i = 0; i < requiredKeys.length; i++) {
                    if (!pressedKeys[requiredKeys[i]]) {
                        return false;
                    }
                }

                // Check we don't have extra modifier keys
                var expectedCount = requiredKeys.length;
                var actualCount = Object.keys(pressedKeys).length;

                return actualCount === expectedCount;
            }

            // Helper to insert text at cursor position
            function fillInputField(activeElement, text) {
                // Get current value and cursor position
                var currentValue = activeElement.value || '';
                var cursorPos = activeElement.selectionStart || 0;

                // Insert text at cursor position
                var newValue = currentValue.substring(0, cursorPos) + text + currentValue.substring(activeElement.selectionEnd || cursorPos);

                // Use proper setter that React/Vue can detect
                var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype,
                    'value'
                ).set;
                var nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype,
                    'value'
                ).set;

                if (activeElement.tagName === 'INPUT') {
                    nativeInputValueSetter.call(activeElement, newValue);
                } else if (activeElement.tagName === 'TEXTAREA') {
                    nativeTextAreaValueSetter.call(activeElement, newValue);
                }

                // Set cursor position after inserted text
                var newCursorPos = cursorPos + text.length;
                activeElement.setSelectionRange(newCursorPos, newCursorPos);

                // Dispatch proper input event that React recognizes
                var inputEvent = new InputEvent('input', {
                    bubbles: true,
                    cancelable: true,
                    inputType: 'insertText',
                    data: text
                });
                activeElement.dispatchEvent(inputEvent);

                // Also dispatch change event
                var changeEvent = new Event('change', { bubbles: true });
                activeElement.dispatchEvent(changeEvent);

                // Dispatch keyup event to trigger any validation
                var keyupEvent = new KeyboardEvent('keyup', {
                    bubbles: true,
                    cancelable: true,
                    key: ' ',
                    code: 'Space'
                });
                activeElement.dispatchEvent(keyupEvent);
            }

            // Listen for keyboard shortcuts on the entire document
            document.addEventListener('keydown', function(event) {
                // Check if the ACTIVE ELEMENT is specifically the OpenEvidence search input
                var activeElement = document.activeElement;

                // Make sure we're in an input/textarea element
                var isInputElement = activeElement && (
                    activeElement.tagName === 'INPUT' ||
                    activeElement.tagName === 'TEXTAREA'
                );

                // Make sure it's specifically the OpenEvidence search box
                var isOpenEvidenceSearchBox = false;
                if (isInputElement) {
                    var placeholder = activeElement.placeholder || '';
                    var type = activeElement.type || '';

                    isOpenEvidenceSearchBox = (
                        placeholder.toLowerCase().includes('medical') ||
                        placeholder.toLowerCase().includes('question') ||
                        type === 'text' ||
                        activeElement.tagName === 'TEXTAREA'
                    );
                }

                // Only proceed if in OpenEvidence search box
                if (!isInputElement || !isOpenEvidenceSearchBox) {
                    return;
                }

                // Read keybindings from global variable (updated from Python)
                var keybindings = window.ankiKeybindings || [];

                // Check each keybinding
                for (var i = 0; i < keybindings.length; i++) {
                    var binding = keybindings[i];

                    if (keysMatch(event, binding.keys)) {
                        console.log('Anki: Keybinding "' + binding.name + '" triggered');
                        event.preventDefault();

                        // Get the appropriate text for this keybinding
                        if (window.ankiCardTexts && window.ankiCardTexts[i]) {
                            fillInputField(activeElement, window.ankiCardTexts[i]);
                            console.log('Anki: Filled search box with card text using React-compatible events');
                        } else {
                            console.log('Anki: No card text available for this keybinding');
                        }

                        break; // Only trigger first matching keybinding
                    }
                }
            }, true);
        })();
        """

        try:
            self.web.page().runJavaScript(listener_js)
        except Exception as e:
            print(f"OpenEvidence: Error injecting listener: {e}")

        # Also inject the current card texts
        self.update_card_text_in_js()

    def update_keybindings_in_js(self):
        """Update the keybindings in the JavaScript context without re-injecting the listener"""
        # Get keybindings from config
        config = mw.addonManager.getConfig(__name__) or {}
        keybindings = config.get("keybindings", [])

        # If no keybindings, add default
        if not keybindings:
            keybindings = [
                {
                    "name": "Standard Explain",
                    "keys": ["Control", "Shift", "S"],
                    "question_template": "Can you explain this to me:\n\n{front}",
                    "answer_template": "Can you explain this to me:\n\nQuestion:\n{front}\n\nAnswer:\n{back}"
                },
                {
                    "name": "Front/Back",
                    "keys": ["Control", "Shift", "Q"],
                    "question_template": "{front}",
                    "answer_template": "{front}"
                },
                {
                    "name": "Back Only",
                    "keys": ["Control", "Shift", "A"],
                    "question_template": "",
                    "answer_template": "{back}"
                }
            ]

        # Convert keybindings to JSON and inject
        keybindings_json = json.dumps(keybindings)
        js_code = f"window.ankiKeybindings = {keybindings_json};"
        try:
            self.web.page().runJavaScript(js_code)
        except Exception as e:
            print(f"OpenEvidence: Error updating keybindings: {e}")

    def update_card_text_in_js(self):
        """Update the card texts in the JavaScript context for all keybindings"""
        # Import here to avoid circular imports
        from . import current_card_question, current_card_answer, is_showing_answer

        # Get keybindings from config
        config = mw.addonManager.getConfig(__name__) or {}
        keybindings = config.get("keybindings", [])

        # If no keybindings, add default
        if not keybindings:
            keybindings = [
                {
                    "name": "Standard Explain",
                    "keys": ["Control", "Shift", "S"],
                    "question_template": "Can you explain this to me:\n\n{front}",
                    "answer_template": "Can you explain this to me:\n\nQuestion:\n{front}\n\nAnswer:\n{back}"
                },
                {
                    "name": "Front/Back",
                    "keys": ["Control", "Shift", "Q"],
                    "question_template": "{front}",
                    "answer_template": "{front}"
                },
                {
                    "name": "Back Only",
                    "keys": ["Control", "Shift", "A"],
                    "question_template": "",
                    "answer_template": "{back}"
                }
            ]

        # Generate text for each keybinding
        card_texts = []
        for kb in keybindings:
            if is_showing_answer:
                # Use answer template
                template = kb.get("answer_template", "")
                text = template.replace("{front}", current_card_question).replace("{back}", current_card_answer)
            else:
                # Use question template
                template = kb.get("question_template", "")
                text = template.replace("{front}", current_card_question)

            card_texts.append(text)

        # Convert to JSON and inject
        if card_texts:
            texts_json = json.dumps(card_texts)
            js_code = f"window.ankiCardTexts = {texts_json};"
            try:
                self.web.page().runJavaScript(js_code)
            except Exception as e:
                print(f"OpenEvidence: Error updating card texts: {e}")


class OnboardingWidget(QWidget):
    """Onboarding widget shown in the side panel"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.step_completed = False
        self.setup_ui()

    def set_icon_from_svg(self, label, svg_str, size=20, color=None):
        """Helper to set SVG icon to a label"""
        # Render at high resolution (4x scale) for crisp display on Retina/HighDPI
        render_size = size * 4

        svg_bytes = QByteArray(svg_str.encode())
        renderer = QSvgRenderer(svg_bytes)
        pixmap = QPixmap(render_size, render_size)
        try:
            pixmap.fill(Qt.GlobalColor.transparent)
        except:
            pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        # Set scalable contents on label so it downscales the high-res pixmap
        label.setPixmap(pixmap)
        label.setScaledContents(True)

    def setup_ui(self):
        # Main outer layout - positions content at "optical center" (15% from top)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Add spacing at top (15% of typical height ~600px = 90px)
        outer_layout.addSpacing(90)

        # THE INVISIBLE COLUMN - Container with fixed width (380px)
        container = QWidget()
        container.setMaximumWidth(380)
        container.setStyleSheet("background: transparent;")

        # Inner layout for the container
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # HEADER SECTION - Title and Creator grouped close together
        # Title
        title = QLabel("OpenEvidence Add-On")
        title.setStyleSheet("""
            font-size: 26px;
            font-weight: 700;
            color: #FFFFFF;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0px 0px 8px 0px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Creator name
        creator = QLabel("Created by Luke Pettit")
        creator.setStyleSheet("""
            font-size: 14px;
            color: #777777;
            font-weight: 500;
        """)
        creator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(creator)

        # Gap after header (32px)
        layout.addSpacing(32)

        # CONTENT SECTION - Description text (LEFT-ALIGNED to match box edge)
        description = QLabel("To enable this add-on, please support this project by giving us a free star on GitHub.")
        description.setWordWrap(True)
        description.setStyleSheet("""
            font-size: 15px;
            color: #BBBBBB;
            font-weight: 400;
            line-height: 1.5;
            padding-left: 2px;
        """)
        description.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(description)

        # Small gap before checkbox (20px)
        layout.addSpacing(20)

        # CHECKBOX ROW - custom widget using QPushButton for layout control
        self.star_btn = QPushButton()
        self.star_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.star_btn.setFixedHeight(54)
        self.star_btn.setStyleSheet("""
            QPushButton {
                background: #2b2b2b;
                border: 1px solid #444444;
                border-radius: 8px;
                text-align: left;
            }
            QPushButton:hover {
                background: #3a3a3a;
                border-color: #666666;
            }
        """)

        # Layout for the button content
        btn_layout = QHBoxLayout(self.star_btn)
        btn_layout.setContentsMargins(16, 0, 16, 0)
        btn_layout.setSpacing(12)

        # 1. Checkbox Icon
        self.checkbox_label = QLabel()
        self.checkbox_label.setFixedSize(20, 20)
        self.checkbox_label.setStyleSheet("background: transparent; border: none;")
        self.checkbox_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # SVG for empty checkbox
        empty_checkbox_svg = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="2" y="2" width="20" height="20" rx="5" stroke="#FFFFFF" stroke-width="2"/>
        </svg>"""
        self.set_icon_from_svg(self.checkbox_label, empty_checkbox_svg)
        btn_layout.addWidget(self.checkbox_label)

        # 2. Text
        self.star_text = QLabel("Star on GitHub")
        self.star_text.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: 500; border: none; background: transparent;")
        self.star_text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        btn_layout.addWidget(self.star_text)

        # 3. Spacer to push arrow to the right
        btn_layout.addStretch()

        # 4. Arrow Icon
        self.arrow_label = QLabel()
        self.arrow_label.setFixedSize(20, 20)
        self.arrow_label.setStyleSheet("background: transparent; border: none;")
        self.arrow_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # SVG for external link arrow
        arrow_svg = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="7" y1="17" x2="17" y2="7"></line>
            <polyline points="7 7 17 7 17 17"></polyline>
        </svg>"""
        self.set_icon_from_svg(self.arrow_label, arrow_svg)
        btn_layout.addWidget(self.arrow_label)

        self.star_btn.clicked.connect(self.on_star_clicked)
        layout.addWidget(self.star_btn)

        # Gap before Next button (16px)
        layout.addSpacing(16)

        # BIG NEXT BUTTON - Grayed out "locked" state
        self.continue_btn = QPushButton("Next →")
        self.continue_btn.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
        self.continue_btn.setEnabled(False)
        self.continue_btn.setStyleSheet("""
            QPushButton {
                background: #333333;
                color: #666666;
                border: 1px solid #444444;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                padding: 16px;
            }
        """)
        self.continue_btn.clicked.connect(self.on_continue_clicked)
        layout.addWidget(self.continue_btn)

        # Add the container to the outer layout (horizontally centered)
        outer_layout.addWidget(container, 0, Qt.AlignmentFlag.AlignHCenter)
        outer_layout.addStretch(1)

    def on_star_clicked(self):
        if not self.step_completed:
            webbrowser.open("https://github.com/Lukeyp43/Anki-OpenEvidence-Add-On")

            # Disable button to prevent multiple clicks, but keep it looking active
            self.star_btn.setEnabled(False)

            # Wait 4 seconds before showing success state
            QTimer.singleShot(4000, self.finalize_onboarding_step)

    def finalize_onboarding_step(self):
        if not self.step_completed:
            self.step_completed = True

            # Update Star Button to checked state (Dark Gray background, Checkbox turns blue with checkmark)
            # Re-enable button but cursor changes
            self.star_btn.setEnabled(True)
            self.star_btn.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            # Remove hover effect by setting same background
            self.star_btn.setStyleSheet("""
                QPushButton {
                    background: #2b2b2b;
                    border: 1px solid #444444;
                    border-radius: 8px;
                    text-align: left;
                }
            """)

            # Update icons/text for checked state

            # 1. Checkbox becomes filled blue square with checkmark
            filled_check_svg = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="2" width="20" height="20" rx="5" fill="#3498db"/>
                <polyline points="16 9 10 15 7 12" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>"""
            self.set_icon_from_svg(self.checkbox_label, filled_check_svg)

            # Update Continue Button to UNLOCKED state (Bright Blue)
            self.continue_btn.setEnabled(True)
            self.continue_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.continue_btn.setStyleSheet("""
                QPushButton {
                    background: #3498db;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: 600;
                    padding: 16px;
                }
                QPushButton:hover {
                    background: #5dade2;
                }
            """)

    def on_continue_clicked(self):
        # Save config
        config = mw.addonManager.getConfig(__name__) or {}
        config["onboarding_completed"] = True
        mw.addonManager.writeConfig(__name__, config)

        # Replace widget with actual OpenEvidence panel
        from . import dock_widget
        if dock_widget:
            panel = OpenEvidencePanel()
            dock_widget.setWidget(panel)
