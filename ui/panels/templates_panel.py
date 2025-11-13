from PyQt6.QtWidgets import QDockWidget, QListWidget, QVBoxLayout, QWidget, QLabel, QPushButton, QFileDialog
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDrag
from modules.automation import Automation
import os
import json

class TemplatesPanel(QDockWidget):
    def __init__(self, template_dir="C:\\EnhancedFileExplorer\\templates", destination_dir="projects", parent=None):
        super().__init__("Templates", parent)

        # Paths
        self.template_dir = template_dir
        self.destination_dir = destination_dir

        # Configure the dockable panel
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)

        # Main widget and layout
        self.main_widget = QWidget()
        self.setWidget(self.main_widget)
        self.layout = QVBoxLayout()
        self.main_widget.setLayout(self.layout)

        # Label
        self.info_label = QLabel("Drag and drop templates into directories or use the Create button.")
        self.layout.addWidget(self.info_label)

        # Templates list
        self.templates_list = QListWidget()
        self.templates_list.setDragEnabled(True)
        self.layout.addWidget(self.templates_list)

        # Create button
        self.create_button = QPushButton("Create Folder")
        self.create_button.clicked.connect(self.create_folder_from_selected_template)
        self.layout.addWidget(self.create_button)

        # Refresh button
        self.refresh_button = QPushButton("Refresh Templates")
        self.refresh_button.clicked.connect(self.populate_templates)
        self.layout.addWidget(self.refresh_button)

        # Load templates initially
        self.populate_templates()

    def populate_templates(self):
        """Populate the list with available JSON templates."""
        self.templates_list.clear()

        if not os.path.exists(self.template_dir):
            os.makedirs(self.template_dir)

        for template_name in os.listdir(self.template_dir):
            template_path = os.path.join(self.template_dir, template_name)
            if os.path.isfile(template_path) and template_name.endswith(".json"):
                self.templates_list.addItem(template_name)

    def create_folder_from_selected_template(self):
        """Create a folder using the selected JSON template."""
        selected_items = self.templates_list.selectedItems()
        if not selected_items:
            print("No template selected.")
            return

        selected_template_name = selected_items[0].text()
        selected_template_path = os.path.join(self.template_dir, selected_template_name)

        folder_name, ok = QFileDialog.getSaveFileName(self, "Enter Folder Name", self.destination_dir)
        if not ok or not folder_name:
            print("Folder creation canceled.")
            return

        try:
            with open(selected_template_path, "r") as file:
                template_structure = json.load(file)

            folder_path = os.path.join(self.destination_dir, folder_name)
            os.makedirs(folder_path, exist_ok=True)

            for sub_folder in template_structure.get("folders", []):
                os.makedirs(os.path.join(folder_path, sub_folder), exist_ok=True)

            print(f"Folder created: {folder_path}")
        except Exception as e:
            print(f"Failed to create folder: {e}")

    def startDrag(self, dropAction):
        """Enable drag-and-drop for templates."""
        item = self.templates_list.currentItem()
        if item:
            mime_data = QMimeData()
            template_name = item.text()
            template_path = os.path.abspath(os.path.join(self.template_dir, template_name))
            mime_data.setText(template_path)

            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.exec(Qt.DropAction.CopyAction)

# Example usage
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow
    import sys

    app = QApplication(sys.argv)

    main_window = QMainWindow()
    main_window.setWindowTitle("Templates Panel Example")
    main_window.resize(800, 600)

    templates_panel = TemplatesPanel("C:\\EnhancedFileExplorer\\templates", "projects", main_window)
    main_window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, templates_panel)

    main_window.show()
    sys.exit(app.exec())
