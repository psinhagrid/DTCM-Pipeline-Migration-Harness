-- Owner: data-engineering@ecommerce.io
-- Reads: external.raw_currency_feed
-- Writes: bronze.currency_rates
--
-- Purpose: Ingests daily currency exchange rates from the raw external feed
--          into the bronze layer. Filters to the target run date and excludes
--          any rows with non-positive rates (bad feed entries).
--
-- Run: hive -hiveconf run_date=2024-01-15 -f ingest_currency_rates.hql

SET hive.exec.dynamic.partition=true;
SET hive.exec.dynamic.partition.mode=nonstrict;
SET hive.exec.max.dynamic.partitions=1000;
SET hive.exec.max.dynamic.partitions.pernode=500;

INSERT OVERWRITE TABLE bronze.currency_rates
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    currency_code,
    currency_name,
    rate_to_usd,
    effective_date
FROM
    external.raw_currency_feed
WHERE
    effective_date = '${hiveconf:run_date}'
    AND rate_to_usd > 0;
