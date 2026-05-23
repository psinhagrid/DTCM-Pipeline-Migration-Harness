-- session_funnel_attribution.hql
-- Owner: growth-analytics-team
-- Description: Attributes each completed session to a marketing touchpoint using a configurable
--              attribution model (first-touch / last-touch). Joins session data with the ordered
--              clickstream and a cross-database campaign touchpoints table. FIRST_VALUE and
--              LAST_VALUE window functions identify entry and exit touchpoints per session.
-- Reads:  raw.sessions                      (written by raw_events_ingest/ingest_user_sessions.hql)
--         raw.events                        (written by raw_events_ingest/ingest_clickstream.hql)
--         analytics.campaign_touchpoints    (cross-database join — analytics schema)
-- Writes: enriched.funnel_attribution       (partitioned by dt)

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 5000;

INSERT OVERWRITE TABLE enriched.funnel_attribution
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    attr.session_id,
    attr.user_id,
    attr.first_touch_campaign,
    attr.last_touch_campaign,
    attr.first_touch_channel,
    attr.last_touch_channel,
    attr.session_start,
    attr.session_end,
    udf_attribution_model(
        attr.first_touch_campaign,
        attr.last_touch_campaign
    )                                                AS attributed_campaign,
    s.page_count,
    s.is_bounce,
    attr.dt
FROM (
    SELECT
        tp.session_id,
        tp.user_id,
        tp.dt,
        FIRST_VALUE(tp.campaign_id) OVER (
            PARTITION BY tp.session_id
            ORDER BY tp.touch_ts ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )                                            AS first_touch_campaign,
        LAST_VALUE(tp.campaign_id) OVER (
            PARTITION BY tp.session_id
            ORDER BY tp.touch_ts ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )                                            AS last_touch_campaign,
        FIRST_VALUE(tp.channel) OVER (
            PARTITION BY tp.session_id
            ORDER BY tp.touch_ts ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )                                            AS first_touch_channel,
        LAST_VALUE(tp.channel) OVER (
            PARTITION BY tp.session_id
            ORDER BY tp.touch_ts ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )                                            AS last_touch_channel,
        MIN(e.event_ts) OVER (PARTITION BY tp.session_id) AS session_start,
        MAX(e.event_ts) OVER (PARTITION BY tp.session_id) AS session_end
    FROM (
        SELECT
            act.campaign_id,
            act.channel,
            act.touch_ts,
            act.session_id,
            act.user_id,
            act.dt
        FROM analytics.campaign_touchpoints act
        WHERE act.dt = '${hiveconf:run_date}'
          AND act.session_id IS NOT NULL
    ) tp
    JOIN raw.events e
        ON  tp.session_id = e.session_id
        AND e.dt          = '${hiveconf:run_date}'
) attr
JOIN raw.sessions s
    ON  attr.session_id = s.session_id
    AND s.dt            = '${hiveconf:run_date}'
QUALIFY ROW_NUMBER() OVER (PARTITION BY attr.session_id ORDER BY attr.first_touch_campaign) = 1;
