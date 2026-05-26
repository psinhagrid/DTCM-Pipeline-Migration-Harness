-- Owner: data-engineering@ecommerce.io
-- Reads: silver.ip_country_lookup
-- Writes: silver.geo_coverage_stats
--
-- Purpose: Produces per-country IP address space coverage statistics from the
--          curated ip_country_lookup table. Countries represented by fewer than
--          2 distinct ranges are excluded (likely stub or bad feed entries).
--          A RANK window assigns a global coverage_rank so that operational
--          dashboards can surface the most-covered countries without a second
--          sort pass.
--
-- Run: hive -hiveconf run_date=2024-01-15 -f validate_geo_coverage.hql

SET hive.exec.dynamic.partition=true;
SET hive.exec.dynamic.partition.mode=nonstrict;
SET hive.exec.max.dynamic.partitions=1000;
SET hive.exec.max.dynamic.partitions.pernode=500;

INSERT OVERWRITE TABLE silver.geo_coverage_stats
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    country_code,
    country_name,
    range_count,
    total_coverage,
    min_ip,
    max_ip,
    RANK() OVER (ORDER BY total_coverage DESC)  AS coverage_rank
FROM (
    SELECT
        country_code,
        country_name,
        COUNT(*)                AS range_count,
        SUM(range_size)         AS total_coverage,
        MIN(ip_range_start)     AS min_ip,
        MAX(ip_range_end)       AS max_ip
    FROM
        silver.ip_country_lookup
    WHERE
        dt = '${hiveconf:run_date}'
    GROUP BY
        country_code,
        country_name
    HAVING
        COUNT(*) >= 2
) country_agg;
