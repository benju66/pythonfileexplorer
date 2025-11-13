# Here is an updated version of file_operations.py with improvements:
# 1. Removed duplicate move_item definition.
# 2. Added docstrings in a consistent style.
# 3. Added basic type hints for clarity.
# 4. Improved error messages and logging.
# 5. Ensured unique file/folder naming logic is consistent.

import os
import shutil
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    filename="file_operations.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

def create_new_file(parent_directory: str, file_name: str = "New File.txt") -> Optional[str]:
    """Create a new file in the specified directory.

    Args:
        parent_directory (str): The directory in which to create the file.
        file_name (str): The desired file name. Defaults to "New File.txt".

    Returns:
        Optional[str]: The path to the newly created file, or None if an error occurred.
    """
    new_file_path = os.path.join(parent_directory, file_name)
    try:
        if not os.path.isdir(parent_directory):
            raise ValueError(f"Parent directory '{parent_directory}' does not exist.")
        
        # Ensure unique file name
        counter = 1
        while os.path.exists(new_file_path):
            base_name, extension = os.path.splitext(file_name)
            new_file_path = os.path.join(
                parent_directory,
                f"{base_name} ({counter}){extension}"
            )
            counter += 1

        with open(new_file_path, 'w', encoding="utf-8") as new_file:
            new_file.write("")  # Create an empty file
        logging.info(f"File created: {new_file_path}")
        return new_file_path
    except Exception as e:
        logging.error(f"Error creating file: {e}")
        return None

def create_new_folder(parent_directory: str, folder_name: str = "New Folder") -> Optional[str]:
    """Create a new folder in the specified directory.

    Args:
        parent_directory (str): The directory in which to create the folder.
        folder_name (str): The desired folder name. Defaults to "New Folder".

    Returns:
        Optional[str]: The path to the newly created folder, or None if an error occurred.
    """
    try:
        if not os.path.isdir(parent_directory):
            raise ValueError(f"Parent directory '{parent_directory}' does not exist.")
        
        # Ensure unique folder name
        counter = 1
        new_folder_path = os.path.join(parent_directory, folder_name)
        while os.path.exists(new_folder_path):
            new_folder_path = os.path.join(
                parent_directory,
                f"{folder_name} ({counter})"
            )
            counter += 1

        os.makedirs(new_folder_path)
        logging.info(f"Folder created: {new_folder_path}")
        return new_folder_path
    except Exception as e:
        logging.error(f"Error creating folder: {e}")
        return None

def rename_item(item_path: str, new_name: str) -> Optional[str]:
    """Rename a file or folder.

    Args:
        item_path (str): The path to the item to rename.
        new_name (str): The new name for the item.

    Returns:
        Optional[str]: The new path if the rename succeeded, or None if it failed.
    """
    try:
        if not os.path.exists(item_path):
            logging.error(f"Error: Item '{item_path}' does not exist.")
            return None
        
        parent_directory = os.path.dirname(item_path)
        new_path = os.path.join(parent_directory, new_name)

        # Prevent overwriting an existing file
        if os.path.exists(new_path):
            logging.error(f"Error: A file with the name '{new_name}' already exists.")
            return None

        # Prevent invalid file names on Windows
        invalid_chars = r'<>:"/\\|?*'
        if any(char in new_name for char in invalid_chars):
            logging.error(f"Error: Invalid characters in filename '{new_name}'.")
            return None

        os.rename(item_path, new_path)
        logging.info(f"Renamed '{item_path}' to '{new_path}'")
        return new_path
    except Exception as e:
        logging.error(f"Error renaming item: {e}")
        return None

def delete_item(item_path: str) -> bool:
    """Delete a file or folder.

    Args:
        item_path (str): The path of the file or folder to delete.

    Returns:
        bool: True if the deletion succeeded, False otherwise.
    """
    try:
        if not os.path.exists(item_path):
            raise ValueError(f"Item '{item_path}' does not exist.")

        if os.path.isfile(item_path):
            os.remove(item_path)
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)
        logging.info(f"Deleted: {item_path}")
        return True
    except Exception as e:
        logging.error(f"Error deleting item: {e}")
        return False

def copy_item(source_path: str, destination_path: str) -> Optional[str]:
    """Copy a file or folder to a new location, ensuring unique names.

    Args:
        source_path (str): The path to the file or folder to copy.
        destination_path (str): The directory to which the item will be copied.

    Returns:
        Optional[str]: The path to the copied item, or None if an error occurred.
    """
    try:
        if not os.path.exists(source_path):
            raise ValueError(f"Source '{source_path}' does not exist.")

        base_name, extension = os.path.splitext(os.path.basename(source_path))
        new_path = os.path.join(destination_path, os.path.basename(source_path))
        counter = 1

        # Generate a unique name if there's a conflict
        while os.path.exists(new_path):
            if os.path.isdir(source_path):
                new_path = os.path.join(destination_path, f"{base_name} ({counter})")
            else:
                new_path = os.path.join(destination_path, f"{base_name} ({counter}){extension}")
            counter += 1

        if os.path.isfile(source_path):
            shutil.copy2(source_path, new_path)
        elif os.path.isdir(source_path):
            shutil.copytree(source_path, new_path)

        logging.info(f"Copied '{source_path}' to '{new_path}'")
        return new_path
    except Exception as e:
        logging.error(f"Error copying item from '{source_path}' to '{destination_path}': {e}")
        return None

def move_item(source_path: str, destination_path: str) -> bool:
    """Move a file or folder to a new location.

    Args:
        source_path (str): The path to the file or folder to move.
        destination_path (str): The directory or path where the item will be moved.

    Returns:
        bool: True if the move succeeded, False otherwise.
    """
    try:
        if not os.path.exists(source_path):
            raise ValueError(f"Source '{source_path}' does not exist.")

        shutil.move(source_path, destination_path)
        logging.info(f"Moved '{source_path}' to '{destination_path}'")
        return True
    except Exception as e:
        logging.error(f"Error moving item: {e}")
        return False
