import json
import os
import logging
import platform
import subprocess
import struct

from ctypes import create_unicode_buffer
from PyQt6.QtCore import (
    Qt,
    QDir,
    QMimeData,
    pyqtSignal,
    QTimer,
    QUrl,
    QPoint
)
from PyQt6.QtGui import (
    QIcon,
    QAction,
    QFileSystemModel,
    QDrag,
    QMouseEvent
)
from PyQt6.QtWidgets import (
    QDockWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QMenu,
    QWidget,
    QTreeView,
    QApplication,
    QInputDialog,
    QMessageBox
)

from modules.metadata_manager import MetadataManager
from ui.file_tree import FileTree
from modules.pinned_manager import PinnedManager

logger = logging.getLogger(__name__)

file_system_model = QFileSystemModel()

def find_file_tree(widget):
    """Recursively search for a FileTree instance inside a QWidget."""
    if isinstance(widget, FileTree):
        return widget
    for child in widget.findChildren(QWidget):
        found = find_file_tree(child)
        if found:
            return found
    return None

class PinnedPanel(QDockWidget):
    pinned_item_added_global = pyqtSignal(str)
    pinned_item_modified = pyqtSignal(str, str)
    pinned_item_removed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Give it a window title (used when floating or in OS listings)
        self.setWindowTitle("Pinned Items")

        # Hide the default dock title bar, so only close/float icons are shown
        self.setTitleBarWidget(QWidget(self))

        # Limit to left dock area if desired
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)

        # Dock features: closable & movable
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )

        # Initialize the pinned manager & metadata manager
        self.pinned_manager = PinnedManager()
        self.metadata_manager = MetadataManager()

        # Connect pinned manager updates
        self.pinned_manager.pinned_items_updated.connect(self.refresh_pinned_items)

        # Track drag state
        self._drag_start_pos = None
        self._is_dragging = False
        self._dragged_item = None

        # Expanded states for tree items
        self.expanded_states = {}

        # Setup UI and refresh pinned items
        self._setup_ui()
        self.refresh_pinned_items()
        self.load_expanded_states_from_file()

    # ----------------------------------------------------------
    # UI Setup
    # ----------------------------------------------------------
    def _setup_ui(self):
        """Set up the UI elements for the pinned panel."""

        # This optional custom role is used to mark items as "heading" 
        # so handle_tree_click can ignore them.
        HEADING_ROLE = Qt.ItemDataRole.UserRole + 100

        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        self.main_widget = QWidget()
        self.setWidget(self.main_widget)
        layout = QVBoxLayout()
        self.main_widget.setLayout(layout)

        # Create the tree
        self.pinned_tree = QTreeWidget()
        self.pinned_tree.setHeaderHidden(False)
        self.pinned_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # Slightly revised header label
        self.pinned_tree.setHeaderLabels(["Favorites / Pinned Items"])
        self.pinned_tree.setColumnWidth(0, 250)

        # Drag settings
        self.pinned_tree.setDragEnabled(True)
        self.pinned_tree.setDragDropMode(QTreeWidget.DragDropMode.DragOnly)
        self.pinned_tree.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.pinned_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setAcceptDrops(False)  # The QTreeWidget handles its own drops

        # Connect signals
        self.pinned_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.pinned_tree.itemDoubleClicked.connect(self.handle_double_click)
        self.pinned_tree.itemClicked.connect(lambda item, column: self.handle_tree_click(item, column))

        layout.addWidget(self.pinned_tree)

        # -- Create two top-level nodes in your tree: Favorites & Pinned Items
        self.favorites_root = QTreeWidgetItem(self.pinned_tree)
        self.favorites_root.setText(0, "Favorites")
        self.favorites_root.setData(0, HEADING_ROLE, True)  # Mark this as a heading
        self.favorites_root.setExpanded(True)

        self.pinned_root = QTreeWidgetItem(self.pinned_tree)
        self.pinned_root.setText(0, "Pinned Items")
        self.pinned_root.setData(0, HEADING_ROLE, True)     # Mark this as a heading
        self.pinned_root.setExpanded(True)


    # ----------------------------------------------------------
    # Mouse / Drag Events
    # ----------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events to prepare for a possible drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.pinned_tree.itemAt(event.pos())
            if item:
                self._drag_start_pos = event.pos()
                self._dragged_item = item
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Reset drag state on release."""
        self._drag_start_pos = None
        self._is_dragging = False
        self._dragged_item = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Initiate a drag if the user moves enough with the left button held."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if not self._drag_start_pos:
            return

        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance >= QApplication.startDragDistance():
            self._start_drag()
        super().mouseMoveEvent(event)

    def _start_drag(self):
        """Set up and execute the drag from the pinned tree."""
        selected_items = self.pinned_tree.selectedItems()
        if not selected_items:
            return

        file_paths = []
        for item in selected_items:
            item_path = item.data(0, Qt.ItemDataRole.UserRole)
            if item_path and os.path.exists(item_path):
                file_paths.append(os.path.abspath(item_path))

        if not file_paths:
            logger.error("No valid file paths found for drag operation.")
            return

        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile(fp) for fp in file_paths]
        mime_data.setUrls(urls)
        mime_data.setText("\n".join(file_paths))

        # Windows-specific CF_HDROP:
        drop_data = "\0".join(file_paths) + "\0\0"
        mime_data.setData("application/x-qt-windows-mime;value=\"CF_HDROP\"", drop_data.encode("utf-16le"))

        # FileGroupDescriptorW
        file_descriptor = struct.pack("<I", len(file_paths))
        for fp in file_paths:
            filename_buffer = create_unicode_buffer(fp, 260)
            file_descriptor += filename_buffer.raw
        mime_data.setData("application/x-qt-windows-mime;value=\"FileGroupDescriptorW\"", file_descriptor)

        # FileContents
        mime_data.setData("application/x-qt-windows-mime;value=\"FileContents\"", b"")

        drag = QDrag(self.pinned_tree)
        drag.setMimeData(mime_data)

        # Set drag icon if available
        icon = selected_items[0].icon(0)
        if not icon.isNull():
            pixmap = icon.pixmap(32, 32)
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))

        drag.exec(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event):
        """Allow drag from external apps if it has urls or CF_HDROP."""
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("CF_HDROP"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Accept drag move if it has urls or CF_HDROP."""
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("CF_HDROP"):
            event.acceptProposedAction()
        else:
            event.ignore()

    # ----------------------------------------------------------
    # Pinned Items
    # ----------------------------------------------------------
    def refresh_pinned_items(self):
        # We'll define the same heading role here, so we can reassign it.
        HEADING_ROLE = Qt.ItemDataRole.UserRole + 100

        # 1) Store expanded states
        expanded_states = {}
        for i in range(self.pinned_tree.topLevelItemCount()):
            root_item = self.pinned_tree.topLevelItem(i)
            self._store_expanded_states(root_item, expanded_states)

        # 2) Clear the entire pinned_tree
        self.pinned_tree.clear()

        # 3) Recreate "Favorites" node
        self.favorites_root = QTreeWidgetItem(self.pinned_tree)
        self.favorites_root.setText(0, "Favorites")
        self.favorites_root.setExpanded(True)
        self.favorites_root.setData(0, HEADING_ROLE, True)  # Mark as heading

        # 4) Optionally recreate "Pinned Items" node (if you want a heading for pinned)
        self.pinned_root = QTreeWidgetItem(self.pinned_tree)
        self.pinned_root.setText(0, "Pinned Items")
        self.pinned_root.setExpanded(True)
        self.pinned_root.setData(0, HEADING_ROLE, True)

        # 5) Build your favorites and pinned items
        pinned_items = self.pinned_manager.get_pinned_items()
        favorite_items = self.pinned_manager.get_favorite_items()

        # Create favorites (flat)
        for fav_path in favorite_items:
            self._create_favorite_item(fav_path, self.favorites_root)

        # Create pinned items (nested)
        for pinned_path in pinned_items:
            self.add_pinned_item_to_tree(pinned_path)

        # 6) Restore expansions
        for i in range(self.pinned_tree.topLevelItemCount()):
            self._restore_expanded_states(self.pinned_tree.topLevelItem(i), expanded_states)

        # 7) Save states
        self.save_expanded_states_to_file()


    def save_expanded_states_to_file(self):
        """
        Save current expanded/collapsed states for all pinned items to a JSON file on disk.
        """
        # 1) Collect the states
        states = {}
        for i in range(self.pinned_tree.topLevelItemCount()):
            self._store_expanded_states(self.pinned_tree.topLevelItem(i), states)

        # 2) Make sure the directory exists
        os.makedirs("data", exist_ok=True)
        file_path = "data/pinned_panel_states.json"

        # 3) Write the dictionary to JSON
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(states, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error(f"Failed to save expanded states: {e}")

    def load_expanded_states_from_file(self):
        """
        Load expanded/collapsed states from JSON and apply them to the current tree items.
        Call this after the pinned tree is initially populated.
        """
        file_path = "data/pinned_panel_states.json"
        if not os.path.exists(file_path):
            return  # Nothing to load yet

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                saved_states = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load expanded states: {e}")
            return

        # Apply saved expanded states to each top-level item and its children
        for i in range(self.pinned_tree.topLevelItemCount()):
            self._restore_expanded_states(self.pinned_tree.topLevelItem(i), saved_states)

    def closeEvent(self, event):
        """
        Ensure expanded states are saved when the user closes the pinned panel.
        """
        self.save_expanded_states_to_file()
        super().closeEvent(event)

    def add_pinned_item_to_tree(self, item_path):
        if not os.path.exists(item_path):
            logger.error(f"Path '{item_path}' does not exist.")
            return

        pinned_items = self.pinned_manager.get_pinned_items()
        parent_path = os.path.dirname(item_path)

        # 1) Find the nearest pinned ancestor
        nearest_pinned_ancestor = None
        temp_path = parent_path
        while temp_path:
            if temp_path in pinned_items:
                nearest_pinned_ancestor = temp_path
                break
            new_temp = os.path.dirname(temp_path)
            if new_temp == temp_path:
                break
            temp_path = new_temp

        # 2) Ensure ancestor is in the pinned_tree
        if nearest_pinned_ancestor and not self.find_item_by_path(self.pinned_tree, nearest_pinned_ancestor):
            self.add_pinned_item_to_tree(nearest_pinned_ancestor)

        # 3) Determine the correct parent
        parent_item = (self.find_item_by_path(self.pinned_tree, nearest_pinned_ancestor)
                    if nearest_pinned_ancestor else None)

        # 4) Find or create the item under the correct parent
        existing_item = self.find_item_by_path(self.pinned_tree, item_path)
        if existing_item:
            existing_parent = existing_item.parent()

            # Detect if the existing parent is the "Favorites" heading
            is_favorites = False
            if existing_parent:
                HEADING_ROLE = Qt.ItemDataRole.UserRole + 100
                is_heading = existing_parent.data(0, HEADING_ROLE)
                if is_heading and existing_parent.text(0) == "Favorites":
                    is_favorites = True

            # If the existing item is under some other parent (like Favorites),
            # we create a new item in Pinned to prevent it from disappearing from Favorites
            if existing_parent and existing_parent != parent_item:
                if is_favorites:
                    self._create_tree_item(item_path, parent_item or self.pinned_tree)
                else:
                    # If it's already pinned under a different pinned parent, move it
                    if parent_item and existing_item.parent() != parent_item:
                        self._move_item_to_parent(existing_item, parent_item)
            else:
                # It's already in pinned under the correct parent — do nothing
                pass
        else:
            # No existing item => create it
            self._create_tree_item(item_path, parent_item or self.pinned_tree)

        # 5) Reorganize children if this is a newly pinned folder
        for child_path in pinned_items:
            if os.path.dirname(child_path) == item_path:
                existing_child = self.find_item_by_path(self.pinned_tree, child_path)
                if existing_child:
                    self._move_item_to_parent(
                        existing_child,
                        self.find_item_by_path(self.pinned_tree, item_path)
                    )

    def _move_item_to_parent(self, item, parent):
        """Detach and re-attach the item to the new parent."""
        if item.parent():
            item.parent().removeChild(item)
        else:
            index = self.pinned_tree.indexOfTopLevelItem(item)
            if index >= 0:
                self.pinned_tree.takeTopLevelItem(index)

        if parent:
            parent.addChild(item)
        else:
            self.pinned_tree.addTopLevelItem(item)

    def _create_tree_item(self, path, parent):
        """Create a new pinned tree item and set the tooltip to display any tags."""
        if not os.path.exists(path):
            logger.error(f"Cannot create tree item for non-existent path '{path}'.")
            return
        name = os.path.basename(path)
        new_item = QTreeWidgetItem(parent)
        new_item.setText(0, name)
        new_item.setData(0, Qt.ItemDataRole.UserRole, path)

        # Show an icon
        index = file_system_model.index(path)
        icon = file_system_model.fileIcon(index)
        new_item.setIcon(0, icon)

        # Retrieve tags from the metadata manager
        tags = self.metadata_manager.get_tags(path)  # e.g. ["25-105", "Important"]
        if tags:
            new_item.setToolTip(0, f"Tags: {', '.join(tags)}")
        else:
            new_item.setToolTip(0, "No tags")

        return new_item
    
    def _create_favorite_item(self, path, parent):
        """Create a single-level favorite item under the 'Favorites' node."""
        if not os.path.exists(path):
            logger.error(f"Favorite path does not exist: {path}")
            return
        name = os.path.basename(path)
        fav_item = QTreeWidgetItem(parent)
        fav_item.setText(0, name)
        fav_item.setData(0, Qt.ItemDataRole.UserRole, path)

        # Icon
        index = file_system_model.index(path)
        icon = file_system_model.fileIcon(index)
        fav_item.setIcon(0, icon)

        # Optional: tags, tooltip
        tags = self.metadata_manager.get_tags(path)
        if tags:
            fav_item.setToolTip(0, f"Tags: {', '.join(tags)}")
        else:
            fav_item.setToolTip(0, "No tags")

        return fav_item


    def pin_item(self, item_path):
        """Expose method to pin an item and broadcast globally."""
        self.pinned_manager.add_pinned_item(item_path)
        self.pinned_item_added_global.emit(item_path)

    def unpin_item(self, item_path):
        """Programmatically unpin a given path."""
        self.pinned_manager.remove_pinned_item(item_path)
        self.pinned_item_removed.emit(item_path)

    def remove_pinned_item(self, item_path):
        """UI entry point to unpin an item from the panel."""
        if item_path in self.pinned_manager.get_pinned_items():
            self.pinned_manager.remove_pinned_item(item_path)
            self.pinned_item_removed.emit(item_path)

    # ----------------------------------------------------------
    # Expand/Collapse States
    # ----------------------------------------------------------
    def _store_expanded_states(self, item, states):
        """Recursively store expanded state for each item path."""
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            states[path] = item.isExpanded()
        for i in range(item.childCount()):
            self._store_expanded_states(item.child(i), states)

    def _restore_expanded_states(self, item, states):
        """Recursively restore expanded state for each item path."""
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and path in states:
            item.setExpanded(states[path])
        for i in range(item.childCount()):
            self._restore_expanded_states(item.child(i), states)

    # ----------------------------------------------------------
    # Tree Navigation / Helpers
    # ----------------------------------------------------------
    def handle_tree_click(self, item, column):
        """
        When user single-clicks an item in pinned panel, navigate in the main file tree.
        If the item is a heading (e.g. "Favorites" or "Pinned Items"), do nothing.
        """
        # 1) Safety check: item must be a QTreeWidgetItem
        if not isinstance(item, QTreeWidgetItem):
            return

        # 2) Check if it's a heading node
        # We stored a 'True' value under a custom "HEADING_ROLE" 
        # so we can differentiate headings from normal pinned items.
        HEADING_ROLE = Qt.ItemDataRole.UserRole + 100
        is_heading = item.data(0, HEADING_ROLE)

        if is_heading:
            # It's "Favorites" or "Pinned Items" heading -- don't navigate
            return

        # 3) Otherwise, retrieve the pinned path
        item_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_path:
            return  # No valid path (safeguard)

        if not os.path.exists(item_path):
            logger.error(f"Path '{item_path}' does not exist.")
            return

        # 4) Locate the main file tree and navigate
        main_window = self.window()
        if not hasattr(main_window, 'main_tabs'):
            logger.error("Main tabs not found.")
            return

        current_main_tab = main_window.main_tabs.currentWidget()
        if not current_main_tab:
            logger.error("No active main tab found.")
            return

        tab_manager = getattr(current_main_tab, "tab_manager", None)
        if not tab_manager:
            logger.error("No TabManager found in the current main tab.")
            return

        current_nested_tab = tab_manager.currentWidget()
        if not current_nested_tab:
            logger.error("No active nested tab found.")
            return

        file_tree = current_nested_tab.findChild(FileTree)
        if not file_tree:
            logger.error("No FileTree instance found in the active nested tab.")
            return

        # 5) Actually perform the navigation
        main_window.update_address_bar(item_path)
        file_tree.setUpdatesEnabled(False)
        try:
            current_root = file_tree.file_model.rootPath()
            if not item_path.startswith(current_root):
                # Switch root if needed
                root_to_set = (
                    os.path.dirname(item_path) 
                    if os.path.isfile(item_path) 
                    else item_path
                )
                file_tree.set_root_directory(root_to_set)

            success = file_tree.navigate_and_highlight(item_path)
            if not success:
                logger.error(f"Failed to navigate to {item_path}")
        finally:
            file_tree.setUpdatesEnabled(True)
            file_tree.viewport().update()


    def find_item_by_path(self, root, path):
        if isinstance(root, QTreeWidget):
            for i in range(root.topLevelItemCount()):
                item = root.topLevelItem(i)
                if item.data(0, Qt.ItemDataRole.UserRole) == path:
                    return item
                found = self._search_children(item, path)
                if found:
                    return found
            return None
        return None

    def _search_children(self, item, path):
        if item.data(0, Qt.ItemDataRole.UserRole) == path:
            return item
        for i in range(item.childCount()):
            child = item.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == path:
                return child
            found = self._search_children(child, path)
            if found:
                return found
        return None

    # ----------------------------------------------------------
    # Double Click, Rename, etc.
    # ----------------------------------------------------------
    def handle_double_click(self, item):
        """Open a pinned file/folder when double-clicked."""
        item_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_path:
            return  # Safety check in case item_path is missing or invalid

        # If it's a folder, open in a new tab
        if os.path.isdir(item_path):
            self.open_in_new_tab(item_path)

        # Otherwise, treat it as a file and open with default system app
        else:
            try:
                if platform.system() == "Windows":
                    os.startfile(item_path)
                elif platform.system() == "Darwin":
                    subprocess.call(["open", item_path])
                else:
                    subprocess.call(["xdg-open", item_path])
            except Exception as e:
                logger.error(f"Error opening file: {item_path}. Error: {e}")

    def rename_pinned_item(self, item):
        """Rename a pinned item both on disk and in metadata if needed."""
        item_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not os.path.exists(item_path):
            logger.error("Cannot rename, path does not exist.")
            return

        new_name, ok = QInputDialog.getText(self, "Rename Item", "Enter new name:")
        if ok and new_name:
            new_path = os.path.join(os.path.dirname(item_path), new_name)
            try:
                os.rename(item_path, new_path)
                # Update pinned items and metadata
                self.metadata_manager.remove_pinned_item(item_path)
                self.metadata_manager.add_pinned_item(new_path)
                self.pinned_item_modified.emit(item_path, new_path)
                logger.info(f"Renamed '{item_path}' to '{new_path}'")
            except Exception as e:
                logger.error(f"Error renaming file: {e}")

    # ----------------------------------------------------------
    # Tagging Methods for Pinned Items
    # ----------------------------------------------------------
    def add_tag_to_item(self, tree_item):
        """
        Prompt user for a tag and add it to the pinned item's 'tags' in metadata.
        """
        item_path = tree_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_path:
            logger.error("Cannot add tag, item path is invalid.")
            return

        tag, ok = QInputDialog.getText(self, "Add Tag", f"Enter a tag for pinned item: {tree_item.text(0)}")
        if ok and tag:
            # Use MetadataManager
            current_tags = self.metadata_manager.get_tags(item_path)
            if tag not in current_tags:
                self.metadata_manager.add_tag(item_path, tag)
                QMessageBox.information(self, "Tag Added", f"Tag '{tag}' added to '{tree_item.text(0)}'.")
            else:
                QMessageBox.information(self, "Tag Exists", f"'{tree_item.text(0)}' already has tag '{tag}'.")

            self.refresh_pinned_items()  # re-build the tree, updating tooltips

    def remove_tag_from_item(self, tree_item):
        """
        Prompt user to remove a tag from the pinned item's metadata.
        """
        item_path = tree_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_path:
            logger.error("Cannot remove tag, item path is invalid.")
            return

        current_tags = self.metadata_manager.get_tags(item_path)
        if not current_tags:
            QMessageBox.information(self, "No Tags", f"No tags available for '{tree_item.text(0)}'.")
            return

        tag, ok = QInputDialog.getItem(
            self, "Remove Tag",
            f"Select a tag to remove from pinned item '{tree_item.text(0)}':",
            current_tags, 0, False
        )
        if ok and tag:
            self.metadata_manager.remove_tag(item_path, tag)
            QMessageBox.information(self, "Tag Removed", f"Removed '{tag}' from '{tree_item.text(0)}'.")
            self.refresh_pinned_items()

    # ----------------------------------------------------------
    # Context Menu Actions
    # ----------------------------------------------------------
    def show_context_menu(self, position):
        # Determine which item was right-clicked
        item = self.pinned_tree.itemAt(position)
        if not item:
            return

        item_path = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(self)

        # -----------------------------------------
        # 1) Quick Access / Open / Navigation
        # -----------------------------------------
        open_tab_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/open-tab.svg"), 
            "Open in New Tab", 
            self
        )
        open_tab_action.triggered.connect(lambda: self.open_in_new_tab(item_path))
        menu.addAction(open_tab_action)

        open_window_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/open-window.svg"), 
            "Open in New Window", 
            self
        )
        open_window_action.triggered.connect(lambda: self.open_in_new_window(item_path))
        menu.addAction(open_window_action)

        split_view_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/split.svg"), 
            "Open in Right Pane (Split View)", 
            self
        )
        split_view_action.triggered.connect(lambda: self.open_in_split_view(item_path))
        menu.addAction(split_view_action)

        menu.addSeparator()

        # -----------------------------------------
        # 2) Pin/Unpin + Favorites
        # -----------------------------------------
        unpin_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/pin-off.svg"), 
            "Unpin", 
            self
        )
        unpin_action.triggered.connect(lambda: self.unpin_item(item_path))
        menu.addAction(unpin_action)

        # NEW: Favorite / Unfavorite
        if not self.pinned_manager.is_favorite(item_path):
            add_fav_action = QAction(
                QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/star.svg"), 
                "Add to Favorites", 
                self
            )
            add_fav_action.triggered.connect(lambda: self._favorite_item(item_path))
            menu.addAction(add_fav_action)
        else:
            remove_fav_action = QAction(
                QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/star-off.svg"), 
                "Remove from Favorites", 
                self
            )
            remove_fav_action.triggered.connect(lambda: self._unfavorite_item(item_path))
            menu.addAction(remove_fav_action)

        menu.addSeparator()

        # -----------------------------------------
        # 3) Preview / PDF
        # -----------------------------------------
        preview_pdf_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/preview-pdf.svg"), 
            "Preview PDF", 
            self
        )
        preview_pdf_action.triggered.connect(lambda: self.preview_pdf(item_path))
        menu.addAction(preview_pdf_action)

        menu.addSeparator()

        # -----------------------------------------
        # 4) Explorer / File Operations
        # -----------------------------------------
        show_in_explorer_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/folder.svg"), 
            "Show in File Explorer", 
            self
        )
        show_in_explorer_action.triggered.connect(lambda: self.show_in_file_explorer(item_path))
        show_in_explorer_action.setEnabled(os.path.exists(item_path))
        menu.addAction(show_in_explorer_action)

        open_with_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/external-link.svg"), 
            "Open with Default App", 
            self
        )
        open_with_action.triggered.connect(lambda: self.open_with_default_application(item_path))
        open_with_action.setEnabled(os.path.exists(item_path))
        menu.addAction(open_with_action)

        copy_path_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/copy.svg"), 
            "Copy File Path", 
            self
        )
        copy_path_action.triggered.connect(lambda: self.copy_file_path(item_path))
        menu.addAction(copy_path_action)

        menu.addSeparator()

        # -----------------------------------------
        # 5) Rename / Properties
        # -----------------------------------------
        rename_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/folder-pen.svg"), 
            "Rename", 
            self
        )
        rename_action.triggered.connect(lambda: self.rename_pinned_item(item))
        rename_action.setEnabled(os.path.exists(item_path))
        menu.addAction(rename_action)

        properties_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/info.svg"), 
            "Properties", 
            self
        )
        properties_action.triggered.connect(lambda: self.show_item_properties(item_path))
        properties_action.setEnabled(os.path.exists(item_path))
        menu.addAction(properties_action)

        menu.addSeparator()

        # -----------------------------------------
        # 6) Tags
        # -----------------------------------------
        add_tag_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/add-tag.svg"), 
            "Add Tag", 
            self
        )
        add_tag_action.triggered.connect(lambda: self.add_tag_to_item(item))
        menu.addAction(add_tag_action)

        remove_tag_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/remove-tag.svg"), 
            "Remove Tag", 
            self
        )
        remove_tag_action.triggered.connect(lambda: self.remove_tag_from_item(item))
        menu.addAction(remove_tag_action)

        menu.addSeparator()

        # -----------------------------------------
        # 7) Refresh
        # -----------------------------------------
        refresh_action = QAction(
            QIcon("C:/EnhancedFileExplorer/assets/icons/lucid/refresh.svg"), 
            "Refresh Pinned Items", 
            self
        )
        refresh_action.triggered.connect(self.refresh_pinned_items)
        menu.addAction(refresh_action)

        # -----------------------------------------
        # Disable certain actions if path doesn't exist
        # -----------------------------------------
        if not os.path.exists(item_path):
            open_tab_action.setEnabled(False)
            open_with_action.setEnabled(False)
            rename_action.setEnabled(False)
            properties_action.setEnabled(False)
            show_in_explorer_action.setEnabled(False)
            copy_path_action.setEnabled(False)

        # -----------------------------------------
        # Execute the context menu
        # -----------------------------------------
        menu.exec(self.pinned_tree.viewport().mapToGlobal(position))


    # (Below are the helper methods for (un)favoriting)
    def _favorite_item(self, path):
        """Add this item to favorites (auto-pins if not pinned)."""
        self.pinned_manager.favorite_item(path)
        self.refresh_pinned_items()

    def _unfavorite_item(self, path):
        """Remove this item from favorites (remains pinned unless unpinned)."""
        self.pinned_manager.unfavorite_item(path)
        self.refresh_pinned_items()



    # ----------------------------------------------------------
    # Additional Actions
    # ----------------------------------------------------------

    def sort_favorites_alpha(self):
        # get all child items under favorites_root
        children = [self.favorites_root.child(i) for i in range(self.favorites_root.childCount())]
        # sort them by item.text(0)
        children.sort(key=lambda c: c.text(0))
        self.favorites_root.takeChildren()
        for c in children:
            self.favorites_root.addChild(c)

    def sort_pinned_alpha(self):
        # similarly sort pinned_root children by text(0)
        pass

    def open_in_split_view(self, item_path):
        """Open pinned item in a split view in the current container."""
        if not os.path.exists(item_path):
            logger.error(f"Path does not exist - {item_path}")
            return

        main_window = self.window()
        if not hasattr(main_window, 'main_tabs'):
            logger.error("Main tabs not found.")
            return

        current_container = main_window.main_tabs.currentWidget()
        if not current_container:
            logger.error("No active container found.")
            return

        splitter_active = getattr(current_container, "splitter", None)
        if splitter_active and splitter_active.count() > 1:
            # Already in split view => open path in the right tab manager
            right_tab_manager = splitter_active.widget(1)
            if right_tab_manager:
                self._open_in_tab_manager(right_tab_manager, item_path)
        else:
            # Toggle split view with a target path
            current_container.toggle_split_view(target_path=item_path)

    def open_in_new_tab(self, item_path):
        """Open a pinned folder (or the parent if it's a file) in a new tab."""
        if not os.path.exists(item_path):
            logger.error(f"Path does not exist - {item_path}")
            return

        main_window = self.window()
        if not hasattr(main_window, 'main_tabs'):
            logger.error("Main tabs not found.")
            return

        current_container = main_window.main_tabs.currentWidget()
        if not hasattr(current_container, 'tab_manager'):
            logger.error("TabManager not available.")
            return

        tab_manager = current_container.tab_manager

        # If user double-clicked a file, we open its parent folder as the new tab's root
        root_path = os.path.dirname(item_path) if os.path.isfile(item_path) else item_path
        new_tab = tab_manager.add_new_tab(
            title=os.path.basename(root_path),
            root_path=root_path
        )

        if not new_tab:
            logger.error(f"Failed to create new tab for {root_path}")
            return

        tab_manager.setCurrentWidget(new_tab)
        # Wait briefly, then ensure this pinned file/folder is selected in the new tab (if desired)
        QTimer.singleShot(200, lambda: self.ensure_pinned_selection(new_tab, item_path))

    def open_in_new_window(self, item_path):
        if os.path.exists(item_path):
            main_window = self.window()
            if hasattr(main_window, 'main_tabs'):
                new_main_tab = main_window.main_tabs.add_new_main_window_tab(root_path=item_path)
                main_window.main_tabs.setCurrentWidget(new_main_tab)

                file_tree = new_main_tab.findChild(FileTree)
                if file_tree:
                    file_tree.navigate_and_highlight(item_path)
                    if os.path.isdir(item_path) and hasattr(file_tree, "expand_to_path"):
                        file_tree.expand_to_path(item_path)
                else:
                    logger.error("FileTree not found in the new main tab.")
            else:
                logger.error("Main tabs not found.")
        else:
            logger.error(f"Path does not exist - {item_path}")

    def ensure_pinned_selection(self, new_tab, item_path):
        """After a short delay, navigate/highlight the pinned path in the newly created tab."""
        if not os.path.exists(item_path):
            logger.error(f"Cannot navigate to non-existent path: {item_path}")
            return

        file_tree = new_tab.findChild(FileTree)
        if not file_tree:
            logger.error("FileTree not found in the new nested tab.")
            return

        file_tree.setUpdatesEnabled(False)
        try:
            root_path = os.path.dirname(item_path) if os.path.isfile(item_path) else item_path
            file_tree.set_root_directory(root_path)
            QTimer.singleShot(100, lambda: self._complete_highlight(file_tree, item_path))
        finally:
            file_tree.setUpdatesEnabled(True)

    def _complete_highlight(self, file_tree, item_path):
        try:
            success = file_tree.navigate_and_highlight(item_path)
            if success:
                if os.path.isdir(item_path):
                    index = file_tree.file_model.index(item_path)
                    if index.isValid():
                        file_tree.expand(index)
                index = file_tree.file_model.index(item_path)
                if index.isValid():
                    file_tree.scrollTo(index, QTreeView.ScrollHint.PositionAtCenter)
                    file_tree.setCurrentIndex(index)
            else:
                logger.error(f"Failed to navigate to {item_path}")
        except Exception as e:
            logger.error(f"Exception while completing highlight: {e}")

    def preview_pdf(self, item_path):
        """Placeholder for PDF preview logic."""
        logger.info(f"Preview PDF not implemented. Path: {item_path}")

    def show_in_file_explorer(self, item_path):
        """Open the pinned item folder in the system's file explorer."""
        if os.path.exists(item_path):
            try:
                if platform.system() == "Windows":
                    os.startfile(item_path)
                elif platform.system() == "Darwin":
                    subprocess.call(["open", item_path])
                else:
                    subprocess.call(["xdg-open", item_path])
            except Exception as e:
                logger.error(f"Error opening {item_path} in explorer: {e}")
        else:
            logger.error(f"Path does not exist - {item_path}")

    def open_with_default_application(self, file_path):
        """Open pinned item with the system's default application."""
        if os.path.exists(file_path):
            try:
                if platform.system() == "Windows":
                    os.startfile(file_path)
                elif platform.system() == "Darwin":
                    subprocess.call(["open", file_path])
                else:
                    subprocess.call(["xdg-open", file_path])
            except Exception as e:
                logger.error(f"Error opening file: {file_path}. Error: {e}")

    def copy_file_path(self, file_path):
        """Copy pinned item's path to the clipboard."""
        if file_path:
            clipboard = QApplication.clipboard()
            clipboard.setText(file_path)
            logger.info(f"Copied to clipboard: {file_path}")

    def show_item_properties(self, item_path):
        """Placeholder for showing properties dialog."""
        logger.info(f"Showing properties for: {item_path}")
