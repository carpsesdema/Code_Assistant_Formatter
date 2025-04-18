import subprocess
import sys
import traceback
import os  # Needed for os.linesep and Windows console flags

# Import constants from the constants module (Direct Import)
from constants import RUFF_TIMEOUT

def _remove_trailing_semicolons(code_string: str) -> str:
    """
    Removes trailing semicolons from lines of code.

    Specifically targets semicolons that are the last non-whitespace character
    on a line. Intended to run *before* the main formatter.

    Args:
        code_string: The code string potentially containing trailing semicolons.

    Returns:
        The code string with trailing semicolons removed.
    """
    # Split the code into individual lines
    lines = code_string.splitlines()
    processed_lines = []
    for line in lines:
        # Remove whitespace from the right side of the line
        stripped_line = line.rstrip()
        # Check if the stripped line actually ends with a semicolon
        if stripped_line.endswith(';'):
            # If it ends with a semicolon, remove it and any trailing whitespace
            processed_lines.append(stripped_line[:-1].rstrip())
        else:
            # If it doesn't end with a semicolon, add the original line back
            processed_lines.append(line)

    # Join the processed lines back together using newline characters.
    return "\n".join(processed_lines)


def format_code_with_ruff(code_string: str) -> tuple[str, str | None]:
    """
    Formats a Python code string by first removing trailing semicolons and then
    using the ruff command line tool ('ruff format') via subprocess.

    Handles finding the Python executable, running the preliminary cleanup,
    running ruff, capturing output, and managing errors like timeouts or ruff failures.

    Args:
        code_string: The Python code to format as a single string.

    Returns:
        A tuple containing:
        - The fully formatted code string (or the intermediate cleaned string if Ruff failed).
        - An error message string if formatting failed, otherwise None.
    """
    # --- Step 1: Initial Cleanup ---
    cleaned_input_code = code_string.strip()

    # --- Step 2: Preliminary Semicolon Removal ---
    try:
        semicolon_cleaned_code = _remove_trailing_semicolons(cleaned_input_code)
    except Exception as cleanup_e:
        error_message = f"Error during preliminary semicolon removal: {cleanup_e}"
        print(error_message)
        traceback.print_exc()
        return cleaned_input_code, error_message

    # Initialize defaults
    final_code = semicolon_cleaned_code
    error_message = None

    try:
        # --- Step 3: Run Ruff Formatter ---
        command = [sys.executable, "-m", "ruff", "format", "-"]

        # On Windows, prevent a new console window from popping up
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW

        process = subprocess.run(
            command,
            input=semicolon_cleaned_code,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            timeout=RUFF_TIMEOUT,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        # Check exit code
        if process.returncode != 0:
            stderr_output = process.stderr.strip() if process.stderr else "No stderr output."
            error_message = f"Ruff formatting failed (exit code {process.returncode}):\n{stderr_output}"
            print(error_message)
            return semicolon_cleaned_code, error_message

        # On warnings in stderr, we log but don't treat as failure
        if process.stderr and process.stderr.strip():
            print(f"Ruff formatting warnings:\n{process.stderr.strip()}")

        final_code = process.stdout
        error_message = None

    except subprocess.TimeoutExpired:
        error_message = f"Ruff formatting timed out after {RUFF_TIMEOUT} seconds."
        print(error_message)
        return semicolon_cleaned_code, error_message
    except FileNotFoundError:
        error_message = (
            f"Ruff command failed. Is ruff installed in the Python environment "
            f"located at '{sys.executable}' and accessible in the system PATH?"
        )
        print(error_message)
        return semicolon_cleaned_code, error_message
    except Exception as e:
        error_message = f"An unexpected error occurred while running ruff: {e}"
        print(error_message)
        traceback.print_exc()
        return semicolon_cleaned_code, error_message

    return final_code, error_message
