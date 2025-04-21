# --- utils.py ---

import sys
import os
import platform
import subprocess
import shutil
import traceback
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox # Added QMessageBox for error display

# --- ADDED: Import constant for backup dir ---
from constants import CODE_HELPER_BACKUP_DIR_NAME

# --- Resource Path Handling (For PyInstaller Bundles) ---
def resource_path(relative_path: str) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
        # Ensure base_path is a string (it should be, but helps type checkers)
        base_path_str = str(base_path)
    except Exception:
        # _MEIPASS not defined, so running in development mode
        # Assume the resource is in the same directory as this script
        # Use Path(__file__).parent for robustness
        base_path_str = str(Path(__file__).parent)

    # Join the base path and the relative path using os.path.join
    # This handles path separators correctly across OSes
    return os.path.join(base_path_str, relative_path)


# --- File/Folder Operations ---
def open_containing_folder(path_obj: Path) -> tuple[bool, str | None]:
    """Opens the directory containing the given file or directory path."""
    if not path_obj.exists():
        return False, f"Path does not exist: {path_obj}"
    if not path_obj.is_dir(): # If it's a file, get its parent directory
        target_dir = path_obj.parent
    else: # It's already a directory
        target_dir = path_obj

    try:
        # Convert Path object to string for OS compatibility
        target_dir_str = str(target_dir.resolve()) # Use resolve() for absolute path

        system = platform.system()
        if system == "Windows":
            # Use os.startfile on Windows for more robust opening
            os.startfile(target_dir_str)
            return True, None
        elif system == "Darwin": # macOS
            subprocess.run(["open", target_dir_str], check=True)
            return True, None
        else: # Linux and other Unix-like
            subprocess.run(["xdg-open", target_dir_str], check=True)
            return True, None
    except FileNotFoundError as e:
        # Handle cases where 'open' or 'xdg-open' might not be found
        return False, f"Could not find command to open folder: {e}"
    except PermissionError as e:
        return False, f"Permission denied opening folder: {e}"
    except subprocess.CalledProcessError as e:
        # Handle errors from the subprocess command itself
        return False, f"Failed to open folder (process error): {e}"
    except Exception as e:
        # Catch any other unexpected errors
        return False, f"An unexpected error occurred opening folder: {e}"


def copy_to_clipboard(text: str) -> tuple[bool, str | None]:
    """Copies the given text to the system clipboard."""
    try:
        clipboard = QApplication.clipboard()
        if clipboard is None:
            # This can happen in environments without a GUI session (e.g., some CI/CD)
            return False, "Clipboard service not available."
        clipboard.setText(text)
        return True, None
    except Exception as e:
        return False, f"Failed to copy to clipboard: {e}"


# --- File I/O Safety ---
def safe_read_file(file_path: Path) -> tuple[str | None, str | None]:
    """Reads file content safely, handling potential errors."""
    content = None
    error = None
    try:
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not os.access(str(file_path), os.R_OK):
            raise PermissionError(f"Permission denied reading file: {file_path.name}")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"Warning: Non UTF-8 file {file_path.name}. Trying fallback encoding.")
            try:
                content = file_path.read_text(encoding=None) # System default
            except Exception as fallback_e:
                raise UnicodeDecodeError("utf-8", b'', 0, 0, f"Not UTF-8 and fallback failed: {fallback_e}") from fallback_e

    except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
        error = str(e)
    except Exception as e:
        error = f"Unexpected read error for {file_path.name}: {e}"
        print(error) # Log unexpected errors
        traceback.print_exc()
    return content, error


def safe_write_file(file_path: Path, content: str) -> tuple[bool, str | None]:
    """Writes content to a file safely, handling potential errors."""
    error = None
    success = False
    try:
        # Check if directory exists and is writable before attempting write
        parent_dir = file_path.parent
        if not parent_dir.exists():
            raise FileNotFoundError(f"Parent directory does not exist: {parent_dir}")
        if not os.access(str(parent_dir), os.W_OK):
            raise PermissionError(f"Permission denied writing to directory: {parent_dir}")
        # Check if file exists and is writable (if it exists)
        if file_path.exists() and not os.access(str(file_path), os.W_OK):
             raise PermissionError(f"Permission denied writing to file: {file_path.name}")

        file_path.write_text(content, encoding="utf-8")
        success = True

    except (PermissionError, FileNotFoundError, OSError) as e: # Catch common I/O errors
        error = str(e)
    except Exception as e:
        error = f"Unexpected write error for {file_path.name}: {e}"
        print(error) # Log unexpected errors
        traceback.print_exc()
    return success, error

