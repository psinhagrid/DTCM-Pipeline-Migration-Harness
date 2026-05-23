-- revenue_daily.hql
-- Daily revenue aggregation — core transform for this pipeline
-- Reads: raw_transactions, merchant_profiles
-- Writes: revenue_daily (partitioned managed table)

INSERT OVERWRITE TABLE revenue_daily
PARTITION (dt = '${hiveconf:run_date}', channel = '${hiveconf:channel}')
SELECT
    t.merchant_id,
    SUM(t.txn_amount)                             AS total_revenue,
    COUNT(*)                                       AS txn_count,
    AVG(t.txn_amount)                              AS avg_txn,
    udf_currency_normalize(t.txn_currency, 'USD') AS normalised_currency,
    udf_merchant_tier(m.tier_code)                AS merchant_tier,
    m.region_code
FROM raw.transactions t
JOIN merchant_profiles m
    ON  t.merchant_id = m.merchant_id
    AND m.dt          = '${hiveconf:run_date}'
WHERE t.dt     = '${hiveconf:run_date}'
  AND t.status = 'SETTLED'
GROUP BY
    t.merchant_id,
    t.txn_currency,
    m.tier_code,
    m.region_code;
