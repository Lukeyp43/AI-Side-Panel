"""
Tutorial accordion widget that floats in the bottom left corner.
Shows after onboarding is complete to guide users through key features.
"""

import json
from aqt import mw
from aqt.qt import *

try:
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                  QPushButton, QCheckBox, QFrame)
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
    from PyQt6.QtGui import QPainter, QCursor, QPixmap
    from PyQt6.QtSvg import QSvgRenderer
except ImportError:
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                  QPushButton, QCheckBox, QFrame)
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
    from PyQt5.QtGui import QPainter, QCursor, QPixmap
    from PyQt5.QtSvg import QSvgRenderer


class AccordionItem(QWidget):
    """Single accordion item with icon, title, description, and collapsible tasks"""

    toggled = pyqtSignal()

    def __init__(self, icon_svg, title, description, tasks, parent=None):
        super().__init__(parent)
        self.icon_svg = icon_svg
        self.title_text = title
        self.description_text = description
        self.tasks_data = tasks
        self.is_expanded = False
        self.task_checkboxes = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button
        self.header_btn = QPushButton()
        self.header_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.header_btn.setFixedHeight(72)
        self.header_btn.clicked.connect(self.toggle)

        header_layout = QHBoxLayout(self.header_btn)
        header_layout.setContentsMargins(24, 16, 24, 16)
        header_layout.setSpacing(16)

        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.update_icon()
        header_layout.addWidget(self.icon_label)

        # Title and description
        text_container = QWidget()
        text_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.title_label = QLabel(self.title_text)
        self.title_label.setStyleSheet("color: white; font-size: 14px; font-weight: 500; background: transparent; border: none;")
        text_layout.addWidget(self.title_label)

        self.description_label = QLabel(self.description_text)
        self.description_label.setStyleSheet("color: #9ca3af; font-size: 13px; background: transparent; border: none;")
        text_layout.addWidget(self.description_label)

        header_layout.addWidget(text_container)
        header_layout.addStretch()

        # Chevron
        self.chevron_label = QLabel()
        self.chevron_label.setFixedSize(20, 20)
        self.chevron_label.setStyleSheet("background: transparent; border: none;")
        self.chevron_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.update_chevron()
        header_layout.addWidget(self.chevron_label)

        self.header_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.03);
            }
        """)

        layout.addWidget(self.header_btn)

        # Content container
        self.content_widget = QWidget()
        self.content_widget.setVisible(False)
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 16)
        content_layout.setSpacing(0)

        if self.tasks_data:
            tasks_container = QWidget()
            tasks_layout = QVBoxLayout(tasks_container)
            tasks_layout.setContentsMargins(64, 0, 24, 0)
            tasks_layout.setSpacing(8)

            for task_data in self.tasks_data:
                task_widget = self.create_task_widget(task_data)
                tasks_layout.addWidget(task_widget)

            content_layout.addWidget(tasks_container)

        layout.addWidget(self.content_widget)

    def create_task_widget(self, task_data):
        """Create a single task row with checkbox"""
        task_widget = QWidget()
        task_layout = QHBoxLayout(task_widget)
        task_layout.setContentsMargins(0, 0, 0, 0)
        task_layout.setSpacing(12)

        checkbox = QCheckBox(task_data["text"])
        checkbox.setChecked(task_data["completed"])
        checkbox.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        checkbox.setStyleSheet("""
            QCheckBox {
                color: #d1d5db;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid #6b7280;
                background: #1f2937;
            }
            QCheckBox::indicator:hover {
                border-color: #9ca3af;
            }
            QCheckBox::indicator:checked {
                background: #3b82f6;
                border-color: #3b82f6;
            }
            QCheckBox:checked {
                color: #6b7280;
            }
        """)
        checkbox.stateChanged.connect(self.on_task_changed)
        self.task_checkboxes.append(checkbox)
        task_layout.addWidget(checkbox)

        return task_widget

    def on_task_changed(self):
        self.update_icon()
        self.toggled.emit()

    def is_all_tasks_completed(self):
        return all(cb.isChecked() for cb in self.task_checkboxes)

    def get_completed_count(self):
        return sum(1 for cb in self.task_checkboxes if cb.isChecked())

    def get_total_count(self):
        return len(self.task_checkboxes)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.content_widget.setVisible(self.is_expanded)
        self.update_chevron()

    def update_icon(self):
        if self.is_all_tasks_completed():
            check_svg = """<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="20" cy="20" r="20" fill="#3b82f6"/>
                <path d="M12 20 L17 25 L28 14" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>"""
            self.set_svg_icon(self.icon_label, check_svg)
        else:
            wrapped_svg = f"""<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="20" cy="20" r="20" fill="#374151"/>
                <g transform="translate(10, 10)">
                    {self.icon_svg}
                </g>
            </svg>"""
            self.set_svg_icon(self.icon_label, wrapped_svg)

    def update_chevron(self):
        if self.is_expanded:
            chevron_svg = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M6 9 L12 15 L18 9" stroke="#9ca3af" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>"""
        else:
            chevron_svg = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M9 6 L15 12 L9 18" stroke="#9ca3af" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>"""
        self.set_svg_icon(self.chevron_label, chevron_svg)

    def set_svg_icon(self, label, svg_str):
        from aqt.qt import QByteArray
        svg_bytes = QByteArray(svg_str.encode())
        renderer = QSvgRenderer(svg_bytes)
        pixmap = QPixmap(label.size())
        try:
            pixmap.fill(Qt.GlobalColor.transparent)
        except:
            pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        label.setPixmap(pixmap)


