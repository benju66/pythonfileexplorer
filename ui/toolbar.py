# toolbar.py

import os
from PyQt6.QtWidgets import (
    QToolBar, QToolButton, QPushButton, QMenu, QLineEdit, QApplication
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtSvg import QSvgRenderer


from modules.undo_manager import undo_manager
from ui.icon_utils import create_colored_svg_icon


class Toolbar(QToolBar):
    def __init__(self, parent):
        """
        parent should be your main window (or container)
        that has go_back, go_forward, go_up, refresh_file_tree,
        etc. defined.
        """
        super().__init__("Main Toolbar", parent)
        self.setMovable(False)
        self.parent_window = parent  # The window that has those navigation methods
        self._current_path = ""  # Keep track of the current path internally
        self.init_ui()

    def init_ui(self):
        """Optimized layout with logical grouping of features."""
        icon_path = "assets/icons"

        # --- Remove Back/Forward and keep Up, Refresh ---

        up_button = QPushButton(
            create_colored_svg_icon(f"{icon_path}/arrow-up.svg", color="#FFFFFF", icon_size=QSize(24, 24)),
            ""
        )
        up_button.setToolTip("Go up one folder level in the active tab")
        up_button.clicked.connect(lambda: self.parent_window.go_up())
        self.addWidget(up_button)

        refresh_button = QPushButton(
            create_colored_svg_icon(f"{icon_path}/refresh-cw.svg", color="#FFFFFF", icon_size=QSize(24, 24)),
            ""
        )
        refresh_button.clicked.connect(lambda: self.parent_window.refresh_file_tree())
        self.addWidget(refresh_button)

        # --- Undo/Redo Buttons ---
        undo_button = QPushButton(
            create_colored_svg_icon(f"{icon_path}/rotate-ccw.svg", color="#FFFFFF", icon_size=QSize(24, 24)),
            ""
        )
        undo_button.setToolTip("Undo last action")
        undo_button.clicked.connect(lambda: undo_manager.undo())
        self.addWidget(undo_button)

        redo_button = QPushButton(
            create_colored_svg_icon(f"{icon_path}/rotate-cw.svg", color="#FFFFFF", icon_size=QSize(24, 24)),
            ""
        )
        redo_button.setToolTip("Redo last action")
        redo_button.clicked.connect(lambda: undo_manager.redo())
        self.addWidget(redo_button)

        # --- Unified Search/Address Bar ---
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search files or enter a path...")
        # Pressing Enter will attempt path navigation or a fuzzy search
        self.search_bar.returnPressed.connect(self.handle_search_or_navigation)
        # Custom context menu for copy/paste/etc.
        self.search_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.search_bar.customContextMenuRequested.connect(self.show_search_bar_context_menu)
        # Override mouse press to handle placeholder text
        self.search_bar.mousePressEvent = self.handle_search_bar_click
        self.addWidget(self.search_bar)

        # --- Settings Button ---
        settings_button = QToolButton()
        settings_button.setIcon(
            create_colored_svg_icon(f"{icon_path}/settings.svg", color="#FFFFFF", icon_size=QSize(24, 24))
        )
        settings_button.clicked.connect(self.parent_window.open_settings_dialog)
        self.addWidget(settings_button)



    def handle_search_or_navigation(self):
        """Detect if the user entered a path or a search query."""
        text = self.search_bar.text().strip()
        normalized_path = os.path.normpath(text)
        print(f"[DEBUG] Search/Address bar triggered: {normalized_path}")

        if os.path.exists(normalized_path):
            # Valid path (file/folder), so navigate
            if os.path.isdir(normalized_path):
                print(f"[DEBUG] Navigating to directory: {normalized_path}")
                self.parent_window.open_directory_in_tab(normalized_path)
                self.update_search_bar(normalized_path)
            else:
                # If it's a file, navigate to its parent directory
                parent_dir = os.path.dirname(normalized_path)
                print(f"[DEBUG] Navigating to parent directory: {parent_dir}")
                self.parent_window.open_directory_in_tab(parent_dir)
                self.update_search_bar(parent_dir)
        else:
            # Treat as fuzzy search
            print(f"[DEBUG] Performing fuzzy search for: {text}")
            file_tree = self.parent_window.get_active_file_tree()
            if file_tree:
                selected_indexes = file_tree.selectionModel().selectedIndexes()
                if selected_indexes:
                    selected_path = file_tree.file_model.filePath(selected_indexes[0])
                    if os.path.isdir(selected_path):
                        search_directory = selected_path
                    else:
                        search_directory = os.path.dirname(selected_path)
                else:
                    root_index = file_tree.rootIndex()
                    search_directory = file_tree.file_model.filePath(root_index)

                print(f"[DEBUG] Searching in directory: {search_directory}")
                from modules.search import FileSearch
                threshold = 60  # Adjust fuzzy matching threshold
                results = FileSearch.fuzzy_search_by_name(
                    directory=search_directory,
                    query=text,
                    threshold=threshold,
                    include_folders=True
                )
                if results:
                    first_match = results[0]
                    print(f"[DEBUG] Fuzzy match: {first_match}")
                    index = file_tree.file_model.index(first_match)
                    if index.isValid():
                        file_tree.setUpdatesEnabled(False)
                        try:
                            file_tree.expand(index.parent())
                            file_tree.setCurrentIndex(index)
                            file_tree.scrollTo(index)
                        finally:
                            file_tree.setUpdatesEnabled(True)
                    else:
                        print("[WARNING] Could not create a valid index for the fuzzy match path.")
                else:
                    print("[INFO] No fuzzy matches found.")
            else:
                print("[WARNING] No active FileTree found for fuzzy searching.")

    def update_search_bar(self, path):
        """
        Update the internal current path and display it as placeholder text.
        Clears the actual text so it acts like 'ghost text' for the user.
        """
        self._current_path = path
        self.search_bar.clear()
        if path:
            self.search_bar.setPlaceholderText(path)
        else:
            self.search_bar.setPlaceholderText("Search files or enter a path...")

    def handle_search_bar_click(self, event):
        """If user left-clicks and the line edit is empty, clear it to allow fresh typing."""
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.search_bar.text():
                self.search_bar.clear()
        super(QLineEdit, self.search_bar).mousePressEvent(event)

    def show_search_bar_context_menu(self, position):
        """Context menu: cut/copy/paste plus 'Copy Path' and 'Edit Path'."""
        menu = QMenu()
        cut_action = menu.addAction("Cut")
        copy_action = menu.addAction("Copy")
        paste_action = menu.addAction("Paste")
        menu.addSeparator()

        copy_path_action = menu.addAction("Copy Path")
        if self._current_path:
            copy_path_action.triggered.connect(lambda: self.copy_to_clipboard(self._current_path))
        else:
            copy_path_action.setEnabled(False)

        edit_path_action = menu.addAction("Edit Path")
        if self._current_path:
            edit_path_action.triggered.connect(self.edit_current_path)
        else:
            edit_path_action.setEnabled(False)

        cut_action.triggered.connect(self.handle_cut)
        copy_action.triggered.connect(self.handle_copy)
        paste_action.triggered.connect(self.search_bar.paste)

        menu.exec(self.search_bar.mapToGlobal(position))

    def handle_copy(self):
        """If QLineEdit is empty, copy the ghost text; otherwise, normal copy."""
        if self.search_bar.text():
            self.search_bar.copy()
        else:
            if self._current_path:
                self.copy_to_clipboard(self._current_path)

    def handle_cut(self):
        """If QLineEdit is empty, optionally copy the ghost text. Otherwise, normal cut."""
        if self.search_bar.text():
            self.search_bar.cut()
        else:
            if self._current_path:
                self.copy_to_clipboard(self._current_path)

    def edit_current_path(self):
        """Switch from placeholder text to real text so the user can edit it."""
        if self._current_path:
            self.search_bar.setText(self._current_path)
            self.search_bar.setFocus()
            self.search_bar.setCursorPosition(len(self._current_path))

    def copy_to_clipboard(self, text):
        """Helper method to copy text to system clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
