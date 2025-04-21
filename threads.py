
import os
import re
import shutil
import difflib
import traceback
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

# --- CHANGED IMPORT ---
from formatter_utils import preprocess_and_format_with_black # Use the new formatter utility
# --- END CHANGE ---
from utils import backup_and_redo, safe_write_file

# --- File Scanning Thread ---
class FileLoaderThread(QThread):
    """
    Scans a directory recursively for Python files (`*.py`) in the background.

    Signals:
        files_loaded (list[Path], str): Emitted when scanning is complete.
                                        Provides a list of found Path objects
                                        and the original folder path scanned.
                                        List is empty if cancelled or error.
        error_occurred (str): Emitted if a significant error occurs during scanning
                              (e.g., permission denied on the root folder).
    """
    files_loaded = pyqtSignal(list, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, folder_path: str, parent=None):
        """
        Initializes the file loader thread.

        Args:
            folder_path: The absolute path to the folder to scan.
            parent: Optional parent object.
        """
        super().__init__(parent)
        self.folder_path = folder_path
        self._is_running = True # Flag to control cancellation

    def stop(self):
        """Sets the flag to stop the scanning process."""
        print("Requesting FileLoaderThread stop...")
        self._is_running = False

    def run(self):
        """The main execution method of the thread."""
        files_found = []
        error_msg = None
        folder = Path(self.folder_path)

        try:
            # Basic validation of the starting path
            if not folder.is_dir():
                error_msg = f"Selected path is not a directory: {self.folder_path}"
                self.error_occurred.emit(error_msg)
                self.files_loaded.emit([], self.folder_path) # Emit empty list
                return

            # Use rglob for recursive globbing, yields Path objects directly
            # Wrap in try/except in case of permission errors during iteration itself
            iterator = None
            try:
                 iterator = folder.rglob("*.py")
            except PermissionError as e:
                 error_msg = f"Permission error starting scan in '{self.folder_path}': {e}"
                 print(error_msg)
                 self.error_occurred.emit(error_msg)
                 self.files_loaded.emit([], self.folder_path) # Emit empty list
                 return
            except Exception as e:
                 error_msg = f"Error starting scan in '{self.folder_path}': {e}"
                 print(error_msg)
                 traceback.print_exc()
                 self.error_occurred.emit(error_msg)
                 self.files_loaded.emit([], self.folder_path) # Emit empty list
                 return


            for item in iterator:
                if not self._is_running:
                    print("File scan cancelled during iteration.")
                    # Don't emit error, just stop and emit potentially partial list later
                    break # Exit the loop if cancelled

                # Process the found item
                try:
                    # Ensure it's actually a file (rglob might yield dirs if pattern allows)
                    # and check if we can read it to avoid issues later.
                    if item.is_file() and os.access(str(item), os.R_OK):
                        files_found.append(item)
                    elif item.is_file(): # It's a file but not readable
                        print(f"Warning: Skipping non-readable file: {item}")
                        # Optionally emit a warning signal here
                    # Ignore directories yielded by rglob if pattern was less specific
                except OSError as os_err:
                    # Handle specific OS errors during file access check
                    print(f"Warning: Cannot access file {item} during scan: {os_err}")
                except Exception as item_err:
                    # Catch unexpected errors processing a single item
                    print(f"Warning: Error processing item {item} during scan: {item_err}")

            # --- End of Loop ---

            if not self._is_running:
                # If cancelled, emit whatever was found up to that point, or empty list
                print(f"File scan finished after cancellation request. Found {len(files_found)} files.")
                self.files_loaded.emit(files_found, self.folder_path) # Emit potentially partial list
            else:
                 # Scan completed normally
                 print(f"File scan completed normally. Found {len(files_found)} files.")
                 self.files_loaded.emit(files_found, self.folder_path) # Emit full list

        except Exception as e:
            # Catch-all for unexpected errors during the run method
            error_msg = f"Unexpected error during file scan: {e}"
            print(error_msg)
            traceback.print_exc()
            self.error_occurred.emit(error_msg)
            self.files_loaded.emit([], self.folder_path) # Emit empty list on error

