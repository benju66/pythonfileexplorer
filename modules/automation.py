import os
import shutil
import json
from datetime import datetime

class Automation:
    @staticmethod
    def create_folder_from_template(template_path, destination_path, folder_name):
        """Create a new folder from a template."""
        new_folder_path = os.path.join(destination_path, folder_name)
        try:
            if os.path.exists(new_folder_path):
                raise FileExistsError(f"Folder '{folder_name}' already exists in {destination_path}.")

            shutil.copytree(template_path, new_folder_path)
            return new_folder_path
        except Exception as e:
            print(f"Error creating folder from template: {e}")
            return None

    @staticmethod
    def generate_sequential_folder_name(base_path, prefix="E", year=None):
        """Generate a sequential folder name based on existing folders."""
        if year is None:
            year = str(datetime.now().year)[-2:]  # Get the last two digits of the year

        existing_folders = [name for name in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, name))]
        sequential_numbers = []

        for folder in existing_folders:
            if folder.startswith(prefix + year + "-"):
                try:
                    seq_num = int(folder.split("-")[1].split(" ")[0])
                    sequential_numbers.append(seq_num)
                except (IndexError, ValueError):
                    pass

        next_number = max(sequential_numbers, default=0) + 1
        return f"{prefix}{year}-{next_number:03d}"

    @staticmethod
    def create_sequential_folder(template_path, destination_path, project_name, prefix="E", year=None):
        """Create a folder with a sequential name and populate it from a template."""
        folder_name = Automation.generate_sequential_folder_name(destination_path, prefix, year)
        if project_name:
            folder_name += f" - {project_name}"

        return Automation.create_folder_from_template(template_path, destination_path, folder_name)

    @staticmethod
    def load_templates(template_dir):
        """Load available templates from the specified directory."""
        try:
            templates = [
                {
                    "name": os.path.basename(template),
                    "path": os.path.join(template_dir, template)
                }
                for template in os.listdir(template_dir)
                if os.path.isdir(os.path.join(template_dir, template))
            ]
            return templates
        except Exception as e:
            print(f"Error loading templates: {e}")
            return []

# Example usage
if __name__ == "__main__":
    template_path = "templates/project_template"  # Path to the folder template
    destination_path = "projects"  # Path where the new folder will be created

    folder_name = "New Project"

    # Create a folder from a template
    result = Automation.create_folder_from_template(template_path, destination_path, folder_name)
    if result:
        print(f"Folder created: {result}")

    # Create a sequential folder
    sequential_result = Automation.create_sequential_folder(template_path, destination_path, "My Project")
    if sequential_result:
        print(f"Sequential folder created: {sequential_result}")

    # Load templates
    templates = Automation.load_templates("templates")
    print("Available templates:", templates)
