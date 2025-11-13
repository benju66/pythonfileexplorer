# ui/draggable_tab_bar.py

from PyQt6.QtWidgets import QTabBar

class DraggableTabBar(QTabBar):
    """
    A custom QTabBar - drag-and-drop functionality disabled to prevent crashes.
    Tabs can still be reordered using setMovable(True) on the parent QTabWidget.
    To detach tabs, use the context menu "Detach Tab" option instead.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Disable drag-and-drop to prevent crashes
        self.setAcceptDrops(False)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        # Allow normal tab clicking/selection
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Disabled drag functionality - just pass through to parent
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # Allow normal mouse release
        super().mouseReleaseEvent(event)
