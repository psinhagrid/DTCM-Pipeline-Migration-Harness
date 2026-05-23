-- ingest_user_sessions.hql
-- Owner: data-ingestion-team
-- Description: Aggregates raw clickstream rows (same source as ingest_clickstream) at session
--              granularity. Produces one row per session_id with timing, page depth, and
--              bounce classification. Downstream: user_activity_enrichment depends on raw.sessions.
-- Reads:  external.raw_clickstream  (external table, same source as ingest_clickstream)
-- Writes: raw.sessions              (partitioned by dt)

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 5000;

INSERT OVERWRITE TABLE raw.sessions
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    agg.session_id,
    agg.user_id,
    agg.session_start,
    agg.session_end,
    agg.page_count,
    CASE
        WHEN agg.page_count <= 1 THEN 1
        ELSE 0
    END                                              AS is_bounce,
    agg.dt
FROM (
    SELECT
        rc.session_id,
        rc.user_id,
        MIN(rc.event_ts)                             AS session_start,
        MAX(rc.event_ts)                             AS session_end,
        COUNT(DISTINCT rc.page_url)                  AS page_count,
        rc.dt
    FROM external.raw_clickstream rc
    WHERE rc.dt        = '${hiveconf:run_date}'
      AND rc.session_id IS NOT NULL
      AND rc.user_id    IS NOT NULL
    GROUP BY
        rc.session_id,
        rc.user_id,
        rc.dt
) agg;
