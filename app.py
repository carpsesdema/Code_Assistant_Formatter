# --- app.py ---
import sys
import os
import platform
import shutil
import difflib
import traceback
import ast  # For snippet parsing
from pathlib import Path

# --- PyQt6 Imports ---
# (Keep all PyQt6 imports as they were)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLineEdit, QFileDialog, QLabel, QMessageBox, QCheckBox, QTreeView,
    QProgressBar, QSplitter, QDialog, QPlainTextEdit, QStyle, QMenu,
    QSizePolicy, QHeaderView, QSpacerItem,
)
from PyQt6.QtGui import (
    QFont, QIcon, QShortcut, QKeySequence, QFontDatabase, QAction,
    QDesktopServices, QUndoStack, QUndoCommand, QFileSystemModel,
    QTextDocument, QPalette, QColor,
)
from PyQt6.QtCore import (
    Qt, QTimer, QDir, QSortFilterProxyModel, QRegularExpression, QModelIndex,
)


# --- Project Module Imports (Direct Imports for Flat Structure) ---
from constants import * # Import all constants
from utils import (
    resource_path,
    open_containing_folder,
    copy_to_clipboard,
    safe_read_file,
    safe_write_file,
    backup_and_redo,
    get_central_backup_paths # --- ADDED IMPORT ---
)
from formatter_utils import preprocess_and_format_with_black
from ast_utils import find_ast_node
from highlighters import PythonHighlighter, DiffHighlighter
from widgets import (
    CodeEditor,
    DiffDialog,
)
from threads import FileLoaderThread, ReplacementThread


