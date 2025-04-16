
"""
Custom Qt Widgets used in the Code Helper application, including the
CodeEditor with line numbers and the DiffDialog.
"""

import difflib
from PyQt6.QtWidgets import (
    QPlainTextEdit, QWidget, QTextEdit, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextBrowser
)
from PyQt6.QtGui import QFont, QPainter, QColor, QTextCharFormat, QPalette
from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal
from .constants import COLOR_LINE_NUM_BG, COLOR_LINE_NUM_FG, COLOR_HIGHLIGHT_BG # Import colors

# --- Line Number Area for Code Editor ---
class LineNumberArea(QWidget):
    """Widget that displays line numbers alongside a CodeEditor."""
    def __init__(self, editor: 'CodeEditor'):
        """Initializes the line number area."""
        super().__init__(editor)
        self.codeEditor = editor
        # Set background color explicitly (can be overridden by stylesheet)
        # self.setAutoFillBackground(True)
        # palette = self.palette()
        # palette.setColor(QPalette.ColorRole.Window, QColor(COLOR_LINE_NUM_BG))
        # self.setPalette(palette)

    def sizeHint(self) -> QSize:
        """Returns the preferred size hint based on editor's calculation."""
        # Width is determined by the editor, height is flexible (0).
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        """Paints the line numbers. Called by the editor."""
        self.codeEditor.lineNumberAreaPaintEvent(event)

# --- Code Editor with Line Numbers ---
class CodeEditor(QPlainTextEdit):
    """
    A QPlainTextEdit subclass that includes a line number area and
    current line highlighting, customized for code display.
    """
    # Signal emitted when the content of the editor is changed by user interaction
    # contentChanged = pyqtSignal()

    def __init__(self, font: QFont, parent: QWidget | None = None):
        """
        Initializes the CodeEditor.

        Args:
            font: The QFont to use for the editor text.
            parent: The parent widget (optional).
        """
        super().__init__(parent)
        self.setFont(font) # Set the initial font

        # Create and setup the line number area widget
        self.lineNumberArea = LineNumberArea(self)

        # Connect signals to slots for updating line numbers and highlighting
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        # self.textChanged.connect(self.contentChanged.emit) # Emit signal on text change

        # Initial setup
        self.updateLineNumberAreaWidth(0) # Calculate initial width
        self.highlightCurrentLine() # Highlight line where cursor starts

        # Configure tab stop distance (e.g., 4 spaces)
        # Use fontMetrics to calculate the width accurately
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)

        # Set line wrap mode (optional, NoWrap is common for code)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def lineNumberAreaWidth(self) -> int:
        """Calculates the required width for the line number area."""
        digits = 1
        # Get the maximum number of lines (blocks)
        max_lines = max(1, self.blockCount())
        # Calculate number of digits needed for the highest line number
        digits = len(str(max_lines))

        # Calculate width based on digit count and font metrics
        # Add some padding for spacing between numbers and text area
        space = 10 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def updateLineNumberAreaWidth(self, newBlockCount: int = 0):
        """Sets the left margin to accommodate the line number area."""
        # The argument newBlockCount isn't strictly needed here but is passed by signal
        margin_width = self.lineNumberAreaWidth()
        self.setViewportMargins(margin_width, 0, 0, 0)

    def updateLineNumberArea(self, rect: QRect, dy: int):
        """Updates the line number area when the editor scrolls or changes."""
        if dy:
            # Scroll the line number area vertically along with the editor
            self.lineNumberArea.scroll(0, dy)
        else:
            # Schedule an update for the specific rectangular area changed
            # Using update() directly is often fine
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        # Recalculate width if the viewport rect itself changes
        # (e.g., vertical scrollbar appears/disappears)
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth()

    def resizeEvent(self, event):
        """Handles resizing of the editor widget."""
        super().resizeEvent(event)
        # Update the geometry of the line number area to fit the new size
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(
            QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )

    def lineNumberAreaPaintEvent(self, event):
        """Paints the line numbers within the visible area."""
        painter = QPainter(self.lineNumberArea)
        # Fill the background of the line number area (respects stylesheets)
        painter.fillRect(event.rect(), QColor(COLOR_LINE_NUM_BG)) # Use constant

        block = self.firstVisibleBlock() # Get the first visible text block
        blockNumber = block.blockNumber() # Get its line number (0-based)
        font_metrics = self.fontMetrics() # Use the editor's font metrics
        content_offset_y = int(self.contentOffset().y()) # Vertical scroll position
        paint_rect_top = event.rect().top()
        paint_rect_bottom = event.rect().bottom()
        area_width = self.lineNumberArea.width()

        # Iterate through visible blocks
        while block.isValid() and block.isVisible():
            block_rect = self.blockBoundingGeometry(block).translated(0, content_offset_y)
            block_top = int(block_rect.top())
            block_bottom = int(block_rect.bottom())

            # Check if the block is within the vertical area that needs repainting
            if block_top <= paint_rect_bottom and block_bottom >= paint_rect_top:
                number = str(blockNumber + 1) # Display 1-based line number
                painter.setPen(QColor(COLOR_LINE_NUM_FG)) # Set text color

                # Calculate vertical position to center the number within the block's height
                paint_y = block_top + (block_rect.height() - font_metrics.height()) // 2 + font_metrics.ascent()

                # Draw the number, right-aligned with padding
                painter.drawText(
                    0,                    # x-position (start from left)
                    paint_y,              # y-position (calculated baseline)
                    area_width - 5,       # width available (area width - right padding)
                    font_metrics.height(),# height available
                    Qt.AlignmentFlag.AlignRight, # Alignment
                    number,               # The line number text
                )

            # Optimization: Stop drawing if we've moved past the paint area
            if block_top > paint_rect_bottom:
                break

            block = block.next() # Move to the next block
            blockNumber += 1 # Increment line number

    def highlightCurrentLine(self):
        """Applies a background highlight to the line containing the cursor."""
        extraSelections = []
        # Only highlight if the editor is not read-only and has focus maybe?
        # For simplicity, always highlight if not read-only.
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            # Set background color for the highlight
            lineColor = QColor(COLOR_HIGHLIGHT_BG) # Use constant
            selection.format.setBackground(lineColor)
            # Make the selection span the full width of the editor
            selection.format.setProperty(
                QTextCharFormat.Property.FullWidthSelection, True
            )
            # Set the selection to the current cursor position
            selection.cursor = self.textCursor()
            # Ensure the selection doesn't visually select text (only the line)
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        # Apply the created selection highlight
        self.setExtraSelections(extraSelections)

    # Override setFont to ensure dependent calculations are updated
    def setFont(self, font: QFont):
        """Sets the font for the editor and updates related components."""
        super().setFont(font)
        # Check if lineNumberArea exists yet (might be called during super().__init__)
        if hasattr(self, "lineNumberArea"):
            # Recalculate tab stop distance based on the new font's metrics
            self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
            # Update the width of the line number area
            self.updateLineNumberAreaWidth()
            # Force a repaint of the line numbers to use the new font size implicitly
            self.lineNumberArea.update()