# --- NEW FUNCTION: Get Central Backup Paths ---
def get_central_backup_paths(original_file_path: Path) -> tuple[Path | None, Path | None, Path | None, str | None]:
    """
    Calculates the corresponding .bak and .redo file paths in a central backup directory.

    Creates the central directory and necessary subdirectories if they don't exist.

    Args:
        original_file_path: The Path object of the original source file.

    Returns:
        A tuple containing:
        - central_backup_dir (Path | None): The root backup directory path, or None on error.
        - backup_path (Path | None): The full path for the .bak file, or None on error.
        - redo_path (Path | None): The full path for the .redo file, or None on error.
        - error_message (str | None): An error message if directory creation failed, otherwise None.
    """
    error_message = None
    central_backup_dir = None
    backup_path = None
    redo_path = None

    try:
        # 1. Get User Home and Central Backup Root Directory
        home_dir = Path.home()
        central_backup_dir = home_dir / CODE_HELPER_BACKUP_DIR_NAME

        # 2. Construct Path Inside Backup Directory (Mirroring Original Structure)
        # - Get parts relative to the drive/anchor
        relative_parts = original_file_path.parts[len(original_file_path.anchor):]

        # - Handle drive letter (Windows) safely - remove colon
        drive = original_file_path.drive
        sanitized_drive = drive.replace(":", "") if drive else ""

        # - Combine base backup dir, sanitized drive (if any), and relative parts
        target_base_in_backup = central_backup_dir
        if sanitized_drive:
            target_base_in_backup = target_base_in_backup / sanitized_drive
        for part in relative_parts:
            target_base_in_backup = target_base_in_backup / part

        # 3. Define Full Backup and Redo Paths
        backup_path = target_base_in_backup.with_suffix(target_base_in_backup.suffix + ".bak")
        redo_path = target_base_in_backup.with_suffix(target_base_in_backup.suffix + ".redo")

        # 4. Ensure Destination Directory Exists in Backup Location
        #    Create parent directories for the backup/redo files *within* the central store.
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        # redo_path.parent will be the same, so no need to call mkdir again

    except PermissionError as e:
        error_message = f"Permission denied creating backup directory structure: {e}"
        print(error_message)
        # Reset paths on error
        central_backup_dir, backup_path, redo_path = None, None, None
    except Exception as e:
        error_message = f"Error getting/creating central backup paths: {e}"
        print(error_message)
        traceback.print_exc()
        # Reset paths on error
        central_backup_dir, backup_path, redo_path = None, None, None

    return central_backup_dir, backup_path, redo_path, error_message


# --- MODIFIED FUNCTION: Backup and Redo ---
def backup_and_redo(original_file_path: Path) -> tuple[bool, str | None]:
    """
    Creates/updates backup (.bak) and redo (.redo) files for a given file
    in a central backup location.

    1. Gets the central backup paths using `get_central_backup_paths`.
    2. If a `.redo` file exists in the central location, it's moved to `.bak` (overwriting old .bak).
    3. The current `original_file_path` content is copied to the `.redo` file in the central location.

    Args:
        original_file_path: The Path object of the file being modified.

    Returns:
        A tuple containing:
        - True if the operation was successful, False otherwise.
        - An error message string if an error occurred, otherwise None.
    """
    # --- Step 1: Get Central Paths ---
    central_backup_dir, backup_path, redo_path, path_err = get_central_backup_paths(original_file_path)
    if path_err:
        return False, f"Failed to determine backup paths: {path_err}"
    if not backup_path or not redo_path: # Should not happen if path_err is None, but check defensively
         return False, "Failed to determine backup paths (unknown reason)."

    try:
        # --- Step 2: Handle Existing Redo File ---
        # Check if redo exists *in the central location*
        if redo_path.exists():
            # Check permissions before replacing backup
            if backup_path.exists() and not os.access(str(backup_path), os.W_OK):
                 raise PermissionError(f"Cannot overwrite existing central backup file: {backup_path.name}")
            if not os.access(str(redo_path), os.R_OK):
                 raise PermissionError(f"Cannot read existing central redo file: {redo_path.name}")
            if not os.access(str(backup_path.parent), os.W_OK): # Check write permission for backup dir
                 raise PermissionError(f"Cannot write to central backup directory: {backup_path.parent}")

            # Move .redo to .bak (atomic replace if possible, handles overwrite)
            # os.replace is generally preferred over shutil.move for atomic potential
            print(f"Moving existing central redo {redo_path} to central bak {backup_path}")
            os.replace(str(redo_path), str(backup_path))

        # --- Step 3: Copy Current File to Redo ---
        # Check permissions for the original file and the central redo location
        if not original_file_path.exists():
            # If the original file doesn't exist (e.g., being created), we can't create a redo state from it.
            # This might be okay depending on the workflow, but let's log a warning.
            print(f"Warning: Original file {original_file_path} does not exist; cannot create redo state.")
            # We might still want to create the .bak from the .redo if it existed.
            # Decide if this should be an error or just skip redo creation.
            # For now, let's allow the operation to succeed if the .bak was handled.
            return True, None # Return success, but no redo state was created.

        if not os.access(str(original_file_path), os.R_OK):
            raise PermissionError(f"Cannot read original file: {original_file_path.name}")
        if not os.access(str(redo_path.parent), os.W_OK): # Check write permission for redo dir
             raise PermissionError(f"Cannot write to central redo directory: {redo_path.parent}")

        # Copy current original file content to the central .redo file
        # Use copy2 to preserve metadata if desired, though maybe not critical for redo
        print(f"Copying {original_file_path} to central redo {redo_path}")
        shutil.copy2(str(original_file_path), str(redo_path))

        return True, None # Success

    except (PermissionError, OSError, shutil.Error) as e:
        error_msg = f"Backup/Redo file operation failed: {e}"
        print(error_msg)
        traceback.print_exc()
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error during backup/redo: {e}"
        print(error_msg)
        traceback.print_exc()
        return False, error_msg