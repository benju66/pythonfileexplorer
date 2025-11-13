from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QPushButton, QCheckBox
)
from PyQt6.QtCore import Qt
from modules.settings_manager import SettingsManager

class GeneralSettingsTab(QWidget):
    def __init__(self, parent, settings_manager):
        super().__init__()
        self.parent_window = parent
        self.settings_manager = settings_manager
        layout = QVBoxLayout()

        # Theme Options
        theme_label = QLabel("Theme Settings")
        theme_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(theme_label)

        self.dark_mode_toggle = QCheckBox("Enable Dark Mode")
        self.dark_mode_toggle.setChecked(
            self.settings_manager.get_setting("ui_preferences.Enable Dark Mode", False)
        )
        self.dark_mode_toggle.stateChanged.connect(
            lambda state: self.toggle_setting("ui_preferences.Enable Dark Mode", state)
        )
        layout.addWidget(self.dark_mode_toggle)

        # Panel Visibility
        panel_label = QLabel("Panel Visibility")
        panel_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(panel_label)

        # Get current panel settings
        panel_settings = self.settings_manager.get_setting("dockable_panels", {})

        # UPDATED: Add one_note_panel
        panel_configs = {
            "pinned_panel":       "Show Pinned Panel",
            "recent_items_panel": "Show Recent Items Panel",
            "preview_panel":      "Show Preview Panel",
            "details_panel":      "Show Details Panel",
            "bookmarks_panel":    "Show Bookmarks Panel",
            "procore_panel":      "Show Procore Quick Links Panel",
            "to_do_panel":        "Show To-Do Panel",
            "one_note_panel":     "Show OneNote Panel"  # NEW
        }

        self.panel_toggles = {}
        for setting_key, display_name in panel_configs.items():
            checkbox = QCheckBox(display_name)
            is_visible = panel_settings.get(setting_key, True)
            checkbox.setChecked(is_visible)
            # Use a lambda with default argument for setting_key
            checkbox.stateChanged.connect(
                lambda state, key=setting_key: self.toggle_panel(key, state)
            )
            layout.addWidget(checkbox)
            self.panel_toggles[setting_key] = checkbox

        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(layout)

    def toggle_setting(self, setting, state):
        is_enabled = state == Qt.CheckState.Checked.value
        self.settings_manager.update_setting(setting, is_enabled)
        if setting == "ui_preferences.Enable Dark Mode":
            self.parent_window.apply_theme("dark" if is_enabled else "light")

    def toggle_panel(self, panel_key, state):
        is_visible = state == Qt.CheckState.Checked.value
        # Update settings
        self.settings_manager.update_setting(f"dockable_panels.{panel_key}", is_visible)
        
        # Update UI if possible
        if hasattr(self.parent_window, "dock_panels"):
            dock_widget = self.parent_window.dock_panels.get(panel_key)
            if dock_widget:
                dock_widget.setVisible(is_visible)


