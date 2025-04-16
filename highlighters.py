

import re
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
# Use direct import for flat structure
from constants import COLOR_DIFF_ADDED_BG, COLOR_DIFF_REMOVED_BG # Import colors

class PythonHighlighter(QSyntaxHighlighter):
    """
    A syntax highlighter for Python code, designed for dark themes.
    Handles keywords, builtins, numbers, strings (including multiline),
    comments, decorators, function/class names, and self/cls.
    """
    def __init__(self, document):
        super().__init__(document)
        self.highlightingRules = []

        # --- Text Format Definitions ---
        # Keyword format (e.g., def, class, if, for)
        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#569CD6")) # Blue
        # keywordFormat.setFontWeight(QFont.Weight.Bold) # Optional: Bold keywords

        # Builtin functions/types format (e.g., print, str, list)
        builtinFormat = QTextCharFormat()
        builtinFormat.setForeground(QColor("#4EC9B0")) # Teal

        # Comment format (e.g., # This is a comment)
        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#6A9955")) # Green
        commentFormat.setFontItalic(True) # Optional: Italic comments

        # String format (single, double, f-strings, etc.)
        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) # Orange

        # Number format (int, float, hex, binary)
        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) # Light green/yellow

        # Decorator format (e.g., @property)
        decoratorFormat = QTextCharFormat()
        decoratorFormat.setForeground(QColor("#C586C0")) # Purple

        # Function and Class definition name format
        funcClassFormat = QTextCharFormat()
        funcClassFormat.setForeground(QColor("#DCDCAA")) # Yellowish
        # funcClassFormat.setFontWeight(QFont.Weight.Bold) # Optional: Bold names

        # self/cls parameter format
        selfFormat = QTextCharFormat()
        selfFormat.setForeground(QColor("#9CDCFE")) # Light blue

        # --- Regex Rules ---
        # Keywords
        keywords = [
            "and", "as", "assert", "async", "await", "break", "class", "continue",
            "def", "del", "elif", "else", "except", "False", "finally", "for", "from",
            "global", "if", "import", "in", "is", "lambda", "None", "nonlocal", "not",
            "or", "pass", "raise", "return", "True", "try", "while", "with", "yield",
        ]
        for word in keywords:
            pattern = r"\b" + word + r"\b"
            self.highlightingRules.append((re.compile(pattern), keywordFormat))

        # Builtins (common ones)
        builtins = [
            "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
            "callable", "chr", "classmethod", "compile", "complex", "delattr", "dict",
            "dir", "divmod", "enumerate", "eval", "exec", "filter", "float", "format",
            "frozenset", "getattr", "globals", "hasattr", "hash", "help", "hex", "id",
            "input", "int", "isinstance", "issubclass", "iter", "len", "list", "locals",
            "map", "max", "memoryview", "min", "next", "object", "oct", "open", "ord",
            "pow", "print", "property", "range", "repr", "reversed", "round", "set",
            "setattr", "slice", "sorted", "staticmethod", "str", "sum", "super", "tuple",
            "type", "vars", "zip", "__import__",
        ]
        for word in builtins:
            pattern = r"\b" + word + r"\b"
            self.highlightingRules.append((re.compile(pattern), builtinFormat))

        # Single-line comments
        self.highlightingRules.append((re.compile(r"#.*"), commentFormat))

        # Strings (handle prefixes f, r, b, u and combinations)
        # Matches '...', "...", f'...', r"...", br'...', etc.
        # Basic single/double quotes
        self.highlightingRules.append((re.compile(r"'(?:[^'\\]|\\.)*'"), stringFormat))
        self.highlightingRules.append((re.compile(r'"(?:[^"\\]|\\.)*"'), stringFormat))
        # With prefixes (optional group for prefix, required group for quotes)
        self.highlightingRules.append(
            (re.compile(r"[fFrRbBuU]{1,2}'(?:[^'\\]|\\.)*'"), stringFormat)
        )
        self.highlightingRules.append(
            (re.compile(r'[fFrRbBuU]{1,2}"(?:[^"\\]|\\.)*"'), stringFormat)
        )
        # Note: This doesn't separately color the prefix, which is simpler.

        # Numbers (order matters: floats before ints to avoid partial matches)
        # Floats (including scientific notation like 1e3, .5, 1.)
        self.highlightingRules.append(
            (re.compile(r"\b\d+\.\d*([eE][-+]?\d+)?\b"), numberFormat)
        )
        self.highlightingRules.append(
            (re.compile(r"\.\d+([eE][-+]?\d+)?\b"), numberFormat)
        )
        self.highlightingRules.append(
            (re.compile(r"\b\d+[eE][-+]?\d+\b"), numberFormat)
        )
         # Integers (decimal, hex, octal, binary) after floats
        self.highlightingRules.append(
            (re.compile(r"\b0[xX][0-9a-fA-F]+\b"), numberFormat)
        )
        self.highlightingRules.append(
            (re.compile(r"\b0[oO][0-7]+\b"), numberFormat)
        )
        self.highlightingRules.append(
            (re.compile(r"\b0[bB][01]+\b"), numberFormat)
        )
        self.highlightingRules.append(
            (re.compile(r"\b\d+\b"), numberFormat) # Plain integers last
        )


        # Decorators (@ followed by identifier)
        self.highlightingRules.append((re.compile(r"@\w+"), decoratorFormat))

        # Function and class definition names (using capture group 1)
        self.highlightingRules.append(
            (re.compile(r"\bdef\s+([A-Za-z_]\w*)"), funcClassFormat, 1) # Group 1 is the name
        )
        self.highlightingRules.append(
            (re.compile(r"\bclass\s+([A-Za-z_]\w*)"), funcClassFormat, 1) # Group 1 is the name
        )

        # self/cls parameters
        self.highlightingRules.append((re.compile(r"\bself\b"), selfFormat))
        self.highlightingRules.append((re.compile(r"\bcls\b"), selfFormat))

        # --- Multi-line String Handling ---
        self.multiLineStringFormat = stringFormat
        # Start patterns for """ and '''
        self.triSingleQuoteStart = re.compile(r"'''")
        self.triDoubleQuoteStart = re.compile(r'"""')
        # End patterns (kept simple, state machine handles context)
        self.triSingleQuoteEnd = re.compile(r"'''")
        self.triDoubleQuoteEnd = re.compile(r'"""')


    def highlightBlock(self, text: str):
        """Highlights a single block of text (typically one line)."""
        # --- Apply Single-Line Rules ---
        # Apply rules that don't span lines first
        for rule_tuple in self.highlightingRules:
            pattern = rule_tuple[0]
            fmt = rule_tuple[1]
            # Check if a specific capture group should be formatted
            capture_group_index = rule_tuple[2] if len(rule_tuple) > 2 else 0

            # Use finditer to catch all occurrences in the line
            for match in pattern.finditer(text):
                try:
                    # Get the start and end positions of the match (or capture group)
                    start, end = match.span(capture_group_index)

                    # Apply the format for the calculated span
                    # Check for valid span to avoid potential errors
                    if 0 <= start < end <= len(text):
                        self.setFormat(start, end - start, fmt)
                    # else: # Optional debug for invalid spans
                        # print(f"Debug: Invalid span ({start}, {end}) for pattern '{pattern.pattern}' in text: '{text[:50]}...'")
                except IndexError:
                    # This can happen if the capture group doesn't exist in a specific match
                    # (e.g., regex allows optional parts) - safely ignore these cases.
                    # print(f"Debug: Capture group {capture_group_index} not found for pattern '{pattern.pattern}'")
                    pass


        # --- Multi-line String Highlighting Logic (State Machine) ---
        # State: 0 = Normal Code, 1 = Inside ''', 2 = Inside """
        self.setCurrentBlockState(0)
        block_state = self.previousBlockState() # Get state from the end of previous block
        search_offset = 0 # Where to start searching for delimiters in the current block

        # --- Handle Continuation from Previous Block ---
        if block_state == 1: # Previous block ended inside '''
            end_match = self.triSingleQuoteEnd.search(text)
            if end_match:
                # Found the end delimiter in this block
                end_pos = end_match.end()
                self.setFormat(0, end_pos, self.multiLineStringFormat) # Format up to the end
                search_offset = end_pos # Start searching for new strings after this one
                # State returns to 0 (Normal Code) implicitly by not setting it
            else:
                # String continues to the next block
                self.setCurrentBlockState(1) # Maintain state 1
                self.setFormat(0, len(text), self.multiLineStringFormat) # Format whole block
                return # Nothing else to do in this block

        elif block_state == 2: # Previous block ended inside """
            end_match = self.triDoubleQuoteEnd.search(text)
            if end_match:
                # Found the end delimiter in this block
                end_pos = end_match.end()
                self.setFormat(0, end_pos, self.multiLineStringFormat) # Format up to the end
                search_offset = end_pos # Start searching for new strings after this one
                # State returns to 0 (Normal Code) implicitly
            else:
                # String continues to the next block
                self.setCurrentBlockState(2) # Maintain state 2
                self.setFormat(0, len(text), self.multiLineStringFormat) # Format whole block
                return # Nothing else to do in this block

        # --- Search for New Multiline Strings Starting in This Block ---
        # This loop finds the *next* starting delimiter (''' or """)
        while search_offset < len(text):
            # Find the nearest start delimiter from the current offset
            start_single_match = self.triSingleQuoteStart.search(text, search_offset)
            start_double_match = self.triDoubleQuoteStart.search(text, search_offset)

            # Determine which delimiter comes first (if any)
            if start_single_match and start_double_match:
                if start_single_match.start() < start_double_match.start():
                    start_match = start_single_match
                    current_state = 1 # Entering ''' state
                    delimiter_end_pattern = self.triSingleQuoteEnd
                else:
                    start_match = start_double_match
                    current_state = 2 # Entering """ state
                    delimiter_end_pattern = self.triDoubleQuoteEnd
            elif start_single_match:
                start_match = start_single_match
                current_state = 1
                delimiter_end_pattern = self.triSingleQuoteEnd
            elif start_double_match:
                start_match = start_double_match
                current_state = 2
                delimiter_end_pattern = self.triDoubleQuoteEnd
            else:
                # No more multiline string starts found in the remainder of the block
                break

            string_start_index = start_match.start()

            # Find the corresponding end delimiter *after* the start delimiter
            # Important: Start search for end *after* the start delimiter begins
            end_match = delimiter_end_pattern.search(text, start_match.end())

            if end_match:
                # Multiline string starts and ends within this block
                string_end_index = end_match.end()
                self.setFormat(string_start_index, string_end_index - string_start_index, self.multiLineStringFormat)
                # Continue searching for the *next* multiline string start after this one ends
                search_offset = string_end_index
            else:
                # Multiline string starts here but continues into the next block
                self.setCurrentBlockState(current_state) # Set state for the next block
                # Format from the start delimiter to the end of the current block
                self.setFormat(string_start_index, len(text) - string_start_index, self.multiLineStringFormat)
                # Since the string continues, we are done processing this block
                break # Exit the while loop


