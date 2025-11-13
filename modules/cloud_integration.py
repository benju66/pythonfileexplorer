import os
import requests
from msal import PublicClientApplication

class OneDriveIntegration:
    def __init__(self, client_id, authority, scopes):
        """Initialize OneDrive integration with Microsoft Graph API."""
        self.client_id = client_id
        self.authority = authority
        self.scopes = scopes
        self.token_cache = {}  # Token cache for authentication
        self.app = PublicClientApplication(
            client_id=self.client_id, authority=self.authority, token_cache=self.token_cache
        )

    def authenticate(self):
        """Authenticate the user with Microsoft Graph API."""
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(self.scopes, account=accounts[0])
        else:
            result = self.app.acquire_token_interactive(scopes=self.scopes)

        if "access_token" in result:
            return result["access_token"]
        else:
            raise Exception("Authentication failed.")

    def list_files(self, folder_id=None):
        """List files and folders in OneDrive."""
        access_token = self.authenticate()
        headers = {"Authorization": f"Bearer {access_token}"}
        base_url = "https://graph.microsoft.com/v1.0/me/drive/root"

        if folder_id:
            url = f"{base_url}/items/{folder_id}/children"
        else:
            url = f"{base_url}/children"

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            raise Exception(f"Error listing files: {response.text}")

    def upload_file(self, file_path, folder_id=None):
        """Upload a file to OneDrive."""
        access_token = self.authenticate()
        headers = {"Authorization": f"Bearer {access_token}"}
        base_url = "https://graph.microsoft.com/v1.0/me/drive/root"

        file_name = os.path.basename(file_path)
        with open(file_path, "rb") as file_data:
            if folder_id:
                url = f"{base_url}/items/{folder_id}:/{file_name}:/content"
            else:
                url = f"{base_url}:/{file_name}:/content"

            response = requests.put(url, headers=headers, data=file_data)
            if response.status_code in (200, 201):
                return response.json()
            else:
                raise Exception(f"Error uploading file: {response.text}")

    def download_file(self, file_id, destination_path):
        """Download a file from OneDrive."""
        access_token = self.authenticate()
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"

        response = requests.get(url, headers=headers, stream=True)
        if response.status_code == 200:
            with open(destination_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            return destination_path
        else:
            raise Exception(f"Error downloading file: {response.text}")

# Example usage
if __name__ == "__main__":
    client_id = "YOUR_CLIENT_ID"
    authority = "https://login.microsoftonline.com/YOUR_TENANT_ID"
    scopes = ["Files.ReadWrite"]

    onedrive = OneDriveIntegration(client_id, authority, scopes)

    try:
        # List files in the root directory
        files = onedrive.list_files()
        print("Files:", files)

        # Upload a file
        result = onedrive.upload_file("example.txt")
        print("Uploaded file:", result)

        # Download a file
        download_result = onedrive.download_file("FILE_ID", "downloaded_example.txt")
        print("Downloaded file:", download_result)

    except Exception as e:
        print("Error:", e)
