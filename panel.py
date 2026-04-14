import json
import webbrowser
from aqt import mw
from aqt.qt import *

from aqt.qt import *
from .utils import ADDON_NAME

try:
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                  QDockWidget, QStackedWidget, QGraphicsDropShadowEffect)
    from PyQt6.QtCore import Qt, QUrl, QTimer, QByteArray, QSize, QEvent
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QCursor, QColor
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile, QWebEnginePage
except ImportError:
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                  QDockWidget, QStackedWidget, QGraphicsDropShadowEffect)
    from PyQt5.QtCore import Qt, QUrl, QTimer, QByteArray, QSize, QEvent
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
from .theme_manager import ThemeManager
import os


# Custom WebEnginePage to intercept console messages for analytics
class TutorialAwarePage(QWebEnginePage):
    """Custom page that intercepts JavaScript console messages for analytics"""

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """Override to catch special analytics messages from JavaScript"""
        # Check for auth button click tracking
        if message == "ANKI_ANALYTICS:signup_clicked":
            try:
                from .analytics import track_auth_button_click
                track_auth_button_click("signup")
            except:
                pass
        elif message == "ANKI_ANALYTICS:login_clicked":
            try:
                from .analytics import track_auth_button_click
                track_auth_button_click("login")
            except:
                pass
        # Track when user sends a message in the chat
        elif message == "ANKI_ANALYTICS:message_sent":
            try:
                from .analytics import track_message_sent
                track_message_sent()

                from .review import show_review_modal_if_eligible
                show_review_modal_if_eligible()
            except Exception as e:
                print(f"AI Panel: Error in message tracking: {e}")
        # Call parent implementation for normal logging
        super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)


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
        c = ThemeManager.get_palette()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 4, 4)
        layout.setSpacing(2)

        # Back button with arrow icon (hidden by default)
        self.back_button = QPushButton()
        self.back_button.setFixedSize(24, 24)
        self.back_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_button.setVisible(False)  # Hidden by default

        # Create high-resolution SVG icon for back button
        back_icon_svg = f"""<?xml version="1.0" encoding="UTF-8"?>
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M30 12 L18 24 L30 36" stroke="{c['icon_color']}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
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

        self.back_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {c['hover']};
            }}
        """)
        self.back_button.clicked.connect(self.go_back)
        layout.addWidget(self.back_button)

        # Title label
        self.title_label = QLabel("Anki Copilot")
        self.title_label.setStyleSheet(f"color: {c['text']}; font-size: 13px; font-weight: 500;")
        layout.addWidget(self.title_label)

        # Add stretch to push buttons to the right
        layout.addStretch()

        # Float/Undock button with high-quality SVG icon
        self.float_button = QPushButton()
        self.float_button.setFixedSize(24, 24)
        self.float_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Create high-resolution SVG icon for float button
        float_icon_svg = f"""<?xml version="1.0" encoding="UTF-8"?>
        <svg width="48" height="48" viewBox="0 0 24 24" fill="{c['icon_color']}" xmlns="http://www.w3.org/2000/svg">
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

        self.float_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {c['hover']};
            }}
        """)
        self.float_button.clicked.connect(self.toggle_floating)
        layout.addWidget(self.float_button)

        # Settings/Gear button with high-quality SVG icon
        self.settings_button = QPushButton()
        self.settings_button.setFixedSize(24, 24)
        self.settings_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Create high-resolution minimalistic SVG icon for settings button
        settings_icon_svg = f"""<?xml version="1.0" encoding="UTF-8"?>
        <svg width="48" height="48" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill-rule="evenodd" clip-rule="evenodd">
            <path d="M12 8.666c-1.838 0-3.333 1.496-3.333 3.334s1.495 3.333 3.333 3.333 3.333-1.495 3.333-3.333-1.495-3.334-3.333-3.334m0 7.667c-2.39 0-4.333-1.943-4.333-4.333s1.943-4.334 4.333-4.334 4.333 1.944 4.333 4.334c0 2.39-1.943 4.333-4.333 4.333m-1.193 6.667h2.386c.379-1.104.668-2.451 2.107-3.05 1.496-.617 2.666.196 3.635.672l1.686-1.688c-.508-1.047-1.266-2.199-.669-3.641.567-1.369 1.739-1.663 3.048-2.099v-2.388c-1.235-.421-2.471-.708-3.047-2.098-.572-1.38.057-2.395.669-3.643l-1.687-1.686c-1.117.547-2.221 1.257-3.642.668-1.374-.571-1.656-1.734-2.1-3.047h-2.386c-.424 1.231-.704 2.468-2.099 3.046-.365.153-.718.226-1.077.226-.843 0-1.539-.392-2.566-.893l-1.687 1.686c.574 1.175 1.251 2.237.669 3.643-.571 1.375-1.734 1.654-3.047 2.098v2.388c1.226.418 2.468.705 3.047 2.098.581 1.403-.075 2.432-.669 3.643l1.687 1.687c1.45-.725 2.355-1.204 3.642-.669 1.378.572 1.655 1.738 2.1 3.047m3.094 1h-3.803c-.681-1.918-.785-2.713-1.773-3.123-1.005-.419-1.731.132-3.466.952l-2.689-2.689c.873-1.837 1.367-2.465.953-3.465-.412-.991-1.192-1.087-3.123-1.773v-3.804c1.906-.678 2.712-.782 3.123-1.773.411-.991-.071-1.613-.953-3.466l2.689-2.688c1.741.828 2.466 1.365 3.465.953.992-.412 1.082-1.185 1.775-3.124h3.802c.682 1.918.788 2.714 1.774 3.123 1.001.416 1.709-.119 3.467-.952l2.687 2.688c-.878 1.847-1.361 2.477-.952 3.465.411.992 1.192 1.087 3.123 1.774v3.805c-1.906.677-2.713.782-3.124 1.773-.403.975.044 1.561.954 3.464l-2.688 2.689c-1.728-.82-2.467-1.37-3.456-.955-.988.41-1.08 1.146-1.785 3.126" fill="{c['icon_color']}"/>
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

        self.settings_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {c['hover']};
            }}
        """)
        self.settings_button.clicked.connect(self.toggle_settings)
        layout.addWidget(self.settings_button)

        # Close button with high-quality SVG icon
        self.close_button = QPushButton()
        self.close_button.setFixedSize(24, 24)
        self.close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Create high-resolution SVG icon for close button
        close_icon_svg = f"""<?xml version="1.0" encoding="UTF-8"?>
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 8 L40 40 M40 8 L8 40" stroke="{c['icon_color']}" stroke-width="4" stroke-linecap="round"/>
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

        self.close_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {c['danger_hover']};
            }}
        """)
        self.close_button.clicked.connect(self.dock_widget.hide)
        layout.addWidget(self.close_button)

        # Set background color for title bar
        c = ThemeManager.get_palette()
        self.setStyleSheet(f"background: {c['surface']}; border-bottom: 1px solid {c['border_subtle']};")

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
            self.title_label.setText("Anki Copilot")
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
        # Create loading overlay first (so it's on top in z-order)
        self.loading_overlay = QWebEngineView(self.web_container)
        
        # Use ThemeManager for style
        c = ThemeManager.get_palette()
        self.loading_overlay.setStyleSheet(f"QWebEngineView {{ background: {c['background']}; }}")
        
        # Loading HTML with rolling dots animation (dynamically colored)
        self.loading_overlay.setHtml(ThemeManager.get_loading_html())
        
        # Create web view for OpenEvidence
        self.web = QWebEngineView(self.web_container)

        # Set up persistent profile for cookies/session storage
        persistent_profile = get_persistent_profile()
        if persistent_profile and QWebEnginePage:
            # Create a custom page with the persistent profile that can intercept console messages
            page = TutorialAwarePage(persistent_profile, self.web)
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

        c = ThemeManager.get_palette()
        self.web.setStyleSheet(f"QWebEngineView {{ background: {c['background']}; }}")
        
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

        # Set up auth detection timer (check every 30 seconds)
        self.auth_check_timer = QTimer(self)
        self.auth_check_timer.timeout.connect(self.check_auth_status)
        self.auth_check_timer.start(300000)  # 5 minutes

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
            self.inject_auth_button_listener()
            self.inject_message_tracking_listener()
            # Check auth status when page is ready
            QTimer.singleShot(2000, self.check_auth_status)  # Wait 2 seconds for tokens to load
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

    def check_auth_status(self):
        """Check if user is authenticated on OpenEvidence"""
        # Skip if already detected
        from .analytics import is_user_logged_in
        if is_user_logged_in():
            # Already logged in, stop checking
            if hasattr(self, 'auth_check_timer'):
                self.auth_check_timer.stop()
            return

        # JavaScript to check for authentication by DOM elements (not tokens)
        # More reliable - checks if Login/SignUp buttons are present (logged out)
        # vs if Avatar/Sidebar elements are present (logged in)
        auth_check_js = """
        (function() {
            try {
                // 1. Check if Login/SignUp buttons exist (means NOT logged in)
                var buttons = Array.from(document.querySelectorAll('button'));
                var loginButton = buttons.find(function(el) { 
                    return el.innerText && el.innerText.includes('Log In'); 
                });
                var signupButton = buttons.find(function(el) { 
                    return el.innerText && el.innerText.includes('Sign Up'); 
                });
                
                // If both login buttons are present, user is NOT logged in
                if (loginButton && signupButton) {
                    return false;
                }
                
                // 2. Check for logged-in indicators (Avatar, Drawer/Sidebar)
                var hasAvatar = !!document.querySelector('.MuiAvatar-root, [class*="Avatar"]');
                var hasDrawer = !!document.querySelector('.MuiDrawer-root, [class*="Drawer"], [class*="Sidebar"]');
                
                // 3. Check for user profile text (e.g., user name or email)
                var allText = document.body.innerText || '';
                var hasEmailPattern = /@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/.test(allText);
                
                // User is logged in if: no login buttons AND (has avatar OR has drawer OR has email)
                var isLoggedIn = !loginButton && !signupButton && (hasAvatar || hasDrawer || hasEmailPattern);
                
                return isLoggedIn;
            } catch(e) {
                return false;
            }
        })();
        """

        try:
            self.web.page().runJavaScript(auth_check_js, self.handle_auth_check)
        except Exception as e:
            print(f"AI Panel: Error checking auth status: {e}")

    def handle_auth_check(self, is_authenticated):
        """Handle result of authentication check"""
        if is_authenticated:
            from .analytics import track_login_detected
            track_login_detected()
            # Stop the timer since we detected login
            if hasattr(self, 'auth_check_timer'):
                self.auth_check_timer.stop()

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
            from .settings_quick_actions import QuickActionsSettingsView

            if isinstance(current_widget, SettingsEditorView):
                # In editor view, discard changes and go back to templates list view
                if hasattr(current_widget, 'discard_and_go_back'):
                    current_widget.discard_and_go_back()
                else:
                    self.show_templates_view()
            elif isinstance(current_widget, SettingsListView):
                # In templates list view, go back to settings home
                self.show_home_view()
            elif isinstance(current_widget, QuickActionsSettingsView):
                # In quick actions view, go back to settings home
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

    def show_list_view(self):
        """Show the settings list view (alias for show_templates_view for backward compatibility)"""
        self.show_templates_view()

    def show_quick_actions_view(self):
        """Show the quick actions settings view"""
        current_widget = self.stacked_widget.widget(1)

        from .settings_quick_actions import QuickActionsSettingsView

        # If it's already a QuickActionsSettingsView, just show it
        if current_widget and isinstance(current_widget, QuickActionsSettingsView):
            self.stacked_widget.setCurrentIndex(1)
            self._update_title_bar(True)
            return

        # Otherwise, swap in a fresh quick actions view
        if current_widget:
            self.stacked_widget.removeWidget(current_widget)
            current_widget.deleteLater()

        self.settings_view = QuickActionsSettingsView(self)
        self.stacked_widget.addWidget(self.settings_view)
        self.stacked_widget.setCurrentIndex(1)
        self._update_title_bar(True)

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

    def inject_auth_button_listener(self):
        """Inject JavaScript to track clicks on Sign up / Log in buttons"""
        listener_js = """
        (function() {
            // Only inject if not already injected
            if (window.ankiAuthButtonListenerInjected) {
                console.log('Anki: Auth button listener already exists, skipping injection');
                return;
            }

            console.log('Anki: Injecting auth button click tracker');
            window.ankiAuthButtonListenerInjected = true;

            // Use event delegation to catch clicks on dynamically loaded buttons
            document.addEventListener('click', function(event) {
                var target = event.target;

                // Traverse up to find the actual button/link (in case user clicks on text inside)
                var clickedElement = target;
                for (var i = 0; i < 5 && clickedElement; i++) {
                    // Only check actual interactive elements (buttons, links)
                    var tagName = clickedElement.tagName ? clickedElement.tagName.toLowerCase() : '';
                    if (tagName !== 'button' && tagName !== 'a') {
                        clickedElement = clickedElement.parentElement;
                        continue;
                    }

                    var text = (clickedElement.textContent || '').toLowerCase().trim();
                    var href = (clickedElement.href || '').toLowerCase();

                    // Check for "Sign up" button - must be exact match or in href
                    if (text === 'sign up' || text === 'sign up for free access' ||
                        href.includes('/signup') || href.includes('/register')) {
                        console.log('ANKI_ANALYTICS:signup_clicked');
                        break;
                    }

                    // Check for "Log in" button - must be exact match or in href
                    if (text === 'log in' || text === 'login' || text === 'log in here' ||
                        href.includes('/login') || href.includes('/signin')) {
                        console.log('ANKI_ANALYTICS:login_clicked');
                        break;
                    }

                    // Move up to parent element
                    clickedElement = clickedElement.parentElement;
                }
            }, true);  // Use capture phase to catch all clicks
        })();
        """

        try:
            self.web.page().runJavaScript(listener_js)
        except Exception as e:
            print(f"AI Panel: Error injecting auth button listener: {e}")

    def inject_message_tracking_listener(self):
        """Inject JavaScript to track when user submits a message in the chat"""
        listener_js = """
        (function() {
            // Only inject if not already injected
            if (window.ankiMessageTrackingInjected) {
                console.log('Anki: Message tracking already exists, skipping injection');
                return;
            }
            
            console.log('Anki: Injecting message tracking listener');
            window.ankiMessageTrackingInjected = true;

            // Only count as a message if a chat input is actually present on the
            // page. This prevents login page form submissions / "Continue" button
            // clicks from incrementing the counter.
            function isOnChatPage() {
                var inputs = document.querySelectorAll('input, textarea');
                for (var i = 0; i < inputs.length; i++) {
                    var ph = (inputs[i].placeholder || '').toLowerCase();
                    if (ph.indexOf('medical') !== -1 || ph.indexOf('question') !== -1 ||
                        ph.indexOf('ask') !== -1 || ph.indexOf('follow') !== -1 ||
                        ph.indexOf('message') !== -1) {
                        return true;
                    }
                }
                return false;
            }

            // Debounce to prevent double-counting (Enter key + form submit can fire close together)
            var lastMessageTime = 0;
            function trackMessage() {
                if (!isOnChatPage()) {
                    return;  // Login/signup/other pages — don't count
                }
                var now = Date.now();
                if (now - lastMessageTime > 200) {  // 200ms debounce
                    lastMessageTime = now;
                    console.log('ANKI_ANALYTICS:message_sent');
                }
            }
            
            // Track form submissions
            document.addEventListener('submit', function(event) {
                trackMessage();
            }, true);
            
            // Track Enter key in input/textarea (common chat pattern)
            document.addEventListener('keydown', function(event) {
                if (event.key === 'Enter' && !event.shiftKey) {
                    var target = event.target;
                    var tagName = target.tagName.toLowerCase();
                    // Only track if in input or textarea that looks like a chat input
                    if (tagName === 'input' || tagName === 'textarea') {
                        var placeholder = (target.placeholder || '').toLowerCase();
                        var value = (target.value || '').trim();
                        // Check if it looks like a chat/search input OR has content to send
                        if (placeholder.includes('question') || placeholder.includes('search') || 
                            placeholder.includes('ask') || placeholder.includes('message') ||
                            placeholder.includes('medical') || placeholder.includes('follow') ||
                            value.length > 0) {
                            trackMessage();
                        }
                    }
                }
            }, true);
            
            // Track clicks on send/submit buttons (including icon-only buttons)
            document.addEventListener('click', function(event) {
                var target = event.target;
                // Walk up to find button (also check for SVG clicks inside buttons)
                while (target && target.tagName !== 'BUTTON' && target !== document.body) {
                    target = target.parentElement;
                }
                if (target && target.tagName === 'BUTTON') {
                    var buttonText = (target.textContent || '').toLowerCase();
                    var ariaLabel = (target.getAttribute('aria-label') || '').toLowerCase();
                    var buttonType = (target.getAttribute('type') || '').toLowerCase();
                    var hasSvg = target.querySelector('svg') !== null;
                    var className = (target.className || '').toLowerCase();
                    
                    // Check if it's a send/submit button (text, aria-label, type, or icon button)
                    if (buttonText.includes('send') || buttonText.includes('submit') ||
                        buttonText.includes('ask') || ariaLabel.includes('send') ||
                        ariaLabel.includes('submit') || buttonType === 'submit' ||
                        (hasSvg && (className.includes('send') || className.includes('submit') || 
                         className.includes('primary') || className.includes('action')))) {
                        trackMessage();
                    }
                    
                    // Also track if button is near an input/textarea (likely a send button)
                    var parent = target.parentElement;
                    if (parent) {
                        var hasInputSibling = parent.querySelector('input, textarea') !== null;
                        if (hasInputSibling && hasSvg) {
                            trackMessage();
                        }
                    }
                }
            }, true);
        })();
        """
        
        try:
            self.web.page().runJavaScript(listener_js)
        except Exception as e:
            print(f"AI Panel: Error injecting message tracking listener: {e}")

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
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
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
        config = mw.addonManager.getConfig(ADDON_NAME) or {}
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


