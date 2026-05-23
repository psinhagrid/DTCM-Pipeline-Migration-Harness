"""
static_analyzer.py — Real lightweight semantic validation.

Parses source HiveQL and converted PySpark using regex, extracts structural
and semantic elements, compares them, and returns structured check results
including specific issues found.

No LLM, no Spark runtime — pure text analysis.
"""

import re
from dataclasses import dataclass, field


# ── Strip helpers ─────────────────────────────────────────────────────────────

def _strip_comments(sql: str) -> str:
    sql = re.sub(r'--[^\n]*', ' ', sql)
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
    return sql

def _norm(s: str) -> str:
    return ' '.join(_strip_comments(s).split())


# ── HiveQL patterns ───────────────────────────────────────────────────────────

_HQL_FROM_TABLE   = re.compile(r'\b(?:FROM|JOIN)\s+([`\w]+(?:\.[`\w]+)?)', re.I)
_HQL_WRITE_TABLE  = re.compile(r'\bINSERT\s+(?:INTO|OVERWRITE)\s+(?:TABLE\s+)?([`\w]+)', re.I)
_HQL_AGG          = re.compile(r'\b(SUM|COUNT|AVG|MIN|MAX|COLLECT_LIST|COLLECT_SET|PERCENTILE|STDDEV|VARIANCE)\s*\(', re.I)
_HQL_JOIN_TYPED   = re.compile(r'\b(LEFT\s+(?:OUTER\s+)?|RIGHT\s+(?:OUTER\s+)?|INNER\s+|CROSS\s+|FULL\s+(?:OUTER\s+)?)JOIN\b', re.I)
_HQL_JOIN_ANY     = re.compile(r'\bJOIN\b', re.I)
_HQL_GROUP        = re.compile(r'\bGROUP\s+BY\s+(.+?)(?=\bHAVING\b|\bORDER\b|\bLIMIT\b|;|$)', re.I | re.DOTALL)
_HQL_WHERE        = re.compile(r'\bWHERE\b(.+?)(?=\bGROUP\b|\bORDER\b|\bLIMIT\b|\bHAVING\b|;|$)', re.I | re.DOTALL)
_HQL_SELECT_BLOCK = re.compile(r'\bSELECT\b(.*?)\bFROM\b', re.I | re.DOTALL)
_HQL_WINDOW       = re.compile(r'\bOVER\s*\(', re.I)
_HQL_SUBQUERY     = re.compile(r'\(\s*SELECT\b', re.I)
_HQL_PARTITION    = re.compile(r'\bPARTITION\s*\(([^)]+)\)', re.I)
_HQL_PARTITIONED  = re.compile(r'\bPARTITIONED\s+BY\s*\(([^)]+)\)', re.I)
_HQL_OVERWRITE    = re.compile(r'\bINSERT\s+OVERWRITE\b', re.I)
_HQL_ALIAS        = re.compile(r'\bAS\s+(\w+)\s*$', re.I)
_HIVECONF         = re.compile(r'\$\{hiveconf:[^}]+\}')

# ── PySpark patterns ──────────────────────────────────────────────────────────

