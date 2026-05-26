-- Owner: data-engineering@ecommerce.io
-- Reads: bronze.geolocation
-- Writes: silver.ip_country_lookup
--
-- Purpose: Curates the raw geolocation ranges into a clean lookup table.
--          Filters out malformed rows (inverted or zero-width ranges, null/empty
--          country codes), computes the range_size for downstream coverage
--          analysis, and assigns a region_seq ordinal per country so that
--          IP-lookup joins can iterate through ranges in start-address order.
--
-- Run: hive -hiveconf run_date=2024-01-15 -f build_ip_country_lookup.hql

SET hive.exec.dynamic.partition=true;
SET hive.exec.dynamic.partition.mode=nonstrict;
SET hive.exec.max.dynamic.partitions=1000;
SET hive.exec.max.dynamic.partitions.pernode=500;

INSERT OVERWRITE TABLE silver.ip_country_lookup
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    ip_range_start,
    ip_range_end,
    country_code,
    country_name,
    (ip_range_end - ip_range_start)                                        AS range_size,
    ROW_NUMBER() OVER (
        PARTITION BY country_code
        ORDER BY ip_range_start ASC
    )                                                                       AS region_seq
FROM
    bronze.geolocation
WHERE
    dt             = '${hiveconf:run_date}'
    AND ip_range_start < ip_range_end
    AND country_code   IS NOT NULL
    AND country_code   != '';
