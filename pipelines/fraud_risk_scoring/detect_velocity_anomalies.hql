-- detect_velocity_anomalies.hql
-- Owner: fraud-platform-team
-- Description: Applies time-range window functions over raw transactions to compute per-user
--              velocity signals: transaction count in the last hour, cumulative spend in 24 h,
--              and time gap to the previous transaction. These features feed score_transactions.hql.
--              RANGE BETWEEN INTERVAL windows are the core logic of this file.
-- Reads:  raw.transactions      (written by raw_events_ingest/ingest_transactions.hql)
-- Writes: risk.velocity_checks  (partitioned by dt)

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 2000;

INSERT OVERWRITE TABLE risk.velocity_checks
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    vel.txn_id,
    vel.user_id,
    vel.merchant_id,
    vel.txn_amount,
    vel.txn_currency,
    vel.channel,
    vel.status,
    vel.txn_ts,
    vel.txns_last_hour,
    vel.spend_24h,
    vel.prev_txn_ts,
    UNIX_TIMESTAMP(vel.txn_ts) - UNIX_TIMESTAMP(vel.prev_txn_ts) AS secs_since_prev_txn,
    udf_velocity_flag(
        vel.txns_last_hour,
        vel.spend_24h
    )                                                AS velocity_flag,
    vel.dt
FROM (
    SELECT
        t.txn_id,
        t.user_id,
        t.merchant_id,
        t.txn_amount,
        t.txn_currency,
        t.channel,
        t.status,
        t.txn_ts,
        t.dt,
        COUNT(*) OVER (
            PARTITION BY t.user_id
            ORDER BY UNIX_TIMESTAMP(t.txn_ts)
            RANGE BETWEEN 3600 PRECEDING AND CURRENT ROW
        )                                            AS txns_last_hour,
        SUM(t.txn_amount) OVER (
            PARTITION BY t.user_id
            ORDER BY UNIX_TIMESTAMP(t.txn_ts)
            RANGE BETWEEN 86400 PRECEDING AND CURRENT ROW
        )                                            AS spend_24h,
        LAG(t.txn_ts, 1) OVER (
            PARTITION BY t.user_id
            ORDER BY t.txn_ts
        )                                            AS prev_txn_ts
    FROM raw.transactions t
    WHERE t.dt = '${hiveconf:run_date}'
      AND t.status NOT IN ('SYSTEM_ERROR', 'GATEWAY_TIMEOUT')
) vel;