# --- Main Application Window ---
class App(QWidget):
    """
    The main application window for the Code Helper tool.
    Provides UI for
    selecting folders, finding/replacing text, formatting code with Black,
    previewing changes, and applying them to Python files.
    Backups/Redo files stored centrally in user's home directory.
    """

    # __init__ and other methods (_load_custom_font, _set_app_icon, _init_ui, _init_hotkeys, handle_escape, select_folder, _hide_tree_columns, filter_file_tree)
    # remain IDENTICAL to the previous version (after Black integration)
    # up to the show_tree_context_menu method.

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.files = []  # Stores list of Path objects from scan
        self.current_folder_path: str | None = None
        self.highlighter_preview: PythonHighlighter | None = None
        self.highlighter_new_code: PythonHighlighter | None = None
        self.code_font = self._load_custom_font()  # Load font early

        # File System Model setup
        self.fs_model = QFileSystemModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.fs_model)
        self.proxy_model.setFilterKeyColumn(0)  # Filter by filename
        self.proxy_model.setRecursiveFilteringEnabled(True)  # Allow filtering subdirs
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        # State variables
        self._pending_patch_info: dict | None = None  # Stores info for snippet apply
        self.scan_thread: FileLoaderThread | None = None
        self.replace_thread: ReplacementThread | None = None
        self._find_match_palette_no_match = QPalette() # For find input indication
        self._find_match_palette_match = QPalette() # For find input indication

        # ### Undo/Redo ### Sticking to file-based .bak/.redo
        # self.undo_stack = QUndoStack(self)

        # Initialize UI elements and hotkeys
        self._init_ui()
        self._init_hotkeys()

        # Apply base styles and window properties
        self.setStyleSheet(STYLE_SHEET)
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setGeometry(100, 100, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Load and set application icon
        self._set_app_icon()

        # Initialize find palettes
        self._find_match_palette_no_match.setColor(QPalette.ColorRole.Base, QColor(COLOR_ERROR).lighter(180))
        self._find_match_palette_match.setColor(QPalette.ColorRole.Base, QColor(COLOR_SUCCESS).lighter(180))

    def _load_custom_font(self) -> QFont:
        """Loads the custom font (JetBrains Mono) or falls back."""
        font_path_str = ""  # Initialize
        try:
            font_path_str = resource_path(FONT_FILENAME)
            font_id = QFontDatabase.addApplicationFont(font_path_str)

            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    print(f"Successfully loaded font: {font_families[0]}")
                    return QFont(font_families[0], DEFAULT_FONT_SIZE)
                else:
                    print(f"Warning: Could not get family name for font: {font_path_str}")
            else:
                if not Path(font_path_str).exists():
                    print(f"Error: Font file not found at path: {font_path_str}")
                else:
                    print(f"Warning: Failed to load font (QFontDatabase returned -1): {font_path_str}")

        except Exception as e:
            print(f"Error loading custom font '{font_path_str}': {e}")

        print(f"Falling back to font: {FALLBACK_FONT_FAMILY}")
        return QFont(FALLBACK_FONT_FAMILY, DEFAULT_FONT_SIZE - 1)

    def _set_app_icon(self):
        """Loads and sets the application window icon."""
        icon_path_str = ""
        try:
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
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # --- Top Controls (Folder Selection) ---
        top_layout = QHBoxLayout()
        self.select_btn = QPushButton("Select Folder")
        self.select_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.select_btn.setToolTip("Select the root project folder (Ctrl+O)")
        self.select_btn.clicked.connect(self.select_folder)
        top_layout.addWidget(self.select_btn)
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("color: #aaaaaa; padding-left: 10px;")
        self.folder_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_layout.addWidget(self.folder_label, 1)
        main_layout.addLayout(top_layout)

        # --- Find/Replace Controls & Run Button ---
        find_replace_layout = QHBoxLayout()
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find pattern (optional, text or regex)")
        self.find_input.setToolTip("Text or regular expression to find. Leave blank to only format files.")
        self.find_input.setClearButtonEnabled(True)
        find_replace_layout.addWidget(self.find_input, 2)
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with")
        self.replace_input.setToolTip("Replacement text. Used only if 'Find pattern' is provided.")
        self.replace_input.setClearButtonEnabled(True)
        find_replace_layout.addWidget(self.replace_input, 2)
        self.regex_checkbox = QCheckBox("Regex")
        self.regex_checkbox.setToolTip("Treat 'Find pattern' as a regular expression.")
        find_replace_layout.addWidget(self.regex_checkbox)
        find_replace_layout.addSpacing(15)
        self.scan_btn = QPushButton("Scan & Run")
        self.scan_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.scan_btn.setToolTip("Scan selected folder, apply find/replace (if any), and format with Black.")
        self.scan_btn.clicked.connect(self.scan_and_run)
        self.scan_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        find_replace_layout.addWidget(self.scan_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.cancel_btn.setToolTip("Cancel the current Scan or Run operation.")
        self.cancel_btn.clicked.connect(self.cancel_operation)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        find_replace_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(find_replace_layout)

        # --- Main Splitter (File Tree | Editor/Preview Panes) ---
        splitter_main = QSplitter(Qt.Orientation.Horizontal)
        splitter_main.setHandleWidth(6)

        # --- Left Panel: File Tree + Filter ---
        left_panel_widget = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_widget)
        left_panel_layout.setContentsMargins(0, 0, 5, 0)
        left_panel_layout.setSpacing(5)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter files (e.g., utils, *.py)")
        self.filter_input.setToolTip("Filter files by name shown in the tree (supports wildcards *, ?)")
        self.filter_input.textChanged.connect(self.filter_file_tree)
        self.filter_input.setClearButtonEnabled(True)
        left_panel_layout.addWidget(self.filter_input)
        self.fs_model.setNameFilters(["*.py"])
        self.fs_model.setNameFilterDisables(False)
        self.fs_model.setReadOnly(False)
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.proxy_model)
        self.file_tree.setRootIsDecorated(True)
        self.file_tree.setToolTip("Click a Python file to view its content. Right-click for options.")
        self.file_tree.clicked.connect(self.on_tree_clicked)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setAnimated(True)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.file_tree.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.file_tree.setUniformRowHeights(True)
        left_panel_layout.addWidget(self.file_tree)
        splitter_main.addWidget(left_panel_widget)

        # --- Right Side Splitter (Preview | New Code Editor) ---
        splitter_right = QSplitter(Qt.Orientation.Vertical)
        splitter_right.setHandleWidth(6)

        # --- Top Right: Code Preview Area ---
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(5, 0, 0, 0)
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
        new_code_layout.setContentsMargins(5, 5, 0, 0)
        new_code_layout.setSpacing(5)
        new_code_label = QLabel("Code Editor / Snippet Paster:")
        new_code_layout.addWidget(new_code_label)
        self.new_code_editor = CodeEditor(self.code_font)
        self.new_code_editor.setPlaceholderText("Paste code here to clean, format, diff, or apply...")
        self.new_code_editor.setToolTip("Paste code, then use buttons below. Use Ctrl+F to Find.")
        self.highlighter_new_code = PythonHighlighter(self.new_code_editor.document())
        new_code_layout.addWidget(self.new_code_editor)

        # --- Find Bar ---
        find_bar_layout = QHBoxLayout()
        find_bar_layout.setContentsMargins(0, 2, 0, 2)
        find_bar_layout.setSpacing(5)
        self.find_bar_input = QLineEdit()
        self.find_bar_input.setPlaceholderText("Find in editor (Ctrl+F)")
        self.find_bar_input.setClearButtonEnabled(True)
        self.find_bar_input.setToolTip("Enter text to find in the code editor above.")
        self.find_bar_input.textChanged.connect(self._on_find_bar_text_changed)
        self.find_bar_input.returnPressed.connect(self.find_next_in_editor)
        find_bar_layout.addWidget(self.find_bar_input, 1)
        self.find_bar_case_checkbox = QCheckBox("Case Sensitive")
        self.find_bar_case_checkbox.setToolTip("Match case exactly.")
        find_bar_layout.addWidget(self.find_bar_case_checkbox)
        self.find_bar_prev_btn = QPushButton("Previous")
        self.find_bar_prev_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.find_bar_prev_btn.setToolTip("Find previous occurrence (Shift+F3)")
        self.find_bar_prev_btn.clicked.connect(self.find_previous_in_editor)
        find_bar_layout.addWidget(self.find_bar_prev_btn)
        self.find_bar_next_btn = QPushButton("Next")
        self.find_bar_next_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.find_bar_next_btn.setToolTip("Find next occurrence (F3)")
        self.find_bar_next_btn.clicked.connect(self.find_next_in_editor)
        find_bar_layout.addWidget(self.find_bar_next_btn)
        new_code_layout.addLayout(find_bar_layout)

        # --- Buttons below Find Bar / Editor ---
        new_code_controls = QHBoxLayout()
        new_code_controls.setSpacing(8)
        self.format_code_btn = QPushButton("Clean & Format")
        self.format_code_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.format_code_btn.setToolTip("Clean and format the code currently in this editor using Black (Ctrl+Shift+F).")
        self.format_code_btn.clicked.connect(self.format_new_code)
        new_code_controls.addWidget(self.format_code_btn)
        self.preview_diff_btn = QPushButton("Diff (Full)")
        self.preview_diff_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton).fromTheme("view-difference", self.style().standardIcon(QStyle.StandardPixmap.SP_FileLinkIcon)))
        self.preview_diff_btn.setToolTip("Preview changes between selected file and cleaned/formatted pasted code (Ctrl+Shift+D).")
        self.preview_diff_btn.clicked.connect(self.preview_diff)
        new_code_controls.addWidget(self.preview_diff_btn)
        self.preview_snippet_btn = QPushButton("Diff (Snippet)")
        self.preview_snippet_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView).fromTheme("view-split-side-by-side", self.style().standardIcon(QStyle.StandardPixmap.SP_FileLinkIcon)))
        self.preview_snippet_btn.setToolTip("Preview replacing matching function/class in selected file with cleaned/formatted pasted snippet (Ctrl+Alt+D).")
        self.preview_snippet_btn.clicked.connect(self.preview_snippet_change)
        new_code_controls.addWidget(self.preview_snippet_btn)
        self.apply_snippet_btn = QPushButton("Apply Snippet")
        self.apply_snippet_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.apply_snippet_btn.setToolTip("Apply the change from the last successful 'Diff (Snippet)' preview (Ctrl+Alt+Enter).")
        self.apply_snippet_btn.setEnabled(False)
        self.apply_snippet_btn.clicked.connect(self.apply_snippet_patch)
        new_code_controls.addWidget(self.apply_snippet_btn)
        self.apply_new_code_btn = QPushButton("Apply Full File")
        self.apply_new_code_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.apply_new_code_btn.setToolTip("Overwrite selected file with the (cleaned/formatted) content of this editor (Ctrl+Enter).")
        self.apply_new_code_btn.clicked.connect(self.apply_new_code)
        new_code_controls.addWidget(self.apply_new_code_btn)
        new_code_controls.addStretch(1)
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self.undo_btn.setToolTip("Undo last change to selected file (restores from central .bak, creates central .redo) (Ctrl+Z).") # Updated tooltip
        self.undo_btn.clicked.connect(self.undo_change)
        new_code_controls.addWidget(self.undo_btn)
        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        self.redo_btn.setToolTip("Redo last undo for selected file (restores from central .redo, creates central .bak) (Ctrl+Y).") # Updated tooltip
        self.redo_btn.clicked.connect(self.redo_change)
        new_code_controls.addWidget(self.redo_btn)
        self.reset_btn = QPushButton("Reset UI")
        self.reset_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.reset_btn.setToolTip("Clear inputs, editors, logs, selections, and cancel operations.")
        self.reset_btn.clicked.connect(self.reset_ui_state)
        new_code_controls.addWidget(self.reset_btn)
        new_code_layout.addLayout(new_code_controls)
        splitter_right.addWidget(new_code_widget)
        splitter_right.setSizes(DEFAULT_SPLITTER_RIGHT_SIZES)
        splitter_main.addWidget(splitter_right)
        splitter_main.setSizes(DEFAULT_SPLITTER_MAIN_SIZES)
        main_layout.addWidget(splitter_main, 1)

        # --- Bottom Section (Progress Bar and Log Area) ---
        bottom_layout = QVBoxLayout()
        bottom_layout.setSpacing(5)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setToolTip("Progress of the Scan & Run operation.")
        bottom_layout.addWidget(self.progress_bar)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(LOG_AREA_HEIGHT)
        self.log_area.setToolTip("Operation logs, errors, and diff summaries.")
        self.log_area.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        bottom_layout.addWidget(self.log_area)
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

    def _init_hotkeys(self):
        """Initializes keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, activated=self.format_new_code)
        QShortcut(QKeySequence("Ctrl+Shift+D"), self, activated=self.preview_diff)
        QShortcut(QKeySequence("Ctrl+Alt+D"), self, activated=self.preview_snippet_change)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.apply_new_code)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self.apply_new_code)
        QShortcut(QKeySequence("Ctrl+Alt+Return"), self, activated=self.apply_snippet_patch)
        QShortcut(QKeySequence("Ctrl+Alt+Enter"), self, activated=self.apply_snippet_patch)
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo_change)
        QShortcut(QKeySequence.StandardKey.Redo, self, activated=self.redo_change)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.redo_change)
        QShortcut(QKeySequence.StandardKey.Open, self, activated=self.select_folder)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.handle_escape)
        QShortcut(QKeySequence.StandardKey.Find, self, activated=self.focus_find_input)
        QShortcut(QKeySequence(Qt.Key.Key_F3), self, activated=self.find_next_in_editor)
        QShortcut(QKeySequence("Shift+F3"), self, activated=self.find_previous_in_editor)

    def handle_escape(self):
        focused_widget = self.focusWidget()
        if focused_widget == self.find_bar_input:
            if self.find_bar_input.text():
                self.find_bar_input.clear()
                self.find_bar_input.setPalette(self.new_code_editor.palette())
            else:
                self.new_code_editor.setFocus()
        elif isinstance(focused_widget, QLineEdit):
            focused_widget.clear()
        elif focused_widget == self.file_tree:
            self.file_tree.clearSelection()
            self._clear_and_disable_on_selection_change()
        elif isinstance(focused_widget, CodeEditor):
            cursor = focused_widget.textCursor()
            if cursor.hasSelection():
                cursor.clearSelection()
                focused_widget.setTextCursor(cursor)
            else:
                self.setFocus()
        else:
            if focused_widget and focused_widget != self:
                focused_widget.clearFocus()

    def select_folder(self):
        start_dir = self.current_folder_path if self.current_folder_path else str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder", start_dir, QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks)
        if folder:
            self.reset_ui_state()
            self.current_folder_path = folder
            folder_path_obj = Path(folder)
            try:
                parent_name = folder_path_obj.parent.name
                display_name = f"{parent_name}{os.sep}{folder_path_obj.name}"
            except Exception:
                display_name = folder_path_obj.name
            if len(display_name) > 80:
                display_name = "..." + display_name[-77:]
            self.folder_label.setText(display_name)
            self.folder_label.setToolTip(folder)
            source_root_index = self.fs_model.setRootPath(folder)
            if not source_root_index.isValid():
                self.log_message(f"Error: Could not set root path in model: {folder}", COLOR_ERROR)
                QMessageBox.critical(self, "Model Error", f"Failed to set the file system model root path to:\n{folder}")
                return
            proxy_root_index = self.proxy_model.mapFromSource(source_root_index)
            if not proxy_root_index.isValid():
                self.log_message(f"Error: Could not map root path to proxy model: {folder}", COLOR_ERROR)
            self.file_tree.setRootIndex(proxy_root_index)
            QTimer.singleShot(0, self._hide_tree_columns)
            self.log_message(f"Selected folder: {folder}", COLOR_INFO)

    def _hide_tree_columns(self):
        if self.fs_model:
            for i in range(1, self.fs_model.columnCount()):
                self.file_tree.setColumnHidden(i, True)

    def filter_file_tree(self, text: str):
        filter_pattern = f"*{text}*" if text else ""
        self.proxy_model.setFilterWildcard(filter_pattern)


    # --- MODIFIED: show_tree_context_menu ---
    def show_tree_context_menu(self, position):
        """Displays a context menu for the clicked item in the file tree."""
        index: QModelIndex = self.file_tree.indexAt(position)
        if not index.isValid():
            return

        source_index = self.proxy_model.mapToSource(index)
        if not source_index.isValid():
            return

        file_path_str = self.fs_model.filePath(source_index)
        original_file_path = Path(file_path_str) # Keep original path name
        is_dir = self.fs_model.isDir(source_index)

        menu = QMenu(self)

        # --- Common Actions ---
        open_folder_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), "Open Containing Folder", self)
        target_folder_path = original_file_path if is_dir else original_file_path.parent
        open_folder_action.triggered.connect(lambda: self.trigger_open_containing_folder(target_folder_path))
        menu.addAction(open_folder_action)

        copy_path_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView), "Copy Full Path", self)
        copy_path_action.triggered.connect(lambda: self.trigger_copy_file_path(file_path_str))
        menu.addAction(copy_path_action)

        menu.addSeparator()

        # --- File-Specific Actions ---
        if not is_dir:
            # --- Get CENTRAL backup/redo paths ---
            central_dir, central_backup_path, central_redo_path, path_err = get_central_backup_paths(original_file_path)

            if path_err:
                # Show error in context menu if paths can't be determined
                err_action = QAction(f"Error: {path_err}", self)
                err_action.setEnabled(False)
                menu.addAction(err_action)
            else:
                # Only add actions if paths are valid
                # Check existence of CENTRAL files
                backup_exists = central_backup_path and central_backup_path.exists()
                redo_exists = central_redo_path and central_redo_path.exists()

                # Action: Diff Against Backup
                diff_bak_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileLinkIcon), "Diff vs Backup (.bak)", self)
                diff_bak_action.setEnabled(backup_exists)
                # Pass ORIGINAL path and CENTRAL backup path to trigger
                diff_bak_action.triggered.connect(
                    lambda: self.trigger_diff_against_backup(original_file_path, central_backup_path)
                )
                menu.addAction(diff_bak_action)

                # Action: Diff Against Redo State
                diff_redo_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileLinkIcon), "Diff vs Redo (.redo)", self)
                diff_redo_action.setEnabled(redo_exists)
                # Pass ORIGINAL path and CENTRAL redo path to trigger
                diff_redo_action.triggered.connect(
                    lambda: self.trigger_diff_against_redo(original_file_path, central_redo_path)
                )
                menu.addAction(diff_redo_action)

                menu.addSeparator()

                # Action: Restore from Backup
                restore_bak_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack).fromTheme("document-revert"), "Restore from Backup (.bak)", self)
                restore_bak_action.setEnabled(backup_exists)
                # Pass ORIGINAL target path and CENTRAL backup source path
                restore_bak_action.triggered.connect(
                    lambda: self.trigger_restore_from_source(original_file_path, central_backup_path)
                )
                menu.addAction(restore_bak_action)

                # Action: Restore from Redo State
                restore_redo_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward).fromTheme("document-revert"), "Restore from Redo (.redo)", self)
                restore_redo_action.setEnabled(redo_exists)
                # Pass ORIGINAL target path and CENTRAL redo source path
                restore_redo_action.triggered.connect(
                    lambda: self.trigger_restore_from_source(original_file_path, central_redo_path)
                )
                menu.addAction(restore_redo_action)

        # Show menu
        menu.exec(self.file_tree.viewport().mapToGlobal(position))


    # --- Context Menu Trigger Methods ---
    # trigger_open_containing_folder, trigger_copy_file_path remain IDENTICAL
    # trigger_diff_against_backup, trigger_diff_against_redo, _show_diff_dialog_helper, trigger_restore_from_source
    # now correctly receive the appropriate original or central paths from the modified context menu logic.
    # The methods themselves don't need changes as they just operate on the Path objects passed to them.

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

    # --- MODIFIED: Takes original file and CENTRAL backup/redo file paths ---
    def trigger_diff_against_backup(self, original_file_path: Path, central_backup_path: Path):
        """Shows diff between current file and its central backup."""
        if not central_backup_path:
            QMessageBox.warning(self, "Diff Error", "Central backup path is invalid.")
            return
        self._show_diff_dialog_helper(original_file_path, central_backup_path, "Diff: Current vs Backup")

    # --- MODIFIED: Takes original file and CENTRAL backup/redo file paths ---
    def trigger_diff_against_redo(self, original_file_path: Path, central_redo_path: Path):
        """Shows diff between current file and its central redo state."""
        if not central_redo_path:
            QMessageBox.warning(self, "Diff Error", "Central redo path is invalid.")
            return
        self._show_diff_dialog_helper(original_file_path, central_redo_path, "Diff: Current vs Redo State")

    # _show_diff_dialog_helper remains IDENTICAL (it takes any two paths)
    def _show_diff_dialog_helper(self, file1_path: Path, file2_path: Path, title_prefix: str):
        """Helper method to read files and display the DiffDialog."""
        # ... (No changes needed inside this helper) ...
        if not file1_path.exists():
            QMessageBox.warning(self, "Diff Error", f"File not found: {file1_path.name}")
            return
        # Check the *second* path (which might be the central backup/redo)
        if not file2_path.exists():
            QMessageBox.warning(self, "Diff Error", f"Comparison file not found: {file2_path}") # Show full path for central files
            return

        try:
            content1, err1 = safe_read_file(file1_path)
            content2, err2 = safe_read_file(file2_path)

            if err1: raise ValueError(f"Error reading {file1_path.name}: {err1}")
            if err2: raise ValueError(f"Error reading comparison file {file2_path.name}: {err2}")

            lines1 = content1.splitlines() if content1 is not None else []
            lines2 = content2.splitlines() if content2 is not None else []

            # Use relative names for dialog clarity if possible, or full path for central
            fdesc1 = f"a/{file1_path.name}"
            fdesc2 = f"b/{file2_path.name}" # Default name
            # Heuristic: if file2 is likely in the central backup dir, show more path?
            try:
                # Check if file2_path shares the central backup dir root
                home_dir = Path.home()
                central_backup_dir_root = home_dir / CODE_HELPER_BACKUP_DIR_NAME
                if file2_path.is_relative_to(central_backup_dir_root):
                   # Show path relative to central backup dir? Or just name + (central)?
                   fdesc2 = f"b/{file2_path.name} (Backup)" # Keep it simple
            except ValueError: # is_relative_to can fail if paths are different drives
                 pass
            except Exception: # Catch other potential errors in this heuristic
                 pass

            dialog = DiffDialog(lines1, lines2, fromdesc=fdesc1, todesc=fdesc2, parent=self)
            dialog_title = f"{title_prefix} - {file1_path.name}"
            dialog.setWindowTitle(dialog_title[:120])
            dialog.exec()

        except Exception as e:
            error_msg = f"Failed to generate diff between {file1_path.name} and {file2_path.name}: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            QMessageBox.critical(self, "Diff Error", error_msg)


    # --- MODIFIED: Takes original target file and CENTRAL source file ---
    def trigger_restore_from_source(self, target_file: Path, source_file: Path):
        """Handles restoring a file from a central source (.bak or .redo) after confirmation."""
        # source_file is now expected to be the central backup/redo path
        if not source_file or not source_file.exists():
            QMessageBox.warning(self, "Restore Error", f"Central source file not found or invalid: {source_file}")
            return

        source_type = ".bak (Backup)" if source_file.suffix.endswith(".bak") else ".redo (Undo State)"
        # Show the original target filename and the central source filename/type
        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            f"This will overwrite:\n'{target_file.name}'\n\nwith the content from central {source_type}:\n'{source_file.name}'\n\nAre you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Check read permission for CENTRAL source
                if not os.access(str(source_file), os.R_OK):
                    raise PermissionError(f"Permission denied reading source file: {source_file}")

                # Check write permission for ORIGINAL target (or its directory)
                can_write_target = (target_file.exists() and os.access(str(target_file), os.W_OK)) or \
                                   (not target_file.exists() and os.access(str(target_file.parent), os.W_OK))
                if not can_write_target:
                    perm_issue = f"writing to file {target_file.name}" if target_file.exists() else f"writing to directory {target_file.parent}"
                    raise PermissionError(f"Permission denied {perm_issue}")

                # Create .redo state from the *current* ORIGINAL target file *before* overwriting it.
                # backup_and_redo handles storing this new redo state CENTRALLY.
                if target_file.exists():
                    backup_ok, backup_err = backup_and_redo(target_file)
                    if not backup_ok:
                        raise OSError(f"Could not create central undo state (.redo) before restoring: {backup_err}")

                # Perform Restore: Copy from CENTRAL source to ORIGINAL target
                shutil.copy2(str(source_file), str(target_file))

                self.log_message(f"Restored '{target_file.name}' from central {source_type} '{source_file.name}'", COLOR_SUCCESS)

                # Refresh preview if the restored file is currently selected
                self._refresh_preview_after_change(target_file)
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
    # reset_ui_state, _perform_reset, log_message remain IDENTICAL

    def reset_ui_state(self):
        self.cancel_operation()
        QTimer.singleShot(150, self._perform_reset)

    def _perform_reset(self):
        if self.scan_thread and self.scan_thread.isRunning(): print("Warning: Scan thread did not stop quickly during reset.")
        if self.replace_thread and self.replace_thread.isRunning(): print("Warning: Replace thread did not stop quickly during reset.")
        self.find_input.clear()
        self.replace_input.clear()
        self.regex_checkbox.setChecked(False)
        self.filter_input.clear()
        self.find_bar_input.clear()
        self.find_bar_case_checkbox.setChecked(False)
        self.find_bar_input.setPalette(self.new_code_editor.palette())
        self.preview_area.setReadOnly(False); self.preview_area.clear(); self.preview_area.setReadOnly(True)
        self.new_code_editor.clear()
        self.log_area.clear()
        self.progress_bar.setValue(0); self.progress_bar.setFormat("%p%")
        self.file_tree.clearSelection()
        self.files = []
        self._pending_patch_info = None
        self.apply_snippet_btn.setEnabled(False)
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.log_message("UI Reset.", COLOR_INFO); print("UI Reset performed.")

    def log_message(self, message: str, color: str = COLOR_DEFAULT_TEXT, is_html: bool = False):
        if not hasattr(self, "log_area"): return
        log_entry = ""
        if is_html:
            log_entry = f'<font color="{color}">{message}</font>'
        else:
            escaped_message = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            log_entry = f'<font color="{color}">{escaped_message}</font>'
        self.log_area.append(log_entry)
        QTimer.singleShot(0, lambda: self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum()))

    # --- Thread Handling ---
    # handle_thread_error, cancel_operation, scan_and_run, scan_finished_or_cancelled, run_replacement, update_progress, handle_replacement_error, replacement_finished
    # remain IDENTICAL to previous version (Black integration)

    def handle_thread_error(self, error_message: str):
        self.log_message(f"ERROR: {error_message}", COLOR_ERROR)
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def cancel_operation(self):
        cancelled_scan = False; cancelled_replace = False
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop(); self.log_message("Attempting to cancel file scan...", COLOR_WARNING); cancelled_scan = True
        if self.replace_thread and self.replace_thread.isRunning():
            self.replace_thread.stop(); self.log_message("Attempting to cancel replacement process...", COLOR_WARNING); cancelled_replace = True
        if cancelled_scan or cancelled_replace:
            self.cancel_btn.setEnabled(False)
        else:
            self.log_message("No operation currently running to cancel.", COLOR_INFO)

    def scan_and_run(self):
        if not self.current_folder_path:
            QMessageBox.warning(self,"No Folder Selected","Please select a folder first using 'Select Folder'.")
            return
        if (self.scan_thread and self.scan_thread.isRunning()) or (self.replace_thread and self.replace_thread.isRunning()):
            QMessageBox.warning(self, "Operation in Progress","A scan or replacement operation is already running.")
            return
        pattern = self.find_input.text()
        replacement = self.replace_input.text()
        use_regex = self.regex_checkbox.isChecked()
        self.log_message(f"Starting scan in '{Path(self.current_folder_path).name}'...", COLOR_DEFAULT_TEXT)
        self.progress_bar.setValue(0); self.progress_bar.setFormat("Scanning... %p%")
        self.scan_btn.setEnabled(False); self.cancel_btn.setEnabled(True)
        self.scan_thread = None; self.replace_thread = None
        try:
            self.scan_thread = FileLoaderThread(self.current_folder_path, parent=self)
            self.scan_thread.files_loaded.connect(lambda files, folder_path: self.run_replacement(files, pattern, replacement, use_regex))
            self.scan_thread.error_occurred.connect(self.handle_thread_error)
            self.scan_thread.finished.connect(self.scan_finished_or_cancelled)
            self.scan_thread.start()
        except Exception as e:
            error_msg = f"Failed to start file scanning thread: {e}"; self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc(); QMessageBox.critical(self, "Thread Error", error_msg)
            self.scan_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.progress_bar.setFormat("%p%")

    def scan_finished_or_cancelled(self):
        print("FileLoaderThread finished signal received.")
        if not (self.replace_thread and self.replace_thread.isRunning()):
            print("Resetting buttons from scan_finished_or_cancelled.")
            self.scan_btn.setEnabled(True); self.cancel_btn.setEnabled(False)
            self.progress_bar.setValue(0); self.progress_bar.setFormat("%p%")

    def run_replacement(self, files: list[Path], pattern: str, replacement: str, use_regex: bool):
        print(f"run_replacement called with {len(files)} files.")
        self.files = files
        if self.scan_thread and not self.scan_thread._is_running:
            self.log_message("Scan was cancelled before replacement could start.", COLOR_WARNING)
            return
        if not files:
            self.log_message("No '.py' files found in the selected folder or subfolders.", COLOR_WARNING)
            self.scan_btn.setEnabled(True); self.cancel_btn.setEnabled(False)
            self.progress_bar.setValue(0); self.progress_bar.setFormat("No files found")
            return
        self.log_message(f"Scan complete. Found {len(files)} files. Starting processing...", COLOR_DEFAULT_TEXT)
        self.progress_bar.setValue(0); self.progress_bar.setFormat("Processing... %p%")
        try:
            if self.replace_thread and self.replace_thread.isRunning():
                self.log_message("Error: Previous replacement thread still running.", COLOR_ERROR)
                self.scan_btn.setEnabled(True); self.cancel_btn.setEnabled(False)
                return
            self.replace_thread = ReplacementThread(self.files, pattern, replacement, use_regex, parent=self)
            self.replace_thread.progress.connect(self.update_progress)
            self.replace_thread.error_occurred.connect(self.handle_replacement_error)
            self.replace_thread.finished.connect(self.replacement_finished)
            self.replace_thread.start()
        except Exception as e:
            error_msg = f"Failed to start replacement thread: {e}"; self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc(); QMessageBox.critical(self, "Thread Error", error_msg)
            self.scan_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.progress_bar.setFormat("%p%")

    def update_progress(self, progress_percent: int, log_msg: str):
        self.progress_bar.setValue(progress_percent)
        color = COLOR_DEFAULT_TEXT; is_html = False
        log_summary = log_msg.splitlines()[0] if "\n" in log_msg else log_msg
        if ("[Error]" in log_summary or "[Read Error]" in log_summary or "[Replace Error]" in log_summary or
            "[Write Error]" in log_summary or "[Backup/Redo Error]" in log_summary or "Permission denied" in log_summary or
            "Invalid regex" in log_summary or "Cannot decode" in log_summary or "formatting failed" in log_summary):
            color = COLOR_ERROR; self.log_message(log_msg, color, is_html=False)
        elif "[Updated]" in log_summary or "[Updated with Format Warning]" in log_summary or "[Updated with Replace Error]" in log_summary:
            color = COLOR_SUCCESS
            if "[Updated with Format Warning]" in log_summary or "[Updated with Replace Error]" in log_summary: color = COLOR_WARNING
            summary_line = log_summary.replace("<", "&lt;").replace(">", "&gt;")
            diff_html = ""
            if "\nDiff:\n" in log_msg:
                try:
                    diff_part = log_msg.split("\nDiff:\n", 1)[1]
                    escaped_diff_lines = [l.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for l in diff_part.splitlines()]
                    diff_html = (f'<pre style="color:{COLOR_INFO}; margin-top: 2px; margin-bottom: 0px; white-space: pre-wrap; font-size: 9pt;">'
                                 f"{'<br>'.join(escaped_diff_lines)}</pre>")
                except Exception as e:
                    print(f"Error processing diff for logging: {e}"); diff_html = f"<br><i>(Error displaying diff)</i>"
            log_html = f'<font color="{color}">{summary_line}</font>{diff_html}"'
            self.log_message(log_html, is_html=True)
        elif "[Format Warning]" in log_summary: color = COLOR_WARNING; self.log_message(log_msg, color, is_html=False)
        elif "[No change]" in log_summary: color = COLOR_INFO; self.log_message(log_msg, color, is_html=False)
        elif "[Cancelled]" in log_summary or "[Skipped]" in log_summary: color = COLOR_WARNING; self.log_message(log_msg, color, is_html=False)
        else: self.log_message(log_msg, color, is_html=False)

    def handle_replacement_error(self, error_message: str): pass

    def replacement_finished(self):
        print("ReplacementThread finished signal received.")
        was_cancelled = self.replace_thread and not self.replace_thread._is_running
        if was_cancelled:
            self.log_message("--- Processing cancelled by user ---", COLOR_WARNING); self.progress_bar.setFormat("Cancelled")
        else:
            self.log_message("--- Processing complete ---", COLOR_DEFAULT_TEXT)
            if self.progress_bar.value() < 100: self.progress_bar.setValue(100)
            self.progress_bar.setFormat("Finished")
        self.scan_btn.setEnabled(True); self.cancel_btn.setEnabled(False)
        self._refresh_preview_if_selected()


    # --- File Tree and Preview Interaction ---
    # on_tree_clicked, _load_file_into_preview, _clear_and_disable_on_selection_change
    # remain IDENTICAL

    def on_tree_clicked(self, index: QModelIndex):
        if not index.isValid(): self._clear_and_disable_on_selection_change(); return
        source_index = self.proxy_model.mapToSource(index)
        if not source_index.isValid(): self._clear_and_disable_on_selection_change(); return
        if self.fs_model.isDir(source_index): self._clear_and_disable_on_selection_change(); return
        file_path_str = self.fs_model.filePath(source_index)
        self._load_file_into_preview(Path(file_path_str))

    def _load_file_into_preview(self, file_path: Path):
        self._clear_and_disable_on_selection_change()
        content, error_msg = safe_read_file(file_path)
        self.preview_area.setReadOnly(False)
        if error_msg:
            self.preview_area.setPlainText(f"# Error loading preview:\n# {error_msg}"); self.log_message(f"Preview Error: {error_msg}", COLOR_ERROR)
        elif content is not None:
            self.preview_area.setPlainText(content); self.preview_area.moveCursor(self.preview_area.textCursor().MoveOperation.Start)
        else:
            self.preview_area.setPlainText(f"# Error: Could not read file {file_path.name}, reason unknown."); self.log_message(f"Preview Error: Unknown issue reading {file_path.name}", COLOR_ERROR)
        self.preview_area.setReadOnly(True)

    def _clear_and_disable_on_selection_change(self):
        self._pending_patch_info = None
        if hasattr(self, "apply_snippet_btn"): self.apply_snippet_btn.setEnabled(False)

    # --- MODIFIED: _get_selected_source_index_and_path - NO LONGER USED FOR BACKUP PATHS ---
    # This helper is now ONLY used to get the *original* selected file path.
    def _get_selected_source_index_and_path(self,) -> tuple[QModelIndex | None, Path | None]:
        """Gets the source model index and Path object for the currently selected file."""
        current_proxy_index = self.file_tree.currentIndex()
        if not current_proxy_index.isValid(): return None, None
        source_index = self.proxy_model.mapToSource(current_proxy_index)
        if not source_index.isValid() or self.fs_model.isDir(source_index): return None, None
        file_path = Path(self.fs_model.filePath(source_index))
        return source_index, file_path


    # _refresh_preview_after_change, _refresh_preview_if_selected
    # remain IDENTICAL
    def _refresh_preview_after_change(self, file_path: Path):
        try:
            current_source_index, current_file_path = self._get_selected_source_index_and_path()
            if current_file_path == file_path:
                print(f"Refreshing preview for modified file: {file_path.name}")
                self._load_file_into_preview(file_path)
        except Exception as e:
            print(f"Error during preview refresh for {file_path.name}: {e}")
            self.log_message(f"Warning: Error refreshing preview for {file_path.name}: {e}", COLOR_WARNING)

    def _refresh_preview_if_selected(self):
        source_index, file_path = self._get_selected_source_index_and_path()
        if file_path: self._refresh_preview_after_change(file_path)


    # --- Code Editor Actions ---
    # format_new_code, apply_new_code, preview_diff, preview_snippet_change, apply_snippet_patch
    # remain IDENTICAL to previous version (Black integration)

    def format_new_code(self):
        editor = self.new_code_editor; current_code = editor.toPlainText()
        if not current_code.strip(): QMessageBox.warning(self,"No Code","The code editor is empty. Paste some Python code first."); return
        try:
            formatted_code, format_error = preprocess_and_format_with_black(current_code)
            if format_error:
                QMessageBox.warning(self,"Cleaning/Formatting Error",f"Could not clean or format the pasted code:\n{format_error}")
                self.log_message(f"Pasted code cleaning/formatting failed: {format_error}", COLOR_ERROR)
            else:
                cursor = editor.textCursor(); original_pos = cursor.position(); original_anchor = cursor.anchor(); has_selection = cursor.hasSelection()
                editor.setPlainText(formatted_code)
                new_length = len(formatted_code); cursor.setPosition(min(original_anchor, new_length))
                if has_selection: cursor.setPosition(min(original_pos, new_length), cursor.MoveMode.KeepAnchor)
                else: cursor.setPosition(min(original_pos, new_length))
                editor.setTextCursor(cursor)
                self.log_message("Pasted code cleaned and formatted successfully with Black.", COLOR_INFO)
        except Exception as e:
            error_msg = f"An unexpected error occurred during cleaning/formatting: {e}"; self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc(); QMessageBox.critical(self, "Processing Error", error_msg)

    def apply_new_code(self):
        source_index, file_path = self._get_selected_source_index_and_path()
        if not file_path: QMessageBox.warning(self,"No File Selected","Please select a file in the tree to apply the editor content to."); return
        new_code_raw = self.new_code_editor.toPlainText()
        if not new_code_raw.strip():
            reply = QMessageBox.question(self,"Apply Empty Content?",f"The code editor is empty. Apply empty content to overwrite '{file_path.name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel: return
        self._clear_and_disable_on_selection_change()
        final_code_to_write = ""; log_color = COLOR_SUCCESS; log_suffix = "."
        try:
            processed_code, process_error = preprocess_and_format_with_black(new_code_raw)
            if process_error:
                reply = QMessageBox.warning(self,"Formatting Error", f"Black failed to format the code:\n{process_error}\n\nDo you want to apply the code *after cleaning/normalization but without Black formatting*?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No: self.log_message(f"Apply Full File cancelled due to formatting error on {file_path.name}.", COLOR_WARNING); return
                final_code_to_write = processed_code; log_color = COLOR_WARNING; log_suffix = " (applied after preprocessing, but Black format failed)."
                self.log_message(f"Applying preprocessed code to {file_path.name} after Black formatting error.", COLOR_WARNING)
            else: final_code_to_write = processed_code; log_suffix = " (cleaned & formatted)."
        except Exception as e:
            error_msg = f"Unexpected error during processing before apply: {e}"; self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc(); QMessageBox.critical(self, "Processing Error", error_msg); return
        try:
            backup_ok, backup_err = backup_and_redo(file_path) # This now uses central store
            if not backup_ok:
                error_msg = f"Could not create backup/redo for {file_path.name}: {backup_err}"; self.log_message(error_msg, COLOR_ERROR); QMessageBox.critical(self, "Backup/Redo Error", error_msg); return
        except Exception as e:
            error_msg = f"Unexpected error during backup/redo before apply: {e}"; self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc(); QMessageBox.critical(self, "Backup/Redo Error", error_msg); return
        try:
            write_ok, write_err = safe_write_file(file_path, final_code_to_write)
            if not write_ok:
                error_msg = f"Failed to write changes to {file_path.name}: {write_err}"; self.log_message(error_msg, COLOR_ERROR); QMessageBox.critical(self, "File Write Error", error_msg); return
            self.log_message(f"Applied editor content to {file_path.name}{log_suffix}", log_color)
            self._refresh_preview_after_change(file_path)
            self.new_code_editor.clear()
        except Exception as e:
            error_msg = f"Unexpected error applying code to {file_path.name}: {e}"; self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc(); QMessageBox.critical(self, "Apply Error", error_msg)

    def preview_diff(self):
        source_index, file_path = self._get_selected_source_index_and_path()
        if not file_path: QMessageBox.warning(self,"No File Selected","Select a file in the tree to compare against."); return
        new_code_raw = self.new_code_editor.toPlainText()
        if not new_code_raw.strip(): QMessageBox.warning(self, "Editor Empty", "Paste code into the editor to compare."); return
        self._clear_and_disable_on_selection_change()
        try:
            original_content, read_error = safe_read_file(file_path)
            if read_error: QMessageBox.critical(self,"File Read Error",f"Could not read selected file '{file_path.name}':\n{read_error}"); return
            original_lines = original_content.splitlines() if original_content is not None else []
            processed_code, process_error = preprocess_and_format_with_black(new_code_raw)
            if process_error:
                reply = QMessageBox.warning(self,"Formatting Error",f"Could not format pasted code with Black:\n{process_error}\n\nShow diff against the *preprocessed* pasted code?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.No: return
                new_lines = processed_code.splitlines(); to_desc = f"b/{file_path.name} (Pasted - Preprocessed)"
                self.log_message("Previewing diff against preprocessed pasted code due to Black error.", COLOR_WARNING)
            else:
                new_lines = processed_code.splitlines(); to_desc = f"b/{file_path.name} (Pasted - Cleaned & Formatted)"
                self.log_message(f"Previewing diff for {file_path.name} vs cleaned/formatted pasted code.", COLOR_INFO)
            diff_dialog = DiffDialog(original_lines, new_lines, fromdesc=f"a/{file_path.name} (Current)", todesc=to_desc, parent=self)
            dialog_title = f"Diff Preview (Full): {file_path.name}"; diff_dialog.setWindowTitle(dialog_title[:120]); diff_dialog.exec()
        except Exception as e:
            error_msg = f"Failed to generate full diff: {e}"; self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc(); QMessageBox.critical(self, "Diff Error", error_msg)

    def preview_snippet_change(self):
        self._clear_and_disable_on_selection_change()
        source_index, file_path = self._get_selected_source_index_and_path()
        if not file_path: QMessageBox.warning(self, "No File Selected", "Select a target file in the tree first."); return
        snippet_text_raw = self.new_code_editor.toPlainText().strip()
        if not snippet_text_raw: QMessageBox.warning(self,"No Snippet","Paste the code snippet (function or class) into the editor below."); return
        if not file_path.exists(): QMessageBox.warning(self, "File Not Found", f"Selected target file not found:\n{file_path}"); return
        try:
            processed_snippet, process_error = preprocess_and_format_with_black(snippet_text_raw)
            if process_error: QMessageBox.warning(self,"Snippet Processing Error",f"Could not clean or format the pasted snippet (check syntax or Black issues):\n{process_error}"); return
            snippet_node, ast_parse_err = find_ast_node(processed_snippet, "")
            if ast_parse_err: QMessageBox.warning(self,"Invalid Snippet Syntax",f"Snippet has syntax errors even after processing:\n{ast_parse_err}"); return
            target_name = None; target_type = "block"
            try:
                snippet_tree = ast.parse(processed_snippet)
                for node in ast.walk(snippet_tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        target_name = node.name
                        target_type = "function" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "class"
                        break
            except Exception as e: QMessageBox.critical(self, "Snippet AST Error", f"Error analyzing snippet structure: {e}"); return
            if not target_name: QMessageBox.warning(self,"Cannot Identify Snippet Target","Could not find a function or class definition at the beginning of the pasted snippet using AST analysis."); return
            self.log_message(f"Snippet identified as {target_type} '{target_name}'. Looking in target file...", COLOR_INFO)
            original_content, read_error = safe_read_file(file_path)
            if read_error: QMessageBox.critical(self,"File Read Error",f"Could not read target file '{file_path.name}':\n{read_error}"); return
            target_node, find_node_err = find_ast_node(original_content, target_name)
            if find_node_err: QMessageBox.warning(self,"Target File Syntax Error",f"Could not accurately find '{target_name}' in '{file_path.name}' due to a syntax error in that file:\n{find_node_err}"); return
            if not target_node: QMessageBox.warning(self,"Target Not Found",f"Could not find {target_type} '{target_name}' in the target file '{file_path.name}' using AST.\n(Check spelling or ensure the definition exists)."); return
            start_line_index = target_node.lineno - 1; end_line_index = target_node.end_lineno
            if start_line_index < 0 or end_line_index is None or end_line_index <= start_line_index: QMessageBox.critical(self,"AST Line Number Error",f"AST returned invalid line numbers for '{target_name}': start={start_line_index + 1}, end={end_line_index}"); return
            original_lines = original_content.splitlines()
            if start_line_index >= len(original_lines) or end_line_index > len(original_lines): QMessageBox.critical(self,"AST Line Number Error",f"AST line numbers ({start_line_index + 1}-{end_line_index}) are out of bounds for file '{file_path.name}' (Total lines: {len(original_lines)})"); return
            existing_block_lines = original_lines[start_line_index:end_line_index]
            snippet_lines = processed_snippet.splitlines()
            if not existing_block_lines: print(f"Warning: Extracted empty block for '{target_name}' at lines {start_line_index + 1}-{end_line_index}")
            diff_dialog = DiffDialog(existing_block_lines, snippet_lines, fromdesc=f"a/{file_path.name} ({target_name} - Current)", todesc=f"b/{file_path.name} ({target_name} - Snippet)", parent=self)
            dialog_title = f"Snippet Diff: {target_name} in {file_path.name}"; diff_dialog.setWindowTitle(dialog_title[:120])
            diff_lines = list(difflib.unified_diff([line + "\n" for line in existing_block_lines], [line + "\n" for line in snippet_lines], lineterm="", n=0))
            if not diff_lines: QMessageBox.information(self,"No Changes Detected",f"The provided (cleaned/formatted) snippet seems identical to the existing {target_type} '{target_name}' in the target file."); self.log_message(f"Snippet diff for '{target_name}' showed no changes.", COLOR_INFO); return
            self._pending_patch_info = {"file_path": file_path, "start_line": start_line_index, "end_line": end_line_index, "snippet_lines": snippet_lines, "target_name": target_name, "target_type": target_type}
            self.apply_snippet_btn.setEnabled(True)
            self.log_message(f"Snippet diff for '{target_name}' ready. Use 'Apply Snippet' to confirm.", COLOR_INFO)
            diff_dialog.exec()
        except FileNotFoundError as e: self.log_message(f"File not found during snippet preview: {e}", COLOR_ERROR); QMessageBox.critical(self, "File Error", f"File not found: {e}")
        except Exception as e:
            error_msg = f"Failed to preview snippet change: {e}"; self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc(); QMessageBox.critical(self, "Snippet Preview Error", error_msg)
            self._clear_and_disable_on_selection_change()

    def apply_snippet_patch(self):
        if not self._pending_patch_info: QMessageBox.warning(self,"No Pending Snippet","Run 'Diff (Snippet)' first to prepare a change."); return
        file_path = self._pending_patch_info.get("file_path"); start_line = self._pending_patch_info.get("start_line")
        end_line = self._pending_patch_info.get("end_line"); snippet_lines = self._pending_patch_info.get("snippet_lines")
        target_name = self._pending_patch_info.get("target_name", "snippet"); target_type = self._pending_patch_info.get("target_type", "block")
        if file_path is None or start_line is None or end_line is None or snippet_lines is None:
            QMessageBox.critical(self,"Internal Error","Pending snippet patch information is incomplete or corrupted.")
            self._clear_and_disable_on_selection_change(); return
        try:
            backup_ok, backup_err = backup_and_redo(file_path) # Uses central store
            if not backup_ok: error_msg = f"Could not create backup/redo for {file_path.name}: {backup_err}"; self.log_message(error_msg, COLOR_ERROR); QMessageBox.critical(self, "Backup/Redo Error", error_msg); self._clear_and_disable_on_selection_change(); return
            try:
                with open(file_path, "r", encoding="utf-8") as f: original_lines_with_ends = f.readlines()
            except Exception as read_error: QMessageBox.critical(self,"File Read Error",f"Could not read file '{file_path.name}' for patching:\n{read_error}"); self._clear_and_disable_on_selection_change(); return
            if start_line < 0 or end_line > len(original_lines_with_ends) or start_line > end_line: QMessageBox.critical(self,"Patch Index Error",f"Stored line indices ({start_line + 1}-{end_line}) are invalid for the current state of '{file_path.name}' (Total lines: {len(original_lines_with_ends)}).\nFile may have changed since preview."); self._clear_and_disable_on_selection_change(); return
            lines_before = original_lines_with_ends[:start_line]
            snippet_lines_with_os_nl = [line + os.linesep for line in snippet_lines]
            lines_after = original_lines_with_ends[end_line:]
            new_content = "".join(lines_before + snippet_lines_with_os_nl + lines_after)
            write_ok, write_err = safe_write_file(file_path, new_content)
            if not write_ok: error_msg = f"Failed to write patch to {file_path.name}: {write_err}"; self.log_message(error_msg, COLOR_ERROR); QMessageBox.critical(self, "File Write Error", error_msg); self._clear_and_disable_on_selection_change(); return
            self.log_message(f"Applied '{target_name}' {target_type} snippet patch to {file_path.name}.", COLOR_SUCCESS)
            self._refresh_preview_after_change(file_path)
        except (PermissionError, OSError, shutil.Error) as io_error: error_msg = f"Could not apply patch to {file_path.name}: {io_error}"; self.log_message(error_msg, COLOR_ERROR); QMessageBox.critical(self, "File Operation Error", error_msg)
        except Exception as e: error_msg = f"Failed to apply snippet patch to {file_path.name}: {e}"; self.log_message(error_msg, COLOR_ERROR); traceback.print_exc(); QMessageBox.critical(self, "Apply Patch Error", error_msg)
        finally: self._clear_and_disable_on_selection_change()


    # --- MODIFIED: Simple File-Based Undo/Redo Using Central Store ---
    def _get_selected_file_paths_for_undo_redo(self) -> tuple[Path | None, Path | None, Path | None, str | None]:
        """
        Gets the original file Path and calculates the CENTRAL .bak and .redo paths.
        Handles potential errors during path calculation.
        """
        source_index, original_file_path = self._get_selected_source_index_and_path()
        if not original_file_path:
            return None, None, None, None # No file selected

        # Use the utility to get central paths
        _central_dir, backup_path, redo_path, path_err = get_central_backup_paths(original_file_path)

        if path_err:
            # Log or show error if paths couldn't be determined
            QMessageBox.warning(self, "Undo/Redo Path Error", f"Could not determine backup/redo paths:\n{path_err}")
            return original_file_path, None, None, path_err # Return original path but None for backups

        return original_file_path, backup_path, redo_path, None # Return original and central paths


    def undo_change(self):
        """Restores the selected file from its CENTRAL .bak file (if exists)."""
        original_file_path, central_backup_path, central_redo_path, path_err = (
            self._get_selected_file_paths_for_undo_redo()
        )

        if not original_file_path:
            QMessageBox.warning(self, "No File Selected", "Please select a file in the tree to undo changes for.")
            return
        if path_err: return # Error already shown by helper function
        if not central_backup_path: # Check if helper returned valid path
             QMessageBox.critical(self, "Internal Error", "Could not calculate the central backup path.")
             return

        # Check existence of the CENTRAL backup file
        if not central_backup_path.exists():
            QMessageBox.information(self, "Undo Unavailable", f"No central backup file (.bak) found for '{original_file_path.name}'. Cannot undo.")
            return

        try:
            # Check read permission for CENTRAL backup
            if not os.access(str(central_backup_path), os.R_OK):
                raise PermissionError(f"Cannot read central backup file: {central_backup_path}")

            # Check write permission for ORIGINAL target (or its directory)
            can_write_target = (original_file_path.exists() and os.access(str(original_file_path), os.W_OK)) or \
                               (not original_file_path.exists() and os.access(str(original_file_path.parent), os.W_OK))
            if not can_write_target:
                perm_issue = f"writing to file {original_file_path.name}" if original_file_path.exists() else f"writing to directory {original_file_path.parent}"
                raise PermissionError(f"Permission denied {perm_issue}")

            # --- Save Current State for Redo (Centrally) ---
            # Use backup_and_redo utility: it saves current ORIGINAL file state to CENTRAL .redo
            # and moves existing CENTRAL .redo to CENTRAL .bak
            redo_ok, redo_err = backup_and_redo(original_file_path)
            if not redo_ok:
                raise OSError(f"Could not save current state for central redo: {redo_err}")

            # --- Perform Undo (Restore from CENTRAL Backup to ORIGINAL file) ---
            shutil.copy2(str(central_backup_path), str(original_file_path))

            self.log_message(f"Undo: Restored '{original_file_path.name}' from central backup.", COLOR_SUCCESS)

            # --- Post Undo ---
            self._refresh_preview_after_change(original_file_path)
            self._clear_and_disable_on_selection_change()

        except (PermissionError, OSError, shutil.Error) as io_error:
            error_msg = f"Undo Error: {io_error}"
            self.log_message(error_msg, COLOR_ERROR)
            QMessageBox.critical(self, "File Operation Error", error_msg)
        except Exception as e:
            error_msg = f"Failed to perform undo for {original_file_path.name}: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc()
            QMessageBox.critical(self, "Undo Error", error_msg)

    def redo_change(self):
        """Restores the selected file from its CENTRAL .redo file (if exists)."""
        original_file_path, central_backup_path, central_redo_path, path_err = (
            self._get_selected_file_paths_for_undo_redo()
        )

        if not original_file_path:
            QMessageBox.warning(self, "No File Selected", "Please select a file in the tree to redo changes for.")
            return
        if path_err: return # Error already shown
        if not central_redo_path: # Check if helper returned valid path
             QMessageBox.critical(self, "Internal Error", "Could not calculate the central redo path.")
             return

        # Check existence of the CENTRAL redo file
        if not central_redo_path.exists():
            QMessageBox.information(self, "Redo Unavailable", f"No central redo state file (.redo) found for '{original_file_path.name}'. Cannot redo.")
            return

        try:
            # Check read permission for CENTRAL redo file
            if not os.access(str(central_redo_path), os.R_OK):
                raise PermissionError(f"Cannot read central redo file: {central_redo_path}")

            # Check write permission for ORIGINAL target (or its directory)
            can_write_target = (original_file_path.exists() and os.access(str(original_file_path), os.W_OK)) or \
                               (not original_file_path.exists() and os.access(str(original_file_path.parent), os.W_OK))
            if not can_write_target:
                perm_issue = f"writing to file {original_file_path.name}" if original_file_path.exists() else f"writing to directory {original_file_path.parent}"
                raise PermissionError(f"Permission denied {perm_issue}")

            # --- Save Current State for Undo (Back to CENTRAL Backup) ---
            # Before restoring from .redo, save the *current* ORIGINAL state back to the
            # CENTRAL .bak file. This allows undoing the redo.
            if original_file_path.exists():
                # Need central backup path again
                _cbd, cbp, _crp, p_err = get_central_backup_paths(original_file_path)
                if p_err or not cbp:
                     print(f"Warning: Cannot determine central backup path before redo for {original_file_path.name}. Undo may fail.")
                else:
                     # Ensure central backup directory exists
                     cbp.parent.mkdir(parents=True, exist_ok=True)
                     # Check permissions
                     can_read_target = os.access(str(original_file_path), os.R_OK)
                     can_write_bak_dir = os.access(str(cbp.parent), os.W_OK)
                     if not can_read_target:
                         print(f"Warning: Cannot read current file {original_file_path.name} to update central backup before redo.")
                     elif not can_write_bak_dir:
                         print(f"Warning: Cannot write central backup file in {cbp.parent} before redo (permission denied).")
                     else:
                         # Create CENTRAL backup from current state (overwrites existing central .bak)
                         shutil.copy2(str(original_file_path), str(cbp))

            # --- Perform Redo (Restore from CENTRAL Redo State to ORIGINAL File) ---
            shutil.copy2(str(central_redo_path), str(original_file_path))

            self.log_message(f"Redo: Restored '{original_file_path.name}' from central redo state.", COLOR_SUCCESS)

            # --- Post Redo ---
            self._refresh_preview_after_change(original_file_path)
            self._clear_and_disable_on_selection_change()

        except (PermissionError, OSError, shutil.Error) as io_error:
            error_msg = f"Redo Error: {io_error}"
            self.log_message(error_msg, COLOR_ERROR)
            QMessageBox.critical(self, "File Operation Error", error_msg)
        except Exception as e:
            error_msg = f"Failed to perform redo for {original_file_path.name}: {e}"
            self.log_message(error_msg, COLOR_ERROR)
            traceback.print_exc()
            QMessageBox.critical(self, "Redo Error", error_msg)


    # --- Editor Find Functionality ---
    # focus_find_input, _get_find_flags, _do_find_in_editor, find_next_in_editor, find_previous_in_editor, _on_find_bar_text_changed
    # remain IDENTICAL

    def focus_find_input(self):
        self.find_bar_input.setFocus(); self.find_bar_input.selectAll()

    def _get_find_flags(self, backward: bool = False) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if self.find_bar_case_checkbox.isChecked(): flags |= QTextDocument.FindFlag.FindCaseSensitively
        if backward: flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def _do_find_in_editor(self, backward: bool = False):
        search_text = self.find_bar_input.text(); editor = self.new_code_editor
        if not search_text: self.find_bar_input.setPalette(editor.palette()); return False
        flags = self._get_find_flags(backward=backward)
        found = editor.find(search_text, flags)
        if found: self.find_bar_input.setPalette(self._find_match_palette_match)
        else:
            self.find_bar_input.setPalette(self._find_match_palette_no_match)
            cursor = editor.textCursor()
            if backward: cursor.movePosition(cursor.MoveOperation.End)
            else: cursor.movePosition(cursor.MoveOperation.Start)
            editor.setTextCursor(cursor)
            found = editor.find(search_text, flags)
            if found: self.find_bar_input.setPalette(self._find_match_palette_match)
            else: self.log_message(f"Find: Text '{search_text}' not found.", COLOR_INFO)
        return found

    def find_next_in_editor(self): self._do_find_in_editor(backward=False)
    def find_previous_in_editor(self): self._do_find_in_editor(backward=True)

    def _on_find_bar_text_changed(self, text: str):
        current_base_color = self.find_bar_input.palette().color(QPalette.ColorRole.Base)
        default_base_color = self.new_code_editor.palette().color(QPalette.ColorRole.Base)
        if current_base_color != default_base_color: self.find_bar_input.setPalette(self.new_code_editor.palette())


    # --- Graceful Shutdown ---
    # closeEvent, _check_threads_before_close remain IDENTICAL

    def closeEvent(self, event):
        print("Close event triggered.")
        self.cancel_operation()
        scan_running = self.scan_thread and self.scan_thread.isRunning()
        replace_running = self.replace_thread and self.replace_thread.isRunning()
        if scan_running or replace_running:
            print("Background operations active. Waiting briefly before re-checking...")
            QTimer.singleShot(300, lambda: self._check_threads_before_close(event))
            event.ignore()
        else:
            print("No background operations running. Closing application.")
            event.accept()

    def _check_threads_before_close(self, event):
        print("Re-checking thread status before close...")
        scan_running = self.scan_thread and self.scan_thread.isRunning()
        replace_running = self.replace_thread and self.replace_thread.isRunning()
        if scan_running or replace_running:
            thread_names = []
            if scan_running: thread_names.append("File Scan")
            if replace_running: thread_names.append("File Processing")
            running_tasks = " and ".join(thread_names)
            reply = QMessageBox.warning(self,"Operations Still Running",f"The following background task(s) did not stop quickly:\n- {running_tasks}\n\nForcing quit might leave files in an inconsistent state.\n\nForce quit anyway?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes: print("User chose to force quit. Accepting close event."); event.accept()
            else:
                print("User cancelled close. Allowing operations to continue.")
                event.ignore()
                if hasattr(self, "cancel_btn"): self.cancel_btn.setEnabled(True)
        else:
            print("Background operations finished. Closing application.")
            event.accept()