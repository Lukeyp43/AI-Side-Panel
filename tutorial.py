"""
Interactive tutorial system for OpenEvidence addon.
Shows floating tooltips and guides users through key features.
"""

from aqt import mw
from aqt.qt import *

try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
    from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, QByteArray
    from PyQt6.QtGui import QColor, QPainter, QPainterPath, QCursor, QPixmap
    from PyQt6.QtSvg import QSvgRenderer
except ImportError:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
    from PyQt5.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, QByteArray
    from PyQt5.QtGui import QColor, QPainter, QPainterPath, QCursor, QPixmap
    from PyQt5.QtSvg import QSvgRenderer


class TutorialChecklist(QWidget):
    """Fixed tutorial panel with accordion checklist"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        except:
            pass

        self._opacity = 1.0
        self.sections = []
        self.section_widgets = []
        self.task_widgets = []
        self.setup_ui()

    def set_icon_from_svg(self, label, svg_str, size=20):
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
        self.setFixedWidth(420)
        self.setStyleSheet("background: #1e1e1e;")

        # Main layout - zero spacing, zero margins
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header (72px fixed)
        header_container = QWidget()
        header_container.setMinimumHeight(72)
        header_container.setMaximumHeight(72)
        header_container.setStyleSheet("""
            QWidget {
                background: #1e1e1e;
                border-bottom: 1px solid #39404c;
            }
        """)
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(12)

        # Header title
        title = QLabel("Just one step ahead!")
        title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: 600; background: transparent; border: none;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Minimize button
        minimize_btn = QPushButton()
        minimize_btn.setFixedSize(32, 32)
        minimize_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        minimize_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 16px;
                border: none;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
        """)
        minus_svg = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>"""
        minus_icon = QLabel()
        minus_icon.setFixedSize(16, 16)
        self.set_icon_from_svg(minus_icon, minus_svg, size=16)
        minus_layout = QVBoxLayout(minimize_btn)
        minus_layout.setContentsMargins(0, 0, 0, 0)
        minus_layout.addWidget(minus_icon, 0, Qt.AlignmentFlag.AlignCenter)
        minimize_btn.clicked.connect(self.close_tutorial)
        header_layout.addWidget(minimize_btn)

        layout.addWidget(header_container)

        # Progress section (same height as accordion parents)
        progress_container = QWidget()
        progress_container.setFixedHeight(72)  # Use fixed height to prevent spacing
        progress_container.setStyleSheet("""
            QWidget {
                background: #2c2c2c;
                border-bottom: 1px solid #39404c;
                margin: 0px;
                padding: 0px;
            }
        """)
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(24, 0, 24, 0)
        progress_layout.setSpacing(16)

        # Emoji
        emoji_label = QLabel("👏")
        emoji_label.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        progress_layout.addWidget(emoji_label)

        # Progress bar container
        progress_bar_container = QWidget()
        progress_bar_container.setStyleSheet("background: transparent; border: none;")
        progress_bar_layout = QVBoxLayout(progress_bar_container)
        progress_bar_layout.setContentsMargins(0, 0, 0, 0)
        progress_bar_layout.setSpacing(0)

        # Progress bar background (progress track)
        self.progress_bg = QWidget()
        self.progress_bg.setFixedHeight(10)
        self.progress_bg.setStyleSheet("""
            QWidget {
                background: #404040;
                border-radius: 5px;
            }
        """)

        # Progress bar fill (blue accent)
        self.progress_fill = QWidget(self.progress_bg)
        self.progress_fill.setFixedHeight(10)
        self.progress_fill.setStyleSheet("""
            QWidget {
                background: #3b82f6;
                border-radius: 5px;
            }
        """)
        self.progress_fill.setFixedWidth(0)  # Start at 0

        progress_bar_layout.addWidget(self.progress_bg)
        progress_layout.addWidget(progress_bar_container, 1)

        # Progress percentage (foreground color)
        self.progress_label = QLabel("0%")
        self.progress_label.setStyleSheet("color: #fafafa; font-size: 18px; font-weight: 600; background: transparent; border: none;")
        progress_layout.addWidget(self.progress_label)

        layout.addWidget(progress_container)

        # Define sections with tasks
        self.sections = [
            {
                "title": "Getting Started",
                "tasks": [
                    {"text": "Click the book icon 📖 in toolbar", "id": 0},
                ]
            },
            {
                "title": "Using Shortcuts",
                "tasks": [
                    {"text": "Open a flashcard", "id": 1},
                    {"text": "Press Ctrl+Shift+S (Cmd+Shift+S) in search box", "id": 2},
                ]
            },
            {
                "title": "Quick Actions",
                "tasks": [
                    {"text": "Select text on flashcard", "id": 3},
                ]
            },
            {
                "title": "Customization",
                "tasks": [
                    {"text": "Click gear icon ⚙️ to explore settings", "id": 4},
                ]
            }
        ]

        # Add sections directly to main layout (no container)
        for section_idx, section in enumerate(self.sections):
            section_widget = self.create_section(section, section_idx)
            layout.addWidget(section_widget)
            self.section_widgets.append(section_widget)

        # Expand the first section by default to show checkboxes
        QTimer.singleShot(100, lambda: self.toggle_section(0))

        # Calculate initial progress
        self.update_progress()

        # Snap to exact content size
        QTimer.singleShot(150, self.adjustSize)

    def update_progress(self):
        """Update the progress bar and percentage"""
        total_tasks = sum(len(section["tasks"]) for section in self.sections)
        completed_tasks = sum(
            section.get("_data", {}).get("completed_count", 0)
            for section in self.sections
        )

        if total_tasks > 0:
            progress = int((completed_tasks / total_tasks) * 100)
            self.progress_label.setText(f"{progress}%")

            # Animate progress bar width
            bar_width = int((self.progress_bg.width() * progress) / 100)
            self.progress_fill.setFixedWidth(bar_width)

    def create_section(self, section, section_idx):
        """Create a simple accordion section"""
        is_last = section_idx == len(self.sections) - 1

        # Container for parent + children
        section_container = QWidget()
        section_container.setStyleSheet("background: #2c2c2c;")

        # Vertical layout: parent row, then children rows
        section_layout = QVBoxLayout(section_container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)

        # Parent button (72px fixed height, padding, hover effect)
        parent_btn = QPushButton()
        parent_btn.setFixedHeight(72)
        parent_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        border_bottom = "" if is_last else "border-bottom: 1px solid #39404c;"
        parent_btn.setStyleSheet(f"""
            QPushButton {{
                background: #2c2c2c;
                {border_bottom}
                text-align: left;
                padding: 0;
                border-top: none;
                border-left: none;
                border-right: none;
            }}
            QPushButton:hover {{
                background: #333333;
            }}
        """)

        parent_layout = QHBoxLayout()
        parent_layout.setContentsMargins(24, 0, 24, 0)
        parent_layout.setSpacing(16)

        # Circular icon on the left
        icon_container = QLabel()
        icon_container.setFixedSize(40, 40)
        icon_container.setStyleSheet("""
            QLabel {
                background: #383838;
                border-radius: 20px;
            }
        """)

        # Add section-specific SVG icon (icon color #999999)
        section_icons = {
            "Getting Started": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#999999" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <circle cx="12" cy="12" r="3"></circle>
            </svg>""",
            "Using Shortcuts": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#999999" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                <path d="M2 17l10 5 10-5M2 12l10 5 10-5"></path>
            </svg>""",
            "Quick Actions": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#999999" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
            </svg>""",
            "Customization": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#999999" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
            </svg>"""
        }

        icon_svg = section_icons.get(section['title'], section_icons["Getting Started"])
        icon_label = QLabel()
        icon_label.setFixedSize(20, 20)
        self.set_icon_from_svg(icon_label, icon_svg, size=20)

        # Center the icon in the container
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)

        parent_layout.addWidget(icon_container, 0, Qt.AlignmentFlag.AlignVCenter)

        # Text container (title + description)
        text_container = QWidget()
        text_container.setStyleSheet("background: transparent; border: none;")
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        # Section title (foreground color #fafafa)
        total_tasks = len(section["tasks"])
        title_label = QLabel(section['title'])
        title_label.setStyleSheet("""
            QLabel {
                color: #fafafa;
                font-size: 15px;
                font-weight: 500;
                background: transparent;
                border: none;
            }
        """)
        text_layout.addWidget(title_label)

        # Description (muted foreground #999999)
        descriptions = {
            "Getting Started": "Click the book icon in toolbar",
            "Using Shortcuts": "Press shortcuts to populate search",
            "Quick Actions": "Highlight text on flashcards",
            "Customization": "Explore settings and customize"
        }
        description = descriptions.get(section['title'], "Complete the tasks below")
        subtitle_label = QLabel(description)
        subtitle_label.setObjectName("subtitle")
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #999999;
                font-size: 13px;
                font-weight: 400;
                background: transparent;
                border: none;
            }
        """)
        text_layout.addWidget(subtitle_label)

        parent_layout.addWidget(text_container, 1, Qt.AlignmentFlag.AlignVCenter)

        # Right indicator container (checkmark or chevron)
        arrow_container = QWidget()
        arrow_container.setFixedSize(40, 40)
        arrow_container.setStyleSheet("background: transparent; border: none;")
        arrow_container_layout = QVBoxLayout(arrow_container)
        arrow_container_layout.setContentsMargins(0, 0, 0, 0)

        arrow = QLabel()
        arrow.setFixedSize(40, 40)
        arrow.setStyleSheet("""
            QLabel {
                background: #383838;
                border-radius: 20px;
            }
        """)

        # Chevron icon (default state, icon color #999999)
        chevron_right_svg = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#999999" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6"></polyline>
        </svg>"""
        chevron_icon = QLabel(arrow)
        chevron_icon.setFixedSize(20, 20)
        chevron_icon.setObjectName("chevron_icon")
        self.set_icon_from_svg(chevron_icon, chevron_right_svg, size=20)

        # Center the chevron
        chevron_layout = QVBoxLayout(arrow)
        chevron_layout.setContentsMargins(0, 0, 0, 0)
        chevron_layout.addWidget(chevron_icon, 0, Qt.AlignmentFlag.AlignCenter)

        arrow_container_layout.addWidget(arrow, 0, Qt.AlignmentFlag.AlignCenter)
        parent_layout.addWidget(arrow_container, 0, Qt.AlignmentFlag.AlignVCenter)

        parent_btn.setLayout(parent_layout)
        section_layout.addWidget(parent_btn)

        # Tasks container (collapsible)
        tasks_container = QWidget()
        tasks_container.setStyleSheet("background: #2c2c2c; border: none; margin: 0px; padding: 0px;")
        # Set size policy so hidden widget takes no space
        try:
            from PyQt6.QtWidgets import QSizePolicy
            tasks_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        except:
            from PyQt5.QtWidgets import QSizePolicy
            tasks_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        tasks_outer_layout = QVBoxLayout(tasks_container)
        tasks_outer_layout.setContentsMargins(56, 0, 24, 0)  # Left margin aligns with text, no bottom margin
        tasks_outer_layout.setSpacing(0)

        section_data = {
            "parent_btn": parent_btn,
            "arrow": arrow,
            "chevron_icon": chevron_icon,
            "title": title_label,
            "subtitle": subtitle_label,
            "tasks_container": tasks_container,
            "collapsed": True,
            "tasks": [],
            "completed_count": 0,
            "total_count": total_tasks
        }

        # Create tasks with connecting lines
        for idx, task in enumerate(section["tasks"]):
            is_first = idx == 0
            is_last = idx == len(section["tasks"]) - 1
            task_widget = self.create_task(task, is_first, is_last)
            tasks_outer_layout.addWidget(task_widget)
            section_data["tasks"].append({
                "widget": task_widget,
                "checkbox": task_widget.findChild(QWidget, "checkbox"),
                "label": task_widget.findChild(QLabel, "label"),
                "line_top": task_widget.findChild(QWidget, "line_top"),
                "line_bottom": task_widget.findChild(QWidget, "line_bottom"),
                "id": task["id"],
                "completed": False
            })

        section_layout.addWidget(tasks_container)
        section["_data"] = section_data
        tasks_container.hide()
        tasks_container.setMaximumHeight(0)  # Ensure no space when hidden
        parent_btn.clicked.connect(lambda: self.toggle_section(section_idx))

        # Ensure section is visible
        section_container.show()

        return section_container

    def create_task(self, task, is_first=False, is_last=False):
        """Create a task row with checkbox and connecting line"""
        task_row = QWidget()
        task_row.setStyleSheet("background: transparent; border: none;")
        task_layout = QHBoxLayout(task_row)
        task_layout.setContentsMargins(0, 4, 0, 4)
        task_layout.setSpacing(12)

        # Checkbox column with connecting line
        checkbox_column = QWidget()
        checkbox_column.setFixedWidth(24)
        checkbox_column.setStyleSheet("background: transparent; border: none;")
        checkbox_layout = QVBoxLayout(checkbox_column)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setSpacing(0)

        # Top line (hidden for first item) - dark theme
        line_top = QWidget()
        line_top.setObjectName("line_top")
        line_top.setFixedWidth(2)
        if is_first:
            line_top.setStyleSheet("background: transparent;")
        else:
            line_top.setStyleSheet("background: #4b5563;")
        checkbox_layout.addWidget(line_top, 1)

        # Checkbox (dark theme)
        checkbox = QWidget()
        checkbox.setObjectName("checkbox")
        checkbox.setFixedSize(24, 24)
        checkbox.setStyleSheet("""
            QWidget {
                background: #2c2c2c;
                border: 2px solid #4b5563;
                border-radius: 6px;
            }
        """)
        checkbox_layout.addWidget(checkbox, 0, Qt.AlignmentFlag.AlignHCenter)

        # Bottom line (hidden for last item) - dark theme
        line_bottom = QWidget()
        line_bottom.setObjectName("line_bottom")
        line_bottom.setFixedWidth(2)
        if is_last:
            line_bottom.setStyleSheet("background: transparent;")
        else:
            line_bottom.setStyleSheet("background: #4b5563;")
        checkbox_layout.addWidget(line_bottom, 1)

        task_layout.addWidget(checkbox_column)

        # Task text (foreground color #fafafa)
        label = QLabel(task["text"])
        label.setObjectName("label")
        label.setWordWrap(True)
        label.setStyleSheet("""
            QLabel {
                color: #fafafa;
                font-size: 13px;
                font-weight: 400;
                background: transparent;
                border: none;
                padding-top: 2px;
            }
        """)
        task_layout.addWidget(label, 1)

        return task_row

    def toggle_section(self, section_idx):
        """Toggle section collapse/expand"""
        section_data = self.sections[section_idx]["_data"]
        is_currently_collapsed = section_data["collapsed"]

        # Close all other sections first
        for idx, section in enumerate(self.sections):
            other_data = section["_data"]
            if idx != section_idx and not other_data["collapsed"]:
                other_data["collapsed"] = True
                other_data["tasks_container"].hide()
                other_data["tasks_container"].setMaximumHeight(0)
                # Reset chevron to right
                chevron_right_svg = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#999999" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="9 18 15 12 9 6"></polyline>
                </svg>"""
                self.set_icon_from_svg(other_data["chevron_icon"], chevron_right_svg, size=20)

        # Toggle current section
        section_data["collapsed"] = not is_currently_collapsed

        if section_data["collapsed"]:
            section_data["tasks_container"].hide()
            section_data["tasks_container"].setMaximumHeight(0)
            # Chevron right
            chevron_right_svg = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#999999" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"></polyline>
            </svg>"""
            self.set_icon_from_svg(section_data["chevron_icon"], chevron_right_svg, size=20)
        else:
            section_data["tasks_container"].setMaximumHeight(16777215)  # Qt's QWIDGETSIZE_MAX
            section_data["tasks_container"].show()
            # Chevron down
            chevron_down_svg = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#999999" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"></polyline>
            </svg>"""
            self.set_icon_from_svg(section_data["chevron_icon"], chevron_down_svg, size=20)

        # Force layout recalculation from bottom up
        section_data["tasks_container"].updateGeometry()
        self.section_widgets[section_idx].updateGeometry()

        # Resize to fit new content size after layouts update
        QTimer.singleShot(50, self.adjustSize)

    def complete_task(self, task_id):
        """Mark a task as completed by task ID"""
        # Find the task in all sections
        for section in self.sections:
            section_data = section["_data"]
            for task in section_data["tasks"]:
                if task["id"] == task_id and not task["completed"]:
                    # Mark task as completed
                    task["completed"] = True

                    # Update checkbox with blue checkmark (blue accent for dark theme)
                    task["checkbox"].setStyleSheet("""
                        QWidget {
                            background: #3b82f6;
                            border: 2px solid #3b82f6;
                            border-radius: 6px;
                        }
                    """)

                    # Add checkmark icon to checkbox
                    check_icon = QLabel(task["checkbox"])
                    check_icon.setFixedSize(20, 20)
                    check_svg = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>"""
                    self.set_icon_from_svg(check_icon, check_svg, size=20)
                    check_layout = QVBoxLayout(task["checkbox"])
                    check_layout.setContentsMargins(0, 0, 0, 0)
                    check_layout.addWidget(check_icon, 0, Qt.AlignmentFlag.AlignCenter)

                    # Update connecting lines to blue (blue accent)
                    if task["line_top"]:
                        task["line_top"].setStyleSheet("background: #3b82f6;")
                    if task["line_bottom"]:
                        task["line_bottom"].setStyleSheet("background: #3b82f6;")

                    # Strike through text (muted foreground)
                    task["label"].setStyleSheet("""
                        QLabel {
                            color: #999999;
                            font-size: 13px;
                            font-weight: 400;
                            background: transparent;
                            border: none;
                            padding-top: 2px;
                            text-decoration: line-through;
                        }
                    """)

                    # Update section progress
                    section_data["completed_count"] += 1
                    completed = section_data["completed_count"]
                    total = section_data["total_count"]

                    # If all tasks in section complete, show blue checkmark (blue accent)
                    if completed == total:
                        section_data["arrow"].setStyleSheet("""
                            QLabel {
                                background: #3b82f6;
                                border-radius: 20px;
                            }
                        """)
                        # Replace chevron with checkmark
                        checkmark_svg = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>"""
                        self.set_icon_from_svg(section_data["chevron_icon"], checkmark_svg, size=20)

                    # Update global progress
                    self.update_progress()

                    return

    def close_tutorial(self):
        """Close and complete tutorial"""
        self.fade_out()

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, value):
        self._opacity = value
        self.setWindowOpacity(value)

    opacity = pyqtProperty(float, get_opacity, set_opacity)

    def fade_in(self):
        """Fade in animation"""
        self.setWindowOpacity(0)
        self.show()

        anim = QPropertyAnimation(self, b"opacity")
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._fade_anim = anim  # Keep reference

    def fade_out(self, callback=None):
        """Fade out animation"""
        anim = QPropertyAnimation(self, b"opacity")
        anim.setDuration(200)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        if callback:
            anim.finished.connect(callback)
        anim.finished.connect(self.hide)
        anim.start()
        self._fade_anim = anim  # Keep reference


