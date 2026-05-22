-- settlement_staging.hql
-- Intermediate staging table for reconciliation step
-- Populated before revenue roll-up runs

INSERT INTO TABLE settlement_staging
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    t.txn_id,
    t.merchant_id,
    t.txn_amount,
    t.txn_currency,
    t.status,
    CASE
        WHEN t.txn_amount > 10000 THEN 'HIGH_VALUE'
        WHEN t.txn_amount > 1000  THEN 'STANDARD'
        ELSE                           'MICRO'
    END                                            AS value_band,
    s.settlement_ref
FROM raw_transactions t
LEFT JOIN settlement_refs s
    ON t.txn_id = s.txn_id
WHERE t.dt = '${hiveconf:run_date}'
  AND t.status IN ('SETTLED', 'PENDING');
