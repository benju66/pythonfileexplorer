import json
import os
import webbrowser

from PyQt6.QtWidgets import (
    QDockWidget, QVBoxLayout, QWidget, QTreeWidget, QTreeWidgetItem,
    QInputDialog, QMessageBox, QLineEdit, QMenu, QApplication, QHBoxLayout, 
    QToolButton, QSizePolicy
)
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import (
    Qt, QRect, QSize
)

class ProcoreQuickLinksPanel(QDockWidget):
    def __init__(self, parent=None, data_file="data/procore_links.json"):
        super().__init__(parent)

        # 1) Hide this dock’s built-in header so only the outer dock shows a title.
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setTitleBarWidget(QWidget(self))

        self.data_file = data_file
        self.projects = {}
        self._initialized = False
        self._expanded_items = set()

        # 2) Main layout: same as before
        self.main_widget = QWidget()
        self.setWidget(self.main_widget)
        self.layout = QVBoxLayout()
        self.main_widget.setLayout(self.layout)

        # 3) Top row layout for search bar + tool buttons
        top_row_layout = QHBoxLayout()
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(5)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search projects or links...")
        self.search_bar.textChanged.connect(self.filter_tree)
        size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_bar.setSizePolicy(size_policy)
        top_row_layout.addWidget(self.search_bar, 1)

        self.add_project_button = QToolButton(self)
        self.add_project_button.setIcon(QIcon("C:/EnhancedFileExplorer/assets/icons/diff.svg"))
        self.add_project_button.setToolTip("Add Project")
        self.add_project_button.clicked.connect(self.add_project)
        top_row_layout.addWidget(self.add_project_button)

        self.add_link_button = QToolButton(self)
        self.add_link_button.setIcon(QIcon("C:/EnhancedFileExplorer/assets/icons/plus.svg"))
        self.add_link_button.setToolTip("Add Link")
        self.add_link_button.clicked.connect(self.add_link)
        top_row_layout.addWidget(self.add_link_button)

        self.remove_button = QToolButton(self)
        self.remove_button.setIcon(QIcon("C:/EnhancedFileExplorer/assets/icons/trash-2.svg"))
        self.remove_button.setToolTip("Remove Selected")
        self.remove_button.clicked.connect(self.remove_selected)
        top_row_layout.addWidget(self.remove_button)

        self.layout.addLayout(top_row_layout)

        # 4) QTreeWidget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self.open_selected_link)
        self.tree.itemChanged.connect(self.rename_link)
        self.tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.layout.addWidget(self.tree)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initialized:
            self.projects = self.load_links()
            self.populate_tree()
            self._initialized = True
        # Animation call removed here

    # -----------------------------
    # 1) JSON File Handling
    # -----------------------------
    def load_links(self):
        """
        Load projects & links from the JSON file.
        Also migrate any plain-string links to the dict format {"url": "...", "tags": []},
        and ensure each project has "_tags": [] for its own tags.
        """
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                QMessageBox.critical(self, "Error", "Failed to load links (JSON decode error).")
                data = {}
        else:
            data = {}

        # Ensure each project has "_tags" and convert old-style string links
        for project_name, project_data in data.items():
            # If the project doesn't have _tags, create an empty list
            if "_tags" not in project_data:
                project_data["_tags"] = []

            # Convert any string link into { "url": string, "tags": [] }
            for link_name, link_obj in list(project_data.items()):
                if link_name == "_tags":
                    continue
                if isinstance(link_obj, str):
                    project_data[link_name] = {"url": link_obj, "tags": []}

        return data

    def save_links(self):
        """Save the current projects dict to JSON."""
        if not self.projects:
            return  # If it's empty, skip
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, "w") as f:
                json.dump(self.projects, f, indent=4)
        except Exception as e:
            print(f"Error saving Procore links: {e}")

    # -----------------------------
    # 2) Populate & Filter Tree
    # -----------------------------
    def store_expanded_items(self):
        self._expanded_items = set()

        def recurse(item):
            if item.isExpanded():
                self._expanded_items.add(item.text(0))
            for i in range(item.childCount()):
                recurse(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            recurse(top_item)

    def restore_expanded_items(self):
        def recurse(item):
            if item.text(0) in self._expanded_items:
                item.setExpanded(True)
            for i in range(item.childCount()):
                recurse(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            recurse(top_item)

    
    def populate_tree(self):
        """
        Fill the QTreeWidget with project/link items, 
        while making link items *not* editable on double-click.
        """
        # 1) Store expansions
        self.store_expanded_items()

        # 2) Clear the tree
        self.tree.clear()

        for project_name, project_data in self.projects.items():
            # -- Project Item: still editable if you want to rename by double-click --
            project_item = QTreeWidgetItem([project_name])
            project_item.setFlags(project_item.flags() | Qt.ItemFlag.ItemIsEditable)
            project_item.setData(0, Qt.ItemDataRole.UserRole, project_data)

            project_tags = project_data.get("_tags", [])
            if project_tags:
                project_item.setToolTip(0, f"Tags: {', '.join(project_tags)}")
            else:
                project_item.setToolTip(0, "No tags")

            self.tree.addTopLevelItem(project_item)

            # -- Child Link Items: NOT editable on double-click --
            for link_name, link_data in project_data.items():
                if link_name == "_tags":
                    continue

                link_item = QTreeWidgetItem([link_name])
                # Removed: link_item.setFlags(link_item.flags() | Qt.ItemFlag.ItemIsEditable)
                link_item.setData(0, Qt.ItemDataRole.UserRole, link_data)

                link_tags = link_data.get("tags", [])
                if link_tags:
                    link_item.setToolTip(0, f"Tags: {', '.join(link_tags)}")
                else:
                    link_item.setToolTip(0, "No tags")

                project_item.addChild(link_item)

        # 3) Restore expansions
        self.restore_expanded_items()

    def filter_tree(self):
        """
        Filter both project and link items by the search bar text.
        Matches project name, project tags, link name, link URL, or link tags.
        """
        query = self.search_bar.text().lower()

        for i in range(self.tree.topLevelItemCount()):
            project_item = self.tree.topLevelItem(i)
            project_data = project_item.data(0, Qt.ItemDataRole.UserRole)
            project_visible = False

            # Check project name
            if query in project_item.text(0).lower():
                project_visible = True

            # Check project tags
            proj_tags = project_data.get("_tags", [])
            for t in proj_tags:
                if query in t.lower():
                    project_visible = True
                    break

            # Now check each link
            any_link_visible = False
            for j in range(project_item.childCount()):
                link_item = project_item.child(j)
                link_data = link_item.data(0, Qt.ItemDataRole.UserRole)

                name_match = (query in link_item.text(0).lower())
                url_match = False
                tag_match = False

                if link_data and isinstance(link_data, dict):
                    # Check the URL
                    if query in link_data.get("url", "").lower():
                        url_match = True
                    # Check link tags
                    link_tags = link_data.get("tags", [])
                    for tag in link_tags:
                        if query in tag.lower():
                            tag_match = True
                            break

                link_visible = name_match or url_match or tag_match
                link_item.setHidden(not link_visible)
                if link_visible:
                    any_link_visible = True

            # If any link is visible, the project is also visible
            if any_link_visible:
                project_visible = True

            # Hide or show the project item
            project_item.setHidden(not project_visible)

    # -----------------------------
    # 3) Context Menu
    # -----------------------------
    def show_context_menu(self, position):
        selected_item = self.tree.itemAt(position)
        menu = QMenu(self)

        if not selected_item:
            # Right-clicked in an empty area
            sort_all_action = QAction("Sort All Projects", self)
            sort_all_action.triggered.connect(self.sort_all_projects_and_links)
            menu.addAction(sort_all_action)
        else:
            # We have a selected item
            parent_item = selected_item.parent()

            if not parent_item:
                # -----------------------------
                # PROJECT CONTEXT MENU
                # -----------------------------
                rename_action = QAction("Rename Project", self)
                rename_action.triggered.connect(lambda: self.rename_project(selected_item))
                menu.addAction(rename_action)

                add_project_tag_action = QAction("Add Tag to Project", self)
                add_project_tag_action.triggered.connect(lambda: self.tag_project(selected_item))
                menu.addAction(add_project_tag_action)

                remove_project_tag_action = QAction("Remove Tag from Project", self)
                remove_project_tag_action.triggered.connect(lambda: self.remove_tag_from_project(selected_item))
                menu.addAction(remove_project_tag_action)

                # NEW: Add Link to this Project
                add_link_action = QAction("Add Link", self)
                add_link_action.triggered.connect(lambda: self.add_link_for_project(selected_item))
                menu.addAction(add_link_action)

                delete_action = QAction("Delete Project", self)
                delete_action.triggered.connect(self.remove_selected)
                menu.addAction(delete_action)

                # (Optional) If you also want to right-click a project and only sort its child links:
                # sort_links_action = QAction("Sort Links Under This Project", self)
                # sort_links_action.triggered.connect(lambda: self.sort_links_in_project(selected_item))
                # menu.addAction(sort_links_action)

            else:
                # -----------------------------
                # LINK CONTEXT MENU
                # -----------------------------
                open_action = QAction("Open Link", self)
                open_action.triggered.connect(lambda: self.open_selected_link(selected_item, 0))
                menu.addAction(open_action)

                rename_action = QAction("Rename Link", self)
                rename_action.triggered.connect(lambda: self.rename_link(selected_item, 0))
                menu.addAction(rename_action)

                copy_action = QAction("Copy URL", self)
                copy_action.triggered.connect(lambda: self.copy_link(selected_item))
                menu.addAction(copy_action)

                add_tag_action = QAction("Add Tag", self)
                add_tag_action.triggered.connect(lambda: self.tag_link(selected_item))
                menu.addAction(add_tag_action)

                remove_tag_action = QAction("Remove Tag", self)
                remove_tag_action.triggered.connect(lambda: self.remove_tag_from_link(selected_item))
                menu.addAction(remove_tag_action)

                delete_action = QAction("Delete Link", self)
                delete_action.triggered.connect(self.remove_selected)
                menu.addAction(delete_action)

        # Show the context menu
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def add_link_for_project(self, project_item):
        """
        Prompt the user for link info and add it under the given project item.
        """
        if not project_item:
            QMessageBox.warning(self, "No Project Selected", "Please select a project first.")
            return

        project_name = project_item.text(0)
        if project_name not in self.projects:
            QMessageBox.warning(self, "Invalid Project", f"Project '{project_name}' not found.")
            return

        # Prompt for link title
        link_title, ok1 = QInputDialog.getText(self, "Add Link", "Enter link title:")
        if not ok1 or not link_title:
            return  # user canceled or empty

        # Prompt for link URL
        link_url, ok2 = QInputDialog.getText(self, "Add Link", "Enter URL:")
        if not ok2 or not link_url:
            return  # user canceled or empty

        # Insert the new link data
        self.projects[project_name][link_title] = {"url": link_url, "tags": []}

        # Save changes and refresh
        self.save_links()
        self.populate_tree()



    def sort_all_projects_and_links(self):
        """
        Sorts all top-level projects so that text-based project names come first,
        then numeric-based project names (all alphabetically).
        Also sorts each project's child links in alphabetical order under its parent.
        """
        # 1) Convert self.projects (dict) -> list of (project_name, project_data)
        items = list(self.projects.items())

        # 2) Sort top-level projects with text first, numeric last.
        #    Example order: BuildingConnected, FP, Links, 23-197, 24-105
        def project_sort_key(item):
            project_name, project_data = item
            # If the first character is a digit, we group it after the text-based names
            if project_name and project_name[0].isdigit():
                return (1, project_name.lower())
            return (0, project_name.lower())

        items.sort(key=project_sort_key)

        # 3) Rebuild the dictionary in sorted order, also sorting child links
        sorted_projects = {}
        for project_name, project_data in items:
            # Collect all links except the special "_tags"
            link_pairs = []
            for link_name, link_info in project_data.items():
                if link_name == "_tags":
                    continue
                link_pairs.append((link_name, link_info))

            # Sort child links alphabetically
            link_pairs.sort(key=lambda x: x[0].lower())

            # Rebuild the project dict, preserving project tags
            new_project_data = {"_tags": project_data.get("_tags", [])}
            for link_name, link_info in link_pairs:
                new_project_data[link_name] = link_info

            sorted_projects[project_name] = new_project_data

        # 4) Update self.projects and refresh
        self.projects = sorted_projects
        self.save_links()
        self.populate_tree()



    # -----------------------------
    # 4) Link & Project Actions
    # -----------------------------
    def copy_link(self, link_item):
        """
        Copy the link's URL to the system clipboard.
        """
        link_data = link_item.data(0, Qt.ItemDataRole.UserRole)
        if link_data and isinstance(link_data, dict):
            url = link_data.get("url")
            if url:
                clipboard = QApplication.clipboard()
                clipboard.setText(url)
                QMessageBox.information(self, "Copied", f"Copied: {url}")
        else:
            print("[ERROR] Link data missing or invalid.")

    def open_selected_link(self, link_item, column):
        """
        Open the link in a browser.
        """
        link_data = link_item.data(0, Qt.ItemDataRole.UserRole)
        if link_data and isinstance(link_data, dict):
            url = link_data.get("url")
            if url:
                webbrowser.open(url)
                link_item.setSelected(True)
        else:
            print("[ERROR] link_data is missing or invalid for item:", link_item.text(0))

    def rename_project(self, project_item):
        """
        Rename the project key in self.projects and update the UI.
        """
        old_name = project_item.text(0)
        new_name, ok = QInputDialog.getText(self, "Rename Project", "Enter new name:", text=old_name)
        if ok and new_name:
            if old_name in self.projects:
                self.projects[new_name] = self.projects.pop(old_name)
                project_item.setText(0, new_name)
                self.save_links()
                self.populate_tree()

    def rename_link(self, link_item, column):
        """
        Rename the link key under its parent project.
        """
        parent_item = link_item.parent()
        if not parent_item:
            return  # It's a project, not a link

        project_name = parent_item.text(0)
        old_name = link_item.text(0)
        link_data = link_item.data(0, Qt.ItemDataRole.UserRole)

        new_name, ok = QInputDialog.getText(self, "Rename Link", "Enter new name:", text=old_name)
        if ok and new_name:
            if project_name in self.projects and old_name in self.projects[project_name]:
                del self.projects[project_name][old_name]
            self.projects[project_name][new_name] = link_data
            link_item.setText(0, new_name)
            self.save_links()
            self.populate_tree()

    def add_project(self):
        """
        Create a new project in self.projects and refresh the UI.
        """
        project_name, ok = QInputDialog.getText(self, "Add Project", "Enter project name:")
        if ok and project_name:
            if project_name not in self.projects:
                self.projects[project_name] = {"_tags": []}
                self.save_links()
                self.populate_tree()

                # Optionally expand the new project in the tree
                items = self.tree.findItems(project_name, Qt.MatchFlag.MatchExactly)
                if items:
                    self.tree.expandItem(items[0])

    def add_link(self):
        """
        Create a new link under the selected project item.
        """
        selected_item = self.tree.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Select Project", "Please select a project first.")
            return

        # If user selected a link, use its parent (the project)
        if selected_item.parent():
            project_name = selected_item.parent().text(0)
        else:
            project_name = selected_item.text(0)

        link_title, ok1 = QInputDialog.getText(self, "Add Link", "Enter link title:")
        if not ok1 or not link_title:
            return

        link_url, ok2 = QInputDialog.getText(self, "Add Link", "Enter URL:")
        if not ok2 or not link_url:
            return

        if project_name in self.projects:
            self.projects[project_name][link_title] = {"url": link_url, "tags": []}
            self.save_links()
            self.populate_tree()

    def remove_selected(self):
        """
        Remove either a project or a link, depending on what's selected.
        """
        selected_item = self.tree.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Select Item", "Please select a project or link to remove.")
            return

        parent = selected_item.parent()
        if parent:
            # It's a link
            project_name = parent.text(0)
            link_title = selected_item.text(0)
            if project_name in self.projects and link_title in self.projects[project_name]:
                del self.projects[project_name][link_title]
        else:
            # It's a project
            project_name = selected_item.text(0)
            if project_name in self.projects:
                del self.projects[project_name]

        self.save_links()
        self.populate_tree()

    # -----------------------------
    # 5) Tagging Methods
    # -----------------------------
    def tag_link(self, link_item):
        """
        Prompt user for a tag and add it to the link's 'tags' list.
        """
        link_data = link_item.data(0, Qt.ItemDataRole.UserRole)
        if not link_data or not isinstance(link_data, dict):
            print("[ERROR] link_data is missing or not a dict.")
            return

        tag, ok = QInputDialog.getText(self, "Add Tag", f"Enter a tag for link '{link_item.text(0)}':")
        if ok and tag:
            if "tags" not in link_data:
                link_data["tags"] = []

            if tag not in link_data["tags"]:
                link_data["tags"].append(tag)

                # Save back to self.projects
                parent_item = link_item.parent()
                project_name = parent_item.text(0)
                old_name = link_item.text(0)
                self.projects[project_name][old_name] = link_data
                self.save_links()

                QMessageBox.information(self, "Tag Added", f"Tag '{tag}' added to link '{old_name}'.")
                self.populate_tree()
            else:
                QMessageBox.information(self, "Tag Exists", f"Link '{link_item.text(0)}' already has tag '{tag}'.")

    def remove_tag_from_link(self, link_item):
        """
        Prompt user to remove an existing tag from the link.
        """
        link_data = link_item.data(0, Qt.ItemDataRole.UserRole)
        if not link_data or not isinstance(link_data, dict):
            print("[ERROR] link_data is missing or not a dict.")
            return

        tags = link_data.get("tags", [])
        if not tags:
            QMessageBox.information(self, "No Tags", f"No tags available for link '{link_item.text(0)}'.")
            return

        tag, ok = QInputDialog.getItem(
            self, "Remove Tag",
            f"Select a tag to remove from link '{link_item.text(0)}':",
            tags, 0, False
        )
        if ok and tag:
            tags.remove(tag)
            parent_item = link_item.parent()
            project_name = parent_item.text(0)
            link_name = link_item.text(0)
            self.projects[project_name][link_name] = link_data
            self.save_links()
            QMessageBox.information(self, "Tag Removed", f"Removed '{tag}' from link '{link_name}'.")
            self.populate_tree()

    def tag_project(self, project_item):
        """
        Prompt user for a tag and add it to the project's '_tags' list.
        """
        project_data = project_item.data(0, Qt.ItemDataRole.UserRole)
        if not project_data or not isinstance(project_data, dict):
            print("[ERROR] project_data is missing or not a dict.")
            return

        tag, ok = QInputDialog.getText(self, "Add Tag to Project", f"Enter a tag for project '{project_item.text(0)}':")
        if ok and tag:
            if "_tags" not in project_data:
                project_data["_tags"] = []

            if tag not in project_data["_tags"]:
                project_data["_tags"].append(tag)

                project_name = project_item.text(0)
                self.projects[project_name] = project_data
                self.save_links()

                QMessageBox.information(self, "Tag Added", f"Tag '{tag}' added to project '{project_name}'.")
                self.populate_tree()
            else:
                QMessageBox.information(self, "Tag Exists", f"Project '{project_item.text(0)}' already has tag '{tag}'.")

    def remove_tag_from_project(self, project_item):
        """
        Prompt user to remove an existing tag from the project's '_tags'.
        """
        project_data = project_item.data(0, Qt.ItemDataRole.UserRole)
        if not project_data or not isinstance(project_data, dict):
            print("[ERROR] project_data is missing or not a dict.")
            return

        tags = project_data.get("_tags", [])
        if not tags:
            QMessageBox.information(self, "No Tags", f"No tags available for project '{project_item.text(0)}'.")
            return

        tag, ok = QInputDialog.getItem(
            self, "Remove Project Tag",
            f"Select a tag to remove from project '{project_item.text(0)}':",
            tags, 0, False
        )
        if ok and tag:
            tags.remove(tag)
            project_name = project_item.text(0)
            self.projects[project_name] = project_data
            self.save_links()
            QMessageBox.information(self, "Tag Removed", f"Removed '{tag}' from '{project_name}'.")
            self.populate_tree()
