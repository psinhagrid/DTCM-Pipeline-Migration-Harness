-- build_exec_dashboard.hql
-- Owner: bi-platform-team
-- Description: Assembles the executive dashboard mart by joining four upstream pipeline outputs:
--              daily revenue aggregates, settlement facts, fraud flags, and user segments.
--              Computes a rolling 30-day revenue window and applies KPI UDFs for exec-level
--              metrics. Cross-joins to reporting.targets for variance tracking.
-- Reads:  revenue_daily               (written by daily_revenue_agg/revenue_daily.hql)
--         settlement_facts            (written by merchant_settlement/settlement_facts.hql)
--         risk.fraud_flags            (written by fraud_risk_scoring/flag_high_risk_txns.hql)
--         enriched.user_segments      (written by user_activity_enrichment/compute_user_segments.hql)
--         reporting.targets           (cross-database join — reporting schema)
-- Writes: mart.exec_dashboard         (partitioned by dt, region)

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 1000;

INSERT OVERWRITE TABLE mart.exec_dashboard
PARTITION (dt = '${hiveconf:run_date}', region = '${hiveconf:region}')
SELECT
    kpi.region_code,
    kpi.merchant_tier,
    kpi.total_revenue,
    kpi.txn_count,
    kpi.settled_amount,
    kpi.fraud_txn_count,
    kpi.fraud_rate,
    kpi.active_users,
    kpi.high_ltv_users,
    kpi.rolling_30d_revenue,
    udf_executive_kpi(
        kpi.total_revenue,
        kpi.fraud_rate,
        kpi.settlement_rate
    )                                                AS exec_kpi_score,
    udf_region_benchmark(
        kpi.region_code,
        kpi.total_revenue,
        tgt.target_revenue
    )                                                AS region_benchmark,
    kpi.settlement_rate,
    tgt.target_revenue,
    tgt.target_fraud_rate,
    kpi.dt
FROM (
    SELECT
        rev.region_code,
        rev.merchant_tier,
        rev.dt,
        SUM(rev.total_revenue)                       AS total_revenue,
        SUM(rev.txn_count)                           AS txn_count,
        SUM(sf.txn_amount)                           AS settled_amount,
        COUNT(ff.txn_id)                             AS fraud_txn_count,
        COUNT(DISTINCT us.user_id)                   AS active_users,
        SUM(CASE WHEN us.ltv_band = 'HIGH' THEN 1 ELSE 0 END) AS high_ltv_users,
        CASE
            WHEN SUM(rev.txn_count) > 0
            THEN COUNT(ff.txn_id) / SUM(rev.txn_count)
            ELSE 0
        END                                          AS fraud_rate,
        CASE
            WHEN SUM(rev.total_revenue) > 0
            THEN SUM(sf.txn_amount) / SUM(rev.total_revenue)
            ELSE 0
        END                                          AS settlement_rate,
        SUM(rev.total_revenue) OVER (
            PARTITION BY rev.region_code
            ORDER BY rev.dt
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        )                                            AS rolling_30d_revenue
    FROM revenue_daily rev
    LEFT JOIN settlement_facts sf
        ON  rev.merchant_id = sf.merchant_id
        AND sf.dt           = '${hiveconf:run_date}'
        AND sf.region_code  = '${hiveconf:region}'
    LEFT JOIN risk.fraud_flags ff
        ON  ff.dt           = '${hiveconf:run_date}'
    LEFT JOIN enriched.user_segments us
        ON  us.dt           = '${hiveconf:run_date}'
        AND us.segment      = '${hiveconf:segment_version}'
    WHERE rev.dt      = '${hiveconf:run_date}'
      AND rev.channel = '${hiveconf:channel}'
    GROUP BY
        rev.region_code,
        rev.merchant_tier,
        rev.dt
) kpi
JOIN reporting.targets tgt
    ON  kpi.region_code = tgt.region
    AND tgt.target_dt   = '${hiveconf:run_date}'
WHERE kpi.region_code = '${hiveconf:region}';
