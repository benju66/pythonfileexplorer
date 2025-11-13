# tab_history_manager.py

import os
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import QWidget


class TabHistoryManager:
    """
    Manages navigation history for tabs using widget IDs instead of indices.
    
    This design allows history to persist when tabs are moved, reordered, or
    moved between tab widgets, making it compatible with drag-and-drop operations.
    
    History is keyed by widget object ID (id(widget)), which is stable for the
    lifetime of the widget, regardless of its position in the tab widget.
    
    Usage:
        manager = TabHistoryManager()
        tab_widget = tab_manager.currentWidget()
        manager.init_tab_history(tab_widget, "/path/to/dir")
        manager.push_path(tab_widget, "/new/path")
        current = manager.get_current_path(tab_widget)
    """

    def __init__(self):
        """
        Initialize the history manager.
        
        Internal structure:
            widget_id (int) -> {
                "history": List[str],      # List of paths in navigation order
                "history_index": int       # Current position in history
            }
        """
        # widget_id -> {"history": [paths], "history_index": int}
        self.tab_states: Dict[int, Dict[str, Any]] = {}

    def _get_widget_id(self, widget: QWidget) -> int:
        """
        Get stable ID for widget.
        
        Args:
            widget: The widget to get ID for
            
        Returns:
            int: Widget object ID (stable for widget lifetime)
            
        Raises:
            ValueError: If widget is None
        """
        if widget is None:
            raise ValueError("Widget cannot be None")
        return id(widget)

    def init_tab_history(self, widget: QWidget, initial_path: str) -> None:
        """
        Initialize navigation history for a tab widget.
        
        Call this when creating a new tab to set up its history tracking.
        The initial path becomes the first entry in the history.
        
        Args:
            widget: The QWidget representing the tab content (must contain FileTree)
            initial_path: The initial directory path for this tab
            
        Raises:
            ValueError: If widget is None or initial_path is empty
            TypeError: If initial_path is not a string
        """
        if widget is None:
            raise ValueError("Widget cannot be None")
        if not isinstance(initial_path, str):
            raise TypeError(f"initial_path must be str, got {type(initial_path)}")
        if not initial_path:
            raise ValueError("initial_path cannot be empty")

        widget_id = self._get_widget_id(widget)
        self.tab_states[widget_id] = {
            "history": [initial_path],
            "history_index": 0
        }

    def remove_tab_history(self, widget: QWidget) -> None:
        """
        Remove history for a tab widget when it's closed.
        
        This cleans up memory and prevents stale data. Call this when
        a tab is permanently closed (not just moved).
        
        Args:
            widget: The widget whose history should be removed
            
        Raises:
            ValueError: If widget is None
        """
        if widget is None:
            raise ValueError("Widget cannot be None")

        widget_id = self._get_widget_id(widget)
        self.tab_states.pop(widget_id, None)

    def get_current_path(self, widget: QWidget) -> str:
        """
        Get the current path for a tab widget based on its history.
        
        Args:
            widget: The widget to get current path for
            
        Returns:
            str: Current path, or empty string if no history exists
        """
        if widget is None:
            return ""

        widget_id = self._get_widget_id(widget)
        state = self.tab_states.get(widget_id)
        if not state:
            return ""

        history = state["history"]
        history_index = state["history_index"]

        if 0 <= history_index < len(history):
            return history[history_index]
        return ""

    def push_path(self, widget: QWidget, new_path: str) -> None:
        """
        Add a new path to the tab's navigation history.
        
        This is called when the user navigates to a new directory. If the user
        had previously gone "back" in history, any forward history is discarded.
        
        Args:
            widget: The widget whose history to update
            new_path: The new directory path to add
            
        Raises:
            ValueError: If widget is None or new_path is empty
            TypeError: If new_path is not a string
        """
        if widget is None:
            raise ValueError("Widget cannot be None")
        if not isinstance(new_path, str):
            raise TypeError(f"new_path must be str, got {type(new_path)}")
        if not new_path:
            raise ValueError("new_path cannot be empty")

        widget_id = self._get_widget_id(widget)
        state = self.tab_states.get(widget_id)

        if not state:
            # Initialize if not already done
            self.init_tab_history(widget, new_path)
            return

        # If user had previously gone "Back," remove any forward entries
        current_i = state["history_index"]
        state["history"] = state["history"][:current_i + 1]

        # Append the new path and move forward
        state["history"].append(new_path)
        state["history_index"] += 1

    def go_back(self, widget: QWidget) -> str:
        """
        Navigate back one step in the tab's history.
        
        Args:
            widget: The widget to navigate back for
            
        Returns:
            str: The previous path, or empty string if no back history exists
        """
        if widget is None:
            return ""

        widget_id = self._get_widget_id(widget)
        state = self.tab_states.get(widget_id)
        if not state:
            return ""

        if state["history_index"] > 0:
            state["history_index"] -= 1

        return self.get_current_path(widget)

    def go_forward(self, widget: QWidget) -> str:
        """
        Navigate forward one step in the tab's history.
        
        Args:
            widget: The widget to navigate forward for
            
        Returns:
            str: The next path, or empty string if no forward history exists
        """
        if widget is None:
            return ""

        widget_id = self._get_widget_id(widget)
        state = self.tab_states.get(widget_id)
        if not state:
            return ""

        history = state["history"]
        history_index = state["history_index"]

        # Check if we can go forward
        if history_index < len(history) - 1:
            state["history_index"] += 1
            return self.get_current_path(widget)
        else:
            # Already at the end, can't go forward
            return ""

    def go_up(self, widget: QWidget) -> str:
        """
        Navigate to the parent directory of the current path.
        
        Computes the parent directory and adds it to history.
        
        Args:
            widget: The widget to navigate up for
            
        Returns:
            str: The parent directory path, or empty string if no valid parent
        """
        if widget is None:
            return ""

        current_path = self.get_current_path(widget)
        if not current_path:
            return ""

        parent_dir = os.path.dirname(current_path)
        if parent_dir and os.path.exists(parent_dir):
            self.push_path(widget, parent_dir)
            return parent_dir

        return ""

    def migrate_history(self, source_widget: QWidget, target_widget: QWidget) -> None:
        """
        Migrate history from one widget to another.
        
        Useful when moving tabs between TabManager instances. The source
        widget's history is copied to the target widget, and the source
        history is removed.
        
        Args:
            source_widget: Widget to copy history from
            target_widget: Widget to copy history to
            
        Raises:
            ValueError: If either widget is None
        """
        if source_widget is None or target_widget is None:
            raise ValueError("Both widgets must be provided")

        source_id = self._get_widget_id(source_widget)
        target_id = self._get_widget_id(target_widget)

        # Copy history if it exists
        if source_id in self.tab_states:
            # Deep copy the history state
            source_state = self.tab_states[source_id]
            self.tab_states[target_id] = {
                "history": source_state["history"].copy(),
                "history_index": source_state["history_index"]
            }
            # Remove source history
            del self.tab_states[source_id]

    def get_history_debug_info(self, widget: QWidget) -> Dict[str, Any]:
        """
        Get debug information about a widget's history.
        
        Useful for testing and debugging. Returns a dictionary with:
        - widget_id: The widget's ID
        - has_history: Whether history exists
        - history: List of all paths in history
        - current_index: Current position in history
        - current_path: Current path being displayed
        
        Args:
            widget: The widget to get debug info for
            
        Returns:
            dict: Debug information dictionary
        """
        if widget is None:
            return {
                "widget_id": None,
                "has_history": False,
                "error": "Widget is None"
            }
        
        widget_id = self._get_widget_id(widget)
        state = self.tab_states.get(widget_id)
        
        if not state:
            return {
                "widget_id": widget_id,
                "has_history": False,
                "history": [],
                "current_index": -1,
                "current_path": ""
            }
        
        return {
            "widget_id": widget_id,
            "has_history": True,
            "history": state["history"].copy(),
            "current_index": state["history_index"],
            "current_path": self.get_current_path(widget),
            "can_go_back": state["history_index"] > 0,
            "can_go_forward": state["history_index"] < len(state["history"]) - 1
        }
    
    def print_all_history(self) -> None:
        """
        Print all tab histories for debugging.
        
        Useful for verifying history state across all tabs.
        """
        print("\n" + "="*60)
        print("TAB HISTORY DEBUG INFO")
        print("="*60)
        
        if not self.tab_states:
            print("No tab histories found.")
            return
        
        for widget_id, state in self.tab_states.items():
            print(f"\nWidget ID: {widget_id}")
            print(f"  History: {state['history']}")
            print(f"  Current Index: {state['history_index']}")
            print(f"  Current Path: {state['history'][state['history_index']]}")
            print(f"  Can Go Back: {state['history_index'] > 0}")
            print(f"  Can Go Forward: {state['history_index'] < len(state['history']) - 1}")
        
        print("\n" + "="*60)