# --- Side-by-Side Diff Dialog ---
class DiffDialog(QDialog):
    """
    A dialog window that displays a side-by-side diff of two text inputs
    using `difflib.HtmlDiff`.
    """
    def __init__(self, original_lines: list[str], new_lines: list[str],
                 fromdesc: str = "Original", todesc: str = "New",
                 parent: QWidget | None = None):
        """
        Initializes the DiffDialog.

        Args:
            original_lines: A list of strings representing the original text.
            new_lines: A list of strings representing the new text.
            fromdesc: Label for the original text side (default: "Original").
            todesc: Label for the new text side (default: "New").
            parent: The parent widget (optional).
        """
        super().__init__(parent)
        self.setWindowTitle("Side-by-Side Diff Preview")
        self.resize(1000, 700) # Slightly larger default size

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5) # Reduce margins slightly

        # Generate the HTML diff using difflib
        # context=True shows lines around changes, numlines controls how many
        html_diff_generator = difflib.HtmlDiff(wrapcolumn=80, tabsize=4)
        html_diff = html_diff_generator.make_file(
            original_lines,
            new_lines,
            fromdesc=fromdesc,
            todesc=todesc,
            context=True, # Show context lines
            numlines=3,   # Number of context lines
        )

        # Use QTextBrowser to render the HTML
        self.diff_browser = QTextBrowser()
        self.diff_browser.setOpenExternalLinks(True) # Open links externally if any

        # Basic CSS for styling the HTML diff table for a dark theme
        # Matches common diff tool colors.
        css = """
        <style>
            body { background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas, Courier, monospace; }
            table.diff { border-collapse: collapse; width: 100%; font-size: 9pt; }
            td.diff_header { text-align: center; background-color: #333; padding: 3px; font-weight: bold; border: 1px solid #555; }
            td.diff_next { background-color: #2a2a2b; border: 1px solid #444; padding: 1px 3px; } /* Line numbers etc */
            td.diff_add { background-color: #043904; border: 1px solid #444; padding: 1px 3px; } /* Added content */
            td.diff_chg { background-color: #043939; border: 1px solid #444; padding: 1px 3px; } /* Changed content */
            td.diff_sub { background-color: #3f0404; border: 1px solid #444; padding: 1px 3px; } /* Removed content */
            thead th { /* Styles for the main headers (fromdesc, todesc) if needed */
                background-color: #333; padding: 5px; text-align: center;
                border: 1px solid #555; font-weight: bold;
            }
            a { color: #3794ff; text-decoration: none; } /* Link color */
            a:hover { text-decoration: underline; }
            /* Ensure preformatted text within cells wraps correctly */
            td pre { white-space: pre-wrap; word-wrap: break-word; margin: 0; }
        </style>
        """
        # Combine CSS and HTML and set it in the browser
        self.diff_browser.setHtml(css + html_diff)
        layout.addWidget(self.diff_browser) # Add browser to layout

        # --- Bottom Button Box ---
        button_box = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.setDefault(True) # Make Close the default button (Enter key)
        close_button.clicked.connect(self.accept) # Close dialog on click

        button_box.addStretch() # Push button to the right
        button_box.addWidget(close_button)
        # button_box.addStretch() # Uncomment for centered button

        layout.addLayout(button_box) # Add button layout