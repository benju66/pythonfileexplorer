import os
import json
import logging

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

class PinnedManager(QObject):
    """Singleton class to manage pinned items (and optional favorites) across all main windows and tabs."""

    pinned_items_updated = pyqtSignal()

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def __init__(self):
        # Ensure initialization runs only once
        if not self.__initialized:
            super().__init__()
            self.__initialized = True

            # Internal data
            self.pinned_items = set()
            self.favorite_items = set()  # <--- NEW

            # Where to store pinned items on disk
            self.pinned_file = "data/pinned_items.json"

            # Load any existing pinned items (and favorites if present)
            self.load_pinned_items()

    def load_pinned_items(self):
        """Load pinned items & favorites from a JSON file."""
        if not os.path.exists(self.pinned_file):
            logger.debug(f"Pinned file does not exist: {self.pinned_file}")
            return
        try:
            with open(self.pinned_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # If data is just a list, it's the old format: all are pinned, no favorites
                if isinstance(data, list):
                    self.pinned_items = set(data)
                    self.favorite_items = set()
                elif isinstance(data, dict):
                    pinned_list = data.get("pinned", [])
                    favorites_list = data.get("favorites", [])
                    self.pinned_items = set(pinned_list)
                    self.favorite_items = set(favorites_list)
                else:
                    logger.warning("Unexpected data format in pinned file, ignoring.")
            logger.debug(f"Loaded pinned items: {self.pinned_items}")
            logger.debug(f"Loaded favorite items: {self.favorite_items}")
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load pinned items from {self.pinned_file}: {e}")

    def save_pinned_items(self):
        """Persist pinned items & favorites to a JSON file."""
        os.makedirs(os.path.dirname(self.pinned_file), exist_ok=True)
        try:
            with open(self.pinned_file, "w", encoding="utf-8") as f:
                json.dump({
                    "pinned": list(self.pinned_items),
                    "favorites": list(self.favorite_items),
                }, f, ensure_ascii=False, indent=2)
            logger.debug("Successfully saved pinned & favorite items.")
        except OSError as e:
            logger.error(f"Failed to save pinned items to {self.pinned_file}: {e}")

    def add_pinned_item(self, item_path: str):
        """Add a new pinned item, save, and emit an update signal."""
        if not os.path.exists(item_path):
            logger.warning(f"Cannot pin non-existent path: {item_path}")
            return
        if item_path not in self.pinned_items:
            self.pinned_items.add(item_path)
            self.save_pinned_items()
            self.pinned_items_updated.emit()
            logger.debug(f"Pinned item: {item_path}")
        else:
            logger.debug(f"Item already pinned: {item_path}")

    def remove_pinned_item(self, item_path: str):
        """Remove a pinned item, and if it's a favorite, remove it there too. Then save & emit."""
        if item_path in self.pinned_items:
            self.pinned_items.remove(item_path)
            # Also remove it from favorites if present
            if item_path in self.favorite_items:
                self.favorite_items.remove(item_path)

            self.save_pinned_items()
            self.pinned_items_updated.emit()
            logger.debug(f"Unpinned item: {item_path}")
        else:
            logger.debug(f"Cannot unpin; item not found: {item_path}")

    def get_pinned_items(self):
        """Return the pinned items as a list."""
        return list(self.pinned_items)

    def is_pinned(self, item_path: str) -> bool:
        """Check if a path is pinned."""
        return item_path in self.pinned_items

    # ----------------------------------------------------------------
    # Favorites Handling
    # ----------------------------------------------------------------
    def favorite_item(self, item_path: str):
        """
        Mark a pinned item as a favorite. 
        If the item isn't pinned, automatically pin it first.
        """
        if not os.path.exists(item_path):
            logger.warning(f"Cannot favorite non-existent path: {item_path}")
            return

        # Auto-pin if not already pinned
        if item_path not in self.pinned_items:
            self.add_pinned_item(item_path)

        if item_path not in self.favorite_items:
            self.favorite_items.add(item_path)
            self.save_pinned_items()
            self.pinned_items_updated.emit()
            logger.debug(f"Favorited item: {item_path}")
        else:
            logger.debug(f"Item already a favorite: {item_path}")

    def unfavorite_item(self, item_path: str):
        """Remove from favorites only; remains pinned unless unpinned separately."""
        if item_path in self.favorite_items:
            self.favorite_items.remove(item_path)
            self.save_pinned_items()
            self.pinned_items_updated.emit()
            logger.debug(f"Unfavorited item: {item_path}")
        else:
            logger.debug(f"Cannot unfavorite; item not in favorites: {item_path}")

    def get_favorite_items(self):
        """Return the favorite items as a list."""
        return list(self.favorite_items)

    def is_favorite(self, item_path: str) -> bool:
        """Check if a path is in favorites."""
        return item_path in self.favorite_items
