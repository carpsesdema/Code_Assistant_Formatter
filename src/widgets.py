# src/widgets.py

"""
Custom Qt Widgets used in the Code Helper application, including the
CodeEditor with line numbers and the DiffDialog.
"""

import difflib
from PyQt6.QtWidgets import (
    QPlainTextEdit, QWidget, QTextEdit, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextBrowser
)
from PyQt6.QtGui import QFont, QPainter, QColor, QTextCharFormat
from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal
from .constants import COLOR_LINE_NUM_BG, COLOR_LINE_NUM_FG, COLOR_HIGHLIGHT_BG

# --- Line Number Area ---
class LineNumberArea(QWidget):
    def __init__(self, editor: 'CodeEditor'):
        super().__init__(editor); self.codeEditor = editor
    def sizeHint(self) -> QSize: return QSize(self.codeEditor.lineNumberAreaWidth(), 0)
    def paintEvent(self, event): self.codeEditor.lineNumberAreaPaintEvent(event)

# --- Code Editor with Line Numbers ---
class CodeEditor(QPlainTextEdit):
    def __init__(self, font: QFont, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFont(font)
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def lineNumberAreaWidth(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def updateLineNumberAreaWidth(self, newBlockCount: int = 0):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect: QRect, dy: int):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()): self.updateLineNumberAreaWidth()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        """Paints the line numbers within the visible area."""
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor(COLOR_LINE_NUM_BG))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        font_metrics = self.fontMetrics()
        content_offset_y = int(self.contentOffset().y()) # Ensure offset is int
        paint_rect_top = event.rect().top()
        paint_rect_bottom = event.rect().bottom()
        area_width = self.lineNumberArea.width() # This should be int

        while block.isValid() and block.isVisible():
            block_rect = self.blockBoundingGeometry(block).translated(0, content_offset_y)
            block_top = int(block_rect.top())
            block_bottom = int(block_rect.bottom())

            if block_top <= paint_rect_bottom and block_bottom >= paint_rect_top:
                number = str(blockNumber + 1)
                painter.setPen(QColor(COLOR_LINE_NUM_FG))

                # Calculate vertical position - use integer division //
                paint_y_float = block_top + (block_rect.height() - font_metrics.height()) / 2.0 + font_metrics.ascent()

                # --- CHANGE: Explicitly cast all relevant arguments to int ---
                draw_x = 0
                draw_y = int(paint_y_float) # Cast y-coord
                draw_width = int(area_width - 5) # Cast width
                draw_height = int(font_metrics.height()) # Cast height
                draw_flags = int(Qt.AlignmentFlag.AlignRight) # Cast flags (usually safe but explicit)
                # --- END CHANGE ---

                # Draw the number using guaranteed integer arguments
                painter.drawText(
                    draw_x,
                    draw_y,
                    draw_width,
                    draw_height,
                    draw_flags,
                    number,
                )

            if block_top > paint_rect_bottom:
                break

            block = block.next()
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = [];
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor(COLOR_HIGHLIGHT_BG)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor(); selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def setFont(self, font: QFont):
        super().setFont(font)
        if hasattr(self, "lineNumberArea"):
            self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
            self.updateLineNumberAreaWidth()
            self.lineNumberArea.update()

# --- Side-by-Side Diff Dialog ---
# (DiffDialog class remains unchanged)
class DiffDialog(QDialog):
    def __init__(self, original_lines: list[str], new_lines: list[str],
                 fromdesc: str = "Original", todesc: str = "New",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Side-by-Side Diff Preview"); self.resize(1000, 700)
        layout = QVBoxLayout(self); layout.setContentsMargins(5, 5, 5, 5)
        html_diff = difflib.HtmlDiff(wrapcolumn=80, tabsize=4).make_file(
            original_lines, new_lines, fromdesc=fromdesc, todesc=todesc, context=True, numlines=3
        )
        self.diff_browser = QTextBrowser(); self.diff_browser.setOpenExternalLinks(True)
        css = """<style>
            body { background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas, Courier, monospace; }
            table.diff { border-collapse: collapse; width: 100%; font-size: 9pt; }
            td.diff_header { text-align: center; background-color: #333; padding: 3px; font-weight: bold; border: 1px solid #555; }
            td.diff_next { background-color: #2a2a2b; border: 1px solid #444; padding: 1px 3px; }
            td.diff_add { background-color: #043904; border: 1px solid #444; padding: 1px 3px; }
            td.diff_chg { background-color: #043939; border: 1px solid #444; padding: 1px 3px; }
            td.diff_sub { background-color: #3f0404; border: 1px solid #444; padding: 1px 3px; }
            thead th { background-color: #333; padding: 5px; text-align: center; border: 1px solid #555; font-weight: bold; }
            a { color: #3794ff; text-decoration: none; } a:hover { text-decoration: underline; }
            td pre { white-space: pre-wrap; word-wrap: break-word; margin: 0; }
        </style>"""
        self.diff_browser.setHtml(css + html_diff); layout.addWidget(self.diff_browser)
        button_box = QHBoxLayout(); close_button = QPushButton("Close"); close_button.setDefault(True)
        close_button.clicked.connect(self.accept); button_box.addStretch(); button_box.addWidget(close_button)
        layout.addLayout(button_box)