-- compute_user_segments.hql
-- Owner: growth-analytics-team
-- Description: Derives behavioural user segments by combining enriched events with session
--              depth data. Computes rolling 7-day page engagement and average session depth
--              windows to feed the udf_ltv_band classifier. Partitioned by both date and
--              segment_version so A/B segment models can coexist in the table.
-- Reads:  enriched.user_events   (written by user_activity_enrichment/enrich_user_events.hql)
--         raw.sessions           (written by raw_events_ingest/ingest_user_sessions.hql)
-- Writes: enriched.user_segments (partitioned by dt, segment)

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 10000;

INSERT OVERWRITE TABLE enriched.user_segments
PARTITION (dt = '${hiveconf:run_date}', segment = '${hiveconf:segment_version}')
SELECT
    windowed.user_id,
    windowed.user_segment,
    windowed.rolling_7d_pages,
    windowed.avg_session_depth,
    udf_ltv_band(
        windowed.rolling_7d_pages,
        windowed.avg_session_depth
    )                                                AS ltv_band,
    udf_user_segment(
        windowed.age_band,
        windowed.country_code
    )                                                AS segment_label,
    windowed.event_count,
    windowed.distinct_sessions,
    windowed.dt
FROM (
    SELECT
        daily_agg.user_id,
        daily_agg.user_segment,
        daily_agg.age_band,
        daily_agg.country_code,
        daily_agg.event_count,
        daily_agg.distinct_sessions,
        daily_agg.dt,
        SUM(sess_agg.page_count) OVER (
            PARTITION BY daily_agg.user_id
            ORDER BY daily_agg.dt
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        )                                            AS rolling_7d_pages,
        AVG(sess_agg.page_count) OVER (
            PARTITION BY daily_agg.user_id
            ORDER BY daily_agg.dt
        )                                            AS avg_session_depth
    FROM (
        SELECT
            ue.user_id,
            ue.user_segment,
            ue.age_band,
            ue.country_code,
            COUNT(ue.event_id)                       AS event_count,
            COUNT(DISTINCT ue.session_id)            AS distinct_sessions,
            ue.dt
        FROM enriched.user_events ue
        WHERE ue.dt = '${hiveconf:run_date}'
        GROUP BY
            ue.user_id,
            ue.user_segment,
            ue.age_band,
            ue.country_code,
            ue.dt
    ) daily_agg
    JOIN (
        SELECT
            s.user_id,
            AVG(s.page_count)                        AS page_count,
            s.dt
        FROM raw.sessions s
        WHERE s.dt = '${hiveconf:run_date}'
        GROUP BY
            s.user_id,
            s.dt
    ) sess_agg
        ON  daily_agg.user_id = sess_agg.user_id
        AND daily_agg.dt      = sess_agg.dt
) windowed;
