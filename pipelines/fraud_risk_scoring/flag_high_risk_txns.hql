-- flag_high_risk_txns.hql
-- Owner: fraud-platform-team
-- Description: Applies a risk-score threshold filter over risk.risk_scores to produce the final
--              fraud flag set for the run date. Also cross-references a previously flagged
--              merchant subquery so repeat offenders are always flagged regardless of score.
--              Output feeds mart.exec_dashboard via the executive_reporting pipeline.
-- Reads:  risk.risk_scores   (written by fraud_risk_scoring/score_transactions.hql)
-- Writes: risk.fraud_flags   (partitioned by dt)

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 2000;

INSERT OVERWRITE TABLE risk.fraud_flags
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    flagged.txn_id,
    flagged.user_id,
    flagged.merchant_id,
    flagged.txn_amount,
    flagged.txn_currency,
    flagged.channel,
    flagged.risk_score,
    flagged.fraud_probability,
    flagged.velocity_flag,
    flagged.is_blacklisted_merchant,
    udf_fraud_category(
        flagged.risk_score,
        flagged.fraud_probability
    )                                                AS fraud_category,
    flagged.flag_reason,
    flagged.txn_ts,
    flagged.dt
FROM (
    SELECT
        rs.txn_id,
        rs.user_id,
        rs.merchant_id,
        rs.txn_amount,
        rs.txn_currency,
        rs.channel,
        rs.risk_score,
        rs.fraud_probability,
        rs.velocity_flag,
        rs.is_blacklisted_merchant,
        rs.txn_ts,
        rs.dt,
        CASE
            WHEN rs.risk_score        > '${hiveconf:risk_threshold}'
                 AND rs.fraud_probability > 0.7   THEN 'HIGH_SCORE_HIGH_PROB'
            WHEN rs.is_blacklisted_merchant = 1   THEN 'BLACKLISTED_MERCHANT'
            WHEN prev_flagged.merchant_id IS NOT NULL THEN 'REPEAT_OFFENDER'
            ELSE 'THRESHOLD_BREACH'
        END                                          AS flag_reason
    FROM risk.risk_scores rs
    LEFT JOIN (
        -- Merchants that were flagged on any prior date within a lookback window
        SELECT DISTINCT merchant_id
        FROM risk.fraud_flags
        WHERE dt >= DATE_SUB('${hiveconf:run_date}', 30)
          AND dt <  '${hiveconf:run_date}'
    ) prev_flagged
        ON rs.merchant_id = prev_flagged.merchant_id
    WHERE rs.dt = '${hiveconf:run_date}'
      AND (
            rs.risk_score        > '${hiveconf:risk_threshold}'
         OR rs.is_blacklisted_merchant = 1
         OR prev_flagged.merchant_id IS NOT NULL
      )
) flagged;
