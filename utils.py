
import shutil
import sys
import os
import platform
import subprocess
import traceback
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox # For copy_to_clipboard & open_folder

# No changes needed to constants import here

def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller bundles.

    Args:
        relative_path: The relative path to the resource file (e.g., "icon.ico").

    Returns:
        The absolute path to the resource.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS (for --onefile)
        if hasattr(sys, '_MEIPASS'):
            # This is the path to the extracted files in the temp folder
            base_path = sys._MEIPASS
        # Check if running as a bundled executable (covers --onedir)
        # elif getattr(sys, 'frozen', False): # This condition might be redundant with _MEIPASS for --onefile
        #      base_path = os.path.dirname(sys.executable)
        else:
             # Not frozen, running from source.
             # Base path is directory containing *this* script file (__file__).
             # Since all scripts are now in the root, this should be the project root.
             base_path = os.path.dirname(os.path.abspath(__file__))
             # If __file__ isn't reliable, fallback to current working directory might be needed
             # base_path = os.path.abspath(".")

    except Exception as e:
         print(f"Warning: Error determining base path in resource_path: {e}")
         base_path = os.path.abspath(".") # Use current working directory as last resort

    final_path = os.path.join(base_path, relative_path)
    # print(f"Resource path resolved: '{relative_path}' -> '{final_path}' (Base: '{base_path}')") # Optional Debug print
    return os.path.normpath(final_path)

def open_containing_folder(folder_path: Path) -> tuple[bool, str | None]:
    """
    Opens the specified folder path in the system's file explorer.

    Args:
        folder_path: A Path object representing the folder to open.

    Returns:
        A tuple (success: bool, error_message: str | None).
    """
    folder_path_str = str(folder_path)
    if not folder_path.is_dir(): # Check if it exists and is a directory
        error_msg = f"Cannot open folder, path is not a valid directory: {folder_path_str}"
        print(error_msg)
        return False, error_msg

    try:
        print(f"Attempting to open folder: {folder_path_str}") # Debug
        system = platform.system()
        if system == "Windows":
            # os.startfile is generally reliable for opening folders on Windows
            os.startfile(folder_path_str)
        elif system == "Darwin": # macOS
            subprocess.run(["open", folder_path_str], check=True)
        else: # Linux and other Unix-like
            subprocess.run(["xdg-open", folder_path_str], check=True)
        print(f"Opened folder: {folder_path_str}")
        return True, None
    except FileNotFoundError:
        # Handle case where the command (open, xdg-open) isn't found
        error_msg = f"File explorer command not found for '{system}'. Cannot open folder."
        print(error_msg)
        return False, error_msg
    except subprocess.CalledProcessError as e:
        # Handle errors reported by the command itself
        error_msg = f"Command failed to open folder '{folder_path_str}': {e}"
        print(error_msg)
        return False, error_msg
    except Exception as e:
        # Catch-all for other potential issues
        error_msg = f"An unexpected error occurred trying to open folder '{folder_path_str}': {e}"
        print(error_msg)
        traceback.print_exc()
        return False, error_msg

def copy_to_clipboard(text: str) -> tuple[bool, str | None]:
    """
    Copies the given text to the system clipboard using QApplication.

    Args:
        text: The string to copy.

    Returns:
        A tuple (success: bool, error_message: str | None).
    """
    try:
        clipboard = QApplication.clipboard()
        if clipboard is None:
            # This might happen if QApplication instance doesn't exist,
            # although unlikely when called from within the app.
            raise RuntimeError("Could not access clipboard (QApplication instance needed).")
        clipboard.setText(text)
        print(f"Copied to clipboard: '{text[:50]}...'")
        return True, None
    except Exception as e:
        error_msg = f"Failed to copy to clipboard: {e}"
        print(error_msg)
        traceback.print_exc()
        return False, error_msg

