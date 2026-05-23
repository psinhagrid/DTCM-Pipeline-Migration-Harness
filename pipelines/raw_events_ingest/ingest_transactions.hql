-- ingest_transactions.hql
-- Owner: data-ingestion-team
-- Description: Lands raw payment-gateway feed rows into the managed raw.transactions table.
--              Filters out terminal-error statuses and null amounts before writing.
--              Downstream pipelines (fraud_risk_scoring, merchant_settlement) depend on this table.
-- Reads:  external.payment_gateway_feed  (external table, sourced from payment processor drop)
-- Writes: raw.transactions               (partitioned by dt)

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 2000;

INSERT OVERWRITE TABLE raw.transactions
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    pgf.txn_id,
    pgf.user_id,
    pgf.merchant_id,
    pgf.txn_amount,
    pgf.txn_currency,
    pgf.channel,
    pgf.status,
    pgf.txn_ts,
    pgf.dt
FROM external.payment_gateway_feed pgf
WHERE pgf.dt          = '${hiveconf:run_date}'
  AND pgf.txn_id      IS NOT NULL
  AND pgf.txn_amount  IS NOT NULL
  AND pgf.txn_amount  > 0
  AND pgf.status      NOT IN ('SYSTEM_ERROR', 'GATEWAY_TIMEOUT', 'INVALID_REQUEST');
