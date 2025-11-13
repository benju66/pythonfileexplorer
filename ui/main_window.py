import os
import shutil
from functools import partial
from typing import Optional, Dict, List, Set, Any, Tuple, Union

from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTreeView,
    QToolBar, QPushButton, QLineEdit, QDockWidget, QLabel, QMenu, 
    QSplitter, QDialog, QComboBox, QCheckBox, QTableWidget, 
    QTableWidgetItem, QMessageBox, QTabWidget, QToolButton, QSizePolicy
)
from PyQt6.QtCore import Qt, QObject, QEvent, QTimer, QRect, QPropertyAnimation, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QAction

from ui.file_tree import FileTree
from ui.tab_manager import TabManager
from ui.panels.preview_panel import PreviewPanel
from ui.panels.pinned_panel import PinnedPanel
from ui.panels.recent_items_panel import RecentItemsPanel
from ui.panels.templates_panel import TemplatesPanel
from ui.settings_dialog import SettingsDialog
from ui.toolbar import Toolbar
from ui.panels.procore_links_panel import ProcoreQuickLinksPanel
from ui.panels.bookmarks_panel import BookmarksPanel
from ui.panels.to_do_panel import ToDoPanel
from ui.panels.one_note_panel import OneNotePanel
from ui.draggable_tab_bar import DraggableTabBar

from modules.search import FileSearch
from modules.preview import FilePreview
from modules.automation import Automation
from modules.file_operations import create_new_folder, delete_item, rename_item
from modules.settings_manager import SettingsManager
from modules.cloud_integration import OneDriveIntegration
from modules.pinned_manager import PinnedManager
from modules.metadata_manager import MetadataManager


# Constants for UI elements
DEFAULT_DOCK_WIDTH = 200
QWIDGETSIZE_MAX = 16777215
DOCK_AREA_STYLESHEET = """
    QMainWindow::separator {
        background-color: transparent;
        margin: 0px;
        padding: 0px;
        width: 3px;
    }
    QMainWindow::separator:hover {
        background-color: #0083DB;
    }
"""
DROP_INDICATOR_STYLESHEET = """
    background-color: rgba(0, 131, 219, 0.85);
    color: white;
    border: 3px dashed white;
    border-radius: 3px;
    font-weight: bold;
    padding: 10px;
"""


class AutoResizeDock(QDockWidget):
    """
    Subclass of QDockWidget that stores original width for collapsing/expanding
    but delegates actual collapse/expand behavior to MainWindowContainer.
    """
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._original_width = DEFAULT_DOCK_WIDTH
        self.setObjectName(title.lower().replace(" ", "_") + "_dock")


