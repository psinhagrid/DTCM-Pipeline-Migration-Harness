-- enrich_user_events.hql
-- Owner: growth-analytics-team
-- Description: Joins raw clickstream events with the user dimension to produce an enriched
--              event table. Applies UDF-based user segment and device category labels, and
--              attaches a per-user chronological event sequence number via window function.
--              Filters PING heartbeat events before writing.
-- Reads:  raw.events   (written by raw_events_ingest/ingest_clickstream.hql)
--         dim.users    (slowly-changing dimension, current snapshot)
-- Writes: enriched.user_events  (partitioned by dt)

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 5000;

INSERT OVERWRITE TABLE enriched.user_events
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    e.event_id,
    e.user_id,
    e.session_id,
    e.event_type,
    e.page_url,
    e.device_type,
    e.country_code,
    e.event_ts,
    u.age_band,
    u.customer_since,
    udf_user_segment(u.age_band, u.country_code)     AS user_segment,
    udf_device_category(e.device_type)               AS device_category,
    ROW_NUMBER() OVER (
        PARTITION BY e.user_id
        ORDER BY e.event_ts ASC
    )                                                AS event_seq,
    e.dt
FROM raw.events e
JOIN dim.users u
    ON  e.user_id = u.user_id
    AND u.is_current = 1
WHERE e.dt         = '${hiveconf:run_date}'
  AND e.source     = 'web'
  AND e.event_type != 'PING';
