# --- constants.py ---
import platform
from pathlib import Path

# --- Application Info ---
APP_NAME = "Code Helper"
ORG_NAME = "Snowball" # Optional: Used for QSettings, set to "" if none
APP_VERSION = "0.7.0" # Increment version (significant change)

# --- Configuration ---
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 850
LOG_AREA_HEIGHT = 100
DEFAULT_FONT_SIZE = 10
FALLBACK_FONT_FAMILY = "Courier New" if platform.system() == "Windows" else "Monospace"
FONT_FILENAME = "JetBrainsMono-Regular.ttf" # Expected in root or resources
ICON_FILENAME = "Code_Helper.ico" # Expected in root or resources
DEFAULT_SPLITTER_MAIN_SIZES = [250, 750] # Initial sizes for Tree | Editors splitter
DEFAULT_SPLITTER_RIGHT_SIZES = [400, 350] # Initial sizes for Preview | New Code splitter
# RUFF_TIMEOUT = 5.0 # Timeout for Ruff subprocess calls in seconds - REMOVED
BLACK_TIMEOUT = 5.0 # Timeout for Black subprocess calls in seconds
CODE_HELPER_BACKUP_DIR_NAME = ".code_helper_backups" # ADDED: Central backup dir name

# --- Style & Colors (Dark Theme) ---
COLOR_BACKGROUND = "#1e1e1e"
COLOR_FOREGROUND = "#d4d4d4"
COLOR_INPUT_BG = "#2a2a2a"
COLOR_INPUT_BORDER = "#4a4a4a"
COLOR_BUTTON_BG = "#3a3a3a"
COLOR_BUTTON_FG = "#f0f0f0"
COLOR_BUTTON_HOVER_BG = "#4a4a4a"
COLOR_BUTTON_PRESSED_BG = "#5a5a5a"
COLOR_LIST_BG = "#252526"
COLOR_LIST_ALT_BG = "#2a2a2b"
COLOR_LIST_HEADER_BG = "#333333"
COLOR_HIGHLIGHT_BG = "#264f78" # Current line highlight
COLOR_LINE_NUM_BG = "#2a2a2b"
COLOR_LINE_NUM_FG = "#858585"
COLOR_ERROR = "#f44747"
COLOR_SUCCESS = "#4EC9B0" # Teal/Greenish
COLOR_WARNING = "#ffcc00" # Yellow/Orange
COLOR_INFO = "#9CDCFE" # Light blue/Grayish
COLOR_DEFAULT_TEXT = "#d4d4d4" # Default log text color

# Diff Colors
COLOR_DIFF_ADDED_BG = "#1c3d1c" # Dark Green background
COLOR_DIFF_REMOVED_BG = "#4d1c1c" # Dark Red background

