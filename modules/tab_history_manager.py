# tab_history_manager.py

import os

class TabHistoryManager:
    """
    A small helper class that manages a separate back/forward history 
    for each tab index, without cluttering TabManager directly.
    """

    def __init__(self):
        # tab index -> {"history": [paths], "history_index": int}
        self.tab_states = {}

    def init_tab_history(self, tab_index: int, initial_path: str):
        """
        Initialize a brand new tab’s history. Call this whenever you 
        create a new tab in TabManager.
        """
        self.tab_states[tab_index] = {
            "history": [initial_path],
            "history_index": 0
        }

    def remove_tab_history(self, tab_index: int):
        """
        Cleanup tab history if the tab is closed, to avoid stale data.
        """
        self.tab_states.pop(tab_index, None)

    def get_current_path(self, tab_index: int) -> str:
        """
        Return the path that the tab at `tab_index` is currently displaying, 
        based on its history index. If there's nothing found, return "".
        """
        state = self.tab_states.get(tab_index)
        if not state:
            return ""
        return state["history"][state["history_index"]]

    def push_path(self, tab_index: int, new_path: str):
        """
        Navigate to a new path for the tab, discarding any 'forward' 
        history if the user previously went back. 
        """
        state = self.tab_states.get(tab_index)
        if not state:
            # If the tab wasn't initialized, do it now
            self.init_tab_history(tab_index, new_path)
            return

        # If the user had previously gone "Back," 
        # we remove any forward entries 
        current_i = state["history_index"]
        state["history"] = state["history"][: current_i + 1]

        # Append the new path and move forward
        state["history"].append(new_path)
        state["history_index"] += 1

    def go_back(self, tab_index: int) -> str:
        """
        Move the tab's current_history_index one step back, 
        and return the new path. Returns an empty string if no back is possible.
        """
        state = self.tab_states.get(tab_index)
        if not state:
            return ""
        if state["history_index"] > 0:
            state["history_index"] -= 1
        return state["history"][state["history_index"]]

    def go_forward(self, tab_index: int) -> str:
        """
        Move the tab's current_history_index one step forward, 
        and return the new path. Returns an empty string if no forward is possible.
        """
        state = self.tab_states.get(tab_index)
        if not state:
            return ""
        if state["history_index"] < len(state["history"]) - 1:
            state["history_index"] += 1
        return state["history"][state["history_index"]]

    def go_up(self, tab_index: int) -> str:
        """
        Compute the parent directory of the current path, push it onto 
        history, and return it. Return empty string if no valid parent.
        """
        current_path = self.get_current_path(tab_index)
        if not current_path:
            return ""
        parent_dir = os.path.dirname(current_path)
        if parent_dir and os.path.exists(parent_dir):
            self.push_path(tab_index, parent_dir)
            return parent_dir
        return ""
