import os
import json
import re  # only if you want optional pattern checks on numeric tags

class MetadataManager:
    def __init__(self, metadata_file="data/metadata.json"):
        self.metadata_file = metadata_file
        # Provide defaults for any keys used later
        self.metadata = {
            "pinned_items": [],
            "recent_items": [],
            "tags": {},
            "last_accessed": {},
            "item_colors": {},   # for both files and folders
            "item_bold": {},     # for both files and folders
            "recent_colors": []  # store up to 5 or so
        }
        self.load_metadata()

    def load_metadata(self):
        """Load metadata from the JSON file or create a default structure if missing/corrupt."""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, "r", encoding="utf-8") as file:
                    self.metadata = json.load(file)
        except (json.JSONDecodeError, IOError):
            print("Metadata file is corrupt or missing. Recreating with defaults.")
            self.metadata = {
                "pinned_items": [],
                "recent_items": [],
                "tags": {},
                "last_accessed": {},
                "item_colors": {},
                "item_bold": {},
                "recent_colors": []
            }

        # Ensure all keys exist in the metadata structure
        required_dict_keys = ["tags", "last_accessed", "item_colors", "item_bold"]
        required_list_keys = ["pinned_items", "recent_items", "recent_colors"]

        for key in required_dict_keys:
            if key not in self.metadata:
                self.metadata[key] = {}
        for key in required_list_keys:
            if key not in self.metadata:
                self.metadata[key] = []

        self.save_metadata()

    def save_metadata(self):
        """Save the current metadata to the JSON file."""
        os.makedirs(os.path.dirname(self.metadata_file), exist_ok=True)
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as file:
                json.dump(self.metadata, file, indent=4)
        except IOError as e:
            print(f"Error saving metadata: {e}")

    # ─────────────────────────────────────────────────────────
    # Recent Colors (NEW)
    # ─────────────────────────────────────────────────────────
    def get_recent_colors(self):
        """Return the list of recent color hex codes (e.g., ['#FF0000', '#00FF00'])."""
        return self.metadata.get("recent_colors", [])

    def add_recent_color(self, color_hex):
        """
        Insert a newly used color at the front of the list, removing
        duplicates, and limit to 5 entries, then save.
        """
        colors = self.metadata.get("recent_colors", [])
        # If color is already in the list, remove it so we can re-insert at front
        if color_hex in colors:
            colors.remove(color_hex)
        colors.insert(0, color_hex)
        # Cap at 5
        colors = colors[:5]
        self.metadata["recent_colors"] = colors
        self.save_metadata()

    def remove_recent_color(self, color_hex):
        """
        Remove a single color from recent_colors, then save.
        """
        colors = self.metadata.get("recent_colors", [])
        if color_hex in colors:
            colors.remove(color_hex)
            self.metadata["recent_colors"] = colors
            self.save_metadata()

    def clear_recent_colors(self):
        """
        Remove all recent colors at once, then save.
        """
        self.metadata["recent_colors"] = []
        self.save_metadata()

    # ─────────────────────────────────────────────────────────
    # Item-based Color & Bold Methods
    # ─────────────────────────────────────────────────────────
    def set_item_color(self, item_path, color_hex):
        """Store a color (e.g. '#FF0000') for any path (file or folder)."""
        self.metadata["item_colors"][item_path] = color_hex
        self.save_metadata()

    def get_item_color(self, item_path):
        """Retrieve a stored color hex for a path, or None if none set."""
        return self.metadata["item_colors"].get(item_path)

    def set_item_bold(self, item_path, bold_flag):
        """Store whether this path's text should be bold (True/False)."""
        self.metadata["item_bold"][item_path] = bool(bold_flag)
        self.save_metadata()

    def get_item_bold(self, item_path):
        """Return True if a path is bold, else False."""
        return self.metadata["item_bold"].get(item_path, False)

    # ─────────────────────────────────────────────────────────
    # Pinned Items Methods
    # ─────────────────────────────────────────────────────────
    def add_pinned_item(self, item_path):
        if item_path not in self.metadata["pinned_items"]:
            self.metadata["pinned_items"].append(item_path)
            self.save_metadata()

    def remove_pinned_item(self, item_path):
        if item_path in self.metadata["pinned_items"]:
            self.metadata["pinned_items"].remove(item_path)
            self.save_metadata()

    def get_pinned_items(self):
        """Retrieve pinned items, sorted for consistency."""
        return sorted(self.metadata["pinned_items"])

    # ─────────────────────────────────────────────────────────
    # Recent Items Methods
    # ─────────────────────────────────────────────────────────
    def add_recent_item(self, item_path):
        """Add a new recent item, keeping the list at max length 10."""
        if item_path in self.metadata["recent_items"]:
            self.metadata["recent_items"].remove(item_path)
        self.metadata["recent_items"].insert(0, item_path)
        self.metadata["recent_items"] = self.metadata["recent_items"][:10]
        self.save_metadata()

    def get_recent_items(self):
        return self.metadata["recent_items"]

    # ─────────────────────────────────────────────────────────
    # Tagging Methods
    # ─────────────────────────────────────────────────────────
    def set_tags(self, item_path, tags):
        """Overwrite all tags for a specific item with a new list."""
        self.metadata["tags"][item_path] = tags
        self.save_metadata()

    def add_tag(self, item_path, tag):
        """Add a single tag to an item."""
        if item_path not in self.metadata["tags"]:
            self.metadata["tags"][item_path] = []
        if tag not in self.metadata["tags"][item_path]:
            self.metadata["tags"][item_path].append(tag)
            self.save_metadata()

    def remove_tag(self, item_path, tag):
        if item_path in self.metadata["tags"] and tag in self.metadata["tags"][item_path]:
            self.metadata["tags"][item_path].remove(tag)
            self.save_metadata()

    def get_tags(self, item_path):
        """Retrieve all tags for a given item path."""
        return self.metadata["tags"].get(item_path, [])

    def get_items_with_tag(self, tag):
        """Return a list of all items that have the given tag."""
        matching_items = []
        for path, tags in self.metadata["tags"].items():
            if tag in tags:
                matching_items.append(path)
        return matching_items

    # ─────────────────────────────────────────────────────────
    # Last Accessed Methods
    # ─────────────────────────────────────────────────────────
    def set_last_accessed(self, item_path):
        """Set the last accessed time for a file/folder if it exists on disk."""
        if os.path.exists(item_path):
            self.metadata["last_accessed"][item_path] = os.path.getatime(item_path)
            self.save_metadata()

    def get_last_accessed(self, item_path):
        """Retrieve the last accessed time for a file or folder."""
        return self.metadata["last_accessed"].get(item_path)


if __name__ == "__main__":
    # Quick demo usage
    manager = MetadataManager()

    # Example: set color/bold for a file
    file_path = "C:/example/some_file.txt"
    manager.set_item_color(file_path, "#FF0000")
    manager.set_item_bold(file_path, True)
    print("Color for file:", manager.get_item_color(file_path))  # => "#FF0000"
    print("Bold for file?:", manager.get_item_bold(file_path))   # => True

    # Demo: store a new recent color, remove one, or clear them all
    manager.add_recent_color("#FFA500")
    print("Recent colors:", manager.get_recent_colors())

    manager.remove_recent_color("#FFA500")
    print("Recent colors (after removal):", manager.get_recent_colors())

    manager.clear_recent_colors()
    print("Recent colors (after clearing all):", manager.get_recent_colors())
