import os
import json
import uuid
from datetime import datetime

from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QMenu,
    QInputDialog,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QLineEdit,
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QDateEdit,
    QStyledItemDelegate,
    QToolTip,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QLabel,
    QToolButton
)
from PyQt6.QtCore import (
    Qt,
    QPoint,
    QDate,
    QTimer,
    QSize
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QIcon
)


from ui.icon_utils import create_colored_svg_icon  

# Add this code near the beginning of the file, after imports but before the classes

class CustomTreeWidgetItem(QTreeWidgetItem):
    def __lt__(self, other):
        """
        Force undone < done among siblings, then compare by current sort column if both undone or both done.
        """
        if not isinstance(other, QTreeWidgetItem):
            return super().__lt__(other)

        self_done = (self.checkState(0) == Qt.CheckState.Checked)
        other_done = (other.checkState(0) == Qt.CheckState.Checked)

        # undone items appear before done items
        if self_done != other_done:
            return not self_done

        # fallback: compare text in the current sort column
        tree = self.treeWidget()
        if not tree:
            return super().__lt__(other)

        sort_col = tree.sortColumn()
        return self.text(sort_col) < other.text(sort_col)

class SafeTreeItem(CustomTreeWidgetItem):
    """
    A wrapper around QTreeWidgetItem that safely handles flag operations
    to prevent recursion errors with PyQt6.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store a tooltip for the first column if text is provided
        if len(args) > 0 and isinstance(args[0], list) and len(args[0]) > 0:
            self.setToolTip(0, args[0][0])
    
    def safeFlags(self):
        """Get flags safely without risking recursion"""
        # Call super's flags method to avoid potential custom handling
        return super().flags()
    
    def hasFlag(self, flag):
        """Safely check if this item has a specific flag"""
        flags = self.safeFlags()
        return (flags & flag) == flag
    
    def addFlag(self, flag):
        """Safely add a flag to this item"""
        flags = self.safeFlags()
        flags |= flag
        self.setFlags(flags)
        
    def removeFlag(self, flag):
        """Safely remove a flag from this item"""
        flags = self.safeFlags()
        flags &= ~flag
        self.setFlags(flags)
    
    def setMultipleFlags(self, *flags_to_add, clear_first=False):
        """Set multiple flags at once"""
        if clear_first:
            flags = Qt.ItemFlag.NoItemFlags
        else:
            flags = self.safeFlags()
            
        for flag in flags_to_add:
            flags |= flag
            
        self.setFlags(flags)
        
    def markAsDone(self, is_done=True):
        """Mark the item as done, with appropriate visual styling"""
        state = Qt.CheckState.Checked if is_done else Qt.CheckState.Unchecked
        self.setCheckState(0, state)
        
        # Apply visual formatting
        font = self.font(0)
        font.setStrikeOut(is_done)
        self.setFont(0, font)
        
        # Set text color
        color = Qt.GlobalColor.darkGray if is_done else Qt.GlobalColor.white
        for col in range(4):  # Adjust if you have more columns
            self.setForeground(col, color)
    
    def isDone(self):
        """Check if the item is marked as done"""
        return self.checkState(0) == Qt.CheckState.Checked

# Define the create_item function at the module level
def create_item(texts, is_checkable=True, is_editable=True, is_draggable=True, is_droppable=True, user_data=None):
    """
    Factory method to create SafeTreeItems with consistent properties.
    
    Args:
        texts: List of text values for columns
        is_checkable: Whether the item should be checkable
        is_editable: Whether the item should be editable  
        is_draggable: Whether the item can be dragged
        is_droppable: Whether it can accept drops
        user_data: Optional user data to store (dict)
        
    Returns:
        SafeTreeItem: A properly configured item
    """
    item = SafeTreeItem(texts)
    
    # Set base flags
    flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
    
    # Add optional flags
    if is_checkable:
        flags |= Qt.ItemFlag.ItemIsUserCheckable
        item.setCheckState(0, Qt.CheckState.Unchecked)
    
    if is_editable:
        flags |= Qt.ItemFlag.ItemIsEditable
        
    if is_draggable:
        flags |= Qt.ItemFlag.ItemIsDragEnabled
        
    if is_droppable:
        flags |= Qt.ItemFlag.ItemIsDropEnabled
    
    # Set flags in one operation
    item.setFlags(flags)
    
    # Set user data if provided
    if user_data:
        item.setData(0, Qt.ItemDataRole.UserRole, user_data)
        
    return item

class AddItemDialog(QDialog):
    """
    A generic dialog that collects multiple new items from the user,
    each with: 
      - Name (required)
      - Optional Due Date (can be omitted by checking "No Due Date")
      - Optional Priority
      - Optional Recurrence (None, Daily, Weekly, Monthly)

    Supports "OK," "Add Another," and "Cancel."
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Item(s)")
        # Will hold dicts of the form:
        # {
        #   "name": str,
        #   "due": str (YYYY-MM-DD or empty),
        #   "priority": str,
        #   "recurrence": str ("None", "Daily", "Weekly", or "Monthly")
        # }
        self.new_items = []

        self.init_ui()

    def init_ui(self):
        from PyQt6.QtWidgets import (
            QLabel, QComboBox, QVBoxLayout, QHBoxLayout,
            QPushButton, QLineEdit, QDateEdit, QCheckBox
        )
        from PyQt6.QtCore import QDate

        self.layout = QVBoxLayout(self)

        # --- 1) Name Field ---
        self.name_label = QLabel("Name:")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter name...")

        name_row = QHBoxLayout()
        name_row.addWidget(self.name_label)
        name_row.addWidget(self.name_edit)
        self.layout.addLayout(name_row)

        # --- 2) No Due Date Checkbox + Date Field ---
        self.no_date_checkbox = QCheckBox("No Due Date")
        self.no_date_checkbox.setChecked(True)
        self.no_date_checkbox.toggled.connect(self.on_no_date_toggled)

        self.due_label = QLabel("Due Date:")
        self.due_edit = QDateEdit()
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDate(QDate.currentDate())
        # If "No Due Date" is checked initially, disable the date field
        self.due_edit.setDisabled(True)

        # If the user changes the date, we automatically uncheck "No Due Date"
        self.due_edit.dateChanged.connect(self.on_due_date_changed)

        date_row = QHBoxLayout()
        date_row.addWidget(self.no_date_checkbox)
        date_row.addWidget(self.due_label)
        date_row.addWidget(self.due_edit)
        self.layout.addLayout(date_row)

        # --- 3) Priority Field ---
        self.priority_label = QLabel("Priority:")
        self.priority_combo = QComboBox()
        # Insert "(None)" at the top to allow skipping priority
        self.priority_combo.addItems(["(None)", "Low", "Medium", "High", "Critical"])

        prio_row = QHBoxLayout()
        prio_row.addWidget(self.priority_label)
        prio_row.addWidget(self.priority_combo)
        self.layout.addLayout(prio_row)

        # --- 4) Recurrence Field ---
        self.recurrence_label = QLabel("Recurrence:")
        self.recurrence_combo = QComboBox()
        # Available recurrence choices
        self.recurrence_combo.addItems(["None", "Daily", "Weekly", "Monthly"])

        rec_row = QHBoxLayout()
        rec_row.addWidget(self.recurrence_label)
        rec_row.addWidget(self.recurrence_combo)
        self.layout.addLayout(rec_row)

        # --- 5) Buttons ---
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_add_another = QPushButton("Add Another")
        self.btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_add_another)
        btn_layout.addWidget(self.btn_cancel)
        self.layout.addLayout(btn_layout)

        # Connect signals
        self.btn_ok.clicked.connect(self.on_ok_clicked)
        self.btn_add_another.clicked.connect(self.on_add_another_clicked)
        self.btn_cancel.clicked.connect(self.reject)

    def on_no_date_toggled(self, checked: bool):
        """
        If 'No Due Date' is checked, disable the QDateEdit so
        the user can't pick a date.
        """
        self.due_edit.setDisabled(checked)

    def on_due_date_changed(self, new_date):
        """
        If the user picks or changes the date, automatically uncheck 
        the "No Due Date" checkbox.
        """
        if self.no_date_checkbox.isChecked():
            self.no_date_checkbox.setChecked(False)

    def _collect_current_item(self):
        """
        Gather what's currently typed in the fields:
          - name (required)
          - due (if No Due Date not checked)
          - priority
          - recurrence
        Return as a dict, or None if there's no name.
        """
        name_str = self.name_edit.text().strip()
        if not name_str:
            return None  # user must provide a name

        if self.no_date_checkbox.isChecked():
            due_str = ""
        else:
            due_str = self.due_edit.date().toString("yyyy-MM-dd")

        # If priority is "(None)", we store ""
        prio_selected = self.priority_combo.currentText()
        prio_str = "" if prio_selected == "(None)" else prio_selected

        # Recurrence from dropdown
        rec_str = self.recurrence_combo.currentText()

        return {
            "name": name_str,
            "due": due_str,
            "priority": prio_str,
            "recurrence": rec_str
        }

    def on_ok_clicked(self):
        """
        Gather current fields into a dict, append to self.new_items,
        then close the dialog.
        """
        current_item = self._collect_current_item()
        if current_item:
            self.new_items.append(current_item)
        self.accept()

    def on_add_another_clicked(self):
        """
        Gather the current fields, add to self.new_items,
        then reset the fields so the user can add another.
        """
        current_item = self._collect_current_item()
        if current_item:
            self.new_items.append(current_item)

        # Reset fields for the next item
        self.name_edit.clear()
        self.name_edit.setFocus()

        self.no_date_checkbox.setChecked(True)
        from PyQt6.QtCore import QDate
        self.due_edit.setDate(QDate.currentDate())

        self.priority_combo.setCurrentIndex(0)
        self.recurrence_combo.setCurrentIndex(0)


class ClickDeselectTreeWidget(QTreeWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.pos())
            if not index.isValid():
                self.clearSelection()
        super().mousePressEvent(event)

    def dropEvent(self, event):
        super().dropEvent(event)

        parent_panel = self.parentWidget()
        while parent_panel and not hasattr(parent_panel, "_update_undone_counts_for_all"):
            parent_panel = parent_panel.parentWidget()

        if parent_panel and hasattr(parent_panel, "_update_undone_counts_for_all"):
            # Re-run undone counts
            parent_panel._update_undone_counts_for_all()

            # Also reorder all top-level (and children) if desired
            self._reorder_entire_tree(parent_panel)

    def _reorder_entire_tree(self, panel):
        """Reorder all top-level items and each parent's children so done items are last."""
        for i in range(panel.tree.topLevelItemCount()):
            parent_item = panel.tree.topLevelItem(i)
            panel.reorder_items_in(parent_item)  # reorder each parent's children