_PY_TABLE         = re.compile(r'spark\.table\(["\']([^"\']+)["\']\)')
_PY_AGG           = re.compile(r'\bF\.(sum|count|avg|min|max|collect_list|collect_set|percentile|stddev|variance)\s*\(', re.I)
_PY_JOIN          = re.compile(r'\.join\s*\(', re.I)
_PY_JOIN_TYPE     = re.compile(r'\.join\s*\([^,)]+,[^,)]+,\s*["\'](\w+)["\']', re.I)
_PY_GROUP         = re.compile(r'\.groupBy\s*\(([^)]+)\)')
_PY_FILTER        = re.compile(r'\.filter\s*\((.+?)(?=\)\s*[\\.\n]|\)\s*$)', re.I | re.DOTALL)
_PY_WRITE         = re.compile(r'\.writeTo\s*\(["\']([^"\']+)["\']\)')
_PY_PARTITION_BY  = re.compile(r'\.partitionedBy\s*\(([^)]+)\)')
_PY_OVERWRITE     = re.compile(r'\.overwritePartitions\s*\(\s*\)')
_PY_WINDOW        = re.compile(r'Window\.|\.over\s*\(', re.I)
_PY_ALIAS         = re.compile(r'\.alias\(["\'](\w+)["\']\)')
_PY_WITH_COL      = re.compile(r'\.withColumn\(["\'](\w+)["\']')
_PY_SELECT        = re.compile(r'\.select\s*\(([^)]+)\)')
_PY_CONF_GET      = re.compile(r'spark\.conf\.get\(["\']([^"\']+)["\']\)')


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class QueryStructure:
    source_type:    str   = "unknown"   # "hiveql" | "pyspark"
    tables:         set   = field(default_factory=set)
    write_target:   str   = ""
    output_cols:    set   = field(default_factory=set)
    aggs:           set   = field(default_factory=set)
    join_count:     int   = 0
    join_types:     list  = field(default_factory=list)
    group_cols:     list  = field(default_factory=list)
    where_tokens:   set   = field(default_factory=set)
    has_filter:     bool  = False
    has_window:     bool  = False
    has_subquery:   bool  = False
    is_overwrite:   bool  = False
    partition_keys: list  = field(default_factory=list)
    runtime_vars:   set   = field(default_factory=set)


# ── HiveQL analysis ───────────────────────────────────────────────────────────

def _split_select_items(sel: str) -> list[str]:
    """Split SELECT list respecting parentheses."""
    items, current, depth = [], [], 0
    for ch in sel:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            items.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        items.append(''.join(current).strip())
    return [i for i in items if i.strip()]


def _hql_output_cols(sql: str) -> set:
    clean = _norm(sql)
    m     = _HQL_SELECT_BLOCK.search(clean)
    if not m:
        return set()
    cols = set()
    for item in _split_select_items(m.group(1)):
        item = item.strip()
        if not item or item.strip() == '*':
            continue
        alias_m = _HQL_ALIAS.search(item)
        if alias_m:
            cols.add(alias_m.group(1).lower())
        else:
            base = item.split('.')[-1].strip().lower()
            base = re.sub(r'\s.*$', '', base)
            if re.match(r'^\w+$', base):
                cols.add(base)
    return cols


def _hql_where_tokens(sql: str) -> set:
    clean = _norm(sql)
    m     = _HQL_WHERE.search(clean)
    if not m:
        return set()
    raw = _HIVECONF.sub('__hiveconf__', m.group(1).lower())
    return {t for t in re.findall(r'\b\w+\b', raw)
            if len(t) > 2 and t not in ('and', 'not', 'the', 'for', 'all')}


def analyze_hiveql(hql: str) -> QueryStructure:
    clean = _norm(hql)
    qs    = QueryStructure(source_type="hiveql")

    qs.tables       = {m.group(1).lower() for m in _HQL_FROM_TABLE.finditer(clean)}
    qs.aggs         = {m.group(1).upper() for m in _HQL_AGG.finditer(clean)}
    qs.join_types   = [re.sub(r'\s+', ' ', m.group(1)).strip().upper()
                       for m in _HQL_JOIN_TYPED.finditer(clean)]
    qs.join_count   = max(len(qs.join_types), len(_HQL_JOIN_ANY.findall(clean)))
    qs.has_filter   = bool(_HQL_WHERE.search(clean))
    qs.where_tokens = _hql_where_tokens(hql)
    qs.has_window   = bool(_HQL_WINDOW.search(clean))
    qs.has_subquery = bool(_HQL_SUBQUERY.search(clean))
    qs.is_overwrite = bool(_HQL_OVERWRITE.search(clean))
    qs.output_cols  = _hql_output_cols(clean)
    qs.runtime_vars = set(_HIVECONF.findall(hql))

    m_grp = _HQL_GROUP.search(clean)
    if m_grp:
        qs.group_cols = [c.strip().split('.')[-1].lower()
                         for c in m_grp.group(1).split(',') if c.strip()]

    m_part = _HQL_PARTITIONED.search(clean)
    if m_part:
        qs.partition_keys = [c.strip().split()[0].lower()
                             for c in m_part.group(1).split(',')]

    m_write = _HQL_WRITE_TABLE.search(clean)
    if m_write:
        qs.write_target = m_write.group(1).lower()

    # Remove write target from read tables
    qs.tables -= {qs.write_target}
    return qs


