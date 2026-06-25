from .utils.smoke_tests import run_all_smoke_tests

def run_smoke_tests_tool(pipeline: str, conversion: dict, reconcile: dict) -> dict:
    """
    Run the full smoke test suite.
    Returns tests list, overall status, passed/total counts, and score.
    """
    return run_all_smoke_tests(pipeline, conversion, reconcile)