# >>> NEW <<< 
class RecurrenceManager:
    """
    Manages the recurring tasks stored in C:\\EnhancedFileExplorer\\data\\recurrence.json.
    Provides:
      - load_data() / save_data()
      - add_or_update_recurrence(...)
      - remove_recurrence(...)
      - check_and_spawn_recurrences(...)
      - handle_completion_of_recurring(...)
      - get_next_month_date(...) for monthly logic
    """
    def __init__(self, parent_panel=None):
        import os, json
        self.parent_panel = parent_panel
        self.recurrence_file_path = r"C:\EnhancedFileExplorer\data\recurrence.json"
        self.data = {}
        self.load_data()

    def load_data(self):
        if not os.path.exists(self.recurrence_file_path):
            self.data = {}
            return
        try:
            with open(self.recurrence_file_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except:
            self.data = {}

    def save_data(self):
        import os, json
        try:
            os.makedirs(os.path.dirname(self.recurrence_file_path), exist_ok=True)
            with open(self.recurrence_file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"[ERROR] Could not save {self.recurrence_file_path}: {e}")

    def add_or_update_recurrence(self, task_uuid, name, frequency, due_date, priority=""):
        """
        Create or update an entry for a recurring task.
        'frequency' can be: 'None', 'Daily', 'Weekly', 'Monthly'.
        'due_date' is the next due date in 'YYYY-MM-DD' format.
        """
        if frequency == "None":
            # If user explicitly says no recurrence, remove if it exists
            if task_uuid in self.data:
                self.data.pop(task_uuid)
                self.save_data()
            return

        # If monthly, store the 'original_due_day' for next month logic
        import datetime
        original_day = None
        if frequency == "Monthly" and due_date:
            try:
                dt = datetime.datetime.strptime(due_date, "%Y-%m-%d")
                original_day = dt.day
            except:
                pass

        self.data[task_uuid] = {
            "name": name,
            "frequency": frequency,
            "next_due_date": due_date,
            "priority": priority,
            "original_due_day": original_day,
            "shift_weekends": True,  # always shift weekends
        }
        self.save_data()

    def remove_recurrence(self, task_uuid):
        if task_uuid in self.data:
            del self.data[task_uuid]
            self.save_data()

    def check_and_spawn_recurrences(self):
        """
        Called daily (just after midnight). If 'today' is exactly
        the day BEFORE an item's next_due_date, we spawn it in the to-do panel.
        """
        import datetime
        if not self.parent_panel:
            return

        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        for task_uuid, rec in list(self.data.items()):
            due_str = rec.get("next_due_date", "")
            if not due_str or rec.get("frequency", "None") == "None":
                continue

            try:
                dt_due = datetime.datetime.strptime(due_str, "%Y-%m-%d").date()
                # If today == (due_date - 1 day)
                if (dt_due - datetime.timedelta(days=1)).strftime("%Y-%m-%d") == today_str:
                    # Spawn a new item for this recurrence
                    self.parent_panel.spawn_recurring_item(task_uuid, rec)
            except:
                pass

    def handle_completion_of_recurring(self, task_uuid):
        """
        Called when the user checks off (completes) a recurring item.
        We bump the next_due_date by 1 day/week/month, etc.
        """
        import datetime
        if task_uuid not in self.data:
            return

        rec = self.data[task_uuid]
        freq = rec.get("frequency", "None")
        due_str = rec.get("next_due_date", "")
        if not due_str:
            return

        try:
            old_dt = datetime.datetime.strptime(due_str, "%Y-%m-%d")
        except:
            return

        new_dt = old_dt
        if freq == "Daily":
            new_dt = old_dt + datetime.timedelta(days=1)
        elif freq == "Weekly":
            new_dt = old_dt + datetime.timedelta(days=7)
        elif freq == "Monthly":
            orig_day = rec.get("original_due_day", old_dt.day)
            new_dt = self.get_next_month_date(old_dt, orig_day)

        # Shift weekends to Friday if needed
        if rec.get("shift_weekends", True):
            new_dt = self.shift_if_weekend(new_dt)

        rec["next_due_date"] = new_dt.strftime("%Y-%m-%d")
        self.data[task_uuid] = rec
        self.save_data()

    def shift_if_weekend(self, dt):
        """
        If dt falls on Saturday (5) or Sunday (6), shift back to Friday.
        """
        while dt.weekday() in (5, 6):
            dt = dt - __import__('datetime').timedelta(days=1)
        return dt

    def get_next_month_date(self, old_dt, original_day):
        """
        For 'Monthly' recurrences: increment by 1 month,
        clamp to last valid day if next month is shorter,
        then shift weekend if needed.
        """
        import datetime, calendar
        year = old_dt.year
        month = old_dt.month
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

        # max day in that new month
        days_in_new_month = calendar.monthrange(year, month)[1]
        day = min(original_day, days_in_new_month)
        return datetime.datetime(year, month, day)
    
# >>> NEW <<<
class ManageRecurringItemsDialog(QDialog):
    """
    Allows user to see all recurring tasks from recurrence.json,
    and Edit or Remove them.
    """
    def __init__(self, recurrence_manager, parent=None):
        super().__init__(parent)
        self.recurrence_manager = recurrence_manager
        self.setWindowTitle("Manage Recurring Items")
        self.resize(600, 300)

        main_layout = QVBoxLayout(self)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Frequency", "Next Due Date", "Priority"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        main_layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_edit = QPushButton("Edit Recurrence")
        self.btn_remove = QPushButton("Remove Recurrence")
        self.btn_close = QPushButton("Close")
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_close)
        main_layout.addLayout(btn_row)

        self.btn_edit.clicked.connect(self.on_edit_clicked)
        self.btn_remove.clicked.connect(self.on_remove_clicked)
        self.btn_close.clicked.connect(self.accept)

        self.setLayout(main_layout)
        self.populate_table()

    def populate_table(self):
        data = self.recurrence_manager.data
        self.table.setRowCount(len(data))
        for row_idx, (task_uuid, info) in enumerate(data.items()):
            name_item = QTableWidgetItem(info.get("name", "Untitled"))
            freq_item = QTableWidgetItem(info.get("frequency", "None"))
            due_item = QTableWidgetItem(info.get("next_due_date", ""))
            prio_item = QTableWidgetItem(info.get("priority", ""))

            # Store uuid in the name column's user data
            name_item.setData(Qt.ItemDataRole.UserRole, task_uuid)

            self.table.setItem(row_idx, 0, name_item)
            self.table.setItem(row_idx, 1, freq_item)
            self.table.setItem(row_idx, 2, due_item)
            self.table.setItem(row_idx, 3, prio_item)

    def on_edit_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        task_uuid = name_item.data(Qt.ItemDataRole.UserRole)
        if not task_uuid:
            return

        rec = self.recurrence_manager.data.get(task_uuid, None)
        if not rec:
            return

        dlg = EditRecurrenceDialog(rec, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated_rec = dlg.get_updated_data()
            self.recurrence_manager.data[task_uuid] = updated_rec
            self.recurrence_manager.save_data()
            self.populate_table()

    def on_remove_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        task_uuid = name_item.data(Qt.ItemDataRole.UserRole)
        if not task_uuid:
            return

        self.recurrence_manager.remove_recurrence(task_uuid)
        self.populate_table()

# >>> NEW <<<
class EditRecurrenceDialog(QDialog):
    """
    Lets the user change the recurrence settings: name, frequency, next due date, priority.
    """
    def __init__(self, rec_data, parent=None):
        super().__init__(parent)
        self.rec_data = dict(rec_data)  # copy
        self.setWindowTitle("Edit Recurrence")
        self.resize(400, 200)

        self.layout = QVBoxLayout(self)

        # Name
        self.lbl_name = QLabel("Name:")
        self.edt_name = QLineEdit(self.rec_data.get("name", "Untitled"))
        self.layout.addWidget(self.lbl_name)
        self.layout.addWidget(self.edt_name)

        # Frequency
        self.lbl_freq = QLabel("Frequency:")
        self.cmb_freq = QComboBox()
        self.cmb_freq.addItems(["None", "Daily", "Weekly", "Monthly"])
        current_freq = self.rec_data.get("frequency", "None")
        if current_freq in ["None", "Daily", "Weekly", "Monthly"]:
            self.cmb_freq.setCurrentText(current_freq)
        self.layout.addWidget(self.lbl_freq)
        self.layout.addWidget(self.cmb_freq)

        # Next Due Date
        self.lbl_nd = QLabel("Next Due Date:")
        self.dte_nd = QDateEdit()
        self.dte_nd.setCalendarPopup(True)
        from datetime import datetime
        nd_str = self.rec_data.get("next_due_date", "")
        default_date = QDate.currentDate()
        if nd_str:
            try:
                dt = datetime.strptime(nd_str, "%Y-%m-%d")
                default_date = QDate(dt.year, dt.month, dt.day)
            except:
                pass
        self.dte_nd.setDate(default_date)
        self.layout.addWidget(self.lbl_nd)
        self.layout.addWidget(self.dte_nd)

        # Priority
        self.lbl_prio = QLabel("Priority:")
        self.cmb_prio = QComboBox()
        self.cmb_prio.addItems(["", "Low", "Medium", "High", "Critical"])
        current_prio = self.rec_data.get("priority", "")
        if current_prio in ["", "Low", "Medium", "High", "Critical"]:
            self.cmb_prio.setCurrentText(current_prio)
        self.layout.addWidget(self.lbl_prio)
        self.layout.addWidget(self.cmb_prio)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        btn_row.addWidget(self.btn_ok)
        btn_row.addWidget(self.btn_cancel)
        self.layout.addLayout(btn_row)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        self.setLayout(self.layout)

    def get_updated_data(self):
        updated = dict(self.rec_data)
        updated["name"] = self.edt_name.text().strip()
        updated["frequency"] = self.cmb_freq.currentText()
        nd_qdate = self.dte_nd.date()
        updated["next_due_date"] = nd_qdate.toString("yyyy-MM-dd")
        updated["priority"] = self.cmb_prio.currentText()
        return updated



class DateEditDelegate(QStyledItemDelegate):
    """
    A delegate that provides a QDateEdit editor for date columns.
    """

    def createEditor(self, parent, option, index):
        # Create a QDateEdit with calendar popup
        editor = QDateEdit(parent)
        editor.setCalendarPopup(True)
        # Set a preferred date format
        editor.setDisplayFormat("yyyy-MM-dd")
        return editor

    def setEditorData(self, editor, index):
        # Get the existing text in the item
        text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        # Attempt to parse it as yyyy-MM-dd
        date_value = QDate.fromString(text, "yyyy-MM-dd")
        if date_value.isValid():
            editor.setDate(date_value)
        else:
            # Fallback if existing text isn't a valid date
            editor.setDate(QDate.currentDate())

    def setModelData(self, editor, model, index):
        # Convert the QDate back to a string
        date_str = editor.date().toString("yyyy-MM-dd")
        # Write it into the model (which updates the QTreeWidgetItem text)
        model.setData(index, date_str, Qt.ItemDataRole.EditRole)


UUID_ROLE = Qt.ItemDataRole.UserRole + 100

class ToDoPanel(QDockWidget):
    """
    A robust To-Do panel with:
      - 4 columns: (0=Name, 1=Count, 2=DueDate, 3=Priority)
      - Checkboxes to mark tasks done (strike out, move to bottom)
      - Drag-and-drop rearranging
      - Recurring-task logic via RecurrenceManager
      - etc.

    This version uses a QTimer-based "debounce" approach to reduce
    repeated saves. Instead of saving *every time* we check a box
    or slightly modify an item, we wait a short period of inactivity.
    """

    class ToDoPanel(QDockWidget):
        """
        A robust To-Do panel with:
        - 4 columns: (0=Name, 1=Count, 2=DueDate, 3=Priority)
        - Checkboxes to mark tasks done (strike out, move to bottom)
        - Drag-and-drop rearranging
        - Recurring-task logic via RecurrenceManager
        - etc.

        This version uses a QTimer-based "debounce" approach to reduce
        repeated saves. Instead of saving *every time* we check a box
        or slightly modify an item, we wait a short period of inactivity.
        """

    def __init__(self, parent=None):
        super().__init__(parent)

        # ----------------------------------------------------------------
        # 1) Basic Panel Setup
        # ----------------------------------------------------------------
        self.overdue_today_item = None
        self.my_day_item = None

        self.setWindowTitle("To-Do")
        self.setTitleBarWidget(QWidget(self))  # Hide default dock title bar
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        self.main_widget = QWidget()
        self.setWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)
        self.main_widget.setLayout(self.layout)

        # ----------------------------------------------------------------
        # 2) Debounce Timer for Saving
        # ----------------------------------------------------------------
        self.save_timer = QTimer(self)
        self.save_timer.setInterval(2000)  # 2-second delay
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.perform_delayed_save)

        # ----------------------------------------------------------------
        # 3) Recurrence Manager (NEW)
        # ----------------------------------------------------------------
        self.recurrence_manager = RecurrenceManager(parent_panel=self)

        # ----------------------------------------------------------------
        # 4) Quick Add Bar with Additional Buttons
        # ----------------------------------------------------------------
        top_row = QHBoxLayout()

        # Quick add input for new items
        self.quick_add_input = QLineEdit()
        self.quick_add_input.setPlaceholderText("New item...")
        top_row.addWidget(self.quick_add_input, 1)
        self.quick_add_input.returnPressed.connect(self.handle_quick_add)

        # Add Parent Button
        self.add_parent_button = QToolButton(self)
        self.add_parent_button.setIcon(QIcon("C:/EnhancedFileExplorer/assets/icons/diff.svg"))
        self.add_parent_button.setToolTip("Add Parent List")
        self.add_parent_button.clicked.connect(self.add_parent_list_dialog)
        top_row.addWidget(self.add_parent_button)

        # Add Subtask Button
        self.add_subtask_button = QToolButton(self)
        self.add_subtask_button.setIcon(QIcon("C:/EnhancedFileExplorer/assets/icons/plus.svg"))
        self.add_subtask_button.setToolTip("Add Subtask")
        self.add_subtask_button.clicked.connect(self.add_subtask_with_check)
        top_row.addWidget(self.add_subtask_button)

        # Remove Selected Button
        self.remove_button = QToolButton(self)
        self.remove_button.setIcon(QIcon("C:/EnhancedFileExplorer/assets/icons/trash-2.svg"))
        self.remove_button.setToolTip("Remove Selected")
        self.remove_button.clicked.connect(self.remove_selected_item)
        top_row.addWidget(self.remove_button)

        # Clear All Checked Items Button
        self.clear_checked_button = QToolButton(self)
        self.clear_checked_button.setIcon(QIcon("C:/EnhancedFileExplorer/assets/icons/eraser.svg"))
        self.clear_checked_button.setToolTip("Clear All Checked Items")
        self.clear_checked_button.clicked.connect(self.clear_all_checked_items)
        top_row.addWidget(self.clear_checked_button)

        self.layout.addLayout(top_row)

        # ----------------------------------------------------------------
        # 5) The Tree Widget
        # ----------------------------------------------------------------
        self.tree = ClickDeselectTreeWidget()
        self.tree.setHeaderLabels(["Task / Project", "Count", "Due Date", "Priority"])
        self.tree.setRootIsDecorated(True)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

        # Make columns resizable
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)

        # Optionally set an initial width
        self.tree.setColumnWidth(0, 190)

        # Allow item editing (double-click, select-click, F2)
        self.tree.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )

        # DateEditDelegate on column 2
        self.due_date_delegate = DateEditDelegate(self.tree)
        self.tree.setItemDelegateForColumn(2, self.due_date_delegate)

        self.layout.addWidget(self.tree)

        # Context menu on right-click
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

        # Listen for item changes (e.g., checkbox toggles, text edits)
        self.tree.itemChanged.connect(self.on_item_changed)

        # ----------------------------------------------------------------
        # 6) Load Existing Tasks, Ensure Special Lists
        # ----------------------------------------------------------------
        self.load_tasks_from_file("tasks.json")
        self._ensure_special_lists_exist()
        self._rebuild_overdue_today_list()

        # ----------------------------------------------------------------
        # 7) Auto-Save, Daily Check for Recurrences
        # ----------------------------------------------------------------
        self.setup_auto_save()

        # Timer to check daily recurrences at or after midnight
        self.daily_check_timer = QTimer(self)
        self.daily_check_timer.setInterval(60_000)  # check every minute
        self.daily_check_timer.timeout.connect(self.daily_recurrence_check)
        self.daily_check_timer.start()

        # Keep track of the last day we triggered the daily check
        self.last_check_date = None

    def daily_recurrence_check(self):
        """
        Called every minute. If local time >= 00:01
        and we haven't checked yet today, run check_and_spawn_recurrences().
        """
        now = datetime.now()
        if now.hour == 0 and now.minute >= 1:
            today_str = now.strftime("%Y-%m-%d")
            if self.last_check_date != today_str:
                self.last_check_date = today_str
                self.recurrence_manager.check_and_spawn_recurrences()

    def spawn_recurring_item(self, task_uuid, rec_data):
        """
        Called by the RecurrenceManager to create a new item the day before it's due.
        """
        name = rec_data.get("name", "Unnamed Recurring")
        due_str = rec_data.get("next_due_date", "")
        prio_str = rec_data.get("priority", "")

        new_item = create_item(
            [name, "", due_str, prio_str],
            is_checkable=True,
            is_editable=True,
            is_draggable=True,
            is_droppable=True
        )
        # set the existing UUID so we can track it
        new_item.setData(0, UUID_ROLE, task_uuid)

        # highlight if needed
        if due_str:
            self.apply_due_date_highlight(new_item)
        if prio_str:
            self._apply_priority_color(new_item, prio_str)

        self.tree.addTopLevelItem(new_item)
        new_item.setExpanded(True)
        self._update_undone_counts_for_all()
        self.save_tasks_to_file("tasks.json")

    # ─────────────────────────────────────────────────────────────────────
    # Debounce Save
    # ─────────────────────────────────────────────────────────────────────

    def _update_tooltip_for_item(self, item: QTreeWidgetItem):
        """Makes the item’s column-0 tooltip match the item's full text."""
        item.setToolTip(0, item.text(0))

    def on_header_double_clicked(self, logical_index: int):
        """
        Auto-size the double-clicked column to contents, then revert
        to Interactive so user can keep dragging if desired.
        """
        header = self.tree.header()
        header.setSectionResizeMode(logical_index, QHeaderView.ResizeMode.ResizeToContents)
        QTimer.singleShot(
            0,
            lambda: header.setSectionResizeMode(logical_index, QHeaderView.ResizeMode.Interactive)
        )

    def _on_sort_indicator_changed(self, logical_index, order):
        """
        Called whenever the user changes the sort column or sort order
        by clicking the header. We'll re-pin 'My Day' at index 0.
        """
        self.pin_my_day_on_top()

    def pin_my_day_on_top(self):
        """
        Finds the top-level item named 'My Day', removes it, and reinserts
        it at index 0 so it remains pinned at the top.
        """
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.text(0) == "My Day":
                item = self.tree.takeTopLevelItem(i)
                self.tree.insertTopLevelItem(0, item)
                break


    # -------------------------------------------------------------------
    # Quick Add
    # -------------------------------------------------------------------
    
    def handle_quick_add(self):
        text = self.quick_add_input.text().strip()
        if not text:
            return

        selected_items = self.tree.selectedItems()
        if selected_items:
            parent_item = selected_items[0]
            new_child = create_item([text, "", "", ""], True, True, True, True)
            parent_item.addChild(new_child)
            parent_item.setExpanded(True)
        else:
            new_parent = create_item([text, "", "", ""], True, True, True, True, user_data={"isParent": True})
            self.tree.addTopLevelItem(new_parent)
            new_parent.setExpanded(True)

        self._update_undone_counts_for_all()
        self.save_tasks_to_file("tasks.json")
        self.quick_add_input.clear()

    def add_quick_task(self):
        text = self.quick_add_input.text().strip()
        if not text:
            return

        # Create a SafeTreeItem
        new_child = create_item(
            [text, "", "", ""],
            is_checkable=True,
            is_editable=True,
            is_draggable=True,
            is_droppable=True
        )
        # Optionally set the initial check state (unchecked)
        new_child.setCheckState(0, Qt.CheckState.Unchecked)

        # Also set tooltip to "ChildName - MyDayName"
        my_day_name = self.my_day_item.text(0)  # typically "My Day"
        new_child.setToolTip(0, f"{text} - {my_day_name}")

        # Add under My Day
        self.my_day_item.addChild(new_child)
        self.my_day_item.setExpanded(True)
        self.quick_add_input.clear()

        # Recalc undone counts for My Day
        self._update_undone_counts_recursively(self.my_day_item)

        # Save once after the new task is added
        self.save_tasks_to_file("tasks.json")


    # -------------------------------------------------------------------
    # Parent List Creation
    # -------------------------------------------------------------------
    def add_parent_list_dialog(self):
        dialog = AddItemDialog(self)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted and dialog.new_items:
            for entry in dialog.new_items:
                name_str = entry["name"]
                due_str = entry["due"]
                prio_str = entry["priority"]
                rec_str = entry.get("recurrence", "None")

                new_parent = create_item(
                    [name_str, "", due_str, prio_str],
                    is_checkable=True,
                    is_editable=True,
                    is_draggable=True,
                    is_droppable=True,
                    user_data={"isParent": True}
                )
                gen_uuid = str(uuid.uuid4())
                new_parent.setData(0, UUID_ROLE, gen_uuid)

                if due_str:
                    self.apply_due_date_highlight(new_parent)
                if prio_str:
                    self._apply_priority_color(new_parent, prio_str)

                self.tree.addTopLevelItem(new_parent)

                # If there's recurrence, store it
                self.recurrence_manager.add_or_update_recurrence(
                    gen_uuid, name_str, rec_str, due_str, prio_str
                )

            self._update_undone_counts_for_all()
            self.save_tasks_to_file("tasks.json")


    # -------------------------------------------------------------------
    # Context menu and actions
    # -------------------------------------------------------------------
    def show_context_menu(self, position: QPoint):
        """
        Show a context menu with different actions depending on
        whether the user right-clicked empty space or a particular item.
        """
        item = self.tree.itemAt(position)
        if not item:
            # Right-click on empty space
            menu = QMenu(self)

            sort_all_action = menu.addAction("Sort All Lists")
            sort_all_action.triggered.connect(self.sort_all_lists_and_tasks)

            add_parent_list_action = menu.addAction("Add Parent List")
            add_parent_list_action.triggered.connect(self.add_parent_list_dialog)

            menu.addSeparator()

            expand_all_action = menu.addAction("Expand All Lists")
            expand_all_action.triggered.connect(self.expand_all_lists)

            collapse_all_action = menu.addAction("Collapse All Lists")
            collapse_all_action.triggered.connect(self.collapse_all_lists)

            menu.addSeparator()

            clear_checked_action = menu.addAction("Clear All Checked Items")
            clear_checked_action.triggered.connect(self.clear_all_checked_items)

            # Manage Recurring Items
            menu.addSeparator()
            manage_recurring_action = menu.addAction("Manage Recurring Items")
            manage_recurring_action.triggered.connect(self.open_manage_recurring_dialog)

            menu.exec(self.tree.mapToGlobal(position))
            return

        # If user right-clicked on an actual item: your existing item-based menu logic
        self._show_item_context_menu(item)

    def _show_item_context_menu(self, item: QTreeWidgetItem):
        """
        The separate method that builds a context menu for a specific item.
        (Kept distinct for clarity.)
        """
        menu = QMenu(self)
        # confirm the item has a stable UUID
        existing_uuid = item.data(0, UUID_ROLE)
        if not existing_uuid:
            new_uuid = str(uuid.uuid4())
            item.setData(0, UUID_ROLE, new_uuid)

        is_parent_data = item.data(0, Qt.ItemDataRole.UserRole)
        is_parent = bool(is_parent_data and is_parent_data.get("isParent"))

        if is_parent:
            # Parent List context menu
            add_task_action = menu.addAction("Add Sub-Task")
            rename_list_action = menu.addAction("Rename Parent List")
            delete_list_action = menu.addAction("Delete Parent List")

            add_task_action.triggered.connect(lambda: self.add_subtask(item))
            rename_list_action.triggered.connect(lambda: self.rename_parent_list(item))
            delete_list_action.triggered.connect(lambda: self.delete_parent_list(item))

            menu.addSeparator()
            move_my_day_action = menu.addAction("Move to My Day")
            move_my_day_action.triggered.connect(
                lambda: self.on_move_to_my_day_triggered(item.data(0, UUID_ROLE))
            )

            menu.addSeparator()
            set_due_date_action = menu.addAction("Set Due Date")
            clear_due_date_action = menu.addAction("Clear Due Date")
            set_priority_action = menu.addAction("Set Priority")
            clear_priority_action = menu.addAction("Clear Priority")

            set_due_date_action.triggered.connect(lambda: self.set_due_date(item))
            clear_due_date_action.triggered.connect(lambda: self.clear_due_date_value(item))
            set_priority_action.triggered.connect(lambda: self.set_priority(item))
            clear_priority_action.triggered.connect(lambda: self.clear_priority_value(item))

        else:
            # Normal to-do item context menu
            add_subtask_action = menu.addAction("Add Sub-Task")
            move_my_day_action = menu.addAction("Move to My Day")

            add_subtask_action.triggered.connect(lambda: self.add_subtask(item))
            move_my_day_action.triggered.connect(
                lambda: self.on_move_to_my_day_triggered(item.data(0, UUID_ROLE))
            )

            menu.addSeparator()
            if self.is_item_done(item):
                mark_done_action = menu.addAction("Mark as Not Done")
            else:
                mark_done_action = menu.addAction("Mark as Done")
            add_tag_action = menu.addAction("Add Tag")

            mark_done_action.triggered.connect(lambda: self.toggle_done(item))
            add_tag_action.triggered.connect(lambda: self.add_tag_to_item(item))

            menu.addSeparator()
            set_due_date_action = menu.addAction("Set Due Date")
            clear_due_date_action = menu.addAction("Clear Due Date")
            set_priority_action = menu.addAction("Set Priority")
            clear_priority_action = menu.addAction("Clear Priority")

            set_due_date_action.triggered.connect(lambda: self.set_due_date(item))
            clear_due_date_action.triggered.connect(lambda: self.clear_due_date_value(item))
            set_priority_action.triggered.connect(lambda: self.set_priority(item))
            clear_priority_action.triggered.connect(lambda: self.clear_priority_value(item))

            menu.addSeparator()
            delete_action = menu.addAction("Delete Task")
            delete_action.triggered.connect(lambda: self.delete_task(item))

        menu.exec(self.tree.mapToGlobal(self.tree.viewport().mapFromGlobal(QCursor.pos())))

    def open_manage_recurring_dialog(self):
        dlg = ManageRecurringItemsDialog(self.recurrence_manager, self)
        dlg.exec()

    # ─────────────────────────────────────────────────────────────────
    # Clear All Checked Items (invoked by context menu on empty space)
    # ─────────────────────────────────────────────────────────────────
    def clear_all_checked_items(self):
        """
        Gathers all items that are checked in column 0, then deletes them.
        Finally saves once at the end.
        """
        checked_items = []
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            self._gather_checked_items(top_item, checked_items)

        # Delete each item, deferring the final save
        for item in checked_items:
            self.delete_task(item, save_after_delete=False)

        # Now do a single save
        self.save_tasks_to_file("tasks.json")
        print(f"[INFO] Deleted {len(checked_items)} checked items.")

    def _gather_checked_items(self, item, checked_list):
        if item.checkState(0) == Qt.CheckState.Checked:
            checked_list.append(item)

        for i in range(item.childCount()):
            self._gather_checked_items(item.child(i), checked_list)


    def on_move_to_my_day_triggered(self, item_uuid: str):
        """
        Re-find the item by UUID, ensuring we get a fresh pointer.
        Then move it to My Day if it still exists.
        """
        item = self._find_item_by_uuid(item_uuid)
        if not item:
            print(f"[WARNING] Could not find item for UUID: {item_uuid}")
            return

        # Make sure we have a My Day item (create if missing)
        self._ensure_my_day_exists()

        # Now self.my_day_item should exist
        if not self.my_day_item:
            print("[ERROR] No 'My Day' item found or created.")
            return

        self.move_item_to_parent(item, self.my_day_item)


    def rename_parent_list(self, parent_item: QTreeWidgetItem):
        """
        Renames the parent list (like "My Day") to a new user-entered name.
        Autosaves immediately after.
        """
        # Block renaming if this is "My Day"
        if parent_item.text(0) == "My Day":
            QMessageBox.information(
                self,
                "Rename Blocked",
                "You cannot rename 'My Day'."
            )
            return

        new_name, ok = QInputDialog.getText(self, "Rename Parent List", "Enter new name:")
        if ok and new_name.strip():
            parent_item.setText(0, new_name.strip())
            # Update the tooltip so hovering still shows the full text
            parent_item.setToolTip(0, new_name.strip())

            # Finally, save after renaming
            self.save_tasks_to_file("tasks.json")



    def delete_parent_list(self, parent_item: QTreeWidgetItem):
        """
        Deletes the entire parent list (and all tasks under it).
        Asks for user confirmation first.
        """
        list_name = parent_item.text(0)
        reply = QMessageBox.question(
            self,
            "Delete Parent List",
            f"Are you sure you want to delete '{list_name}' and all its tasks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            idx = self.tree.indexOfTopLevelItem(parent_item)
            if idx >= 0:
                self.tree.takeTopLevelItem(idx)
            self.save_tasks_to_file("tasks.json")

    def sort_all_lists_and_tasks(self):
        # Block signals to prevent recursion while we rebuild items
        self.tree.blockSignals(True)
        try:
            """
            Sorts all parent lists (top-level items) and their child tasks 
            alphabetically by name, preserving expansions and check states, 
            with 'My Day' pinned at the top.
            """
            expanded_data = {}
            self._store_expanded_states(self.tree, expanded_data)

            data_list = []
            for i in range(self.tree.topLevelItemCount()):
                parent_item = self.tree.topLevelItem(i)
                data_list.append(self._item_to_dict(parent_item))

            self.tree.clear()

            # Sort parent items by name, pin My Day
            data_list.sort(key=lambda d: d["name"].lower())
            my_day_index = None
            for i, parent_dict in enumerate(data_list):
                if parent_dict["name"] == "My Day":
                    my_day_index = i
                    break
            if my_day_index is not None:
                my_day_dict = data_list.pop(my_day_index)
                data_list.insert(0, my_day_dict)

            # Sort children recursively, rebuild
            for parent_dict in data_list:
                self._sort_children(parent_dict)
                parent_item = self._dict_to_item(parent_dict)
                self.tree.addTopLevelItem(parent_item)

            self._restore_expanded_states(self.tree, expanded_data)
            self.save_tasks_to_file("tasks.json")
            print("[INFO] Sort complete.")

            # Recalculate undone counts
            for i in range(self.tree.topLevelItemCount()):
                parent_item = self.tree.topLevelItem(i)
                self._update_undone_counts_recursively(parent_item)
        finally:
            # Unblock signals so normal itemChanged events can resume
            self.tree.blockSignals(False)


    # -------------------------------------------------------------------
    # Recursive Count Logic
    # -------------------------------------------------------------------
    def _update_undone_counts_for_all(self):
        """
        Recalculate the undone counts for every top-level item
        and all its descendants. If an item has zero undone children,
        we display a blank in column 1; otherwise, we show the number.
        """
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            self._update_undone_counts_recursively(top_item)

    def _update_undone_counts_recursively(self, item: QTreeWidgetItem):
        if not item:
            return
        
        undone_count = 0
        child_count = item.childCount()
        for i in range(child_count):
            child = item.child(i)
            if child.checkState(0) != Qt.CheckState.Checked:
                undone_count += 1

        # Show blank if undone_count == 0, otherwise the number
        if undone_count > 0:
            item.setText(1, str(undone_count))
        else:
            item.setText(1, "")

        # ─────────────────────────────────────────────────────────
        #  BOLD any item that has children
        # ─────────────────────────────────────────────────────────
        font = item.font(0)
        font.setBold(child_count > 0)  # true => bold
        item.setFont(0, font)

        # Recurse for all children
        for i in range(child_count):
            self._update_undone_counts_recursively(item.child(i))

        # Optionally auto-resize the Count column
        self.tree.resizeColumnToContents(1)


    def _sort_children(self, item_dict):
        """Sort children by their 'name' key, then recurse."""
        children = item_dict.get("children", [])
        children.sort(key=lambda c: c["name"].lower())
        for child_dict in children:
            self._sort_children(child_dict)

    def _item_to_dict(self, item: QTreeWidgetItem):
        """
        Convert a QTreeWidgetItem to a Python dict, capturing name,
        check state, expansions, due date, priority, and children.
        """
        data = {
            "name": item.text(0),
            "is_checked": (item.checkState(0) == Qt.CheckState.Checked),
            "expanded": item.isExpanded(),
            # col 2 = Due Date, col 3 = Priority
            "due": item.text(2),
            "priority": item.text(3),
            "children": []
        }

        # If you still want to store a "tags" field, you can do so,
        # but your UI has only 4 columns (0..3), so you can remove or comment out:
        # "tags": item.text(2),

        # user_data if needed
        user_data = item.data(0, Qt.ItemDataRole.UserRole)
        if user_data:
            data["user_data"] = user_data

        for i in range(item.childCount()):
            child_item = item.child(i)
            data["children"].append(self._item_to_dict(child_item))
        return data


    def _dict_to_item(self, data: dict):
        """
        Build a SafeTreeItem from the dict, restoring text,
        check state, expansions, due date, priority, and children.
        """
        name = data.get("name", "")
        due_str = data.get("due", "")
        prio_str = data.get("priority", "")

        # Instead of QTreeWidgetItem, use create_item(...) to get a SafeTreeItem
        item = create_item(
            [name, "", due_str, prio_str],
            is_checkable=True,
            is_editable=True,
            is_draggable=True,
            is_droppable=True
        )

        # Mark checked/unchecked
        if data.get("is_checked", False):
            item.setCheckState(0, Qt.CheckState.Checked)
        else:
            item.setCheckState(0, Qt.CheckState.Unchecked)

        # Expand/collapse
        item.setExpanded(data.get("expanded", False))

        # Restore user_data if present
        if "user_data" in data:
            item.setData(0, Qt.ItemDataRole.UserRole, data["user_data"])

        # Recursively rebuild children
        for child_dict in data.get("children", []):
            child_item = self._dict_to_item(child_dict)
            item.addChild(child_item)

        # If there's a due date, apply the highlight
        if due_str:
            self.apply_due_date_highlight(item)

        return item


    def _store_expanded_states(self, widget_or_item, expanded_data):
        # Single definition that calls _store_expanded_for_subtree
        # to store expansions by id(item)
        from PyQt6.QtWidgets import QTreeWidget
        if isinstance(widget_or_item, QTreeWidget):
            for i in range(widget_or_item.topLevelItemCount()):
                self._store_expanded_for_subtree(widget_or_item.topLevelItem(i), expanded_data)
        else:
            self._store_expanded_for_subtree(widget_or_item, expanded_data)

    def _restore_expanded_states(self, widget_or_item, expanded_data):
        # Single definition that calls _restore_expanded_for_subtree
        # to restore expansions by id(item)
        from PyQt6.QtWidgets import QTreeWidget
        if isinstance(widget_or_item, QTreeWidget):
            for i in range(widget_or_item.topLevelItemCount()):
                self._restore_expanded_for_subtree(widget_or_item.topLevelItem(i), expanded_data)
        else:
            self._restore_expanded_for_subtree(widget_or_item, expanded_data)


    # -------------------------------------------------------------------
    # Subtask, toggling done, moving, tagging, deleting normal tasks
    # -------------------------------------------------------------------

    def add_subtask_with_check(self):
        """
        Helper function to add a subtask only if a parent is selected.
        If no parent is selected, shows a warning.
        """
        parent_item = self.tree.currentItem()
        if not parent_item:
            QMessageBox.warning(self, "Select Parent", "Please select a parent list to add a subtask.")
            return
        self.add_subtask(parent_item)
    
    def add_subtask(self, parent_item: QTreeWidgetItem):
        dialog = AddItemDialog(self)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted and dialog.new_items:
            for entry in dialog.new_items:
                name_str = entry["name"]
                due_str = entry["due"]
                prio_str = entry["priority"]
                rec_str = entry.get("recurrence", "None")

                new_child = create_item([name_str, "", due_str, prio_str], True, True, True, True)
                gen_uuid = str(uuid.uuid4())
                new_child.setData(0, UUID_ROLE, gen_uuid)

                if due_str:
                    self.apply_due_date_highlight(new_child)
                if prio_str:
                    self._apply_priority_color(new_child, prio_str)

                parent_item.addChild(new_child)

                # If there's recurrence, store it
                self.recurrence_manager.add_or_update_recurrence(
                    gen_uuid, name_str, rec_str, due_str, prio_str
                )

            parent_item.setExpanded(True)
            self._update_undone_counts_for_all()
            self.save_tasks_to_file("tasks.json")

    def toggle_done(self, item: QTreeWidgetItem):
        if self.is_item_done(item):
            item.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            item.setCheckState(0, Qt.CheckState.Checked)
        self.save_timer.start()

        # Instead of self.save_tasks_to_file("tasks.json"), do:
        self.save_timer.start()
    
    def is_item_done(self, item: QTreeWidgetItem) -> bool:
        """
        Returns True if the given item is checked (done), otherwise False.
        """
        # Get the check state directly to prevent potential recursion
        check_state = item.checkState(0)
        return check_state == Qt.CheckState.Checked


    def move_item_to_parent(self, item: QTreeWidgetItem, new_parent: QTreeWidgetItem):
        if not item or not new_parent:
            return

        if item is new_parent:
            return

        old_parent = item.parent()
        if old_parent:
            # Removing from child list
            old_parent.removeChild(item)
            self.update_count_for(old_parent)
        else:
            # The item is top-level
            idx = self.tree.indexOfTopLevelItem(item)
            if idx >= 0:
                # 'takeTopLevelItem' returns the pointer
                item = self.tree.takeTopLevelItem(idx)

        new_parent.addChild(item)
        new_parent.setExpanded(True)

        self.update_count_for(new_parent)
        self.save_tasks_to_file("tasks.json")

    def update_count_for(self, parent_item: QTreeWidgetItem):
        undone_children = 0
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.checkState(0) != Qt.CheckState.Checked:
                undone_children += 1
        # Show undone child tasks in col 1
        parent_item.setText(1, str(undone_children))

    def add_tag_to_item(self, item: QTreeWidgetItem):
        tag, ok = QInputDialog.getText(self, "Add Tag", "Enter tag name:")
        if ok and tag.strip():
            existing = item.text(2).strip()  # now col2 is Tag(s)/Status
            tags = existing.split(",") if existing else []
            tags = [t.strip() for t in tags if t.strip()]
            if tag not in tags:
                tags.append(tag)
            item.setText(2, ", ".join(tags))
            self.save_tasks_to_file("tasks.json")

    def delete_task(self, item, save_after_delete=True):
        """
        Removes 'item' from the tree (parent or top-level).
        Then calls _update_undone_counts_for_all().
        If save_after_delete=True, do a final save.
        """
        parent = item.parent()
        if parent:
            parent.removeChild(item)
        else:
            idx = self.tree.indexOfTopLevelItem(item)
            if idx >= 0:
                self.tree.takeTopLevelItem(idx)

        self._update_undone_counts_for_all()

        # A single user action => immediate save is usually fine
        if save_after_delete:
            self.save_tasks_to_file("tasks.json")

    def remove_selected_item(self):
        """
        Removes the currently selected item from the tree.
        If no item is selected, it shows a warning.
        """
        selected_item = self.tree.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Remove Selected", "Please select an item to remove.")
            return
        self.delete_task(selected_item)

    # -------------------------------------------------------------------
    # Done-state (checkbox) handling
    # -------------------------------------------------------------------
    
    def on_item_changed(self, item: QTreeWidgetItem, column: int):
        if not self._is_valid_item(item):
            return

        self._begin_update()
        try:
            # Only do this logic if column 0 changed (the checkbox)
            if column == 0:
                has_checkbox = False
                try:
                    check_state = item.checkState(0)
                    has_checkbox = True
                except:
                    pass

                if has_checkbox:
                    is_done = (item.checkState(0) == Qt.CheckState.Checked)
                    parent = item.parent()

                    # ─────────────────────────────────────────────────────────
                    # 1) If this item is in "Overdue / Today," sync the real item
                    #    so it has the same check state & styling right away
                    # ─────────────────────────────────────────────────────────
                    if parent and parent.text(0) == "Overdue / Today":
                        mirror_data = item.data(0, Qt.ItemDataRole.UserRole)
                        if mirror_data and "mirror_uuid" in mirror_data:
                            real_item = self._find_item_by_uuid(mirror_data["mirror_uuid"])
                            if real_item:
                                # Sync the real item’s checkbox
                                real_item.setCheckState(0, item.checkState(0))

                                # Apply strikeout & color to the real item
                                is_done_real = (real_item.checkState(0) == Qt.CheckState.Checked)
                                real_font = real_item.font(0)
                                if is_done_real:
                                    real_font.setStrikeOut(True)
                                    real_item.setFont(0, real_font)
                                    for c in (0, 1, 2, 3):
                                        real_item.setForeground(c, Qt.GlobalColor.darkGray)

                                    # If it's recurring, update next due date
                                    real_uuid = real_item.data(0, UUID_ROLE)
                                    if real_uuid:
                                        self.recurrence_manager.handle_completion_of_recurring(real_uuid)
                                else:
                                    real_font.setStrikeOut(False)
                                    real_item.setFont(0, real_font)
                                    for c in (0, 1, 2, 3):
                                        real_item.setForeground(c, Qt.GlobalColor.white)

                    # ─────────────────────────────────────────────────────────
                    # 2) Strikeout & color changes for *this* item (mirror or normal)
                    # ─────────────────────────────────────────────────────────
                    font = item.font(0)
                    if is_done:
                        font.setStrikeOut(True)
                        item.setFont(0, font)
                        for c in (0, 1, 2, 3):
                            item.setForeground(c, Qt.GlobalColor.darkGray)

                        # If this item is recurring, update next due date
                        task_uuid = item.data(0, UUID_ROLE)
                        if task_uuid:
                            self.recurrence_manager.handle_completion_of_recurring(task_uuid)
                    else:
                        font.setStrikeOut(False)
                        item.setFont(0, font)
                        for c in (0, 1, 2, 3):
                            item.setForeground(c, Qt.GlobalColor.white)

                    # Reorder so done items go to the bottom, update undone counts, etc.
                    QTimer.singleShot(0, lambda: self.reorder_items_in(parent if parent else None))
                    self._update_undone_counts_for_all()
                    self.save_timer.start()

            # If user changed the "Due Date" (column 2), re-highlight
            elif column == 2:
                self.apply_due_date_highlight(item)
                self.save_timer.start()

        finally:
            self._end_update()

        # Always rebuild Overdue/Today after changes
        self._rebuild_overdue_today_list()

    def _has_flag(self, item: QTreeWidgetItem, flag: Qt.ItemFlag) -> bool:
        """
        Safely check if an item has a specific flag, using bitwise operations
        that avoid recursion issues.
        """
        try:
            # Use direct bitwise comparison
            current_flags = item.flags()
            return (current_flags & flag) == flag
        except (RuntimeError, RecursionError):
            # If we hit recursion or another error, assume the flag is not present
            return False
        
    def _add_flag(self, item: QTreeWidgetItem, flag: Qt.ItemFlag):
        """
        Safely add a flag to an item's flags.
        """
        try:
            # Use flags directly without int conversion
            current_flags = item.flags()
            new_flags = current_flags | flag
            item.setFlags(new_flags)
        except (RuntimeError, RecursionError):
            # In case of error, try a more direct approach
            if isinstance(item, SafeTreeItem) and hasattr(item, 'addFlag'):
                item.addFlag(flag)
        
    def _remove_flag(self, item: QTreeWidgetItem, flag: Qt.ItemFlag):
        """
        Safely remove a flag from an item's flags.
        """
        try:
            # Use flags directly without int conversion
            current_flags = item.flags()
            new_flags = current_flags & ~flag
            item.setFlags(new_flags)
        except (RuntimeError, RecursionError):
            # In case of error, try a more direct approach
            if isinstance(item, SafeTreeItem) and hasattr(item, 'removeFlag'):
                item.removeFlag(flag)
        
    def _set_flags(self, item: QTreeWidgetItem, *flags_to_add, **kwargs):
        """
        Set multiple flags at once, optionally clearing existing flags.
        
        Args:
            item: The QTreeWidgetItem to modify
            *flags_to_add: Qt.ItemFlag values to add
            clear_first: If True, clear all existing flags before adding new ones
        """
        clear_first = kwargs.get('clear_first', False)
        
        try:
            # Directly use the flags rather than trying to convert to int
            if clear_first:
                new_flags = Qt.ItemFlag.NoItemFlags
            else:
                # Get current flags
                new_flags = item.flags()
                
            for flag in flags_to_add:
                new_flags |= flag
                
            # Set the flags directly
            item.setFlags(new_flags)
        except (RuntimeError, RecursionError):
            # In case of error, try a more direct approach for SafeTreeItem
            if isinstance(item, SafeTreeItem) and hasattr(item, 'setMultipleFlags'):
                item.setMultipleFlags(*flags_to_add, clear_first=clear_first)

    def reorder_items_in(self, parent: QTreeWidgetItem | None):
        # Save the current vertical & horizontal scroll positions
        v_scroll_value = self.tree.verticalScrollBar().value()
        h_scroll_value = self.tree.horizontalScrollBar().value()

        # Begin batch update
        self._begin_update()
        try:
            """
            Rebuild the parent's (or top-level) children so undone items come first,
            done items come last, preserving each child's expanded state.
            """
            if parent and not self._is_valid_item(parent):
                return

            # 2a) Gather the items from either parent or top-level
            if parent:
                child_count = parent.childCount()
                children = [parent.child(i) for i in range(child_count)]
            else:
                child_count = self.tree.topLevelItemCount()
                children = [self.tree.topLevelItem(i) for i in range(child_count)]

            # Filter out any invalid items
            children = [c for c in children if self._is_valid_item(c)]
            if not children:
                return

            # 2b) Store expansions for these child items (subtree)
            expansions = {}
            for c in children:
                self._store_expanded_for_subtree(c, expansions)

            # 2c) Remove them all from the tree
            if parent:
                for c in children:
                    parent.removeChild(c)
            else:
                for c in children:
                    idx = self.tree.indexOfTopLevelItem(c)
                    if idx >= 0:
                        self.tree.takeTopLevelItem(idx)

            # 2d) Separate undone from done
            undone = []
            done = []
            for c in children:
                if self.is_item_done(c):
                    done.append(c)
                else:
                    undone.append(c)

            # 2e) Re-insert undone items first, then done
            if parent:
                for c in undone:
                    parent.addChild(c)
                for c in done:
                    parent.addChild(c)
            else:
                for c in undone:
                    self.tree.addTopLevelItem(c)
                for c in done:
                    self.tree.addTopLevelItem(c)

            # 2f) Restore expansions at the subtree level
            for c in children:
                if self._is_valid_item(c):
                    self._restore_expanded_for_subtree(c, expansions)

        finally:
            # End batch update
            self._end_update()

            # Restore the scroll positions
            self.tree.verticalScrollBar().setValue(v_scroll_value)
            self.tree.horizontalScrollBar().setValue(h_scroll_value)

    # -------------------------------------------------------------------
    # New: Due Date & Priority
    # -------------------------------------------------------------------
    def set_due_date(self, item: QTreeWidgetItem):
        """
        Prompt the user with a date picker (no time), store it in column 2,
        then apply highlighting. Works for both parent and child items.
        """
        current_text = item.text(2).strip()  # <-- col 2
        current_date = QDate.currentDate()
        if current_text:
            # parse existing date
            date_parsed = QDate.fromString(current_text, "yyyy-MM-dd")
            if date_parsed.isValid():
                current_date = date_parsed

        temp_dialog = QDialog(self)
        temp_dialog.setWindowTitle("Set Due Date")
        layout = QVBoxLayout(temp_dialog)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDate(current_date)
        layout.addWidget(date_edit)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        btn_ok.clicked.connect(temp_dialog.accept)
        btn_cancel.clicked.connect(temp_dialog.reject)

        if temp_dialog.exec() == QDialog.DialogCode.Accepted:
            new_d = date_edit.date()
            date_str = new_d.toString("yyyy-MM-dd")
            item.setText(2, date_str)  # <-- store in col 2
            self.apply_due_date_highlight(item)
            self.save_tasks_to_file("tasks.json")

    def clear_due_date_format(self, item: QTreeWidgetItem):
        """
        Clears the icon in col 0 and background in col 2.
        """
        from PyQt6.QtGui import QBrush, QIcon
        # Clear due-date cell background
        item.setBackground(2, QBrush())
        # Clear the small icon
        item.setIcon(0, QIcon())

    def clear_due_date_value(self, item: QTreeWidgetItem):
        """
        Clear the due date in column 2, remove highlight/icon, then save.
        """
        item.setText(2, "")
        self.clear_due_date_format(item)
        self.save_tasks_to_file("tasks.json")

    def clear_priority_value(self, item: QTreeWidgetItem):
        """
        Clear the priority in column 3, reset text color, then save.
        """
        from PyQt6.QtGui import QColor
        item.setText(3, "")
        item.setForeground(3, QColor("white"))  # revert to default
        self.save_tasks_to_file("tasks.json")



    def _highlight_whole_row(self, item: QTreeWidgetItem, color):
        """
        Applies the given background color to all columns in the row.
        """
        for col in range(item.columnCount()):
            item.setBackground(col, color)

    def set_priority(self, item: QTreeWidgetItem):
        """
        Prompts user for a priority (Low, Medium, High, Critical),
        stores it in column 3, and color-codes that column text
        for better visibility.
        """
        from PyQt6.QtGui import QColor

        # Updated priority list
        priorities = ["Low", "Medium", "High", "Critical"]

        current_prio = item.text(3).strip()  # Column 3 is "Priority"
        if current_prio and current_prio not in priorities:
            # If the current text doesn't match, insert it at front so user sees it in the combo
            priorities.insert(0, current_prio)

        new_priority, ok = QInputDialog.getItem(
            self,
            "Set Priority",
            "Select priority:",
            priorities,
            0,
            False
        )
        if ok and new_priority:
            # Store the chosen priority
            item.setText(3, new_priority)

            # Color-code the text in the Priority column
            if new_priority == "Low":
                item.setForeground(3, QColor(100, 255, 100))   # light green
            elif new_priority == "Medium":
                item.setForeground(3, QColor(255, 215, 0))     # gold-ish
            elif new_priority == "High":
                item.setForeground(3, QColor(255, 150, 0))     # bold orange
            elif new_priority == "Critical":
                item.setForeground(3, QColor(255, 50, 50))      # bright red
            else:
                # If you add more levels, or a fallback
                item.setForeground(3, QColor("white"))

            self.save_tasks_to_file("tasks.json")


    def apply_due_date_highlight(self, item: QTreeWidgetItem):
        """
        If Overdue, color col 2 red + icon in col 0.
        If Due Today, color col 2 orange + icon.
        If Due Tomorrow, color col 2 yellow + icon.
        Otherwise clear both the icon and col 2 highlight.
        """
        from PyQt6.QtGui import QColor
        from datetime import datetime, timedelta

        date_str = item.text(2).strip()  # Column 2 is "Due Date"
        if not date_str:
            self.clear_due_date_format(item)
            return

        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            now = datetime.now()
            today = now.date()
            item_date = dt.date()

            if item_date < today:
                # Overdue => deeper red
                color = QColor(180, 40, 40)
            elif item_date == today:
                # Due Today => deeper orange
                color = QColor(230, 140, 0)
            elif item_date == (today + timedelta(days=1)):
                # Due Tomorrow => golden yellow
                color = QColor(220, 180, 0)
            else:
                # Beyond tomorrow => clear
                self.clear_due_date_format(item)
                return  # exit early

            # If we got a color, set col 2 background + icon in col 0
            item.setBackground(2, color)
            self._set_small_color_icon(item, color)

        except ValueError:
            # If parsing fails, clear
            self.clear_due_date_format(item)

    def _set_small_color_icon(self, item: QTreeWidgetItem, color: QColor):
        """
        Create a small colored pixmap and set it as column 0's icon.
        """
        from PyQt6.QtGui import QPixmap, QPainter, QIcon

        icon_width = 10
        icon_height = 10
        pix = QPixmap(icon_width, icon_height)
        pix.fill(color)

        # (Optional) add a small border:
        painter = QPainter(pix)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawRect(0, 0, icon_width - 1, icon_height - 1)
        painter.end()

        item.setIcon(0, QIcon(pix))

    # -------------------------------------------------------------------
    # Smart List of Overdue and Due items
    # -------------------------------------------------------------------
    def _ensure_special_lists_exist(self):
        """
        Ensures we have both the 'Overdue / Today' smart list pinned at index 0
        and the 'My Day' list pinned at index 1.
        All special behaviors (mirroring, auto-check, etc.) only apply
        to items under these two lists.
        """
        # Make sure Overdue/Today exists
        self._ensure_overdue_today_exists()

        # Make sure My Day exists
        self._ensure_my_day_exists()

        # Optionally, re-pin Overdue/Today at index 0 if it's not already
        od_index = self.tree.indexOfTopLevelItem(self.overdue_today_item)
        if od_index != 0:
            od_item = self.tree.takeTopLevelItem(od_index)
            self.tree.insertTopLevelItem(0, od_item)

        # Optionally, re-pin My Day at index 1 if it's not already
        my_day_index = self.tree.indexOfTopLevelItem(self.my_day_item)
        if my_day_index != 1:
            md_item = self.tree.takeTopLevelItem(my_day_index)
            self.tree.insertTopLevelItem(1, md_item)


    def _ensure_overdue_today_exists(self):
        """
        Check if there's a top-level item named 'Overdue / Today'.
        If missing, create it and insert at index 0.
        """
        self.overdue_today_item = None
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.text(0) == "Overdue / Today":
                self.overdue_today_item = item
                break

        if not self.overdue_today_item:
            # Create a new SafeTreeItem using our factory
            self.overdue_today_item = create_item(
                ["Overdue / Today", "", "", ""],
                is_checkable=False,  # Not checkable
                is_editable=False,   # Not editable 
                is_draggable=True,
                is_droppable=True,
                user_data={"isSmartList": True}
            )

            # Insert at index 0
            self.tree.insertTopLevelItem(0, self.overdue_today_item)

        # Expand it by default
        self.overdue_today_item.setExpanded(True)

        # Make sure it stays pinned at index 0
        index_in_tree = self.tree.indexOfTopLevelItem(self.overdue_today_item)
        if index_in_tree != 0:
            item = self.tree.takeTopLevelItem(index_in_tree)
            self.tree.insertTopLevelItem(0, item)

    def _ensure_misc_tasks_exists(self):
        """
        Ensures a top-level 'Misc Tasks' parent.
        We'll put newly created Overdue/Today tasks here as their real item, if needed.
        """
        self.misc_tasks_item = None
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            if top_item.text(0) == "Misc Tasks":
                self.misc_tasks_item = top_item
                break

        if not self.misc_tasks_item:
            # Create a SafeTreeItem using create_item(...)
            self.misc_tasks_item = create_item(
                ["Misc Tasks", "", "", ""],
                is_checkable=True,
                is_editable=True,
                is_draggable=True,
                is_droppable=True,
                user_data={"isParent": True}
            )
            self.misc_tasks_item.setCheckState(0, Qt.CheckState.Unchecked)

            self.tree.addTopLevelItem(self.misc_tasks_item)

        self.misc_tasks_item.setExpanded(True)

    def _rebuild_overdue_today_list(self):
        """
        Clears all children under 'Overdue / Today' and re-adds any tasks
        (parent or child) that have a due date of 'today or earlier' (and not done).
        Each child is a 'mirror' that references the real item by UUID.
        """
        # If Overdue/Today doesn't exist yet, exit gracefully.
        if not self.overdue_today_item or not self._is_valid_item(self.overdue_today_item):
            return

        # Begin batch update
        self._begin_update()
        try:
            # Clear existing mirrored items
            while self.overdue_today_item.childCount() > 0:
                self.overdue_today_item.takeChild(0)

            # Scan every real item in the tree
            top_count = self.tree.topLevelItemCount()
            for i in range(top_count):
                parent_item = self.tree.topLevelItem(i)
                if not self._is_valid_item(parent_item) or parent_item == self.overdue_today_item:
                    # Skip invalid items or the smart-list item itself
                    continue
                self._scan_and_mirror_overdue_today(parent_item)
        finally:
            # End batch update
            self._end_update()

    def _scan_and_mirror_overdue_today(self, item: QTreeWidgetItem):
        """
        Recursively checks 'item'. If it's overdue or due today (and not done),
        create a mirrored child under self.overdue_today_item.
        Then recurse children.
        """
        if self._is_overdue_or_today(item) and not self.is_item_done(item):
            self._add_mirrored_item(item)

        # Recurse
        for i in range(item.childCount()):
            child = item.child(i)
            self._scan_and_mirror_overdue_today(child)

    def _is_overdue_or_today(self, item: QTreeWidgetItem) -> bool:
        """
        Returns True if 'item' has a due date <= today's date.
        """
        due_str = item.text(2).strip()  # Column 2 is the 'Due Date'
        if not due_str:
            return False

        try:
            dt = datetime.strptime(due_str, "%Y-%m-%d")
        except ValueError:
            return False

        now = datetime.now().date()
        item_date = dt.date()
        return (item_date <= now)
    
    def _get_top_level_parent_name(self, item: QTreeWidgetItem) -> str:
        """
        Climbs up the parent chain until it reaches a top-level item,
        returning .text(0). If 'item' is already top-level, return its own name.

        This helper can be used for Overdue/Today or My Day tasks to show
        "ChildTaskName - ParentListName" in tooltips, etc.
        """
        p = item.parent()
        if not p:
            return item.text(0)
        return self._get_top_level_parent_name(p)

    def _add_mirrored_item(self, real_item: QTreeWidgetItem):
        """
        Creates a 'mirror' task under 'Overdue / Today' that references 'real_item'.
        Uses UUID-based referencing for increased robustness.
        """
        # Ensure real_item has a UUID
        real_item_uuid = self._ensure_item_has_uuid(real_item)
        
        # Copy relevant text columns: 0=Name, 2=Due, 3=Priority
        mirror_text = [
            real_item.text(0),  # Name
            "",                 # No sub-count for mirrored items
            real_item.text(2),  # Due
            real_item.text(3),  # Priority
        ]
        mirror = SafeTreeItem(mirror_text)  # Use SafeTreeItem instead of QTreeWidgetItem

        # Store reference to the real item using UUID instead of direct reference
        mirror.setData(0, Qt.ItemDataRole.UserRole, {"mirror_uuid": real_item_uuid})

        # Set flags using our helper method
        self._set_flags(mirror,
            Qt.ItemFlag.ItemIsUserCheckable,
            Qt.ItemFlag.ItemIsEditable,
            Qt.ItemFlag.ItemIsDragEnabled
        )

        # Match check state
        if real_item.checkState(0) == Qt.CheckState.Checked:
            mirror.setCheckState(0, Qt.CheckState.Checked)
        else:
            mirror.setCheckState(0, Qt.CheckState.Unchecked)

        # Set tooltip to "TaskName - TopLevelParentName"
        top_parent_name = self._get_top_level_parent_name(real_item)
        mirror.setToolTip(0, f"{real_item.text(0)} - {top_parent_name}")

        # Apply the same due-date highlight & priority color to the mirror
        self.apply_due_date_highlight(mirror)
        self._apply_priority_color(mirror, mirror.text(3))

        # Finally, add this mirrored item under Overdue/Today
        self.overdue_today_item.addChild(mirror)

    def _ensure_item_has_uuid(self, item: QTreeWidgetItem) -> str:
        """Ensure item has a UUID and return it."""
        existing_uuid = item.data(0, UUID_ROLE)
        if not existing_uuid:
            generated_uuid = str(uuid.uuid4())
            item.setData(0, UUID_ROLE, generated_uuid)
            return generated_uuid
        return existing_uuid

    # -------------------------------------------------------------------
    # Load / Save from file (with expanded state) - unchanged structure
    # -------------------------------------------------------------------
    def load_tasks_from_file(self, filename: str):
        """
        Loads tasks from JSON, reconstructing top-level parents and their children.
        Skips any "Overdue / Today" if it exists in old data, 
        because we rebuild that list automatically.
        """
        if not os.path.exists(filename):
            # File not found => just ensure My Day is created
            self.tree.clear()
            self._ensure_my_day_exists()
            return

        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.tree.clear()

            # Build each parent
            for parent_name, content in data.items():
                # If old JSON had "Overdue / Today", skip it
                if parent_name == "Overdue / Today":
                    continue

                is_expanded = content.get("expanded", True)
                parent_done = content.get("done", False)
                parent_due = content.get("due", "")
                parent_priority = content.get("priority", "")

                # Use create_item(...) instead of QTreeWidgetItem
                parent_item = create_item(
                    [parent_name, "0", parent_due, parent_priority],
                    is_checkable=True,
                    is_editable=True,
                    is_draggable=True,
                    is_droppable=True,
                    user_data={"isParent": True}
                )

                # Set expanded/collapsed
                parent_item.setExpanded(is_expanded)

                # Check state (done/undone)
                if parent_done:
                    parent_item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    parent_item.setCheckState(0, Qt.CheckState.Unchecked)

                # Highlight due date / priority if needed
                if parent_due:
                    self.apply_due_date_highlight(parent_item)
                if parent_priority:
                    self._apply_priority_color(parent_item, parent_priority)

                # Build children recursively
                for child_data in content.get("items", []):
                    child_item = self.create_item_from_data(child_data)
                    parent_item.addChild(child_item)

                self.tree.addTopLevelItem(parent_item)

            # Always ensure My Day is present (and any other special items you want)
            self._ensure_my_day_exists()

            # Recalc undone counts
            for i in range(self.tree.topLevelItemCount()):
                top_item = self.tree.topLevelItem(i)
                self._update_undone_counts_recursively(top_item)

        except Exception as e:
            print(f"Error loading tasks: {e}")
            self._ensure_my_day_exists()


    def create_item_from_data(self, data_obj: dict):
        """
        Recursively create an item from the data (like a child task),
        restoring name, done state, expanded state, due date, priority, etc.
        """
        text = data_obj.get("text", "Untitled")
        done = data_obj.get("done", False)
        expanded = data_obj.get("expanded", False)
        due_str = data_obj.get("due", "")
        prio_str = data_obj.get("priority", "")
        children_data = data_obj.get("children", [])

        # Build a SafeTreeItem
        item = create_item(
            [text, "", due_str, prio_str],
            is_checkable=True,
            is_editable=True,
            is_draggable=True,
            is_droppable=True
        )

        # If there's a user_data dict in your JSON, restore it
        if "user_data" in data_obj:
            item.setData(0, Qt.ItemDataRole.UserRole, data_obj["user_data"])

        # Mark done or undone
        if done:
            item.setCheckState(0, Qt.CheckState.Checked)
        else:
            item.setCheckState(0, Qt.CheckState.Unchecked)

        # Expand or collapse
        item.setExpanded(expanded)

        # If we have a due date, highlight
        if due_str:
            self.apply_due_date_highlight(item)
        # If we have a priority, color it
        if prio_str:
            self._apply_priority_color(item, prio_str)

        # Rebuild children
        for child_data in children_data:
            child_item = self.create_item_from_data(child_data)
            item.addChild(child_item)

        return item


    def save_tasks_to_file(self, filename: str):
        """
        Saves all tasks (except the Overdue / Today smart list) to a JSON file.
        JSON structure: 
        {
            "ParentName": {
            "expanded": bool,
            "done": bool,
            "due": str,
            "priority": str,
            "items": [ ...children... ]
            },
            ...
        }
        """
        data = {}

        # Loop over all top-level parent items
        for i in range(self.tree.topLevelItemCount()):
            parent_item = self.tree.topLevelItem(i)

            # Skip if this is the Overdue / Today smart list
            is_smart_data = parent_item.data(0, Qt.ItemDataRole.UserRole)
            if is_smart_data and is_smart_data.get("isSmartList"):
                continue

            parent_name = parent_item.text(0)
            parent_done = (parent_item.checkState(0) == Qt.CheckState.Checked)
            parent_due = parent_item.text(2).strip()
            parent_priority = parent_item.text(3).strip()

            parent_data = {
                "expanded": parent_item.isExpanded(),
                "done": parent_done,
                "due": parent_due,
                "priority": parent_priority,
                "items": self.collect_children_data(parent_item)
            }
            data[parent_name] = parent_data

        # Write out to JSON
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            print(f"[INFO] Saved tasks to {filename}")
        except Exception as e:
            print(f"Error saving tasks: {e}")


    def collect_children_data(self, parent_item: QTreeWidgetItem) -> list:
        """
        Recursively gather child items into the 'items' list:
        {
        "text": str  (from col 0),
        "done": bool,
        "expanded": bool,
        "due": str   (from col 2),
        "priority": str (from col 3),
        "children": [...]
        }
        """
        items_data = []
        child_count = parent_item.childCount()

        for i in range(child_count):
            child = parent_item.child(i)
            # Column layout: 0=Name, 1=Count, 2=Due, 3=Priority
            text_value = child.text(0)
            done_value = (child.checkState(0) == Qt.CheckState.Checked)
            expanded_value = child.isExpanded()
            due_value = child.text(2).strip()
            prio_value = child.text(3).strip()

            child_data = {
                "text": text_value,
                "done": done_value,
                "expanded": expanded_value,
                "due": due_value,
                "priority": prio_value,
                "children": self.collect_children_data(child),
            }
            items_data.append(child_data)

        return items_data

    def _find_item_by_uuid(self, target_uuid: str) -> QTreeWidgetItem | None:
        """
        Traverse the entire tree, searching for an item
        whose data(0, UUID_ROLE) == target_uuid.
        Return the item if found, else None.
        """
        top_count = self.tree.topLevelItemCount()
        for i in range(top_count):
            top_item = self.tree.topLevelItem(i)
            found = self._search_item_uuid_recursively(top_item, target_uuid)
            if found:
                return found
        return None


    def _search_item_uuid_recursively(self, item: QTreeWidgetItem, target_uuid: str) -> QTreeWidgetItem | None:
        current_uuid = item.data(0, UUID_ROLE)
        if current_uuid == target_uuid:
            return item

        for i in range(item.childCount()):
            child = item.child(i)
            found = self._search_item_uuid_recursively(child, target_uuid)
            if found:
                return found

        return None
    
    def expand_all_lists(self):
        """
        Expand all top-level items and their children recursively.
        """
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            self._expand_recursively(top_item)

    def _expand_recursively(self, item):
        item.setExpanded(True)
        for i in range(item.childCount()):
            self._expand_recursively(item.child(i))

    def collapse_all_lists(self):
        """
        Collapse all top-level items and their children recursively.
        """
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            self._collapse_recursively(top_item)

    def _collapse_recursively(self, item):
        item.setExpanded(False)
        for i in range(item.childCount()):
            self._collapse_recursively(item.child(i))

    def _ensure_my_day_exists(self):
        found_my_day = None
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            if top_item.text(0) == "My Day":
                found_my_day = top_item
                break

        if not found_my_day:
            # Create a SafeTreeItem using create_item(...)
            found_my_day = create_item(
                ["My Day", "0", "", ""],
                is_checkable=True,
                is_editable=True,
                is_draggable=True,
                is_droppable=True,
                user_data={"isParent": True}
            )
            # Mark it unchecked if you want the "My Day" parent not to be done
            found_my_day.setCheckState(0, Qt.CheckState.Unchecked)

            # Insert at top (index 0)
            self.tree.insertTopLevelItem(0, found_my_day)

        # Always expand My Day
        found_my_day.setExpanded(True)

        self.my_day_item = found_my_day


    def _store_expanded_for_subtree(self, item: QTreeWidgetItem, expansions: dict):
        """
        Recursively store expanded state for 'item' and its children.
        expansions is a dict: expansions[id(item)] = bool
        """
        expansions[id(item)] = item.isExpanded()
        for i in range(item.childCount()):
            self._store_expanded_for_subtree(item.child(i), expansions)

    def _restore_expanded_for_subtree(self, item: QTreeWidgetItem, expansions: dict):
        """
        Recursively restore expanded state from expansions dict
        using item id as the key.
        """
        if id(item) in expansions:
            item.setExpanded(expansions[id(item)])

        for i in range(item.childCount()):
            self._restore_expanded_for_subtree(item.child(i), expansions)

    def _apply_priority_color(self, item: QTreeWidgetItem, priority: str):
        """
        Color the Priority column (col 3) based on priority.
        """
        from PyQt6.QtGui import QColor
        if priority == "Low":
            item.setForeground(3, QColor(100, 255, 100))
        elif priority == "Medium":
            item.setForeground(3, QColor(255, 215, 0))
        elif priority == "High":
            item.setForeground(3, QColor(255, 150, 0))
        elif priority == "Critical":
            item.setForeground(3, QColor(255, 50, 50))
        else:
            # e.g., empty or unknown
            item.setForeground(3, QColor("white"))

    def _begin_update(self):
        """Begin a batch update to prevent intermediate signals."""
        self.tree.blockSignals(True)
        self.tree.setUpdatesEnabled(False)
        
    def _end_update(self):
        """End a batch update and refresh UI."""
        self.tree.setUpdatesEnabled(True)
        self.tree.blockSignals(False)
        self.tree.update()

    def _is_valid_item(self, item):
        """Check if an item is valid and not deleted."""
        if item is None:
            return False
        try:
            # Try to access a property - will fail if item is deleted
            _ = item.text(0)
            return True
        except (RuntimeError, ReferenceError):
            return False
        
    def setup_auto_save(self):
        """Set up periodic auto-save."""
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.setInterval(300000)  # Every 5 minutes
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start()
        
    def auto_save(self):
        """Auto-save with versioning."""
        try:
            # Save to main file
            self.save_tasks_to_file("tasks.json")
            
            # Create a backup directory if it doesn't exist
            backup_dir = "todo_backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                
            # Make a versioned backup (limit to 10 most recent)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"tasks_backup_{timestamp}.json")
            
            # Copy main file to backup
            import shutil
            shutil.copy("tasks.json", backup_path)
            
            # Clean up old backups (keep only 10 most recent)
            backup_files = sorted([f for f in os.listdir(backup_dir) if f.startswith("tasks_backup_")])
            if len(backup_files) > 10:
                for old_file in backup_files[:-10]:
                    os.remove(os.path.join(backup_dir, old_file))
                    
        except Exception as e:
            print(f"Auto-save failed: {e}")

     # ─────────────────────────────────────────────────────────────────
    # Debounce Callback
    # ─────────────────────────────────────────────────────────────────
    def perform_delayed_save(self):
        """Called by QTimer once user stops toggling or editing for 2s."""
        self.save_tasks_to_file("tasks.json")
        print("[DEBUG] Debounced save triggered in ToDoPanel.")