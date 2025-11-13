import os
import datetime
from PyPDF2 import PdfReader
from docx import Document
# 1) Import the fuzzy matching library
from thefuzz import fuzz

class FileSearch:

    @staticmethod
    def search_by_name(directory, query, include_folders=True, depth=None):
        """
        Search for files and folders by exact substring match 
        within the specified directory.
        """
        results = []
        try:
            for root, dirs, files in os.walk(directory):
                if include_folders:
                    for dir_name in dirs:
                        if query.lower() in dir_name.lower():
                            results.append(os.path.join(root, dir_name))

                for file_name in files:
                    if query.lower() in file_name.lower():
                        results.append(os.path.join(root, file_name))

                # Stop searching deeper if depth is specified
                if depth is not None:
                    depth -= 1
                    if depth <= 0:
                        break  
        except PermissionError:
            print(f"[ERROR] Permission denied: {directory}")
        except Exception as e:
            print(f"[ERROR] Search failed in {directory}: {e}")
        return results

    @staticmethod
    def fuzzy_search_by_name(directory, query, threshold=60, include_folders=True, depth=None):
        """
        Search for files/folders by fuzzy matching within the specified directory.
        
        :param directory:     The root directory to start searching from
        :param query:         The user’s search text (approximate matches allowed)
        :param threshold:     Minimum similarity score (0-100) to consider a match
        :param include_folders: Whether to include folders in the search
        :param depth:         How many levels of subfolders to descend (None = unlimited)
        :return:              A list of file/folder paths whose names are fuzzy-matched
        """
        results = []
        try:
            for root, dirs, files in os.walk(directory):
                if include_folders:
                    for dir_name in dirs:
                        score = fuzz.partial_ratio(query.lower(), dir_name.lower())
                        if score >= threshold:
                            results.append(os.path.join(root, dir_name))

                for file_name in files:
                    score = fuzz.partial_ratio(query.lower(), file_name.lower())
                    if score >= threshold:
                        results.append(os.path.join(root, file_name))

                # Stop searching deeper if depth is specified
                if depth is not None:
                    depth -= 1
                    if depth <= 0:
                        break  
        except PermissionError:
            print(f"[ERROR] Permission denied: {directory}")
        except Exception as e:
            print(f"[ERROR] Fuzzy search failed in {directory}: {e}")
        return results

    @staticmethod
    def search_with_filters(directory, query, file_type=None, size_range=None, date_range=None):
        """
        Advanced search with optional filters for file type, size, and date range.
        """
        results = []
        try:
            for root, dirs, files in os.walk(directory):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    # Basic name check (exact substring)
                    if query.lower() not in file_name.lower():
                        continue

                    # Filter by file type
                    if file_type and not file_name.lower().endswith(file_type.lower()):
                        continue

                    # Filter by size
                    if size_range:
                        try:
                            file_size = os.path.getsize(file_path)
                            if file_size < size_range[0] or file_size > size_range[1]:
                                continue
                        except OSError:
                            print(f"[WARNING] Could not retrieve size for {file_path}")
                            continue

                    # Filter by date
                    if date_range:
                        try:
                            file_mtime = os.path.getmtime(file_path)
                            file_date = datetime.datetime.fromtimestamp(file_mtime)
                            if file_date < date_range[0] or file_date > date_range[1]:
                                continue
                        except OSError:
                            print(f"[WARNING] Could not retrieve date for {file_path}")
                            continue

                    results.append(file_path)
        except PermissionError:
            print(f"[ERROR] Permission denied: {directory}")
        except Exception as e:
            print(f"[ERROR] Filtered search failed in {directory}: {e}")
        return results

    @staticmethod
    def search_file_content(directory, query, max_results=10):
        """
        Search for content within files (supports PDFs and DOCX).
        """
        results = []
        try:
            for root, dirs, files in os.walk(directory):
                for file_name in files:
                    file_path = os.path.join(root, file_name)

                    # Skip unsupported files
                    if not file_name.lower().endswith((".pdf", ".docx")):
                        continue

                    try:
                        if file_name.lower().endswith(".pdf"):
                            reader = PdfReader(file_path)
                            for page in reader.pages:
                                text = page.extract_text()
                                if text and query.lower() in text.lower():
                                    results.append(file_path)
                                    break  # ✅ Stop after first match

                        elif file_name.lower().endswith(".docx"):
                            document = Document(file_path)
                            for paragraph in document.paragraphs:
                                if query.lower() in paragraph.text.lower():
                                    results.append(file_path)
                                    break  # ✅ Stop after first match

                    except Exception as e:
                        print(f"[ERROR] Failed to read {file_path}: {e}")

                    if len(results) >= max_results:
                        return results  # ✅ Stop early if max results are found
        except PermissionError:
            print(f"[ERROR] Permission denied: {directory}")
        except Exception as e:
            print(f"[ERROR] Content search failed in {directory}: {e}")
        return results


# Example usage
if __name__ == "__main__":
    # Use a raw string to avoid backslash escape problems.
    search_directory = r"C:\Users"
    search_query = "example"

    print("Exact substring search (search_by_name):")
    results = FileSearch.search_by_name(search_directory, search_query, include_folders=True, depth=2)
    for result in results:
        print("  ", result)

    print("\nFuzzy search by name (fuzzy_search_by_name):")
    # Trying a slight typo: "exmple"
    fuzzy_results = FileSearch.fuzzy_search_by_name(search_directory, "exmple", threshold=60)
    for result in fuzzy_results:
        print("  ", result)

    print("\nSearch with filters:")
    filtered_results = FileSearch.search_with_filters(
        search_directory, search_query, file_type=".txt", size_range=(0, 10000)
    )
    for result in filtered_results:
        print("  ", result)

    print("\nSearch file content (PDF/DOCX):")
    content_results = FileSearch.search_file_content(search_directory, search_query, max_results=5)
    for result in content_results:
        print("  ", result)
