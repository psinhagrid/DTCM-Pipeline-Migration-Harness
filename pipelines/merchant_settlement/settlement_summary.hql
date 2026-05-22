-- settlement_summary.hql
-- Daily merchant settlement summary with chargeback metrics
-- Reads: settlement_facts, merchant_profiles
-- Writes: settlement_summary (downstream: finance_reporting_dag, risk_dashboard_dag)

INSERT OVERWRITE TABLE settlement_summary
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    f.merchant_id,
    m.merchant_name,
    m.tier_code,
    COUNT(*)                                        AS total_txns,
    SUM(f.amount_usd)                               AS gross_settlement_usd,
    SUM(CASE WHEN f.status = 'REVERSED'
             THEN f.amount_usd ELSE 0 END)          AS reversal_amount_usd,
    SUM(f.amount_usd) - SUM(
        CASE WHEN f.status = 'REVERSED'
             THEN f.amount_usd ELSE 0 END)          AS net_settlement_usd,
    COUNT(f.chargeback_ref)                         AS chargeback_count,
    AVG(f.risk_score)                               AS avg_risk_score,
    MAX(f.txn_rank)                                 AS max_txn_rank,
    udf_settlement_fee(SUM(f.amount_usd), m.tier_code) AS settlement_fee_usd
FROM settlement_facts f
JOIN merchant_profiles m
    ON  f.merchant_id = m.merchant_id
    AND m.dt          = '${hiveconf:run_date}'
WHERE f.dt = '${hiveconf:run_date}'
GROUP BY
    f.merchant_id,
    m.merchant_name,
    m.tier_code;
