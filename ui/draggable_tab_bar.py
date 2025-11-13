# ui/draggable_tab_bar.py

from PyQt6.QtWidgets import QTabBar
from PyQt6.QtCore import Qt, QMimeData, QPoint
from PyQt6.QtGui import QDrag

class DraggableTabBar(QTabBar):
    """
    A custom QTabBar allowing drag-and-drop to detach tabs.
    In conjunction with your existing logic, you can call 'detach_main_tab'
    or similar methods to tear the tab off once dropped.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        # Record the mouse press position if it's the left button
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # If left button is pressed and the cursor has moved enough, initiate a drag
        if (event.buttons() & Qt.MouseButton.LeftButton) and self.drag_start_pos:
            distance = (event.pos() - self.drag_start_pos).manhattanLength()
            if distance > 10:  # Drag threshold in pixels
                self.startDrag()
        super().mouseMoveEvent(event)

    def startDrag(self):
        # Prepare a QDrag object with the dragged tab’s index
        drag = QDrag(self)
        mime_data = QMimeData()

        tab_index = self.tabAt(self.drag_start_pos)
        mime_data.setText(str(tab_index))  # Simple way to pass which tab is dragged

        drag.setMimeData(mime_data)

        # Execute the drag with move action
        drop_action = drag.exec(Qt.DropAction.MoveAction)
        # If needed, check drop_action for further logic

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
        super().mouseReleaseEvent(event)
