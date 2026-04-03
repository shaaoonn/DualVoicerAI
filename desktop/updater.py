"""
Auto-Update System for Dual Voicer
Checks for updates from GitHub repository and downloads new versions
"""

import requests
import os
import sys
import threading
import subprocess
from pathlib import Path
import tempfile

class UpdateChecker:
    def __init__(self, current_version, repo_url):
        """
        Initialize Update Checker
        
        Args:
            current_version (str): Current version of the application (e.g., "1.0")
            repo_url (str): GitHub repository URL for version.json
        """
        self.current_version = current_version
        self.repo_url = repo_url
        self.version_check_url = f"{repo_url}/version.json"
        self.latest_version = None
        self.download_url = None
        self.release_notes = None
        
    def check_for_updates(self):
        """
        Check if a new version is available
        
        Returns:
            dict: Update information or None if no update available
        """
        try:
            # Fetch version.json from GitHub
            headers = {'User-Agent': 'DualVoicer-AutoUpdater/1.0'}
            response = requests.get(self.version_check_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            self.latest_version = data.get("version", "1.0")
            self.download_url = data.get("download_url", "")
            self.release_notes = data.get("release_notes", "New update available")
            
            # Compare versions
            if self._compare_versions(self.latest_version, self.current_version):
                return {
                    "available": True,
                    "version": self.latest_version,
                    "download_url": self.download_url,
                    "release_notes": self.release_notes
                }
            else:
                return {
                    "available": False,
                    "message": "You are using the latest version"
                }
                
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to check for updates: {e}")
            return {
                "available": False,
                "error": str(e),
                "message": "Failed to connect to update server"
            }
        except Exception as e:
            print(f"[ERROR] Update check error: {e}")
            return {
                "available": False,
                "error": str(e),
                "message": "Update check failed"
            }
    
    def _compare_versions(self, latest, current):
        """
        Compare version strings
        
        Args:
            latest (str): Latest version from server
            current (str): Current version
            
        Returns:
            bool: True if latest > current
        """
        try:
            # Convert versions to comparable tuples (e.g., "2.0.1" -> (2, 0, 1))
            latest_parts = tuple(map(int, latest.split('.')))
            current_parts = tuple(map(int, current.split('.')))
            
            return latest_parts > current_parts
        except:
            # Fallback to string comparison
            return latest > current


class UpdateDownloader:
    def __init__(self, download_url, progress_callback=None):
        """
        Initialize Update Downloader
        
        Args:
            download_url (str): URL to download the installer
            progress_callback (callable): Callback function for progress updates
        """
        self.download_url = download_url
        self.progress_callback = progress_callback
        self.download_path = None
        self.is_downloading = False
        
    def download_update(self):
        """
        Download the update installer
        
        Returns:
            str: Path to downloaded file or None if failed
        """
        try:
            self.is_downloading = True
            
            # Use User's Downloads Folder instead of Temp
            downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            # Create "Dual Voicer Updates" folder inside Downloads for organization
            update_dir = os.path.join(downloads_dir, "Dual Voicer Updates")
            if not os.path.exists(update_dir):
                os.makedirs(update_dir)
                
            filename = "DualVoicer_Setup.exe"
            self.download_path = os.path.join(update_dir, filename)
            
            # Download with progress
            print(f"[INFO] Downloading update to: {self.download_path}")
            headers = {'User-Agent': 'DualVoicer-AutoUpdater/1.0'}
            response = requests.get(self.download_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(self.download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Update progress
                        if self.progress_callback and total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            self.progress_callback(progress, downloaded_size, total_size)
            
            self.is_downloading = False
            print(f"[INFO] Update downloaded successfully to: {self.download_path}")
            return self.download_path
            
        except Exception as e:
            self.is_downloading = False
            print(f"[ERROR] Download failed: {e}")
            return None
    
    def download_async(self, completion_callback=None):
        """
        Download update in background thread
        
        Args:
            completion_callback (callable): Called when download completes
        """
        def download_thread():
            result = self.download_update()
            if completion_callback:
                completion_callback(result)
        
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()


class UpdateInstaller:
    @staticmethod
    def install_update(installer_path, close_current_app=True):
        """
        Run the installer and optionally close current application
        
        Args:
            installer_path (str): Path to the installer executable
            close_current_app (bool): Whether to close current app before installing
        """
        try:
            if not os.path.exists(installer_path):
                print(f"[ERROR] Installer not found: {installer_path}")
                return False
            
            print(f"[INFO] Launching installer: {installer_path}")
            
            # Use os.startfile for Windows - acts like double-clicking the file
            # This is robust and launches independently of the parent process
            try:
                os.startfile(installer_path)
            except AttributeError:
                # Fallback for non-Windows (though this is a Windows app)
                subprocess.Popen([installer_path], shell=True)
            
            # Close current application
            if close_current_app:
                # Give a small delay for the installer to start initializing
                import time
                time.sleep(1.0) 
                print("[INFO] Closing application to allow update...")
                # Force exit
                os._exit(0)
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to run installer: {e}")
            return False


# Utility function for main application
def format_size(bytes_size):
    """
    Format bytes to human-readable size
    
    Args:
        bytes_size (int): Size in bytes
        
    Returns:
        str: Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"
