-- score_transactions.hql
-- Owner: fraud-platform-team
-- Description: Combines raw transaction features, enriched user segment signals, velocity checks,
--              and a compliance blacklist to produce a per-transaction risk score and fraud
--              probability estimate. Scores are consumed downstream by flag_high_risk_txns.hql
--              and the executive dashboard.
-- Reads:  raw.transactions          (written by raw_events_ingest/ingest_transactions.hql)
--         enriched.user_events      (written by user_activity_enrichment/enrich_user_events.hql)
--         risk.velocity_checks      (written by fraud_risk_scoring/detect_velocity_anomalies.hql)
--         compliance.blacklist_merchants  (cross-database join — compliance schema)
-- Writes: risk.risk_scores          (partitioned by dt)

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 2000;

INSERT OVERWRITE TABLE risk.risk_scores
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    t.txn_id,
    t.user_id,
    t.merchant_id,
    t.txn_amount,
    t.txn_currency,
    t.channel,
    t.status,
    t.txn_ts,
    vc.velocity_flag,
    vc.txns_last_hour,
    vc.spend_24h,
    vc.prev_txn_ts,
    latest_event.user_segment,
    latest_event.device_category,
    CASE
        WHEN bl.merchant_id IS NOT NULL THEN 1
        ELSE 0
    END                                              AS is_blacklisted_merchant,
    udf_risk_score(
        t.txn_amount,
        vc.velocity_flag,
        latest_event.user_segment
    )                                                AS risk_score,
    udf_fraud_probability(
        udf_risk_score(
            t.txn_amount,
            vc.velocity_flag,
            latest_event.user_segment
        ),
        CASE WHEN bl.merchant_id IS NOT NULL THEN 1 ELSE 0 END
    )                                                AS fraud_probability,
    '${hiveconf:model_version}'                      AS model_version,
    t.dt
FROM raw.transactions t
JOIN risk.velocity_checks vc
    ON  t.txn_id = vc.txn_id
    AND vc.dt    = '${hiveconf:run_date}'
LEFT JOIN (
    SELECT
        ue.user_id,
        ue.user_segment,
        ue.device_category,
        ue.dt
    FROM enriched.user_events ue
    WHERE ue.dt = '${hiveconf:run_date}'
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY ue.user_id
        ORDER BY ue.event_ts DESC
    ) = 1
) latest_event
    ON  t.user_id = latest_event.user_id
    AND latest_event.dt = '${hiveconf:run_date}'
LEFT JOIN compliance.blacklist_merchants bl
    ON  t.merchant_id = bl.merchant_id
    AND bl.is_active  = 1
WHERE t.dt = '${hiveconf:run_date}'
  AND t.txn_amount > '${hiveconf:risk_threshold}';
