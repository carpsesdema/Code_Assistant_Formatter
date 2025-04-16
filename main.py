
"""
Main entry point for the Code Helper application.
Sets up the QApplication and runs the main window.
Includes necessary setup for PyInstaller.
"""

import sys
import multiprocessing

from PyQt6.QtCore import Qt
# --- PyQt6 Imports ---
# Import QApplication from QtWidgets
from PyQt6.QtWidgets import QApplication

# --- Project Module Imports (Direct Imports for Flat Structure) ---
from app import SmartReplaceApp
from constants import APP_NAME, ORG_NAME, APP_VERSION
# from utils import resource_path # Import if needed directly here

def main():
    """Main function to initialize and run the application."""
    # --- PyInstaller freeze_support ---
    # Necessary for multiprocessing support when bundled, especially on Windows.
    # Must be called right at the beginning of the main execution block.
    multiprocessing.freeze_support()

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
    # os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1" # Basic enable


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
    main()
