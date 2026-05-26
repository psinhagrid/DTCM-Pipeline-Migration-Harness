-- compute_traffic_stats.hql
-- Owner: data-engineering@ecommerce.io
-- Description: Aggregates enriched web access logs into a country-level traffic statistics
--              table. Computes per-group request counts and unique visitor counts, then
--              applies window functions to derive a 7-day rolling request total and a
--              within-day traffic rank per country. Only well-known HTTP response codes
--              are retained. Output is partitioned by run date.
-- Reads:  silver.web_logs_enriched    (written by silver_logs/enrich_access_logs.hql)
-- Writes: silver.traffic_stats        (partitioned by dt)
--
-- Run: hive -hiveconf run_date=2024-01-15 -f compute_traffic_stats.hql

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 2000;
SET hive.exec.max.dynamic.partitions.pernode = 500;
SET hive.map.aggr                      = true;
SET hive.groupby.skewindata            = true;

INSERT OVERWRITE TABLE silver.traffic_stats
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    windowed.country_name,
    windowed.country_code,
    windowed.response_code,
    windowed.request_count,
    windowed.unique_visitors,
    windowed.dt,
    SUM(windowed.request_count) OVER (
        PARTITION BY windowed.country_name
        ORDER BY windowed.dt
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    )                                                   AS rolling_7d_requests,
    RANK() OVER (
        PARTITION BY windowed.dt
        ORDER BY windowed.request_count DESC
    )                                                   AS traffic_rank
FROM (
    -- Pre-aggregate before windowing to ensure COUNT(DISTINCT) is resolved
    -- prior to being referenced by window functions, which is required in HiveQL.
    SELECT
        country_name,
        country_code,
        response_code,
        dt,
        COUNT(*)                                        AS request_count,
        COUNT(DISTINCT remote_ip)                       AS unique_visitors
    FROM silver.web_logs_enriched
    WHERE dt           = '${hiveconf:run_date}'
      AND response_code IN ('200', '301', '404', '500')
      AND country_name IS NOT NULL
    GROUP BY
        country_name,
        country_code,
        response_code,
        dt
) windowed;
