
import sys
import os
import platform
import shutil
import difflib
import traceback
import ast # For snippet parsing
from pathlib import Path

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLineEdit, QFileDialog, QLabel, QMessageBox, QCheckBox, QTreeView,
    QProgressBar, QSplitter, QDialog, QPlainTextEdit, QStyle, QMenu,
    QSizePolicy, QHeaderView
)
from PyQt6.QtGui import (
    QFont, QIcon, QShortcut, QKeySequence, QFontDatabase, QAction, QDesktopServices,
    QUndoStack, QUndoCommand, QFileSystemModel, # Keep imports even if not fully implemented yet
)
from PyQt6.QtCore import (
    Qt, QTimer, QDir, QSortFilterProxyModel, QRegularExpression, QModelIndex
)

# --- Project Module Imports ---
from .constants import * # Import all constants
from .utils import (
    resource_path, open_containing_folder, copy_to_clipboard,
    safe_read_file, safe_write_file, backup_and_redo
)
from .ruff_utils import format_code_with_ruff
from .ast_utils import find_ast_node
from .highlighters import PythonHighlighter, DiffHighlighter
from .widgets import CodeEditor, DiffDialog # LineNumberArea is used internally by CodeEditor
from .threads import FileLoaderThread, ReplacementThread


# --- Main Application Window ---
class SmartReplaceApp(QWidget):
    """
    The main application window for the Code Helper tool. Provides UI for
    selecting folders, finding/replacing text, formatting code with Ruff,
    previewing changes, and applying them to Python files.
    """
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.files = [] # Stores list of Path objects from scan
        self.current_folder_path: str | None = None
        self.highlighter_preview: PythonHighlighter | None = None
        self.highlighter_new_code: PythonHighlighter | None = None
        self.code_font = self._load_custom_font() # Load font early

        # File System Model setup
        self.fs_model = QFileSystemModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.fs_model)
        self.proxy_model.setFilterKeyColumn(0) # Filter by filename
        self.proxy_model.setRecursiveFilteringEnabled(True) # Allow filtering subdirs
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        # State variables
        self._pending_patch_info: dict | None = None # Stores info for snippet apply
        self.scan_thread: FileLoaderThread | None = None
        self.replace_thread: ReplacementThread | None = None

        # ### Undo/Redo ### Initialize QUndoStack (even if file-based is primary)
        # Using QUndoStack would require significant changes to how operations
        # are performed (wrapping them in QUndoCommand subclasses).
        # Sticking to file-based .bak/.redo for now as per original code.
        # self.undo_stack = QUndoStack(self)

        # Initialize UI elements and hotkeys
        self._init_ui()
        self._init_hotkeys()
        # self._setup_undo_redo_actions() # Call if using QUndoStack

        # Apply base styles and window properties
        self.setStyleSheet(STYLE_SHEET) # Apply stylesheet from constants
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setGeometry(100, 100, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Load and set application icon
        self._set_app_icon()

    def _load_custom_font(self) -> QFont:
        """Loads the custom font (JetBrains Mono) or falls back."""
        font_path_str = "" # Initialize
        try:
            # Use resource_path to find the font file
            font_path_str = resource_path(FONT_FILENAME)
            font_id = QFontDatabase.addApplicationFont(font_path_str)

            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    print(f"Successfully loaded font: {font_families[0]}")
                    # Return the loaded font with the default size
                    return QFont(font_families[0], DEFAULT_FONT_SIZE)
                else:
                    print(f"Warning: Could not get family name for font: {font_path_str}")
            else:
                 # Check if the file actually exists before printing the warning
                if not Path(font_path_str).exists():
                    print(f"Error: Font file not found at path: {font_path_str}")
                else:
                     print(f"Warning: Failed to load font (QFontDatabase returned -1): {font_path_str}")

        except Exception as e:
            print(f"Error loading custom font '{font_path_str}': {e}")

        # Fallback font if custom loading fails
        print(f"Falling back to font: {FALLBACK_FONT_FAMILY}")
        return QFont(FALLBACK_FONT_FAMILY, DEFAULT_FONT_SIZE - 1) # Use slightly smaller fallback

    def _set_app_icon(self):
        """Loads and sets the application window icon."""
        icon_path_str = "" # Initialize
        try:
            # Use resource_path to find the icon file
            icon_path_str = resource_path(ICON_FILENAME)
            icon_path = Path(icon_path_str)
            if icon_path.exists() and icon_path.is_file():
                self.setWindowIcon(QIcon(icon_path_str))
                print(f"Loaded application icon: {icon_path_str}")
            else:
                print(f"Warning: Application icon not found or invalid: {icon_path_str}")
        except Exception as e:
            print(f"Error loading application icon '{icon_path_str}': {e}")


    def _init_ui(self):
        """Creates and arranges all UI widgets."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10) # Standard margins
        main_layout.setSpacing(8) # Consistent spacing

        # --- Top Controls (Folder Selection) ---
        top_layout = QHBoxLayout()
        self.select_btn = QPushButton("Select Folder")
        self.select_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.select_btn.setToolTip("Select the root project folder (Ctrl+O)")
        self.select_btn.clicked.connect(self.select_folder)
        top_layout.addWidget(self.select_btn)

        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("color: #aaaaaa; padding-left: 10px;") # Dimmer color
        self.folder_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_layout.addWidget(self.folder_label, 1) # Allow label to stretch
        main_layout.addLayout(top_layout)

        # --- Find/Replace Controls & Run Button ---
        find_replace_layout = QHBoxLayout()
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find pattern (optional, text or regex)")
        self.find_input.setToolTip("Text or regular expression to find. Leave blank to only format files.")
        self.find_input.setClearButtonEnabled(True)
        find_replace_layout.addWidget(self.find_input, 2) # Give more space

        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with")
        self.replace_input.setToolTip("Replacement text. Used only if 'Find pattern' is provided.")
        self.replace_input.setClearButtonEnabled(True)
        find_replace_layout.addWidget(self.replace_input, 2) # Give more space

        self.regex_checkbox = QCheckBox("Regex")
        self.regex_checkbox.setToolTip("Treat 'Find pattern' as a regular expression.")
        find_replace_layout.addWidget(self.regex_checkbox)

        # Add some spacing before buttons
        find_replace_layout.addSpacing(15)

        self.scan_btn = QPushButton("Scan & Run")
        self.scan_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.scan_btn.setToolTip("Scan selected folder, apply find/replace (if any), and format with Ruff.")
        self.scan_btn.clicked.connect(self.scan_and_run)
        self.scan_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        find_replace_layout.addWidget(self.scan_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.cancel_btn.setToolTip("Cancel the current Scan or Run operation.")
        self.cancel_btn.clicked.connect(self.cancel_operation)
        self.cancel_btn.setEnabled(False) # Initially disabled
        self.cancel_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        find_replace_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(find_replace_layout)

        # --- Main Splitter (File Tree | Editor/Preview Panes) ---
        splitter_main = QSplitter(Qt.Orientation.Horizontal)
        splitter_main.setHandleWidth(6) # Slightly thicker handle

        # --- Left Panel: File Tree + Filter ---
        left_panel_widget = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_widget)
        left_panel_layout.setContentsMargins(0, 0, 5, 0) # Add right margin
        left_panel_layout.setSpacing(5)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter files (e.g., utils, *.py)")
        self.filter_input.setToolTip("Filter files by name shown in the tree (supports wildcards *, ?)")
        self.filter_input.textChanged.connect(self.filter_file_tree)
        self.filter_input.setClearButtonEnabled(True)
        left_panel_layout.addWidget(self.filter_input)

        # Configure File System Model
        self.fs_model.setNameFilters(["*.py"]) # Only show Python files initially
        self.fs_model.setNameFilterDisables(False) # Apply filter to files, not hide dirs
        # Consider read-only for safety, but renaming/deleting might be future features
        self.fs_model.setReadOnly(False) # Allows interaction, but handle actions carefully

        # Configure Tree View
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.proxy_model) # Use the proxy model for filtering/sorting
        self.file_tree.setRootIsDecorated(True) # Show expand/collapse icons
        self.file_tree.setToolTip("Click a Python file to view its content. Right-click for options.")
        self.file_tree.clicked.connect(self.on_tree_clicked)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.file_tree.setHeaderHidden(True) # Hide default header (Name, Size, etc.)
        self.file_tree.setAnimated(True) # Enable expand/collapse animation
        self.file_tree.setSortingEnabled(True) # Allow sorting by column (name)
        self.file_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder) # Default sort by name
        # Improve selection behavior
        self.file_tree.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.file_tree.setUniformRowHeights(True) # Performance hint

        left_panel_layout.addWidget(self.file_tree)
        splitter_main.addWidget(left_panel_widget)

        # --- Right Side Splitter (Preview | New Code Editor) ---
        splitter_right = QSplitter(Qt.Orientation.Vertical)
        splitter_right.setHandleWidth(6)

        # --- Top Right: Code Preview Area ---
        # Wrap CodeEditor in a layout for potential labels/controls later
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(5, 0, 0, 0) # Add left margin
        preview_layout.setSpacing(2)
        preview_label = QLabel("File Preview (Read-Only):")
        preview_layout.addWidget(preview_label)

        self.preview_area = CodeEditor(self.code_font)
        self.preview_area.setReadOnly(True)
        self.preview_area.setToolTip("Content of the selected file from the tree.")
        self.highlighter_preview = PythonHighlighter(self.preview_area.document())
        preview_layout.addWidget(self.preview_area)
        splitter_right.addWidget(preview_widget)


        # --- Bottom Right: New Code Editor Section ---
        new_code_widget = QWidget()
        new_code_layout = QVBoxLayout(new_code_widget)
        new_code_layout.setContentsMargins(5, 5, 0, 0) # Add left margin, top margin
        new_code_layout.setSpacing(5)

        new_code_label = QLabel("Code Editor / Snippet Paster:")
        new_code_layout.addWidget(new_code_label)

        self.new_code_editor = CodeEditor(self.code_font)
        self.new_code_editor.setPlaceholderText("Paste code here to format, diff, or apply...")
        self.new_code_editor.setToolTip("Paste code, then use buttons below.")
        self.highlighter_new_code = PythonHighlighter(self.new_code_editor.document())
        new_code_layout.addWidget(self.new_code_editor)

        # --- Buttons below New Code Editor ---
        new_code_controls = QHBoxLayout()
        new_code_controls.setSpacing(8)

        # Action Buttons (Left Aligned)
        self.format_code_btn = QPushButton("Format Pasted")
        self.format_code_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)) # Placeholder icon
        self.format_code_btn.setToolTip("Format the code currently in this editor using Ruff (Ctrl+Shift+F).")
        self.format_code_btn.clicked.connect(self.format_new_code)
        new_code_controls.addWidget(self.format_code_btn)

        self.preview_diff_btn = QPushButton("Diff (Full)")
        self.preview_diff_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton).fromTheme("view-difference", self.style().standardIcon(QStyle.StandardPixmap.SP_FileLinkIcon))) # Diff icon
        self.preview_diff_btn.setToolTip("Preview changes between selected file and formatted pasted code (Ctrl+Shift+D).")
        self.preview_diff_btn.clicked.connect(self.preview_diff)
        new_code_controls.addWidget(self.preview_diff_btn)

        self.preview_snippet_btn = QPushButton("Diff (Snippet)")
        self.preview_snippet_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView).fromTheme("view-split-side-by-side", self.style().standardIcon(QStyle.StandardPixmap.SP_FileLinkIcon))) # Another diff icon
        self.preview_snippet_btn.setToolTip("Preview replacing matching function/class in selected file with pasted snippet (Ctrl+Alt+D).")
        self.preview_snippet_btn.clicked.connect(self.preview_snippet_change)
        new_code_controls.addWidget(self.preview_snippet_btn)

        self.apply_snippet_btn = QPushButton("Apply Snippet")
        self.apply_snippet_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.apply_snippet_btn.setToolTip("Apply the change from the last successful 'Diff (Snippet)' preview (Ctrl+Alt+Enter).")
        self.apply_snippet_btn.setEnabled(False) # Disabled until preview runs
        self.apply_snippet_btn.clicked.connect(self.apply_snippet_patch)
        new_code_controls.addWidget(self.apply_snippet_btn)

        self.apply_new_code_btn = QPushButton("Apply Full File")
        self.apply_new_code_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.apply_new_code_btn.setToolTip("Overwrite selected file with the (formatted) content of this editor (Ctrl+Enter).")
        self.apply_new_code_btn.clicked.connect(self.apply_new_code)
        new_code_controls.addWidget(self.apply_new_code_btn)

        # Spacer to push next buttons to the right
        new_code_controls.addStretch(1)

        # Undo/Redo/Reset Buttons (Right Aligned)
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self.undo_btn.setToolTip("Undo last change to selected file (restores from .bak, creates .redo) (Ctrl+Z).")
        self.undo_btn.clicked.connect(self.undo_change)
        new_code_controls.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        self.redo_btn.setToolTip("Redo last undo for selected file (restores from .redo, creates .bak) (Ctrl+Y).")
        self.redo_btn.clicked.connect(self.redo_change)
        new_code_controls.addWidget(self.redo_btn)

        self.reset_btn = QPushButton("Reset UI")
        self.reset_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.reset_btn.setToolTip("Clear inputs, editors, logs, selections, and cancel operations.")
        self.reset_btn.clicked.connect(self.reset_ui_state)
        new_code_controls.addWidget(self.reset_btn)


        new_code_layout.addLayout(new_code_controls)
        splitter_right.addWidget(new_code_widget)
        # Set initial sizes for the vertical splitter
        splitter_right.setSizes(DEFAULT_SPLITTER_RIGHT_SIZES)

        # Add the right splitter to the main horizontal splitter
        splitter_main.addWidget(splitter_right)
        # Set initial sizes for the main horizontal splitter
        splitter_main.setSizes(DEFAULT_SPLITTER_MAIN_SIZES)

        # Add the main splitter to the main layout (stretch factor 1)
        main_layout.addWidget(splitter_main, 1)

        # --- Bottom Section (Progress Bar and Log Area) ---
        bottom_layout = QVBoxLayout()
        bottom_layout.setSpacing(5)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True) # Show percentage text
        self.progress_bar.setRange(0, 100) # Standard percentage range
        self.progress_bar.setValue(0)
        self.progress_bar.setToolTip("Progress of the Scan & Run operation.")
        bottom_layout.addWidget(self.progress_bar)

        self.log_area = QTextEdit() # Use QTextEdit for rich text (HTML formatting)
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(LOG_AREA_HEIGHT) # Set fixed height from constants
        self.log_area.setToolTip("Operation logs, errors, and diff summaries.")
        self.log_area.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap) # No wrap for logs often better
        # Optionally use code font for logs if preferred
        # self.log_area.setFont(self.code_font)
        bottom_layout.addWidget(self.log_area)

        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)


    def _init_hotkeys(self):
        """Initializes keyboard shortcuts."""
        # Action Hotkeys
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, activated=self.format_new_code)
        QShortcut(QKeySequence("Ctrl+Shift+D"), self, activated=self.preview_diff)
        QShortcut(QKeySequence("Ctrl+Alt+D"), self, activated=self.preview_snippet_change)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.apply_new_code) # Ctrl+Enter
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self.apply_new_code) # Explicitly add both
        QShortcut(QKeySequence("Ctrl+Alt+Return"), self, activated=self.apply_snippet_patch) # Ctrl+Alt+Enter
        QShortcut(QKeySequence("Ctrl+Alt+Enter"), self, activated=self.apply_snippet_patch)

        # Standard Editing/Navigation Hotkeys
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo_change) # Ctrl+Z
        QShortcut(QKeySequence.StandardKey.Redo, self, activated=self.redo_change) # Ctrl+Shift+Z (Standard)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.redo_change) # Common Ctrl+Y alternative for Redo
        QShortcut(QKeySequence.StandardKey.Open, self, activated=self.select_folder) # Ctrl+O
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.handle_escape) # Esc key

        # Add Cut/Copy/Paste for the editable text area?
        # Standard keys usually work automatically for focused QLineEdit/CodeEditor.
        # QShortcut(QKeySequence.StandardKey.Cut, self, activated=self._standard_edit_action)
        # QShortcut(QKeySequence.StandardKey.Copy, self, activated=self._standard_edit_action)
        # QShortcut(QKeySequence.StandardKey.Paste, self, activated=self._standard_edit_action)

    # --- UI Action Handlers ---

    def handle_escape(self):
        """Handles the Escape key press for clearing inputs or selections."""
        focused_widget = self.focusWidget()

        # If find/replace/filter inputs have focus, clear them
        if isinstance(focused_widget, QLineEdit):
            focused_widget.clear()
        # If the file tree has focus, clear its selection
        elif focused_widget == self.file_tree:
            self.file_tree.clearSelection()
            # Also clear dependent UI elements when tree selection is cleared
            self._clear_and_disable_on_selection_change()
        # If a code editor has focus, maybe clear its selection? (Optional)
        elif isinstance(focused_widget, CodeEditor):
             cursor = focused_widget.textCursor()
             if cursor.hasSelection():
                 cursor.clearSelection()
                 focused_widget.setTextCursor(cursor)
        else:
            # Default behavior: Maybe clear focus from the current widget?
             if focused_widget and focused_widget != self: # Avoid clearing focus from main window
                 focused_widget.clearFocus()

    def select_folder(self):
        """Opens a dialog to select the root project folder."""
        start_dir = self.current_folder_path if self.current_folder_path else str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Project Folder",
            start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if folder:
            # Reset UI state before loading new folder content
            self.reset_ui_state()

            self.current_folder_path = folder
            folder_path_obj = Path(folder)

            # Update folder label with a truncated path for display
            try:
                # Show parent/name for context
                parent_name = folder_path_obj.parent.name
                # Use os.sep for correct path separator display
                display_name = f"{parent_name}{os.sep}{folder_path_obj.name}"
            except Exception: # Handle root drives (e.g., C:\)
                display_name = folder_path_obj.name

            # Truncate if the display name is excessively long
            if len(display_name) > 80:
                display_name = "..." + display_name[-77:]
            self.folder_label.setText(display_name)
            self.folder_label.setToolTip(folder) # Show full path in tooltip

            # --- Update File System Model and Tree View ---
            # Set the root path on the *source* model
            source_root_index = self.fs_model.setRootPath(folder)
            if not source_root_index.isValid():
                 self.log_message(f"Error: Could not set root path in model: {folder}", COLOR_ERROR)
                 QMessageBox.critical(self, "Model Error", f"Failed to set the file system model root path to:\n{folder}")
                 return

            # Map the source root index to the *proxy* model index
            proxy_root_index = self.proxy_model.mapFromSource(source_root_index)
            if not proxy_root_index.isValid():
                 self.log_message(f"Error: Could not map root path to proxy model: {folder}", COLOR_ERROR)
                 # This might happen if the root itself is filtered out, though unlikely here.
                 # QMessageBox.critical(self, "Proxy Model Error", f"Failed to map the root path to the proxy model.")
                 # Allow setting root anyway, might just appear empty if filtered
                 # return

            # Set the root index for the QTreeView widget
            self.file_tree.setRootIndex(proxy_root_index)

            # Ensure columns other than the name (column 0) are hidden
            # Run this *after* setting the root path
            QTimer.singleShot(0, self._hide_tree_columns) # Delay slightly if needed

            # Optionally auto-expand the root node for immediate visibility
            # QTimer.singleShot(100, lambda: self.file_tree.expand(proxy_root_index))

            self.log_message(f"Selected folder: {folder}", COLOR_INFO)

    def _hide_tree_columns(self):
        """Hides all columns in the file tree except the first (Name)."""
        if self.fs_model:
            for i in range(1, self.fs_model.columnCount()):
                self.file_tree.setColumnHidden(i, True)

    def filter_file_tree(self, text: str):
        """Filters the files shown in the tree view based on user input."""
        # Use wildcard matching for simple filtering
        # Add '*' around the text for contains-style filtering
        filter_pattern = f"*{text}*" if text else ""
        # Use QRegularExpression for more complex patterns if needed later
        # filter_regex = QRegularExpression(text, QRegularExpression.PatternOption.CaseInsensitiveOption)
        # self.proxy_model.setFilterRegularExpression(filter_regex)
        self.proxy_model.setFilterWildcard(filter_pattern)

        # Optional: Adjust root index mapping if filtering might affect the root itself
        # (Usually not needed if root is a directory and filter targets files)
        # root_path = self.fs_model.rootPath()
        # if root_path:
        #     source_root_index = self.fs_model.index(root_path)
        #     proxy_root_index = self.proxy_model.mapFromSource(source_root_index)
        #     self.file_tree.setRootIndex(proxy_root_index)


    def show_tree_context_menu(self, position):
        """Displays a context menu for the clicked item in the file tree."""
        index: QModelIndex = self.file_tree.indexAt(position)
        if not index.isValid():
            return # Clicked on empty area

        # Map the proxy index back to the source model index
        source_index = self.proxy_model.mapToSource(index)
        if not source_index.isValid(): return # Should not happen if proxy index is valid

        # Get file path and type from the source model
        file_path_str = self.fs_model.filePath(source_index)
        file_path = Path(file_path_str)
        is_dir = self.fs_model.isDir(source_index)

        menu = QMenu(self)

        # --- Common Actions (Files & Directories) ---
        # Action: Open Containing Folder
        open_folder_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), "Open Containing Folder", self)
        # Target the directory itself if it's a dir, otherwise the file's parent
        target_folder_path = file_path if is_dir else file_path.parent
        open_folder_action.triggered.connect(lambda: self.trigger_open_containing_folder(target_folder_path))
        menu.addAction(open_folder_action)

        # Action: Copy Full Path
        copy_path_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView), "Copy Full Path", self)
        copy_path_action.triggered.connect(lambda: self.trigger_copy_file_path(file_path_str))
        menu.addAction(copy_path_action)

        menu.addSeparator()

        # --- File-Specific Actions ---
        if not is_dir:
            # Backup and Redo file paths
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            redo_path = file_path.with_suffix(file_path.suffix + ".redo")

            # Action: Diff Against Backup
            diff_bak_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileLinkIcon), "Diff vs Backup (.bak)", self)
            diff_bak_action.setEnabled(backup_path.exists())
            diff_bak_action.triggered.connect(lambda: self.trigger_diff_against_backup(file_path, backup_path))
            menu.addAction(diff_bak_action)

            # Action: Diff Against Redo State
            diff_redo_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileLinkIcon), "Diff vs Redo (.redo)", self)
            diff_redo_action.setEnabled(redo_path.exists())
            diff_redo_action.triggered.connect(lambda: self.trigger_diff_against_redo(file_path, redo_path))
            menu.addAction(diff_redo_action)

            menu.addSeparator()

            # Action: Restore from Backup
            restore_bak_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack).fromTheme("document-revert"), "Restore from Backup (.bak)", self)
            restore_bak_action.setEnabled(backup_path.exists())
            restore_bak_action.triggered.connect(lambda: self.trigger_restore_from_source(file_path, backup_path))
            menu.addAction(restore_bak_action)

            # Action: Restore from Redo State
            restore_redo_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward).fromTheme("document-revert"), "Restore from Redo (.redo)", self)
            restore_redo_action.setEnabled(redo_path.exists())
            restore_redo_action.triggered.connect(lambda: self.trigger_restore_from_source(file_path, redo_path))
            menu.addAction(restore_redo_action)

            # Potentially add Delete/Rename actions here in the future
            # These would require more careful handling (confirmation, model updates)

        # Show the menu at the cursor position
        menu.exec(self.file_tree.viewport().mapToGlobal(position))

    # --- Context Menu Trigger Methods ---
    # These methods wrap the actual logic calls, allowing for easier connection
    # from lambdas in the context menu creation.

    def trigger_open_containing_folder(self, folder_path: Path):
        """Calls the utility function to open the folder."""
        success, error_msg = open_containing_folder(folder_path)
        if success:
            self.log_message(f"Opened folder: {folder_path}", COLOR_INFO)
        else:
            self.log_message(f"Failed to open folder '{folder_path}': {error_msg}", COLOR_ERROR)
            QMessageBox.warning(self, "Error Opening Folder", error_msg or "Could not open folder.")

    def trigger_copy_file_path(self, file_path_str: str):
        """Calls the utility function to copy text to clipboard."""
        success, error_msg = copy_to_clipboard(file_path_str)
        if success:
            self.log_message(f"Copied path: {file_path_str}", COLOR_INFO)
        else:
            self.log_message(f"Failed to copy path '{file_path_str}': {error_msg}", COLOR_ERROR)
            QMessageBox.warning(self, "Error Copying Path", error_msg or "Could not copy path.")

    def trigger_diff_against_backup(self, file_path: Path, backup_path: Path):
        """Shows diff between current file and its backup."""
        self._show_diff_dialog_helper(file_path, backup_path, "Diff: Current vs Backup")

    def trigger_diff_against_redo(self, file_path: Path, redo_path: Path):
        """Shows diff between current file and its redo state."""
        self._show_diff_dialog_helper(file_path, redo_path, "Diff: Current vs Redo State")

    def _show_diff_dialog_helper(self, file1_path: Path, file2_path: Path, title_prefix: str):
        """Helper method to read files and display the DiffDialog."""
        if not file1_path.exists():
             QMessageBox.warning(self, "Diff Error", f"File not found: {file1_path.name}")
             return
        if not file2_path.exists():
             QMessageBox.warning(self, "Diff Error", f"Comparison file not found: {file2_path.name}")
             return

        try:
            # Read both files safely
            content1, err1 = safe_read_file(file1_path)
            content2, err2 = safe_read_file(file2_path)

            if err1: raise ValueError(f"Error reading {file1_path.name}: {err1}")
            if err2: raise ValueError(f"Error reading {file2_path.name}: {err2}")

            lines1 = content1.splitlines() if content1 is not None else []
            lines2 = content2.splitlines() if content2 is not None else []

            # Create and execute the dialog
            dialog = DiffDialog(lines1, lines2,
                                fromdesc=f"a/{file1_path.name}",
                                todesc=f"b/{file2_path.name}",
                                parent=self) # Set parent
            dialog_title = f"{title_prefix} - {file1_path.name}"
            dialog.setWindowTitle(dialog_title[:120]) # Truncate long titles
            dialog.exec() # Show modally

        except Exception as e:
            error_msg = f"Failed to generate diff between {file1_path.name} and {file2_path.name}: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            QMessageBox.critical(self, "Diff Error", error_msg)

    def trigger_restore_from_source(self, target_file: Path, source_file: Path):
        """Handles restoring a file from a source (.bak or .redo) after confirmation."""
        if not source_file.exists():
            QMessageBox.warning(self, "Restore Error", f"Source file not found: {source_file.name}")
            return

        source_type = ".bak (Backup)" if source_file.suffix.endswith('.bak') else ".redo (Undo State)"
        reply = QMessageBox.question(self, "Confirm Restore",
                                     f"This will overwrite:\n'{target_file.name}'\n\nwith the content from:\n'{source_file.name}'\n({source_type})\n\nAre you sure?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Cancel) # Default to Cancel

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # --- Prepare for Restore ---
                # Check read permission for source
                if not os.access(str(source_file), os.R_OK):
                    raise PermissionError(f"Permission denied reading source file: {source_file.name}")

                # Check write permission for target (or its directory if it doesn't exist)
                can_write_target = (target_file.exists() and os.access(str(target_file), os.W_OK)) or \
                                   (not target_file.exists() and os.access(str(target_file.parent), os.W_OK))
                if not can_write_target:
                    perm_issue = f"writing to file {target_file.name}" if target_file.exists() else f"writing to directory {target_file.parent}"
                    raise PermissionError(f"Permission denied {perm_issue}")

                # --- IMPORTANT: Decide on Undo/Redo behavior for Restore ---
                # Option A: Restore creates its OWN .redo state (allowing undo of restore)
                # Option B: Restore simply copies, breaking the simple undo/redo chain for this action.
                # Let's choose Option A for consistency with other file modifications.
                # Create .redo from the *current* target file *before* overwriting it.
                if target_file.exists():
                     backup_ok, backup_err = backup_and_redo(target_file) # This creates .redo from current target
                     if not backup_ok:
                          # If creating redo state fails, maybe warn but allow restore? Or abort?
                          # Let's abort for safety.
                          raise OSError(f"Could not create undo state (.redo) before restoring: {backup_err}")


                # --- Perform Restore ---
                # Use shutil.copy2 to preserve metadata (like modification time)
                shutil.copy2(str(source_file), str(target_file))

                self.log_message(f"Restored '{target_file.name}' from '{source_file.name}'", COLOR_SUCCESS)

                # Refresh preview if the restored file is currently selected
                self._refresh_preview_after_change(target_file)
                # Clear any pending snippet patch if restoring the selected file
                self._clear_and_disable_on_selection_change()

            except (PermissionError, OSError, shutil.Error) as io_error:
                error_msg = f"Restore Error: {io_error}"
                self.log_message(error_msg, COLOR_ERROR)
                QMessageBox.critical(self, "File Operation Error", error_msg)
            except Exception as e:
                error_msg = f"Failed to restore {target_file.name} from {source_file.name}: {e}"
                self.log_message(error_msg, COLOR_ERROR)
                traceback.print_exc()
                QMessageBox.critical(self, "Restore Error", error_msg)


    # --- UI State Management ---

    def reset_ui_state(self):
        """Resets UI elements to their default state and cancels operations."""
        # 1. Attempt to cancel any running background threads
        self.cancel_operation() # Request threads to stop

        # 2. Wait briefly to allow threads to potentially finish cleanly
        #    Using a timer and then performing the reset ensures the UI remains
        #    responsive while waiting. Adjust delay if needed.
        QTimer.singleShot(150, self._perform_reset)

    def _perform_reset(self):
        """Performs the actual UI reset after attempting thread cancellation."""
        # Double-check if threads are *still* running after the delay
        if self.scan_thread and self.scan_thread.isRunning():
            print("Warning: Scan thread did not stop quickly during reset.")
            # Optionally terminate forcefully? (Risky) self.scan_thread.terminate()
        if self.replace_thread and self.replace_thread.isRunning():
            print("Warning: Replace thread did not stop quickly during reset.")
            # self.replace_thread.terminate() # Risky

        # Clear input fields
        self.find_input.clear()
        self.replace_input.clear()
        self.regex_checkbox.setChecked(False)
        self.filter_input.clear() # Clear file tree filter

        # Clear editor areas
        self.preview_area.setReadOnly(False) # Must be writable to clear
        self.preview_area.clear()
        self.preview_area.setReadOnly(True)
        self.new_code_editor.clear()

        # Clear log and progress
        self.log_area.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%") # Reset format if needed

        # Clear file tree selection and internal file list
        self.file_tree.clearSelection()
        self.files = []

        # Reset pending snippet patch state
        self._pending_patch_info = None
        self.apply_snippet_btn.setEnabled(False)

        # Reset button states
        self.scan_btn.setEnabled(True) # Ensure scan button is usable
        self.cancel_btn.setEnabled(False) # Cancel button should be disabled

        # Reset folder label (optional, or leave last selected)
        # self.folder_label.setText("No folder selected")
        # self.folder_label.setToolTip("")
        # self.current_folder_path = None
        # Clear file tree model? (Might be slow if large dir)
        # self.fs_model.setRootPath("")


        # ### Undo/Redo ### Clear undo stack if using QUndoStack
        # self.undo_stack.clear()

        self.log_message("UI Reset.", COLOR_INFO)
        print("UI Reset performed.")


    def log_message(self, message: str, color: str = COLOR_DEFAULT_TEXT, is_html: bool = False):
        """
        Appends a message to the log area QTextEdit.

        Args:
            message: The message string to append.
            color: The hex color code (e.g., "#FF0000") or standard color name.
                   Defaults to the standard text color.
            is_html: If True, the message is assumed to be valid HTML already.
                     If False (default), HTML characters in the message will be escaped.
        """
        # Ensure log area exists
        if not hasattr(self, 'log_area'): return

        log_entry = ""
        if is_html:
            # Assume message is already safe HTML, wrap with color if needed
            # (Be careful with this flag, ensure input is trusted/sanitized)
            # Basic wrapping, might interfere if message already has complex structure.
            log_entry = f'<font color="{color}">{message}</font>'
        else:
            # Escape HTML characters in the plain text message
            escaped_message = message.replace("&", "&amp;") \
                                     .replace("<", "&lt;") \
                                     .replace(">", "&gt;") \
                                     .replace("\n", "<br>") # Convert newlines to <br>
            log_entry = f'<font color="{color}">{escaped_message}</font>'

        # Append the HTML fragment to the log area
        self.log_area.append(log_entry)

        # Auto-scroll to the bottom to show the latest message
        # Use singleShot to ensure scrolling happens after append is processed
        QTimer.singleShot(0, lambda: self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        ))

    # --- Thread Handling ---

    def handle_thread_error(self, error_message: str):
        """Logs errors emitted by background threads."""
        # Log the error message with an error color
        self.log_message(f"ERROR: {error_message}", COLOR_ERROR)

        # Optionally show a popup, but might be annoying for many small errors.
        # Consider logging only, or maybe only popup for critical thread failures.
        # QMessageBox.warning(self, "Operation Error", error_message)

        # Ensure buttons are reset to a safe state if a thread errors out
        # (This might also be handled in finished signals)
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def cancel_operation(self):
        """Requests cancellation of any running background threads."""
        cancelled_scan = False
        cancelled_replace = False

        # Check and stop scan thread
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop() # Set the internal flag
            self.log_message("Attempting to cancel file scan...", COLOR_WARNING)
            cancelled_scan = True

        # Check and stop replacement thread
        if self.replace_thread and self.replace_thread.isRunning():
            self.replace_thread.stop() # Set the internal flag
            self.log_message("Attempting to cancel replacement process...", COLOR_WARNING)
            cancelled_replace = True

        # Update UI based on cancellation attempt
        if cancelled_scan or cancelled_replace:
            # Disable the cancel button immediately upon request
            self.cancel_btn.setEnabled(False)
            # The Scan button will be re-enabled by the respective thread's
            # finished signal handler (scan_finished_or_cancelled or replacement_finished)
            # to ensure it's only enabled when truly idle.
        else:
            self.log_message("No operation currently running to cancel.", COLOR_INFO)


    def scan_and_run(self):
        """Starts the process of scanning files and then running replacements."""
        # 1. Pre-checks
        if not self.current_folder_path:
            QMessageBox.warning(self, "No Folder Selected", "Please select a folder first using 'Select Folder'.")
            return

        if (self.scan_thread and self.scan_thread.isRunning()) or \
           (self.replace_thread and self.replace_thread.isRunning()):
            QMessageBox.warning(self, "Operation in Progress", "A scan or replacement operation is already running.")
            return

        # 2. Get inputs from UI
        pattern = self.find_input.text()
        replacement = self.replace_input.text()
        use_regex = self.regex_checkbox.isChecked()

        # 3. Update UI state for running operation
        self.log_message(f"Starting scan in '{Path(self.current_folder_path).name}'...", COLOR_DEFAULT_TEXT)
        self.progress_bar.setValue(0) # Reset progress
        self.progress_bar.setFormat("Scanning... %p%") # Indicate scanning phase
        self.scan_btn.setEnabled(False) # Disable scan button
        self.cancel_btn.setEnabled(True)  # Enable cancel button

        # 4. Clear previous thread instances (important for re-runs)
        self.scan_thread = None
        self.replace_thread = None # Ensure replacement thread is also cleared

        # 5. Create and start the FileLoaderThread
        try:
            self.scan_thread = FileLoaderThread(self.current_folder_path, parent=self)

            # Connect signals *before* starting the thread
            # Use a lambda for run_replacement to capture current UI values
            self.scan_thread.files_loaded.connect(
                lambda files, folder_path: self.run_replacement(files, pattern, replacement, use_regex)
            )
            self.scan_thread.error_occurred.connect(self.handle_thread_error)
            # Connect finished signal to handle button states if scan finishes/cancels early
            self.scan_thread.finished.connect(self.scan_finished_or_cancelled)

            self.scan_thread.start() # Start the background thread
        except Exception as e:
             error_msg = f"Failed to start file scanning thread: {e}"
             self.log_message(error_msg, COLOR_ERROR)
             traceback.print_exc()
             QMessageBox.critical(self, "Thread Error", error_msg)
             # Reset UI state on failure to start
             self.scan_btn.setEnabled(True)
             self.cancel_btn.setEnabled(False)
             self.progress_bar.setFormat("%p%")


    def scan_finished_or_cancelled(self):
        """
        Slot connected to the `finished` signal of `FileLoaderThread`.
        Ensures UI buttons are reset correctly if the scan finishes
        (or is cancelled) *before* the replacement thread starts.
        """
        print("FileLoaderThread finished signal received.")
        # Only reset buttons if the replacement thread hasn't started running yet.
        # If run_replacement was called, it will manage the button states.
        if not (self.replace_thread and self.replace_thread.isRunning()):
            print("Resetting buttons from scan_finished_or_cancelled.")
            self.scan_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setValue(0) # Reset progress if only scan ran
            self.progress_bar.setFormat("%p%")
        # else: # Debugging
            # print("Replacement thread is running or about to run, skipping button reset here.")


    def run_replacement(self, files: list[Path], pattern: str, replacement: str, use_regex: bool):
        """
        Slot connected to `files_loaded` signal from `FileLoaderThread`.
        Starts the `ReplacementThread` if files were found and scan wasn't cancelled.
        """
        print(f"run_replacement called with {len(files)} files.")
        self.files = files # Store the list of files found

        # Check if the scan thread was cancelled *before* this slot was called
        if self.scan_thread and not self.scan_thread._is_running:
            self.log_message("Scan was cancelled before replacement could start.", COLOR_WARNING)
            # scan_finished_or_cancelled should handle button reset
            return

        if not files:
            # Handle case where no .py files were found (and not cancelled)
            self.log_message("No '.py' files found in the selected folder or subfolders.", COLOR_WARNING)
            self.scan_btn.setEnabled(True) # Re-enable scan button
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("No files found")
            return

        # Proceed to start the replacement thread
        self.log_message(f"Scan complete. Found {len(files)} files. Starting processing...", COLOR_DEFAULT_TEXT)
        self.progress_bar.setValue(0) # Reset progress for replacement phase
        self.progress_bar.setFormat("Processing... %p%")

        try:
            # Ensure no previous replacement thread is lingering (shouldn't happen often)
            if self.replace_thread and self.replace_thread.isRunning():
                self.log_message("Error: Previous replacement thread still running.", COLOR_ERROR)
                self.scan_btn.setEnabled(True) # Reset buttons
                self.cancel_btn.setEnabled(False)
                return

            # Create and start the ReplacementThread
            self.replace_thread = ReplacementThread(
                self.files, pattern, replacement, use_regex, parent=self
            )

            # Connect signals *before* starting
            self.replace_thread.progress.connect(self.update_progress)
            self.replace_thread.error_occurred.connect(self.handle_replacement_error) # Use specific handler if needed
            self.replace_thread.finished.connect(self.replacement_finished)

            # Keep Scan button disabled, Cancel button enabled while replacement runs
            self.replace_thread.start()

        except Exception as e:
            error_msg = f"Failed to start replacement thread: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc()
            QMessageBox.critical(self, "Thread Error", error_msg)
            # Reset UI state on failure to start replacement thread
            self.scan_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setFormat("%p%")


    def update_progress(self, progress_percent: int, log_msg: str):
        """Updates the progress bar and logs messages from ReplacementThread."""
        self.progress_bar.setValue(progress_percent)

        # --- Determine Log Color and Format ---
        # Default color
        color = COLOR_DEFAULT_TEXT
        is_html = False # Flag to indicate if log_msg is already HTML

        # Check first line for primary status keywords
        log_summary = log_msg.splitlines()[0] if '\n' in log_msg else log_msg

        if "[Error]" in log_summary or "[Read Error]" in log_summary or \
           "[Replace Error]" in log_summary or "[Write Error]" in log_summary or \
           "[Backup/Redo Error]" in log_summary or "Permission denied" in log_summary or \
           "Invalid regex" in log_summary or "Cannot decode" in log_summary:
            color = COLOR_ERROR
            # Log entire message in error color (escaping handled by log_message)
            self.log_message(log_msg, color, is_html=False)

        elif "[Updated]" in log_summary:
            color = COLOR_SUCCESS
            # Format with colored summary and dimmer diff - requires HTML
            summary_line = log_summary.replace("<", "&lt;").replace(">", "&gt;") # Escape summary
            diff_html = ""
            if "\nDiff:\n" in log_msg:
                try:
                    diff_part = log_msg.split("\nDiff:\n", 1)[1]
                    # Escape HTML chars in diff lines and join with <br>
                    escaped_diff_lines = [l.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                                          for l in diff_part.splitlines()]
                    # Wrap diff in <pre> for monospace and style for dim color
                    diff_html = (f'<pre style="color:{COLOR_INFO}; margin-top: 2px; margin-bottom: 0px; '
                                 f'white-space: pre-wrap; font-size: 9pt;">'
                                 f'{"<br>".join(escaped_diff_lines)}</pre>')
                except Exception as e:
                    print(f"Error processing diff for logging: {e}")
                    diff_html = f"<br><i>(Error displaying diff)</i>"

            log_html = f'<font color="{color}">{summary_line}</font>{diff_html}'
            self.log_message(log_html, is_html=True) # Mark as already HTML

        elif "[Format Warning]" in log_summary:
             color = COLOR_WARNING
             # Log warning message (escaping handled by log_message)
             self.log_message(log_msg, color, is_html=False)

        elif "[No change]" in log_summary:
            color = COLOR_INFO # Dim gray for no changes
            self.log_message(log_msg, color, is_html=False)

        elif "[Cancelled]" in log_summary or "[Skipped]" in log_summary:
            color = COLOR_WARNING # Orange for cancellations/skips
            self.log_message(log_msg, color, is_html=False)

        else: # Default case for other messages like "[Processed]"
            self.log_message(log_msg, color, is_html=False)


    def handle_replacement_error(self, error_message: str):
        """Logs file-specific errors from the replacement thread."""
        # This handler mainly exists to differentiate from critical thread errors
        # if needed, but currently just logs using the main log_message.
        # We use the color determination logic in update_progress now.
        # self.log_message(f"File Error: {error_message}", COLOR_ERROR)
        pass # Errors are logged via the progress signal's logic


    def replacement_finished(self):
        """Slot connected to the `finished` signal of `ReplacementThread`."""
        print("ReplacementThread finished signal received.")
        # Determine if cancellation was the reason for finishing
        was_cancelled = self.replace_thread and not self.replace_thread._is_running

        # Log completion status
        if was_cancelled:
            self.log_message("--- Processing cancelled by user ---", COLOR_WARNING)
            self.progress_bar.setFormat("Cancelled")
        else:
            self.log_message("--- Processing complete ---", COLOR_DEFAULT_TEXT)
            # Ensure progress bar reaches 100% if not cancelled
            if self.progress_bar.value() < 100:
                self.progress_bar.setValue(100)
            self.progress_bar.setFormat("Finished")


        # Reset button states now that operation is fully complete or cancelled
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        # Refresh the preview area in case the currently selected file was modified
        self._refresh_preview_if_selected()


    # --- File Tree and Preview Interaction ---

    def on_tree_clicked(self, index: QModelIndex):
        """Handles clicks on items in the file tree view."""
        if not index.isValid():
            self._clear_and_disable_on_selection_change()
            return

        source_index = self.proxy_model.mapToSource(index)
        if not source_index.isValid():
             self._clear_and_disable_on_selection_change()
             return # Should not happen normally

        # If a directory is clicked, clear preview and disable buttons
        if self.fs_model.isDir(source_index):
            # self.preview_area.clear() # Keep preview showing last file for comparison
            self._clear_and_disable_on_selection_change()
            return

        # If a file is clicked, load it into the preview area
        file_path_str = self.fs_model.filePath(source_index)
        self._load_file_into_preview(Path(file_path_str))

    def _load_file_into_preview(self, file_path: Path):
        """Loads the content of a file into the read-only preview area."""
        self._clear_and_disable_on_selection_change() # Clear previous state

        # Use safe_read_file utility function
        content, error_msg = safe_read_file(file_path)

        # Must make writable to set text, then read-only again
        self.preview_area.setReadOnly(False)
        if error_msg:
            self.preview_area.setPlainText(f"# Error loading preview:\n# {error_msg}")
            self.log_message(f"Preview Error: {error_msg}", COLOR_ERROR)
        elif content is not None:
            self.preview_area.setPlainText(content)
            self.preview_area.moveCursor(self.preview_area.textCursor().MoveOperation.Start) # Go to start
        else:
            # Should not happen if safe_read_file returns None without error, but handle defensively
            self.preview_area.setPlainText(f"# Error: Could not read file {file_path.name}, reason unknown.")
            self.log_message(f"Preview Error: Unknown issue reading {file_path.name}", COLOR_ERROR)

        self.preview_area.setReadOnly(True) # Make read-only after setting content


    def _clear_and_disable_on_selection_change(self):
        """
        Clears state related to a specific file selection (e.g., pending patch)
        and disables relevant buttons. Called when selection changes or is cleared.
        """
        # Don't clear the preview_area here, allows comparing unselected file
        # with pasted code in the editor.
        self._pending_patch_info = None
        # Check button exists before trying to disable
        if hasattr(self, 'apply_snippet_btn'):
            self.apply_snippet_btn.setEnabled(False)
        # Optionally disable other apply buttons too if selection is lost?
        # if hasattr(self, 'apply_new_code_btn'): self.apply_new_code_btn.setEnabled(False)


    def _get_selected_source_index_and_path(self) -> tuple[QModelIndex | None, Path | None]:
        """Gets the source model index and Path object for the currently selected file."""
        current_proxy_index = self.file_tree.currentIndex()
        if not current_proxy_index.isValid():
            return None, None

        source_index = self.proxy_model.mapToSource(current_proxy_index)
        if not source_index.isValid() or self.fs_model.isDir(source_index):
            return None, None # Invalid index or directory selected

        file_path = Path(self.fs_model.filePath(source_index))
        return source_index, file_path

    def _refresh_preview_after_change(self, file_path: Path):
        """
        Refreshes the content in the preview area if the provided
        file_path matches the currently selected file in the tree.
        """
        try:
            # Get the currently selected file path
            current_source_index, current_file_path = self._get_selected_source_index_and_path()

            # If the changed file is the one selected, reload its content
            if current_file_path == file_path:
                print(f"Refreshing preview for modified file: {file_path.name}")
                self._load_file_into_preview(file_path)
            # else: # Debugging
                 # print(f"Skipping preview refresh: {file_path.name} != {current_file_path}")
        except Exception as e:
            # Avoid crashing the UI if refresh fails
            print(f"Error during preview refresh for {file_path.name}: {e}")
            self.log_message(f"Warning: Error refreshing preview for {file_path.name}: {e}", COLOR_WARNING)

    def _refresh_preview_if_selected(self):
        """Refreshes preview only if a file is currently selected in the tree."""
        source_index, file_path = self._get_selected_source_index_and_path()
        if file_path:
            self._refresh_preview_after_change(file_path)


    # --- Code Editor Actions ---

    def format_new_code(self):
        """Formats the code in the bottom 'new_code_editor' using Ruff."""
        editor = self.new_code_editor
        current_code = editor.toPlainText()

        if not current_code.strip():
            QMessageBox.warning(self, "No Code", "The code editor is empty. Paste some Python code first.")
            return

        try:
            # Use the utility function to format
            formatted_code, format_error = format_code_with_ruff(current_code)

            if format_error:
                # Show error message, don't change editor content
                QMessageBox.warning(self, "Formatting Error",
                                    f"Could not format the pasted code:\n{format_error}")
                self.log_message(f"Pasted code formatting failed: {format_error}", COLOR_ERROR)
            else:
                # Formatting successful, update editor content
                # Save cursor position to avoid jump
                cursor = editor.textCursor()
                original_pos = cursor.position()
                original_anchor = cursor.anchor()
                has_selection = cursor.hasSelection()

                editor.setPlainText(formatted_code) # Update content

                # Restore cursor position/selection
                # Ensure positions are within the new bounds
                new_length = len(formatted_code)
                cursor.setPosition(min(original_anchor, new_length))
                if has_selection:
                    cursor.setPosition(min(original_pos, new_length), cursor.MoveMode.KeepAnchor)
                else:
                    # If no selection, just place cursor at original position (or end)
                    cursor.setPosition(min(original_pos, new_length))
                editor.setTextCursor(cursor)

                self.log_message("Pasted code formatted successfully with Ruff.", COLOR_INFO)

        except Exception as e:
            # Catch unexpected errors during the formatting process
            error_msg = f"An unexpected error occurred during formatting: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc()
            QMessageBox.critical(self, "Formatting Error", error_msg)


    def apply_new_code(self):
        """Overwrites the selected file with the formatted content from the editor."""
        # 1. Get selected file
        source_index, file_path = self._get_selected_source_index_and_path()
        if not file_path:
            QMessageBox.warning(self, "No File Selected", "Please select a file in the tree to apply the editor content to.")
            return

        # 2. Get code from editor
        new_code_raw = self.new_code_editor.toPlainText()
        # Allow applying empty content to clear a file, maybe confirm first?
        if not new_code_raw.strip():
             reply = QMessageBox.question(self, "Apply Empty Content?",
                                         f"The code editor is empty. Apply empty content to overwrite '{file_path.name}'?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel)
             if reply == QMessageBox.StandardButton.Cancel:
                 return

        # 3. Clear pending snippet patch info
        self._clear_and_disable_on_selection_change()

        # 4. Format the pasted code
        final_code_to_write = ""
        log_color = COLOR_SUCCESS
        log_suffix = "." # For log message

        try:
            formatted_code, format_error = format_code_with_ruff(new_code_raw)
            if format_error:
                # Ask user if they want to apply the *unformatted* code
                reply = QMessageBox.warning(self, "Formatting Error",
                                            f"Ruff failed to format the pasted code:\n{format_error}\n\nDo you want to apply the code *without* formatting?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                            QMessageBox.StandardButton.No) # Default to No
                if reply == QMessageBox.StandardButton.No:
                    self.log_message(f"Apply Full File cancelled due to formatting error on {file_path.name}.", COLOR_WARNING)
                    return # Abort apply

                # User chose Yes, apply the raw (unformatted) code
                final_code_to_write = new_code_raw
                log_color = COLOR_WARNING
                log_suffix = " (unformatted due to Ruff error)."
                self.log_message(f"Applying unformatted code to {file_path.name} after formatting error.", COLOR_WARNING)
            else:
                # Formatting successful
                final_code_to_write = formatted_code
                log_suffix = " (formatted)."

        except Exception as e:
            # Catch unexpected errors during formatting attempt
            error_msg = f"Unexpected error during formatting before apply: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc()
            QMessageBox.critical(self, "Formatting Error", error_msg)
            return # Abort apply


        # 5. Create Backup/Redo state
        try:
            backup_ok, backup_err = backup_and_redo(file_path)
            if not backup_ok:
                # Log error and abort write if backup/redo failed
                error_msg = f"Could not create backup/redo for {file_path.name}: {backup_err}"
                self.log_message(error_msg, COLOR_ERROR)
                QMessageBox.critical(self, "Backup/Redo Error", error_msg)
                return
        except Exception as e:
             error_msg = f"Unexpected error during backup/redo before apply: {e}"
             self.log_message(error_msg, COLOR_ERROR)
             traceback.print_exc()
             QMessageBox.critical(self, "Backup/Redo Error", error_msg)
             return # Abort apply


        # 6. Write the file
        try:
            write_ok, write_err = safe_write_file(file_path, final_code_to_write)
            if not write_ok:
                # Log error, maybe attempt to restore backup? (Complex)
                error_msg = f"Failed to write changes to {file_path.name}: {write_err}"
                self.log_message(error_msg, COLOR_ERROR)
                QMessageBox.critical(self, "File Write Error", error_msg)
                # Consider attempting to restore from the .redo file created just before write attempt
                # self.restore_from_source(file_path, file_path.with_suffix(file_path.suffix + ".redo"))
                return

            # Write successful
            self.log_message(f"Applied editor content to {file_path.name}{log_suffix}", log_color)

            # Refresh preview and clear the editor after successful apply
            self._refresh_preview_after_change(file_path)
            self.new_code_editor.clear()

        except Exception as e:
            # Catch unexpected errors during the write phase
            error_msg = f"Unexpected error applying code to {file_path.name}: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc()
            QMessageBox.critical(self, "Apply Error", error_msg)


    # --- Diffing Actions ---

    def preview_diff(self):
        """Shows a diff between the selected file and the formatted editor content."""
        # 1. Get selected file
        source_index, file_path = self._get_selected_source_index_and_path()
        if not file_path:
            QMessageBox.warning(self, "No File Selected", "Select a file in the tree to compare against.")
            return

        # 2. Get and check editor content
        new_code_raw = self.new_code_editor.toPlainText()
        if not new_code_raw.strip():
            QMessageBox.warning(self, "Editor Empty", "Paste code into the editor to compare.")
            return

        # 3. Clear pending snippet patch info (this is a full diff)
        self._clear_and_disable_on_selection_change()

        try:
            # 4. Read original file content safely
            original_content, read_error = safe_read_file(file_path)
            if read_error:
                 QMessageBox.critical(self, "File Read Error", f"Could not read selected file '{file_path.name}':\n{read_error}")
                 return
            original_lines = original_content.splitlines() if original_content is not None else []

            # 5. Format the pasted code
            new_code_formatted, format_error = format_code_with_ruff(new_code_raw)
            if format_error:
                # Warn but allow diffing against unformatted code
                reply = QMessageBox.warning(self, "Formatting Error",
                                            f"Could not format pasted code:\n{format_error}\n\nShow diff against the *unformatted* pasted code?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                            QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.No:
                    return # Abort diff
                # Proceed with raw code
                new_lines = new_code_raw.splitlines()
                to_desc = f"b/{file_path.name} (Pasted - Unformatted)"
                self.log_message(f"Previewing diff against unformatted pasted code due to Ruff error.", COLOR_WARNING)
            else:
                # Use formatted code
                new_lines = new_code_formatted.splitlines()
                to_desc = f"b/{file_path.name} (Pasted - Formatted)"
                self.log_message(f"Previewing diff for {file_path.name} vs formatted pasted code.", COLOR_INFO)


            # 6. Show Diff Dialog
            diff_dialog = DiffDialog(original_lines, new_lines,
                                     fromdesc=f"a/{file_path.name} (Current)",
                                     todesc=to_desc,
                                     parent=self) # Set parent
            dialog_title = f"Diff Preview (Full): {file_path.name}"
            diff_dialog.setWindowTitle(dialog_title[:120]) # Truncate title
            diff_dialog.exec() # Show modally

        except Exception as e:
            error_msg = f"Failed to generate full diff: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc()
            QMessageBox.critical(self, "Diff Error", error_msg)


    def preview_snippet_change(self):
        """
        Previews replacing a function/class in the selected file with the
        (formatted) snippet from the editor, using AST to find the target.
        """
        # 1. Reset previous snippet state
        self._clear_and_disable_on_selection_change()

        # 2. Get selected file
        source_index, file_path = self._get_selected_source_index_and_path()
        if not file_path:
            QMessageBox.warning(self, "No File Selected", "Select a target file in the tree first.")
            return

        # 3. Get and check snippet from editor
        snippet_text_raw = self.new_code_editor.toPlainText().strip()
        if not snippet_text_raw:
            QMessageBox.warning(self, "No Snippet", "Paste the code snippet (function or class) into the editor below.")
            return

        # 4. Check target file exists
        if not file_path.exists():
            QMessageBox.warning(self, "File Not Found", f"Selected target file not found:\n{file_path}")
            return

        try:
            # --- 5. Format Snippet & Identify Target Name via AST ---
            formatted_snippet, format_error = format_code_with_ruff(snippet_text_raw)
            if format_error:
                QMessageBox.warning(self, "Snippet Formatting Error", f"Could not format the pasted snippet (check syntax):\n{format_error}")
                return # Stop if snippet itself is invalid

            # Parse the *formatted* snippet to find the target name
            snippet_node, ast_parse_err = find_ast_node(formatted_snippet, "") # Initial parse
            if ast_parse_err:
                 # This shouldn't happen if Ruff succeeded, but check anyway
                 QMessageBox.warning(self, "Invalid Snippet Syntax", f"Snippet has syntax errors even after formatting:\n{ast_parse_err}")
                 return

            # Now find the *first* function or class definition name in the snippet AST
            target_name = None
            target_type = "block" # Default type
            try:
                snippet_tree = ast.parse(formatted_snippet)
                for node in ast.walk(snippet_tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        target_name = node.name
                        target_type = "function" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "class"
                        break # Found the first top-level definition
            except Exception as e:
                 QMessageBox.critical(self, "Snippet AST Error", f"Error analyzing snippet structure: {e}")
                 return


            if not target_name:
                QMessageBox.warning(self, "Cannot Identify Snippet Target",
                                    "Could not find a function or class definition at the beginning of the pasted snippet using AST analysis.")
                return

            self.log_message(f"Snippet identified as {target_type} '{target_name}'. Looking in target file...", COLOR_INFO)

            # --- 6. Find Existing Node in Target File via AST ---
            original_content, read_error = safe_read_file(file_path)
            if read_error:
                 QMessageBox.critical(self, "File Read Error", f"Could not read target file '{file_path.name}':\n{read_error}")
                 return

            # Use find_ast_node to find the *target_name* in the *original_content*
            target_node, find_node_err = find_ast_node(original_content, target_name)

            if find_node_err:
                # Syntax error in the target file prevented finding the node
                QMessageBox.warning(self, "Target File Syntax Error",
                                    f"Could not accurately find '{target_name}' in '{file_path.name}' due to a syntax error in that file:\n{find_node_err}")
                return
            if not target_node:
                QMessageBox.warning(self, "Target Not Found",
                                    f"Could not find {target_type} '{target_name}' in the target file '{file_path.name}' using AST.\n(Check spelling or ensure the definition exists).")
                return

            # --- 7. Extract Existing Block & Generate Diff ---
            # AST lineno is 1-based, end_lineno points to the last line.
            # Adjust to 0-based indices for slicing.
            start_line_index = target_node.lineno - 1
            # Slicing needs exclusive end index, AST end_lineno is inclusive last line.
            end_line_index = target_node.end_lineno # end_lineno is often the index *after* the last line in practice with ast.parse

             # Basic sanity check on line numbers from AST
            if start_line_index < 0 or end_line_index is None or end_line_index <= start_line_index:
                 QMessageBox.critical(self,"AST Line Number Error", f"AST returned invalid line numbers for '{target_name}': start={start_line_index+1}, end={end_line_index}")
                 return


            original_lines = original_content.splitlines() # Split without keeping ends for slicing
            # Ensure indices are within bounds
            if start_line_index >= len(original_lines) or end_line_index > len(original_lines):
                  QMessageBox.critical(self,"AST Line Number Error", f"AST line numbers ({start_line_index+1}-{end_line_index}) are out of bounds for file '{file_path.name}' (Total lines: {len(original_lines)})")
                  return

            existing_block_lines = original_lines[start_line_index:end_line_index]
            snippet_lines = formatted_snippet.splitlines() # Use formatted snippet

            if not existing_block_lines:
                # This might happen if AST gives strange line numbers for an empty block?
                print(f"Warning: Extracted empty block for '{target_name}' at lines {start_line_index+1}-{end_line_index}")
                # Allow diffing against empty block if needed

            # --- 8. Show Diff Dialog ---
            # Add newlines for difflib comparison consistency if needed (splitlines removes them)
            # Using splitlines() for both should be consistent.

            diff_dialog = DiffDialog(existing_block_lines, snippet_lines,
                                     fromdesc=f"a/{file_path.name} ({target_name} - Current)",
                                     todesc=f"b/{file_path.name} ({target_name} - Snippet)",
                                     parent=self)
            dialog_title = f"Snippet Diff: {target_name} in {file_path.name}"
            diff_dialog.setWindowTitle(dialog_title[:120])

            # Check if there are actual changes before showing dialog / enabling apply
            diff_lines = list(difflib.unified_diff(
                [line + '\n' for line in existing_block_lines], # Add nl for diff context check
                [line + '\n' for line in snippet_lines],
                lineterm="", n=0 # n=0 checks for any difference
            ))

            if not diff_lines:
                QMessageBox.information(self, "No Changes Detected", f"The provided snippet seems identical to the existing {target_type} '{target_name}' in the target file.")
                self.log_message(f"Snippet diff for '{target_name}' showed no changes.", COLOR_INFO)
                # Do not enable apply button
                return # Don't show dialog or enable apply

            # --- 9. Store Patch Info & Enable Apply Button (if diff exists) ---
            self._pending_patch_info = {
                "file_path": file_path,
                "start_line": start_line_index, # 0-based inclusive start
                "end_line": end_line_index,     # 0-based exclusive end
                "snippet_lines": snippet_lines, # Store lines *without* added newlines
                "target_name": target_name,
                "target_type": target_type,
            }
            self.apply_snippet_btn.setEnabled(True)
            self.log_message(f"Snippet diff for '{target_name}' ready. Use 'Apply Snippet' to confirm.", COLOR_INFO)

            # Show the diff dialog modally
            diff_dialog.exec()

        except FileNotFoundError as e:
            # Should be caught earlier, but handle defensively
            self.log_message(f"File not found during snippet preview: {e}", COLOR_ERROR)
            QMessageBox.critical(self, "File Error", f"File not found: {e}")
        except Exception as e:
            error_msg = f"Failed to preview snippet change: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc()
            QMessageBox.critical(self, "Snippet Preview Error", error_msg)
            # Ensure button is disabled on any error
            self._clear_and_disable_on_selection_change()


    def apply_snippet_patch(self):
        """Applies the pending snippet patch stored after a successful preview."""
        if not self._pending_patch_info:
            QMessageBox.warning(self, "No Pending Snippet", "Run 'Diff (Snippet)' first to prepare a change.")
            return

        # Retrieve patch information
        file_path = self._pending_patch_info.get("file_path")
        start_line = self._pending_patch_info.get("start_line") # 0-based start
        end_line = self._pending_patch_info.get("end_line")     # 0-based exclusive end
        snippet_lines = self._pending_patch_info.get("snippet_lines")
        target_name = self._pending_patch_info.get("target_name", "snippet")
        target_type = self._pending_patch_info.get("target_type", "block")

        # Validate retrieved info
        if file_path is None or start_line is None or end_line is None or snippet_lines is None:
            QMessageBox.critical(self, "Internal Error", "Pending snippet patch information is incomplete or corrupted.")
            self._clear_and_disable_on_selection_change()
            return

        try:
            # --- 1. Create Backup/Redo state before patching ---
            backup_ok, backup_err = backup_and_redo(file_path)
            if not backup_ok:
                error_msg = f"Could not create backup/redo for {file_path.name}: {backup_err}"
                self.log_message(error_msg, COLOR_ERROR)
                QMessageBox.critical(self, "Backup/Redo Error", error_msg)
                # Clear pending info but don't disable button yet? User might fix and retry.
                # Let's clear and disable for safety.
                self._clear_and_disable_on_selection_change()
                return

            # --- 2. Read original content (preserving line endings) ---
            try:
                 # Use readlines() to preserve original line endings
                 with open(file_path, "r", encoding="utf-8") as f:
                    original_lines_with_ends = f.readlines()
            except Exception as read_error:
                 QMessageBox.critical(self, "File Read Error", f"Could not read file '{file_path.name}' for patching:\n{read_error}")
                 self._clear_and_disable_on_selection_change()
                 return

            # --- 3. Validate line indices against actual file content ---
            if start_line < 0 or end_line > len(original_lines_with_ends) or start_line > end_line:
                 QMessageBox.critical(self, "Patch Index Error", f"Stored line indices ({start_line+1}-{end_line}) are invalid for the current state of '{file_path.name}' (Total lines: {len(original_lines_with_ends)}). File may have changed since preview.")
                 self._clear_and_disable_on_selection_change()
                 return

            # --- 4. Construct the new content ---
            lines_before = original_lines_with_ends[:start_line]
            # Add the OS-specific newline separator to the snippet lines before joining
            # This ensures consistency regardless of the snippet's original endings
            snippet_lines_with_os_nl = [line + os.linesep for line in snippet_lines]
            lines_after = original_lines_with_ends[end_line:]

            # Join the parts to form the complete new content
            new_content = "".join(lines_before + snippet_lines_with_os_nl + lines_after)

            # --- 5. Write the patched content safely ---
            write_ok, write_err = safe_write_file(file_path, new_content)
            if not write_ok:
                error_msg = f"Failed to write patch to {file_path.name}: {write_err}"
                self.log_message(error_msg, COLOR_ERROR)
                QMessageBox.critical(self, "File Write Error", error_msg)
                # Consider attempting restore from .redo state here?
                # self.restore_from_source(file_path, file_path.with_suffix(file_path.suffix + ".redo"))
                self._clear_and_disable_on_selection_change()
                return

            # --- 6. Log success and refresh UI ---
            self.log_message(f"Applied '{target_name}' {target_type} snippet patch to {file_path.name}.", COLOR_SUCCESS)
            self._refresh_preview_after_change(file_path)

        except (PermissionError, OSError, shutil.Error) as io_error:
            # Catch specific file operation errors during backup or write
            error_msg = f"Could not apply patch to {file_path.name}: {io_error}"
            self.log_message(error_msg, COLOR_ERROR)
            QMessageBox.critical(self, "File Operation Error", error_msg)
        except Exception as e:
            # Catch any other unexpected errors during the process
            error_msg = f"Failed to apply snippet patch to {file_path.name}: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc()
            QMessageBox.critical(self, "Apply Patch Error", error_msg)
        finally:
            # --- 7. Always clear pending patch info and disable button afterwards ---
            self._clear_and_disable_on_selection_change()


    # --- Simple File-Based Undo/Redo ---
    # These methods implement the basic .bak/.redo swap logic.

    def _get_selected_file_paths_for_undo_redo(self) -> tuple[Path | None, Path | None, Path | None]:
        """Gets the Path objects for the selected file, its .bak, and .redo files."""
        source_index, file_path = self._get_selected_source_index_and_path()
        if not file_path:
            return None, None, None # No file selected

        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        redo_path = file_path.with_suffix(file_path.suffix + ".redo")
        return file_path, backup_path, redo_path


    def undo_change(self):
        """Restores the selected file from its .bak file (if exists)."""
        file_path, backup_path, redo_path = self._get_selected_file_paths_for_undo_redo()

        if not file_path:
            QMessageBox.warning(self, "No File Selected", "Please select a file in the tree to undo changes for.")
            return

        if not backup_path.exists():
            QMessageBox.information(self, "Undo Unavailable", f"No backup file (.bak) found for '{file_path.name}'. Cannot undo.")
            return

        try:
            # --- Prepare for Undo ---
            # Check read permission for backup
            if not os.access(str(backup_path), os.R_OK):
                raise PermissionError(f"Cannot read backup file: {backup_path.name}")

            # Check write permission for target (or its directory)
            can_write_target = (file_path.exists() and os.access(str(file_path), os.W_OK)) or \
                               (not file_path.exists() and os.access(str(file_path.parent), os.W_OK))
            if not can_write_target:
                 perm_issue = f"writing to file {file_path.name}" if file_path.exists() else f"writing to directory {file_path.parent}"
                 raise PermissionError(f"Permission denied {perm_issue}")

            # --- Save Current State for Redo ---
            # Create redo state *before* overwriting the current file
            # Use backup_and_redo utility: it saves current state to .redo
            # and ensures .bak exists (which it should if we got here).
            redo_ok, redo_err = backup_and_redo(file_path)
            if not redo_ok:
                # If saving redo state fails, abort the undo for safety.
                 raise OSError(f"Could not save current state for redo: {redo_err}")


            # --- Perform Undo (Restore from Backup) ---
            shutil.copy2(str(backup_path), str(file_path)) # copy2 preserves metadata

            self.log_message(f"Undo: Restored '{file_path.name}' from backup.", COLOR_SUCCESS)

            # --- Post Undo ---
            self._refresh_preview_after_change(file_path)
            # Clear any pending snippet patch after undo
            self._clear_and_disable_on_selection_change()

        except (PermissionError, OSError, shutil.Error) as io_error:
            error_msg = f"Undo Error: {io_error}"
            self.log_message(error_msg, COLOR_ERROR)
            QMessageBox.critical(self, "File Operation Error", error_msg)
        except Exception as e:
            error_msg = f"Failed to perform undo for {file_path.name}: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc()
            QMessageBox.critical(self, "Undo Error", error_msg)


    def redo_change(self):
        """Restores the selected file from its .redo file (if exists)."""
        file_path, backup_path, redo_path = self._get_selected_file_paths_for_undo_redo()

        if not file_path:
            QMessageBox.warning(self, "No File Selected", "Please select a file in the tree to redo changes for.")
            return

        if not redo_path.exists():
            QMessageBox.information(self, "Redo Unavailable", f"No redo state file (.redo) found for '{file_path.name}'. Cannot redo.")
            return

        try:
            # --- Prepare for Redo ---
            # Check read permission for redo file
            if not os.access(str(redo_path), os.R_OK):
                 raise PermissionError(f"Cannot read redo file: {redo_path.name}")

            # Check write permission for target (or its directory)
            can_write_target = (file_path.exists() and os.access(str(file_path), os.W_OK)) or \
                               (not file_path.exists() and os.access(str(file_path.parent), os.W_OK))
            if not can_write_target:
                 perm_issue = f"writing to file {file_path.name}" if file_path.exists() else f"writing to directory {file_path.parent}"
                 raise PermissionError(f"Permission denied {perm_issue}")

            # --- Save Current State for Undo (Back to Backup) ---
            # Before restoring from .redo, save the *current* state back to the
            # .bak file. This allows undoing the redo.
            if file_path.exists():
                # Check permissions for backup operation
                 can_read_target = os.access(str(file_path), os.R_OK)
                 can_write_bak_dir = os.access(str(file_path.parent), os.W_OK)
                 if not can_read_target:
                      # If current file unreadable, can't save for undo. Warn/Abort?
                      print(f"Warning: Cannot read current file {file_path.name} to update backup before redo.")
                      # Proceed with redo, but undoing this redo might not work as expected.
                 elif not can_write_bak_dir:
                      print(f"Warning: Cannot write backup file in {file_path.parent} before redo (permission denied).")
                      # Proceed with redo.
                 else:
                      # Create backup from current state (overwrites existing .bak)
                      shutil.copy2(str(file_path), backup_path)


            # --- Perform Redo (Restore from Redo State) ---
            shutil.copy2(str(redo_path), str(file_path)) # copy2 preserves metadata

            # Keep the .redo file after restoring, allowing toggling between .bak and .redo states.
            # Optionally remove it: # if redo_path.exists(): redo_path.unlink(missing_ok=True)

            self.log_message(f"Redo: Restored '{file_path.name}' from redo state.", COLOR_SUCCESS)

            # --- Post Redo ---
            self._refresh_preview_after_change(file_path)
            # Clear any pending snippet patch after redo
            self._clear_and_disable_on_selection_change()

        except (PermissionError, OSError, shutil.Error) as io_error:
            error_msg = f"Redo Error: {io_error}"
            self.log_message(error_msg, COLOR_ERROR)
            QMessageBox.critical(self, "File Operation Error", error_msg)
        except Exception as e:
            error_msg = f"Failed to perform redo for {file_path.name}: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc()
            QMessageBox.critical(self, "Redo Error", error_msg)


    # --- Graceful Shutdown ---
    def closeEvent(self, event):
        """
        Handles the window close event. Attempts to stop background threads
        gracefully before allowing the application to exit.
        """
        print("Close event triggered.")
        # 1. Request threads to stop
        self.cancel_operation() # Sets flags in threads

        # 2. Check immediately if threads are still running
        scan_running = self.scan_thread and self.scan_thread.isRunning()
        replace_running = self.replace_thread and self.replace_thread.isRunning()

        if scan_running or replace_running:
            # 3. If threads running, ignore initial close and check again after delay
            print("Background operations active. Waiting briefly before re-checking...")
            # Disable close button? Maybe not necessary if check is quick.
            # Use QTimer to avoid blocking the event loop
            QTimer.singleShot(300, lambda: self._check_threads_before_close(event))
            event.ignore() # Prevent closing immediately
        else:
            # 4. No threads running, accept the close event
            print("No background operations running. Closing application.")
            event.accept()


    def _check_threads_before_close(self, event):
        """
        Re-checks thread status after a short delay. Prompts user if threads
        are still running, asking whether to force quit.
        """
        print("Re-checking thread status before close...")
        scan_running = self.scan_thread and self.scan_thread.isRunning()
        replace_running = self.replace_thread and self.replace_thread.isRunning()

        if scan_running or replace_running:
            # Threads still haven't finished after the delay
            thread_names = []
            if scan_running: thread_names.append("File Scan")
            if replace_running: thread_names.append("File Processing")
            running_tasks = " and ".join(thread_names)

            reply = QMessageBox.warning(
                self,
                "Operations Still Running",
                f"The following background task(s) did not stop quickly:\n- {running_tasks}\n\n"
                "Forcing quit might leave files in an inconsistent state.\n\n"
                "Force quit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No # Default to No (don't force quit)
            )

            if reply == QMessageBox.StandardButton.Yes:
                print("User chose to force quit. Accepting close event.")
                # Note: Force quitting might require terminating threads forcefully,
                # which can be risky depending on what the thread is doing (e.g., file I/O).
                # if self.scan_thread: self.scan_thread.terminate() # Use with extreme caution
                # if self.replace_thread: self.replace_thread.terminate() # Use with extreme caution
                event.accept() # Allow close
            else:
                print("User cancelled close. Allowing operations to continue.")
                event.ignore() # Prevent close
                # Re-enable cancel button since user wants to wait
                if hasattr(self, 'cancel_btn'): self.cancel_btn.setEnabled(True)
        else:
            # Threads finished during the delay
            print("Background operations finished. Closing application.")
            event.accept() # Allow close normally