# --- Style Sheet ---
# (Style sheet remains the same as before)
STYLE_SHEET = f"""
    QWidget {{
        background-color: {COLOR_BACKGROUND};
        color: {COLOR_FOREGROUND};
        font-size: {DEFAULT_FONT_SIZE}pt; /* Apply base font size */
    }}
    QLabel {{
        /* QLabel inherits QWidget color by default */
        padding: 2px;
    }}
    QLineEdit {{
        background-color: {COLOR_INPUT_BG};
        border: 1px solid {COLOR_INPUT_BORDER};
        padding: 4px;
        border-radius: 3px;
        color: {COLOR_FOREGROUND}; /* Ensure text color */
    }}
    QTextEdit, QPlainTextEdit {{
        background-color: {COLOR_INPUT_BG};
        border: 1px solid {COLOR_INPUT_BORDER};
        padding: 2px;
        color: {COLOR_FOREGROUND}; /* Ensure text color */
        /* Selection colors are often better handled by the platform */
        /* selection-background-color: {COLOR_HIGHLIGHT_BG}; */
        /* selection-color: {COLOR_FOREGROUND}; */
        border-radius: 3px;
    }}
    QPushButton {{
        background-color: {COLOR_BUTTON_BG};
        color: {COLOR_BUTTON_FG};
        border: 1px solid {COLOR_INPUT_BORDER};
        padding: 5px 10px;
        border-radius: 3px;
        min-height: 1.5em; /* Ensure reasonable button height */
    }}
    QPushButton:hover {{
        background-color: {COLOR_BUTTON_HOVER_BG};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_BUTTON_PRESSED_BG};
    }}
    QPushButton:disabled {{
        background-color: #2a2a2a; /* Dimmer background for disabled */
        color: #777777; /* Dimmer text */
        border-color: #444444;
    }}
    QCheckBox {{
        spacing: 5px; /* Space between checkbox and text */
    }}
    QCheckBox::indicator {{
        width: 13px;
        height: 13px;
    }}
    QCheckBox::indicator:unchecked {{
        /* Optional: border: 1px solid {COLOR_INPUT_BORDER}; */
        background-color: {COLOR_INPUT_BG};
    }}
     QCheckBox::indicator:checked {{
        /* Use a theme color or a specific checkmark color */
        background-color: #569CD6; /* Example blue */
    }}
    QProgressBar {{
        border: 1px solid {COLOR_INPUT_BORDER};
        border-radius: 3px;
        text-align: center;
        background-color: {COLOR_INPUT_BG};
        color: {COLOR_FOREGROUND};
    }}
    QProgressBar::chunk {{
        background-color: #569CD6; /* Progress bar fill color */
        width: 10px; /* Adjust chunk width if needed */
        margin: 1px;
    }}
    QTreeView {{
        background-color: {COLOR_LIST_BG};
        alternate-background-color: {COLOR_LIST_ALT_BG};
        border: 1px solid {COLOR_INPUT_BORDER};
        border-radius: 3px;
        show-decoration-selected: 1; /* Highlight full row */
    }}
    QTreeView::item {{
        padding: 3px;
        /* border: none; */ /* Avoid internal borders if they look bad */
    }}
    QTreeView::item:selected {{
        background-color: {COLOR_HIGHLIGHT_BG}; /* Selection background */
        color: {COLOR_FOREGROUND}; /* Ensure selected text is readable */
    }}
    QTreeView::item:hover {{
        background-color: {COLOR_BUTTON_HOVER_BG}; /* Subtle hover */
    }}
    QHeaderView::section {{
        background-color: {COLOR_LIST_HEADER_BG};
        padding: 4px;
        border: 1px solid {COLOR_INPUT_BORDER};
        font-weight: bold;
    }}
    QSplitter::handle {{
        background-color: {COLOR_BUTTON_BG};
        border: 1px solid {COLOR_INPUT_BORDER};
        height: 3px; /* For vertical splitter */
        width: 3px; /* For horizontal splitter */
        margin: 1px; /* Add margin to make handle slightly recessed */
    }}
    QSplitter::handle:horizontal {{
        width: 6px;
        margin-left: 2px;
        margin-right: 2px;
    }}
    QSplitter::handle:vertical {{
        height: 6px;
        margin-top: 2px;
        margin-bottom: 2px;
    }}
    QSplitter::handle:hover {{
        background-color: {COLOR_BUTTON_HOVER_BG};
    }}
    QSplitter::handle:pressed {{
        background-color: {COLOR_BUTTON_PRESSED_BG};
    }}
    QScrollBar:vertical {{
        border: 1px solid {COLOR_INPUT_BORDER};
        background: {COLOR_LIST_BG};
        width: 12px;
        margin: 0px 0px 0px 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {COLOR_BUTTON_BG};
        min-height: 20px;
        border-radius: 6px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLOR_BUTTON_HOVER_BG};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px; /* Hide arrows */
        subcontrol-position: top;
        subcontrol-origin: margin;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
    QScrollBar:horizontal {{
        border: 1px solid {COLOR_INPUT_BORDER};
        background: {COLOR_LIST_BG};
        height: 12px;
        margin: 0px 0px 0px 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: {COLOR_BUTTON_BG};
        min-width: 20px;
        border-radius: 6px;
    }}
     QScrollBar::handle:horizontal:hover {{
        background: {COLOR_BUTTON_HOVER_BG};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px; /* Hide arrows */
        subcontrol-position: left;
        subcontrol-origin: margin;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: none;
    }}
    QToolTip {{
        color: {COLOR_FOREGROUND};
        background-color: {COLOR_BACKGROUND};
        border: 1px solid {COLOR_INPUT_BORDER};
        padding: 4px;
        opacity: 230; /* Slightly transparent */
    }}
    QMenu {{
        background-color: {COLOR_INPUT_BG};
        border: 1px solid {COLOR_INPUT_BORDER};
        padding: 5px;
    }}
    QMenu::item {{
        padding: 5px 15px; /* More padding */
        margin: 2px;
    }}
    QMenu::item:selected {{
        background-color: {COLOR_HIGHLIGHT_BG};
        color: {COLOR_FOREGROUND};
    }}
    QMenu::separator {{
        height: 1px;
        background: {COLOR_INPUT_BORDER};
        margin-left: 10px;
        margin-right: 10px;
    }}
"""