class RoundedPixmapLabel(QLabel):
    """A QLabel that clips its pixmap to a rounded rectangle with smooth
    antialiased corners. QLabel's stylesheet `border-radius` only rounds the
    label's background — the pixmap drawn on top still has square corners. This
    subclass overrides paintEvent to clip drawing to a rounded path so the
    actual image content has smooth, rounded corners.
    """

    def __init__(self, radius=12, border_color=None, parent=None):
        super().__init__(parent)
        self._radius = radius
        self._border_color = border_color

    def paintEvent(self, event):
        try:
            from PyQt6.QtGui import QPainter, QPainterPath, QPen, QColor
            from PyQt6.QtCore import QRectF
        except ImportError:
            from PyQt5.QtGui import QPainter, QPainterPath, QPen, QColor
            from PyQt5.QtCore import QRectF

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rectf = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rectf, float(self._radius), float(self._radius))

        # Clip to rounded shape, then draw the pixmap
        painter.setClipPath(path)
        pix = self.pixmap()
        if pix is not None and not pix.isNull():
            painter.drawPixmap(self.rect(), pix)

        # Draw a 1px rounded border on top, if requested
        if self._border_color:
            painter.setClipping(False)
            pen = QPen(QColor(self._border_color))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                rectf.adjusted(0.5, 0.5, -0.5, -0.5),
                float(self._radius),
                float(self._radius),
            )

        painter.end()


