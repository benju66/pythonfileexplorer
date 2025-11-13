from PyQt6.QtWidgets import QDockWidget, QTextEdit
from PyQt6.QtCore import Qt
from modules.preview import FilePreview
import pandas as pd

class PreviewPanel(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("File Preview", parent)

        # Configure the dockable panel
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)

        # TextEdit for displaying previews
        self.preview_text_area = QTextEdit()
        self.preview_text_area.setReadOnly(True)
        self.setWidget(self.preview_text_area)

    def display_preview(self, file_path):
        """Generate and display the preview of the selected file."""
        preview_content = FilePreview.get_preview(file_path)
        self.preview_text_area.setText(preview_content)

# Example usage
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow
    import sys

    app = QApplication(sys.argv)

    main_window = QMainWindow()
    main_window.setWindowTitle("Preview Panel Example")
    main_window.resize(800, 600)

    preview_panel = PreviewPanel(main_window)
    main_window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, preview_panel)

    # Example file path for testing
    example_file_path = "example.txt"
    preview_panel.display_preview(example_file_path)

    main_window.show()
    sys.exit(app.exec())
