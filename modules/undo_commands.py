# modules/undo_commands.py
from modules.undo_manager import Command
from modules.file_operations import rename_item, delete_item, create_new_file, create_new_folder
import os

class RenameCommand(Command):
    """
    Existing rename command.
    If you want to check for rename failures or store success flags,
    you can expand this further.
    """
    def __init__(self, old_path: str, new_name: str):
        self.old_path = old_path
        self.new_path = None
        self.new_name = new_name

    def do(self):
        # Actually rename
        self.new_path = rename_item(self.old_path, self.new_name)
        # rename_item returns the new path or None on error

    def undo(self):
        # Undo by renaming back
        if self.new_path:
            folder = os.path.dirname(self.new_path)
            old_name = os.path.basename(self.old_path)
            rename_item(self.new_path, old_name)

class CreateFileCommand(Command):
    """
    Creates a new file in a specified directory. On undo, it deletes the file.
    """
    def __init__(self, file_tree, parent_dir, file_name):
        super().__init__()
        self.file_tree = file_tree
        self.parent_dir = parent_dir
        self.file_name = file_name
        self.created_path = None

    def do(self):
        self.created_path = create_new_file(self.parent_dir, self.file_name)
        if self.created_path:
            # Refresh the FileTree to show the new file
            self.file_tree.set_root_directory(self.parent_dir)

    def undo(self):
        if self.created_path and os.path.exists(self.created_path):
            delete_item(self.created_path)
            self.file_tree.set_root_directory(self.parent_dir)

class CreateFolderCommand(Command):
    """
    Creates a new folder in a specified directory. On undo, it removes that folder.
    """
    def __init__(self, file_tree, parent_dir, folder_name):
        super().__init__()
        self.file_tree = file_tree
        self.parent_dir = parent_dir
        self.folder_name = folder_name
        self.created_path = None

    def do(self):
        self.created_path = create_new_folder(self.parent_dir, self.folder_name)
        if self.created_path:
            self.file_tree.set_root_directory(self.parent_dir)

    def undo(self):
        if self.created_path and os.path.exists(self.created_path):
            delete_item(self.created_path)
            self.file_tree.set_root_directory(self.parent_dir)

class DeleteItemCommand(Command):
    """
    Minimal approach: permanently deletes a file or folder from disk.
    Undo won't actually restore it. If you want to truly restore, 
    consider 'moving' to a hidden trash folder instead of deleting.
    """
    def __init__(self, file_tree, target_path):
        super().__init__()
        self.file_tree = file_tree
        self.target_path = target_path
        self.parent_dir = os.path.dirname(target_path)
        self.was_deleted = False

    def do(self):
        if os.path.exists(self.target_path):
            self.was_deleted = delete_item(self.target_path)
        self.file_tree.set_root_directory(self.parent_dir)

    def undo(self):
        """
        This example won't restore the file, because it's gone.
        If you want real undo, you must not truly delete it in do().
        Instead do something like "move to hidden folder".
        """
        pass