# ── PySpark analysis ──────────────────────────────────────────────────────────

def _py_output_cols(py: str) -> set:
    cols = set()
    for m in _PY_ALIAS.finditer(py):
        cols.add(m.group(1).lower())
    for m in _PY_WITH_COL.finditer(py):
        cols.add(m.group(1).lower())
    for m in _PY_GROUP.finditer(py):
        for c in m.group(1).split(','):
            cn = c.strip().strip('"\'').split('.')[-1].lower()
            if re.match(r'^\w+$', cn):
                cols.add(cn)
    for m in _PY_SELECT.finditer(py):
        for c in m.group(1).split(','):
            cn = c.strip().strip('"\'').split('.')[-1].lower()
            if re.match(r'^\w+$', cn) and not cn.startswith('f'):
                cols.add(cn)
    return cols


def _py_where_tokens(py: str) -> set:
    tokens = set()
    for m in _PY_FILTER.finditer(py):
        raw = m.group(1).lower()
        tokens |= {t for t in re.findall(r'\b\w+\b', raw)
                   if len(t) > 2 and t not in ('and', 'col', 'not', 'for', 'the')}
    return tokens


def analyze_pyspark(py: str) -> QueryStructure:
    qs = QueryStructure(source_type="pyspark")

    qs.tables       = {m.group(1).lower().split('.')[-1] for m in _PY_TABLE.finditer(py)}
    qs.aggs         = {m.group(1).upper() for m in _PY_AGG.finditer(py)}
    qs.join_count   = len(_PY_JOIN.findall(py))
    qs.join_types   = [m.group(1).upper() for m in _PY_JOIN_TYPE.finditer(py)]
    qs.has_filter   = bool(_PY_FILTER.search(py))
    qs.where_tokens = _py_where_tokens(py)
    qs.has_window   = bool(_PY_WINDOW.search(py))
    qs.is_overwrite = bool(_PY_OVERWRITE.search(py))
    qs.output_cols  = _py_output_cols(py)
    qs.runtime_vars = set(_PY_CONF_GET.findall(py))

    m_grp = _PY_GROUP.search(py)
    if m_grp:
        qs.group_cols = [c.strip().strip('"\'').split('.')[-1].lower()
                         for c in m_grp.group(1).split(',') if c.strip()]

    m_part = _PY_PARTITION_BY.search(py)
    if m_part:
        qs.partition_keys = [c.strip().strip('"\'').lower()
                             for c in m_part.group(1).split(',')]

    m_write = _PY_WRITE.search(py)
    if m_write:
        qs.write_target = m_write.group(1).lower().split('.')[-1]

    return qs


# ── Semantic comparison ───────────────────────────────────────────────────────

