-- high_value_merchants.hql
-- Identifies merchants exceeding settlement thresholds
-- Uses subquery to filter top-percentile merchants before joining
-- Reads: settlement_summary, risk_scores_feed (ana_risk.risk_scores)

INSERT OVERWRITE TABLE high_value_merchants
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    s.merchant_id,
    s.merchant_name,
    s.gross_settlement_usd,
    s.net_settlement_usd,
    s.chargeback_count,
    s.avg_risk_score,
    r.risk_band,
    r.watchlist_flag,
    udf_compliance_check(s.merchant_id, s.gross_settlement_usd) AS compliance_status
FROM (
    SELECT *
    FROM settlement_summary
    WHERE dt                  = '${hiveconf:run_date}'
      AND gross_settlement_usd > 100000
      AND chargeback_count     < 10
) s
JOIN ana_risk.risk_scores r
    ON  s.merchant_id = r.merchant_id
    AND r.dt          = '${hiveconf:run_date}'
WHERE s.avg_risk_score < 0.75;
