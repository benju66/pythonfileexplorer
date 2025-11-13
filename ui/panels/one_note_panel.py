"""
enhanced_one_note_panel.py

An enhanced OneNote-like panel with dockable functionality for your PyQt application.
It allows you to organize notes into a structured hierarchy:
- Notebooks (top-level)
- Sections (under notebooks)
- Pages (under sections)

Key Features:
1. Nested lists with Tab/Shift+Tab indent functionality
2. Enhanced rich text formatting and table support
3. Basic search across all notebooks
4. Quick notes functionality
5. Hierarchical tree with proper icons
6. Drag-and-drop reordering respecting hierarchy rules
7. Auto-save functionality
8. Smart keyboard shortcuts
"""

import json
import os
import re
from datetime import datetime
import time
from typing import List, Dict, Optional, Tuple, Any

from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QToolBar, QTextEdit, QMenu,
    QInputDialog, QMessageBox, QFontComboBox, QComboBox, QColorDialog,
    QLineEdit, QDialog, QDialogButtonBox, QLabel, QSpinBox,
    QDockWidget, QWidget, QSplitter, QHBoxLayout, QVBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QStyle, QApplication, QFormLayout
)
from PyQt6.QtCore import (
    Qt, QPoint, QTimer, QSize, QDateTime, 
    pyqtSignal
)
from PyQt6.QtGui import (
    QAction, QIcon, QTextCursor, QTextCharFormat, QFont,
    QTextListFormat, QTextTableFormat, QTextFrameFormat, QTextBlockFormat, QBrush, QColor,
    QKeySequence, QShortcut
)

# Custom roles to identify note items and store data
NOTE_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1   # notebook/section/page
PAGE_CONTENT_ROLE = Qt.ItemDataRole.UserRole + 2  # HTML content of page
EXPANDED_ROLE = Qt.ItemDataRole.UserRole + 3    # Expanded state info
CREATED_ROLE = Qt.ItemDataRole.UserRole + 4     # Creation timestamp
MODIFIED_ROLE = Qt.ItemDataRole.UserRole + 5    # Last modification timestamp
UUID_ROLE = Qt.ItemDataRole.UserRole + 6        # Unique identifier


