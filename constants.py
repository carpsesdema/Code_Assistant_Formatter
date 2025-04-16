# src/constants.py

"""
Global constants used throughout the Code Helper application.
"""

# Font Settings
DEFAULT_FONT_SIZE = 11  # Default point size for the code font
FALLBACK_FONT_FAMILY = "Courier"  # Font to use if JetBrains Mono fails to load
FONT_FILENAME = "JetBrainsMono-Regular.ttf"  # Custom font file name

# Icon Settings
ICON_FILENAME = "Code_Helper.ico" # Application icon file name

# External Tool Settings
RUFF_TIMEOUT = 10 # Timeout for ruff subprocess in seconds (adjust as needed)

# UI Defaults & Styles
LOG_AREA_HEIGHT = 150 # Default height for the log area in pixels
DEFAULT_WINDOW_WIDTH = 1400
DEFAULT_WINDOW_HEIGHT = 900
DEFAULT_SPLITTER_MAIN_SIZES = [400, 1000] # Initial sizes for main horizontal splitter
DEFAULT_SPLITTER_RIGHT_SIZES = [450, 250] # Initial sizes for right vertical splitter

# Application Info (Optional, for OS integration/settings)
APP_NAME = "Code Helper"
APP_VERSION = "1.2" # Or your current version
ORG_NAME = "YourOrg" # Optional: Replace or remove

# Colors for logging and highlighting (can be expanded)
COLOR_DEFAULT_TEXT = "#D4D4D4"
COLOR_ERROR = "#FF6B6B" # Reddish
COLOR_SUCCESS = "#6BCB77" # Greenish
COLOR_WARNING = "#FFA500" # Orange
COLOR_INFO = "#A0A0A0" # Dim gray
COLOR_HIGHLIGHT_BG = "#3A3A3D" # Background for current line highlight
COLOR_LINE_NUM_BG = "#252526" # Background for line number area
COLOR_LINE_NUM_FG = "#858585" # Foreground for line number text

# Diff Colors (Backgrounds) - Alpha values control transparency
COLOR_DIFF_ADDED_BG = "rgba(0, 80, 0, 90)"
COLOR_DIFF_REMOVED_BG = "rgba(100, 0, 0, 90)"

# CSS Style Sheet (Moved here for clarity)
# Note: Consider loading from a separate .qss file for very large styles
STYLE_SHEET = """
    QWidget {
        background-color: #1E1E1E;
        color: #D4D4D4;
        font-size: 10pt; /* Base font size */
    }
    QPlainTextEdit, QTextEdit, QTextBrowser {
        background-color: #1E1E1E;
        color: #D4D4D4;
        border: 1px solid #333333;
        selection-background-color: #264F78; /* Use a distinct selection color */
        selection-color: #FFFFFF;
    }
    QLineEdit {
        background-color: #3C3C3C;
        color: #D4D4D4;
        border: 1px solid #555555;
        padding: 4px 5px; /* Slightly more vertical padding */
        border-radius: 3px; /* Slightly rounded corners */
    }
    QPushButton {
        background-color: #3A3A3A;
        color: #FFFFFF;
        border: 1px solid #555555;
        padding: 6px 12px;
        min-width: 80px;
        border-radius: 3px;
        outline: none; /* Remove focus rectangle */
    }
    QPushButton:hover {
        background-color: #4A4A4A;
        border: 1px solid #666666;
    }
    QPushButton:pressed {
        background-color: #5A5A5A; /* Slightly darker when pressed */
    }
    QPushButton:disabled {
        background-color: #2D2D2D;
        color: #777777;
        border: 1px solid #444444;
    }
    QLabel {
        color: #A0A0A0; /* Dimmer than default text */
        padding-bottom: 2px; /* Space below labels */
    }
    QTreeView {
        background-color: #252526;
        border: 1px solid #333333;
        alternate-background-color: #2A2A2B; /* Subtle row alternation */
        color: #CCCCCC;
    }
    QTreeView::item {
        padding: 4px; /* More padding for tree items */
    }
    QTreeView::item:selected {
        background-color: #37373D; /* Standard VSCode selection */
        color: #FFFFFF;
    }
    /* Standard Qt expand/collapse icons */
    QTreeView::branch:has-children:!has-siblings:closed,
    QTreeView::branch:closed:has-children:has-siblings {
        border-image: none;
        image: url(:/qt-project.org/styles/commonstyle/images/branch-closed-16.png);
    }
    QTreeView::branch:open:has-children:!has-siblings,
    QTreeView::branch:open:has-children:has-siblings {
        border-image: none;
        image: url(:/qt-project.org/styles/commonstyle/images/branch-open-16.png);
    }
    QHeaderView::section {
        background-color: #3A3A3A;
        padding: 4px;
        border: 1px solid #555555;
        color: #CCCCCC;
        font-weight: bold; /* Make header text bold */
    }
    QSplitter::handle {
        background-color: #333333; /* Slightly darker handle */
        height: 4px; /* Vertical splitter width */
        width: 4px;  /* Horizontal splitter height */
        border: 1px solid #444444; /* Add subtle border */
    }
    QSplitter::handle:hover {
        background-color: #555555;
    }
    QProgressBar {
        border: 1px solid #333333;
        text-align: center;
        color: #D4D4D4;
        background-color: #2D2D2D;
        height: 18px;
        border-radius: 3px; /* Match button radius */
    }
    QProgressBar::chunk {
        background-color: #0E639C; /* VSCode blue */
        border-radius: 3px;
        /* Add subtle gradient or margin for visual separation */
        margin: 1px;
    }
    QCheckBox {
        color: #A0A0A0;
        spacing: 5px;
    }
    QCheckBox::indicator {
        width: 13px;
        height: 13px;
        border-radius: 3px;
    }
    QCheckBox::indicator:unchecked {
        border: 1px solid #555555;
        background-color: #3C3C3C; /* Match line edit bg */
    }
    QCheckBox::indicator:checked {
        border: 1px solid #555555; /* Keep border */
        background-color: #0E639C; /* Match progress bar chunk */
        image: url(:/qt-project.org/styles/commonstyle/images/checkbox-checked-16.png); /* Optional: add checkmark */
    }
    QCheckBox::indicator:disabled {
         border: 1px solid #444444;
         background-color: #2D2D2D;
    }
    /* Dialog Specific Styles */
    QDialog QTextBrowser { /* Diff Dialog */
        background-color: #1e1e1e;
        border: none;
    }
    QDialog QTextEdit { /* Could be used in future dialogs */
        background-color: #1e1e1e;
        border: none;
        color: #D4D4D4;
    }
    QMenu {
        background-color: #2D2D2D;
        border: 1px solid #555555;
        color: #D4D4D4;
        padding: 4px; /* Padding around menu */
    }
    QMenu::item {
        padding: 5px 20px 5px 20px; /* Top/Bottom L/R */
        border-radius: 3px; /* Rounded corners for items */
    }
    QMenu::item:selected {
        background-color: #37373D; /* Selection color */
    }
    QMenu::item:disabled {
        color: #777777;
    }
    QMenu::separator {
        height: 1px;
        background: #555555;
        margin: 5px 5px; /* Margins around separator */
    }
    /* Tooltip Style */
    QToolTip {
        background-color: #252526;
        color: #CCCCCC;
        border: 1px solid #333333;
        padding: 4px;
        border-radius: 3px;
    }
"""