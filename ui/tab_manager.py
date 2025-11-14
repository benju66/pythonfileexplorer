import os
from PyQt6.QtWidgets import (
    QTabWidget, QTreeView, QVBoxLayout, QWidget, QSplitter, QMenu, QInputDialog,
    QHBoxLayout, QToolButton, QMainWindow
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from ui.file_tree import FileTree
from ui.draggable_tab_bar import DraggableTabBar, TAB_WIDGET_MIME_TYPE
from modules.tab_history_manager import TabHistoryManager
from modules.widget_registry import get_widget_registry
from modules.signal_connection_manager import get_signal_connection_manager


class TabManager(QTabWidget):
    active_manager_changed = pyqtSignal(object, str)
    pin_item_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # ----------------- DraggableTabBar for tab dragging ----------------
        self.setTabBar(DraggableTabBar(self))
        # --------------------------------------------------------------------

        # Enable drag-and-drop for accepting drops
        self.setAcceptDrops(True)
        
        # Note: setMovable(True) is NOT enabled here to avoid conflicts
        # with our custom drag-and-drop. Reordering within same widget will
        # be handled by our drop handler in Phase 3/4.
        
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)

        # Double-click on the tab bar: we'll handle whether it's a tab or empty space
        self.tabBarDoubleClicked.connect(self.handle_tab_bar_double_click)

        # Context menu setup
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_tab_context_menu)

        # Split view-related
        self.splitter = None
        self._split_view_active = False

        # Update address bar (or other UI) when active tab changes
        self.currentChanged.connect(self.on_tab_changed)

        # If this was detached from a TabManager, store a reference
        self.original_tab_manager = None

        # ─────────────────────────────────────────────────────────────────────
        # Top-right "+" button for new nested tabs
        top_right_widget = QWidget(self)
        top_right_layout = QHBoxLayout(top_right_widget)
        top_right_layout.setContentsMargins(0, 0, 0, 0)
        top_right_layout.setSpacing(5)

        self.plus_button = QToolButton(self)
        self.plus_button.setText("+")
        self.plus_button.setToolTip("Open a new nested tab")
        self.plus_button.clicked.connect(self.add_new_nested_tab)
        top_right_layout.addWidget(self.plus_button)

        top_right_layout.addStretch(1)
        self.setCornerWidget(top_right_widget, Qt.Corner.TopRightCorner)
        # ─────────────────────────────────────────────────────────────────────

        # Per-tab history manager
        self.history_manager = TabHistoryManager()
        
        # Infrastructure for drag-and-drop
        self.widget_registry = get_widget_registry()
        self.signal_manager = get_signal_connection_manager()
        
        # Store parent container reference for reliable lookup
        self._store_parent_container_reference()

    def add_new_tab(self, title="New Tab", root_path=None):
        """
        Creates a new tab with a FileTree if `root_path` is valid.
        Call this method when you want to programmatically create a
        tab with a custom title and path.
        """
        if root_path is None or not os.path.exists(root_path):
            print(f"Error: Cannot access directory '{root_path}'. Tab not created.")
            return None

        try:
            tab_content = QWidget()
            layout = QVBoxLayout(tab_content)

            file_tree = FileTree()
            file_tree.set_root_directory(root_path)

            file_tree.file_tree_clicked.connect(self.handle_file_tree_clicked)
            file_tree.context_menu_action_triggered.connect(self.handle_context_menu_action)

            layout.addWidget(file_tree)
            index = self.addTab(tab_content, title)
            self.setCurrentIndex(index)

            # Initialize per-tab history
            self.history_manager.init_tab_history(tab_content, root_path)
            
            # Register widget for drag-and-drop infrastructure
            self._register_tab_widget(tab_content, file_tree)
            
            return tab_content
        except Exception as e:
            print(f"Error creating new tab: {e}")
            return None

    def add_new_nested_tab(self):
        """Called when the user clicks the "+" button in the corner."""
        default_path = "C:/Users/Burness/OneDrive - Fendler Patterson Construction, Inc"
        folder_label = os.path.basename(default_path) or default_path
        self.add_new_file_tree_tab(title=folder_label, root_path=default_path)

    def add_new_file_tree_tab(self, title="New Tab", root_path="/"):
        """
        Create a new tab with a FileTree and initialize its history.
        """
        try:
            file_tree = FileTree()
            file_tree.set_root_directory(root_path)
            file_tree.file_tree_clicked.connect(self.handle_file_tree_clicked)
            file_tree.context_menu_action_triggered.connect(self.handle_context_menu_action)

            tab_content = QWidget()
            layout = QVBoxLayout(tab_content)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(file_tree)
            tab_content.setLayout(layout)

            index = self.addTab(tab_content, title)
            self.setCurrentIndex(index)
            self.setCurrentWidget(tab_content)

            if hasattr(self, 'active_manager_changed'):
                self.active_manager_changed.emit(self, root_path)

            # Initialize the history for this new tab
            self.history_manager.init_tab_history(tab_content, root_path)
            
            # Register widget for drag-and-drop infrastructure
            self._register_tab_widget(tab_content, file_tree)

            return tab_content
        except Exception as e:
            print(f"[ERROR] Failed to create new file tree tab: {str(e)}")
            return None
        
    def handle_tab_bar_double_click(self, index):
        """
        Called whenever the user double-clicks the QTabBar area.
        If index == -1, the double-click happened on empty space
        (not on an existing tab), so we add a new nested tab.
        """
        if index == -1:
            self.add_new_nested_tab()
        else:
            # Double-clicked on an existing tab; do nothing,
            # or keep old logic if you prefer.
            pass


    # ------------------------------------------------------------------------
    # Split view logic (unchanged; can remain as is)
    # ------------------------------------------------------------------------
    def toggle_split_view(self, index):
        main_window = self.window()
        if hasattr(main_window, "toggle_split_view"):
            main_window.toggle_split_view()
        else:
            print("Error: Could not find a valid parent with toggle_split_view method.")

    def reset_split_view(self):
        if self.splitter:
            print("✅ Resetting split view...")

            right_tab_manager = self.splitter.widget(1)
            if right_tab_manager:
                self.splitter.removeWidget(right_tab_manager)
                right_tab_manager.deleteLater()

            main_layout = self.parentWidget().layout()
            if self.splitter in main_layout.children():
                main_layout.removeWidget(self.splitter)

            main_layout.addWidget(self)
            self.splitter.deleteLater()
            self.splitter = None
            self._split_view_active = False
            print("✅ Split view reset successfully.")

    # ------------------------------------------------------------------------
    # Right-click context menu for the tab
    # ------------------------------------------------------------------------
    def show_tab_context_menu(self, position):
        menu = QMenu(self)
        selected_tab_index = self.tabBar().tabAt(position)
        if selected_tab_index < 0:
            return

        detach_action = menu.addAction("Detach Nested Tab")
        detach_action.triggered.connect(lambda: self.detach_nested_tab(selected_tab_index))

        if self.original_tab_manager:
            reattach_action = menu.addAction("Reattach to Original")
            reattach_action.triggered.connect(
                lambda: self.reattach_tab(selected_tab_index, self.original_tab_manager)
            )

        split_view_action = menu.addAction("Split View")
        parent_container = self.get_main_window_container()
        if parent_container and hasattr(parent_container, "toggle_split_view"):
            split_view_action.triggered.connect(parent_container.toggle_split_view)
        else:
            split_view_action.setEnabled(False)

        menu.exec(self.mapToGlobal(position))

    def detach_nested_tab(self, index):
        if index < 0 or index >= self.count():
            print("Error: Invalid tab index for detach.")
            return

        detached_widget = self.widget(index)
        tab_title = self.tabText(index)
        if not detached_widget:
            print("Error: No widget found for the tab to detach.")
            return

        self.removeTab(index)

        new_window = QMainWindow()
        new_window.setWindowTitle(f"Detached - {tab_title}")

        detached_tab_manager = TabManager()
        detached_tab_manager.original_tab_manager = self
        new_window.setCentralWidget(detached_tab_manager)

        new_tab_index = detached_tab_manager.addTab(detached_widget, tab_title)
        detached_tab_manager.setCurrentIndex(new_tab_index)
        new_window.resize(800, 600)
        new_window.show()

        if not hasattr(self, "detached_windows"):
            self.detached_windows = []
        self.detached_windows.append(new_window)

    def reattach_tab(self, index, original_tab_manager):
        if index < 0 or index >= self.count():
            print("Error: Invalid tab index for reattach.")
            return

        tab_widget = self.widget(index)
        tab_title = self.tabText(index)
        if not tab_widget:
            print("Error: No widget found for the tab to reattach.")
            return

        self.removeTab(index)
        new_index = original_tab_manager.addTab(tab_widget, tab_title)
        original_tab_manager.setCurrentIndex(new_index)
        original_tab_manager.setCurrentWidget(tab_widget)
        print(f"Tab '{tab_title}' reattached to the original TabManager.")

    # ------------------------------------------------------------------------
    # Handling user clicks in the FileTree
    # ------------------------------------------------------------------------
    def handle_file_tree_clicked(self):
        """
        1) Find which tab’s FileTree was clicked, make that tab active.
        2) Get a path for the address bar (either selection or root).
        3) Emit active_manager_changed(self, active_path).
        """
        clicked_tree = self.sender()
        if not clicked_tree:
            return

        for i in range(self.count()):
            tab_widget = self.widget(i)
            tree_in_tab = tab_widget.findChild(FileTree)
            if tree_in_tab == clicked_tree:
                self.setCurrentIndex(i)
                active_path = self._determine_path_for_address_bar(tree_in_tab)
                self.active_manager_changed.emit(self, active_path)
                break

    def on_tab_changed(self, index: int):
        """
        Called automatically when user switches to a different tab.
        Tells parent container or main window to update address bar, etc.
        """
        print(f"[DEBUG] User switched to tab index {index}")
        tab_widget = self.widget(index)
        if not tab_widget:
            return

        file_tree = tab_widget.findChild(FileTree)
        if not file_tree:
            print("[WARNING] No FileTree found in the newly selected tab.")
            return

        active_path = self._determine_path_for_address_bar(file_tree)
        print(f"[DEBUG] Active path in the new tab: {active_path}")
        self.active_manager_changed.emit(self, active_path)

    def _determine_path_for_address_bar(self, file_tree):
        """
        Return the path to show in the address bar:
         - If user has an item selected, use that.
         - Otherwise, use the FileTree’s root directory.
        """
        if not file_tree:
            return ""

        selection_model = file_tree.selectionModel()
        selected_indexes = selection_model.selectedIndexes() if selection_model else []
        if selected_indexes:
            first_index = selected_indexes[0]
            return file_tree.file_model.filePath(first_index)
        else:
            return file_tree.file_model.rootPath()

    # ------------------------------------------------------------------------
    # Directory navigation (incl. Up)
    # ------------------------------------------------------------------------
    def open_directory_in_current_tab(self, path):
        """
        Open 'path' in the active nested tab, add to that tab's history.
        """
        if not os.path.isdir(path):
            print(f"Error: {path} is not a valid directory.")
            return

        tab_index = self.currentIndex()
        if tab_index < 0:
            print("No active tab to navigate.")
            return

        tab_widget = self.widget(tab_index)
        if not tab_widget:
            print("No QWidget in the current tab.")
            return

        file_tree = tab_widget.findChild(FileTree)
        if file_tree:
            file_tree.set_root_directory(path)
            self.history_manager.push_path(tab_widget, path)
            print(f"Opened directory: {path} in tab {tab_index}")
        else:
            print("No FileTree found in the current tab.")

    # ------------------------------------------------------------------------
    # If you decide you never want to use Back/Forward, you can comment them
    # out or remove them entirely. Here we comment them in case you need them
    # in the future. They won't do anything if the toolbar doesn't call them.
    # ------------------------------------------------------------------------
    """
    def go_back(self):
        current_widget = self.currentWidget()
        if not current_widget:
            return
        new_path = self.history_manager.go_back(current_widget)
        if new_path:
            self._set_tab_path(current_widget, new_path)

    def go_forward(self):
        current_widget = self.currentWidget()
        if not current_widget:
            return
        new_path = self.history_manager.go_forward(current_widget)
        if new_path:
            self._set_tab_path(current_widget, new_path)
    """

    def go_up(self):
        """
        Go to the parent directory of the current path, push it onto this tab's history.
        """
        current_widget = self.currentWidget()
        if not current_widget:
            return
        new_path = self.history_manager.go_up(current_widget)
        if new_path:
            self._set_tab_path(current_widget, new_path)

    def _set_tab_path(self, widget, path):
        """
        Update the FileTree in the widget to show 'path' WITHOUT adding a new
        history entry (so we don't loop).
        
        Args:
            widget: The tab widget containing the FileTree
            path: The path to set
        """
        if widget is None:
            return
        file_tree = widget.findChild(FileTree)
        if file_tree:
            file_tree.set_root_directory(path)

    # ------------------------------------------------------------------------
    # Context Menu actions from FileTree
    # ------------------------------------------------------------------------
    def handle_context_menu_action(self, action, file_path):
        if action == "pin":
            print(f"[DEBUG] Emitting pin request for: {file_path}")
            self.pin_item_requested.emit(file_path)
        elif action == "show_metadata":
            print(f"Show metadata for: {file_path}")
        elif action == "rename":
            current_tab = self.currentWidget()
            if current_tab:
                file_tree = current_tab.findChild(FileTree)
                if file_tree:
                    index = file_tree.file_model.index(file_path)
                    if index.isValid():
                        file_tree.edit(index)
                    else:
                        print(f"[ERROR] Invalid index for: {file_path}")
                else:
                    print("[ERROR] No FileTree found in the current tab.")

    # ------------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------------
    def refresh_current_tab(self):
        """Refresh the FileTree in the current tab only."""
        current_tab = self.currentWidget()
        if not current_tab:
            print("No active tab to refresh.")
            return

        file_tree = current_tab.findChild(FileTree)
        if not file_tree:
            print("No FileTree found in the current tab.")
            return

        current_directory = file_tree.file_model.rootPath()
        file_tree.set_root_directory(current_directory)
        print(f"Refreshed tab with directory: {current_directory}")

    def refresh_all_tabs(self):
        """Refresh every open tab (if you ever need that)."""
        for index in range(self.count()):
            tab_content = self.widget(index)
            if tab_content:
                file_tree = tab_content.findChild(FileTree)
                if file_tree:
                    current_directory = file_tree.file_model.rootPath()
                    file_tree.set_root_directory(current_directory)
                    print(f"Refreshed tab at index {index} with directory: {current_directory}")

    # ------------------------------------------------------------------------
    # Drag-and-Drop Infrastructure
    # ------------------------------------------------------------------------
    def _register_tab_widget(self, tab_widget: QWidget, file_tree: FileTree):
        """
        Register a tab widget and its FileTree for drag-and-drop infrastructure.
        
        This method:
        1. Registers the widget in the widget registry
        2. Registers signal connections in the signal manager
        3. Stores parent container reference in the widget
        
        Args:
            tab_widget: The tab widget (container for FileTree)
            file_tree: The FileTree widget within the tab
        """
        if tab_widget is None or file_tree is None:
            return
        
        # Get parent container
        container = self.get_main_window_container()
        if container is None:
            print("[WARNING] Could not find parent container for widget registration")
            return
        
        # Register widget in widget registry
        self.widget_registry.register_widget(tab_widget, self)
        
        # Store parent container reference in widget property
        tab_widget.setProperty("main_window_container", container)
        
        # Register signal connections
        # FileTree -> TabManager signals
        self.signal_manager.register_connection(
            widget=tab_widget,
            source=file_tree,
            signal_name="file_tree_clicked",
            target=self,
            slot=self.handle_file_tree_clicked
        )
        
        self.signal_manager.register_connection(
            widget=tab_widget,
            source=file_tree,
            signal_name="context_menu_action_triggered",
            target=self,
            slot=self.handle_context_menu_action
        )
        
        # FileTree -> MainWindowContainer signals
        self.signal_manager.register_connection(
            widget=tab_widget,
            source=file_tree,
            signal_name="location_changed",
            target=container,
            slot=container.update_address_bar
        )
        
        # TabManager -> MainWindowContainer signals (registered once per TabManager)
        # These are already connected in MainWindowContainer.__init__, but we track them
        # for potential reconnection if TabManager moves
        
    # ------------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------------
    def _store_parent_container_reference(self):
        """
        Store a reference to the parent MainWindowContainer in a widget property.
        This allows reliable lookup even after widget moves during drag-and-drop.
        """
        parent = self.parentWidget()
        while parent:
            if hasattr(parent, "dock_area") or hasattr(parent, "toggle_split_view"):
                # Found MainWindowContainer - store reference
                self.setProperty("main_window_container", parent)
                return
            parent = parent.parentWidget()
    
    def get_main_window_container(self):
        """
        Find the MainWindowContainer by checking stored property first,
        then falling back to walking up parent widgets.
        
        This method is robust to widget moves during drag-and-drop operations.
        """
        # First, check if we have a stored reference
        stored_container = self.property("main_window_container")
        if stored_container and hasattr(stored_container, "dock_area"):
            return stored_container
        
        # Fall back to parent traversal
        parent = self.parentWidget()
        while parent:
            if hasattr(parent, "dock_area") or hasattr(parent, "toggle_split_view"):
                # Store reference for future use
                self.setProperty("main_window_container", parent)
                return parent
            parent = parent.parentWidget()

        print("[ERROR] Could not find a valid MainWindowContainer.")
        return None

    def navigate_to_directory(self, path):
        current_tab = self.currentWidget()
        if current_tab:
            file_tree = current_tab.findChild(FileTree)
            if file_tree:
                file_tree.set_root_directory(path)

    def get_active_file_tree(self):
        """Return the FileTree in the current tab."""
        current_tab = self.currentWidget()
        if current_tab:
            file_tree = current_tab.findChild(FileTree)
            if not file_tree:
                print("Error: No FileTree found in the current active tab.")
            return file_tree
        print("Error: No active tab found in TabManager.")
        return None

    def update_active_tab_path(self, file_tree=None):
        """
        If you need to force an address bar update from code. Reuses
        _determine_path_for_address_bar.
        """
        if not file_tree:
            current_tab = self.currentWidget()
            if not current_tab:
                return
            file_tree = current_tab.findChild(FileTree)

        if not file_tree:
            print("[WARNING] No FileTree found to update path.")
            return

        active_path = self._determine_path_for_address_bar(file_tree)
        parent_container = self.parentWidget()
        if parent_container and hasattr(parent_container, "update_address_bar"):
            parent_container.update_address_bar(active_path)

    def debug_current_tab_history(self):
        """
        Print debug information about the current tab's history.
        Useful for testing and verification.
        """
        current_widget = self.currentWidget()
        if not current_widget:
            print("[DEBUG] No current tab widget found.")
            return
        
        debug_info = self.history_manager.get_history_debug_info(current_widget)
        print("\n" + "="*60)
        print("CURRENT TAB HISTORY DEBUG")
        print("="*60)
        for key, value in debug_info.items():
            print(f"  {key}: {value}")
        print("="*60 + "\n")
    
    def debug_all_tabs_history(self):
        """
        Print debug information for all tabs' histories.
        Useful for testing and verification.
        """
        print("\n" + "="*60)
        print("ALL TABS HISTORY DEBUG")
        print("="*60)
        print(f"Total tabs: {self.count()}")
        
        for i in range(self.count()):
            widget = self.widget(i)
            tab_title = self.tabText(i)
            print(f"\nTab {i}: '{tab_title}'")
            if widget:
                debug_info = self.history_manager.get_history_debug_info(widget)
                print(f"  Widget ID: {debug_info.get('widget_id', 'N/A')}")
                print(f"  Has History: {debug_info.get('has_history', False)}")
                print(f"  Current Path: {debug_info.get('current_path', 'N/A')}")
                print(f"  History: {debug_info.get('history', [])}")
                print(f"  Current Index: {debug_info.get('current_index', -1)}")
            else:
                print("  [ERROR] Widget is None")
        
        print("\n" + "="*60)

    def close_tab(self, index):
        """
        Close the tab at the specified index, handle split view if needed,
        and remove the tab's history from the manager.
        """
        tab_widget = self.widget(index)
        if tab_widget:
            # Unregister widget from drag-and-drop infrastructure
            self.widget_registry.unregister_widget(tab_widget)
            self.signal_manager.unregister_widget(tab_widget)
            
            # Remove history
            self.history_manager.remove_tab_history(tab_widget)

        container = self.get_main_window_container()
        if not container or not hasattr(container, "dock_area"):
            print("[ERROR] Could not find a valid MainWindowContainer.")
            return

        splitter = getattr(container, "splitter", None)
        if splitter and splitter.count() > 1:
            # Split view
            tab_to_close = self.widget(index)
            if tab_to_close:
                tab_to_close.deleteLater()
            self.removeTab(index)

            if self.count() == 0:
                other_tab_manager = None
                for i in range(splitter.count()):
                    widget = splitter.widget(i)
                    if isinstance(widget, TabManager) and widget != self:
                        other_tab_manager = widget
                        break

                if other_tab_manager:
                    container.dock_area.setCentralWidget(other_tab_manager)
                    splitter.deleteLater()
                    container.splitter = None
                    print("✅ Splitter removed, restored single-pane mode.")
        else:
            # Normal tab closing
            if self.count() > 1:
                tab_to_close = self.widget(index)
                if tab_to_close:
                    tab_to_close.deleteLater()
                self.removeTab(index)
            elif hasattr(self, "reset_split_view"):
                self.reset_split_view()

        print(f"✅ Closed tab at index {index}")
    
    # ------------------------------------------------------------------------
    # Drag-and-Drop Event Handlers (Phase 3: Same Widget Drops)
    # ------------------------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent):
        """
        Handle drag enter event to accept tab widget drags.
        
        Args:
            event: QDragEnterEvent
        """
        if event.mimeData().hasFormat(TAB_WIDGET_MIME_TYPE):
            # Check if this is a tab widget drag
            widget_id_str = event.mimeData().data(TAB_WIDGET_MIME_TYPE).data().decode('utf-8')
            try:
                widget_id = int(widget_id_str)
                widget = self.widget_registry.get_widget(widget_id)
                
                if widget:
                    # Accept the drag
                    event.acceptProposedAction()
                    return
            except (ValueError, TypeError):
                pass
        
        # Let parent handle other drag types (files, etc.)
        super().dragEnterEvent(event)
    
    def dragMoveEvent(self, event: QDragMoveEvent):
        """
        Handle drag move event to provide visual feedback.
        
        Args:
            event: QDragMoveEvent
        """
        if event.mimeData().hasFormat(TAB_WIDGET_MIME_TYPE):
            # Accept tab widget drags
            event.acceptProposedAction()
            return
        
        # Let parent handle other drag types
        super().dragMoveEvent(event)
    
    def dropEvent(self, event: QDropEvent):
        """
        Handle drop event for tab widgets.
        
        This handles drops within the same TabManager (reordering)
        and drops from other TabManagers (will be handled in Phase 4).
        
        Args:
            event: QDropEvent
        """
        if not event.mimeData().hasFormat(TAB_WIDGET_MIME_TYPE):
            # Not a tab widget drag - let parent handle it
            super().dropEvent(event)
            return
        
        try:
            # Reset tab bar indicator
            tab_bar = self.tabBar()
            if hasattr(tab_bar, 'drop_indicator_pos'):
                tab_bar.drop_indicator_pos = -1
                tab_bar.drop_indicator_index = -1
                tab_bar.update()
            
            # Get widget ID from MIME data
            widget_id_str = event.mimeData().data(TAB_WIDGET_MIME_TYPE).data().decode('utf-8')
            try:
                widget_id = int(widget_id_str)
            except (ValueError, TypeError):
                print("[ERROR] Invalid widget ID in MIME data")
                event.ignore()
                return
            
            # Look up widget in registry
            widget = self.widget_registry.get_widget(widget_id)
            if widget is None:
                print(f"[ERROR] Widget {widget_id} not found in registry")
                event.ignore()
                return
            
            # Get source tab widget
            source_tab_widget = self.widget_registry.get_parent_tab_widget(widget)
            if source_tab_widget is None:
                print(f"[ERROR] Source tab widget not found for widget {widget_id}")
                event.ignore()
                return
            
            # Check if drop is within same widget (Phase 3: Same Widget)
            if source_tab_widget == self:
                # Same widget - handle reordering
                self._handle_same_widget_drop(widget, event)
                event.acceptProposedAction()
            else:
                # Different widget - will be handled in Phase 4
                # For now, ignore it
                print(f"[DEBUG] Drop from different widget - will be handled in Phase 4")
                event.ignore()
                return
                
        except Exception as e:
            print(f"[ERROR] Error in dropEvent: {e}")
            import traceback
            traceback.print_exc()
            event.ignore()
    
    def _handle_same_widget_drop(self, widget: QWidget, event: QDropEvent):
        """
        Handle drop within the same TabManager (reordering).
        
        This method:
        1. Finds the current index of the widget
        2. Determines the target index based on drop position
        3. Moves the tab to the new position
        
        Args:
            widget: The widget being dropped
            event: QDropEvent
        """
        try:
            # Find current index of widget
            current_index = self.indexOf(widget)
            if current_index < 0:
                print(f"[ERROR] Widget not found in this TabManager")
                return
            
            # Get tab bar
            tab_bar = self.tabBar()
            
            # Get target index from tab bar's drop indicator
            # The tab bar calculates this in _update_drop_indicator during dragMoveEvent
            if hasattr(tab_bar, 'drop_indicator_index') and tab_bar.drop_indicator_index >= 0:
                target_index = tab_bar.drop_indicator_index
                print(f"[DEBUG] Using drop_indicator_index: {target_index}")
            else:
                # Fallback: calculate from event position
                # Event position is relative to this widget (TabManager)
                drop_pos = event.pos() if hasattr(event, 'pos') else event.position().toPoint()
                print(f"[DEBUG] Drop position (TabManager coords): {drop_pos}")
                
                # Map position to tab bar coordinates
                tab_bar_pos = self.mapTo(tab_bar, drop_pos)
                print(f"[DEBUG] Tab bar position: {tab_bar_pos}")
                target_index = tab_bar.tabAt(tab_bar_pos)
                print(f"[DEBUG] Tab at position: {target_index}")
                
                if target_index < 0:
                    # Determine position based on x coordinate
                    tab_bar_rect = tab_bar.rect()
                    if tab_bar_pos.x() < tab_bar_rect.width() / 2:
                        target_index = 0
                    else:
                        target_index = self.count()
                    print(f"[DEBUG] No tab at position, using: {target_index}")
                else:
                    # Determine if before or after tab
                    tab_rect = tab_bar.tabRect(target_index)
                    tab_center_x = tab_rect.center().x()
                    if tab_bar_pos.x() < tab_center_x:
                        # Before tab
                        target_index = target_index
                    else:
                        # After tab
                        target_index = target_index + 1
                    print(f"[DEBUG] Tab found, adjusted index: {target_index}")
            
            # Ensure target_index is valid
            if target_index < 0:
                target_index = 0
            if target_index > self.count():
                target_index = self.count()
            
            # If dropped on same position, do nothing
            if target_index == current_index:
                print(f"[DEBUG] Tab dropped on same position - no change needed")
                return
            
            # Get tab title and icon before moving
            tab_title = self.tabText(current_index)
            tab_icon = self.tabIcon(current_index)
            
            # Remove widget from current position
            self.removeTab(current_index)
            
            # Adjust target_index if we removed a tab before it
            if target_index > current_index:
                target_index -= 1
            
            # Ensure target_index is still valid after removal
            if target_index < 0:
                target_index = 0
            if target_index > self.count():
                target_index = self.count()
            
            # Insert widget at new position
            self.insertTab(target_index, widget, tab_title)
            if not tab_icon.isNull():
                self.setTabIcon(target_index, tab_icon)
            
            # Set as active tab
            self.setCurrentIndex(target_index)
            
            print(f"[DEBUG] Tab reordered from index {current_index} to {target_index}")
            
            # No signal reconnection needed (same parent)
            # No history migration needed (same widget)
            
        except Exception as e:
            print(f"[ERROR] Error in _handle_same_widget_drop: {e}")
            import traceback
            traceback.print_exc()
            raise
