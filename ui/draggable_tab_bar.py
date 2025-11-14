# ui/draggable_tab_bar.py

from PyQt6.QtWidgets import QTabBar, QTabWidget
from PyQt6.QtCore import Qt, QMimeData, QPoint, QRect
from PyQt6.QtGui import QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent, QPainter, QPen, QColor
from modules.widget_registry import get_widget_registry

# Custom MIME type for tab drag-and-drop
TAB_WIDGET_MIME_TYPE = "application/x-qtabwidget-widget-id"


class DraggableTabBar(QTabBar):
    """
    A custom QTabBar with drag-and-drop functionality for tabs.
    
    This enables dragging tabs between tab widgets and to external windows.
    The drag operation stores the widget ID in MIME data, which is then
    used during drop to identify and move the widget.
    
    Features:
    - Drag threshold detection (prevents accidental drags)
    - MIME data with widget ID
    - Visual feedback during drag
    - Integration with WidgetRegistry
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Enable drag-and-drop to receive dragEnter/dragMove for visual feedback
        # But we won't accept drop events - let parent handle them
        self.setAcceptDrops(True)
        
        # Drag state tracking
        self.drag_start_pos = None
        self.drag_threshold = 10  # pixels - minimum distance to start drag
        self.is_dragging = False
        
        # Drop indicator line position
        self.drop_indicator_pos = -1  # -1 means no indicator, otherwise x position
        self.drop_indicator_index = -1  # Tab index where drop will occur
        
        # Widget registry for tracking widgets during drag
        self.widget_registry = get_widget_registry()
    
    def mousePressEvent(self, event):
        """
        Handle mouse press event to track drag start position.
        
        Args:
            event: QMouseEvent
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # Store the position where mouse was pressed
            self.drag_start_pos = event.position().toPoint()
            self.is_dragging = False
        else:
            self.drag_start_pos = None
        
        # Allow normal tab clicking/selection
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """
        Handle mouse move event to detect drag threshold and start drag operation.
        
        Args:
            event: QMouseEvent
        """
        # Only handle left button drags
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        
        # If we haven't started dragging yet, check threshold
        if self.drag_start_pos is not None and not self.is_dragging:
            # Calculate distance moved
            distance = (event.position().toPoint() - self.drag_start_pos).manhattanLength()
            
            # If moved beyond threshold, start drag
            if distance > self.drag_threshold:
                # Get the tab index at the drag start position
                tab_index = self.tabAt(self.drag_start_pos)
                
                if tab_index >= 0:
                    # Start the drag operation
                    self.start_drag(tab_index)
                    self.is_dragging = True
                    return
        
        # If already dragging, let Qt handle it
        if self.is_dragging:
            super().mouseMoveEvent(event)
        else:
            # Normal mouse move (not dragging)
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """
        Handle mouse release event to reset drag state.
        
        Args:
            event: QMouseEvent
        """
        # Reset drag state
        self.drag_start_pos = None
        self.is_dragging = False
        
        # Allow normal mouse release
        super().mouseReleaseEvent(event)
    
    def start_drag(self, tab_index: int):
        """
        Start a drag operation for the tab at the specified index.
        
        This method:
        1. Gets the widget from the tab index
        2. Ensures widget is registered in WidgetRegistry
        3. Creates MIME data with widget ID
        4. Starts the drag operation
        
        Args:
            tab_index: Index of the tab to drag
        """
        # Get parent QTabWidget
        parent_tab_widget = self.parent()
        if not isinstance(parent_tab_widget, QTabWidget):
            print("[ERROR] DraggableTabBar parent is not a QTabWidget")
            return
        
        # Get widget from tab index
        widget = parent_tab_widget.widget(tab_index)
        if widget is None:
            print(f"[ERROR] No widget found at tab index {tab_index}")
            return
        
        # Ensure widget is registered (should already be registered, but double-check)
        if not self.widget_registry.is_registered(widget):
            # Register widget if not already registered
            self.widget_registry.register_widget(widget, parent_tab_widget)
            print(f"[DEBUG] Registered widget during drag start: {id(widget)}")
        
        # Create MIME data
        mime_data = QMimeData()
        widget_id_str = str(id(widget))
        mime_data.setData(TAB_WIDGET_MIME_TYPE, widget_id_str.encode('utf-8'))
        
        # Create drag object
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        
        # Set drag pixmap for visual feedback
        # Create a simple pixmap from the tab
        try:
            from PyQt6.QtGui import QPixmap, QPainter, QColor
            tab_icon = self.tabIcon(tab_index)
            if not tab_icon.isNull():
                pixmap = tab_icon.pixmap(16, 16)
            else:
                # Create a simple colored pixmap as fallback
                pixmap = QPixmap(16, 16)
                pixmap.fill(QColor(100, 100, 100, 200))
            drag.setPixmap(pixmap)
            # Set hot spot to center
            drag.setHotSpot(QPoint(8, 8))
        except Exception as e:
            print(f"[DEBUG] Could not create drag pixmap: {e}")
        
        # Start drag operation
        # Qt.DropAction.MoveAction indicates we're moving the widget
        drop_action = drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction)
        
        # Handle drag result
        if drop_action == Qt.DropAction.IgnoreAction:
            # Drag was cancelled or dropped on invalid target
            print(f"[DEBUG] Drag cancelled or ignored for tab {tab_index}")
        elif drop_action == Qt.DropAction.MoveAction:
            # Widget was moved (handled by drop handler)
            print(f"[DEBUG] Tab {tab_index} moved successfully")
        elif drop_action == Qt.DropAction.CopyAction:
            # Widget was copied (if we support copying)
            print(f"[DEBUG] Tab {tab_index} copied")
        
        # Reset drag state
        self.is_dragging = False
        self.drag_start_pos = None
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """
        Handle drag enter event on the tab bar.
        This provides visual feedback when dragging over tabs.
        
        Args:
            event: QDragEnterEvent
        """
        if event.mimeData().hasFormat(TAB_WIDGET_MIME_TYPE):
            event.acceptProposedAction()
            # Update drop indicator
            self._update_drop_indicator(event)
            self.update()  # Trigger repaint
        else:
            super().dragEnterEvent(event)
    
    def dragMoveEvent(self, event: QDragMoveEvent):
        """
        Handle drag move event on the tab bar.
        Updates visual feedback as mouse moves.
        
        Args:
            event: QDragMoveEvent
        """
        if event.mimeData().hasFormat(TAB_WIDGET_MIME_TYPE):
            event.acceptProposedAction()
            # Update drop indicator based on position
            self._update_drop_indicator(event)
            self.update()  # Trigger repaint to show indicator line
        else:
            super().dragMoveEvent(event)
    
    def dragLeaveEvent(self, event):
        """
        Handle drag leave event to reset visual feedback.
        
        Args:
            event: QDragLeaveEvent
        """
        # Reset visual feedback
        self.drop_indicator_pos = -1
        self.drop_indicator_index = -1
        self.update()  # Trigger repaint to remove indicator
        super().dragLeaveEvent(event)
    
    def dropEvent(self, event: QDropEvent):
        """
        Handle drop event on the tab bar.
        Reset visual feedback but don't accept the event - let parent handle it.
        
        Args:
            event: QDropEvent
        """
        # Reset visual feedback
        self.drop_indicator_pos = -1
        self.drop_indicator_index = -1
        self.update()  # Trigger repaint to remove indicator
        
        # Don't accept the event - let it propagate to parent QTabWidget
        # This ensures the parent receives the drop event with correct position
        if event.mimeData().hasFormat(TAB_WIDGET_MIME_TYPE):
            # Don't accept - let parent handle it
            event.ignore()
            # The parent will receive the event automatically
        else:
            super().dropEvent(event)
    
    def _update_drop_indicator(self, event):
        """
        Update the drop indicator line position based on drag event.
        
        Args:
            event: QDragEnterEvent or QDragMoveEvent
        """
        try:
            # Get position relative to tab bar
            pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            
            # Find which tab we're over
            tab_index = self.tabAt(pos)
            
            if tab_index >= 0:
                # Get tab rectangle
                tab_rect = self.tabRect(tab_index)
                
                # Determine if we're dropping before or after the tab
                # Check if mouse is in left half or right half of tab
                tab_center_x = tab_rect.center().x()
                
                if pos.x() < tab_center_x:
                    # Dropping before this tab
                    self.drop_indicator_pos = tab_rect.left()
                    self.drop_indicator_index = tab_index
                else:
                    # Dropping after this tab
                    self.drop_indicator_pos = tab_rect.right()
                    self.drop_indicator_index = tab_index + 1
            else:
                # Not over any tab - determine position based on x coordinate
                if self.count() > 0:
                    # Check if we're on the left or right side
                    if pos.x() < self.width() / 2:
                        # Left side - drop at beginning
                        first_tab_rect = self.tabRect(0)
                        self.drop_indicator_pos = first_tab_rect.left()
                        self.drop_indicator_index = 0
                    else:
                        # Right side - drop at end
                        last_tab_rect = self.tabRect(self.count() - 1)
                        self.drop_indicator_pos = last_tab_rect.right()
                        self.drop_indicator_index = self.count()
                else:
                    # No tabs - drop at position 0
                    self.drop_indicator_pos = pos.x()
                    self.drop_indicator_index = 0
                    
        except Exception as e:
            print(f"[DEBUG] Error updating drop indicator: {e}")
            self.drop_indicator_pos = -1
            self.drop_indicator_index = -1
    
    def paintEvent(self, event):
        """
        Override paint event to draw drop indicator line.
        
        Args:
            event: QPaintEvent
        """
        # Call parent paint event first
        super().paintEvent(event)
        
        # Draw drop indicator line if active
        if self.drop_indicator_pos >= 0:
            painter = QPainter(self)
            pen = QPen(QColor(0, 120, 215), 2)  # Blue line, 2px wide
            painter.setPen(pen)
            
            # Draw vertical line at drop position
            y_top = 0
            y_bottom = self.height()
            painter.drawLine(self.drop_indicator_pos, y_top, self.drop_indicator_pos, y_bottom)
            
            painter.end()
