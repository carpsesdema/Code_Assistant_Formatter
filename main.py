import sys
import multiprocessing

# --- Add this block at the top ---
import os
import traceback
import time # Import time for unique log filenames if needed

# Try to determine the base directory reliably
try:
    frozen = getattr(sys, 'frozen', False)
    if frozen and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle (_MEIPASS is temp dir)
        bundle_dir = sys._MEIPASS
    else:
        # Running as a normal script
        bundle_dir = os.path.dirname(os.path.abspath(__file__))

    # Define log file path in user's home directory
    log_filename = f"code_helper_debug_{int(time.time())}.log" # Add timestamp
    log_path = os.path.join(os.path.expanduser("~"), log_filename)

    # Write debug info to the log file
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Timestamp: {time.asctime()}\n")
        f.write(f"Running from CWD: {os.getcwd()}\n")
        f.write(f"sys.executable: {sys.executable}\n")
        f.write(f"sys.frozen: {frozen}\n")
        f.write(f"sys._MEIPASS exists: {hasattr(sys, '_MEIPASS')}\n")
        if hasattr(sys, '_MEIPASS'):
            f.write(f"sys._MEIPASS value: {sys._MEIPASS}\n")
        f.write(f"Bundle dir determined: {bundle_dir}\n")
        f.write(f"os.environ['PATH']: {os.environ.get('PATH', 'Not Set')}\n")

except Exception as e:
    # Attempt to log any error during the debug logging itself
    try:
        # Define log_path again in case it failed before creation
        log_path_err = os.path.join(os.path.expanduser("~"), f"code_helper_debug_ERROR_{int(time.time())}.log")
        with open(log_path_err, "w", encoding="utf-8") as f_err:
            f_err.write(f"Timestamp: {time.asctime()}\n")
            f_err.write("Error during initial debug logging:\n")
            f_err.write(traceback.format_exc())
    except Exception:
        pass # Ignore errors during error logging
# --- End of debug block ---


# --- PyQt6 Imports ---
# Import QApplication from QtWidgets
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt # Keep this if you use Qt flags directly here
# --- Project Module Imports (Direct Imports for Flat Structure) ---
from app import App
from constants import APP_NAME, ORG_NAME, APP_VERSION
# from utils import resource_path # Import if needed directly here

def main():
    """Main function to initialize and run the application."""
    # --- Application Setup ---
    # Consider setting application attributes for better OS integration
    # and potential future settings persistence using QSettings.
    QApplication.setApplicationName(APP_NAME)
    if ORG_NAME: # Only set organization name if defined
        QApplication.setOrganizationName(ORG_NAME)
    QApplication.setApplicationVersion(APP_VERSION)

    # High DPI scaling can be important on some systems.
    # PyQt6 generally handles this better, but explicit enabling can be useful.
    # Options:
    # import os
    # os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1" # Basic enable
    # QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling) # Another option

    # Create the QApplication instance
    # sys.argv contains command-line arguments, passed to Qt
    app = QApplication(sys.argv)

    # --- Style Selection ---
    # Using "Fusion" provides a more consistent look across platforms
    # compared to native styles like "Windows", "Macintosh".
    app.setStyle("Fusion")

    # --- Create and Show Main Window ---
    # Instantiate the main application window from app.py
    window = App()
    window.show() # Display the window

    # --- Start Event Loop ---
    # Start the Qt event loop. Execution blocks here until the application exits.
    # sys.exit() ensures the application exit code is properly returned.
    sys.exit(app.exec())

# --- Standard Python Entry Point Check ---
# This ensures the main() function is called only when the script is executed directly.
if __name__ == "__main__":
    # ==============================================================
    # CRITICAL: freeze_support() MUST be the first line here!
    # ==============================================================
    multiprocessing.freeze_support()
    # ==============================================================

    # Now call your main application logic
    main()
