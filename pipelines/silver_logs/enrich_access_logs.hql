-- enrich_access_logs.hql
-- Owner: data-engineering@ecommerce.io
-- Description: Enriches raw bronze web access logs with geographic metadata by resolving
--              each remote IP to a country via an integer range lookup against the silver
--              geolocation table. Parses the Apache-format log timestamp into a standard
--              TIMESTAMP column. Rows whose IP does not fall within any known range are
--              excluded (INNER JOIN). Output is partitioned by run date.
-- Reads:  bronze.web_logs              (external raw ingest — partitioned by dt)
--         silver.ip_country_lookup     (written by silver_geolocation pipeline)
-- Writes: silver.web_logs_enriched    (partitioned by dt)
--
-- Run: hive -hiveconf run_date=2024-01-15 -f enrich_access_logs.hql

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 2000;
SET hive.exec.max.dynamic.partitions.pernode = 500;
SET hive.auto.convert.join             = true;
SET hive.mapjoin.smalltable.filesize   = 67108864;

INSERT OVERWRITE TABLE silver.web_logs_enriched
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    logs.log_time,
    from_unixtime(
        unix_timestamp(logs.log_time, 'dd/MMM/yyyy:HH:mm:ss Z')
    )                                                   AS log_time_parsed,
    logs.remote_ip,
    udf_ip_to_country(logs.remote_ip)                   AS ip_number,
    geo.country_code,
    udf_curate_country(geo.country_name)                AS country_name,
    logs.request,
    logs.response_code,
    udf_mask_pii(logs.user_agent)                       AS user_agent
FROM (
    -- Resolve each IP to its integer representation once so the JOIN predicate
    -- only calls the UDF a single time per row rather than twice.
    SELECT
        log_time,
        remote_ip,
        udf_ip_to_country(remote_ip)                    AS ip_number,
        request,
        response_code,
        user_agent
    FROM bronze.web_logs
    WHERE dt = '${hiveconf:run_date}'
      AND remote_ip IS NOT NULL
      AND remote_ip != ''
) logs
JOIN silver.ip_country_lookup geo
    ON  logs.ip_number BETWEEN geo.ip_range_start AND geo.ip_range_end;