class TutorialOverlay(QWidget):
    """Semi-transparent overlay that darkens everything except highlighted area"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            # Make overlay transparent to mouse events so users can click through it
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        except:
            # PyQt5 fallback
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.highlight_rect = None

    def set_highlight(self, rect):
        """Set the area to keep clear (not darkened)"""
        self.highlight_rect = rect
        self.update()

    def paintEvent(self, event):
        """Draw semi-transparent overlay with cutout for highlight"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fill entire widget with semi-transparent black
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))

        # If there's a highlight area, cut it out
        if self.highlight_rect:
            # Create a path for the entire widget
            path = QPainterPath()
            # Convert QRect to QRectF for addRect
            rect_f = QRectF(self.rect())
            path.addRect(rect_f)

            # Subtract the highlight area
            highlight_path = QPainterPath()
            highlight_path.addRoundedRect(self.highlight_rect, 8, 8)
            path = path.subtracted(highlight_path)

            # Fill the path (everything except highlight)
            painter.fillPath(path, QColor(0, 0, 0, 120))


class TutorialManager(QWidget):
    """Manages the interactive tutorial checklist"""

    def __init__(self):
        super().__init__()
        self.checklist = None
        self.completed_tasks = set()
        self.main_window = None

    def start(self):
        """Start the tutorial"""
        # Create checklist panel
        self.checklist = TutorialChecklist(mw)

        # Position in bottom-left corner above footer (Edit button area)
        self.position_tutorial()

        # Show with fade in
        self.checklist.fade_in()

        # Connect close button to complete tutorial
        self.checklist.close_tutorial = self.complete_tutorial

        # Install event filter on main window to track movements
        self.main_window = mw
        mw.installEventFilter(self)

    def position_tutorial(self):
        """Position tutorial in bottom-left corner of main window"""
        if self.checklist and mw:
            margin = 16
            x = mw.x() + margin
            y = mw.y() + mw.height() - self.checklist.sizeHint().height() - margin - 60
            self.checklist.move(x, y)

    def eventFilter(self, obj, event):
        """Track main window movements and reposition tutorial"""
        if obj == self.main_window and self.checklist:
            try:
                # PyQt6
                event_type = event.type()
                if event_type == event.Type.Move or event_type == event.Type.Resize:
                    self.position_tutorial()
            except:
                # PyQt5
                from PyQt5.QtCore import QEvent
                if event.type() == QEvent.Move or event.type() == QEvent.Resize:
                    self.position_tutorial()
        return super().eventFilter(obj, event)

    def complete_tutorial(self):
        """Complete the tutorial and save state"""
        # Remove event filter
        if self.main_window:
            self.main_window.removeEventFilter(self)
            self.main_window = None

        # Hide checklist
        if self.checklist:
            self.checklist.fade_out()
            self.checklist = None

        # Save tutorial completed state
        config = mw.addonManager.getConfig(__name__) or {}
        config["tutorial_completed"] = True
        mw.addonManager.writeConfig(__name__, config)

        print("OpenEvidence: Tutorial completed!")

    def on_event(self, event_name):
        """Handle events from the addon and mark tasks as completed"""
        if not self.checklist:
            return

        # Map events to task indices
        event_to_task = {
            "panel_opened": 0,  # Task 0: Open the panel
            "shortcut_used": 2,  # Task 2: Use keyboard shortcut
            "text_highlighted": 3,  # Task 3: Select text for quick actions
            "settings_opened": 4,  # Task 4: Open settings
        }

        task_index = event_to_task.get(event_name)
        if task_index is not None and task_index not in self.completed_tasks:
            self.completed_tasks.add(task_index)
            self.checklist.complete_task(task_index)

            # Auto-complete task 1 (click in search box) when task 2 (shortcut) is done
            if task_index == 2 and 1 not in self.completed_tasks:
                self.completed_tasks.add(1)
                self.checklist.complete_task(1)


# Global tutorial manager instance
_tutorial_manager = None


def get_tutorial_manager():
    """Get or create the tutorial manager"""
    global _tutorial_manager
    if _tutorial_manager is None:
        _tutorial_manager = TutorialManager()
    return _tutorial_manager


def start_tutorial():
    """Start the tutorial"""
    manager = get_tutorial_manager()
    manager.start()


def tutorial_event(event_name):
    """Notify tutorial of an event"""
    manager = get_tutorial_manager()
    manager.on_event(event_name)

    # Also notify tutorial accordion if it exists
    from .tutorial_accordion import get_tutorial_accordion
    accordion = get_tutorial_accordion()
    if accordion:
        accordion.handle_event(event_name)