class TutorialAccordion(QWidget):
    """Floating tutorial accordion in bottom left corner"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self.accordion_items = []

        # Make this a floating widget
        try:
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        except:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(420)

        self.setup_ui()
        self.position_bottom_left()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(0)

        # Container with border and shadow
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: #171717;
                border: 1px solid #262626;
                border-radius: 8px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background: transparent; border-bottom: 1px solid #262626;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 16, 16, 16)
        header_layout.setSpacing(0)

        self.title_label = QLabel("Just one step ahead!")
        self.title_label.setStyleSheet("color: white; font-size: 18px; font-weight: 500;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        # Collapse button
        self.collapse_btn = QPushButton()
        self.collapse_btn.setFixedSize(24, 24)
        self.collapse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.collapse_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
        """)
        minus_svg = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M5 12 L19 12" stroke="white" stroke-width="2" stroke-linecap="round"/>
        </svg>"""
        self.set_svg_icon(self.collapse_btn, minus_svg, 24)
        self.collapse_btn.clicked.connect(self.toggle_collapse)
        header_layout.addWidget(self.collapse_btn)

        container_layout.addWidget(header)

        # Content
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Progress section
        progress_widget = QWidget()
        progress_widget.setStyleSheet("background: transparent; border-bottom: 1px solid #262626;")
        progress_layout = QHBoxLayout(progress_widget)
        progress_layout.setContentsMargins(24, 20, 24, 20)
        progress_layout.setSpacing(12)

        emoji_label = QLabel("👋")
        emoji_label.setStyleSheet("font-size: 24px;")
        progress_layout.addWidget(emoji_label)

        progress_bar_container = QWidget()
        progress_bar_layout = QVBoxLayout(progress_bar_container)
        progress_bar_layout.setContentsMargins(0, 0, 0, 0)
        progress_bar_layout.setSpacing(0)

        self.progress_bar = QFrame()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("background: #262626; border-radius: 4px;")

        self.progress_fill = QFrame(self.progress_bar)
        self.progress_fill.setFixedHeight(8)
        self.progress_fill.setStyleSheet("background: #404040; border-radius: 4px;")
        self.progress_fill.setFixedWidth(0)

        progress_bar_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(progress_bar_container, 1)

        self.percentage_label = QLabel("0%")
        self.percentage_label.setStyleSheet("color: #9ca3af; font-size: 14px;")
        progress_layout.addWidget(self.percentage_label)

        content_layout.addWidget(progress_widget)

        # Accordion items
        accordion_container = QWidget()
        accordion_container.setStyleSheet("background: transparent;")
        self.accordion_layout = QVBoxLayout(accordion_container)
        self.accordion_layout.setContentsMargins(0, 0, 0, 0)
        self.accordion_layout.setSpacing(0)

        # Define items
        items_data = [
            {
                "icon": '<path d="M2 3 L2 21 L16 21 L16 7 L12 3 Z M12 3 L12 7 L16 7" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>',
                "title": "Getting Started",
                "description": "Click the book icon in toolbar",
                "tasks": [
                    {"text": "Click the book icon 📖 in toolbar", "completed": False}
                ]
            },
            {
                "icon": '<rect x="2" y="2" width="6" height="6" rx="1" stroke="white" stroke-width="1.5" fill="none"/><rect x="11" y="2" width="6" height="6" rx="1" stroke="white" stroke-width="1.5" fill="none"/><rect x="2" y="11" width="6" height="6" rx="1" stroke="white" stroke-width="1.5" fill="none"/>',
                "title": "Using Shortcuts",
                "description": "Press shortcuts to populate search",
                "tasks": [
                    {"text": "Press Ctrl+Shift+S (Cmd+Shift+S on Mac)", "completed": False}
                ]
            },
            {
                "icon": '<circle cx="9" cy="9" r="7" stroke="white" stroke-width="1.5" fill="none"/><path d="M14 14 L18 18" stroke="white" stroke-width="1.5" stroke-linecap="round"/>',
                "title": "Quick Actions",
                "description": "Highlight text on flashcards",
                "tasks": [
                    {"text": "Select text on a flashcard", "completed": False}
                ]
            },
            {
                "icon": '<path d="M9 2 L15 2 L18 9 L15 16 L9 16 L6 9 Z" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>',
                "title": "Customization",
                "description": "Explore settings and customize",
                "tasks": [
                    {"text": "Open settings and explore options", "completed": False}
                ]
            }
        ]

        for item_data in items_data:
            item = AccordionItem(
                item_data["icon"],
                item_data["title"],
                item_data["description"],
                item_data["tasks"]
            )
            item.toggled.connect(self.update_progress)
            self.accordion_items.append(item)
            self.accordion_layout.addWidget(item)

            if item != self.accordion_items[-1]:
                separator = QFrame()
                separator.setFixedHeight(1)
                separator.setStyleSheet("background: #262626;")
                self.accordion_layout.addWidget(separator)

        content_layout.addWidget(accordion_container)
        container_layout.addWidget(self.content_widget)
        main_layout.addWidget(container)

        # Expand first item
        if self.accordion_items:
            self.accordion_items[0].toggle()

        self.update_progress()

    def position_bottom_left(self):
        """Position widget in bottom left corner of Anki window"""
        if mw:
            # Ensure widget is fully laid out before positioning
            self.adjustSize()

            # Get main window geometry
            mw_geometry = mw.geometry()

            # Position in bottom left of Anki window
            # Use 35% from bottom to ensure no overflow
            x = mw_geometry.x() + 16  # 16px from left edge
            bottom_offset = int(mw_geometry.height() * 0.35)  # 35% from bottom
            y = mw_geometry.y() + mw_geometry.height() - self.height() - bottom_offset

            # Safety check: ensure widget doesn't overflow top of window
            min_y = mw_geometry.y() + 60  # At least 60px from top (menu bar)
            y = max(y, min_y)

            self.move(x, y)

    def toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        self.content_widget.setVisible(not self.is_collapsed)

        # Reposition after collapse/expand
        QTimer.singleShot(10, self.position_bottom_left)

    def mark_task_complete(self, item_index, task_index):
        if 0 <= item_index < len(self.accordion_items):
            item = self.accordion_items[item_index]
            if 0 <= task_index < len(item.task_checkboxes):
                item.task_checkboxes[task_index].setChecked(True)
                self.update_progress()

    def handle_event(self, event_name):
        """Handle tutorial events to complete tasks"""
        event_mapping = {
            "panel_opened": (0, 0),
            "shortcut_used": (1, 0),
            "text_highlighted": (2, 0),
            "settings_opened": (3, 0)
        }

        if event_name in event_mapping:
            item_idx, task_idx = event_mapping[event_name]
            self.mark_task_complete(item_idx, task_idx)

    def update_progress(self):
        total = sum(item.get_total_count() for item in self.accordion_items)
        completed = sum(item.get_completed_count() for item in self.accordion_items)

        if total > 0:
            percentage = int((completed / total) * 100)
        else:
            percentage = 0

        self.percentage_label.setText(f"{percentage}%")

        bar_width = self.progress_bar.width()
        fill_width = int(bar_width * (percentage / 100))
        self.progress_fill.setFixedWidth(fill_width)

        # Complete tutorial when all done
        if total > 0 and completed == total:
            QTimer.singleShot(1000, self.complete_tutorial)

    def complete_tutorial(self):
        """Mark tutorial as complete and hide"""
        try:
            config = mw.addonManager.getConfig(__name__) or {}
            config["tutorial_completed"] = True
            mw.addonManager.writeConfig(__name__, config)
            print("OpenEvidence: Tutorial completed!")
        except Exception as e:
            print(f"OpenEvidence: Error saving tutorial config: {e}")

        # Fade out and close
        self.close()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(10, self.update_progress)

    def set_svg_icon(self, widget, svg_str, size):
        from aqt.qt import QByteArray, QIcon
        svg_bytes = QByteArray(svg_str.encode())
        renderer = QSvgRenderer(svg_bytes)
        pixmap = QPixmap(size, size)
        try:
            pixmap.fill(Qt.GlobalColor.transparent)
        except:
            pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        if isinstance(widget, QPushButton):
            widget.setIcon(QIcon(pixmap))
            widget.setIconSize(QSize(size, size))
        else:
            widget.setPixmap(pixmap)


# Global reference to keep tutorial alive
_tutorial_accordion = None


def show_tutorial_accordion():
    """Show the tutorial accordion in bottom left"""
    global _tutorial_accordion

    if _tutorial_accordion is None:
        _tutorial_accordion = TutorialAccordion(mw)

    _tutorial_accordion.show()
    _tutorial_accordion.raise_()
    return _tutorial_accordion


def get_tutorial_accordion():
    """Get the tutorial accordion instance"""
    return _tutorial_accordion