# --- File Processing (Replace/Format) Thread ---
class ReplacementThread(QThread):
    """
    Processes a list of files: applies find/replace (optional) and Black formatting.

    Signals:
        progress (int, str): Emitted during processing. Provides percentage complete
                             and a log message for the current file.
        finished (): Emitted when all files have been processed or the thread is stopped.
        error_occurred (str): Emitted for file-specific errors that don't stop the
                              entire process (e.g., write error, decode error).
    """
    progress = pyqtSignal(int, str) # Percent, Log Message
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str) # File-specific error message

    def __init__(self, files: list[Path], pattern: str, replacement: str, use_regex: bool, parent=None):
        """
        Initializes the replacement/formatting thread.

        Args:
            files: A list of Path objects representing the files to process.
            pattern: The search pattern (string or regex). Empty for format-only.
            replacement: The replacement string.
            use_regex: Boolean indicating if the pattern is a regular expression.
            parent: Optional parent object.
        """
        super().__init__(parent)
        self.files_to_process = files
        self.pattern = pattern
        self.replacement = replacement
        self.use_regex = use_regex
        self._is_running = True # Flag for cancellation

    def stop(self):
        """Sets the flag to stop the processing loop."""
        print("Requesting ReplacementThread stop...")
        self._is_running = False

    def run(self):
        """The main execution method of the thread."""
        total_files = len(self.files_to_process)
        if total_files == 0:
            self.finished.emit() # Nothing to do
            return

        processed_count = 0
        for idx, file_path in enumerate(self.files_to_process):
            if not self._is_running:
                # Emit final progress before breaking
                percent = int(((processed_count) / total_files) * 100) if total_files > 0 else 0
                self.progress.emit(percent, "[Cancelled] Operation stopped before processing remaining files.")
                print("Replacement thread cancelled.")
                break # Exit the loop if cancelled

            # Initialize per-file status
            log_msg = ""
            file_name = file_path.name # For logging
            original_content = None
            read_error = None
            replacement_error = None
            format_error = None # Keep variable name, now represents Black error
            write_error = None
            backup_redo_error = None
            content_changed = False
            final_content_to_write = None


            # --- 1. Read Original File ---
            try:
                original_content, read_error = self._read_file(file_path)
                if read_error:
                    log_msg = f"[Read Error] {file_name}: {read_error}"
                    self.error_occurred.emit(log_msg)
                    # Skip further processing for this file
                    processed_count += 1
                    percent = int(((processed_count) / total_files) * 100)
                    self.progress.emit(percent, log_msg)
                    continue # Move to the next file
            except Exception as e: # Catch unexpected errors during read phase
                 log_msg = f"[Unexpected Read Error] {file_name}: {e}"
                 self.error_occurred.emit(log_msg)
                 processed_count += 1
                 percent = int(((processed_count) / total_files) * 100)
                 self.progress.emit(percent, log_msg)
                 continue # Move to the next file


            modified_content = original_content # Start with original

            # --- 2. Apply Find/Replace (if pattern provided) ---
            if self.pattern:
                try:
                    modified_content, replacement_error = self._apply_replacement(
                        original_content, self.pattern, self.replacement, self.use_regex
                    )
                    if replacement_error:
                        log_msg = f"[Replace Error] {file_name}: {replacement_error}"
                        self.error_occurred.emit(log_msg)
                        # Don't format if replacement failed, proceed with original content
                        modified_content = original_content
                        # Fall through to formatting the original content
                except Exception as e: # Catch unexpected errors during replace phase
                     replacement_error = f"Unexpected error during replace: {e}"
                     log_msg = f"[Unexpected Replace Error] {file_name}: {replacement_error}"
                     self.error_occurred.emit(log_msg)
                     modified_content = original_content # Revert to original


            # --- 3. Preprocess and Format Code (using Black) ---
            # Format the content *after* potential find/replace
            try:
                 # --- CHANGED: Use the new utility function ---
                 # It handles cleaning, normalization, and Black formatting
                 processed_content, format_error_msg = preprocess_and_format_with_black(modified_content)
                 # --- END CHANGE ---

                 if format_error_msg:
                     # Append format error to log, but keep the preprocessed content
                     format_error = f"Preprocessing/Black formatting failed: {format_error_msg}" # Updated error description
                     log_msg += f"\n[Format Warning] {file_name}: {format_error}" if log_msg else f"[Format Warning] {file_name}: {format_error}"
                     self.error_occurred.emit(f"[Format Warning] {file_name}: {format_error}")
                     # Use the content as it was after preprocessing but *before* Black failure
                     final_content_to_write = processed_content # The function returns the pre-Black state on failure
                 else:
                     # Formatting succeeded
                     final_content_to_write = processed_content
            except Exception as e: # Catch unexpected errors during format phase
                 format_error = f"Unexpected error during formatting: {e}"
                 log_msg += f"\n[Unexpected Format Error] {file_name}: {format_error}" if log_msg else f"[Unexpected Format Error] {file_name}: {format_error}"
                 self.error_occurred.emit(f"[Unexpected Format Error] {file_name}: {format_error}")
                 # Revert to content before attempting format
                 final_content_to_write = modified_content


            # --- 4. Check for Changes and Write File ---
            if original_content != final_content_to_write:
                content_changed = True
                diff_str = "" # Initialize diff string

                # --- 4a. Create Backup and Redo Files ---
                try:
                    # Use the utility function for backup/redo
                    backup_ok, backup_redo_err_msg = backup_and_redo(file_path)
                    if not backup_ok:
                        backup_redo_error = backup_redo_err_msg or "Failed to create backup/redo files."
                        log_msg += f"\n[Backup/Redo Error] {file_name}: {backup_redo_error}" if log_msg else f"[Backup/Redo Error] {file_name}: {backup_redo_error}"
                        self.error_occurred.emit(f"[Backup/Redo Error] {file_name}: {backup_redo_error}")
                        # Decide whether to proceed with writing if backup fails. Let's stop here.
                        processed_count += 1
                        percent = int(((processed_count) / total_files) * 100)
                        self.progress.emit(percent, log_msg)
                        continue # Skip writing this file

                except Exception as e: # Catch unexpected errors during backup/redo phase
                     backup_redo_error = f"Unexpected error during backup/redo: {e}"
                     log_msg += f"\n[Unexpected Backup/Redo Error] {file_name}: {backup_redo_error}" if log_msg else f"[Unexpected Backup/Redo Error] {file_name}: {backup_redo_error}"
                     self.error_occurred.emit(f"[Unexpected Backup/Redo Error] {file_name}: {backup_redo_error}")
                     processed_count += 1
                     percent = int(((processed_count) / total_files) * 100)
                     self.progress.emit(percent, log_msg)
                     continue # Skip writing this file


                # --- 4b. Generate Diff (Optional but helpful for logs) ---
                try:
                    diff_str = "\n".join(
                        difflib.unified_diff(
                            original_content.splitlines(),
                            final_content_to_write.splitlines(),
                            fromfile=f"a/{file_name}",
                            tofile=f"b/{file_name}",
                            lineterm="", # Don't add trailing newline to diff lines
                            n=1 # Context lines (optional, 1 is usually enough for logs)
                        )
                    )
                except Exception as diff_e:
                    print(f"Warning: Could not generate diff for {file_name}: {diff_e}")
                    diff_str = "[Diff generation failed]"


                # --- 4c. Write Modified/Formatted Content ---
                try:
                    # Use the utility function for writing
                    write_ok, write_err_msg = safe_write_file(file_path, final_content_to_write)
                    if not write_ok:
                        write_error = write_err_msg or "Failed to write file."
                        log_msg += f"\n[Write Error] {file_name}: {write_error}" if log_msg else f"[Write Error] {file_name}: {write_error}"
                        self.error_occurred.emit(f"[Write Error] {file_name}: {write_error}")
                        # File wasn't written, but backup/redo might exist. State could be inconsistent.
                    else:
                        # Write successful
                        status = "[Updated]"
                        if format_error: status = "[Updated with Format Warning]"
                        if replacement_error: status = "[Updated with Replace Error]" # Overrides format warning
                        log_msg = f"{status} {file_name}\nDiff:\n{diff_str}"

                except Exception as e: # Catch unexpected errors during write phase
                    write_error = f"Unexpected error during write: {e}"
                    log_msg += f"\n[Unexpected Write Error] {file_name}: {write_error}" if log_msg else f"[Unexpected Write Error] {file_name}: {write_error}"
                    self.error_occurred.emit(f"[Unexpected Write Error] {file_name}: {write_error}")

            else:
                # No change detected between original and final content
                content_changed = False
                if not log_msg: # Only report 'no change' if no other errors occurred
                    log_msg = f"[No change] {file_name}"
                else: # Append 'no change' info to existing error/warning messages
                     log_msg += f"\n[Info] No effective change for {file_name} despite previous warnings."

            # --- 5. Emit Progress ---
            processed_count += 1
            percent = int(((processed_count) / total_files) * 100)
            # Ensure a message is emitted even if log_msg is somehow empty
            final_log = log_msg or f"[Processed] {file_name} (Status unknown)"
            self.progress.emit(percent, final_log)


        # --- End of Loop ---
        print("Replacement thread finished processing loop.")
        self.finished.emit() # Signal completion

    def _read_file(self, file_path: Path) -> tuple[str | None, str | None]:
        """Reads file content, handles common errors."""
        content = None
        error = None
        try:
            # Check existence and read permission explicitly first
            if not file_path.is_file():
                raise FileNotFoundError(f"File not found: {file_path}")
            if not os.access(str(file_path), os.R_OK):
                raise PermissionError("Permission denied reading file")

            # Try reading with UTF-8 first
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Log warning and try fallback (system default)
                print(f"Warning: Non UTF-8 file {file_path.name}. Trying fallback encoding.")
                try:
                    content = file_path.read_text(encoding=None) # System default
                except Exception as fallback_e:
                    raise UnicodeDecodeError("utf-8", b'', 0, 0, f"Not UTF-8 and fallback failed: {fallback_e}") from fallback_e

        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            error = str(e)
        except Exception as e:
            error = f"Unexpected read error: {e}"
            traceback.print_exc() # Log unexpected errors fully
        return content, error

    def _apply_replacement(self, content: str, pattern: str, replacement: str, use_regex: bool) -> tuple[str, str | None]:
        """Applies find/replace logic, handles regex errors."""
        modified_content = content
        error = None
        try:
            if use_regex:
                # Compile regex for potential efficiency if used many times,
                # but mainly to catch re.error here.
                compiled_pattern = re.compile(pattern)
                modified_content = compiled_pattern.sub(replacement, content)
            else:
                # Simple string replacement
                modified_content = content.replace(pattern, replacement)
        except re.error as regex_error:
            error = f"Invalid regex pattern: {regex_error}"
        except Exception as e:
            error = f"Unexpected error during replacement: {e}"
            traceback.print_exc()
        return modified_content, error