class MainWindowContainer(QWidget):
    """
    Container widget that hosts a QMainWindow with dockable panels and a tab manager.
    Multiple instances of this class can be created as tabs within MainWindowTabs.
    """
    # Class-level tracking of all containers
    all_main_windows = []

    def __init__(self, parent=None, settings_file="data/settings.json"):
        super().__init__(parent)

        # Track active tab manager (for split view)
        self.active_tab_manager = None
        self._dock_widths = {}
        self._current_animation = None
        self.panels_in_console = set()

        # Initialize layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Initialize settings
        self.settings_manager = SettingsManager(settings_file)

        # Basic navigation
        self.history = []
        self.current_history_index = -1
        self.setAcceptDrops(True)

        # Create QMainWindow for dockable areas
        self.dock_area = QMainWindow()
        self.dock_area.setDockNestingEnabled(False)
        self.dock_area.setDockOptions(
            QMainWindow.DockOption.AllowTabbedDocks | 
            QMainWindow.DockOption.AnimatedDocks
        )
        self.dock_area.setStyleSheet(DOCK_AREA_STYLESHEET)

        # Create main tab manager (center area)
        self.tab_manager = TabManager(self)
        self.tab_manager.pin_item_requested.connect(self.handle_pin_request)
        self.tab_manager.currentChanged.connect(self.update_file_tree_connections)
        self.tab_manager.active_manager_changed.connect(self.on_active_manager_changed)

        # Create center dock widget
        self.center_dock = AutoResizeDock("Main Content", self.dock_area)
        self.center_dock.setObjectName("center_dock")
        self.center_dock.setWidget(self.tab_manager)
        self.dock_area.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.center_dock)

        # Create console area (hidden by default)
        self.setup_console_area()

        # Create other dockable panels
        self.create_dockable_panels()

        # Install event filters
        self.install_event_handlers()

        # Add the dock area to the layout
        self.layout.addWidget(self.dock_area)

        # Connect pinned panel signals if available
        self.connect_pinned_panel_signals()

        # Finally, restore dock positions from saved settings
        self.restore_container_docks()

    def setup_console_area(self):
        """Create and setup the console area (initially hidden)."""
        self.console_area = QDockWidget("Console", self.dock_area)
        self.console_area.setObjectName("console_area")
        self.console_area.setVisible(False)
        self.console_area.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.console_area.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        # Add placeholder widget to control height
        self.console_placeholder = QWidget()
        self.console_placeholder.setMinimumHeight(100)
        self.console_area.setWidget(self.console_placeholder)

        # Add to bottom dock area
        self.dock_area.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_area)

        # Create drop indicator
        self.drop_indicator = QLabel(self.dock_area)
        self.drop_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_indicator.setText("Drop Here to Show Console")
        self.drop_indicator.setStyleSheet(DROP_INDICATOR_STYLESHEET)
        self.drop_indicator.hide()

    def install_event_handlers(self):
        """Install event filters for dock area and widgets."""
        self.dock_area.installEventFilter(self)

    def restore_container_docks(self):
        """Restore dock layout from saved settings."""
        import base64

        geom_b64 = self.settings_manager.get_setting("container_geometry_b64")
        state_b64 = self.settings_manager.get_setting("container_state_b64")

        if geom_b64:
            try:
                geom_bytes = base64.b64decode(geom_b64)
                self.dock_area.restoreGeometry(geom_bytes)
            except Exception as e:
                print(f"Error restoring geometry: {e}")

        if state_b64:
            try:
                state_bytes = base64.b64decode(state_b64)
                self.dock_area.restoreState(state_bytes)
            except Exception as e:
                print(f"Error restoring state: {e}")

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        Unified event filter to handle console drag/drop.
        
        Args:
            obj: The object that triggered the event
            event: The event that occurred
            
        Returns:
            bool: True if the event was handled, False otherwise
        """
        # Handle dock area events (console related)
        if obj == self.dock_area:
            if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                return self._handle_dock_area_drag(event)
            elif event.type() == QEvent.Type.Drop:
                return self._handle_dock_area_drop(event)
            elif event.type() == QEvent.Type.DragLeave:
                self.drop_indicator.hide()
            elif event.type() in (QEvent.Type.ChildAdded, QEvent.Type.ChildRemoved):
                QTimer.singleShot(100, self.update_console_panel_tracking)

        # Handle dock widget events (console tracking only)
        elif isinstance(obj, QDockWidget) and event.type() == QEvent.Type.MouseButtonPress:
            # Detect if panel is moved from console
            if obj in self.panels_in_console:
                QTimer.singleShot(100, self.update_console_panel_tracking)

        return super().eventFilter(obj, event)

    def _handle_dock_area_drag(self, event: QEvent) -> bool:
        """
        Handle drag events in the dock area for console showing/hiding.
        
        Args:
            event: The drag event
            
        Returns:
            bool: True if event was handled
        """
        # Change this line:
        # pos = event.pos()
        # To this:
        pos = event.position().toPoint()
        
        # Rest of the method remains the same
        # Define bottom zone (70% of window height)
        bottom_zone_height = self.dock_area.height() * 0.70
        bottom_zone = QRect(
            0,
            self.dock_area.height() - bottom_zone_height,
            self.dock_area.width(),
            bottom_zone_height
        )
        
        if bottom_zone.contains(pos):
            # Accept the action to prevent Qt from docking elsewhere
            event.acceptProposedAction()
            
            # Show indicator if console not visible
            if not self.console_area.isVisible():
                self.drop_indicator.setGeometry(
                    bottom_zone.x() + 20,
                    bottom_zone.y() + 20,
                    bottom_zone.width() - 40,
                    bottom_zone.height() - 40
                )
                self.drop_indicator.raise_()
                self.drop_indicator.show()
            
            return True
        else:
            self.drop_indicator.hide()
            
        return False

    def _handle_dock_area_drop(self, event: QEvent) -> bool:
        """
        Handle drop events in the dock area for console activation.
        
        Args:
            event: The drop event
            
        Returns:
            bool: True if event was handled
        """
        # Hide the drop indicator if visible
        if self.drop_indicator.isVisible():
            self.drop_indicator.hide()
            
            # Animate console showing
            self.console_area.setVisible(True)
            animation = QPropertyAnimation(self.console_area, b"geometry")
            animation.setDuration(200)
            target_geom = QRect(
                0,
                self.dock_area.height() - 200,  # 200px tall
                self.dock_area.width(),
                200
            )
            animation.setStartValue(QRect(
                0,
                self.dock_area.height(),
                self.dock_area.width(),
                0
            ))
            animation.setEndValue(target_geom)
            
            self._current_animation = animation
            animation.start()
            
        return True

    def update_console_panel_tracking(self):
        """
        Update tracking of which panels are in the console area.
        """
        old_panels = self.panels_in_console.copy()
        self.panels_in_console.clear()
        
        for dock in self.dock_area.findChildren(QDockWidget):
            if dock != self.console_area and \
               self.dock_area.dockWidgetArea(dock) == Qt.DockWidgetArea.BottomDockWidgetArea:
                self.panels_in_console.add(dock)
                
                # Monitor dock position changes
                if not hasattr(dock, "_position_monitored"):
                    dock.installEventFilter(self)
                    dock._position_monitored = True
        
        # Show console if we have panels
        if self.panels_in_console and not self.console_area.isVisible():
            self.console_area.setVisible(True)
            
        # Check if console is now empty
        if old_panels and not self.panels_in_console:
            self.check_console_empty()

    def check_console_empty(self):
        """Check if console is empty and animate closing if so."""
        # Update tracking one more time
        self.update_console_panel_tracking()
        
        if not self.panels_in_console and self.console_area.isVisible():
            animation = QPropertyAnimation(self.console_area, b"geometry")
            animation.setDuration(200)
            current_geom = self.console_area.geometry()
            animation.setStartValue(current_geom)
            animation.setEndValue(QRect(
                current_geom.x(),
                self.dock_area.height(),
                current_geom.width(),
                0
            ))
            self._current_animation = animation
            animation.finished.connect(self._hide_console_when_animation_done)
            animation.start()

    def _hide_console_when_animation_done(self):
        """Hide console after animation finishes."""
        self.console_area.setVisible(False)
        self._current_animation = None

    def dragEnterEvent(self, event):
        """Accept dock widget or file/folder drags."""
        if event.mimeData().hasFormat("application/x-qdockwidget") or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """Accept dock widget or file/folder drag moves."""
        if event.mimeData().hasFormat("application/x-qdockwidget") or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        """Handle file/folder drops by forwarding to active FileTree."""
        if event.mimeData().hasFormat("application/x-qdockwidget"):
            event.acceptProposedAction()  # Let Qt handle re-docking
        elif event.mimeData().hasUrls():
            current_tab = self.tab_manager.currentWidget()
            if current_tab:
                file_tree = current_tab.findChild(FileTree)
                if file_tree:
                    file_tree.dropEvent(event)
                    return
        super().dropEvent(event)

    def closeEvent(self, event):
        """Save dock layout state when container is closed."""
        import base64
        
        try:
            # Save geometry and state
            geom_bytes = self.dock_area.saveGeometry()
            state_bytes = self.dock_area.saveState()
            
            # Store as base64 strings
            self.settings_manager.update_setting(
                "container_geometry_b64",
                base64.b64encode(geom_bytes).decode("utf-8")
            )
            self.settings_manager.update_setting(
                "container_state_b64",
                base64.b64encode(state_bytes).decode("utf-8")
            )
        except Exception as e:
            print(f"Error saving dock layout: {e}")
            
        super().closeEvent(event)

    def resizeEvent(self, event):
        """Update console area size during resize."""
        super().resizeEvent(event)
        if hasattr(self, 'console_area') and self.console_area.isVisible():
            console_height = self.console_area.height()
            self.console_area.setGeometry(
                0,
                self.dock_area.height() - console_height,
                self.dock_area.width(),
                console_height
            )

    def toggle_panel(self, dock_attr: str):
        """
        Toggle visibility of a dock panel by attribute name.
        
        Args:
            dock_attr: The attribute name of the dock widget to toggle
        """
        if not hasattr(self, dock_attr):
            print(f"[ERROR] {dock_attr} was not created.")
            return
        
        dock_widget = getattr(self, dock_attr)
        
        # Get current visibility state
        is_visible = dock_widget.isVisible()
        
        if is_visible:
            # Store width before hiding
            current_width = dock_widget.width()
            if current_width > 10:  # Only store if not collapsed
                dock_widget._original_width = current_width
            
            # Hide the panel
            dock_widget.setVisible(False)
        else:
            # Show the panel
            dock_widget.setVisible(True)
            
            # Restore saved width
            stored_width = getattr(dock_widget, "_original_width", DEFAULT_DOCK_WIDTH)
            
            # Reset size constraints
            dock_widget.setMinimumWidth(20)
            dock_widget.setMaximumWidth(QWIDGETSIZE_MAX)
            
            # Apply saved width
            if stored_width > 10:
                dock_widget.resize(stored_width, dock_widget.height())

    # Panel toggle methods that use the common toggle_panel implementation
    def toggle_pinned_panel(self): 
        self.toggle_panel("pinned_dock")

    def toggle_one_note_panel(self):
        self.toggle_panel("one_note_dock")

    def toggle_bookmarks_panel(self):
        self.toggle_panel("bookmarks_dock")

    def toggle_todo_panel(self):
        self.toggle_panel("to_do_dock")
    
    def toggle_procore_panel(self):
        self.toggle_panel("procore_dock")

    def collapse_dock_to_separator(self, dock_widget: QDockWidget):
        """
        Collapse a dock widget to just a separator width.
        
        Args:
            dock_widget: The dock widget to collapse
        """
        if not dock_widget.isVisible():
            return
            
        # Store current width for later restoration
        dock_name = dock_widget.objectName()
        if not hasattr(self, '_dock_widths'):
            self._dock_widths = {}
            
        self._dock_widths[dock_name] = dock_widget.width()
        
        # Set minimum size constraints
        dock_widget.setMinimumWidth(3)
        dock_widget.setMaximumWidth(3)
        dock_widget.setFixedWidth(3)

    def expand_dock_from_separator(self, dock_widget: QDockWidget):
        """
        Restore a dock widget from collapsed separator state.
        
        Args:
            dock_widget: The dock widget to expand
        """
        dock_name = dock_widget.objectName()
        
        # Reset size constraints
        dock_widget.setMinimumWidth(50)
        dock_widget.setMaximumWidth(QWIDGETSIZE_MAX)
        
        # Restore previous width if available
        if hasattr(self, '_dock_widths') and dock_name in self._dock_widths:
            stored_width = self._dock_widths[dock_name]
            if stored_width > 10:
                dock_widget.setFixedWidth(stored_width)
            else:
                dock_widget.setFixedWidth(DEFAULT_DOCK_WIDTH)
        else:
            dock_widget.setFixedWidth(DEFAULT_DOCK_WIDTH)
        
        # Remove fixed width constraint after restoring
        QTimer.singleShot(0, lambda: dock_widget.setFixedWidth(QWIDGETSIZE_MAX))

    def toggle_dock_separator_state(self, dock_widget: QDockWidget):
        """
        Toggle a dock widget between normal and separator-only states.
        
        Args:
            dock_widget: The dock widget to toggle
        """
        # Check if dock is collapsed
        if dock_widget.width() <= 5:
            self.expand_dock_from_separator(dock_widget)
        else:
            self.collapse_dock_to_separator(dock_widget)

    def install_separator_click_handlers(self):
        """Install event filters on all dock widgets for edge click handling."""
        for dock in self.dock_area.findChildren(QDockWidget):
            # Set object name if needed
            if not dock.objectName():
                dock.setObjectName(f"dock_{id(dock)}")
                
            # Install event filter for edge clicks
            dock.installEventFilter(self)

    def toggle_split_view(self, target_path=None):
        """
        Toggle between single-pane and split-view mode.
        
        Args:
            target_path: Optional path to use for right pane
        """
        import os
        from PyQt6.QtWidgets import QSplitter
        from PyQt6.QtCore import Qt
        from ui.file_tree import FileTree

        # Check if already in split view
        splitter_active = (
            getattr(self, "splitter", None) is not None
            and self.splitter.count() > 1
        )
        
        if splitter_active:
            # Disable split view
            right_tab_manager = self.splitter.widget(1)
            if right_tab_manager:
                self.splitter.removeWidget(right_tab_manager)
                right_tab_manager.deleteLater()

            self.splitter.deleteLater()
            self.splitter = None

            # Restore single pane
            self.dock_area.setCentralWidget(self.tab_manager)
            print("✅ Split view disabled.")
            return

        # Determine path for new right pane
        if target_path:
            # From context menu
            normalized_path = os.path.normpath(target_path)
            if not os.path.isdir(normalized_path):
                print(f"[WARNING] Python can't confirm '{normalized_path}', using it anyway.")
            current_path = normalized_path
            print(f"[DEBUG] Using forced target path for split: {current_path}")
        else:
            # Get path from current tab
            current_path = self._determine_split_view_path()

        # Create splitter and add existing tab_manager
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.dock_area.takeCentralWidget()  
        self.splitter.addWidget(self.tab_manager)

        # Create new tab manager for right pane
        self.right_tab_manager = TabManager()
        self.right_tab_manager.active_manager_changed.connect(self.on_active_manager_changed)
        folder_name = os.path.basename(current_path) or current_path
        self.right_tab_manager.add_new_tab(
            title=folder_name,
            root_path=current_path
        )

        # Set up splitter
        self.splitter.addWidget(self.right_tab_manager)
        self.dock_area.setCentralWidget(self.splitter)
        self.splitter.setSizes([1, 1])

        print(f"✅ Split view enabled at path: {current_path}")

    def _determine_split_view_path(self) -> str:
        """
        Determine the path to use for the right pane in split view.
        
        Returns:
            str: The path to use
        """
        import os
        
        # Default fallback
        current_path = "C:/"  
        
        current_tab = self.tab_manager.currentWidget()
        if current_tab:
            file_tree = current_tab.findChild(FileTree)
            if file_tree:
                # Try last clicked folder
                if file_tree.current_folder_path and os.path.isdir(file_tree.current_folder_path):
                    current_path = os.path.normpath(file_tree.current_folder_path)
                    print(f"[DEBUG] Using last clicked folder: {current_path}")
                else:
                    # Fall back to tab's root path
                    raw_path = file_tree.file_model.rootPath()
                    normalized_path = os.path.normpath(raw_path)
                    if not os.path.isdir(normalized_path):
                        print(f"[WARNING] Python can't confirm '{normalized_path}', using it anyway.")
                    current_path = normalized_path
                    print(f"[DEBUG] Using left tab root path for split: {current_path}")
            else:
                print("[WARNING] No FileTree found in current tab. Using 'C:/' fallback.")
        else:
            print("[WARNING] No current tab found. Using 'C:/' fallback.")
            
        return current_path

    def handle_pin_request(self, file_path: str):
        """
        Handle pin requests from nested tabs or context menus.
        
        Args:
            file_path: Path to pin
        """
        try:
            # Validate path
            if not file_path or not os.path.exists(file_path):
                print(f"[WARNING] Cannot pin non-existent or empty path: {file_path}")
                return

            # Check for pinned_panel
            if not hasattr(self, 'pinned_panel'):
                print("[ERROR] No pinned_panel found in this container.")
                return

            print(f"[DEBUG] Handling pin request for: {file_path}")

            # Pin the item
            self.pinned_panel.pin_item(file_path)

            # Refresh pinned items across windows
            main_window = self.window()
            if hasattr(main_window, 'refresh_all_pinned_panels'):
                main_window.refresh_all_pinned_panels(file_path)

        except Exception as e:
            print(f"[ERROR] Failed to handle pin request: {str(e)}")

    def update_active_tab(self):
        """Update UI to reflect the currently active tab."""
        active_tab_manager = None

        # Determine which tab manager is active
        if hasattr(self, "splitter") and self.splitter and self.splitter.count() > 1:
            if self.splitter.widget(1).hasFocus():
                active_tab_manager = self.splitter.widget(1)
            else:
                active_tab_manager = self.splitter.widget(0)
        else:
            active_tab_manager = self.tab_manager

        if not active_tab_manager:
            print("[ERROR] No active tab manager found.")
            return

        # Update address bar from active tab
        current_tab = active_tab_manager.currentWidget()
        if current_tab:
            file_tree = current_tab.findChild(FileTree)
            if file_tree:
                selected_path = file_tree.file_model.rootPath()
                self.update_address_bar(selected_path)
                print(f"✅ Active tab updated: {selected_path}")

    def on_active_manager_changed(self, manager, path):
        """
        Handle tab manager activation.
        
        Args:
            manager: The activated tab manager
            path: The current path in the activated manager
        """
        self.active_tab_manager = manager
        print(f"[DEBUG] Active TabManager: {manager}, active path: {path}")
        self.update_address_bar(path)
    
    def update_address_bar(self, path):
        """Update address bar in parent MainWindow."""
        main_window = self.window()
        if hasattr(main_window, 'update_address_bar'):
            main_window.update_address_bar(path)

    def load_initial_directory(self):
        """Load the initial directory on startup."""
        import os

        # Skip if tabs already open
        if self.tab_manager.count() > 0:
            return

        # Get path from settings
        raw_path = self.settings_manager.get_setting(
            "last_opened_directory",
            "C:/Users/Burness/OneDrive - Fendler Patterson Construction, Inc/"
        )
        default_directory = os.path.normpath(raw_path)

        print(f"[DEBUG] Startup path: '{raw_path}' => normalized: '{default_directory}'")

        # Warn if path seems invalid
        if not os.path.isdir(default_directory):
            print(f"[WARNING] Python can't confirm '{default_directory}'. Opening anyway.")

        # Open directory
        self.open_directory_in_tab(default_directory)

        # Update address bar
        active_tab = self.tab_manager.currentWidget()
        if active_tab:
            file_tree = active_tab.findChild(FileTree)
            if file_tree:
                self.update_address_bar(file_tree.file_model.rootPath())

    def open_directory_in_tab(self, path: str):
        """
        Open a directory in a new tab if not already open.
        
        Args:
            path: Path to open
        """
        import os

        if not path:
            print("[ERROR] No path provided to open_directory_in_tab.")
            return

        normalized_path = os.path.normpath(path)
        if not os.path.isdir(normalized_path):
            print(f"[WARNING] Python can't confirm '{normalized_path}' as a real directory, but we'll open it anyway.")

        print(f"[DEBUG] Opening directory in tab: {normalized_path}")

        try:
            # Check if directory already open
            for i in range(self.tab_manager.count()):
                tab_widget = self.tab_manager.widget(i)
                file_tree = tab_widget.findChild(FileTree)
                if file_tree and file_tree.file_model.rootPath() == normalized_path:
                    print(f"[DEBUG] Directory already open in tab {i}, switching to it.")
                    self.tab_manager.setCurrentIndex(i)
                    self.update_address_bar(normalized_path)
                    return

            # Open new tab
            print(f"[DEBUG] Opening new tab for directory: {normalized_path}")
            self.tab_manager.add_new_file_tree_tab(
                title=os.path.basename(normalized_path) or normalized_path,
                root_path=normalized_path
            )

            # Update address bar
            self.update_address_bar(normalized_path)

        except Exception as e:
            print(f"[ERROR] Failed to open directory in tab: {str(e)}")

    def update_file_tree_connections(self, index: int):
        """
        Update signal connections when switching tabs.
        
        Args:
            index: Index of the new active tab
        """
        def connect_file_tree(tab_manager, idx):
            """Connect signals for a specific tab."""
            current_widget = tab_manager.widget(idx)
            if not current_widget:
                return

            file_tree = current_widget.findChild(FileTree)
            if not file_tree:
                return

            # Disconnect existing connections
            try:
                file_tree.location_changed.disconnect(self.update_address_bar)
            except TypeError:
                pass  # No existing connection

            # Connect location change signal
            file_tree.location_changed.connect(self.update_address_bar)

            # Update address bar immediately
            selected_path = file_tree.file_model.rootPath()
            if selected_path and os.path.exists(selected_path):
                self.update_address_bar(selected_path)

        # Connect left (main) side
        connect_file_tree(self.tab_manager, index)

        # Connect right side if in split view
        splitter = getattr(self, "splitter", None)
        if splitter and splitter.count() > 1:
            right_pane = splitter.widget(1)
            if right_pane:
                connect_file_tree(right_pane, index)

    def get_active_file_tree(self):
        """
        Get the FileTree from the active tab.
        
        Returns:
            FileTree: The active file tree, or None
        """
        current_tab = self.tab_manager.currentWidget()
        if current_tab:
            file_tree = current_tab.findChild(FileTree)
            if file_tree:
                return file_tree
        return None

    def create_dockable_panels(self):
        """Create all dockable panels in three columns."""
        # Import panels
        from ui.panels.pinned_panel import PinnedPanel
        from ui.panels.recent_items_panel import RecentItemsPanel
        from ui.panels.preview_panel import PreviewPanel
        from ui.panels.bookmarks_panel import BookmarksPanel
        from ui.panels.to_do_panel import ToDoPanel
        from ui.panels.one_note_panel import OneNotePanel
        from ui.panels.procore_links_panel import ProcoreQuickLinksPanel
        from PyQt6.QtWidgets import QSizePolicy, QDockWidget
        from PyQt6.QtCore import Qt

        # Get panel settings
        panel_settings = self.settings_manager.get_setting("dockable_panels", {})

        # Create panel instances
        self.pinned_panel = PinnedPanel(self)
        self.recent_items_panel = RecentItemsPanel(self)
        self.preview_panel = PreviewPanel()
        self.bookmarks_panel = BookmarksPanel(self)
        self.to_do_panel = ToDoPanel(self)
        self.one_note_panel = OneNotePanel(self)
        self.procore_panel = ProcoreQuickLinksPanel(self)
        self.procore_panel.setVisible(False)

        # Wrap in dock widgets
        self.pinned_dock = AutoResizeDock("Pinned Items", self.dock_area)
        self.recent_dock = AutoResizeDock("Recent Items", self.dock_area)
        self.preview_dock = AutoResizeDock("Preview", self.dock_area)
        self.bookmarks_dock = AutoResizeDock("Bookmarks", self.dock_area)
        self.to_do_dock = AutoResizeDock("To-Do", self.dock_area)
        self.one_note_dock = AutoResizeDock("OneNote", self.dock_area)
        self.procore_dock = AutoResizeDock("Procore Links", self.dock_area)

        # Set dock widgets
        self.pinned_dock.setWidget(self.pinned_panel)
        self.recent_dock.setWidget(self.recent_items_panel)
        self.preview_dock.setWidget(self.preview_panel)
        self.bookmarks_dock.setWidget(self.bookmarks_panel)
        self.to_do_dock.setWidget(self.to_do_panel)
        self.one_note_dock.setWidget(self.one_note_panel)
        self.procore_dock.setWidget(self.procore_panel)

        # Configure size policies
        for w in [
            self.pinned_panel, self.recent_items_panel, self.preview_panel,
            self.bookmarks_panel, self.to_do_panel, self.one_note_panel, self.procore_panel
        ]:
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Configure dock widgets
        for dock in [
            self.pinned_dock, self.recent_dock, self.preview_dock,
            self.bookmarks_dock, self.to_do_dock, self.one_note_dock, self.procore_dock
        ]:
            dock.setMinimumWidth(DEFAULT_DOCK_WIDTH)
            dock._original_width = DEFAULT_DOCK_WIDTH
            
            # Enable movable
            dock.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetMovable |
                QDockWidget.DockWidgetFeature.DockWidgetClosable |
                QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )

        # LEFT COLUMN: pinned + recent stacked vertically
        self.dock_area.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.pinned_dock)
        self.dock_area.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.recent_dock)
        self.dock_area.splitDockWidget(self.pinned_dock, self.recent_dock, Qt.Orientation.Vertical)

        # MIDDLE COLUMN: center_dock
        self.dock_area.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.center_dock)
        self.dock_area.splitDockWidget(
            self.pinned_dock,   # Left column anchor
            self.center_dock,   # Middle column
            Qt.Orientation.Horizontal
        )

        # RIGHT COLUMN: to_do on top, then procore, preview, bookmarks, one_note
        self.dock_area.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.to_do_dock)
        self.dock_area.splitDockWidget(
            self.center_dock,
            self.to_do_dock,
            Qt.Orientation.Horizontal
        )

        self.dock_area.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.procore_dock)
        self.dock_area.splitDockWidget(self.to_do_dock, self.procore_dock, Qt.Orientation.Vertical)

        self.dock_area.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.preview_dock)
        self.dock_area.splitDockWidget(self.procore_dock, self.preview_dock, Qt.Orientation.Vertical)

        self.dock_area.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.bookmarks_dock)
        self.dock_area.splitDockWidget(self.preview_dock, self.bookmarks_dock, Qt.Orientation.Vertical)

        self.dock_area.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.one_note_dock)
        self.dock_area.splitDockWidget(self.bookmarks_dock, self.one_note_dock, Qt.Orientation.Vertical)

        # Store dock panels for reference
        self.dock_panels = {
            "pinned_panel": self.pinned_dock,
            "recent_items_panel": self.recent_dock,
            "preview_panel": self.preview_dock,
            "bookmarks_panel": self.bookmarks_dock,
            "to_do_panel": self.to_do_dock,
            "one_note_panel": self.one_note_dock,
            "procore_panel": self.procore_dock,
        }

        # Apply saved visibility
        for panel_name, dock_widget in self.dock_panels.items():
            is_visible = panel_settings.get(panel_name, True)
            dock_widget.setVisible(is_visible)

        # Install event handlers
        # Separator click handlers disabled - removed edge click to collapse functionality
        # self.install_separator_click_handlers()

    def connect_pinned_panel_signals(self):
        """Connect pinned panel signals for syncing across windows."""
        if hasattr(self, 'pinned_panel'):
            main_window = self.window()
            if hasattr(main_window, "refresh_all_pinned_panels"):
                self.pinned_panel.pinned_item_added_global.connect(
                    lambda path: main_window.refresh_all_pinned_panels(path)
                )
                self.pinned_panel.pinned_item_modified.connect(
                    lambda old, new: main_window.refresh_all_pinned_panels(old, new)
                )
                self.pinned_panel.pinned_item_removed.connect(
                    lambda path: main_window.refresh_all_pinned_panels(path)
                )

    def handle_context_menu_action(self, action: str, file_path: str):
        """
        Handle context menu actions triggered from FileTree.
        
        Args:
            action: The action to perform
            file_path: The file path to act on
        """
        if action == "pin":
            if hasattr(self, 'pinned_panel') and hasattr(self.pinned_panel, 'pin_item'):
                if os.path.exists(file_path):
                    # Get the correct container
                    main_window = self.window()
                    if hasattr(main_window, 'main_tabs'):
                        container = main_window.main_tabs.currentWidget()
                    else:
                        print("Error: Current window is not a MainWindow")
                        return
                    
                    if container and isinstance(container, MainWindowContainer):
                        if hasattr(container, 'pinned_panel'):
                            container.pinned_panel.pin_item(file_path)
                            print(f"File pinned: {file_path}")

                            # Refresh pinned panel
                            container.pinned_panel.refresh_pinned_items()
                        else:
                            print("Error: No pinned panel found in current container")
                    else:
                        print("Error: Active tab is not a MainWindowContainer")
                else:
                    print(f"Error: File path does not exist: {file_path}")
            else:
                print("Error: PinnedPanel or pin_item method not found.")

    def delete_file(self, file_path: str):
        """
        Delete a file or directory.
        
        Args:
            file_path: Path to delete
        """
        try:
            if delete_item(file_path):
                print(f"Deleted {file_path}")
            else:
                print(f"Failed to delete {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")

    def rename_file(self, file_path: str):
        """
        Rename a file or directory.
        
        Args:
            file_path: Path to rename
        """
        try:
            from PyQt6.QtWidgets import QInputDialog
            new_name, ok = QInputDialog.getText(self, "Rename File", "Enter new name:")
            if ok and new_name:
                new_path = rename_item(file_path, new_name)
                if new_path:
                    print(f"Renamed {file_path} to {new_path}")
                else:
                    print(f"Failed to rename {file_path}")
        except Exception as e:
            print(f"Error renaming {file_path}: {e}")

    def apply_saved_panel_visibility(self, panel_settings: Dict[str, bool]):
        """
        Apply saved visibility settings to panels.
        
        Args:
            panel_settings: Dictionary of panel name to visibility
        """
        # Apply to all panels
        for panel_name, visible in panel_settings.items():
            if panel_name in self.dock_panels:
                self.dock_panels[panel_name].setVisible(visible)

    def apply_saved_settings(self):
        """Apply all saved settings."""
        # Apply theme
        theme = self.settings_manager.get_setting("theme", "light")
        self.apply_theme(theme)

        # Apply panel visibility
        panels = self.settings_manager.get_setting("dockable_panels", {})
        for panel_name, visible in panels.items():
            if panel_name in self.dock_panels:
                self.dock_panels[panel_name].setVisible(visible)

    def apply_theme(self, theme: str):
        """
        Apply theme to the UI.
        
        Args:
            theme: Theme name (light or dark)
        """
        if theme == "light":
            self.setStyleSheet("")
        elif theme == "dark":
            dark_stylesheet = """
                QMainWindow { background-color: #2B2B2B; color: #FFFFFF; }
                QToolBar { background-color: #3C3F41; border: none; }
                QLabel, QMenuBar, QMenu, QAction { color: #FFFFFF; }
                QListWidget, QTableWidget { background-color: #3C3F41; color: #FFFFFF; }
            """
            self.setStyleSheet(dark_stylesheet)


class MainWindowTabs(QTabWidget):
    """
    Tab widget that contains MainWindowContainer instances.
    Handles tab management, detachment, and panel toggling.
    """
    new_tab_added = pyqtSignal(object)  # Signal emitted when a new tab is added

    def __init__(self, parent=None):
        super().__init__(parent)

        # Replace tab bar with draggable version
        self.setTabBar(DraggableTabBar(self))

        # Configure tab widget
        self.setAcceptDrops(True)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)

        # Create top-right button container
        self.create_top_right_buttons()

        # Set up context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_tab_context_menu)
        self.tabCloseRequested.connect(self.close_tab)

        # Initial state
        self.detached_windows = []

        # Open initial tab
        self.add_new_main_window_tab()

    def create_top_right_buttons(self):
        """Create and configure buttons in the top-right corner."""
        self.top_right_widget = QWidget(self)
        self.top_right_layout = QHBoxLayout(self.top_right_widget)
        self.top_right_layout.setContentsMargins(0, 0, 0, 0)
        self.top_right_layout.setSpacing(5)

        # New Tab button
        self.add_tab_button = QToolButton(self)
        self.add_tab_button.setText("+")
        self.add_tab_button.setToolTip("Open a new tab")
        self.add_tab_button.clicked.connect(self.add_new_main_window_tab)
        self.top_right_layout.addWidget(self.add_tab_button)

        # Toggle Pinned Panel button
        self.toggle_pinned_button = QToolButton(self)
        self.toggle_pinned_button.setIcon(QIcon("assets/icons/pin.svg"))
        self.toggle_pinned_button.setToolTip("Toggle Pinned Panel")
        self.toggle_pinned_button.clicked.connect(self.toggle_pinned_panel)
        self.top_right_layout.addWidget(self.toggle_pinned_button)

        # Toggle Bookmarks button
        self.toggle_bookmarks_button = QToolButton(self)
        self.toggle_bookmarks_button.setIcon(QIcon("assets/icons/star.svg"))
        self.toggle_bookmarks_button.setToolTip("Toggle Bookmarks Panel")
        self.toggle_bookmarks_button.clicked.connect(self.toggle_bookmarks_panel)
        self.top_right_layout.addWidget(self.toggle_bookmarks_button)

        # Toggle Procore Links button
        self.toggle_procore_button = QToolButton(self)
        self.toggle_procore_button.setIcon(QIcon("assets/icons/link.svg"))
        self.toggle_procore_button.setToolTip("Toggle Procore Links Panel")
        self.toggle_procore_button.clicked.connect(self.toggle_procore_panel)
        self.top_right_layout.addWidget(self.toggle_procore_button)

        # Toggle To-Do Panel button
        self.toggle_todo_button = QToolButton(self)
        self.toggle_todo_button.setIcon(QIcon("assets/icons/list-todo.svg"))
        self.toggle_todo_button.setToolTip("Toggle To-Do Panel")
        self.toggle_todo_button.clicked.connect(self.toggle_todo_panel)
        self.top_right_layout.addWidget(self.toggle_todo_button)

        # Toggle OneNote button
        self.toggle_one_note_button = QToolButton(self)
        self.toggle_one_note_button.setIcon(QIcon("assets/icons/notebook.svg"))
        self.toggle_one_note_button.setToolTip("Toggle OneNote Panel")
        self.toggle_one_note_button.clicked.connect(self.toggle_one_note_panel)
        self.top_right_layout.addWidget(self.toggle_one_note_button)

        # Add stretch for right alignment
        self.top_right_layout.addStretch(1)

        # Place in corner
        self.setCornerWidget(self.top_right_widget, Qt.Corner.TopRightCorner)

    def toggle_panel_in_current_container(self, method_name: str):
        """
        Toggle a panel in the current container using the specified method.
        
        Args:
            method_name: Name of the toggle method to call
        """
        main_window = self.window()
        if not hasattr(main_window, 'main_tabs'):
            print(f"[ERROR] Main window does not have 'main_tabs'.")
            return

        current_container = main_window.main_tabs.currentWidget()
        if hasattr(current_container, method_name):
            getattr(current_container, method_name)()
        else:
            print(f"[ERROR] No {method_name} method found in the active MainWindowContainer.")

    # Panel toggle methods using the common implementation
    def toggle_one_note_panel(self):
        self.toggle_panel_in_current_container("toggle_one_note_panel")

    def toggle_pinned_panel(self):
        self.toggle_panel_in_current_container("toggle_pinned_panel")

    def toggle_bookmarks_panel(self):
        self.toggle_panel_in_current_container("toggle_bookmarks_panel")

    def toggle_procore_panel(self):
        self.toggle_panel_in_current_container("toggle_procore_panel")

    def toggle_todo_panel(self):
        self.toggle_panel_in_current_container("toggle_todo_panel")

    def toggle_split_view(self, index: int):
        """
        Toggle split view for a specific tab.
        
        Args:
            index: Index of the tab to toggle
        """
        container = self.widget(index)
        if isinstance(container, MainWindowContainer):
            container.toggle_split_view()
    
    def add_new_main_window_tab(self, root_path=None):
        """
        Create a new main window container as a tab.
        
        Args:
            root_path: Optional root path for the new tab
        
        Returns:
            MainWindowContainer: The created container
        """
        new_container = MainWindowContainer(self)

        # Ensure valid root path
        if not isinstance(root_path, str) or not os.path.exists(root_path):
            onedrive_path = r"C:/Users/Burness/OneDrive - Fendler Patterson Construction, Inc"
            root_path = onedrive_path if os.path.isdir(onedrive_path) else "C:/"

        # Add file explorer tab
        new_container.tab_manager.add_new_file_tree_tab(title="File Explorer", root_path=root_path)

        # Add to tabs
        index = self.addTab(new_container, f"Window {self.count() + 1}")
        self.setCurrentIndex(index)

        # Connect pinned panel
        self.connect_pinned_panel(new_container)

        # Emit signal
        self.new_tab_added.emit(new_container)

        print(f"Added new main window tab with root path: {root_path}")

        return new_container

    def connect_pinned_panel(self, container: MainWindowContainer):
        """
        Connect pinned panel signals.
        
        Args:
            container: Container with pinned panel to connect
        """
        if hasattr(container, 'pinned_panel'):
            main_window = self.window()
            if isinstance(main_window, MainWindow):
                try:
                    # Disconnect existing connections
                    container.pinned_panel.pinned_item_added_global.disconnect(main_window.refresh_all_pinned_panels)
                    container.pinned_panel.pinned_item_removed.disconnect(main_window.refresh_all_pinned_panels)
                except TypeError:
                    pass  # No existing connections

                # Reconnect signals
                container.pinned_panel.pinned_item_added_global.connect(main_window.refresh_all_pinned_panels)
                container.pinned_panel.pinned_item_removed.connect(main_window.refresh_all_pinned_panels)

    def detach_main_tab(self, index: int):
        """
        Detach a tab into a new window.
        
        Args:
            index: Index of the tab to detach
        """
        if index < 0 or index >= self.count():
            return

        detached_widget = self.widget(index)
        tab_title = self.tabText(index)

        if not detached_widget:
            print("Error: No widget found for the tab.")
            return

        # Create new window
        new_window = MainWindow()

        if not hasattr(self, "detached_windows"):
            self.detached_windows = []

        # Remove tab from current window
        self.removeTab(index)

        # Clear tabs in new window
        while new_window.main_tabs.count() > 0:
            new_window.main_tabs.removeTab(0)

        # Track window
        self.detached_windows.append(new_window)

        # Add detached tab to new window
        new_window.main_tabs.addTab(detached_widget, tab_title)

        # Configure new window
        new_window.setWindowTitle(f"Detached - {tab_title}")
        new_window.resize(1000, 700)

        parent_pos = self.window().pos()
        new_window.move(parent_pos.x() + 50, parent_pos.y() + 50)

        # Show new window
        new_window.activateWindow()
        new_window.raise_()
        new_window.show()

        # Connect pinned panel
        if hasattr(detached_widget, 'pinned_panel'):
            new_window.connect_pinned_panel_signals(detached_widget.pinned_panel)

        # Add to global tracking
        MainWindow.all_main_windows.append(new_window)

    def close_tab(self, index: int):
        """
        Close a tab.
        
        Args:
            index: Index of the tab to close
        """
        if self.count() > 1:
            self.removeTab(index)

    def show_tab_context_menu(self, position):
        """
        Show context menu for tabs.
        
        Args:
            position: Position where to show the menu
        """
        menu = QMenu(self)

        # New tab action
        new_tab = menu.addAction("New Tab")
        new_tab.triggered.connect(self.add_new_main_window_tab)

        # Get selected tab
        selected_tab_index = self.tabBar().tabAt(position)

        # Only show certain actions if multiple tabs exist
        if self.count() > 1:
            detach_tab = menu.addAction("Detach Tab")
            detach_tab.triggered.connect(lambda: self.detach_main_tab(selected_tab_index))

            close_tab = menu.addAction("Close Tab")
            close_tab.triggered.connect(lambda: self.close_tab(selected_tab_index))

        # Common actions
        split_view_action = menu.addAction("Toggle Split View")
        split_view_action.triggered.connect(lambda: self.toggle_split_view(selected_tab_index))

        duplicate_tab = menu.addAction("Duplicate Tab")
        duplicate_tab.triggered.connect(lambda: self.duplicate_current_tab())

        move_to_new_window = menu.addAction("Move to New Window")
        move_to_new_window.triggered.connect(lambda: self.move_tab_to_new_window(selected_tab_index))

        # Show menu
        menu.exec(self.mapToGlobal(position))

    def duplicate_current_tab(self):
        """Duplicate the current tab."""
        current = self.currentWidget()
        if current:
            new_container = MainWindowContainer(self)
            self.addTab(new_container, f"Window {self.count() + 1}")
            
            # Connect pinned panel
            self.connect_pinned_panel(new_container)

    def move_tab_to_new_window(self, index=None):
        """
        Move a tab to a new window.
        
        Args:
            index: Optional index of tab to move, uses current if None
        """
        if index is None:
            index = self.currentIndex()
            
        current_tab = self.widget(index)
        if current_tab and self.count() > 1:
            self.detach_main_tab(index)


class MainWindow(QMainWindow):
    """
    Main application window that contains the toolbar and tab widget.
    """
    # Class-level tracking of all main windows
    all_main_windows = []

    def __init__(self, settings_file="data/settings.json"):
        super().__init__()
        
        # Initialize managers
        self.settings_manager = SettingsManager(settings_file, parent_window=self)
        self.metadata_manager = MetadataManager("data/metadata.json")

        # Register in global tracking
        MainWindow.all_main_windows.append(self)

        # Create main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Initialize toolbar
        self.toolbar = Toolbar(self)

        # Initialize tab widget
        self.main_tabs = MainWindowTabs(self)

        # Add to layout
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.main_tabs)

        # Connect signals
        self.main_tabs.currentChanged.connect(self.update_address_bar_on_tab_change)
        self.main_tabs.new_tab_added.connect(self.on_new_tab_added)

        # Initialize history
        self.history = []
        self.current_history_index = -1

        # Configure window
        self.setWindowTitle("Enhanced File Explorer")
        self.resize(1200, 800)
        
        # Apply separator styling
        self.setStyleSheet("""
            QMainWindow::separator {
                background-color: #CCC;
                margin: 0px;
                padding: 0px;
                width: 3px; /* thickness of the separators */
            }
            QMainWindow::separator:hover {
                background-color: #0083DB;
            }
        """)

        # Restore window layout
        self.restore_window_layout()
        
        # Connect all pinned panels
        self.connect_all_pinned_panels()
        
        # Refresh pinned panels
        self.refresh_all_pinned_panels()

    def restore_window_layout(self):
        """Restore window geometry and state from settings."""
        geom_bytes, state_bytes = self.settings_manager.retrieve_main_window_layout()
        if geom_bytes:
            self.restoreGeometry(geom_bytes)
        if state_bytes:
            self.restoreState(state_bytes)

    def update_address_bar_on_tab_change(self, index: int):
        """
        Update address bar when tab changes.
        
        Args:
            index: Index of the new tab
        """
        current_container = self.main_tabs.widget(index)
        if not current_container:
            return

        file_tree = current_container.findChild(FileTree)
        if file_tree:
            path = file_tree.file_model.rootPath()
            self.update_address_bar(path)

    def update_address_bar(self, path: str):
        """
        Update address bar with path as placeholder text.
        
        Args:
            path: Path to display
        """
        if not path:
            print("[WARNING] No path provided to update address bar.")
            return

        if not os.path.exists(path):
            print(f"[ERROR] Invalid path provided: {path}")
            return

        # Check if already showing this path
        if hasattr(self.toolbar, '_current_path') and self.toolbar._current_path == path:
            print(f"[DEBUG] Address bar already showing ghost text for: {path}")
            return

        print(f"[DEBUG] Updating address bar to ghost text: {path}")
        
        # Update placeholder text
        self.toolbar.update_search_bar(path)

    def toggle_split_view(self):
        """Toggle split view in the current container."""
        current_container = self.main_tabs.currentWidget()
        if isinstance(current_container, MainWindowContainer):
            current_container.toggle_split_view()

    def get_active_file_tree(self):
        """
        Get the active file tree.
        
        Returns:
            FileTree: The active file tree or None
        """
        current_container = self.main_tabs.currentWidget()
        if current_container and isinstance(current_container, MainWindowContainer):
            return current_container.get_active_file_tree()
        return None

    def connect_pinned_panel_signals(self, pinned_panel):
        """
        Connect signals for a pinned panel.
        
        Args:
            pinned_panel: The pinned panel to connect
        """
        if not hasattr(pinned_panel, "_signals_connected"):
            pinned_panel.pinned_item_added_global.connect(
                lambda path: self.refresh_all_pinned_panels(path))
            pinned_panel.pinned_item_modified.connect(
                lambda old, new: self.refresh_all_pinned_panels(old, new))
            pinned_panel.pinned_item_removed.connect(
                lambda path: self.refresh_all_pinned_panels(path))
            pinned_panel._signals_connected = True
            
    def connect_all_pinned_panels(self):
        """Connect all pinned panels across all windows."""
        for window in MainWindow.all_main_windows:
            for i in range(window.main_tabs.count()):
                container = window.main_tabs.widget(i)
                if hasattr(container, 'pinned_panel'):
                    pinned_panel = container.pinned_panel

                    # Prevent redundant connections
                    if not hasattr(pinned_panel, "_signals_connected"):
                        pinned_panel.pinned_item_added_global.connect(
                            lambda path: self.refresh_all_pinned_panels(path))
                        pinned_panel.pinned_item_modified.connect(
                            lambda old, new: self.refresh_all_pinned_panels(old, new))
                        pinned_panel.pinned_item_removed.connect(
                            lambda path: self.refresh_all_pinned_panels(path))
                        pinned_panel._signals_connected = True

    def on_new_tab_added(self, container):
        """
        Handle new tab added event.
        
        Args:
            container: The new container that was added
        """
        if hasattr(container, 'pinned_panel'):
            self.connect_pinned_panel_signals(container.pinned_panel)
            
            # Connect instance signals
            container.pinned_panel.pinned_item_added_global.connect(self.refresh_all_pinned_panels)
            container.pinned_panel.pinned_item_modified.connect(self.refresh_all_pinned_panels) 
            container.pinned_panel.pinned_item_removed.connect(self.refresh_all_pinned_panels)
            
            # Refresh to sync with existing items
            self.refresh_all_pinned_panels()

    def get_current_container(self):
        """
        Get the current container.
        
        Returns:
            MainWindowContainer: The current container
        """
        return self.main_tabs.currentWidget()

    def open_settings_dialog(self):
        """Open the settings dialog."""
        dialog = SettingsDialog(self.settings_manager, self)
        if dialog.exec():
            # Apply settings after dialog closes
            self.apply_saved_settings()

    def apply_saved_settings(self):
        """Apply all saved settings."""
        # Apply theme
        theme = self.settings_manager.get_setting("theme", "light")
        self.apply_theme(theme)

        # Apply panel visibility
        panels = self.settings_manager.get_setting("dockable_panels", {})
        for panel_name, visible in panels.items():
            panel = getattr(self, f"{panel_name}", None)
            if panel:
                panel.setVisible(visible)

    def apply_theme(self, theme: str):
        """
        Apply theme to the UI.
        
        Args:
            theme: Theme name ('light' or 'dark')
        """
        if theme == "light":
            self.setStyleSheet("")  # Default Qt theme
        elif theme == "dark":
            dark_stylesheet = """
                QMainWindow { background-color: #2B2B2B; color: #FFFFFF; }
                QToolBar { background-color: #3C3F41; border: none; }
                QLabel, QMenuBar, QMenu, QAction { color: #FFFFFF; }
                QListWidget, QTableWidget { background-color: #3C3F41; color: #FFFFFF; }
            """
            self.setStyleSheet(dark_stylesheet)
            
        # Save theme setting
        self.settings_manager.update_setting("theme", theme)

    def toggle_panel(self, panel):
        """
        Toggle panel visibility.
        
        Args:
            panel: The panel to toggle
        """
        is_visible = not panel.isVisible()
        panel.setVisible(is_visible)
        
        # Save visibility to settings
        panel_name = [k for k, v in vars(self).items() if v == panel][0]
        self.settings_manager.set_panel_visibility(panel_name, is_visible)

    def closeEvent(self, event):
        """Save state and remove from tracking on close."""
        try:
            # Save layout
            geometry_bytes = self.saveGeometry()
            state_bytes = self.saveState()
            self.settings_manager.store_main_window_layout(geometry_bytes, state_bytes)

            # Remove from global tracking
            if self in MainWindow.all_main_windows:
                MainWindow.all_main_windows.remove(self)
        except Exception as e:
            print(f"Error in closeEvent: {e}")
            
        # Continue normal close
        super().closeEvent(event)

    def refresh_all_pinned_panels(self, item_path=None, new_path=None):
        """
        Refresh all pinned panels across all windows.
        
        Args:
            item_path: Optional path of modified item
            new_path: Optional new path if item was renamed/moved
        """
        if not MainWindow.all_main_windows:
            print("[DEBUG] No active MainWindow instances found. Skipping refresh.")
            return

        print(f"[DEBUG] Refreshing all pinned panels for item: {item_path}")
        print(f"[DEBUG] New path (if rename/move): {new_path}")

        try:
            # Refresh pinned panels in all windows
            for window in MainWindow.all_main_windows:
                if not isinstance(window, MainWindow):
                    continue

                for i in range(window.main_tabs.count()):
                    container = window.main_tabs.widget(i)
                    if hasattr(container, "pinned_panel"):
                        pinned_panel = container.pinned_panel

                        # Handle rename/move
                        if new_path:
                            pinned_panel.handle_pinned_item_rename(item_path, new_path)

                        # Refresh panel
                        pinned_panel.refresh_pinned_items()

            # Force update current tab immediately
            current_container = self.get_current_container()
            if current_container and hasattr(current_container, "pinned_panel"):
                print("[DEBUG] Refreshing pinned panel in active tab.")
                current_container.pinned_panel.refresh_pinned_items()

            # Ensure all panels stay connected
            self.connect_all_pinned_panels()
        except Exception as e:
            print(f"[ERROR] Failed to refresh pinned panels: {str(e)}")

    def handle_context_menu_action(self, action: str, file_path: str):
        """
        Handle context menu actions.
        
        Args:
            action: The action to perform
            file_path: The file path to act on
        """
        if action == "show_metadata":
            self.show_metadata(file_path)
        elif action == "delete":
            self.delete_file(file_path)
        elif action == "rename":
            self.rename_file(file_path)
        elif action == "pin":
            if hasattr(self, 'pinned_panel') and hasattr(self.pinned_panel, 'pin_item'):
                if os.path.exists(file_path):
                    self.pinned_panel.pin_item(file_path)
                    print(f"File pinned: {file_path}")
                else:
                    print(f"Error: File path does not exist: {file_path}")
            else:
                print("Error: PinnedPanel or pin_item method not found.")
        elif action == "tag":
            if file_path and os.path.exists(file_path):
                self.tag_item(file_path)
            else:
                print(f"Invalid or non-existent path for tagging: {file_path}")
        else:
            print(f"[WARNING] No handler for action: {action}")

    def tag_item(self, file_path: str):
        """
        Add a tag to a file.
        
        Args:
            file_path: Path to tag
        """
        if not hasattr(self, 'metadata_manager'):
            print("[ERROR] metadata_manager is not defined. Cannot tag item.")
            return

        if not file_path:
            print("[ERROR] No file_path provided to tag_item.")
            return

        from PyQt6.QtWidgets import QInputDialog
        tag, ok = QInputDialog.getText(self, "Tag Item", f"Enter a tag for:\n{file_path}")
        if ok and tag:
            self.metadata_manager.add_tag(file_path, tag)
            print(f"Tag '{tag}' added to '{file_path}'.")

            # Show all tags for this file
            all_tags = self.metadata_manager.get_tags(file_path)
            print(f"Now '{file_path}' has tags: {all_tags}")
        else:
            print("[INFO] Tagging operation canceled or empty tag provided.")

    def delete_file(self, file_path: str):
        """
        Delete a file or directory.
        
        Args:
            file_path: Path to delete
        """
        try:
            if delete_item(file_path):
                print(f"Deleted {file_path}")
                # Refresh UI if needed
            else:
                print(f"Failed to delete {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")

    def rename_file(self, file_path: str):
        """
        Rename a file or directory.
        
        Args:
            file_path: Path to rename
        """
        try:
            from PyQt6.QtWidgets import QInputDialog
            new_name, ok = QInputDialog.getText(self, "Rename File", "Enter new name:")
            if ok and new_name:
                new_path = rename_item(file_path, new_name)
                if new_path:
                    print(f"Renamed {file_path} to {new_path}")
                    # Refresh UI if needed
                else:
                    print(f"Failed to rename {file_path}")
        except Exception as e:
            print(f"Error renaming {file_path}: {e}")

    def open_directory_in_tab(self, path: str):
        """
        Open a directory in a tab.
        
        Args:
            path: Path to open
        """
        import os

        normalized_path = os.path.normpath(path)
        if not os.path.isdir(normalized_path):
            print(f"[WARNING] Python cannot confirm '{normalized_path}' as valid, but we'll open it anyway.")

        # Get active container
        current_container = self.main_tabs.currentWidget()
        if not current_container:
            print("[ERROR] No active MainWindowContainer found.")
            return

        # Check if already open
        for i in range(current_container.tab_manager.count()):
            tab_widget = current_container.tab_manager.widget(i)
            file_tree = tab_widget.findChild(FileTree)
            if file_tree and file_tree.file_model.rootPath() == normalized_path:
                current_container.tab_manager.setCurrentIndex(i)
                self.update_address_bar(normalized_path)
                return

        # Open new tab
        current_container.tab_manager.add_new_file_tree_tab(
            title=os.path.basename(normalized_path) or normalized_path,
            root_path=normalized_path
        )

        # Update address bar
        self.update_address_bar(normalized_path)

    def navigate_to_address_bar_path(self):
        """Open the path currently entered in the address bar."""
        import os
        path = self.toolbar.address_bar.text().strip()

        # Check if path seems valid
        normalized_path = os.path.normpath(path)
        if not os.path.isdir(normalized_path):
            from PyQt6.QtWidgets import QMessageBox
            # Warn but allow opening
            reply = QMessageBox.question(
                self, "Path Not Verified",
                f"Python cannot confirm '{normalized_path}' as a valid folder. Open anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Open directory
        self.open_directory_in_tab(normalized_path)

    def go_up(self):
        """Go up one directory level in the active tab."""
        current_container = self.main_tabs.currentWidget()
        if not current_container:
            print("No current container to go up from.")
            return
            
        if hasattr(current_container, 'tab_manager'):
            current_container.tab_manager.go_up()
        else:
            print("No tab_manager in the current container.")
                    
    def refresh_file_tree(self):
        """Refresh the active file tree."""
        current_container = self.main_tabs.currentWidget()
        if not current_container:
            print("No current container to refresh.")
            return

        if hasattr(current_container, "tab_manager"):
            current_container.tab_manager.refresh_current_tab()
        else:
            print("No tab_manager in the current container.")

    def dropEvent(self, event):
        """Handle file/folder drops."""
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        current_tab = self.main_tabs.currentWidget()
        if current_tab:
            file_tree = current_tab.findChild(FileTree)
            if file_tree:
                file_tree.dropEvent(event)
                file_tree.clearSelection()
            else:
                print("No FileTree in the current tab to handle the drop.")
        else:
            print("No active tab to handle the drop event.")

        event.acceptProposedAction()

    def restore_containers_dock_layouts(self):
        """Restore dock layouts for all containers."""
        for i in range(self.main_tabs.count()):
            container = self.main_tabs.widget(i)
            if hasattr(container, 'restore_container_docks'):
                container.restore_container_docks()

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())