def compare(hive: QueryStructure, spark: QueryStructure) -> dict:
    """
    Compare HiveQL vs PySpark across all semantic dimensions.
    Returns structured check results with status, detail, score, and issues.
    """
    checks = {}
    issues = []

    # ── 1. Table parity ───────────────────────────────────────────────
    missing_tables = hive.tables - spark.tables
    extra_tables   = spark.tables - hive.tables - {spark.write_target}

    if not missing_tables:
        checks["table_parity"] = {
            "status": "PASSED",
            "detail": f"All {len(hive.tables)} source table(s) present in PySpark",
            "score":  1.0,
        }
    else:
        msg = f"Missing in PySpark: {', '.join(sorted(missing_tables))}"
        issues.append(f"Table parity: {msg}")
        checks["table_parity"] = {
            "status": "FAILED",
            "detail": msg,
            "score":  max(0.0, 1.0 - len(missing_tables) / max(len(hive.tables), 1)),
        }

    # ── 2. Column parity ──────────────────────────────────────────────
    if not hive.output_cols:
        checks["column_parity"] = {"status": "SKIPPED", "detail": "No output columns detected in source", "score": 1.0}
    else:
        missing_cols = hive.output_cols - spark.output_cols
        col_score    = 1.0 - len(missing_cols) / max(len(hive.output_cols), 1)
        if col_score >= 0.85:
            status = "PASSED"
        elif col_score >= 0.60:
            status = "WARNING"
        else:
            status = "FAILED"

        if missing_cols:
            msg = f"{len(missing_cols)} column(s) not found in target: {', '.join(sorted(missing_cols)[:5])}"
            if status in ("FAILED", "WARNING"):
                issues.append(f"Column parity: {msg}")
            detail = msg
        else:
            detail = f"All {len(hive.output_cols)} projected column(s) verified"

        checks["column_parity"] = {"status": status, "detail": detail, "score": round(col_score, 3)}

    # ── 3. Aggregation parity ─────────────────────────────────────────
    missing_aggs = hive.aggs - spark.aggs
    if not hive.aggs:
        checks["aggregation_parity"] = {"status": "SKIPPED", "detail": "No aggregations in source", "score": 1.0}
    elif not missing_aggs:
        checks["aggregation_parity"] = {
            "status": "PASSED",
            "detail": f"{len(hive.aggs)} aggregation(s) verified: {', '.join(sorted(hive.aggs))}",
            "score":  1.0,
        }
    else:
        msg = f"Missing aggregation(s) in PySpark: {', '.join(sorted(missing_aggs))}"
        issues.append(f"Aggregation parity: {msg}")
        checks["aggregation_parity"] = {
            "status": "FAILED",
            "detail": msg,
            "score":  max(0.0, 1.0 - len(missing_aggs) / max(len(hive.aggs), 1)),
        }

    # ── 4. JOIN parity ────────────────────────────────────────────────
    if hive.join_count == 0 and spark.join_count == 0:
        checks["join_parity"] = {"status": "SKIPPED", "detail": "No JOINs in source", "score": 1.0}
    elif hive.join_count == spark.join_count:
        type_info = f" ({', '.join(hive.join_types)})" if hive.join_types else ""
        checks["join_parity"] = {
            "status": "PASSED",
            "detail": f"{hive.join_count} JOIN(s) preserved{type_info}",
            "score":  1.0,
        }
    else:
        diff = abs(hive.join_count - spark.join_count)
        direction = "fewer" if spark.join_count < hive.join_count else "more"
        msg = (f"Source: {hive.join_count} JOIN(s) "
               f"({', '.join(hive.join_types) or 'untyped'})  "
               f"PySpark: {spark.join_count} JOIN(s) — {diff} {direction}")
        if diff >= 1:
            issues.append(f"Join parity: {msg}")
        checks["join_parity"] = {
            "status": "WARNING" if diff == 1 else "FAILED",
            "detail": msg,
            "score":  max(0.0, 1.0 - diff / max(hive.join_count, 1)),
        }

    # ── 5. GROUP BY parity ────────────────────────────────────────────
    if not hive.group_cols:
        checks["group_by_parity"] = {"status": "SKIPPED", "detail": "No GROUP BY in source", "score": 1.0}
    else:
        hive_g  = {c.split('.')[-1].lower() for c in hive.group_cols}
        spark_g = {c.split('.')[-1].lower() for c in spark.group_cols}
        missing_g = hive_g - spark_g
        if not missing_g:
            checks["group_by_parity"] = {
                "status": "PASSED",
                "detail": f"{len(hive_g)} GROUP BY column(s) verified",
                "score":  1.0,
            }
        else:
            msg = f"Missing GROUP BY column(s) in PySpark: {', '.join(sorted(missing_g))}"
            issues.append(f"Group-by parity: {msg}")
            checks["group_by_parity"] = {
                "status": "FAILED",
                "detail": msg,
                "score":  max(0.0, 1.0 - len(missing_g) / max(len(hive_g), 1)),
            }

    # ── 6. Filter parity ──────────────────────────────────────────────
    if not hive.has_filter:
        checks["filter_parity"] = {"status": "SKIPPED", "detail": "No WHERE clause in source", "score": 1.0}
    elif hive.has_filter and not spark.has_filter:
        msg = "Source has WHERE clause but no .filter() found in PySpark — possible data loss"
        issues.append(f"Filter parity: {msg}")
        checks["filter_parity"] = {"status": "FAILED", "detail": msg, "score": 0.0}
    else:
        # Compare filter token overlap
        overlap = hive.where_tokens & spark.where_tokens
        token_score = len(overlap) / max(len(hive.where_tokens), 1) if hive.where_tokens else 1.0
        status = "PASSED" if token_score >= 0.6 else "WARNING"
        detail = (f"WHERE → .filter() preserved  "
                  f"token overlap {token_score:.0%} "
                  f"({len(overlap)}/{len(hive.where_tokens)} conditions)")
        if status == "WARNING":
            issues.append(f"Filter parity: low condition overlap ({token_score:.0%})")
        checks["filter_parity"] = {"status": status, "detail": detail, "score": round(token_score, 3)}

    # ── 7. Partition parity ───────────────────────────────────────────
    if not hive.partition_keys:
        checks["partition_parity"] = {"status": "SKIPPED", "detail": "No PARTITIONED BY in source DDL", "score": 1.0}
    else:
        hive_pk  = set(hive.partition_keys)
        spark_pk = set(spark.partition_keys)
        missing_pk = hive_pk - spark_pk
        if not missing_pk:
            checks["partition_parity"] = {
                "status": "PASSED",
                "detail": f"Partition keys preserved: {', '.join(sorted(hive_pk))}",
                "score":  1.0,
            }
        else:
            msg = f"Missing partition key(s) in PySpark: {', '.join(sorted(missing_pk))}"
            issues.append(f"Partition parity: {msg}")
            checks["partition_parity"] = {"status": "WARNING", "detail": msg, "score": 0.5}

    # ── 8. Runtime variable parity ────────────────────────────────────
    if hive.runtime_vars:
        missing_rv = hive.runtime_vars - spark.runtime_vars
        if not missing_rv:
            checks["runtime_var_parity"] = {
                "status": "PASSED",
                "detail": f"All {len(hive.runtime_vars)} hiveconf var(s) mapped to spark.conf.get()",
                "score":  1.0,
            }
        else:
            msg = f"Unmapped hiveconf var(s): {', '.join(sorted(missing_rv))}"
            issues.append(f"Runtime vars: {msg}")
            checks["runtime_var_parity"] = {"status": "WARNING", "detail": msg, "score": 0.5}

    # ── Overall similarity ────────────────────────────────────────────
    scores = [v["score"] for v in checks.values() if isinstance(v, dict) and "score" in v]
    checks["overall_similarity"] = round(sum(scores) / len(scores), 3) if scores else 0.0
    checks["issues"]             = issues

    return checks


# ── Workflow parity ───────────────────────────────────────────────────────────

def check_workflow_parity(conversion: dict) -> dict:
    """
    Compare number of HiveQL DML files against DAG task count.
    Real files vs real DAG task definitions.
    """
    files   = conversion.get("files", [])
    dag_str = conversion.get("dag", "")

    dml_count  = sum(
        1 for f in files
        if re.search(r'\bINSERT\b|\bSELECT\b', f.get("source_hql", ""), re.I)
    )
    task_count = len(re.findall(r'SparkSubmitOperator', dag_str))

    if task_count == 0:
        return {"status": "SKIPPED", "detail": "DAG not generated", "score": 1.0}
    elif task_count >= dml_count:
        return {
            "status": "PASSED",
            "detail": f"{task_count} DAG task(s) cover {dml_count} pipeline file(s)",
            "score":  1.0,
        }
    else:
        return {
            "status": "WARNING",
            "detail": f"DAG has {task_count} task(s) but expected {dml_count}",
            "score":  task_count / max(dml_count, 1),
        }