def safe_read_file(file_path: Path) -> tuple[str | None, str | None]:
    """
    Reads a file, trying UTF-8 then fallback encoding, handling errors.

    Args:
        file_path: Path object for the file.

    Returns:
        tuple: (content: str | None, error_message: str | None)
               Content is None if reading fails.
    """
    content = None
    error_message = None
    try:
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not os.access(str(file_path), os.R_OK):
             raise PermissionError(f"Permission denied reading file: {file_path.name}")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            warning_msg = f"Warning: {file_path.name} is not UTF-8 encoded. Attempting fallback."
            print(warning_msg)
            # Log this warning somewhere accessible if needed (e.g., app log area)
            try:
                # Try default system encoding (use with caution)
                content = file_path.read_text(encoding=None)
            except Exception as fallback_e:
                # Raise the original decode error but add context
                raise UnicodeDecodeError("utf-8", b'', 0, 0, f"File not UTF-8 and fallback failed: {fallback_e}") from fallback_e

    except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
        error_message = f"Error reading {file_path.name}: {e}"
        print(error_message)
    except Exception as e:
        error_message = f"Unexpected error loading {file_path.name}: {e}"
        print(error_message)
        traceback.print_exc()

    return content, error_message

def safe_write_file(file_path: Path, content: str) -> tuple[bool, str | None]:
    """
    Writes content to a file using UTF-8 encoding, handling errors.

    Args:
        file_path: Path object for the file.
        content: The string content to write.

    Returns:
        tuple: (success: bool, error_message: str | None)
    """
    error_message = None
    success = False
    try:
        parent_dir = file_path.parent
        # Check permissions before writing
        can_write_target = (file_path.exists() and os.access(str(file_path), os.W_OK)) or \
                           (not file_path.exists() and os.access(str(parent_dir), os.W_OK))

        if not can_write_target:
            perm_issue = f"writing to file {file_path.name}" if file_path.exists() else f"writing to directory {parent_dir}"
            raise PermissionError(f"Permission denied {perm_issue}")

        file_path.write_text(content, encoding="utf-8")
        success = True

    except PermissionError as pe:
        error_message = f"Write Error: {pe}"
        print(error_message)
    except Exception as e:
        error_message = f"Failed to write file {file_path.name}: {e}"
        print(error_message)
        traceback.print_exc()

    return success, error_message


def backup_and_redo(file_path: Path) -> tuple[bool, str | None]:
    """
    Handles creating .bak and .redo files before a modification.

    Creates '.redo' with the current file content.
    Creates '.bak' with the current file content ONLY if '.bak' doesn't already exist.

    Args:
        file_path: The Path object of the file being modified.

    Returns:
        tuple: (success: bool, error_message: str | None)
    """
    try:
        if not file_path.exists():
            # If the target file doesn't exist, there's nothing to back up or save for redo.
            # This might happen if applying content to create a new file.
            # We might want to remove potentially orphaned .bak/.redo files in this case.
            redo_path = file_path.with_suffix(file_path.suffix + ".redo")
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            if redo_path.exists(): redo_path.unlink(missing_ok=True)
            # Decide if we want to remove the backup too. Let's keep it for now.
            # if backup_path.exists(): backup_path.unlink(missing_ok=True)
            print(f"Target file {file_path.name} does not exist, skipping backup/redo creation.")
            return True, None # Considered success as there's nothing to do

        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        redo_path = file_path.with_suffix(file_path.suffix + ".redo")
        parent_dir = file_path.parent

        # --- Check Permissions ---
        can_read_target = os.access(str(file_path), os.R_OK)
        can_write_dir = os.access(str(parent_dir), os.W_OK)

        if not can_read_target:
            raise PermissionError(f"Permission denied reading file for backup/redo: {file_path.name}")
        if not can_write_dir:
            raise PermissionError(f"Permission denied writing backup/redo files in directory: {parent_dir}")

        # --- Perform Operations ---
        # 1. Save current state to redo path (overwrite existing redo if present)
        shutil.copy2(str(file_path), redo_path) # copy2 preserves metadata

        # 2. Create backup only if it doesn't exist
        if not backup_path.exists():
            shutil.copy2(str(file_path), backup_path)

        return True, None # Success

    except PermissionError as pe:
        error_msg = f"Backup/Redo Error: {pe}"
        print(error_msg)
        return False, error_msg
    except (OSError, shutil.Error) as e:
        error_msg = f"Backup/Redo file operation error for {file_path.name}: {e}"
        print(error_msg)
        traceback.print_exc()
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error during backup/redo for {file_path.name}: {e}"
        print(error_msg)
        traceback.print_exc()
        return False, error_msg
# --- END OF FILE utils.txt ---