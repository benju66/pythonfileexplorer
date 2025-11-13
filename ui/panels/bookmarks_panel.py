# bookmarks_panel.py
import os
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QMessageBox, QInputDialog, QMenu
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QAction
from modules.metadata_manager import MetadataManager

class BookmarksPanel(QDockWidget):
    """
    A robust bookmarks panel that:
      - Reads existing tags from metadata_manager
      - Allows adding new bookmarks (path + tag)
      - Allows removing or updating tags via right-click context menu
    """
    def __init__(self, parent=None):
        super().__init__("Bookmarks", parent)

        # Configure the dock widget properties (movable, closable)
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        # Load from your MetadataManager
        self.metadata_manager = MetadataManager("data/metadata.json")

        # Create a main widget + layout inside the dock
        self.main_widget = QWidget()
        self.setWidget(self.main_widget)
        self.main_layout = QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)

        # -- Top button bar for "Add Bookmark" & "Refresh" --
        self.button_bar = QHBoxLayout()
        self.btn_add_bookmark = QPushButton("Add Bookmark")
        self.btn_add_bookmark.clicked.connect(self.add_bookmark_dialog)
        self.button_bar.addWidget(self.btn_add_bookmark)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_bookmarks)
        self.button_bar.addWidget(self.btn_refresh)

        # Optional: stretch or spacer
        self.button_bar.addStretch(1)

        self.main_layout.addLayout(self.button_bar)

        # Create the tree to display tags
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(False)
        self.tree.setHeaderLabels(["Tags / Items"])
        # Double-click: open item (folder or procore link)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        # Right-click context menu
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_tree_context_menu)

        self.main_layout.addWidget(self.tree)

        # Initially populate the bookmarks tree
        self.refresh_bookmarks()

    # --------------------------------------------------------------------
    # Core functionality
    # --------------------------------------------------------------------

    def refresh_bookmarks(self):
        """
        Rebuild the tree to show all tags. For each tag, list items that have that tag.

        'metadata_manager.metadata["tags"]' should be a dict of:
            {
              "C:/Some/Local/Path": ["TagA", "TagB"],
              "ProcoreLink:Project->Link": ["SomeTag", ...],
              ...
            }
        """
        self.tree.clear()

        # 1) Gather tags from the metadata dict
        tags_dict = self.metadata_manager.metadata.get("tags", {})
        all_tags = {}  # e.g. { "TagA": [ "C:/SomePath", "ProcoreLink:..." ], ... }

        for item_path, tags in tags_dict.items():
            for tag in tags:
                all_tags.setdefault(tag, []).append(item_path)

        # 2) Create a top-level item for each tag
        for tag_name, item_paths in all_tags.items():
            tag_item = QTreeWidgetItem([tag_name])
            self.tree.addTopLevelItem(tag_item)

            # 3) For each path that has this tag, create a child item
            for path in item_paths:
                # Show the last part of the path or an ID, store the full path as user data
                display_name = os.path.basename(path) or path
                child_item = QTreeWidgetItem([display_name])
                child_item.setData(0, Qt.ItemDataRole.UserRole, path)
                tag_item.addChild(child_item)

        self.tree.expandAll()

    def on_item_double_clicked(self, item, column):
        """
        Handle double-clicks:
          - If user clicks a top-level item (the tag itself), do nothing (just a category).
          - If it's a child item referencing a pinned folder or procore link, open/expand it.
        """
        parent = item.parent()
        if parent is None:
            # It's a top-level tag node; do nothing or refresh if desired
            return

        # A child item referencing a path or procore link
        item_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_path:
            return

        # 1) If it’s a real file/folder path, open it in new tab
        if os.path.exists(item_path):
            self.open_pinned_folder_in_tab(item_path)
        # 2) If it’s a procore link
        elif item_path.startswith("ProcoreLink:"):
            self.expand_procore_item(item_path)
        else:
            print(f"[WARNING] Unknown item path: {item_path}")

    def open_pinned_folder_in_tab(self, path):
        """
        Delegates to the main_window to open a pinned folder in a new tab if possible.
        We assume main_window has a .open_directory_in_tab(...) method.
        """
        main_window = self.window()
        if not hasattr(main_window, "open_directory_in_tab"):
            print("[ERROR] main_window is missing 'open_directory_in_tab' method.")
            return

        main_window.open_directory_in_tab(path)
        print(f"[INFO] Opened pinned folder in new tab: {path}")

    def expand_procore_item(self, link_id):
        """
        Demonstrates how you might expand a link in the Procore panel.
        We'll rely on your current_container.procore_panel to do the real work.
        """
        main_window = self.window()
        if not hasattr(main_window, "main_tabs"):
            print("[ERROR] main_window lacks 'main_tabs'. Cannot expand procore item.")
            return

        current_container = main_window.main_tabs.currentWidget()
        if not hasattr(current_container, "procore_panel"):
            print("[ERROR] Current container has no 'procore_panel'.")
            return

        procore_panel = current_container.procore_panel
        if not procore_panel:
            print("[ERROR] Procore panel not found or not created.")
            return

        # Suppose procore_panel has some expand_link_by_id(link_id)
        print(f"[INFO] Expand Procore item: {link_id}")
        # procore_panel.expand_link_by_id(link_id)

    # --------------------------------------------------------------------
    # Adding Bookmarks / Tags
    # --------------------------------------------------------------------

    def add_bookmark_dialog(self):
        """
        Let the user specify a local path or Procore link + a tag.
        Then call metadata_manager.add_tag(...).
        """
        # 1) Ask for item path
        path, ok_path = QInputDialog.getText(
            self, "Add Bookmark Path",
            "Enter local path or procore ID (e.g. 'ProcoreLink:Project->Link'):"
        )
        if not (ok_path and path):
            return  # User cancelled or empty input

        # 2) Ask for tag name
        tag, ok_tag = QInputDialog.getText(
            self, "Tag",
            f"Enter a tag for:\n{path}"
        )
        if not (ok_tag and tag):
            return

        # 3) Add tag to metadata
        self.metadata_manager.add_tag(path, tag)  # or your custom logic
        self.metadata_manager.save_metadata()     # persist
        # 4) Refresh the tree
        self.refresh_bookmarks()
        print(f"[INFO] Added path '{path}' with tag '{tag}'.")

    # --------------------------------------------------------------------
    # Right-click context menu (remove item, remove tag, etc.)
    # --------------------------------------------------------------------

    def on_tree_context_menu(self, position: QPoint):
        """
        Show a context menu to remove tags or remove an item from a tag.
        For top-level (tag), we can remove entire tag from all items.
        For child items, remove that tag from that path.
        """
        item = self.tree.itemAt(position)
        if not item:
            return  # user right-clicked empty area

        menu = QMenu(self)
        parent = item.parent()

        if parent is None:
            # => top-level item = a tag node
            remove_tag_action = QAction("Remove Entire Tag", self)
            remove_tag_action.triggered.connect(lambda: self.remove_entire_tag(item.text(0)))
            menu.addAction(remove_tag_action)
        else:
            # => child item => path under a tag
            remove_item_action = QAction("Remove Tag from This Item", self)
            remove_item_action.triggered.connect(
                lambda: self.remove_tag_from_item(
                    parent.text(0),  # the tag
                    item.data(0, Qt.ItemDataRole.UserRole)  # the path
                )
            )
            menu.addAction(remove_item_action)

        # Show the context menu at cursor
        menu.exec(self.tree.mapToGlobal(position))

    def remove_entire_tag(self, tag_name: str):
        """
        Remove 'tag_name' from the entire metadata dict, i.e. from every path that had it.
        """
        tags_dict = self.metadata_manager.metadata.get("tags", {})
        found_something = False

        for path, tags in tags_dict.items():
            if tag_name in tags:
                tags.remove(tag_name)
                found_something = True

        if found_something:
            self.metadata_manager.save_metadata()
            self.refresh_bookmarks()
            print(f"[INFO] Removed entire tag '{tag_name}' from all items.")
        else:
            QMessageBox.information(self, "Remove Tag", f"Tag '{tag_name}' not found in metadata.")

    def remove_tag_from_item(self, tag_name: str, path: str):
        """
        Remove a single tag from a single path in the metadata.
        """
        tags_dict = self.metadata_manager.metadata.get("tags", {})
        if path not in tags_dict:
            QMessageBox.warning(self, "Remove Tag", f"Path '{path}' not found in metadata.")
            return

        tag_list = tags_dict[path]
        if tag_name in tag_list:
            tag_list.remove(tag_name)
            self.metadata_manager.save_metadata()
            self.refresh_bookmarks()
            print(f"[INFO] Removed tag '{tag_name}' from path '{path}'.")
        else:
            QMessageBox.information(self, "Remove Tag", f"Tag '{tag_name}' not found on path:\n{path}.")

    def reload(self):
        """Public method to re-populate the bookmarks from metadata, if needed."""
        self.refresh_bookmarks()
