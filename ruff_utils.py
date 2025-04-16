
import subprocess
import sys
import traceback
import os # Needed for os.linesep potentially, though \n is often safer

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
            # If it ends with a semicolon, remove the semicolon and any whitespace
            # that might have preceded it by stripping again.
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
    # Remove leading/trailing whitespace from the entire snippet.
    cleaned_input_code = code_string.strip()

    # --- Step 2: Preliminary Semicolon Removal ---
    # Run the custom semicolon remover *before* calling Ruff.
    try:
        semicolon_cleaned_code = _remove_trailing_semicolons(cleaned_input_code)
    except Exception as cleanup_e:
        # Catch unexpected errors during the custom cleanup phase
        error_message = f"Error during preliminary semicolon removal: {cleanup_e}"
        print(error_message)
        traceback.print_exc()
        # Return the result of the initial strip() and the error
        return cleaned_input_code, error_message

    # Initialize final return values, default to the semicolon-cleaned code if Ruff fails
    final_code = semicolon_cleaned_code
    error_message = None

    try:
        # --- Step 3: Run Ruff Formatter ---
        # Construct the command using sys.executable
        command = [sys.executable, "-m", "ruff", "format", "-"]

        # Run Ruff as a subprocess, passing the semicolon-cleaned code
        process = subprocess.run(
            command,
            input=semicolon_cleaned_code, # Pass the semicolon-cleaned code as input
            capture_output=True,        # Capture stdout and stderr
            text=True,                  # Decode output as text
            check=False,                # Check return code manually
            encoding="utf-8",           # Specify UTF-8 encoding
            timeout=RUFF_TIMEOUT        # Set a timeout
        )

        # Check Ruff's exit code
        if process.returncode != 0:
            # Ruff formatting failed
            stderr_output = process.stderr.strip() if process.stderr else "No stderr output."
            error_message = f"Ruff formatting failed (exit code {process.returncode}):\n{stderr_output}"
            print(error_message) # Log the error
            # Return the semicolon-cleaned code (as Ruff failed on it) and the error message
            return semicolon_cleaned_code, error_message

        # Check stderr even on success (might contain warnings)
        if process.stderr and process.stderr.strip():
            # Log warnings from stderr but don't treat as failure
            print(f"Ruff formatting warnings:\n{process.stderr.strip()}")

        # If Ruff was successful, get the final formatted code from stdout
        final_code = process.stdout
        error_message = None # Explicitly set error message to None on success

    except subprocess.TimeoutExpired:
        error_message = f"Ruff formatting timed out after {RUFF_TIMEOUT} seconds."
        print(error_message)
        # Return the semicolon-cleaned code and timeout error message
        return semicolon_cleaned_code, error_message
    except FileNotFoundError:
        # This typically means 'python -m ruff' could not be run.
        error_message = (f"Ruff command failed. Is ruff installed in the Python environment "
                         f"located at '{sys.executable}' and accessible in the system PATH?")
        print(error_message)
        # Return the semicolon-cleaned code and the error message
        return semicolon_cleaned_code, error_message
    except Exception as e:
        # Catch any other unexpected errors during subprocess execution
        error_message = f"An unexpected error occurred while running ruff: {e}"
        print(error_message)
        traceback.print_exc() # Print full traceback for debugging
        # Return the semicolon-cleaned code and the error message
        return semicolon_cleaned_code, error_message

    # Return the fully formatted code (semicolon clean -> Ruff format) and no error message
    return final_code, error_message
