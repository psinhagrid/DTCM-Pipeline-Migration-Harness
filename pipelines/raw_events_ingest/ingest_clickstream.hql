-- ingest_clickstream.hql
-- Owner: data-ingestion-team
-- Description: Ingests raw web clickstream events from the external payment-gateway landing zone
--              into the managed raw.events table. One row per event. No dedup — upstream
--              guarantees exactly-once delivery for the partition window.
-- Reads:  external.raw_clickstream  (external table, S3-backed, source data)
-- Writes: raw.events                (partitioned by dt, source)

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 5000;

INSERT OVERWRITE TABLE raw.events
PARTITION (dt = '${hiveconf:run_date}', source = 'web')
SELECT
    rc.event_id,
    rc.user_id,
    rc.session_id,
    rc.event_type,
    rc.page_url,
    rc.device_type,
    rc.country_code,
    rc.event_ts,
    rc.dt
FROM external.raw_clickstream rc
WHERE rc.dt        = '${hiveconf:run_date}'
  AND rc.event_id  IS NOT NULL
  AND rc.user_id   IS NOT NULL
  AND rc.event_ts  IS NOT NULL;
