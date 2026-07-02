from agents.deploy_agent.tools_impl.utils.smoke_tests import run_all_smoke_tests

def run_smoke_tests_tool(pipeline: str, conversion: dict, reconcile: dict) -> dict:
    """
    Run the full smoke test suite.
    Returns tests list, overall status, passed/total counts, and score.
    """
    try:
        result = run_all_smoke_tests(pipeline, conversion, reconcile)
        result.setdefault("overall", "FAILED")
        result.setdefault("tests", [])
        result.setdefault("passed", 0)
        result.setdefault("failed", 0)
        result.setdefault("warning", 0)
        result.setdefault("total", 0)
        result.setdefault("score", 0)
        return result
    except Exception as e:
        return {
            "overall": "FAILED",
            "tests": [],
            "passed": 0,
            "failed": 1,
            "warning": 0,
            "total": 1,
            "score": 0,
            "error": str(e),
        }
