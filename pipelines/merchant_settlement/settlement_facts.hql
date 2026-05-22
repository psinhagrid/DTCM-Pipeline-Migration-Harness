-- settlement_facts.hql
-- Core settlement fact table — one row per settled transaction
-- Owner: payments-platform-team
-- Reads: raw_transactions, merchant_profiles, chargeback_events

INSERT OVERWRITE TABLE settlement_facts
PARTITION (dt = '${hiveconf:run_date}', region = '${hiveconf:region}')
SELECT
    t.txn_id,
    t.merchant_id,
    t.txn_amount,
    t.txn_currency,
    udf_currency_normalize(t.txn_currency, 'USD')  AS amount_usd,
    t.channel,
    t.status,
    m.tier_code,
    m.region_code,
    udf_merchant_tier(m.tier_code)                  AS tier_label,
    udf_risk_score(t.txn_amount, m.tier_code)       AS risk_score,
    RANK() OVER (
        PARTITION BY t.merchant_id
        ORDER BY t.txn_amount DESC
    )                                               AS txn_rank,
    ROW_NUMBER() OVER (
        PARTITION BY t.merchant_id, t.channel
        ORDER BY t.txn_ts ASC
    )                                               AS seq_num,
    c.chargeback_ref,
    c.dispute_reason
FROM raw_transactions t
JOIN merchant_profiles m
    ON  t.merchant_id = m.merchant_id
    AND m.dt          = '${hiveconf:run_date}'
LEFT JOIN chargeback_events c
    ON  t.txn_id  = c.txn_id
    AND c.dt      = '${hiveconf:run_date}'
WHERE t.dt     = '${hiveconf:run_date}'
  AND t.status IN ('SETTLED', 'REVERSED');
