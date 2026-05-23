"""
Pure parsing utilities for assess_agent.
No async, no I/O side-effects — safe to call via asyncio.to_thread().
"""

import re
from pathlib import Path

from sqlfluff.core import Linter

# ── SQL keywords that look like function calls but aren't ───────────────────
# These are excluded from UDF detection.
SQL_KEYWORDS: set[str] = {
    "partition", "by", "table", "tblproperties", "stored", "as", "if",
    "not", "exists", "select", "from", "where", "join", "on", "and", "or",
    "group", "order", "having", "limit", "insert", "into", "overwrite",
    "create", "drop", "alter", "add", "set", "show", "use", "describe",
    "external", "managed", "partitioned", "clustered", "sorted", "rows",
    "format", "serde", "with", "serdeproperties", "inputformat", "outputformat",
    "location", "comment", "columns", "fields", "terminated", "collection",
    "items", "keys", "lines", "left", "right", "inner", "outer", "cross",
    "full", "union", "all", "distinct", "between", "in", "like", "rlike",
    "case", "when", "then", "else", "end", "null", "true", "false",
    "asc", "desc", "over", "row", "rows", "range", "unbounded", "preceding",
    "following", "current", "interval", "lateral", "view", "values",
    "primary", "key", "foreign", "references", "unique", "default",
    "boolean", "tinyint", "smallint", "int", "integer", "bigint",
    "float", "double", "decimal", "numeric", "string", "varchar", "char",
    "binary", "timestamp", "date", "array", "map", "struct", "uniontype",
}

# ── Hive built-in functions ─────────────────────────────────────────────────
# Anything NOT in this set (and not a SQL keyword) is treated as a UDF.
# TODO: replace with live query to Hive metastore or central UDF registry.
HIVE_BUILTINS: set[str] = {
    "sum", "count", "avg", "min", "max", "coalesce", "nvl", "nvl2",
    "substr", "substring", "length", "trim", "ltrim", "rtrim",
    "upper", "lower", "concat", "concat_ws", "split", "lpad", "rpad",
    "regexp_replace", "regexp_extract",
    "from_unixtime", "unix_timestamp", "to_date", "to_utc_timestamp",
    "year", "month", "day", "hour", "minute", "second",
    "datediff", "date_add", "date_sub", "date_format", "months_between",
    "cast", "round", "floor", "ceil", "abs", "mod", "positive", "negative",
    "greatest", "least", "rand", "pow", "power", "sqrt", "exp", "ln",
    "log", "log2", "log10", "sign", "bin", "hex", "unhex",
    "isnull", "isnotnull",
    "rank", "dense_rank", "row_number", "ntile", "percent_rank",
    "lag", "lead", "first_value", "last_value", "cume_dist",
    "collect_list", "collect_set", "size", "explode", "posexplode",
    "inline", "stack", "get_json_object", "json_tuple", "parse_url",
    "hash", "crc32", "md5", "sha1", "sha2", "aes_encrypt", "aes_decrypt",
    "base64", "unbase64", "printf", "space", "repeat", "reverse", "instr",
    "percentile", "percentile_approx", "histogram_numeric",
    "variance", "var_pop", "var_samp", "stddev", "stddev_pop", "stddev_samp",
    "corr", "covar_pop", "covar_samp", "kurtosis", "skewness",
    "count_distinct", "approx_count_distinct",
    "str_to_map", "sentences", "ngrams", "context_ngrams",
    "assert_true", "current_date", "current_timestamp", "current_user",
    "if", "nvl", "decode",
}

_EXCLUDE = HIVE_BUILTINS | SQL_KEYWORDS

# ── Regex patterns ──────────────────────────────────────────────────────────
RE_TABLE_READ   = re.compile(r'\b(?:FROM|JOIN)\s+([`\w]+(?:\.[`\w]+)?)', re.I)
RE_TABLE_CREATE = re.compile(
    r'\bCREATE\s+(?:EXTERNAL\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\w]+(?:\.[`\w]+)?)', re.I
)
RE_TABLE_WRITE  = re.compile(
    r'\bINSERT\s+(?:INTO|OVERWRITE)\s+(?:TABLE\s+)?([`\w]+(?:\.[`\w]+)?)', re.I
)
RE_FUNCTIONS    = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', re.I)
RE_WINDOW       = re.compile(r'\bOVER\s*\(', re.I)
RE_SUBQUERY     = re.compile(r'\(\s*SELECT\b', re.I)
RE_PARTITION_BY = re.compile(r'\bPARTITIONED\s+BY\s*\(([^)]+)\)', re.I)
RE_DYN_PART     = re.compile(r'\bPARTITION\s*\([^)]*\$\{hiveconf:', re.I)
RE_CROSS_DB     = re.compile(r'\b(?:FROM|JOIN)\s+(\w+)\.(\w+)\b', re.I)
RE_COLUMNS_SEL  = re.compile(r'\bSELECT\b(.*?)\bFROM\b', re.I | re.DOTALL)

