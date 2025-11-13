DEFAULT_THEME = "light"

SUPPORTED_EXTENSIONS = [
    ".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".txt", ".py", ".json", ".xls", ".doc", ".zip", ".exe",
    ".ico", ".bmp", ".gif", ".tiff", ".svg", ".csv", ".ini", ".log", ".html", ".css", ".js", ".md", ".pyc", ".mpp"
]

APP_NAME = "Enhanced File Explorer"
VERSION = "1.0.0"

DEFAULT_TEMPLATE_FOLDER = "assets/templates"
DEFAULT_ICONS_FOLDER = "assets/icons"
DEFAULT_THEME_FOLDER = "assets/themes"

DEFAULT_SETTINGS = {
    "theme": DEFAULT_THEME,
    "last_opened_directory": "",
    "show_hidden_files": False,
}

# Example file size limits or other app-wide limits
MAX_FILE_PREVIEW_SIZE_MB = 10  # Limit file preview to 10MB