class DiffHighlighter(QSyntaxHighlighter):
    """
    A simple syntax highlighter for unified diff format output.
    Highlights lines starting with '+', '-', or '@@'.
    """
    def __init__(self, document):
        super().__init__(document)

        # Format for added lines (+)
        self.addedFormat = QTextCharFormat()
        # Use background color defined in constants
        self.addedFormat.setBackground(QColor(COLOR_DIFF_ADDED_BG))

        # Format for removed lines (-)
        self.removedFormat = QTextCharFormat()
        # Use background color defined in constants
        self.removedFormat.setBackground(QColor(COLOR_DIFF_REMOVED_BG))

        # Format for context/info lines (@@)
        self.infoFormat = QTextCharFormat()
        self.infoFormat.setForeground(QColor("#569CD6")) # Blue, similar to keywords
        self.infoFormat.setFontWeight(QFont.Weight.Bold) # Make context lines bold

    def highlightBlock(self, text: str):
        """Highlights a single block (line) of diff text."""
        # Check the start of the line for diff markers
        # Use startswith for efficiency
        if text.startswith("+") and not text.startswith("+++"):
            # Apply added format to the entire line
            self.setFormat(0, len(text), self.addedFormat)
        elif text.startswith("-") and not text.startswith("---"):
            # Apply removed format to the entire line
            self.setFormat(0, len(text), self.removedFormat)
        elif text.startswith("@@"):
            # Apply info format to the entire line
            self.setFormat(0, len(text), self.infoFormat)
        # Lines without these prefixes (context lines) will retain the default format
# --- END OF FILE highlighters.txt ---