# ── Complexity scoring ──────────────────────────────────────────────────────
# TODO: verify weights + band thresholds with migration team.
WEIGHTS = {
    "per_table":          1,
    "per_udf":            2,
    "window_function":    3,
    "cross_cluster_join": 5,
    "dynamic_partition":  2,
    "per_subquery":       2,
    "per_consumer":       1,
}

BANDS = [
    (0,  5,  "SMALL"),
    (6,  12, "MEDIUM"),
    (13, 20, "LARGE"),
    (21, 999,"COMPLEX"),
]

EFFORT = {
    "SMALL":   "1 day",
    "MEDIUM":  "3 days",
    "LARGE":   "1 week",
    "COMPLEX": "2+ weeks",
}


# ── Pure functions ──────────────────────────────────────────────────────────

def classify(score: int) -> str:
    for lo, hi, label in BANDS:
        if lo <= score <= hi:
            return label
    return "COMPLEX"


def strip_comments(sql: str) -> str:
    sql = re.sub(r'--[^\n]*', ' ', sql)
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
    return sql


def parse_file(path: Path) -> dict:
    """
    Parse a single .hql file.
    Uses sqlfluff for syntax validation, regex for data extraction.
    Returns a findings dict — no side-effects.
    """
    raw = path.read_text(encoding="utf-8")
    sql = strip_comments(raw)

    # Syntax validation via sqlfluff
    linter = Linter(dialect="hive")
    result = linter.parse_string(raw, fname=str(path))
    errors = [str(v) for v in result.violations] if result.violations else []

    # Separate table sets — read vs created vs written
    read_tables    = {m.group(1).lower() for m in RE_TABLE_READ.finditer(sql)}
    created_tables = {m.group(1).lower() for m in RE_TABLE_CREATE.finditer(sql)}
    written_tables = {m.group(1).lower() for m in RE_TABLE_WRITE.finditer(sql)}

    # Column names from SELECT lists
    raw_cols = [
        c.strip()
        for block in RE_COLUMNS_SEL.findall(sql)
        for c in block.split(",")
    ]
    columns = [c for c in raw_cols if c and not c.startswith("*")]

    # Partition keys from PARTITIONED BY (...)
    part_keys = []
    for block in RE_PARTITION_BY.findall(sql):
        for col_def in block.split(","):
            token = col_def.strip().split()[0].strip("`")
            if token:
                part_keys.append(token.lower())

    # UDFs = function calls not in built-ins, SQL keywords, or table names
    all_fns     = {m.group(1).lower() for m in RE_FUNCTIONS.finditer(sql)}
    table_names = read_tables | created_tables | written_tables
    udfs        = sorted(all_fns - _EXCLUDE - table_names)

    # Cross-database joins (db.table notation)
    cross_db = [f"{m.group(1)}.{m.group(2)}" for m in RE_CROSS_DB.finditer(sql)]

    return {
        "file":           path.name,
        "read_tables":    read_tables,
        "created_tables": created_tables,
        "written_tables": written_tables,
        "all_tables":     read_tables | created_tables | written_tables,
        "columns":        columns,
        "partition_keys": part_keys,
        "udfs":           udfs,
        "has_window":     bool(RE_WINDOW.search(sql)),
        "subqueries":     len(RE_SUBQUERY.findall(sql)),
        "has_dyn_part":   bool(RE_DYN_PART.search(sql)),
        "cross_db_joins": cross_db,
        "syntax_errors":  errors,
    }


def discover_downstream(output_tables: set[str], pipeline_dir: Path) -> list[str]:
    """
    Find sibling pipelines that read this pipeline's output tables.
    Matches only FROM/JOIN references (not substrings) after stripping SQL comments.
    This prevents false positives from column names, comments, or partial matches.
    """
    if not output_tables:
        return []

    # Require table name to appear directly after FROM or JOIN keyword.
    # re.escape handles dots (raw.events → raw\.events).
    # Backticks optional. Word boundary prevents partial matches (raw.events vs raw.events_v2).
    patterns = [
        re.compile(
            r'\b(?:FROM|JOIN)\s+`?' + re.escape(tbl) + r'`?\b',
            re.I,
        )
        for tbl in output_tables
    ]

    consumers = []
    for sibling in pipeline_dir.parent.iterdir():
        if sibling == pipeline_dir or not sibling.is_dir():
            continue
        for hql in sibling.glob("*.hql"):
            sql = strip_comments(hql.read_text(encoding="utf-8"))
            if any(p.search(sql) for p in patterns):
                consumers.append(sibling.name)
                break
    return consumers


def compute_score(
    tables: set,
    udfs: set,
    has_window: bool,
    cross_db: set,
    has_dyn_part: bool,
    subqueries: int,
    downstream: list,
) -> int:
    score  = len(tables)     * WEIGHTS["per_table"]
    score += len(udfs)       * WEIGHTS["per_udf"]
    score += has_window      * WEIGHTS["window_function"]
    score += len(cross_db)   * WEIGHTS["cross_cluster_join"]
    score += has_dyn_part    * WEIGHTS["dynamic_partition"]
    score += subqueries      * WEIGHTS["per_subquery"]
    score += len(downstream) * WEIGHTS["per_consumer"]
    return score
