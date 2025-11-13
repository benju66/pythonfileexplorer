import os
from PyQt6.QtWidgets import QTreeView, QMenu, QApplication, QMessageBox, QInputDialog, QHeaderView, QDialog, QVBoxLayout, QLabel, QScrollArea, QPushButton, QHBoxLayout, QVBoxLayout, QAbstractItemView
from PyQt6.QtCore import QDir, Qt, pyqtSignal, QMimeData, QUrl, QTimer, QEvent, QObject
from PyQt6.QtGui import QFileSystemModel, QDrag, QCursor, QIcon, QAction, QPixmap, QImage, QClipboard, QTransform
from PyPDF2 import PdfReader
import fitz  # PyMuPDF
import tempfile
from modules.file_operations import create_new_file, create_new_folder
from models.custom_file_system_model import CustomFileSystemModel
from modules.search import FileSearch
import shutil

# NEW: Import undo_manager & our command classes
from modules.undo_manager import undo_manager
from modules.undo_commands import (
    CreateFileCommand,
    CreateFolderCommand,
    DeleteItemCommand,
    RenameCommand  # If you want to handle rename in the FileTree
)

class FileTree(QTreeView):
    context_menu_action_triggered = pyqtSignal(str, str)  # action, file_path
    location_changed = pyqtSignal(str)
    file_tree_clicked = pyqtSignal(object)

    def __init__(self, metadata_manager=None, parent=None):
        """
        If metadata_manager is not provided, we create a default one here.
        That manager is used for tagging, folder colors, etc.
        """
        super().__init__(parent)

        # If none is provided, create a default one
        if metadata_manager is None:
            from modules.metadata_manager import MetadataManager
            metadata_manager = MetadataManager("data/metadata.json")

        self.metadata_manager = metadata_manager
        from PyQt6.QtWidgets import QAbstractItemView
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.current_folder_path = None
        self.auto_resize_enabled = True
        self._path_cache = {}
        self._index_cache = {}
        self._cache_limit = 1000

        # --------------------------------------------------
        # Use CustomFileSystemModel (enables rename + folder colors)
        # --------------------------------------------------
        self.file_model = CustomFileSystemModel(self.metadata_manager)
        self.file_model.setRootPath(QDir.rootPath())
        self.file_model.setFilter(
            QDir.Filter.Dirs
            | QDir.Filter.NoDotAndDotDot
            | QDir.Filter.AllEntries
        )
        self.file_model.setReadOnly(False)

        # Attach model to the QTreeView
        self.setModel(self.file_model)
        self.setRootIndex(self.file_model.index(QDir.rootPath()))

        # --------------------------------------------------
        # COLUMN + HEADER SETUP
        # --------------------------------------------------
        header = self.header()
        header.setSectionsClickable(True)
        header.setCascadingSectionResizes(False)

        # Let user drag columns (Interactive)
        for col in range(4):  # (Name, Size, Type, Date)
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)

        # Minimum size for any column
        header.setMinimumSectionSize(120)

        self.setHeaderHidden(False)
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.setUniformRowHeights(True)
        self.setAnimated(True)
        self.setExpandsOnDoubleClick(True)
        self.setIndentation(20)

        # --------------------------------------------------
        # DISABLE inline rename on double-click
        # and handle double-click by opening file
        # --------------------------------------------------
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.doubleClicked.connect(self.handle_double_click)

        # --------------------------------------------------
        # CONTEXT MENU & DRAG/DROP
        # --------------------------------------------------
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeView.DragDropMode.DragDrop)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setTabKeyNavigation(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # --------------------------------------------------
        # LAZY LOADING / EXPAND/COLLAPSE HANDLING
        # --------------------------------------------------
        self.expanded.connect(self._load_directory_content)

        # Auto-resize signals (Name column)
        self.expanded.connect(self.auto_resize_name_column)
        self.collapsed.connect(self.auto_resize_name_column)
        self.file_model.rowsInserted.connect(self.auto_resize_name_column)
        self.file_model.rowsRemoved.connect(self.auto_resize_name_column)
        self.file_model.modelReset.connect(self.auto_resize_name_column)

        # --------------------------------------------------
        # CLICK & SELECTION HANDLING
        # --------------------------------------------------
        self.clicked.connect(self.on_tree_item_clicked)
        self.selectionModel().selectionChanged.connect(
            lambda selected, deselected: self.on_tree_item_clicked(selected.indexes()[0])
            if selected.indexes() else None
        )

        # Optionally track window-resize
        if self.window():
            self.window().installEventFilter(self)
            
    # ------------------------------------------------------
    # Double-Click on Column Divider => "Resize to Contents"
    # ------------------------------------------------------
    def on_header_section_doubleclicked(self, logical_index: int):
        """
        Called when user double-clicks a column handle. 
        We'll forcibly resize that column to its contents, 
        then clamp to our minimum.
        """
        self.resizeColumnToContents(logical_index)

        # Enforce a minimum width (like 120). Adjust as needed.
        current_size = self.header().sectionSize(logical_index)
        MIN_SIZE = 120
        if current_size < MIN_SIZE:
            self.header().resizeSection(logical_index, MIN_SIZE)

    def auto_resize_name_column(self, *args, **kwargs):
        """
        Whenever the model changes or a folder expands/collapses,
        auto-resize the Name column (column 0) so the file name is fully visible
        or shrinks if longer filenames are no longer visible.
        Then set it back to Interactive so the user can still drag it manually.
        """
        if not self.auto_resize_enabled:
            return

        name_column = 0
        self.resizeColumnToContents(name_column)
        self.header().setSectionResizeMode(name_column, QHeaderView.ResizeMode.Interactive)


    def _get_cached_index(self, path):
        """Get cached model index for a path or create a new one."""
        if path not in self._index_cache:
            if len(self._index_cache) > self._cache_limit:
                self._index_cache.clear()  # Clear cache if too large
            self._index_cache[path] = self.file_model.index(path)
        return self._index_cache[path]

    def _clear_caches(self):
        """Clear caches when model changes."""
        self._path_cache.clear()
        self._index_cache.clear()

    def _load_directory_content(self, index):
        """Load directory contents lazily, but avoid redundant expansion."""
        if not self.isExpanded(index) or index in self._path_cache:
            return  # ✅ Skip if already expanded
        
        model = self.model()
        rows = model.rowCount(index)
        
        self._path_cache[index] = True  # ✅ Mark as cached to avoid reloading
        chunk_size = 100  

        self.viewport().setUpdatesEnabled(False)  # ✅ Optimize UI updates
        try:
            for i in range(0, rows, chunk_size):
                self._load_chunk(index, i, min(i + chunk_size, rows))
        finally:
            self.viewport().setUpdatesEnabled(True)  # ✅ Re-enable UI updates

    def _load_chunk(self, index, start, end):
        """Efficiently load a batch of directory items."""
        model = self.model()
        for i in range(start, end):
            model.index(i, 0, index)  # ✅ Load without forcing updates

        if end - start > 10:  # ✅ Process events only for large updates
            QApplication.processEvents()

    def show_context_menu(self, position):
        """
        Show the context menu for the file tree with icons and improved grouping,
        including inline renaming, color changes for files/folders, and more.
        """
        # 1) Figure out which item was right-clicked
        index = self.indexAt(position)
        if not index.isValid():
            return

        # 2) Gather all distinct file paths from the selected indexes
        selected_indexes = self.selectedIndexes()
        distinct_paths = set()
        for idx in selected_indexes:
            # Usually we only want column 0, so we skip col 1..3
            if idx.column() == 0:
                path = self.file_model.filePath(idx)
                if path:
                    distinct_paths.add(path)

        # For convenience, the item specifically clicked is:
        selected_path = self.file_model.filePath(index)
        is_folder = os.path.isdir(selected_path)

        # Build the context menu
        context_menu = QMenu(self)
        icon_path = "assets/icons"  # Adjust path if needed

        # ─────────────────────
        # 📁 File & Folder Actions
        # ─────────────────────
        open_action = QAction(QIcon(f"{icon_path}/folder-open.svg"), "Open", self)
        show_metadata_action = QAction(QIcon(f"{icon_path}/info.svg"), "Show Metadata", self)
        show_explorer_action = QAction(QIcon(f"{icon_path}/folder.svg"), "Show in File Explorer", self)
        context_menu.addAction(open_action)
        context_menu.addAction(show_metadata_action)
        context_menu.addAction(show_explorer_action)

        context_menu.addSeparator()  # --- Divider ---

        # ✏️ Inline Editing for Renaming
        rename_action = QAction(QIcon(f"{icon_path}/folder-pen.svg"), "Rename", self)
        rename_action.triggered.connect(lambda: self.edit(index))
        context_menu.addAction(rename_action)

        delete_action = QAction(QIcon(f"{icon_path}/delete.svg"), "Delete", self)
        context_menu.addAction(delete_action)

        context_menu.addSeparator()

        # ─────────────────────
        # 📌 Pin & Tag
        # ─────────────────────
        pin_action = QAction(QIcon(f"{icon_path}/pin.svg"), "Pin Item", self)
        context_menu.addAction(pin_action)

        tag_action = QAction(QIcon(f"{icon_path}/tag.svg"), "Add Tag", self)
        context_menu.addAction(tag_action)

        remove_tag_action = QAction("Remove Tag", self)
        context_menu.addAction(remove_tag_action)

        context_menu.addSeparator()

        # 📋 Copy/Paste & Duplicate
        copy_action = QAction(QIcon(f"{icon_path}/copy.svg"), "Copy", self)
        paste_action = QAction(QIcon(f"{icon_path}/clipboard-paste.svg"), "Paste", self)
        duplicate_action = QAction(QIcon(f"{icon_path}/copy-plus.svg"), "Duplicate", self)
        context_menu.addAction(copy_action)
        context_menu.addAction(paste_action)
        context_menu.addAction(duplicate_action)

        context_menu.addSeparator()

        # 🗂️ File/Folder Creation
        add_new_file_action = QAction(QIcon(f"{icon_path}/file-plus.svg"), "Add New File", self)
        add_new_folder_action = QAction(QIcon(f"{icon_path}/folder-plus.svg"), "Add New Folder", self)
        context_menu.addAction(add_new_file_action)
        context_menu.addAction(add_new_folder_action)

        context_menu.addSeparator()

        # 📂 Tree Navigation
        collapse_action = QAction(QIcon(f"{icon_path}/list-collapse.svg"), "Collapse All", self)
        expand_action = QAction(QIcon(f"{icon_path}/expand.svg"), "Expand All", self)
        context_menu.addAction(collapse_action)
        context_menu.addAction(expand_action)

        context_menu.addSeparator()

        # 🆕 Open in New Tab, New Window, or Split View (Folders only)
        if is_folder:
            open_in_new_tab_action = QAction(QIcon(f"{icon_path}/app-window.svg"), "Open in New Tab", self)
            open_in_new_window_action = QAction(QIcon(f"{icon_path}/app-window.svg"), "Open in New Window", self)
            split_view_action = QAction(QIcon(f"{icon_path}/square-split-horizontal.svg"), "Toggle Split View", self)

            context_menu.addAction(open_in_new_tab_action)
            context_menu.addAction(open_in_new_window_action)
            context_menu.addAction(split_view_action)

            open_in_new_tab_action.triggered.connect(lambda: self.open_folder_in_new_tab(selected_path))
            open_in_new_window_action.triggered.connect(lambda: self.open_folder_in_new_window(selected_path))
            split_view_action.triggered.connect(lambda: self.window().toggle_split_view(selected_path))

        # ✅ PDF Preview
        if selected_path.endswith(".pdf"):
            preview_pdf_action = QAction(QIcon(f"{icon_path}/pdf-preview.svg"), "Preview PDF", self)
            preview_pdf_action.triggered.connect(lambda: self.preview_pdf(selected_path))
            context_menu.addAction(preview_pdf_action)

        SUPPORTED_IMAGES = (".jpg", ".jpeg", ".png", ".svg", ".heic", ".gif", ".bmp")
        if selected_path.lower().endswith(SUPPORTED_IMAGES):
            preview_img_action = QAction(QIcon(f"{icon_path}/image-preview.svg"), "Preview Image", self)
            preview_img_action.triggered.connect(lambda: self.preview_image(selected_path))
            context_menu.addAction(preview_img_action)

        # ─────────────────────
        # NEW: "Change Text Color" that works for single OR multiple items
        # ─────────────────────
        change_color_action = QAction("Change Text Color", self)
        # If more than one distinct path => multi-item approach
        if len(distinct_paths) > 1:
            change_color_action.triggered.connect(lambda: self.change_multiple_items_text_color(distinct_paths))
        else:
            # Single item approach
            change_color_action.triggered.connect(lambda: self.change_item_text_color(selected_path))
        context_menu.addAction(change_color_action)

        # ─────────────────────
        # Connect All Actions
        # ─────────────────────
        open_action.triggered.connect(lambda: self.open_file(selected_path))
        show_metadata_action.triggered.connect(
            lambda: self.context_menu_action_triggered.emit("show_metadata", selected_path))
        show_explorer_action.triggered.connect(lambda: self.show_in_file_explorer(selected_path))

        rename_action.triggered.connect(lambda: self.edit(index))

        # Delete with undo-based approach
        delete_action.triggered.connect(lambda: self.delete_item_with_undo(selected_path))

        pin_action.triggered.connect(lambda: self.context_menu_action_triggered.emit("pin", selected_path))

        tag_action.triggered.connect(lambda: self.tag_item(selected_path))
        remove_tag_action.triggered.connect(lambda: self.remove_tag_from_item(selected_path))

        copy_action.triggered.connect(lambda: self.copy_item(selected_path))
        paste_action.triggered.connect(lambda: self.paste_item(selected_path))
        duplicate_action.triggered.connect(lambda: self.duplicate_item(selected_path))

        add_new_file_action.triggered.connect(lambda: self.create_new_file(selected_path))
        add_new_folder_action.triggered.connect(lambda: self.create_new_folder(selected_path))

        collapse_action.triggered.connect(self.collapseAll)
        expand_action.triggered.connect(self.expandAll)

        # Execute (display) the context menu at the cursor position
        context_menu.exec(self.viewport().mapToGlobal(position))


    def change_item_text_color(self, item_path: str):
        """
        Prompt the user to choose both a color and whether text is bold,
        then store these settings in metadata so the model can render them.

        This version also shows each recent color with an 'X' to remove it,
        and a 'Clear All' button to wipe them all at once.
        """
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QLabel, QPushButton,
            QDialogButtonBox, QCheckBox, QColorDialog,
            QHBoxLayout, QScrollArea, QWidget
        )
        from PyQt6.QtGui import QColor

        class ColorBoldDialog(QDialog):
            """
            Dialog showing:
            - A vertical list of 'recent color' rows: each swatch + remove button
            - An optional "Clear All" button
            - A "Pick Color..." button (full QColorDialog)
            - A "Bold?" checkbox
            - OK/Cancel buttons
            """
            def __init__(self, parent=None, metadata_manager=None):
                super().__init__(parent)
                self.setWindowTitle("Set Item Appearance")
                self.setModal(True)

                self.metadata_manager = metadata_manager
                self.selected_color = None
                self.bold_checked = False

                main_layout = QVBoxLayout(self)

                label = QLabel("Pick a color and choose whether to make text bold:")
                main_layout.addWidget(label)

                # Build the "Recent Colors" section
                recent_colors = self.metadata_manager.get_recent_colors()
                if recent_colors:
                    # Header row with "Recent Colors:" label + "Clear All" button
                    header_layout = QHBoxLayout()
                    rc_label = QLabel("Recent Colors:")
                    header_layout.addWidget(rc_label)

                    clear_all_btn = QPushButton("Clear All")
                    clear_all_btn.setStyleSheet("background-color: none;")
                    clear_all_btn.clicked.connect(self.clear_all_recent_colors)
                    header_layout.addWidget(clear_all_btn)

                    main_layout.addLayout(header_layout)

                    # We'll place all color rows in a vertical layout
                    self.colors_list_layout = QVBoxLayout()
                    # Optionally, put it in a scroll area if you want
                    # but for 5 max, it's probably fine without scrolling.

                    # Build rows for each color
                    for color_hex in recent_colors:
                        self._add_color_row(color_hex)

                    main_layout.addLayout(self.colors_list_layout)

                # "Pick Color…" button (full QColorDialog)
                self.color_button = QPushButton("Pick Color…")
                self.color_button.clicked.connect(self.pick_color)
                main_layout.addWidget(self.color_button)

                # Bold checkbox
                self.bold_checkbox = QCheckBox("Make text bold")
                main_layout.addWidget(self.bold_checkbox)

                # OK/Cancel
                button_box = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok 
                    | QDialogButtonBox.StandardButton.Cancel
                )
                button_box.accepted.connect(self.accept)
                button_box.rejected.connect(self.reject)
                main_layout.addWidget(button_box)

            def _add_color_row(self, color_hex: str):
                """
                Create a horizontal row with:
                - A color swatch button
                - A small 'X' button to remove that color from recent_colors
                """
                row_layout = QHBoxLayout()

                # 1) Swatch button
                swatch_btn = QPushButton()
                swatch_btn.setFixedSize(30, 20)
                swatch_btn.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #CCC;")
                swatch_btn.clicked.connect(lambda _, c=color_hex: self.set_selected_color(c))
                row_layout.addWidget(swatch_btn)

                # 2) Remove color button
                remove_btn = QPushButton("X")
                remove_btn.setFixedSize(20, 20)
                remove_btn.setStyleSheet("background-color: none;")
                remove_btn.clicked.connect(lambda _, c=color_hex: self.remove_color_and_refresh(c))
                row_layout.addWidget(remove_btn)

                self.colors_list_layout.addLayout(row_layout)

            def remove_color_and_refresh(self, color_hex: str):
                """Remove the color from metadata, then rebuild the recent-colors UI."""
                self.metadata_manager.remove_recent_color(color_hex)
                self.refresh_recent_colors_ui()

            def clear_all_recent_colors(self):
                """Remove all recent colors at once, then rebuild UI."""
                self.metadata_manager.clear_recent_colors()
                self.refresh_recent_colors_ui()

            def refresh_recent_colors_ui(self):
                """
                Rebuild the rows for recent colors after removing one or clearing them all.
                """
                # 1) Clear out existing color rows
                while self.colors_list_layout.count():
                    row_item = self.colors_list_layout.takeAt(0)
                    if row_item.layout():
                        # remove child widgets from the row
                        while row_item.layout().count():
                            widget_item = row_item.layout().takeAt(0)
                            w = widget_item.widget()
                            if w:
                                w.deleteLater()
                        row_item.layout().deleteLater()

                # 2) Re-add rows from updated metadata
                for color_hex in self.metadata_manager.get_recent_colors():
                    self._add_color_row(color_hex)

            def set_selected_color(self, color_hex: str):
                """When user clicks a recent swatch button."""
                self.selected_color = QColor(color_hex)
                print(f"User clicked recent color: {color_hex}")

            def pick_color(self):
                """Open a QColorDialog to pick a brand-new color."""
                chosen = QColorDialog.getColor(QColor("white"), self, "Select Text Color")
                if chosen.isValid():
                    self.selected_color = chosen

            def accept(self):
                """When the user clicks OK, store whether text is bold, then close."""
                self.bold_checked = self.bold_checkbox.isChecked()
                super().accept()

        # ─────────────────────────────────────────────────────────────────────
        # Instantiate and run the dialog, passing in metadata_manager
        dialog = ColorBoldDialog(parent=self, metadata_manager=self.metadata_manager)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            if dialog.selected_color is not None:
                color_hex = dialog.selected_color.name(QColor.NameFormat.HexRgb)

                # 1) Add it to recent colors, so it appears next time
                self.metadata_manager.add_recent_color(color_hex)

                # 2) Now save to item_colors
                self.metadata_manager.set_item_color(item_path, color_hex)

            # Bold
            self.metadata_manager.set_item_bold(item_path, dialog.bold_checked)

            # Refresh the model so the new color/bold is shown
            self.file_model.layoutChanged.emit()

    def change_multiple_items_text_color(self, item_paths):
        """
        Let the user pick one color/bold setting, then apply to all paths in 'item_paths'.
        """
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QLabel, QPushButton,
            QDialogButtonBox, QCheckBox, QColorDialog,
            QHBoxLayout
        )
        from PyQt6.QtGui import QColor

        class ColorBoldDialog(QDialog):
            """
            Exactly like your single-item dialog, but we won't do any path-specific logic here.
            We'll just let them pick a color and bold, returning the results.
            """
            def __init__(self, parent=None, metadata_manager=None):
                super().__init__(parent)
                self.setWindowTitle("Set Appearance for Multiple Items")
                self.setModal(True)

                self.metadata_manager = metadata_manager
                self.selected_color = None
                self.bold_checked = False

                layout = QVBoxLayout(self)

                label = QLabel("Pick a color and whether to make text bold for ALL selected items:")
                layout.addWidget(label)

                # Show recent colors row
                self.recent_colors_layout = QHBoxLayout()
                recent_colors = self.metadata_manager.get_recent_colors()
                if recent_colors:
                    rc_label = QLabel("Recent Colors:")
                    layout.addWidget(rc_label)

                    for color_hex in recent_colors:
                        btn = QPushButton()
                        btn.setFixedSize(30, 20)
                        btn.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #CCC;")
                        btn.clicked.connect(lambda _, c=color_hex: self.set_selected_color(c))
                        self.recent_colors_layout.addWidget(btn)

                    layout.addLayout(self.recent_colors_layout)

                # "Pick Color..." button
                self.color_button = QPushButton("Pick Color…")
                self.color_button.clicked.connect(self.pick_color)
                layout.addWidget(self.color_button)

                # Bold checkbox
                self.bold_checkbox = QCheckBox("Make text bold")
                layout.addWidget(self.bold_checkbox)

                # OK/Cancel
                button_box = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok
                    | QDialogButtonBox.StandardButton.Cancel
                )
                button_box.accepted.connect(self.accept)
                button_box.rejected.connect(self.reject)
                layout.addWidget(button_box)

            def set_selected_color(self, color_hex: str):
                self.selected_color = QColor(color_hex)

            def pick_color(self):
                chosen = QColorDialog.getColor(QColor("white"), self, "Select Text Color")
                if chosen.isValid():
                    self.selected_color = chosen

            def accept(self):
                self.bold_checked = self.bold_checkbox.isChecked()
                super().accept()

        # ─────────────────────────────────────────────────────────────────
        # 1) Show the dialog once
        dialog = ColorBoldDialog(parent=self, metadata_manager=self.metadata_manager)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            if dialog.selected_color is not None:
                color_hex = dialog.selected_color.name(QColor.NameFormat.HexRgb)

                # 2) We add it to recent colors, so next time it shows up
                self.metadata_manager.add_recent_color(color_hex)

                # 3) Now loop over each path and set the same color
                for path in item_paths:
                    self.metadata_manager.set_item_color(path, color_hex)

            # 4) Bold
            for path in item_paths:
                self.metadata_manager.set_item_bold(path, dialog.bold_checked)

            # 5) Refresh the model
            self.file_model.layoutChanged.emit()



    def tag_item(self, file_path):
        """
        Prompt user to add a tag to the selected file/folder via the metadata manager.
        """
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Invalid Path", f"'{file_path}' does not exist.")
            return

        tag, ok = QInputDialog.getText(self, "Add Tag", f"Enter a tag for '{file_path}':")
        if ok and tag:
            current_tags = self.metadata_manager.get_tags(file_path)
            if tag not in current_tags:
                self.metadata_manager.add_tag(file_path, tag)
                QMessageBox.information(
                    self, "Tag Added",
                    f"Tag '{tag}' added to '{os.path.basename(file_path)}'."
                )
            else:
                QMessageBox.information(
                    self, "Tag Exists",
                    f"'{os.path.basename(file_path)}' already has tag '{tag}'."
                )

    def remove_tag_from_item(self, file_path):
        """
        Prompt user to remove an existing tag from the selected file/folder.
        """
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Invalid Path", f"'{file_path}' does not exist.")
            return

        current_tags = self.metadata_manager.get_tags(file_path)
        if not current_tags:
            QMessageBox.information(self, "No Tags", f"No tags available for '{file_path}'.")
            return

        tag, ok = QInputDialog.getItem(
            self, "Remove Tag",
            f"Select a tag to remove from '{os.path.basename(file_path)}':",
            current_tags, 0, False
        )
        if ok and tag:
            self.metadata_manager.remove_tag(file_path, tag)
            QMessageBox.information(
                self, "Tag Removed",
                f"Removed '{tag}' from '{os.path.basename(file_path)}'."
            )

    def search_and_highlight_file(self, file_name):
        """Search for a file and highlight it in the tree."""
        root_path = self.file_model.rootPath()
        search_results = FileSearch.search_by_name(root_path, file_name)

        if not search_results:
            print(f"No file found matching: {file_name}")
            return

        self.setUpdatesEnabled(False)  # ✅ Disable updates for bulk operations

        try:
            for file_path in search_results:
                index = self.file_model.index(file_path)
                if index.isValid():
                    self.expand(index.parent())  # ✅ Expand parent only once
                    self.setCurrentIndex(index)
                    self.scrollTo(index, QTreeView.ScrollHint.PositionAtCenter)
                    break  # ✅ Stop at the first valid result
        finally:
            self.setUpdatesEnabled(True)  # ✅ Re-enable UI updates

    def on_tree_item_clicked(self, index):
        """Handle clicks on tree items and emit path changes."""
        if not index.isValid():
            print("[WARNING] Clicked on an empty space, ignoring.")
            return

        selected_path = self.file_model.filePath(index)
        print(f"[DEBUG] File clicked: {selected_path}")

        # Store the folder we just clicked (or its parent if it's a file).
        if os.path.isdir(selected_path):
            self.current_folder_path = selected_path
        else:
            self.current_folder_path = os.path.dirname(selected_path)

        # Emit the existing location_changed signal if the path is valid
        if os.path.exists(selected_path):
            self.location_changed.emit(selected_path)

        # Let the TabManager know this FileTree was clicked
        self.file_tree_clicked.emit(self)

    def handle_double_click(self, index):
        """
        Open the selected file in the system's default application when double-clicked.
        If the path does not exist, warn the user.
        """
        file_path = self.file_model.filePath(index)

        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Not Found", f"Cannot open: {file_path}")
            return

        try:
            import subprocess
            import platform
            system = platform.system()

            if system == "Windows":
                os.startfile(file_path)
            elif system == "Darwin":  # macOS
                subprocess.call(["open", file_path])
            else:  # Linux or other
                subprocess.call(["xdg-open", file_path])

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{file_path}\n\n{str(e)}")

    def auto_resize_columns(self, *args, **kwargs):
        """Resize columns if they're still near the minimum, to accommodate new data."""
        if not self.auto_resize_enabled:
            return

        width_threshold = 130

        for col in range(self.header().count()):
            current_size = self.header().sectionSize(col)
            if current_size <= width_threshold:
                self.resizeColumnToContents(col)
                if self.header().sectionSize(col) < 120:
                    self.header().resizeSection(col, 120)

    def eventFilter(self, obj, event):
        """Handle window resize events."""
        if obj == self.window() and event.type() == QEvent.Type.Resize:
            self.schedule_column_adjustment()
        return super().eventFilter(obj, event)

    def set_root_directory(self, directory):
        """Set the root directory and expand to it."""
        if os.path.exists(directory) and os.access(directory, os.R_OK):
            # Get the model index for the directory
            index = self.file_model.index(directory)
            
            if not index.isValid():
                print(f"[ERROR] Invalid index for directory: {directory}")
                return

            # Set the root index
            self.setRootIndex(index)
            
            # Expand the path to show its contents
            self.expand(index)
            
            # Ensure the directory is visible
            self.scrollTo(index)
            
            # Emit the location changed signal
            self.location_changed.emit(directory)
            
            print(f"[DEBUG] Set root directory to: {directory}")

    def open_folder_in_new_tab(self, folder_path):
        """Open the selected folder in a new nested tab."""
        if not os.path.isdir(folder_path):
            print(f"Error: {folder_path} is not a valid directory.")
            return

        main_window = self.window()
        if hasattr(main_window, 'main_tabs'):
            current_container = main_window.main_tabs.currentWidget()
            if hasattr(current_container, 'tab_manager'):
                current_container.tab_manager.add_new_tab(title=os.path.basename(folder_path), root_path=folder_path)
            else:
                print("Error: TabManager not available.")
        else:
            print("Error: Main tabs not found.")

    def open_folder_in_new_window(self, folder_path):
        """Open the selected folder in a new main tab (new window)."""
        if not os.path.isdir(folder_path):
            print(f"Error: {folder_path} is not a valid directory.")
            return

        main_window = self.window()
        if hasattr(main_window, 'main_tabs'):
            main_window.main_tabs.add_new_main_window_tab(root_path=folder_path)
        else:
            print("Error: Main tabs not found.")

    def show_in_file_explorer(self, folder_path):
        """Open the selected folder in the system's file explorer."""
        if not os.path.exists(folder_path):
            print(f"Error: Path does not exist - {folder_path}")
            return

        import subprocess
        import platform

        try:
            if platform.system() == "Windows":
                subprocess.run(["explorer", folder_path], check=True)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", folder_path], check=True)
            else:  # Linux and others
                subprocess.run(["xdg-open", folder_path], check=True)
        except Exception as e:
            print(f"Error opening file explorer for {folder_path}: {e}")

    def copy_item(self, source_path):
        """Copies file/folder path(s) to the system clipboard."""
        if os.path.exists(source_path):
            # Create a QMimeData object to store file URLs
            mime_data = QMimeData()
            file_url = QUrl.fromLocalFile(source_path)
            mime_data.setUrls([file_url])

            # Place into system clipboard
            clipboard = QApplication.clipboard()
            clipboard.setMimeData(mime_data)

            print(f"Copied: {source_path}")
        else:
            QMessageBox.warning(self, "Error", "The selected file or folder does not exist.")

    def paste_item(self, target_directory):
        """Paste items from the system clipboard into the target directory."""
        if not os.path.isdir(target_directory):
            QMessageBox.warning(self, "Error", "You can only paste into a directory.")
            return

        # Retrieve the data from the QClipboard
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        if not mime_data or not mime_data.hasUrls():
            QMessageBox.warning(self, "Error", "No valid file path(s) in clipboard.")
            return

        from modules.file_operations import copy_item

        # The user may have copied multiple items
        for file_url in mime_data.urls():
            source_path = file_url.toLocalFile()
            if os.path.exists(source_path):
                new_path = copy_item(source_path, target_directory)
                if new_path:
                    print(f"Pasted: {new_path}")
                else:
                    QMessageBox.critical(self, "Error", f"Failed to paste item: {source_path}")
            else:
                QMessageBox.warning(
                    self, "Error",
                    f"Clipboard file/folder does not exist: {source_path}"
                )

        # Optionally clear clipboard if you only want single-use Paste:
        # clipboard.clear()

        # Refresh only the target directory to display the pasted item
        target_index = self.file_model.index(target_directory)
        if target_index.isValid():
            self.expand(target_index)  # Expand the folder
            self.scrollTo(target_index)

    def duplicate_item(self, source_path):
        """Create a duplicate of the selected file or folder in the same directory."""
        if not os.path.exists(source_path):
            QMessageBox.warning(self, "Error", "The selected file or folder does not exist.")
            return

        parent_directory = os.path.dirname(source_path)
        from modules.file_operations import copy_item
        new_path = copy_item(source_path, parent_directory)
        if new_path:
            print(f"Duplicated: {new_path}")
            self.set_root_directory(parent_directory)  # Refresh the view
        else:
            QMessageBox.critical(self, "Error", "Failed to duplicate the item.")

    def create_new_file(self, directory_path):
        """Create a new blank file in the selected directory, integrated with undo/redo."""
        if not os.path.isdir(directory_path):
            QMessageBox.warning(self, "Invalid Target", "Cannot create a file outside a folder.")
            return

        new_file_name, ok = QInputDialog.getText(self, "Add New File", "Enter file name (e.g., new_file.txt):")
        if ok and new_file_name:
            # Push the CreateFileCommand onto the undo stack
            command = CreateFileCommand(self, directory_path, new_file_name)
            undo_manager.push(command)

    def create_new_folder(self, directory_path):
        """Create a new folder in the selected directory, integrated with undo/redo."""
        if not os.path.isdir(directory_path):
            QMessageBox.warning(self, "Invalid Target", "Cannot create a folder outside a directory.")
            return

        new_folder_name, ok = QInputDialog.getText(self, "Add New Folder", "Enter folder name:")
        if ok and new_folder_name:
            command = CreateFolderCommand(self, directory_path, new_folder_name)
            undo_manager.push(command)

    def delete_item_with_undo(self, path):
        """
        Example method you could call from the context menu 
        if you want a minimal delete with possible 'redo only' approach.
        """
        if not os.path.exists(path):
            QMessageBox.warning(self, "Error", f"'{path}' does not exist.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete:\n{path}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            command = DeleteItemCommand(self, path)
            undo_manager.push(command)

    def navigate_and_highlight(self, path):
        """
        Navigate to the given path, expand it if needed, and ensure it is visible in the viewport.
        
        Args:
            path (str): The file system path to navigate to.
        
        Returns:
            bool: True if navigation was successful, False otherwise.
        """
        try:
            abs_path = os.path.abspath(os.path.normpath(path))
            
            if not os.path.exists(abs_path):
                print(f"[ERROR] Cannot navigate to non-existent path: {abs_path}")
                return False

            index = self.file_model.index(abs_path)
            if not index.isValid():
                print(f"[ERROR] Invalid index for path: {abs_path}")
                return False

            print(f"[DEBUG] Navigating and highlighting: {abs_path}")

            try:
                self.setUpdatesEnabled(False)

                # Expand parent directories first
                parent_index = index.parent()
                while parent_index.isValid():
                    self.expand(parent_index)
                    parent_index = parent_index.parent()

                # Select and scroll to the item
                self.setCurrentIndex(index)
                self.scrollTo(index, QTreeView.ScrollHint.PositionAtCenter)

                # Ensure directory expansion
                if os.path.isdir(abs_path):
                    self.expand(index)

                # Schedule multiple adjustments to force scrolling if necessary
                QTimer.singleShot(100, lambda: self.scrollTo(index, QTreeView.ScrollHint.PositionAtCenter))
                QTimer.singleShot(300, lambda: self.scrollTo(index, QTreeView.ScrollHint.PositionAtCenter))
                QTimer.singleShot(600, lambda: self.scrollTo(index, QTreeView.ScrollHint.PositionAtCenter))

            finally:
                self.setUpdatesEnabled(True)
                self.viewport().update()

            print(f"✅ Successfully navigated and highlighted: {abs_path}")
            return True

        except Exception as e:
            print(f"[ERROR] Exception while navigating: {str(e)}")
            return False

    def expand_to_path(self, path):
        """
        Expand all parent directories leading to the given path and ensure visibility.
        
        Args:
            path (str): The file system path to expand to
            
        Returns:
            bool: True if expansion was successful, False otherwise
        """
        try:
            # Convert path to absolute and normalize
            abs_path = os.path.abspath(os.path.normpath(path))
            
            if not os.path.exists(abs_path):
                print(f"[ERROR] Cannot expand non-existent path: {abs_path}")
                return False

            index = self.file_model.index(abs_path)
            if not index.isValid():
                print(f"[ERROR] Invalid index for path: {abs_path}")
                return False

            print(f"[DEBUG] Expanding path: {abs_path}")

            try:
                # Disable updates temporarily for better performance
                self.setUpdatesEnabled(False)
                
                # Expand all parent directories first
                parent_index = index.parent()
                expanded_count = 0
                while parent_index.isValid():
                    if not self.isExpanded(parent_index):
                        self.expand(parent_index)
                        expanded_count += 1
                    parent_index = parent_index.parent()

                # Expand the selected folder itself if it's a directory
                if os.path.isdir(abs_path) and not self.isExpanded(index):
                    self.expand(index)
                    expanded_count += 1

                # Only scroll if we actually expanded something
                if expanded_count > 0:
                    self.scrollTo(index, QTreeView.ScrollHint.PositionAtCenter)
                    
                    # Schedule a column adjustment if we expanded anything
                    if self.auto_resize_enabled:
                        self.schedule_column_adjustment()

            finally:
                # Re-enable updates and force refresh
                self.setUpdatesEnabled(True)
                self.viewport().update()

            return True

        except Exception as e:
            print(f"[ERROR] Exception while expanding path: {str(e)}")
            return False
    
    def mousePressEvent(self, event):
        """
        Handle mouse press events for selection, drag initiation,
        AND click-on-empty-space unselection.
        """
        # 1) Check if user clicked empty space:
        index = self.indexAt(event.pos())
        if not index.isValid():
            # If so, clear any existing selection
            self.clearSelection()

        # 2) Continue with your existing logic
        if event.button() == Qt.MouseButton.LeftButton:
            # Store the start position for potential drag operation
            self.drag_start_position = event.pos()

        # 3) Let QTreeView handle default selection, focus, etc.
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse movement for drag operations."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return

        # Only initiate drag if we have a start position and user has moved enough
        if self.drag_start_position is not None:
            distance = (event.pos() - self.drag_start_position).manhattanLength()
            if distance >= QApplication.startDragDistance():
                # Gather selected indexes
                selected_indexes = self.selectedIndexes()
                if not selected_indexes:
                    return

                # Build the drag object
                drag = QDrag(self)
                mime_data = QMimeData()

                # Collect URLs for all selected files (first column only)
                urls = []
                processed_paths = set()
                for idx in selected_indexes:
                    if idx.column() == 0:  # Only the first column
                        file_path = self.file_model.filePath(idx)
                        if file_path and file_path not in processed_paths:
                            urls.append(QUrl.fromLocalFile(file_path))
                            processed_paths.add(file_path)

                if urls:
                    mime_data.setUrls(urls)
                    drag.setMimeData(mime_data)

                    # Execute drag operation
                    drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

                # Reset drag start position
                self.drag_start_position = None
                return

        # Let QTreeView handle selection
        super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = None
        super().mouseReleaseEvent(event)


    def dragEnterEvent(self, event):
        """
        Accept drag from local files/folders (hasUrls) 
        or from Outlook attachments (FileGroupDescriptor).
        """
        # 1) Local file/folder
        if event.mimeData().hasUrls():
            # Check if all are local
            all_local = all(url.isLocalFile() for url in event.mimeData().urls())
            if all_local:
                event.acceptProposedAction()
                return

        # 2) Outlook attachments
        if event.mimeData().hasFormat("FileGroupDescriptor") or \
        event.mimeData().hasFormat("FileGroupDescriptorW"):
            event.acceptProposedAction()
            return

        # Otherwise ignore
        event.ignore()


    def dragMoveEvent(self, event):
        """
        While dragging over the tree, show a 'move' cursor 
        if we're hovering a valid folder.
        """
        drop_index = self.indexAt(event.position().toPoint())
        if not drop_index.isValid():
            self.clearSelection()
            self.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
            event.ignore()
            return

        target_path = self.file_model.filePath(drop_index)
        if os.path.isdir(target_path):
            self.setCursor(QCursor(Qt.CursorShape.DragMoveCursor))
            self.setCurrentIndex(drop_index)
            event.acceptProposedAction()
        else:
            self.clearSelection()
            self.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
            event.ignore()


    def dropEvent(self, event):
        """
        Distinguish between local file/folder drops or Outlook attachments.
        """
        if not event.mimeData():
            event.ignore()
            return

        self.setUpdatesEnabled(False)
        try:
            # If local URLs
            if event.mimeData().hasUrls():
                self._handle_local_file_drop(event)
                return

            # If Outlook attachments
            if (event.mimeData().hasFormat("FileGroupDescriptor") or
                event.mimeData().hasFormat("FileGroupDescriptorW")):
                self._handle_outlook_attachments(event)
                return

            # Otherwise ignore
            event.ignore()

        finally:
            self.setUpdatesEnabled(True)
            # Always restore the normal arrow cursor
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)


    def _handle_local_file_drop(self, event):
        """
        Copy or move local files/folders into the dropped directory. 
        Example approach using shutil. 
        (You can adapt to your undo stack or rename logic as needed.)
        """
        drop_index = self.indexAt(event.position().toPoint())
        if not drop_index.isValid():
            event.ignore()
            return

        target_path = self.file_model.filePath(drop_index)
        if not os.path.isdir(target_path):
            QMessageBox.warning(self, "Invalid Target", "Drop target must be a directory.")
            event.ignore()
            return

        import shutil

        # We'll do a naive "move" by default. 
        # (You can check if Ctrl is pressed for copy, etc.)
        errors = []
        for url in event.mimeData().urls():
            source_path = url.toLocalFile()
            if not os.path.exists(source_path):
                errors.append(source_path)
                continue

            dest = os.path.join(target_path, os.path.basename(source_path))
            try:
                shutil.move(source_path, dest)
                print(f"Moved {source_path} -> {dest}")
            except Exception as e:
                errors.append(f"{source_path} => {str(e)}")

        if errors:
            QMessageBox.warning(self, "Some files failed", "\n".join(errors))

        event.acceptProposedAction()

        # Refresh the target directory so new items appear
        self.file_model.setRootPath(target_path)
        # or if you prefer:
        # self.set_root_directory(target_path)


    def _handle_outlook_attachments(self, event):
        """
        Parse the FileGroupDescriptor(W) + FileContents(0..n) 
        to retrieve each attachment and save it to the drop target folder.
        """
        drop_index = self.indexAt(event.position().toPoint())
        if not drop_index.isValid():
            event.ignore()
            return

        target_path = self.file_model.filePath(drop_index)
        if not os.path.isdir(target_path):
            QMessageBox.warning(self, "Invalid Target", "Drop target must be a directory.")
            event.ignore()
            return

        mime_data = event.mimeData()

        # 1) Read the descriptor. Could be "FileGroupDescriptor" or "FileGroupDescriptorW"
        descriptor_format = None
        for fmt in ("FileGroupDescriptorW", "FileGroupDescriptor"):
            full_fmt = f'application/x-qt-windows-mime;value="{fmt}"'
            if mime_data.hasFormat(full_fmt):
                descriptor_format = full_fmt
                break

        if not descriptor_format:
            QMessageBox.critical(self, "Error", "No valid FileGroupDescriptor found in Outlook data.")
            event.ignore()
            return

        descriptor_bytes = mime_data.data(descriptor_format)
        filenames = self._parse_file_group_descriptor(descriptor_bytes, wide=("W" in descriptor_format))

        if not filenames:
            QMessageBox.warning(self, "No Attachments", "Could not parse any filenames from Outlook descriptor.")
            event.ignore()
            return

        # 2) For each filename, read the actual file content from "FileContents" + index
        for i, filename in enumerate(filenames):
            # Outlook often uses "FileContents" for the first, "FileContents0", "FileContents1", ...
            # There's no official standard: test with your version of Outlook. 
            # We'll try both "FileContents" (if i=0) and "FileContentsX" for i>0.
            possible_formats = []
            if i == 0:
                possible_formats.append('application/x-qt-windows-mime;value="FileContents"')
            # Also try "FileContents{i}" just in case
            possible_formats.append(f'application/x-qt-windows-mime;value="FileContents{i}"')

            file_bytes = None
            for ffmt in possible_formats:
                if mime_data.hasFormat(ffmt):
                    file_bytes = mime_data.data(ffmt)
                    if file_bytes:
                        break

            if not file_bytes:
                print(f"No content found for: {filename}")
                continue

            # 3) Write to disk
            safe_filename = filename.strip().replace(":", "_").replace("\\", "_").replace("/", "_")
            dest_path = os.path.join(target_path, safe_filename)
            try:
                with open(dest_path, "wb") as outf:
                    outf.write(file_bytes)
                print(f"Saved Outlook attachment => {dest_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to write {safe_filename}:\n{e}")

        event.acceptProposedAction()

        # Refresh
        self.file_model.setRootPath(target_path)


    def _parse_file_group_descriptor(self, descriptor_bytes, wide=False):
        """
        Extract filenames from FileGroupDescriptor or FileGroupDescriptorW data.
        * wide=True indicates 'FileGroupDescriptorW', which is UTF-16.
        * wide=False is old ANSI/ASCII format.

        Return a list of string filenames.
        """
        import struct

        data = bytes(descriptor_bytes)
        # The first 4 bytes are the number of file descriptors
        count, = struct.unpack("<I", data[0:4])

        # Offsets differ slightly between W and non-W versions,
        # but typically the first descriptor is at offset 76 for W.
        # You can adjust if needed based on doc or experimentation.
        # Each descriptor is 560 bytes in W, 512 in ANSI.
        file_descriptors = []
        offset = 76 if wide else 72
        step = 560 if wide else 512

        for _ in range(count):
            chunk = data[offset:offset+step]
            offset += step

            # The filename is at chunk[0:520] for W, or chunk[0:260] for ANSI, etc.
            # We'll decode the chunk accordingly
            if wide:
                raw_name = chunk[0:520]  # 260 UTF-16 chars
                filename = raw_name.decode("utf-16", errors="ignore").split("\x00", 1)[0]
            else:
                raw_name = chunk[0:260]
                filename = raw_name.decode("ascii", errors="ignore").split("\x00", 1)[0]

            file_descriptors.append(filename.strip())

        return file_descriptors


    def dragLeaveEvent(self, event):
        """Handle drag leave events and reset the cursor."""
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))  # Reset to default cursor
        event.accept()

    def handle_standard_file_drop(self, event):
        """Handle standard file URLs dropped into the app."""
        drop_index = self.indexAt(event.position().toPoint())
        target_path = self.file_model.filePath(drop_index)

        # Validate the drop target
        if not os.path.isdir(target_path):
            QMessageBox.warning(self, "Invalid Target", "You can only drop files or folders into directories.")
            event.ignore()
            return

        for url in event.mimeData().urls():
            source_path = url.toLocalFile()
            if os.path.exists(source_path):
                try:
                    # Determine if the operation is a copy or move
                    if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
                        # Perform a copy operation
                        if os.path.isdir(source_path):
                            dest_path = os.path.join(target_path, os.path.basename(source_path))
                            if os.path.exists(dest_path):
                                QMessageBox.warning(self, "Conflict", f"Folder '{os.path.basename(source_path)}' already exists in the target directory.")
                                continue
                            shutil.copytree(source_path, dest_path)
                            print(f"Copied folder {source_path} to {dest_path}")
                        else:
                            dest_path = os.path.join(target_path, os.path.basename(source_path))
                            if os.path.exists(dest_path):
                                QMessageBox.warning(self, "Conflict", f"File '{os.path.basename(source_path)}' already exists in the target directory.")
                                continue
                            shutil.copy2(source_path, dest_path)
                            print(f"Copied file {source_path} to {dest_path}")
                    else:
                        # Perform a move operation
                        if os.path.isdir(source_path):
                            dest_path = os.path.join(target_path, os.path.basename(source_path))
                            if os.path.exists(dest_path):
                                QMessageBox.warning(self, "Conflict", f"Folder '{os.path.basename(source_path)}' already exists in the target directory.")
                                continue
                            shutil.move(source_path, dest_path)
                            print(f"Moved folder {source_path} to {dest_path}")
                        else:
                            dest_path = os.path.join(target_path, os.path.basename(source_path))
                            if os.path.exists(dest_path):
                                QMessageBox.warning(self, "Conflict", f"File '{os.path.basename(source_path)}' already exists in the target directory.")
                                continue
                            shutil.move(source_path, dest_path)
                            print(f"Moved file {source_path} to {dest_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to process file or folder: {source_path}\nError: {e}")
            else:
                QMessageBox.warning(self, "File Not Found", f"The file or folder '{source_path}' does not exist.")
        event.acceptProposedAction()

    def handle_outlook_attachments(self, event):
        """Handle Outlook file attachments."""
        import tempfile

        drop_index = self.indexAt(event.position().toPoint())
        target_path = self.file_model.filePath(drop_index)

        if not os.path.isdir(target_path):
            QMessageBox.warning(self, "Invalid Target", "You can only drop files into folders.")
            event.ignore()
            return

        mime_data = event.mimeData()

        # Ensure we have the necessary MIME formats
        if not mime_data.hasFormat('application/x-qt-windows-mime;value="FileGroupDescriptorW"') or \
        not mime_data.hasFormat('application/x-qt-windows-mime;value="FileContents"'):
            QMessageBox.critical(self, "Error", "Required MIME formats not found.")
            return

        # Extract file descriptors
        file_descriptor = mime_data.data('application/x-qt-windows-mime;value="FileGroupDescriptorW"')
        filenames = self.parse_file_group_descriptor_w(file_descriptor)

        for i, filename in enumerate(filenames):
            # Get the file content
            file_content_format = f"application/x-qt-windows-mime;value=\"FileContents\""
            if not mime_data.hasFormat(file_content_format):
                QMessageBox.critical(self, "Error", f"No content found for file: {filename}")
                continue

            file_data = mime_data.data(file_content_format)
            if not file_data:
                QMessageBox.critical(self, "Error", f"FileContents data empty for: {filename}")
                continue

            temp_path = os.path.join(tempfile.gettempdir(), filename)

            try:
                # Convert QByteArray to bytes
                file_data_bytes = bytes(file_data)

                # Debug: Print length of file content
                print(f"FileContents length for {filename}: {len(file_data_bytes)}")

                # Write the content to a temporary file
                with open(temp_path, "wb") as temp_file:
                    temp_file.write(file_data_bytes)

                # Move the file to the target directory
                shutil.move(temp_path, os.path.join(target_path, filename))
                print(f"Moved {filename} to {target_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to process file: {filename}\n{e}")

        event.acceptProposedAction()

    def parse_file_group_descriptor_w(self, descriptor):
        """Parse the FileGroupDescriptorW to extract filenames."""
        import struct

        filenames = []
        descriptor_bytes = bytes(descriptor)  # Convert QByteArray to bytes
        descriptor_length = len(descriptor_bytes)
        offset = 76  # File descriptors start at offset 76

        while offset < descriptor_length:
            # Extract the Unicode filename (null-terminated UTF-16)
            filename_bytes = descriptor_bytes[offset:offset + 520]  # 520 bytes for UTF-16 (260 characters)
            filename = filename_bytes.decode("utf-16", errors="ignore").split("\x00", 1)[0]  # Decode UTF-16
            if filename:
                filenames.append(filename)
            offset += 560  # Each descriptor is 560 bytes
        return filenames

    def preview_pdf(self, file_path):
        """
        Display a PDF file with scrolling, click-drag, and Ctrl+Zoom without freezing the main app,
        now using an LRU-style cache and explicitly closing the PDF on dialog close.
        """
        if not file_path.endswith(".pdf"):
            QMessageBox.warning(self, "Invalid File", "Only PDF files can be previewed.")
            return

        try:
            import fitz  # PyMuPDF
            from collections import OrderedDict  # For LRU caching

            class PDFPreviewDialog(QDialog):
                MAX_CACHED_PAGES = 5  # Limit how many pages we keep in memory

                def __init__(self, file_path, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("PDF Preview")
                    self.setMinimumSize(900, 1000)

                    # Load PDF
                    self.doc = fitz.open(file_path)
                    self.current_page = 0
                    self.zoom_level = 1.0  # Default zoom level

                    # LRU cache (page_index -> QPixmap)
                    # We store pages in an OrderedDict so we can pop the oldest when full
                    self.page_cache = OrderedDict()

                    # Scroll Area
                    self.scroll_area = QScrollArea()
                    self.scroll_area.setWidgetResizable(True)

                    # QLabel for displaying PDF page
                    self.image_label = QLabel()
                    self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Turn off scaledContents to avoid “double scaling”
                    self.image_label.setScaledContents(False)
                    self.scroll_area.setWidget(self.image_label)

                    # Navigation Buttons
                    self.prev_button = QPushButton("◀ Previous")
                    self.prev_button.clicked.connect(self.prev_page)

                    self.next_button = QPushButton("Next ▶")
                    self.next_button.clicked.connect(self.next_page)

                    # Zoom Controls
                    self.zoom_in_button = QPushButton("➕ Zoom In")
                    self.zoom_in_button.clicked.connect(self.zoom_in)

                    self.zoom_out_button = QPushButton("➖ Zoom Out")
                    self.zoom_out_button.clicked.connect(self.zoom_out)

                    self.reset_zoom_button = QPushButton("🔄 Reset Zoom")
                    self.reset_zoom_button.clicked.connect(self.reset_zoom)

                    self.fit_to_window_button = QPushButton("🖥️ Fit to Window")
                    self.fit_to_window_button.clicked.connect(self.fit_to_window)

                    # Fullscreen Toggle
                    self.fullscreen_button = QPushButton("⛶ Fullscreen")
                    self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

                    # Page Indicator
                    self.page_label = QLabel(f"Page 1 of {len(self.doc)}")

                    # Layout Setup
                    nav_layout = QHBoxLayout()
                    nav_layout.addWidget(self.prev_button)
                    nav_layout.addWidget(self.page_label, alignment=Qt.AlignmentFlag.AlignCenter)
                    nav_layout.addWidget(self.next_button)

                    zoom_layout = QHBoxLayout()
                    zoom_layout.addWidget(self.zoom_out_button)
                    zoom_layout.addWidget(self.zoom_in_button)
                    zoom_layout.addWidget(self.reset_zoom_button)
                    zoom_layout.addWidget(self.fit_to_window_button)
                    zoom_layout.addWidget(self.fullscreen_button)

                    main_layout = QVBoxLayout(self)
                    main_layout.addWidget(self.scroll_area)
                    main_layout.addLayout(nav_layout)
                    main_layout.addLayout(zoom_layout)

                    self.setLayout(main_layout)

                    # Mouse interaction tracking for dragging
                    self.is_dragging = False
                    self.last_mouse_position = None

                    self.image_label.setMouseTracking(True)
                    self.image_label.installEventFilter(self)
                    self.scroll_area.viewport().installEventFilter(self)

                    # Initial page display
                    self.update_page()

                def closeEvent(self, event):
                    """Close the PDF doc to free resources immediately."""
                    self.doc.close()
                    super().closeEvent(event)

                def update_page(self):
                    """Render the current page with the current zoom level, using an LRU cache."""
                    if self.current_page in self.page_cache:
                        pixmap = self.page_cache[self.current_page]
                        # Mark this page as most recently used
                        self.page_cache.move_to_end(self.current_page)
                    else:
                        # Render fresh
                        page = self.doc[self.current_page]
                        pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom_level, self.zoom_level))
                        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                        pixmap = QPixmap.fromImage(img)

                        # Insert into cache, then pop oldest if we're at capacity
                        self.page_cache[self.current_page] = pixmap
                        self.page_cache.move_to_end(self.current_page)
                        if len(self.page_cache) > self.MAX_CACHED_PAGES:
                            self.page_cache.popitem(last=False)  # Remove the oldest page

                    self.image_label.setPixmap(pixmap)
                    self.image_label.adjustSize()
                    self.page_label.setText(f"Page {self.current_page + 1} of {len(self.doc)}")

                def next_page(self):
                    if self.current_page < len(self.doc) - 1:
                        self.current_page += 1
                        self.update_page()

                def prev_page(self):
                    if self.current_page > 0:
                        self.current_page -= 1
                        self.update_page()

                def zoom_in(self):
                    self.zoom_level *= 1.2
                    # Clear entire cache because old pages were rendered at previous zoom
                    self.page_cache.clear()
                    self.update_page()

                def zoom_out(self):
                    self.zoom_level /= 1.2
                    self.page_cache.clear()
                    self.update_page()

                def reset_zoom(self):
                    self.zoom_level = 1.0
                    self.page_cache.clear()
                    self.update_page()

                def fit_to_window(self):
                    """Adjust the PDF preview to fit inside the window."""
                    if self.image_label.pixmap():
                        available_width = self.scroll_area.viewport().width()
                        available_height = self.scroll_area.viewport().height()
                        pixmap = self.image_label.pixmap()
                        if pixmap.width() > 0 and pixmap.height() > 0:
                            self.zoom_level = min(
                                available_width / pixmap.width(),
                                available_height / pixmap.height()
                            )
                            self.page_cache.clear()
                            self.update_page()

                def toggle_fullscreen(self):
                    if self.isFullScreen():
                        self.showNormal()
                        self.fullscreen_button.setText("⛶ Fullscreen")
                    else:
                        self.showFullScreen()
                        self.fullscreen_button.setText("❌ Exit Fullscreen")

                def eventFilter(self, obj, event):
                    """Handle mouse wheel scrolling, dragging, and Ctrl+Zoom."""
                    if event.type() == QEvent.Type.Wheel:
                        modifiers = QApplication.keyboardModifiers()
                        if modifiers == Qt.KeyboardModifier.ControlModifier:
                            # Ctrl + Mouse Wheel for zoom
                            if event.angleDelta().y() > 0:
                                self.zoom_in()
                            else:
                                self.zoom_out()
                            return True
                        else:
                            # Regular Mouse Wheel => next/previous page
                            if event.angleDelta().y() > 0:
                                self.prev_page()
                            else:
                                self.next_page()
                            return True

                    elif event.type() == QEvent.Type.MouseButtonPress:
                        # Ctrl + Left-click => drag to pan
                        if (event.button() == Qt.MouseButton.LeftButton
                                and (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)):
                            self.is_dragging = True
                            self.last_mouse_position = event.position().toPoint()
                            self.image_label.setCursor(Qt.CursorShape.ClosedHandCursor)
                            return True

                    elif event.type() == QEvent.Type.MouseMove and self.is_dragging:
                        if self.last_mouse_position:
                            delta = event.position().toPoint() - self.last_mouse_position
                            if abs(delta.x()) > 1 or abs(delta.y()) > 1:
                                self.last_mouse_position = event.position().toPoint()
                                # Smooth scrolling to reduce jitter
                                self.scroll_area.horizontalScrollBar().setValue(
                                    self.scroll_area.horizontalScrollBar().value() - int(delta.x() * 0.9)
                                )
                                self.scroll_area.verticalScrollBar().setValue(
                                    self.scroll_area.verticalScrollBar().value() - int(delta.y() * 0.9)
                                )
                        return True

                    elif event.type() == QEvent.Type.MouseButtonRelease:
                        if event.button() == Qt.MouseButton.LeftButton:
                            self.is_dragging = False
                            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)
                            return True

                    return super().eventFilter(obj, event)

            # Store a reference so the dialog isn't garbage-collected
            self.pdf_dialog = PDFPreviewDialog(file_path)
            self.pdf_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self.pdf_dialog.show()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to preview PDF: {str(e)}")

    def preview_image(self, file_path):
        """
        Display an image (jpg, png, svg, heic, etc.) with scrolling, Ctrl+zoom,
        drag-pan, LRU caching of zoom levels, fullscreen toggle, and rotation.
        """
        # Basic extension check: you can do more robust checks or rely on Qt to handle it
        SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".svg", ".heic")
        _, ext = os.path.splitext(file_path.lower())
        if ext not in SUPPORTED_EXTS:
            QMessageBox.warning(self, "Invalid File", f"Unsupported or unknown image format: {ext}")
            return

        try:
            from collections import OrderedDict

            class ImagePreviewDialog(QDialog):
                MAX_CACHED_ZOOMS = 5  # LRU cache of scaled images

                def __init__(self, file_path, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("Image Preview")
                    self.setMinimumSize(900, 1000)

                    self.original_image = QImage(file_path)
                    if self.original_image.isNull():
                        raise ValueError(f"Could not load image: {file_path}")

                    # Track both zoom and rotation
                    self.zoom_level = 1.0
                    self.current_rotation = 0  # 0, 90, 180, 270, etc.

                    # Cache: key will be (zoom_level, current_rotation)
                    self.scaled_cache = OrderedDict()

                    # Scroll area + label
                    self.scroll_area = QScrollArea()
                    self.scroll_area.setWidgetResizable(True)

                    self.image_label = QLabel()
                    self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Turn off scaledContents to avoid double-scaling
                    self.image_label.setScaledContents(False)
                    self.scroll_area.setWidget(self.image_label)

                    # Rotate buttons
                    self.rotate_left_button = QPushButton("⟲ Rotate Left")
                    self.rotate_left_button.clicked.connect(self.rotate_left)

                    self.rotate_right_button = QPushButton("⟳ Rotate Right")
                    self.rotate_right_button.clicked.connect(self.rotate_right)

                    # Zoom buttons
                    self.zoom_in_button = QPushButton("➕ Zoom In")
                    self.zoom_in_button.clicked.connect(self.zoom_in)

                    self.zoom_out_button = QPushButton("➖ Zoom Out")
                    self.zoom_out_button.clicked.connect(self.zoom_out)

                    self.reset_zoom_button = QPushButton("🔄 Reset Zoom")
                    self.reset_zoom_button.clicked.connect(self.reset_zoom)

                    self.fit_to_window_button = QPushButton("🖥️ Fit to Window")
                    self.fit_to_window_button.clicked.connect(self.fit_to_window)

                    self.fullscreen_button = QPushButton("⛶ Fullscreen")
                    self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

                    # Layout for buttons
                    button_layout = QHBoxLayout()
                    button_layout.addWidget(self.rotate_left_button)
                    button_layout.addWidget(self.rotate_right_button)
                    button_layout.addWidget(self.zoom_out_button)
                    button_layout.addWidget(self.zoom_in_button)
                    button_layout.addWidget(self.reset_zoom_button)
                    button_layout.addWidget(self.fit_to_window_button)
                    button_layout.addWidget(self.fullscreen_button)

                    # Main layout
                    main_layout = QVBoxLayout(self)
                    main_layout.addWidget(self.scroll_area)
                    main_layout.addLayout(button_layout)
                    self.setLayout(main_layout)

                    # For drag-based panning
                    self.is_dragging = False
                    self.last_mouse_position = None

                    # Install event filters for zoom/pan
                    self.image_label.setMouseTracking(True)
                    self.image_label.installEventFilter(self)
                    self.scroll_area.viewport().installEventFilter(self)

                    # Initial render (zoom = 1.0)
                    self.update_image()
                    # Automatically fit if the image is large
                    self.fit_to_window()

                def closeEvent(self, event):
                    # Clear the cache if desired
                    self.scaled_cache.clear()
                    super().closeEvent(event)

                def rotate_left(self):
                    self.current_rotation = (self.current_rotation - 90) % 360
                    self.scaled_cache.clear()
                    self.update_image()

                def rotate_right(self):
                    self.current_rotation = (self.current_rotation + 90) % 360
                    self.scaled_cache.clear()
                    self.update_image()

                def update_image(self):
                    # Cache key: (zoom_level, current_rotation)
                    cache_key = (self.zoom_level, self.current_rotation)

                    if cache_key in self.scaled_cache:
                        pixmap = self.scaled_cache[cache_key]
                        self.scaled_cache.move_to_end(cache_key)
                    else:
                        # Apply rotation first
                        transform = QTransform().rotate(self.current_rotation)
                        rotated_image = self.original_image.transformed(
                            transform, Qt.TransformationMode.SmoothTransformation
                        )

                        # Then scale according to zoom_level
                        new_w = int(rotated_image.width() * self.zoom_level)
                        new_h = int(rotated_image.height() * self.zoom_level)
                        new_w = max(1, new_w)
                        new_h = max(1, new_h)

                        scaled_img = rotated_image.scaled(
                            new_w, new_h, Qt.AspectRatioMode.KeepAspectRatio
                        )
                        pixmap = QPixmap.fromImage(scaled_img)

                        # Store in cache, remove oldest if needed
                        self.scaled_cache[cache_key] = pixmap
                        self.scaled_cache.move_to_end(cache_key)
                        if len(self.scaled_cache) > self.MAX_CACHED_ZOOMS:
                            self.scaled_cache.popitem(last=False)

                    self.image_label.setPixmap(pixmap)
                    self.image_label.adjustSize()

                def zoom_in(self):
                    self.zoom_level *= 1.2
                    self.update_image()

                def zoom_out(self):
                    self.zoom_level /= 1.2
                    if self.zoom_level <= 0:
                        self.zoom_level = 0.1
                    self.update_image()

                def reset_zoom(self):
                    self.zoom_level = 1.0
                    self.update_image()

                def fit_to_window(self):
                    if not self.original_image.isNull():
                        available_w = self.scroll_area.viewport().width()
                        available_h = self.scroll_area.viewport().height()
                        if self.original_image.width() > 0 and self.original_image.height() > 0:
                            scale_w = available_w / self.original_image.width()
                            scale_h = available_h / self.original_image.height()
                            self.zoom_level = max(0.01, min(scale_w, scale_h))
                            self.update_image()

                def toggle_fullscreen(self):
                    if self.isFullScreen():
                        self.showNormal()
                        self.fullscreen_button.setText("⛶ Fullscreen")
                    else:
                        self.showFullScreen()
                        self.fullscreen_button.setText("❌ Exit Fullscreen")

                def eventFilter(self, obj, event):
                    if event.type() == QEvent.Type.Wheel:
                        mods = QApplication.keyboardModifiers()
                        if mods == Qt.KeyboardModifier.ControlModifier:
                            # Ctrl + wheel => zoom
                            if event.angleDelta().y() > 0:
                                self.zoom_in()
                            else:
                                self.zoom_out()
                            return True
                        else:
                            # Otherwise let QScrollArea handle vertical scrolling
                            pass

                    elif event.type() == QEvent.Type.MouseButtonPress:
                        # Ctrl+Left = drag to pan
                        if (event.button() == Qt.MouseButton.LeftButton
                                and (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)):
                            self.is_dragging = True
                            self.last_mouse_position = event.position().toPoint()
                            self.image_label.setCursor(Qt.CursorShape.ClosedHandCursor)
                            return True

                    elif event.type() == QEvent.Type.MouseMove and self.is_dragging:
                        if self.last_mouse_position:
                            delta = event.position().toPoint() - self.last_mouse_position
                            if abs(delta.x()) > 1 or abs(delta.y()) > 1:
                                self.last_mouse_position = event.position().toPoint()
                                self.scroll_area.horizontalScrollBar().setValue(
                                    self.scroll_area.horizontalScrollBar().value() - int(delta.x() * 0.9)
                                )
                                self.scroll_area.verticalScrollBar().setValue(
                                    self.scroll_area.verticalScrollBar().value() - int(delta.y() * 0.9)
                                )
                            return True

                    elif event.type() == QEvent.Type.MouseButtonRelease:
                        if event.button() == Qt.MouseButton.LeftButton:
                            self.is_dragging = False
                            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)
                            return True

                    return super().eventFilter(obj, event)

            # Create and show the dialog
            self.img_dialog = ImagePreviewDialog(file_path)
            self.img_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self.img_dialog.show()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to preview image: {str(e)}")
