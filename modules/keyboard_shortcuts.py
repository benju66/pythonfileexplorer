from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QObject, QDir
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

class KeyboardShortcuts:
    """
    Manages keyboard shortcuts for the Enhanced File Explorer.
    
    Integrates with MainWindow to provide keyboard shortcuts for common operations
    including navigation, file operations, panel toggling, and view options.
    """
    
    def __init__(self, main_window):
        """
        Initialize keyboard shortcuts for the provided MainWindow.
        
        Args:
            main_window: The main application window instance.
        """
        self.main_window = main_window
        self.shortcuts = []
        
        # Setup all shortcut categories
        self.setup_navigation_shortcuts()
        self.setup_file_operation_shortcuts()
        self.setup_panel_toggle_shortcuts()
        self.setup_tab_shortcuts()
        self.setup_view_shortcuts()
        self.setup_utility_shortcuts()
        
        print("✅ Keyboard shortcuts initialized")

    def setup_navigation_shortcuts(self):
        """Configure navigation shortcuts."""
        # Basic navigation
        self.add_shortcut(QKeySequence("Alt+Up"), self.go_up, "Go Up")
        self.add_shortcut(QKeySequence("F5"), self.refresh, "Refresh")
        
        # Address bar focus
        self.add_shortcut(QKeySequence("Alt+D"), self.focus_address_bar, "Focus Address Bar")
        self.add_shortcut(QKeySequence("Ctrl+L"), self.focus_address_bar, "Focus Address Bar (Alt)")
        
        # Search
        self.add_shortcut(QKeySequence("Ctrl+F"), self.focus_search, "Focus Search")
        self.add_shortcut(QKeySequence("F3"), self.focus_search, "Focus Search (Alt)")
        
        # Back/forward remain available but delegated to container
        self.add_shortcut(QKeySequence("Alt+Left"), self.go_back, "Go Back")
        self.add_shortcut(QKeySequence("Alt+Right"), self.go_forward, "Go Forward")

    def setup_file_operation_shortcuts(self):
        """Configure shortcuts for file operations."""
        # Create operations
        self.add_shortcut(QKeySequence("Ctrl+Shift+N"), self.new_folder, "New Folder")
        self.add_shortcut(QKeySequence("Ctrl+Alt+N"), self.new_file, "New File")
        
        # Clipboard operations
        self.add_shortcut(QKeySequence("Ctrl+C"), self.copy_selected, "Copy")
        self.add_shortcut(QKeySequence("Ctrl+X"), self.cut_selected, "Cut")
        self.add_shortcut(QKeySequence("Ctrl+V"), self.paste, "Paste")
        
        # File manipulation
        self.add_shortcut(QKeySequence("F2"), self.rename_selected, "Rename")
        self.add_shortcut(QKeySequence("Delete"), self.delete_selected, "Delete")
        self.add_shortcut(QKeySequence("Ctrl+Delete"), self.permanent_delete, "Permanent Delete")
        
        # Undo/Redo
        self.add_shortcut(QKeySequence("Ctrl+Z"), self.undo, "Undo")
        self.add_shortcut(QKeySequence("Ctrl+Y"), self.redo, "Redo")
        self.add_shortcut(QKeySequence("Ctrl+Shift+Z"), self.redo, "Redo (Alt)")

    def setup_panel_toggle_shortcuts(self):
        """Configure shortcuts for toggling panels."""
        # Left panels
        self.add_shortcut(QKeySequence("Ctrl+P"), self.toggle_pinned_panel, "Toggle Pinned Panel")
        self.add_shortcut(QKeySequence("Ctrl+R"), self.toggle_recent_panel, "Toggle Recent Panel")
        
        # Right panels
        self.add_shortcut(QKeySequence("Ctrl+B"), self.toggle_bookmarks_panel, "Toggle Bookmarks Panel")
        self.add_shortcut(QKeySequence("Ctrl+D"), self.toggle_todo_panel, "Toggle ToDo Panel")
        self.add_shortcut(QKeySequence("Ctrl+Shift+P"), self.toggle_preview_panel, "Toggle Preview Panel")
        self.add_shortcut(QKeySequence("Ctrl+K"), self.toggle_procore_panel, "Toggle Procore Panel")
        self.add_shortcut(QKeySequence("Ctrl+M"), self.toggle_onenote_panel, "Toggle OneNote Panel")

    def setup_tab_shortcuts(self):
        """Configure shortcuts for tab operations."""
        # Tab navigation
        self.add_shortcut(QKeySequence("Ctrl+Tab"), self.next_tab, "Next Tab")
        self.add_shortcut(QKeySequence("Ctrl+Shift+Tab"), self.prev_tab, "Previous Tab")
        
        # Tab management
        self.add_shortcut(QKeySequence("Ctrl+T"), self.new_tab, "New Tab")
        self.add_shortcut(QKeySequence("Ctrl+W"), self.close_tab, "Close Tab")
        
        # Split view
        self.add_shortcut(QKeySequence("Ctrl+\\"), self.toggle_split_view, "Toggle Split View")

    def setup_view_shortcuts(self):
        """Configure shortcuts for view operations."""
        # Refresh views
        self.add_shortcut(QKeySequence("F10"), self.toggle_fullscreen, "Toggle Fullscreen")
        
        # Zoom
        self.add_shortcut(QKeySequence("Ctrl++"), self.zoom_in, "Zoom In")
        self.add_shortcut(QKeySequence("Ctrl+-"), self.zoom_out, "Zoom Out")
        self.add_shortcut(QKeySequence("Ctrl+0"), self.zoom_reset, "Reset Zoom")

    def setup_utility_shortcuts(self):
        """Configure shortcuts for utility operations."""
        # Help
        self.add_shortcut(QKeySequence("F1"), self.show_help, "Help")
        
        # Settings
        self.add_shortcut(QKeySequence("Ctrl+,"), self.open_settings, "Settings")
        
        # Toggle hidden files
        self.add_shortcut(QKeySequence("Ctrl+H"), self.toggle_hidden_files, "Toggle Hidden Files")
        
        # Escape action (cancel operations)
        self.add_shortcut(QKeySequence("Esc"), self.escape_action, "Escape Current Operation")

    def add_shortcut(self, key_sequence, callback, description=None):
        """
        Register a keyboard shortcut.
        
        Args:
            key_sequence: QKeySequence for the shortcut
            callback: Function to call when shortcut is triggered
            description: Optional description for the shortcut
        """
        shortcut = QShortcut(key_sequence, self.main_window)
        shortcut.activated.connect(callback)
        
        # Store shortcut reference to prevent garbage collection
        shortcut.description = description
        self.shortcuts.append(shortcut)
        
        print(f"  Added shortcut: {key_sequence.toString()} - {description}")

    # === NAVIGATION CALLBACKS ===
    
    def go_back(self):
        """Navigate back in the current active container's tab."""
        current_container = self.get_current_container()
        
        if current_container and hasattr(current_container, "tab_manager"):
            tab_manager = current_container.tab_manager
            current_widget = tab_manager.currentWidget()
            if current_widget and hasattr(tab_manager.history_manager, "go_back"):
                new_path = tab_manager.history_manager.go_back(current_widget)
                if new_path:
                    tab_manager._set_tab_path(current_widget, new_path)
    
    def go_forward(self):
        """Navigate forward in the current active container's tab."""
        current_container = self.get_current_container()
        
        if current_container and hasattr(current_container, "tab_manager"):
            tab_manager = current_container.tab_manager
            current_widget = tab_manager.currentWidget()
            if current_widget and hasattr(tab_manager.history_manager, "go_forward"):
                new_path = tab_manager.history_manager.go_forward(current_widget)
                if new_path:
                    tab_manager._set_tab_path(current_widget, new_path)
    
    def go_up(self):
        """Navigate up to parent directory."""
        # Primary delegation to MainWindow's go_up method
        if hasattr(self.main_window, "go_up"):
            self.main_window.go_up()
        else:
            # Fallback to active container's tab_manager
            current_container = self.get_current_container()
            if current_container and hasattr(current_container, "tab_manager"):
                current_container.tab_manager.go_up()
    
    def refresh(self):
        """Refresh the current file tree view."""
        if hasattr(self.main_window, "refresh_file_tree"):
            self.main_window.refresh_file_tree()
        else:
            # Fallback to active tab's refresh method
            current_container = self.get_current_container()
            if current_container and hasattr(current_container, "tab_manager"):
                current_container.tab_manager.refresh_current_tab()
    
    def focus_address_bar(self):
        """Set focus to the address bar."""
        if hasattr(self.main_window, "toolbar") and hasattr(self.main_window.toolbar, "search_bar"):
            self.main_window.toolbar.edit_current_path()
            self.main_window.toolbar.search_bar.setFocus()

    def focus_search(self):
        """Set focus to the search bar (same as address bar in this app)."""
        if hasattr(self.main_window, "toolbar") and hasattr(self.main_window.toolbar, "search_bar"):
            # Clear the search bar to enable search mode
            self.main_window.toolbar.search_bar.clear()
            self.main_window.toolbar.search_bar.setFocus()

    # === FILE OPERATION CALLBACKS ===
    
    def new_folder(self):
        """Create a new folder in the current directory."""
        file_tree = self.get_active_file_tree()
        if file_tree:
            selected_indexes = file_tree.selectedIndexes()
            if selected_indexes and selected_indexes[0].column() == 0:  # Only use column 0
                selected_path = file_tree.file_model.filePath(selected_indexes[0])
                if selected_path:
                    if not file_tree.file_model.isDir(selected_indexes[0]):
                        # If file is selected, use its parent directory
                        selected_path = file_tree.file_model.filePath(selected_indexes[0].parent())
                    file_tree.create_new_folder(selected_path)
            else:
                # If no selection, use current root path
                root_path = file_tree.file_model.rootPath()
                file_tree.create_new_folder(root_path)
    
    def new_file(self):
        """Create a new file in the current directory."""
        file_tree = self.get_active_file_tree()
        if file_tree:
            selected_indexes = file_tree.selectedIndexes()
            if selected_indexes and selected_indexes[0].column() == 0:  # Only use column 0
                selected_path = file_tree.file_model.filePath(selected_indexes[0])
                if selected_path:
                    if not file_tree.file_model.isDir(selected_indexes[0]):
                        # If file is selected, use its parent directory
                        selected_path = file_tree.file_model.filePath(selected_indexes[0].parent())
                    file_tree.create_new_file(selected_path)
            else:
                # If no selection, use current root path
                root_path = file_tree.file_model.rootPath()
                file_tree.create_new_file(root_path)
    
    def copy_selected(self):
        """Copy selected items to clipboard."""
        file_tree = self.get_active_file_tree()
        if file_tree:
            selected_indexes = file_tree.selectedIndexes()
            if selected_indexes:
                # Filter to only column 0 indexes to avoid duplicates
                unique_indexes = [idx for idx in selected_indexes if idx.column() == 0]
                if unique_indexes:
                    # Get the first selected item
                    first_path = file_tree.file_model.filePath(unique_indexes[0])
                    file_tree.copy_item(first_path)
    
    def cut_selected(self):
        """Cut selected items to clipboard."""
        # Currently using copy mechanism; a proper cut would flag items as "to be moved"
        self.copy_selected()
        
        # Implement proper "cut" visual indication if needed
        file_tree = self.get_active_file_tree()
        if file_tree and hasattr(file_tree, "cut_selected_files"):
            file_tree.cut_selected_files()
    
    def paste(self):
        """Paste items from clipboard."""
        file_tree = self.get_active_file_tree()
        if file_tree:
            selected_indexes = file_tree.selectedIndexes()
            target_path = ""
            
            if selected_indexes and selected_indexes[0].column() == 0:
                selected_path = file_tree.file_model.filePath(selected_indexes[0])
                if file_tree.file_model.isDir(selected_indexes[0]):
                    target_path = selected_path
                else:
                    target_path = file_tree.file_model.filePath(selected_indexes[0].parent())
            else:
                target_path = file_tree.file_model.rootPath()
                
            if target_path:
                file_tree.paste_item(target_path)
    
    def rename_selected(self):
        """Rename the selected item."""
        file_tree = self.get_active_file_tree()
        if file_tree:
            selected_indexes = file_tree.selectedIndexes()
            if selected_indexes and selected_indexes[0].column() == 0:
                file_tree.edit(selected_indexes[0])
    
    def delete_selected(self):
        """Delete the selected item."""
        file_tree = self.get_active_file_tree()
        if file_tree:
            selected_indexes = file_tree.selectedIndexes()
            if selected_indexes and selected_indexes[0].column() == 0:
                selected_path = file_tree.file_model.filePath(selected_indexes[0])
                if selected_path:
                    file_tree.delete_item_with_undo(selected_path)
    
    def permanent_delete(self):
        """Permanently delete the selected item (with confirmation)."""
        file_tree = self.get_active_file_tree()
        if file_tree:
            selected_indexes = file_tree.selectedIndexes()
            if selected_indexes and selected_indexes[0].column() == 0:
                selected_path = file_tree.file_model.filePath(selected_indexes[0])
                if selected_path:
                    reply = QMessageBox.question(
                        self.main_window,
                        "Confirm Permanent Delete",
                        f"Permanently delete '{selected_path}'?\nThis action cannot be undone.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        from modules.file_operations import delete_item
                        delete_item(selected_path)
                        file_tree.refresh_active_tab()

    def undo(self):
        """Trigger undo operation."""
        from modules.undo_manager import undo_manager
        undo_manager.undo()
    
    def redo(self):
        """Trigger redo operation."""
        from modules.undo_manager import undo_manager
        undo_manager.redo()

    # === PANEL TOGGLE CALLBACKS ===
    
    def toggle_pinned_panel(self):
        """Toggle the pinned panel visibility."""
        current_container = self.get_current_container()
        if current_container and hasattr(current_container, "toggle_pinned_panel"):
            current_container.toggle_pinned_panel()
    
    def toggle_recent_panel(self):
        """Toggle the recent items panel visibility."""
        current_container = self.get_current_container()
        # Check for a generic toggle method with panels dictionary
        if current_container and hasattr(current_container, "dock_panels") and "recent_items_panel" in current_container.dock_panels:
            current_container.dock_panels["recent_items_panel"].setVisible(
                not current_container.dock_panels["recent_items_panel"].isVisible()
            )
    
    def toggle_bookmarks_panel(self):
        """Toggle the bookmarks panel visibility."""
        current_container = self.get_current_container()
        if current_container and hasattr(current_container, "toggle_bookmarks_panel"):
            current_container.toggle_bookmarks_panel()
    
    def toggle_todo_panel(self):
        """Toggle the to-do panel visibility."""
        current_container = self.get_current_container()
        if current_container and hasattr(current_container, "toggle_todo_panel"):
            current_container.toggle_todo_panel()
    
    def toggle_preview_panel(self):
        """Toggle the preview panel visibility."""
        current_container = self.get_current_container()
        if current_container and hasattr(current_container, "dock_panels") and "preview_panel" in current_container.dock_panels:
            current_container.dock_panels["preview_panel"].setVisible(
                not current_container.dock_panels["preview_panel"].isVisible()
            )
    
    def toggle_procore_panel(self):
        """Toggle the Procore links panel visibility."""
        current_container = self.get_current_container()
        if current_container and hasattr(current_container, "toggle_procore_panel"):
            current_container.toggle_procore_panel()
    
    def toggle_onenote_panel(self):
        """Toggle the OneNote panel visibility."""
        current_container = self.get_current_container()
        if current_container and hasattr(current_container, "toggle_one_note_panel"):
            current_container.toggle_one_note_panel()

    # === TAB MANAGEMENT CALLBACKS ===
    
    def next_tab(self):
        """Switch to the next main tab."""
        if hasattr(self.main_window, "main_tabs"):
            tabs = self.main_window.main_tabs
            current = tabs.currentIndex()
            if current < tabs.count() - 1:
                tabs.setCurrentIndex(current + 1)
            else:
                tabs.setCurrentIndex(0)  # Wrap around
    
    def prev_tab(self):
        """Switch to the previous main tab."""
        if hasattr(self.main_window, "main_tabs"):
            tabs = self.main_window.main_tabs
            current = tabs.currentIndex()
            if current > 0:
                tabs.setCurrentIndex(current - 1)
            else:
                tabs.setCurrentIndex(tabs.count() - 1)  # Wrap around
    
    def new_tab(self):
        """Open a new main tab."""
        if hasattr(self.main_window, "main_tabs") and hasattr(self.main_window.main_tabs, "add_new_main_window_tab"):
            self.main_window.main_tabs.add_new_main_window_tab()
    
    def close_tab(self):
        """Close the current tab if there's more than one."""
        if hasattr(self.main_window, "main_tabs") and self.main_window.main_tabs.count() > 1:
            self.main_window.main_tabs.close_tab(self.main_window.main_tabs.currentIndex())
    
    def toggle_split_view(self):
        """Toggle split view for the current main window container."""
        current_container = self.get_current_container()
        if current_container and hasattr(current_container, "toggle_split_view"):
            current_container.toggle_split_view()

    # === VIEW CALLBACKS ===
    
    def zoom_in(self):
        """Increase the font size or zoom level."""
        # Future implementation - currently a placeholder
        pass
    
    def zoom_out(self):
        """Decrease the font size or zoom level."""
        # Future implementation - currently a placeholder
        pass
    
    def zoom_reset(self):
        """Reset the zoom level to default."""
        # Future implementation - currently a placeholder
        pass
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.main_window.isFullScreen():
            self.main_window.showNormal()
        else:
            self.main_window.showFullScreen()

    # === UTILITY CALLBACKS ===
    
    def show_help(self):
        """Show the help documentation."""
        if hasattr(self.main_window, "show_documentation"):
            self.main_window.show_documentation()
    
    def open_settings(self):
        """Open the settings dialog."""
        if hasattr(self.main_window, "open_settings_dialog"):
            self.main_window.open_settings_dialog()
    
    def toggle_hidden_files(self):
        """Toggle display of hidden files."""
        file_tree = self.get_active_file_tree()
        if file_tree and hasattr(file_tree, "file_model"):
            current_filters = file_tree.file_model.filter()
            if current_filters & QDir.Filter.Hidden:
                # Hidden files are currently shown, hide them
                file_tree.file_model.setFilter(current_filters & ~QDir.Filter.Hidden)
            else:
                # Hidden files are currently hidden, show them
                file_tree.file_model.setFilter(current_filters | QDir.Filter.Hidden)
    
    def escape_action(self):
        """
        Handle Escape key press.
        - Clear selections
        - Cancel dialogs
        - Exit fullscreen mode
        """
        # If in fullscreen, exit
        if self.main_window.isFullScreen():
            self.main_window.showNormal()
            return
            
        # Clear current file tree selection
        file_tree = self.get_active_file_tree()
        if file_tree:
            file_tree.clearSelection()

    # === HELPER METHODS ===
    
    def get_current_container(self):
        """Get the current MainWindowContainer."""
        if hasattr(self.main_window, "main_tabs"):
            return self.main_window.main_tabs.currentWidget()
        return None
    
    def get_active_file_tree(self):
        """Get the active FileTree instance from the current tab."""
        if hasattr(self.main_window, "get_active_file_tree"):
            return self.main_window.get_active_file_tree()
        
        # Fallback implementation 
        current_container = self.get_current_container()
        if current_container and hasattr(current_container, "tab_manager"):
            tab_manager = current_container.tab_manager
            current_tab = tab_manager.currentWidget()
            if current_tab:
                from ui.file_tree import FileTree
                return current_tab.findChild(FileTree)
        
        return None