"""
Utilities for interacting with the Ruff code formatter.
"""

import subprocess
import sys
import traceback

# Import constants from the constants module
from .constants import RUFF_TIMEOUT

def format_code_with_ruff(code_string: str) -> tuple[str, str | None]:
    """
    Formats a Python code string using the ruff command line tool via subprocess.

    Handles finding the Python executable, running ruff, capturing output,
    and managing errors like timeouts or ruff failures.

    Args:
        code_string: The Python code to format as a single string.

    Returns:
        A tuple containing:
        - The formatted code string (or the original string if formatting failed).
        - An error message string if formatting failed, otherwise None.
    """
    formatted_code = code_string # Default to original if error occurs
    error_message = None

    try:
        # Construct the command using sys.executable to ensure the correct Python env
        command = [sys.executable, "-m", "ruff", "format", "-"]

        # Run Ruff as a subprocess
        process = subprocess.run(
            command,
            input=code_string, # Pass the code string as input via stdin
            capture_output=True, # Capture stdout and stderr
            text=True, # Decode output as text using default encoding (usually utf-8)
            check=False, # Don't raise CalledProcessError automatically, check manually
            encoding="utf-8", # Explicitly specify UTF-8 encoding
            timeout=RUFF_TIMEOUT # Set a timeout to prevent hangs
        )

        # Check Ruff's exit code
        if process.returncode != 0:
            # Formatting failed
            stderr_output = process.stderr.strip() if process.stderr else "No stderr output."
            error_message = f"Ruff formatting failed (exit code {process.returncode}):\n{stderr_output}"
            print(error_message) # Log the error
            # Return original code and the error message
            return code_string, error_message

        # Check stderr even on success (might contain warnings)
        if process.stderr and process.stderr.strip():
            # Log warnings from stderr but don't treat as failure
            print(f"Ruff formatting warnings:\n{process.stderr.strip()}")
            # Optionally, these warnings could be returned or displayed to the user
            # depending on desired behavior. For now, just log them.

        # If successful, return the formatted code from stdout
        formatted_code = process.stdout
        error_message = None # Explicitly set error message to None on success

    except subprocess.TimeoutExpired:
        error_message = f"Ruff formatting timed out after {RUFF_TIMEOUT} seconds."
        print(error_message)
        # Return original code and timeout error message
        return code_string, error_message
    except FileNotFoundError:
        # This typically means 'python -m ruff' could not be run.
        # Check if sys.executable exists, and if ruff is installed in that environment.
        error_message = (f"Ruff command failed. Is ruff installed in the Python environment "
                         f"located at '{sys.executable}' and accessible in the system PATH?")
        print(error_message)
        # This is often a setup issue, consider making it more prominent.
        # Depending on requirements, could raise an exception here.
        return code_string, error_message
    except Exception as e:
        # Catch any other unexpected errors during subprocess execution
        error_message = f"An unexpected error occurred while running ruff: {e}"
        print(error_message)
        traceback.print_exc() # Print full traceback for debugging
        return code_string, error_message

    return formatted_code, error_message