class OnboardingDialog(QWidget):
    """Centered onboarding popup with 3 slides, shown over the main Anki window.
    Animates in with a smooth slide-up + fade. The sidebar already has OpenEvidence
    loading in the background while this dialog is visible."""

    FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

    SLIDES = [
        {
            "title": "Welcome",
            "tagline": "AI for Anki, completely free.",
            "subtitle": "Generate full decks from your notes. Create cards from any topic. Ask questions and get instant explanations on anything you're studying.\n\nNo payments. No subscriptions. No limits.",
            "is_welcome": True,
        },
        {
            "title": "Create a Whole Deck",
            "subtitle": "Paste your notes. Get a free Anki deck in seconds.",
            "gif": "gifs/ai_generate.gif",
        },
        {
            "title": "Explain Anything",
            "subtitle": "Highlight a word in any card and click Explain for an instant breakdown.",
            "gif": "gifs/explain.gif",
        },
        {
            "title": "AI Answers Your Cards",
            "subtitle": "Type the front of a card. Let the AI fill in the back for you.",
            "gif": "gifs/ai_answer.gif",
        },
        {
            "title": "Chat With AI",
            "subtitle": "Click the book icon to open the sidebar. Ask anything about what you're studying.",
            "gif": "gifs/chat_sidebar.gif",
        },
        {
            "title": "Found a Bug? Tell Us.",
            "subtitle": "Bugs and ideas help way more than a bad review. We read every one.",
            "gif": "gifs/report_bug.gif",
            "is_final": True,
        },
    ]

    # First slide shown to existing users on update instead of "Welcome"
    UPDATE_SLIDE = {
        "title": "New Update",
        "tagline": "Here's what's new.",
        "subtitle": "We've added some big features since you last updated. Here's a quick look at what you can do now.",
        "is_welcome": True,
    }

    def __init__(self, parent=None, is_update=False):
        super().__init__(parent)
        import sys
        self.is_mac = sys.platform == "darwin"
        self._backdrop_opacity = 0
        self._tutorial_completed = False  # set True in _complete() to avoid double-tracking
        self._is_update = is_update
        self._connected_dock = None

        # Swap the first slide for the update version if this is an existing user
        if is_update:
            self._slides = [self.UPDATE_SLIDE] + self.SLIDES[1:]
        else:
            self._slides = list(self.SLIDES)

        # Regular child widget of mw (NO window flags) — this paints over
        # everything inside mw including the toolbar (Decks/Add/Browse/
        # Stats/Sync), which a top-level overlay can't do cleanly on macOS.
        # autoFillBackground defaults to False, so our paintEvent controls
        # the surface directly (same approach as ModalOverlay).

        self._setup_ui()

        if parent:
            parent.installEventFilter(self)

        # Re-raise the dialog whenever the AI side panel (dock widget)
        # becomes visible. Without this, closing and reopening the dock
        # while the tutorial is showing would put the dock on top of it.
        try:
            from aqt.qt import QDockWidget
            for dock in mw.findChildren(QDockWidget, "AIPanelDock"):
                try:
                    dock.visibilityChanged.connect(self._on_sibling_visibility)
                    self._connected_dock = dock
                except Exception:
                    pass
        except Exception:
            pass

    def _on_sibling_visibility(self, *args):
        """Re-raise the tutorial when a sibling (dock widget) visibility changes."""
        if self.isVisible():
            QTimer.singleShot(0, self.raise_)

    def eventFilter(self, watched, event):
        # Resize with parent — also re-raise so anything that was drawn
        # during the resize can't end up above the tutorial.
        if watched == self.parent() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(30, self._sync_geometry)
            if self.isVisible():
                QTimer.singleShot(30, self.raise_)
        return super().eventFilter(watched, event)

    # ── Styles ──

    def _primary_btn(self, c):
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c['accent']}, stop:1 #2563eb);
                color: #ffffff;
                border: none;
                border-radius: 12px;
                font-size: 15px;
                font-weight: 600;
                padding: 15px 0px;
                font-family: {self.FONT};
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:1 #1d4ed8);
            }}
        """

    def _ghost_btn(self, c):
        return f"""
            QPushButton {{
                background: transparent;
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 12px;
                font-size: 14px;
                font-weight: 500;
                padding: 13px 0px;
                font-family: {self.FONT};
            }}
            QPushButton:hover {{
                background: {c['hover']};
                border-color: {c['text_secondary']};
            }}
        """

    # ── UI Setup ──

    def _setup_ui(self):
        c = ThemeManager.get_palette()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # Bias the card upward — more space below than above so it sits
        # above center (roughly 1/3 from the top instead of dead middle).
        outer.addStretch(2)

        # The card
        self.card = QWidget()
        self.card.setFixedSize(820, 640)
        self.card.setObjectName("obCard")
        self.card.setStyleSheet(f"""
            QWidget#obCard {{
                background: {c['background']};
                border: 1px solid {c['border']};
                border-radius: 20px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 12)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        # Track each slide's QMovie so we can restart on slide change and
        # pause inactive ones (avoid wasted CPU + lets the user see each
        # GIF from the beginning when they click Continue).
        self._slide_movies = {}

        self.stacked = QStackedWidget()
        card_layout.addWidget(self.stacked)

        for i in range(len(self._slides)):
            self._create_slide(i)

        # Restart the visible GIF from frame 0 every time the user navigates,
        # and pause everything else.
        self.stacked.currentChanged.connect(self._on_slide_changed)
        self.stacked.setCurrentIndex(0)
        self._on_slide_changed(0)

        outer.addWidget(self.card, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(3)

    def _on_slide_changed(self, new_index):
        """Restart the GIF for the newly visible slide; pause all others."""
        for i, movie in self._slide_movies.items():
            try:
                if i == new_index:
                    movie.stop()
                    movie.start()
                else:
                    movie.stop()
            except Exception:
                pass

    def _make_dots(self, active_idx, total=None):
        if total is None:
            total = len(self._slides) if hasattr(self, '_slides') else 3
        c = ThemeManager.get_palette()
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for i in range(total):
            dot = QLabel()
            if i == active_idx:
                dot.setFixedSize(24, 6)
                dot.setStyleSheet(f"background: {c['accent']}; border-radius: 3px;")
            else:
                dot.setFixedSize(6, 6)
                dot.setStyleSheet(f"background: {c['border']}; border-radius: 3px;")
            h.addWidget(dot)
        return w

    def _make_gif(self, gif_rel_path, c):
        """Render a GIF for an onboarding clip with proper HiDPI + aspect-ratio handling.

        Three things differ from the naive QMovie+setScaledContents approach:
        1. Uses QMovie.setScaledSize() for high-quality scaling (instead of QLabel's
           per-frame setScaledContents which uses fast/blurry interpolation).
        2. Targets PHYSICAL pixels (logical × devicePixelRatio) so Retina displays
           render the GIF crisply instead of upscaling 1x→2x and softening it.
        3. Respects the GIF's natural aspect ratio so frames aren't squished.
        """
        gif_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), gif_rel_path)
        if not os.path.exists(gif_path):
            return None
        try:
            from aqt.qt import QMovie
        except ImportError:
            try:
                from PyQt6.QtGui import QMovie
            except ImportError:
                from PyQt5.QtGui import QMovie
        try:
            from PyQt6.QtCore import QSize
            from PyQt6.QtGui import QGuiApplication
        except ImportError:
            from PyQt5.QtCore import QSize
            from PyQt5.QtGui import QGuiApplication

        # Device pixel ratio for HiDPI rendering (2.0 on Retina, 1.0 otherwise)
        screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0

        # Read the GIF's native size by jumping to frame 0
        movie = QMovie(gif_path)
        movie.jumpToFrame(0)
        natural = movie.currentPixmap().size()

        # Compute display size that preserves aspect ratio
        max_w = 732  # available width inside the card (820 - 44*2 margins)
        target_h = 380
        if natural.width() > 0 and natural.height() > 0:
            aspect = natural.width() / natural.height()
            target_w = int(target_h * aspect)
            if target_w > max_w:
                target_w = max_w
                target_h = int(max_w / aspect)
        else:
            target_w = max_w

        # Scale movie frames to PHYSICAL pixels — Qt's QMovie scaling is much
        # higher quality than QLabel.setScaledContents.
        movie.setScaledSize(QSize(int(target_w * dpr), int(target_h * dpr)))

        # Use RoundedPixmapLabel so the GIF actually has rounded corners
        # (a stylesheet border-radius alone doesn't clip pixmap content).
        lbl = RoundedPixmapLabel(radius=12, border_color=c['border'])
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFixedSize(target_w, target_h)

        # On each frame, set the pixmap manually with the right DPR so Qt
        # treats it as a high-resolution asset and renders at logical size.
        def _on_frame(_=None):
            pix = movie.currentPixmap()
            pix.setDevicePixelRatio(dpr)
            lbl.setPixmap(pix)

        movie.frameChanged.connect(_on_frame)
        _on_frame()  # set the first frame immediately
        movie.start()
        lbl._movie = movie
        return lbl

    # ── Slides ──

    def _create_slide(self, index):
        c = ThemeManager.get_palette()
        slide = self._slides[index]
        total = len(self._slides)
        is_final = slide.get("is_final", False)
        is_welcome = slide.get("is_welcome", False)

        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setSpacing(0)

        # Build the slide content (everything above the button)
        if is_welcome:
            self._populate_welcome_slide(lay, slide, c)
        else:
            self._populate_feature_slide(lay, slide, c, index)

        # ── Continue / Get Started button (shared) ──
        if is_welcome:
            btn_text = "Let's Go \u2192"
        elif is_final:
            btn_text = "Get Started \u2192"
        else:
            btn_text = "Continue"

        btn = QPushButton(btn_text)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(self._primary_btn(c))
        if is_final:
            btn.clicked.connect(self._complete)
        else:
            next_idx = index + 1
            btn.clicked.connect(lambda _=False, i=next_idx: self.stacked.setCurrentIndex(i))
        lay.addWidget(btn)
        lay.addSpacing(14)
        lay.addWidget(self._make_dots(index, total))

        self.stacked.addWidget(page)

    def _populate_welcome_slide(self, lay, slide, c):
        """Welcome slide layout — big hero title, accent tagline, body text,
        all vertically centered between the top of the card and the button."""
        lay.setContentsMargins(80, 40, 80, 24)

        lay.addStretch(1)

        # Big hero title
        title = QLabel(slide["title"])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: {c['text']}; font-size: 68px; font-weight: 800; "
            f"background: transparent; font-family: {self.FONT}; letter-spacing: -1px;"
        )
        lay.addWidget(title)
        lay.addSpacing(20)

        # Tagline (accent color, semibold) — punchy "100% free" hook
        tagline = QLabel(slide.get("tagline", ""))
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setWordWrap(True)
        tagline.setStyleSheet(
            f"color: {c['accent']}; font-size: 20px; font-weight: 600; "
            f"background: transparent; font-family: {self.FONT};"
        )
        lay.addWidget(tagline)
        lay.addSpacing(32)

        # Body text — friendly intro
        body = QLabel(slide["subtitle"])
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color: {c['text_secondary']}; font-size: 17px; "
            f"background: transparent; font-family: {self.FONT}; line-height: 1.6;"
        )
        lay.addWidget(body)

        lay.addStretch(1)

        # Subtle "Made by" credit — small, low-emphasis
        credit = QLabel("Made by Luke Pettit")
        credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit.setStyleSheet(
            f"color: {c['text_secondary']}; font-size: 12px; "
            f"background: transparent; font-family: {self.FONT}; opacity: 0.6;"
        )
        lay.addWidget(credit)
        lay.addSpacing(16)

    def _populate_feature_slide(self, lay, slide, c, index):
        """Feature slide layout — step counter, title, subtitle, GIF."""
        lay.setContentsMargins(44, 32, 44, 24)

        # Feature step counter — excludes welcome from the numbering
        feature_total = sum(1 for s in self._slides if not s.get("is_welcome"))
        feature_num = index  # welcome is index 0, so feature 1 is at index 1
        step = QLabel(f"STEP {feature_num} OF {feature_total}")
        step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step.setStyleSheet(
            f"color: {c['accent']}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: 2px; background: transparent; font-family: {self.FONT};"
        )
        lay.addWidget(step)
        lay.addSpacing(10)

        # Title
        title = QLabel(slide["title"])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: {c['text']}; font-size: 26px; font-weight: 700; "
            f"background: transparent; font-family: {self.FONT};"
        )
        lay.addWidget(title)
        lay.addSpacing(6)

        # Subtitle
        sub = QLabel(slide["subtitle"])
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color: {c['text_secondary']}; font-size: 14px; "
            f"background: transparent; font-family: {self.FONT};"
        )
        lay.addWidget(sub)
        lay.addSpacing(18)

        # GIF (centered horizontally; width adapts to aspect ratio)
        gif = self._make_gif(slide["gif"], c)
        if gif:
            lay.addWidget(gif, alignment=Qt.AlignmentFlag.AlignCenter)
            if hasattr(gif, "_movie"):
                self._slide_movies[index] = gif._movie

        lay.addStretch()

    # ── Drawing & Animation ──

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, self._backdrop_opacity))
        painter.end()
        super().paintEvent(event)

    def show_animated(self):
        """Animate the dialog: fade backdrop + slide card up."""
        self._sync_geometry()
        self.show()
        self.raise_()

        # Fade in backdrop
        self._backdrop_opacity = 0
        self._fade_timer = QTimer()
        def _fade_step():
            self._backdrop_opacity = min(self._backdrop_opacity + 8, 120)
            self.update()
            if self._backdrop_opacity >= 120:
                self._fade_timer.stop()
        self._fade_timer.timeout.connect(_fade_step)
        self._fade_timer.start(16)

        # Slide card up
        try:
            from PyQt6.QtCore import QPropertyAnimation, QRect, QEasingCurve
        except ImportError:
            from PyQt5.QtCore import QPropertyAnimation, QRect, QEasingCurve

        end_rect = self.card.geometry()
        start_rect = QRect(end_rect.x(), end_rect.y() + 60, end_rect.width(), end_rect.height())
        self.card.setGeometry(start_rect)

        self._slide_anim = QPropertyAnimation(self.card, b"geometry")
        self._slide_anim.setDuration(450)
        self._slide_anim.setStartValue(start_rect)
        self._slide_anim.setEndValue(end_rect)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._slide_anim.start()

    def _sync_geometry(self):
        # As a child widget, geometry is relative to mw's content area.
        # mw.rect() covers everything inside mw including the toolbar.
        if mw and mw.isVisible():
            self.setGeometry(mw.rect())

    def closeEvent(self, event):
        """Mark update dialog as seen if closed early (tutorial just re-shows next launch)."""
        if not self._tutorial_completed and self._is_update:
            try:
                from .utils import ADDON_NAME
                config = mw.addonManager.getConfig(ADDON_NAME) or {}
                analytics = config.get("analytics", {})
                analytics["update_v2_shown"] = True
                config["analytics"] = analytics
                mw.addonManager.writeConfig(ADDON_NAME, config)
            except Exception:
                pass

        # Disconnect the dock widget's visibilityChanged signal
        if hasattr(self, "_connected_dock") and self._connected_dock is not None:
            try:
                self._connected_dock.visibilityChanged.disconnect(self._on_sibling_visibility)
            except Exception:
                pass
            self._connected_dock = None

        super().closeEvent(event)

    def _complete(self):
        """Tear down the dialog cleanly before deletion.

        On macOS, deleting a frameless WindowStaysOnTopHint dialog inside the
        click handler that fires it (while QMovies are still emitting
        frameChanged and an event filter is installed on the parent) crashes
        Qt's Cocoa platform plugin with:
            -[_NSAlertPanel showsSuppressionButton]: unrecognized selector
        The fix is to stop all signals/timers/movies, remove the event filter,
        then defer deleteLater() to the next event-loop tick.
        """
        # Track completion
        self._tutorial_completed = True
        try:
            from datetime import datetime
            from .utils import ADDON_NAME

            config = mw.addonManager.getConfig(ADDON_NAME) or {}
            analytics = config.get("analytics", {})

            if self._is_update:
                # Update dialog — just mark as seen, don't overwrite tutorial metrics
                analytics["update_v2_shown"] = True
            else:
                # Fresh tutorial — set status, step, and duration directly on the
                # dict (not via tracking functions, which would read/write config
                # independently and get overwritten by the stale dict below).
                total_slides = len(self._slides)
                analytics["tutorial_status"] = "completed"
                analytics["tutorial_current_step"] = f"{total_slides}/{total_slides}"
                # Fresh-install users already see the new tutorial content, so
                # mark the update dialog as seen too. Without this, the update
                # modal would pop up on their next Anki launch.
                analytics["update_v2_shown"] = True

                start_time = analytics.get("tutorial_start_time")
                if start_time:
                    start_dt = datetime.fromisoformat(start_time)
                    duration = round((datetime.now() - start_dt).total_seconds(), 1)
                    analytics["tutorial_duration_seconds"] = duration

            config["analytics"] = analytics
            mw.addonManager.writeConfig(ADDON_NAME, config)
        except Exception as e:
            print(f"AI Panel: Error tracking tutorial completion: {e}")

        # Stop all GIF playback so frameChanged signals stop firing into labels
        for movie in self._slide_movies.values():
            try:
                movie.stop()
            except Exception:
                pass
        self._slide_movies.clear()

        # Stop the fade-in timer if it's still running
        if hasattr(self, "_fade_timer") and self._fade_timer is not None:
            try:
                self._fade_timer.stop()
            except Exception:
                pass

        # Stop the slide-up animation if it's still running
        if hasattr(self, "_slide_anim") and self._slide_anim is not None:
            try:
                self._slide_anim.stop()
            except Exception:
                pass

        # Remove the event filter we installed on the parent — otherwise the
        # parent may try to dispatch a Resize event to this widget after it
        # has been deleted, crashing inside libqcocoa.
        parent = self.parent()
        if parent is not None:
            try:
                parent.removeEventFilter(self)
            except Exception:
                pass

        # Disconnect the dock widget's visibilityChanged signal so it doesn't
        # try to raise_() us after we've been deleted.
        if hasattr(self, "_connected_dock") and self._connected_dock is not None:
            try:
                self._connected_dock.visibilityChanged.disconnect(self._on_sibling_visibility)
            except Exception:
                pass
            self._connected_dock = None

        # Hide immediately, but defer the actual deletion to the next event
        # loop tick so we're not destroying the widget while it's still
        # processing the click event that called us.
        self.hide()
        QTimer.singleShot(0, self.deleteLater)
