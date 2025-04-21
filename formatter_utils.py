# --- formatter_utils.py ---

import subprocess
import sys
import traceback
import os
import textwrap # Added for indentation normalization

# Import constants from the constants module (Direct Import)
from constants import BLACK_TIMEOUT # Use BLACK_TIMEOUT now

def clean_chat_paste(code_string: str) -> str:
    """
    Cleans common artifacts from code pasted from chat or web sources.
    - Replaces non-breaking spaces with regular spaces.
    - Replaces various "smart" quotes with standard ASCII quotes.
    - Normalizes line endings to Unix-style (\n).
    - Strips leading/trailing whitespace.

    Args:
        code_string: The potentially messy code string.

    Returns:
        The cleaned code string.
    """
    if not isinstance(code_string, str):
        # Handle potential non-string input gracefully
        return ""

    try:
        # Replace non-breaking space (U+00A0) with standard space
        cleaned = code_string.replace('\xa0', ' ')

        # Replace common "smart" quotes with standard ASCII quotes
        cleaned = cleaned.replace('“', '"').replace('”', '"') # Double quotes
        cleaned = cleaned.replace("‘", "'").replace("’", "'") # Single quotes

        # Normalize line endings: CR LF -> LF, CR -> LF
        cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')

        # Strip leading/trailing whitespace from the entire block
        cleaned = cleaned.strip()

        return cleaned
    except Exception as e:
        print(f"Error during chat paste cleaning: {e}")
        # Return the original string if cleaning fails unexpectedly
        return code_string


def normalize_indentation(code_string: str, indent_width: int = 4) -> str:
    """
    Normalizes indentation in a code block:
    - Removes common leading indentation using textwrap.dedent.
    - Converts remaining tabs to spaces using the specified width.

    Args:
        code_string: The code string with potentially inconsistent indentation.
        indent_width: The number of spaces to use for each tab/indent level.

    Returns:
        The code string with normalized indentation.
    """
    if not isinstance(code_string, str):
        return ""

    try:
        # Dedent removes common leading whitespace from all lines
        # It's quite robust against mixed tabs/spaces in the leading indent
        dedented_code = textwrap.dedent(code_string)

        # Replace any remaining tabs with the specified number of spaces
        space_normalized_code = dedented_code.replace("\t", " " * indent_width)

        return space_normalized_code
    except Exception as e:
        print(f"Error during indentation normalization: {e}")
        # Return the original string if normalization fails
        return code_string

def preprocess_and_format_with_black(code_string: str) -> tuple[str, str | None]:
    """
    Preprocesses and formats a Python code string using Black.

    Preprocessing steps:
    1. `clean_chat_paste`: Removes chat artifacts (NBSP, smart quotes, line endings).
    2. `normalize_indentation`: Dedents and converts tabs to spaces.

    Formatting step:
    - Uses the 'black' command-line tool via subprocess.

    Args:
        code_string: The raw Python code to preprocess and format.

    Returns:
        A tuple containing:
        - The preprocessed and Black-formatted code string. If Black fails,
          returns the code after preprocessing. If preprocessing fails,
          returns the original code.
        - An error message string if any step failed, otherwise None.
    """
    original_code = code_string # Keep original for fallback
    processed_code = ""
    error_message = None

    # --- Step 1: Clean Chat Artifacts ---
    try:
        cleaned_code = clean_chat_paste(code_string)
        processed_code = cleaned_code # Update progress
    except Exception as cleanup_e:
        error_message = f"Error during chat artifact cleaning: {cleanup_e}"
        print(error_message)
        traceback.print_exc()
        return original_code, error_message # Return original on cleaning error

    # --- Step 2: Normalize Indentation ---
    try:
        normalized_code = normalize_indentation(cleaned_code)
        processed_code = normalized_code # Update progress
    except Exception as norm_e:
        error_message = f"Error during indentation normalization: {norm_e}"
        print(error_message)
        traceback.print_exc()
        # Return the *cleaned* code if normalization failed
        return cleaned_code, error_message

    # If pre-processing resulted in empty code, no need to call Black
    if not processed_code.strip():
        return processed_code, None # Return empty string, no error

    # --- Step 3: Run Black Formatter ---
    try:
        command = [sys.executable, "-m", "black", "-", "--quiet"]

        # Windows specific flags to prevent console window popup
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW

        process = subprocess.run(
            command,
            input=processed_code, # Pass the preprocessed code to Black
            capture_output=True,
            text=True,
            check=False, # Don't raise exception on non-zero exit code, handle manually
            encoding="utf-8",
            timeout=BLACK_TIMEOUT,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        # Check Black's exit code
        if process.returncode != 0:
            stderr_output = process.stderr.strip() if process.stderr else "No stderr output."
            # Black often puts syntax errors or other issues in stderr
            error_message = f"Black formatting failed (exit code {process.returncode}):\n{stderr_output}"
            print(error_message)
            # Return the *preprocessed* code when Black fails, along with the error
            return processed_code, error_message
        else:
            # Black succeeded
            final_code = process.stdout
            error_message = None
            # Check for potential warnings even on success (less common with --quiet)
            if process.stderr and process.stderr.strip():
                 print(f"Black formatting warnings:\n{process.stderr.strip()}")
            return final_code, error_message

    except subprocess.TimeoutExpired:
        error_message = f"Black formatting timed out after {BLACK_TIMEOUT} seconds."
        print(error_message)
        # Return the preprocessed code if Black times out
        return processed_code, error_message
    except FileNotFoundError:
        error_message = (
            f"Black command failed. Is 'black' installed in the Python environment "
            f"located at '{sys.executable}' and accessible in the system PATH?"
        )
        print(error_message)
        # Return the preprocessed code if Black is not found
        return processed_code, error_message
    except Exception as e:
        error_message = f"An unexpected error occurred while running Black: {e}"
        print(error_message)
        traceback.print_exc()
        # Return the preprocessed code on unexpected errors
        return processed_code, error_message