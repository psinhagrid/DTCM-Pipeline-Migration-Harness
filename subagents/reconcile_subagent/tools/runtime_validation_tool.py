from ..utils.validators import row_count_check, checksum_check, sla_check, consumer_replay_check

def runtime_validation_tool(pipeline: str, complexity: str, similarity: float) -> dict:
    """
    Run all 4 runtime validation checks:
    row_count, checksum, sla_compliance, consumer_replay.
    Returns a dict with all 4 results keyed by check name.
    """
    return {
        "row_count":       row_count_check(pipeline, complexity, similarity),
        "checksum":        checksum_check(pipeline, similarity),
        "sla_compliance":  sla_check(pipeline, complexity),
        "consumer_replay": consumer_replay_check(pipeline, complexity, similarity),
    }
