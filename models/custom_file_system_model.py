from PyQt6.QtGui import QFileSystemModel, QBrush, QColor, QFont
from PyQt6.QtCore import Qt
import os

# NEW: import undo_manager and RenameCommand
from modules.undo_manager import undo_manager
from modules.undo_commands import RenameCommand

class CustomFileSystemModel(QFileSystemModel):
    def __init__(self, metadata_manager, parent=None):
        """
        metadata_manager: an instance of MetadataManager, enabling:
          - get_item_color(...)
          - get_item_bold(...)
        """
        super().__init__(parent)
        self.metadata_manager = metadata_manager

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        """
        Override setData for inline rename. Instead of directly renaming,
        we push a RenameCommand onto the undo stack.
        """
        if role == Qt.ItemDataRole.EditRole:
            old_path = self.filePath(index)
            new_name = str(value).strip()

            # If user didn't actually change the name, do nothing
            if not new_name or new_name == os.path.basename(old_path):
                return True

            # Push an undoable rename command
            command = RenameCommand(old_path, new_name)
            undo_manager.push(command)

            # If rename failed, e.g. new_path is None, return False
            if command.new_path is None:
                return False

            # Force a layout refresh after rename
            self.layoutChanged.emit()
            return True

        # Otherwise, fall back to default
        return super().setData(index, value, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """
        Override data() to handle:
          - Bold text if self.metadata_manager.get_item_bold(...) is True.
          - Custom text color if self.metadata_manager.get_item_color(...) is set.
        Applies to both files and folders.
        """
        file_path = self.filePath(index)

        # 1) Handle bold text
        if role == Qt.ItemDataRole.FontRole:
            if self.metadata_manager.get_item_bold(file_path):
                font = QFont()
                font.setBold(True)
                return font

        # 2) Handle custom text color
        if role == Qt.ItemDataRole.ForegroundRole:
            color_hex = self.metadata_manager.get_item_color(file_path)
            if color_hex:
                return QBrush(QColor(color_hex))

        # Otherwise, defer to default behavior
        return super().data(index, role)
