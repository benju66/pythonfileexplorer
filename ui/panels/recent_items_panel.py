from PyQt6.QtWidgets import QDockWidget, QListWidget, QVBoxLayout, QPushButton, QWidget
from PyQt6.QtCore import Qt
from modules.metadata_manager import MetadataManager

class RecentItemsPanel(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Recent Items", parent)

        # Initialize metadata manager
        self.metadata_manager = MetadataManager()

        # Configure the dockable panel
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)

        # Main widget and layout
        self.main_widget = QWidget()
        self.setWidget(self.main_widget)
        self.layout = QVBoxLayout()
        self.main_widget.setLayout(self.layout)

        # Recent items list
        self.recent_list = QListWidget()
        self.layout.addWidget(self.recent_list)

        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_recent_items)
        self.layout.addWidget(self.refresh_button)

        # Populate recent items initially
        self.refresh_recent_items()

    def refresh_recent_items(self):
        """Refresh the recent items list."""
        self.recent_list.clear()
        recent_items = self.metadata_manager.get_recent_items()
        for item in recent_items:
            self.recent_list.addItem(item)

    def add_recent_item(self, item_path):
        """Add an item to the recent list."""
        self.metadata_manager.add_recent_item(item_path)
        self.refresh_recent_items()

# Example usage
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow
    import sys

    app = QApplication(sys.argv)

    main_window = QMainWindow()
    main_window.setWindowTitle("Recent Items Panel Example")
    main_window.resize(800, 600)

    recent_items_panel = RecentItemsPanel(main_window)
    main_window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, recent_items_panel)

    main_window.show()
    sys.exit(app.exec())
