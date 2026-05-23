from ..utils.hql_utils import compute_score, classify, EFFORT


def classify_complexity_tool(
    tables: set,
    udfs: set,
    has_window: bool,
    cross_db: set,
    has_dyn_part: bool,
    subqueries: int,
    downstream: list,
) -> dict:
    """
    Score and classify pipeline migration complexity.
    Returns score, complexity band, and estimated migration effort.
    """
    score      = compute_score(tables, udfs, has_window, cross_db, has_dyn_part, subqueries, downstream)
    complexity = classify(score)
    return {
        "score":            score,
        "complexity":       complexity,
        "estimated_effort": EFFORT[complexity],
    }
