

"""
Utilities for parsing and analyzing Python code using the Abstract Syntax Tree (AST).
(No internal project imports needed here)
"""

import ast
import traceback

class FindFunctionOrClass(ast.NodeVisitor):
    """
    An AST visitor to find the first FunctionDef, AsyncFunctionDef, or ClassDef node
    matching a given name at the top level or directly within the parsed code.

    Attributes:
        target_name (str): The name of the function or class to find.
        node (ast.AST | None): The found AST node, or None if not found.
        found (bool): Flag indicating if the target node has been found.
    """
    def __init__(self, target_name: str):
        """
        Initializes the visitor.

        Args:
            target_name: The name of the function or class definition to search for.
        """
        super().__init__()
        self.target_name = target_name
        self.node: ast.AST | None = None
        self.found = False

    def _visit_definition(self, node: ast.AST, node_type: str):
        """Helper to process FunctionDef, AsyncFunctionDef, and ClassDef nodes."""
        # Only consider the node if we haven't found our target yet
        # and if the node's name matches the target name.
        if not self.found and hasattr(node, 'name') and node.name == self.target_name:
            self.node = node
            self.found = True
            # Debug print (optional)
            # print(f"AST Found {node_type}: {node.name} (Lines: {node.lineno}-{node.end_lineno})")

        # We only want the *first* match at the top level(s) visited.
        # If we found it, we don't need to visit children of this node seeking
        # nested definitions of the *same* name. However, we DO need to
        # continue visiting *siblings* of this node or nodes encountered
        # before this one if the target wasn't found yet.
        # The `self.found` flag prevents further assignment to `self.node`.
        # We still call generic_visit *unless* found to check other branches.
        if not self.found:
            self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visits Function Definition nodes."""
        self._visit_definition(node, "Function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visits Asynchronous Function Definition nodes."""
        self._visit_definition(node, "Async Function")

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visits Class Definition nodes."""
        self._visit_definition(node, "Class")

def find_ast_node(code_string: str, target_name: str) -> tuple[ast.AST | None, str | None]:
    """
    Parses Python code and uses the FindFunctionOrClass visitor to find the
    first top-level AST node (FunctionDef, AsyncFunctionDef, or ClassDef)
    matching the target name.

    Args:
        code_string: The Python code to parse as a string.
        target_name: The name of the function or class to find.

    Returns:
        A tuple containing:
        - The found ast.AST node, or None if not found or if a parsing error occurred.
        - An error message string if parsing failed, otherwise None.
    """
    node: ast.AST | None = None
    error_message: str | None = None

    try:
        # Attempt to parse the code string into an AST
        tree = ast.parse(code_string)

        # Create an instance of the visitor
        visitor = FindFunctionOrClass(target_name)

        # Traverse the AST using the visitor
        visitor.visit(tree)

        # Retrieve the found node from the visitor
        node = visitor.node

    except SyntaxError as e:
        # Handle syntax errors during parsing
        error_message = f"AST Parsing Syntax Error: {e}"
        print(error_message)
        node = None # Ensure node is None on error
    except Exception as e:
        # Handle other unexpected errors during AST processing
        error_message = f"Unexpected AST processing error: {e}"
        print(error_message)
        traceback.print_exc() # Print full traceback for debugging
        node = None # Ensure node is None on error

    return node, error_message