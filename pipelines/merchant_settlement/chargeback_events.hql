-- chargeback_events.hql
-- Chargeback and dispute event dimension
-- Owner: risk-team
-- Source: disputes_raw (ana_risk cluster)

CREATE TABLE IF NOT EXISTS chargeback_events (
    chargeback_id   STRING         COMMENT 'Unique chargeback ID',
    txn_id          STRING         COMMENT 'Original transaction ID',
    merchant_id     STRING,
    dispute_reason  STRING         COMMENT 'FRAUD | DUPLICATE | SERVICE | OTHER',
    chargeback_ref  STRING,
    dispute_amount  DECIMAL(18, 2),
    raised_by       STRING,
    resolution      STRING         COMMENT 'WIN | LOSS | PENDING',
    resolved_ts     TIMESTAMP
)
PARTITIONED BY (dt STRING)
STORED AS ORC
TBLPROPERTIES ('transactional' = 'false');

INSERT OVERWRITE TABLE chargeback_events
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    d.chargeback_id,
    d.txn_id,
    d.merchant_id,
    d.dispute_reason,
    d.chargeback_ref,
    d.dispute_amount,
    d.raised_by,
    CASE
        WHEN d.dispute_amount > 5000 THEN 'ESCALATED'
        WHEN d.resolution IS NOT NULL THEN d.resolution
        ELSE 'PENDING'
    END AS resolution,
    d.resolved_ts
FROM disputes_raw d
WHERE d.dt = '${hiveconf:run_date}';