class AdvancedSettingsTab(QWidget):
    """Advanced settings for AI and automation."""
    def __init__(self, parent):
        super().__init__()
        self.parent_window = parent
        self.settings_manager = SettingsManager()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Advanced AI & Automation Settings"))

        # AI-Powered Search Settings
        self.enable_ai_search = QCheckBox("Enable AI-Powered Search")
        self.enable_ai_search.setChecked(
            self.settings_manager.get_setting("ai_settings.enable_ai_search", False)
        )
        self.enable_ai_search.stateChanged.connect(
            lambda state: self.toggle_setting("ai_settings.enable_ai_search", state)
        )
        layout.addWidget(self.enable_ai_search)

        self.search_inside_files = QCheckBox("Search Inside Files (PDF, DOCX, TXT)")
        self.search_inside_files.setChecked(
            self.settings_manager.get_setting("ai_settings.search_inside_files", False)
        )
        self.search_inside_files.stateChanged.connect(
            lambda state: self.toggle_setting("ai_settings.search_inside_files", state)
        )
        layout.addWidget(self.search_inside_files)

        self.enable_ai_autocomplete = QCheckBox("Enable AI Autocomplete in Search")
        self.enable_ai_autocomplete.setChecked(
            self.settings_manager.get_setting("ai_settings.enable_ai_autocomplete", False)
        )
        self.enable_ai_autocomplete.stateChanged.connect(
            lambda state: self.toggle_setting("ai_settings.enable_ai_autocomplete", state)
        )
        layout.addWidget(self.enable_ai_autocomplete)

        # AI-Powered File Organization
        self.auto_organize_files = QCheckBox("Auto-Organize Files Using AI")
        self.auto_organize_files.setChecked(
            self.settings_manager.get_setting("ai_settings.auto_organize_files", False)
        )
        self.auto_organize_files.stateChanged.connect(
            lambda state: self.toggle_setting("ai_settings.auto_organize_files", state)
        )
        layout.addWidget(self.auto_organize_files)

        self.ai_file_tagging = QCheckBox("Enable Smart AI File Tagging")
        self.ai_file_tagging.setChecked(
            self.settings_manager.get_setting("ai_settings.ai_file_tagging", False)
        )
        self.ai_file_tagging.stateChanged.connect(
            lambda state: self.toggle_setting("ai_settings.ai_file_tagging", state)
        )
        layout.addWidget(self.ai_file_tagging)

        self.ai_duplicate_detection = QCheckBox("Detect & Suggest Duplicate Files")
        self.ai_duplicate_detection.setChecked(
            self.settings_manager.get_setting("ai_settings.ai_duplicate_detection", False)
        )
        self.ai_duplicate_detection.stateChanged.connect(
            lambda state: self.toggle_setting("ai_settings.ai_duplicate_detection", state)
        )
        layout.addWidget(self.ai_duplicate_detection)

        # Cloud & OneDrive AI Integration
        self.ai_keep_folders_local = QCheckBox("Ensure AI-Indexed Folders Stay Local")
        self.ai_keep_folders_local.setChecked(
            self.settings_manager.get_setting("ai_settings.ai_keep_folders_local", False)
        )
        self.ai_keep_folders_local.stateChanged.connect(
            lambda state: self.toggle_setting("ai_settings.ai_keep_folders_local", state)
        )
        layout.addWidget(self.ai_keep_folders_local)

        self.ai_cloud_file_search = QCheckBox("Allow AI Search on Cloud-Only Files")
        self.ai_cloud_file_search.setChecked(
            self.settings_manager.get_setting("ai_settings.ai_cloud_file_search", False)
        )
        self.ai_cloud_file_search.stateChanged.connect(
            lambda state: self.toggle_setting("ai_settings.ai_cloud_file_search", state)
        )
        layout.addWidget(self.ai_cloud_file_search)

        # AI Summarization & Metadata Extraction
        self.ai_file_summarization = QCheckBox("Enable AI File Summarization")
        self.ai_file_summarization.setChecked(
            self.settings_manager.get_setting("ai_settings.ai_file_summarization", False)
        )
        self.ai_file_summarization.stateChanged.connect(
            lambda state: self.toggle_setting("ai_settings.ai_file_summarization", state)
        )
        layout.addWidget(self.ai_file_summarization)

        self.ai_metadata_extraction = QCheckBox("Enable AI-Based Metadata Extraction")
        self.ai_metadata_extraction.setChecked(
            self.settings_manager.get_setting("ai_settings.ai_metadata_extraction", False)
        )
        self.ai_metadata_extraction.stateChanged.connect(
            lambda state: self.toggle_setting("ai_settings.ai_metadata_extraction", state)
        )
        layout.addWidget(self.ai_metadata_extraction)

        self.setLayout(layout)

    def toggle_setting(self, setting, state):
        """Update AI-related settings dynamically."""
        is_enabled = (state == Qt.CheckState.Checked.value)
        self.settings_manager.update_setting(setting, is_enabled)


class SettingsDialog(QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings_manager = settings_manager
        self.parent_window = parent

        layout = QVBoxLayout()
        
        # Tabs
        self.tabs = QTabWidget()
        self.general_tab = GeneralSettingsTab(self.parent_window, self.settings_manager)
        self.advanced_tab = AdvancedSettingsTab(self)
        self.tabs.addTab(self.general_tab, "General")
        self.tabs.addTab(self.advanced_tab, "Advanced")
        layout.addWidget(self.tabs)

        # Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def save_settings(self):
        """Save settings and keep dialog open until explicitly closed."""
        self.settings_manager.save_settings()
        # Apply settings to main window
        if self.parent_window:
            self.parent_window.apply_saved_settings()
        self.accept()

    def open_advanced_settings(self):
        """Switch to the Advanced Settings tab."""
        self.tabs.setCurrentIndex(1)

    def open_advanced_settings_dialog(self):
        """Open the Settings UI with the Advanced tab selected."""
        dialog = SettingsDialog(self.settings_manager, self)
        dialog.tabs.setCurrentIndex(1)  # open advanced tab
        dialog.exec()