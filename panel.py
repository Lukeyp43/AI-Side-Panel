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
        # Track template usage (any template)
        if message.startswith("ANKI_ANALYTICS:template_used"):
            try:
                from .analytics import track_template_used
                track_template_used()
            except:
                pass
        # Check for auth button click tracking
        elif message == "ANKI_ANALYTICS:signup_clicked":
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

                from .review import show_review_overlay_if_eligible
                from aqt.qt import QTimer
                panel = self.parent()
                if panel:
                    QTimer.singleShot(500, lambda: show_review_overlay_if_eligible(panel))
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
        self.title_label = QLabel("AI Side Panel")
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
            self.title_label.setText("AI Side Panel")
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
            
            // Debounce to prevent double-counting (Enter key + form submit can fire close together)
            var lastMessageTime = 0;
            function trackMessage() {
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

                            // Track template usage with specific shortcut for analytics
                            console.log('ANKI_ANALYTICS:template_used:' + binding.keys.join('+'));
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


class OnboardingDialog(QWidget):
    """Centered onboarding popup with 3 slides, shown over the main Anki window.
    Animates in with a smooth slide-up + fade. The sidebar already has OpenEvidence
    loading in the background while this dialog is visible."""

    FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

    def __init__(self, parent=None):
        super().__init__(parent)
        import sys
        self.is_mac = sys.platform == "darwin"
        self._backdrop_opacity = 0

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._setup_ui()

        if parent:
            parent.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched == self.parent() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(30, self._sync_geometry)
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
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # The card
        self.card = QWidget()
        self.card.setFixedSize(540, 500)
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

        self.stacked = QStackedWidget()
        card_layout.addWidget(self.stacked)

        self._create_slide_1()
        self._create_slide_2()
        self._create_slide_3()
        self.stacked.setCurrentIndex(0)

        outer.addWidget(self.card)

    def _make_dots(self, active_idx):
        c = ThemeManager.get_palette()
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for i in range(3):
            dot = QLabel()
            if i == active_idx:
                dot.setFixedSize(24, 6)
                dot.setStyleSheet(f"background: {c['accent']}; border-radius: 3px;")
            else:
                dot.setFixedSize(6, 6)
                dot.setStyleSheet(f"background: {c['border']}; border-radius: 3px;")
            h.addWidget(dot)
        return w

    def _make_gif(self, gif_name, c):
        gif_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), gif_name)
        if not os.path.exists(gif_path):
            return None
        try:
            from aqt.qt import QMovie
        except ImportError:
            try:
                from PyQt6.QtGui import QMovie
            except ImportError:
                from PyQt5.QtGui import QMovie
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"border: 1px solid {c['border']}; border-radius: 12px; background: {c['surface']};")
        lbl.setFixedHeight(220)
        movie = QMovie(gif_path)
        lbl.setMovie(movie)
        lbl.setScaledContents(True)
        movie.start()
        lbl._movie = movie
        return lbl

    def _make_keycap(self, text, c):
        """Render a keyboard shortcut as a styled inline keycap."""
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            background: {c['surface']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 13px;
            font-weight: 600;
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
        """)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    def _shortcut_row(self, key_text, desc_text, c):
        """Build a row: [keycap] description"""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(14)
        rl.addStretch()
        rl.addWidget(self._make_keycap(key_text, c))
        desc = QLabel(desc_text)
        desc.setStyleSheet(f"color: {c['text_secondary']}; font-size: 14px; font-weight: 400; background: transparent; font-family: {self.FONT};")
        rl.addWidget(desc)
        rl.addStretch()
        return row

    # ── Slides ──

    def _create_slide_1(self):
        c = ThemeManager.get_palette()
        mod = "\u2318" if self.is_mac else "Ctrl"
        mod_word = "Cmd" if self.is_mac else "Ctrl"

        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(44, 36, 44, 28)
        lay.setSpacing(0)

        # Step label
        step = QLabel("STEP 1 OF 3")
        step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step.setStyleSheet(f"color: {c['accent']}; font-size: 11px; font-weight: 700; letter-spacing: 2px; background: transparent; font-family: {self.FONT};")
        lay.addWidget(step)
        lay.addSpacing(10)

        title = QLabel("Quick Actions")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {c['text']}; font-size: 28px; font-weight: 700; background: transparent; font-family: {self.FONT};")
        lay.addWidget(title)
        lay.addSpacing(8)

        sub = QLabel(f"Hold {mod_word} and highlight text on any card")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {c['text_secondary']}; font-size: 14px; background: transparent; font-family: {self.FONT};")
        lay.addWidget(sub)
        lay.addSpacing(20)

        gif = self._make_gif("onboarding_1.gif", c)
        if gif:
            lay.addWidget(gif)
            lay.addSpacing(20)

        lay.addWidget(self._shortcut_row(f"{mod}+F", "Add selected text to chat", c))
        lay.addSpacing(8)
        lay.addWidget(self._shortcut_row(f"{mod}+R", "Ask a question about it", c))

        lay.addStretch()

        btn = QPushButton("Continue")
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(self._primary_btn(c))
        btn.clicked.connect(lambda: self.stacked.setCurrentIndex(1))
        lay.addWidget(btn)
        lay.addSpacing(16)
        lay.addWidget(self._make_dots(0))

        self.stacked.addWidget(page)

    def _create_slide_2(self):
        c = ThemeManager.get_palette()

        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(44, 36, 44, 28)
        lay.setSpacing(0)

        step = QLabel("STEP 2 OF 3")
        step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step.setStyleSheet(f"color: {c['accent']}; font-size: 11px; font-weight: 700; letter-spacing: 2px; background: transparent; font-family: {self.FONT};")
        lay.addWidget(step)
        lay.addSpacing(10)

        title = QLabel("Customize Your Setup")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {c['text']}; font-size: 28px; font-weight: 700; background: transparent; font-family: {self.FONT};")
        lay.addWidget(title)
        lay.addSpacing(8)

        sub = QLabel("Click the gear icon to adjust shortcuts and templates")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {c['text_secondary']}; font-size: 14px; background: transparent; font-family: {self.FONT};")
        lay.addWidget(sub)
        lay.addSpacing(20)

        gif = self._make_gif("onboarding_2.gif", c)
        if gif:
            lay.addWidget(gif)
            lay.addSpacing(20)

        lay.addWidget(self._shortcut_row("Ctrl+Shift+S", "Explain the current card", c))

        lay.addStretch()

        btn = QPushButton("Continue")
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(self._primary_btn(c))
        btn.clicked.connect(lambda: self.stacked.setCurrentIndex(2))
        lay.addWidget(btn)
        lay.addSpacing(16)
        lay.addWidget(self._make_dots(1))

        self.stacked.addWidget(page)

    def _create_slide_3(self):
        c = ThemeManager.get_palette()

        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(44, 36, 44, 28)
        lay.setSpacing(0)

        step = QLabel("STEP 3 OF 3")
        step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step.setStyleSheet(f"color: {c['accent']}; font-size: 11px; font-weight: 700; letter-spacing: 2px; background: transparent; font-family: {self.FONT};")
        lay.addWidget(step)
        lay.addSpacing(10)

        title = QLabel("We'd Love Your Feedback")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {c['text']}; font-size: 28px; font-weight: 700; background: transparent; font-family: {self.FONT};")
        lay.addWidget(title)
        lay.addSpacing(8)

        sub = QLabel("Found a bug or have an idea?\nLet us know \u2014 it helps way more than a bad review!")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {c['text_secondary']}; font-size: 14px; background: transparent; font-family: {self.FONT};")
        lay.addWidget(sub)

        lay.addSpacing(28)

        feature_btn = QPushButton("\U0001f4a1  Request a Feature")
        feature_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        feature_btn.setStyleSheet(self._ghost_btn(c))
        feature_btn.clicked.connect(lambda: webbrowser.open("https://github.com/Lukeyp43/AI-Side-Panel/issues/new?labels=feature%20request"))
        lay.addWidget(feature_btn)
        lay.addSpacing(10)

        bug_btn = QPushButton("\U0001f41b  Report a Bug")
        bug_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        bug_btn.setStyleSheet(self._ghost_btn(c))
        bug_btn.clicked.connect(lambda: webbrowser.open("https://github.com/Lukeyp43/AI-Side-Panel/issues/new?labels=bug"))
        lay.addWidget(bug_btn)

        lay.addStretch()

        start_btn = QPushButton("Get Started \u2192")
        start_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        start_btn.setStyleSheet(self._primary_btn(c))
        start_btn.clicked.connect(self._complete)
        lay.addWidget(start_btn)
        lay.addSpacing(16)
        lay.addWidget(self._make_dots(2))

        self.stacked.addWidget(page)

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
        if mw and mw.isVisible():
            self.setGeometry(mw.rect())
            self.move(mw.pos())

    def _complete(self):
        self.hide()
        self.deleteLater()
