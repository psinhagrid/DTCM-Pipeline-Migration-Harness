from pathlib import Path

from .utils.hql_utils import parse_file


def parse_hql_tool(path: Path) -> dict:
    """
    Parse a single .hql file — syntax validation + extraction.
    Delegates to utils.parse_file (sqlfluff + regex).
    Returns the findings dict: tables, columns, UDFs, complexity signals, syntax errors.
    """
    return parse_file(path)
