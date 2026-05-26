-- Owner: data-engineering@ecommerce.io
-- Reads: external.raw_geolocation_csv
-- Writes: bronze.geolocation
--
-- Purpose: Ingests raw IP geolocation range data from the CSV-backed external
--          table into the bronze layer. No transformations are applied at this
--          stage; enrichment happens downstream in silver_geolocation.
--
-- Run: hive -hiveconf run_date=2024-01-15 -f ingest_geolocation.hql

SET hive.exec.dynamic.partition=true;
SET hive.exec.dynamic.partition.mode=nonstrict;
SET hive.exec.max.dynamic.partitions=1000;
SET hive.exec.max.dynamic.partitions.pernode=500;

INSERT OVERWRITE TABLE bronze.geolocation
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    ip_range_start,
    ip_range_end,
    country_code,
    country_name
FROM
    external.raw_geolocation_csv;
