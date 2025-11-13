import os
import json
import logging
import base64

class SettingsManager:
    def __init__(self, settings_file="data/settings.json", parent_window=None):
        """Initialize the settings manager and load settings."""
        self.settings_file = settings_file
        self.parent_window = parent_window

        # Updated default settings to include one_note_panel
        self.default_settings = {
            "theme": "light",
            "last_opened_directory": r"C:\\Users\\Burness\\OneDrive - Fendler Patterson Construction, Inc",
            "ui_preferences": {
                "Enable Dark Mode": False,
                "Show Address Bar": True
            },
            "dockable_panels": {
                "pinned_panel": True,
                "recent_items_panel": False,
                "preview_panel": False,
                "details_panel": True,
                "procore_panel": False,
                "bookmarks_panel": False,
                "to_do_panel": True,
                "one_note_panel": False  # NEW: Start hidden by default
            },
            "window_geometry_b64": None,
            "window_state_b64": None,
        }

        self.settings = self.load_settings()

    def load_settings(self):
        """Load settings from the JSON file and ensure missing settings are added."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as file:
                    loaded_settings = json.load(file)

                    # Ensure missing keys are filled with defaults
                    for key, default_value in self.default_settings.items():
                        if key not in loaded_settings:
                            loaded_settings[key] = default_value

                    self.settings = loaded_settings
                    return self.settings
            except json.JSONDecodeError:
                logging.error("Error decoding settings file. Using default settings.")
                self.reset_to_defaults(save=True)
        else:
            self.reset_to_defaults(save=True)

        return self.default_settings

    def save_settings(self, settings=None):
        """Save the current settings to the JSON file."""
        if settings is not None:
            self.settings = settings

        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        try:
            with open(self.settings_file, "w") as file:
                json.dump(self.settings, file, indent=4)
            return True
        except IOError as e:
            logging.error(f"Error saving settings: {e}")
            return False

    def reset_to_defaults(self, save=False):
        """Reset settings to default values and ensure all keys exist."""
        self.settings = json.loads(json.dumps(self.default_settings))  # deep copy
        if save:
            self.save_settings()

    def get_setting(self, key, default=None):
        """Retrieve a specific setting, ensuring nested defaults exist."""
        keys = key.split(".")
        value = self.settings
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value if value is not None else default

    def update_setting(self, key, value):
        """Update a setting while preserving existing data."""
        keys = key.split(".")
        settings = self.settings

        for k in keys[:-1]:
            settings = settings.setdefault(k, {})

        settings[keys[-1]] = value
        self.save_settings()

    def set_panel_visibility(self, panel_name, is_visible):
        """Update visibility of a specific panel and apply changes to the UI."""
        self.settings["dockable_panels"][panel_name] = is_visible
        self.save_settings()

        if self.parent_window and hasattr(self.parent_window, "dock_panels"):
            dock_widget = self.parent_window.dock_panels.get(panel_name)
            if dock_widget:
                dock_widget.setVisible(is_visible)

    def store_main_window_layout(self, geometry_bytes: bytes, state_bytes: bytes):
        """
        Save the main window geometry and state as base64-encoded strings in settings.
        """
        if geometry_bytes:
            self.settings["window_geometry_b64"] = base64.b64encode(geometry_bytes).decode("utf-8")
        if state_bytes:
            self.settings["window_state_b64"] = base64.b64encode(state_bytes).decode("utf-8")

        self.save_settings()

    def retrieve_main_window_layout(self):
        """
        Return the previously saved geometry and state as raw bytes, or None if not set.
        """
        geometry_b64 = self.settings.get("window_geometry_b64")
        state_b64 = self.settings.get("window_state_b64")

        geometry_bytes = base64.b64decode(geometry_b64) if geometry_b64 else None
        state_bytes = base64.b64decode(state_b64) if state_b64 else None

        return geometry_bytes, state_bytes