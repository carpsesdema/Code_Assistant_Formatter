import sys
import multiprocessing

# --- PyQt6 Imports ---
# Import QApplication from QtWidgets
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt # Keep this if you use Qt flags directly here
# --- Project Module Imports (Direct Imports for Flat Structure) ---
from app import SmartReplaceApp
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
    window = SmartReplaceApp()
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
