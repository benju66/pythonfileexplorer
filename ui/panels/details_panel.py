from PyQt6.QtWidgets import QDockWidget, QVBoxLayout, QLabel, QWidget, QLineEdit, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt
from modules.metadata_manager import MetadataManager
import os
import datetime

class DetailsPanel(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("File Details", parent)

        # Configure the dockable panel
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)

        # Metadata Manager
        self.metadata_manager = MetadataManager()

        # Main widget and layout
        self.main_widget = QWidget()
        self.setWidget(self.main_widget)
        self.layout = QVBoxLayout()
        self.main_widget.setLayout(self.layout)

        # Labels for metadata display
        self.file_name_label = QLabel("File Name: ")
        self.file_path_label = QLabel("File Path: ")
        self.file_size_label = QLabel("File Size: ")
        self.last_modified_label = QLabel("Last Modified: ")
        self.last_accessed_label = QLabel("Last Accessed: ")
        self.tags_label = QLabel("Tags: ")

        # Add labels to layout
        self.layout.addWidget(self.file_name_label)
        self.layout.addWidget(self.file_path_label)
        self.layout.addWidget(self.file_size_label)
        self.layout.addWidget(self.last_modified_label)
        self.layout.addWidget(self.last_accessed_label)
        self.layout.addWidget(self.tags_label)

        # Tag editor UI
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Enter tag...")
        self.add_tag_button = QPushButton("Add Tag")
        self.remove_tag_button = QPushButton("Remove Tag")

        tag_editor_layout = QHBoxLayout()
        tag_editor_layout.addWidget(self.tag_input)
        tag_editor_layout.addWidget(self.add_tag_button)
        tag_editor_layout.addWidget(self.remove_tag_button)
        self.layout.addLayout(tag_editor_layout)

        # Connect buttons
        self.add_tag_button.clicked.connect(self.add_tag)
        self.remove_tag_button.clicked.connect(self.remove_tag)

        # File path for current selection
        self.current_file_path = None

    def display_metadata(self, file_path):
        """Display metadata for the selected file or folder."""
        self.current_file_path = file_path

        if not os.path.exists(file_path):
            self.clear_metadata()
            return

        self.file_name_label.setText(f"File Name: {os.path.basename(file_path)}")
        self.file_path_label.setText(f"File Path: {file_path}")

        if os.path.isfile(file_path):
            self.file_size_label.setText(f"File Size: {os.path.getsize(file_path)} bytes")
            self.last_modified_label.setText(f"Last Modified: {datetime.datetime.fromtimestamp(os.path.getmtime(file_path))}")
        elif os.path.isdir(file_path):
            self.file_size_label.setText("File Size: N/A")
            self.last_modified_label.setText("Last Modified: N/A")

        # Handle last accessed
        last_accessed = self.metadata_manager.get_last_accessed(file_path)
        if not last_accessed:
            last_accessed = datetime.datetime.fromtimestamp(os.path.getatime(file_path))
            self.metadata_manager.set_last_accessed(file_path)
        else:
            last_accessed = datetime.datetime.fromtimestamp(last_accessed)
        self.last_accessed_label.setText(f"Last Accessed: {last_accessed}")

        # Tags
        tags = self.metadata_manager.get_tags(file_path)
        self.tags_label.setText(f"Tags: {', '.join(tags) if tags else 'None'}")


    def clear_metadata(self):
        """Clear metadata labels."""
        self.current_file_path = None
        self.file_name_label.setText("File Name: ")
        self.file_path_label.setText("File Path: ")
        self.file_size_label.setText("File Size: ")
        self.last_modified_label.setText("Last Modified: ")
        self.last_accessed_label.setText("Last Accessed: ")
        self.tags_label.setText("Tags: ")

    def add_tag(self):
        """Add a tag to the current file."""
        if self.current_file_path:
            tag = self.tag_input.text().strip()
            if tag:
                self.metadata_manager.add_tag(self.current_file_path, tag)
                self.display_metadata(self.current_file_path)

    def remove_tag(self):
        """Remove a tag from the current file."""
        if self.current_file_path:
            tag = self.tag_input.text().strip()
            if tag:
                self.metadata_manager.remove_tag(self.current_file_path, tag)
                self.display_metadata(self.current_file_path)

# Example usage
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow
    import sys

    app = QApplication(sys.argv)

    main_window = QMainWindow()
    main_window.setWindowTitle("Details Panel Example")
    main_window.resize(800, 600)

    details_panel = DetailsPanel(main_window)
    main_window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, details_panel)

    # Example file path
    example_file_path = "example.txt"
    details_panel.display_metadata(example_file_path)

    main_window.show()
    sys.exit(app.exec())