class DraggableTreeWidget(QTreeWidget):
    """
    An enhanced QTreeWidget that supports hierarchy-aware drag-and-drop 
    for reorganizing items with proper validation of allowed moves.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setIconSize(QSize(16, 16))
        
        # Load icons from a resource directory or embedded resources
        self.icons = {}
        self._load_icons()
    
    def _load_icons(self):
        """Load icons for the tree items or use system icons as fallbacks"""
        # Using system icons as an example - you'd replace with your own icons
        style = QApplication.style()
        self.icons = {
            "notebook": style.standardIcon(QStyle.StandardPixmap.SP_DirIcon),
            "section": style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
            "page": style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        }
    
    def dropEvent(self, event):
        """
        Handle drop event with hierarchy validation to ensure only valid moves.
        For example, pages can only go into sections, not directly into notebooks.
        """
        if not event.source():
            event.ignore()
            return
            
        drop_pos = event.pos()
        target_item = self.itemAt(drop_pos)
        dragged_items = self.selectedItems()
        
        if not target_item or not dragged_items:
            event.ignore()
            return
            
        # Check if the move is valid by validating hierarchy rules
        target_type = target_item.data(0, NOTE_TYPE_ROLE)
        
        for item in dragged_items:
            item_type = item.data(0, NOTE_TYPE_ROLE)
            
            # Validate move based on hierarchy rules
            if not self._validate_hierarchy_move(item_type, target_type):
                event.ignore()
                return
                
        # If we've reached here, let the parent class handle the move
        super().dropEvent(event)
        
        # Notify the parent (OneNotePanel) to re-save the new order
        if hasattr(self.parent(), "on_items_reorganized"):
            self.parent().on_items_reorganized()
    
    def _validate_hierarchy_move(self, source_type, target_type) -> bool:
        """
        Validate if an item can be moved to another based on hierarchy rules
        
        Rules:
        - Notebooks must remain at top level
        - Sections can go inside notebooks
        - Pages can only go inside sections
        """
        valid_targets = {
            "notebook": None,  # Notebooks can only be at top level
            "section": ["notebook"],  # Sections can go inside notebooks
            "page": ["section"]  # Pages can only go inside sections
        }
        
        if source_type not in valid_targets:
            return False
            
        # If the item can't be nested (like notebooks)
        if valid_targets[source_type] is None:
            return False
            
        return target_type in valid_targets[source_type]


class NoteTextEdit(QTextEdit):
    """
    Enhanced QTextEdit that handles:
    1) Tab/Shift+Tab indent/outdent in bulleted or numbered lists
    2) Always pastes as plain text
    3) Advanced list formatting with multiple list types
    4) Automatic formatting features like converting URLs to links
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Track link detection
        self.auto_link_detection = True
        
        # Set up rich text capabilities
        self.setup_text_edit()
    
    def setup_text_edit(self):
        """Configure the text editor for rich text editing"""
        font = QFont("Segoe UI", 11)
        self.setFont(font)
        
        # Set up reasonable default margins
        default_fmt = QTextBlockFormat()
        default_fmt.setTopMargin(4)
        default_fmt.setBottomMargin(4)
        
        # Misc. settings
        self.setTabChangesFocus(False)
        self.setAcceptRichText(True)
        self.setAutoFormatting(QTextEdit.AutoFormattingFlag.AutoAll)
        
    def paste_plain_text(self):
        """Paste clipboard text as plain text without formatting"""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            cursor = self.textCursor()
            cursor.insertText(text)
            
            # If auto-link detection is on, convert any URLs to links
            if self.auto_link_detection:
                self._detect_links_in_selection(cursor)
    
    def _detect_links_in_selection(self, cursor):
        """
        Detect URLs in the pasted text and convert them to hyperlinks
        """
        url_pattern = r'(https?://[^\s]+)'
        
        cursor.setPosition(cursor.selectionStart())
        cursor.setPosition(cursor.selectionEnd(), QTextCursor.MoveMode.KeepAnchor)
        text = cursor.selectedText()
        
        # Find URLs
        urls = re.finditer(url_pattern, text)
        for url_match in urls:
            url = url_match.group(0)
            
            # Create a cursor for this specific URL
            url_cursor = QTextCursor(self.document())
            start_pos = cursor.selectionStart() + url_match.start(0)
            end_pos = cursor.selectionStart() + url_match.end(0)
            
            url_cursor.setPosition(start_pos)
            url_cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
            
            # Apply link format
            link_format = QTextCharFormat()
            link_format.setAnchor(True)
            link_format.setAnchorHref(url)
            link_format.setForeground(QColor("blue"))
            link_format.setFontUnderline(True)
            
            url_cursor.mergeCharFormat(link_format)
    
    def keyPressEvent(self, event):
        """
        Enhanced key press handler with support for:
        - Plain text paste (Ctrl+V)
        - Tab/Shift+Tab for list indentation
        - Enter on empty list items
        """
        # Plain text paste for Ctrl+V
        if (event.key() == Qt.Key.Key_V and 
            event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.paste_plain_text()
            return
        
        # In the keyPressEvent method of NoteTextEdit:
        if event.key() == Qt.Key.Key_Tab:
            cursor = self.textCursor()
            if not cursor.hasSelection():
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                self.setTextCursor(cursor)
            
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Outdent (just call the function and don't do default behavior)
                self.handle_list_indent_outdent(direction=-1)
                return  # Return here to prevent default behavior
            else:
                # Indent (just call the function and don't do default behavior)
                self.handle_list_indent_outdent(direction=1)
                return  # Return here to prevent default behavior
        
        # Handle Enter key on lists
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            block = cursor.block()
            text_in_block = block.text().strip()
            current_list = block.textList()
            
            # If we have a list and the line is empty, remove this block from the list
            if current_list and not text_in_block:
                current_list.remove(block)
                # Let normal "enter" happen after removing formatting
                super().keyPressEvent(event)
                return
        
        # Default handling for other keys
        super().keyPressEvent(event)
    
    # List indent/outdent handling
    def _get_margin_for_indent(self, indent_level: int) -> float:
        """Return appropriate margin for indentation level"""
        base_margin = 15.0
        increment = 10.0
        return base_margin + (increment * indent_level)
    
    def handle_list_indent_outdent(self, direction: int) -> bool:
        """
        Handle Tab/Shift+Tab indentation for all list types
        direction: +1 for indent, -1 for outdent
        """
        # Get style for indent level (can be customized)
        def get_style_for_indent(indent_level: int):
            # Create a pattern of list styles based on level
            styles = [
                QTextListFormat.Style.ListDisc,
                QTextListFormat.Style.ListCircle,
                QTextListFormat.Style.ListSquare,
                QTextListFormat.Style.ListDecimal
            ]
            return styles[indent_level % len(styles)]
        
        # Common function to calculate appropriate margin
        def _get_margin_for_indent(indent_level: int) -> float:
            base_margin = 10.0
            increment = 5.0
            return base_margin + (increment * indent_level)
        
        # Main indentation logic
        cursor = self.textCursor()
        original_start = cursor.selectionStart()
        original_end = cursor.selectionEnd()
        cursor.beginEditBlock()
        
        doc = cursor.document()
        start_block = doc.findBlock(original_start)
        end_block = doc.findBlock(original_end)
        if not start_block.isValid() or not end_block.isValid():
            cursor.endEditBlock()
            return False
        
        changed_any = False
        current_block = start_block
        
        while current_block.isValid() and current_block.position() <= end_block.position():
            block_cursor = QTextCursor(current_block)
            current_list = current_block.textList()
            
            if current_list:
                # Already in a list -> adjust indent level
                list_format = current_list.format()
                current_indent = list_format.indent()
                
                if direction > 0:  # Indent
                    new_indent = current_indent + 1
                    current_list.remove(current_block)
                    
                    new_format = QTextListFormat(list_format)
                    new_format.setIndent(new_indent)
                    new_format.setStyle(get_style_for_indent(new_indent))
                    block_cursor.createList(new_format)
                    
                    block_fmt = block_cursor.blockFormat()
                    block_fmt.setLeftMargin(_get_margin_for_indent(new_indent))
                    block_cursor.setBlockFormat(block_fmt)
                    changed_any = True
                    
                else:  # Outdent
                    if current_indent > 0:
                        new_indent = current_indent - 1
                        current_list.remove(current_block)
                        
                        new_format = QTextListFormat(list_format)
                        new_format.setIndent(new_indent)
                        new_format.setStyle(get_style_for_indent(new_indent))
                        block_cursor.createList(new_format)
                        
                        block_fmt = block_cursor.blockFormat()
                        block_fmt.setLeftMargin(_get_margin_for_indent(new_indent))
                        block_cursor.setBlockFormat(block_fmt)
                        changed_any = True
                    else:
                        # Already at indent 0 => remove list formatting
                        current_list.remove(current_block)
                        changed_any = True
                        
            else:
                # Not in a list
                if direction > 0:
                    # Tab -> create or join a list
                    prev_block = current_block.previous()
                    prev_list = prev_block.textList() if prev_block.isValid() else None
                    
                    if prev_list:
                        parent_format = prev_list.format()
                        new_indent = parent_format.indent() + 1
                        
                        new_format = QTextListFormat(parent_format)
                        new_format.setIndent(new_indent)
                        new_format.setStyle(get_style_for_indent(new_indent))
                        block_cursor.createList(new_format)
                        
                        block_fmt = block_cursor.blockFormat()
                        block_fmt.setLeftMargin(_get_margin_for_indent(new_indent))
                        block_cursor.setBlockFormat(block_fmt)
                    else:
                        # Start a new list at indent=0
                        new_format = QTextListFormat()
                        new_format.setIndent(0)
                        new_format.setStyle(QTextListFormat.Style.ListDisc)
                        block_cursor.createList(new_format)
                        
                        block_fmt = block_cursor.blockFormat()
                        block_fmt.setLeftMargin(_get_margin_for_indent(0))
                        block_cursor.setBlockFormat(block_fmt)
                    changed_any = True
                    
                else:
                    # Shift+Tab on non-list block: adjust margin if needed
                    block_fmt = block_cursor.blockFormat()
                    current_margin = block_fmt.leftMargin()
                    
                    # Compare margin to baseMargin for indent_level=0
                    base_margin = _get_margin_for_indent(0)
                    if current_margin > base_margin + 1:
                        # Reduce margin by one "indent" step
                        new_margin = max(base_margin, current_margin - 5.0)
                        block_fmt.setLeftMargin(new_margin)
                        block_cursor.setBlockFormat(block_fmt)
                        changed_any = True
            
            if current_block == end_block:
                break
            current_block = current_block.next()
        
        cursor.endEditBlock()
        
        # Restore selection
        cursor.setPosition(original_start)
        cursor.setPosition(original_end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        
        return changed_any
    
    # List formatting
    def toggleListFormat(self, desired_style):
        """
        Toggle between bullet or numbered lists across selected paragraphs
        """
        cursor = self.textCursor()
        if not cursor.hasSelection():
            # If nothing is explicitly selected, apply to current paragraph
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            self.setTextCursor(cursor)
        
        # Track selection to restore later
        original_start = cursor.selectionStart()
        original_end = cursor.selectionEnd()
        
        doc = cursor.document()
        start_block = doc.findBlock(original_start)
        end_block = doc.findBlock(original_end)
        
        cursor.beginEditBlock()  # group all changes
        
        block = start_block
        while True:
            if not block.isValid() or block.position() > end_block.position():
                break
            
            # Handle regular list formatting
            current_list = block.textList()
            
            if current_list:
                # Already in a list
                list_fmt = current_list.format()
                current_style = list_fmt.style()
                
                if current_style == desired_style:
                    # Remove from list if same style
                    self._removeListFromBlock(block)
                else:
                    # Switch styles while keeping indent
                    current_indent = list_fmt.indent()
                    self._applyListStyleToBlock(block, desired_style, current_indent)
            else:
                # Not in a list -> apply new style at indent=0
                self._applyListStyleToBlock(block, desired_style, 0)
            
            if block == end_block:
                break
            block = block.next()
        
        cursor.endEditBlock()  # end group
        
        # Restore selection
        cursor.setPosition(original_start)
        cursor.setPosition(original_end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
    
    def _removeListFromBlock(self, block):
        """Remove list formatting from a block"""
        current_list = block.textList()
        if current_list:
            current_list.remove(block)
    
    def _applyListStyleToBlock(self, block, style, indent):
        """Apply list style to a block with proper indentation"""
        cursor = QTextCursor(block)
        list_fmt = QTextListFormat()
        list_fmt.setStyle(style)
        list_fmt.setIndent(indent)
        cursor.createList(list_fmt)
        
        # Adjust left margin for indent
        block_fmt = cursor.blockFormat()
        block_fmt.setLeftMargin(self._get_margin_for_indent(indent))
        cursor.setBlockFormat(block_fmt)
    
    # Add methods for list formats
    def toggle_bullet_list(self):
        """Toggle bullet list formatting"""
        self.toggleListFormat(QTextListFormat.Style.ListDisc)
    
    def toggle_number_list(self):
        """Toggle numbered list formatting"""
        self.toggleListFormat(QTextListFormat.Style.ListDecimal)


class QuickNoteDialog(QDialog):
    """Dialog for creating a quick note"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Note")
        self.resize(400, 300)
        
        self.layout = QVBoxLayout(self)
        
        # Title field
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Note title...")
        self.layout.addWidget(self.title_edit)
        
        # Content field
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("Type your note here...")
        self.layout.addWidget(self.content_edit)
        
        # Destination selector
        self.dest_group = QWidget()
        self.dest_layout = QHBoxLayout(self.dest_group)
        self.dest_layout.setContentsMargins(0, 0, 0, 0)
        
        self.dest_label = QLabel("Save to:")
        self.location_combo = QComboBox()
        
        self.dest_layout.addWidget(self.dest_label)
        self.dest_layout.addWidget(self.location_combo, 1)
        
        self.layout.addWidget(self.dest_group)
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | 
            QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)
    
    def set_locations(self, locations):
        """Set available locations in the combo box"""
        self.location_combo.clear()
        for loc in locations:
            self.location_combo.addItem(loc["path"], loc["item"])
    
    def get_note_data(self):
        """Return the note data entered by user"""
        return {
            "title": self.title_edit.text().strip(),
            "content": self.content_edit.toHtml(),
            "location": self.location_combo.currentData()
        }


class TableDialog(QDialog):
    """Dialog for table insertion with basic formatting options"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Table")
        self.resize(300, 150)
        
        self.layout = QVBoxLayout(self)
        
        # Table dimensions
        self.form_layout = QFormLayout()
        
        self.row_spin = QSpinBox()
        self.row_spin.setMinimum(1)
        self.row_spin.setMaximum(50)
        self.row_spin.setValue(3)
        
        self.col_spin = QSpinBox()
        self.col_spin.setMinimum(1)
        self.col_spin.setMaximum(20)
        self.col_spin.setValue(3)
        
        self.form_layout.addRow("Rows:", self.row_spin)
        self.form_layout.addRow("Columns:", self.col_spin)
        
        self.layout.addLayout(self.form_layout)
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)
    
    def get_table_format(self):
        """Return the table format settings"""
        return {
            "rows": self.row_spin.value(),
            "cols": self.col_spin.value(),
            "border": 1,
            "border_color": QColor("lightgray"),
            "padding": 2,
            "spacing": 0
        }


class OneNotePanel(QDockWidget):
    """
    A dockable panel providing an enhanced OneNote-like hierarchy:
      Notebook -> Section -> Pages
      
    Features include:
    - Full hierarchy with notebooks, sections, and pages
    - Rich text formatting with improved list handling
    - Simple search functionality
    - Quick notes
    - Automatic saving
    - Smart keyboard shortcuts
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Notes")
        # Hide the default title bar
        self.setTitleBarWidget(QWidget(self))
        # Allow movement and closing from the main window
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                         QDockWidget.DockWidgetFeature.DockWidgetClosable)
        
        # Main container widget and layout
        self.main_widget = QWidget()
        self.setWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)
        self.main_widget.setLayout(self.layout)
        
        # Setup toolbar with text formatting and controls
        self.create_toolbars()
        
        # Create the main splitter and content areas
        self.create_main_layout()
        
        # Keep references for current page and loading flags
        self.current_page_item = None
        self._loading_content = False
        
        # JSON file to load/save notes
        self.notes_file = "notes.json"
        self.load_notes_from_file(self.notes_file)
        
        # Setup autosave timer
        self.setup_autosave()
        
        # Set up keyboard shortcuts
        self.setup_shortcuts()
        
        # Default notebook for quick notes
        self.default_notebook = None
        self.default_section = None
        self.setup_defaults()
    
    def create_toolbars(self):
        """Create the formatting and main toolbars"""
        # Main toolbar with search and quick note
        self.main_toolbar = QToolBar("Main", self)
        self.layout.addWidget(self.main_toolbar)
        
        # Search box
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("Search notes...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedWidth(180)
        self.search_box.returnPressed.connect(self.perform_search)
        
        # Search button
        self.search_button = QAction("Search", self)
        self.search_button.triggered.connect(self.perform_search)
        
        # Quick note button
        self.quick_note_action = QAction("Quick Note", self)
        self.quick_note_action.triggered.connect(self.create_quick_note)
        
        # Add main toolbar actions
        self.main_toolbar.addWidget(self.search_box)
        self.main_toolbar.addAction(self.search_button)
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.quick_note_action)
        
        # Formatting toolbar
        self.format_toolbar = QToolBar("Format", self)
        self.layout.addWidget(self.format_toolbar)
        
        # Bold action
        self.bold_action = QAction("B", self)
        self.bold_action.setCheckable(True)
        self.bold_action.setFont(QFont("Arial", weight=QFont.Weight.Bold))
        self.bold_action.triggered.connect(self.on_bold_triggered)
        self.format_toolbar.addAction(self.bold_action)
        
        # Italic action
        self.italic_action = QAction("I", self)
        self.italic_action.setCheckable(True)
        italic_font = QFont("Arial")
        italic_font.setItalic(True)
        self.italic_action.setFont(italic_font)
        self.italic_action.triggered.connect(self.on_italic_triggered)
        self.format_toolbar.addAction(self.italic_action)
        
        # Underline action
        self.underline_action = QAction("U", self)
        self.underline_action.setCheckable(True)
        underline_font = QFont("Arial")
        underline_font.setUnderline(True)
        self.underline_action.setFont(underline_font)
        self.underline_action.triggered.connect(self.on_underline_triggered)
        self.format_toolbar.addAction(self.underline_action)
        
        # Font family combo
        self.font_family_combo = QFontComboBox(self)
        self.font_family_combo.currentFontChanged.connect(self.on_font_family_changed)
        self.format_toolbar.addWidget(self.font_family_combo)
        
        # Font size combo
        self.font_size_combo = QComboBox(self)
        for size in [8, 9, 10, 11, 12, 14, 16, 18, 24, 36, 48]:
            self.font_size_combo.addItem(str(size))
        self.font_size_combo.setCurrentText("12")  # Default size
        self.font_size_combo.currentIndexChanged.connect(self.on_font_size_changed)
        self.format_toolbar.addWidget(self.font_size_combo)
        
        # Text color
        self.color_action = QAction("Color", self)
        self.color_action.triggered.connect(self.on_text_color_changed)
        self.format_toolbar.addAction(self.color_action)
        
        # Lists
        self.format_toolbar.addSeparator()
        
        # Bulleted list
        self.bullet_list_action = QAction("• Bullets", self)
        self.bullet_list_action.triggered.connect(self.toggle_bullet_list)
        self.format_toolbar.addAction(self.bullet_list_action)
        
        # Numbered list
        self.number_list_action = QAction("1. Numbered", self)
        self.number_list_action.triggered.connect(self.toggle_number_list)
        self.format_toolbar.addAction(self.number_list_action)
        
        # Table and link actions
        self.format_toolbar.addSeparator()
        
        # Insert table
        self.table_action = QAction("Table", self)
        self.table_action.triggered.connect(self.on_insert_table)
        self.format_toolbar.addAction(self.table_action)
        
        # Insert link
        self.link_action = QAction("Link", self)
        self.link_action.triggered.connect(self.on_insert_link)
        self.format_toolbar.addAction(self.link_action)
    
    def create_main_layout(self):
        """Create the main splitter and content areas"""
        # Use QSplitter for draggable divider
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter)
        
        # Left: Navigation Tree (custom tree widget)
        self.nav_tree = DraggableTreeWidget()
        self.nav_tree.setHeaderLabels(["Notebooks"])
        self.nav_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.nav_tree.customContextMenuRequested.connect(self.on_tree_context_menu)
        self.nav_tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        self.splitter.addWidget(self.nav_tree)
        
        # Right: Custom text editor
        self.text_editor = NoteTextEdit()
        self.text_editor.textChanged.connect(self.on_editor_text_changed)
        self.splitter.addWidget(self.text_editor)
        
        # Set initial splitter proportions
        self.splitter.setSizes([int(self.width() * 0.3), int(self.width() * 0.7)])
    
    def setup_autosave(self):
        """Configure auto-save functionality"""
        # Timer for delayed saving
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(1500)  # 1.5 seconds
        self.save_timer.timeout.connect(self._on_save_timer_timeout)
    
    def setup_shortcuts(self):
        """Set up keyboard shortcuts for common actions"""
        # Format shortcuts
        QShortcut(QKeySequence("Ctrl+B"), self, self.on_bold_triggered)
        QShortcut(QKeySequence("Ctrl+I"), self, self.on_italic_triggered)
        QShortcut(QKeySequence("Ctrl+U"), self, self.on_underline_triggered)
        
        # List shortcuts
        QShortcut(QKeySequence("Ctrl+Shift+B"), self, self.toggle_bullet_list)
        QShortcut(QKeySequence("Ctrl+Shift+N"), self, self.toggle_number_list)
        
        # Navigation shortcuts
        QShortcut(QKeySequence("Ctrl+F"), self, self.focus_search)
        QShortcut(QKeySequence("Ctrl+N"), self, self.create_quick_note)
        
        # Save shortcut
        QShortcut(QKeySequence("Ctrl+S"), self, lambda: self.save_notes_to_file(self.notes_file))
    
    def setup_defaults(self):
        """Set up default notebook and section for quick notes"""
        # Find or create default notebook
        found_default = False
        
        for i in range(self.nav_tree.topLevelItemCount()):
            nb_item = self.nav_tree.topLevelItem(i)
            if nb_item.text(0) == "Quick Notes":
                self.default_notebook = nb_item
                found_default = True
                break
        
        if not found_default:
            # Create default notebook and section
            self.default_notebook = QTreeWidgetItem(["Quick Notes"])
            self.default_notebook.setData(0, NOTE_TYPE_ROLE, "notebook")
            self.default_notebook.setData(0, EXPANDED_ROLE, True)
            
            # Set icon
            if "notebook" in self.nav_tree.icons:
                self.default_notebook.setIcon(0, self.nav_tree.icons["notebook"])
                
            self.nav_tree.addTopLevelItem(self.default_notebook)
            
            # Add a default section
            default_section = QTreeWidgetItem(["Unfiled Notes"])
            default_section.setData(0, NOTE_TYPE_ROLE, "section")
            default_section.setData(0, EXPANDED_ROLE, True)
            
            # Set icon
            if "section" in self.nav_tree.icons:
                default_section.setIcon(0, self.nav_tree.icons["section"])
                
            self.default_notebook.addChild(default_section)
            
            self.default_section = default_section
            self.queue_save()
        else:
            # Find or create default section
            found_section = False
            for i in range(self.default_notebook.childCount()):
                child = self.default_notebook.child(i)
                if child.data(0, NOTE_TYPE_ROLE) == "section" and child.text(0) == "Unfiled Notes":
                    self.default_section = child
                    found_section = True
                    break
            
            if not found_section:
                self.default_section = QTreeWidgetItem(["Unfiled Notes"])
                self.default_section.setData(0, NOTE_TYPE_ROLE, "section")
                self.default_section.setData(0, EXPANDED_ROLE, True)
                
                # Set icon
                if "section" in self.nav_tree.icons:
                    self.default_section.setIcon(0, self.nav_tree.icons["section"])
                    
                self.default_notebook.addChild(self.default_section)
                self.queue_save()
    
    # Search functionality
    def focus_search(self):
        """Focus the search box"""
        self.search_box.setFocus()
        self.search_box.selectAll()
    
    def perform_search(self):
        """Start a search operation"""
        search_text = self.search_box.text().strip().lower()
        if not search_text:
            return
        
        # Perform search directly
        results = self.search_notes(search_text)
        self.search_completed(results)
    
    def search_notes(self, search_text):
        """
        Search all notes for the given text
        Returns a list of results with page items and context
        """
        results = []
        
        # Search through all notebooks
        for i in range(self.nav_tree.topLevelItemCount()):
            nb_item = self.nav_tree.topLevelItem(i)
            self._search_item_recursive(nb_item, search_text, results, [nb_item.text(0)])
        
        return results
    
    def _search_item_recursive(self, item, search_text, results, path):
        """Recursively search through the tree items"""
        item_type = item.data(0, NOTE_TYPE_ROLE)
        
        # If it's a page, search its content
        if item_type == "page":
            content = item.data(0, PAGE_CONTENT_ROLE) or ""
            title = item.text(0).lower()
            
            # Convert HTML to plain text for searching (simple approach)
            plain_content = content.lower()
            for tag in ["<br>", "<p>", "</p>", "<div>", "</div>"]:
                plain_content = plain_content.replace(tag, " ")
            
            # Remove all HTML tags for a crude plain text version
            plain_content = re.sub(r'<[^>]*>', '', plain_content)
            
            # Search in title and content
            if search_text in title or search_text in plain_content:
                # Found a match - add to results
                results.append({
                    'item': item,
                    'path': " > ".join(path + [item.text(0)])
                })
        
        # Continue searching children
        for i in range(item.childCount()):
            child = item.child(i)
            # Add current item to path only for non-page items
            if item_type != "page":
                self._search_item_recursive(child, search_text, results, path + [item.text(0)])
            else:
                self._search_item_recursive(child, search_text, results, path)
    
    def search_completed(self, results):
        """Handle search completion"""
        if not results:
            QMessageBox.information(self, "Search Results", 
                                   f"No results found for '{self.search_box.text()}'")
            return
        
        # Simple results dialog
        result_text = f"Found {len(results)} matches for '{self.search_box.text()}':\n\n"
        
        # Create message box with results
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Search Results")
        msg_box.setIcon(QMessageBox.Icon.Information)
        
        # Add buttons for each result
        msg_box.setStandardButtons(QMessageBox.StandardButton.Close)
        
        # List of results
        list_widget = QListWidget()
        list_widget.setMinimumWidth(400)
        list_widget.setMinimumHeight(300)
        
        # Add results to list
        for i, result in enumerate(results):
            item = QListWidgetItem(result['path'])
            item.setData(Qt.ItemDataRole.UserRole, result['item'])
            list_widget.addItem(item)
        
        # Connect double-click to navigate to result
        list_widget.itemDoubleClicked.connect(
            lambda item: self.nav_tree.setCurrentItem(item.data(Qt.ItemDataRole.UserRole)))
        
        # Set layout with list widget
        layout = msg_box.layout()
        layout.addWidget(list_widget, 1, 0, 1, layout.columnCount())
        
        # Show dialog
        msg_box.exec()
    
    # Quick note functionality
    def create_quick_note(self):
        """Show dialog to create a quick note"""
        dialog = QuickNoteDialog(self)
        
        # Get all possible locations
        locations = self.get_note_locations()
        dialog.set_locations(locations)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            note_data = dialog.get_note_data()
            
            if not note_data["title"]:
                # Use timestamp as default title
                now = datetime.now()
                note_data["title"] = f"Note {now.strftime('%m/%d/%Y %H:%M')}"
            
            # Determine where to create the note
            if note_data["location"]:
                section_item = note_data["location"]
                if section_item.data(0, NOTE_TYPE_ROLE) == "section":
                    page_item = self.add_page(section_item, note_data["title"], note_data["content"])
                    # Select the newly created page
                    self.nav_tree.setCurrentItem(page_item)
            else:
                # Use default location
                page_item = self.add_page(self.default_section, note_data["title"], note_data["content"])
                # Select the newly created page
                self.nav_tree.setCurrentItem(page_item)
    
    def get_note_locations(self):
        """Get all available sections for note placement"""
        locations = []
        
        def process_item(item, path=""):
            item_type = item.data(0, NOTE_TYPE_ROLE)
            current_path = f"{path} > {item.text(0)}" if path else item.text(0)
            
            if item_type == "section":
                locations.append({"path": current_path, "item": item})
            
            for i in range(item.childCount()):
                child = item.child(i)
                process_item(child, current_path)
        
        # Process all notebooks
        for i in range(self.nav_tree.topLevelItemCount()):
            nb_item = self.nav_tree.topLevelItem(i)
            process_item(nb_item)
        
        return locations
    
    # Basic text formatting
    def on_bold_triggered(self, checked=None):
        """Toggle bold formatting"""
        fmt = QTextCharFormat()
        if checked is None:  # Called from shortcut
            cursor = self.text_editor.textCursor()
            checked = not cursor.charFormat().fontWeight() > QFont.Weight.Normal
            
        fmt.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
        self.merge_format_on_word_or_selection(fmt)
    
    def on_italic_triggered(self, checked=None):
        """Toggle italic formatting"""
        fmt = QTextCharFormat()
        if checked is None:  # Called from shortcut
            cursor = self.text_editor.textCursor()
            checked = not cursor.charFormat().fontItalic()
            
        fmt.setFontItalic(checked)
        self.merge_format_on_word_or_selection(fmt)
    
    def on_underline_triggered(self, checked=None):
        """Toggle underline formatting"""
        fmt = QTextCharFormat()
        if checked is None:  # Called from shortcut
            cursor = self.text_editor.textCursor()
            checked = not cursor.charFormat().fontUnderline()
            
        fmt.setFontUnderline(checked)
        self.merge_format_on_word_or_selection(fmt)
    
    def merge_format_on_word_or_selection(self, char_format):
        """Apply formatting to current word or selection"""
        cursor = self.text_editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.mergeCharFormat(char_format)
        self.text_editor.mergeCurrentCharFormat(char_format)
    
    # Advanced formatting
    def on_font_family_changed(self, font):
        """Change font family"""
        cursor = self.text_editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        char_format = QTextCharFormat()
        char_format.setFontFamily(font.family())
        cursor.mergeCharFormat(char_format)
        self.text_editor.mergeCurrentCharFormat(char_format)
    
    def on_font_size_changed(self):
        """Change font size"""
        size = int(self.font_size_combo.currentText())
        cursor = self.text_editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        char_format = QTextCharFormat()
        char_format.setFontPointSize(size)
        cursor.mergeCharFormat(char_format)
        self.text_editor.mergeCurrentCharFormat(char_format)
    
    def on_text_color_changed(self):
        """Change text color"""
        color = QColorDialog.getColor()
        if color.isValid():
            cursor = self.text_editor.textCursor()
            if not cursor.hasSelection():
                cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            char_format = QTextCharFormat()
            char_format.setForeground(color)
            cursor.mergeCharFormat(char_format)
            self.text_editor.mergeCurrentCharFormat(char_format)
    
    # List formatting
    def toggle_bullet_list(self):
        """Toggle bullet list"""
        self.text_editor.toggle_bullet_list()
    
    def toggle_number_list(self):
        """Toggle numbered list"""
        self.text_editor.toggle_number_list()
    
    # Table insertion
    def on_insert_table(self):
        """Show dialog for table insertion"""
        dialog = TableDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            format_data = dialog.get_table_format()
            self.insert_table_with_format(format_data)
    
    def insert_table_with_format(self, format_data):
        """Insert a table with specified formatting"""
        rows = format_data["rows"]
        cols = format_data["cols"]
        
        # Prepare table format
        table_format = QTextTableFormat()
        table_format.setBorder(format_data["border"])
        table_format.setCellPadding(format_data["padding"])
        table_format.setCellSpacing(format_data["spacing"])
        table_format.setBorderBrush(QBrush(format_data["border_color"]))
        
        try:
            table_format.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        except AttributeError:
            # Handle older PyQt versions
            pass
        
        # Insert the table
        cursor = self.text_editor.textCursor()
        cursor.insertTable(rows, cols, table_format)
    
    # Insert link
    def on_insert_link(self):
        """Insert a hyperlink at cursor position"""
        cursor = self.text_editor.textCursor()
        selected_text = cursor.selectedText()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Insert Link")
        dialog.resize(400, 150)
        
        layout = QVBoxLayout(dialog)
        
        # Text field
        text_layout = QHBoxLayout()
        text_label = QLabel("Text:")
        text_edit = QLineEdit(selected_text)
        text_layout.addWidget(text_label)
        text_layout.addWidget(text_edit)
        layout.addLayout(text_layout)
        
        # URL field
        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        url_edit = QLineEdit("https://")
        url_layout.addWidget(url_label)
        url_layout.addWidget(url_edit)
        layout.addLayout(url_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            link_text = text_edit.text()
            url = url_edit.text()
            
            if not link_text:
                link_text = url
                
            # Apply link format
            cursor = self.text_editor.textCursor()
            
            # Remove any selected text first
            if cursor.hasSelection():
                cursor.removeSelectedText()
                
            # Insert the link with formatting
            link_format = QTextCharFormat()
            link_format.setAnchor(True)
            link_format.setAnchorHref(url)
            link_format.setFontUnderline(True)
            link_format.setForeground(QBrush(QColor("blue")))
            
            cursor.insertText(link_text, link_format)
    
    # Context menu handling
    def on_tree_context_menu(self, position):
        """Show context menu for tree items"""
        item = self.nav_tree.itemAt(position)
        menu = QMenu(self)
        
        if not item:
            # No item selected - show notebook actions
            add_notebook_action = menu.addAction("Add Notebook")
            add_notebook_action.triggered.connect(self.add_notebook_dialog)
            menu.exec(self.nav_tree.mapToGlobal(position))
            return
        
        item_type = item.data(0, NOTE_TYPE_ROLE)
        
        if item_type == "notebook":
            # Notebook actions
            add_section_action = menu.addAction("Add Section")
            add_section_action.triggered.connect(lambda: self.add_section_dialog(item))
            
            menu.addSeparator()
            
            rename_action = menu.addAction("Rename Notebook")
            rename_action.triggered.connect(lambda: self.rename_item(item))
            
            menu.addSeparator()
            
            delete_action = menu.addAction("Delete Notebook")
            delete_action.triggered.connect(lambda: self.delete_item(item))
            
        elif item_type == "section":
            # Section actions
            add_page_action = menu.addAction("Add Page")
            add_page_action.triggered.connect(lambda: self.add_page_dialog(item))
            
            menu.addSeparator()
            
            rename_action = menu.addAction("Rename Section")
            rename_action.triggered.connect(lambda: self.rename_item(item))
            
            menu.addSeparator()
            
            delete_action = menu.addAction("Delete Section")
            delete_action.triggered.connect(lambda: self.delete_item(item))
            
        elif item_type == "page":
            # Page actions
            rename_action = menu.addAction("Rename Page")
            rename_action.triggered.connect(lambda: self.rename_item(item))
            
            menu.addSeparator()
            
            delete_action = menu.addAction("Delete Page")
            delete_action.triggered.connect(lambda: self.delete_item(item))
        
        menu.exec(self.nav_tree.mapToGlobal(position))
    
    # Tree CRUD operations
    def add_notebook_dialog(self):
        """Show dialog to add a notebook"""
        name, ok = QInputDialog.getText(self, "Add Notebook", "Notebook name:")
        if ok and name.strip():
            self.add_notebook(name.strip())
    
    def add_notebook(self, title):
        """Add a new notebook to the tree"""
        now = datetime.now().isoformat()
        
        new_item = QTreeWidgetItem([title])
        new_item.setData(0, NOTE_TYPE_ROLE, "notebook")
        new_item.setData(0, EXPANDED_ROLE, True)
        new_item.setData(0, CREATED_ROLE, now)
        new_item.setData(0, MODIFIED_ROLE, now)
        new_item.setData(0, UUID_ROLE, f"nb_{int(time.time()*1000)}")
        
        # Set icon
        if "notebook" in self.nav_tree.icons:
            new_item.setIcon(0, self.nav_tree.icons["notebook"])
        
        self.nav_tree.addTopLevelItem(new_item)
        self.queue_save()
        
        return new_item
    
    def add_section_dialog(self, parent_item):
        """Show dialog to add a section"""
        name, ok = QInputDialog.getText(self, "Add Section", "Section name:")
        if ok and name.strip():
            section_item = self.add_section(parent_item, name.strip())
            
            # Automatically add one blank page
            self.add_page(section_item, "Untitled Page")
    
    def add_section(self, parent_item, title):
        """Add a new section under parent"""
        now = datetime.now().isoformat()
        
        new_item = QTreeWidgetItem([title])
        new_item.setData(0, NOTE_TYPE_ROLE, "section")
        new_item.setData(0, EXPANDED_ROLE, True)
        new_item.setData(0, CREATED_ROLE, now)
        new_item.setData(0, MODIFIED_ROLE, now)
        new_item.setData(0, UUID_ROLE, f"s_{int(time.time()*1000)}")
        
        # Set icon
        if "section" in self.nav_tree.icons:
            new_item.setIcon(0, self.nav_tree.icons["section"])
        
        parent_item.addChild(new_item)
        parent_item.setExpanded(True)
        self.queue_save()
        
        return new_item
    
    def add_page_dialog(self, section_item):
        """Show dialog to add a page"""
        name, ok = QInputDialog.getText(self, "Add Page", "Page name:")
        if ok and name.strip():
            self.add_page(section_item, name.strip())
    
    def add_page(self, section_item, title, content=""):
        """Add a new page under section"""
        now = datetime.now().isoformat()
        
        new_item = QTreeWidgetItem([title])
        new_item.setData(0, NOTE_TYPE_ROLE, "page")
        new_item.setData(0, EXPANDED_ROLE, False)
        new_item.setData(0, PAGE_CONTENT_ROLE, content)
        new_item.setData(0, CREATED_ROLE, now)
        new_item.setData(0, MODIFIED_ROLE, now)
        new_item.setData(0, UUID_ROLE, f"p_{int(time.time()*1000)}")
        
        # Set icon
        if "page" in self.nav_tree.icons:
            new_item.setIcon(0, self.nav_tree.icons["page"])
        
        section_item.addChild(new_item)
        section_item.setExpanded(True)
        self.queue_save()
        
        return new_item
    
    def rename_item(self, item):
        """Show dialog to rename an item"""
        old_text = item.text(0)
        item_type = item.data(0, NOTE_TYPE_ROLE)
        title_str = f"Rename {item_type.capitalize()}"
        
        new_name, ok = QInputDialog.getText(
            self, title_str, f"New name for '{old_text}':", 
            text=old_text
        )
        
        if ok and new_name.strip():
            item.setText(0, new_name.strip())
            item.setData(0, MODIFIED_ROLE, datetime.now().isoformat())
            self.queue_save()
    
    def delete_item(self, item):
        """Show confirmation and delete an item"""
        reply = QMessageBox.question(
            self,
            "Delete",
            f"Are you sure you want to delete '{item.text(0)}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            parent_item = item.parent()
            
            # Check if this is the current page
            if item == self.current_page_item:
                self.current_page_item = None
                self._loading_content = True
                self.text_editor.clear()
                self.text_editor.setReadOnly(True)
                self._loading_content = False
            
            # Remove from tree
            if parent_item:
                index = parent_item.indexOfChild(item)
                parent_item.takeChild(index)
            else:
                index = self.nav_tree.indexOfTopLevelItem(item)
                self.nav_tree.takeTopLevelItem(index)
            
            self.queue_save()
    
    # Content handling
    def on_tree_selection_changed(self):
        """Handle selection change in the tree"""
        # Save current page content first
        if self.current_page_item:
            old_content = self.text_editor.toHtml()
            self.current_page_item.setData(0, PAGE_CONTENT_ROLE, old_content)
            self.current_page_item.setData(0, MODIFIED_ROLE, datetime.now().isoformat())
            self.queue_save()
        
        # Handle the new selection
        selected_items = self.nav_tree.selectedItems()
        if not selected_items:
            self.current_page_item = None
            self._loading_content = True
            self.text_editor.clear()
            self.text_editor.setReadOnly(True)
            self._loading_content = False
            return
        
        new_item = selected_items[0]
        item_type = new_item.data(0, NOTE_TYPE_ROLE)
        
        if item_type == "page":
            # Load page content
            self.current_page_item = new_item
            content = new_item.data(0, PAGE_CONTENT_ROLE)
            
            self._loading_content = True
            self.text_editor.setHtml(content if content else "")
            self.text_editor.setReadOnly(False)
            self._loading_content = False
        else:
            # Clear editor for non-page items
            self.current_page_item = None
            self._loading_content = True
            self.text_editor.clear()
            self.text_editor.setReadOnly(True)
            self._loading_content = False
    
    def on_editor_text_changed(self):
        """Save content when editor text changes"""
        if self._loading_content:
            return
            
        if self.current_page_item:
            new_content = self.text_editor.toHtml()
            self.current_page_item.setData(0, PAGE_CONTENT_ROLE, new_content)
            self.current_page_item.setData(0, MODIFIED_ROLE, datetime.now().isoformat())
            self.queue_save()
    
    # Save/Load functionality
    def on_items_reorganized(self):
        """Handle tree items being reorganized"""
        self.queue_save()
    
    def queue_save(self):
        """Queue a delayed save operation"""
        if self.save_timer.isActive():
            self.save_timer.stop()
        self.save_timer.start()
    
    def _on_save_timer_timeout(self):
        """Execute the actual save when timer expires"""
        self._save_notes_to_file_internal()
    
    def _save_notes_to_file_internal(self):
        """Save notes to JSON file"""
        data = {"notebooks": [], "version": "2.0"}
        
        for i in range(self.nav_tree.topLevelItemCount()):
            nb_item = self.nav_tree.topLevelItem(i)
            notebook_dict = self._serialize_item(nb_item)
            data["notebooks"].append(notebook_dict)
        
        try:
            with open(self.notes_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[ERROR] Could not save notes to {self.notes_file}: {e}")
        else:
            print(f"[INFO] Notes saved to {self.notes_file}")
    
    def _serialize_item(self, item):
        """Recursively serialize an item and its children"""
        item_type = item.data(0, NOTE_TYPE_ROLE)
        item_dict = {
            "title": item.text(0),
            "type": item_type,
            "expanded": item.isExpanded(),
            "created": item.data(0, CREATED_ROLE) or datetime.now().isoformat(),
            "modified": item.data(0, MODIFIED_ROLE) or datetime.now().isoformat(),
            "uuid": item.data(0, UUID_ROLE) or f"{item_type[0]}_{int(time.time()*1000)}",
            "children": []
        }
        
        # Add content for pages
        if item_type == "page":
            item_dict["content"] = item.data(0, PAGE_CONTENT_ROLE) or ""
        
        # Process children
        for j in range(item.childCount()):
            child_item = item.child(j)
            child_dict = self._serialize_item(child_item)
            item_dict["children"].append(child_dict)
        
        return item_dict
    
    def save_notes_to_file(self, filepath):
        """Public method to save notes immediately"""
        if self.save_timer.isActive():
            self.save_timer.stop()
        self._save_notes_to_file_internal()
    
    def load_notes_from_file(self, filepath):
        """Load notes from JSON file"""
        if not os.path.exists(filepath):
            print(f"[INFO] {filepath} not found; no data to load.")
            return
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load notes from {filepath}: {e}")
            return
        
        self.nav_tree.clear()
        
        # Check version to handle different formats
        version = data.get("version", "1.0")
        
        if version >= "2.0":
            # New format with full hierarchy
            notebooks = data.get("notebooks", [])
            for nb in notebooks:
                self._deserialize_item(nb, None)
        else:
            # Legacy format (backward compatibility)
            notebooks = data.get("notebooks", [])
            for nb in notebooks:
                nb_item = QTreeWidgetItem([nb["title"]])
                nb_item.setData(0, NOTE_TYPE_ROLE, "notebook")
                nb_item.setData(0, EXPANDED_ROLE, nb.get("expanded", True))
                nb_item.setData(0, UUID_ROLE, f"nb_{int(time.time()*1000)}")
                
                # Set icon
                if "notebook" in self.nav_tree.icons:
                    nb_item.setIcon(0, self.nav_tree.icons["notebook"])
                    
                self.nav_tree.addTopLevelItem(nb_item)
                nb_item.setExpanded(nb.get("expanded", True))
                
                sections = nb.get("sections", [])
                for s in sections:
                    s_item = QTreeWidgetItem([s["title"]])
                    s_item.setData(0, NOTE_TYPE_ROLE, "section")
                    s_item.setData(0, EXPANDED_ROLE, s.get("expanded", True))
                    s_item.setData(0, UUID_ROLE, f"s_{int(time.time()*1000)}")
                    
                    # Set icon
                    if "section" in self.nav_tree.icons:
                        s_item.setIcon(0, self.nav_tree.icons["section"])
                        
                    nb_item.addChild(s_item)
                    s_item.setExpanded(s.get("expanded", True))
                    
                    pages = s.get("pages", [])
                    for p in pages:
                        p_item = QTreeWidgetItem([p["title"]])
                        p_item.setData(0, NOTE_TYPE_ROLE, "page")
                        p_item.setData(0, PAGE_CONTENT_ROLE, p.get("content", ""))
                        p_item.setData(0, EXPANDED_ROLE, p.get("expanded", False))
                        p_item.setData(0, UUID_ROLE, f"p_{int(time.time()*1000)}")
                        
                        # Set icon
                        if "page" in self.nav_tree.icons:
                            p_item.setIcon(0, self.nav_tree.icons["page"])
                            
                        s_item.addChild(p_item)
                        p_item.setExpanded(p.get("expanded", False))
    
    def _deserialize_item(self, item_data, parent_item):
        """Recursively deserialize items from JSON"""
        # Create new item
        new_item = QTreeWidgetItem([item_data["title"]])
        
        # Set item data
        item_type = item_data["type"]
        new_item.setData(0, NOTE_TYPE_ROLE, item_type)
        new_item.setData(0, EXPANDED_ROLE, item_data.get("expanded", True))
        new_item.setData(0, CREATED_ROLE, item_data.get("created"))
        new_item.setData(0, MODIFIED_ROLE, item_data.get("modified"))
        new_item.setData(0, UUID_ROLE, item_data.get("uuid"))
        
        # Set icon based on type
        if item_type in self.nav_tree.icons:
            new_item.setIcon(0, self.nav_tree.icons[item_type])
        
        # Set content for pages
        if item_type == "page":
            new_item.setData(0, PAGE_CONTENT_ROLE, item_data.get("content", ""))
        
        # Add to tree
        if parent_item:
            parent_item.addChild(new_item)
        else:
            self.nav_tree.addTopLevelItem(new_item)
        
        # Set expanded state
        new_item.setExpanded(item_data.get("expanded", True))
        
        # Process children
        for child_data in item_data.get("children", []):
            self._deserialize_item(child_data, new_item)
        
        return new_item