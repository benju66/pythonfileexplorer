import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

# 1) Import your new KeyboardShortcuts class
from modules.keyboard_shortcuts import KeyboardShortcuts

def load_settings():
    """Load user settings from a JSON file or set defaults if not found."""
    import os
    import json

    settings_file = "data/settings.json"
    default_settings = {
        "theme": "light",
        "last_opened_directory": "",
    }

    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Error loading settings. Using defaults.")
            return default_settings
    else:
        # Save default settings to file
        os.makedirs("data", exist_ok=True)
        with open(settings_file, "w") as f:
            json.dump(default_settings, f, indent=4)
        return default_settings

def main():
    settings_file = "data/settings.json"
    app = QApplication([])

    try:
        window = MainWindow(settings_file)
        # Apply settings after window creation but before show()
        window.apply_saved_settings()

        # 2) Instantiate KeyboardShortcuts after the MainWindow is created
        KeyboardShortcuts(window)
        
        # 3) Ensure all containers restore their dock layouts
        window.restore_containers_dock_layouts()

    except Exception as e:
        print(f"Error loading settings. Using defaults: {e}")
        window = MainWindow()
        window.apply_saved_settings()

        # Still set up the keyboard shortcuts even if there was an error in settings
        KeyboardShortcuts(window)
        
        # Ensure all containers restore their dock layouts even with default settings
        window.restore_containers_dock_layouts()

    window.show()
    app.exec()

if __name__ == "__main__":
    main()