-- build_ops_report.hql
-- Owner: bi-platform-team
-- Description: Produces the daily operations summary mart. Combines raw transaction volumes
--              with settlement throughput and risk scores to generate SLA breach indicators,
--              processing quartile buckets, and ops-health KPI labels. Nested subqueries handle
--              pre-aggregation before windowing to control data skew on high-volume merchants.
-- Reads:  raw.transactions    (written by raw_events_ingest/ingest_transactions.hql)
--         settlement_facts    (written by merchant_settlement/settlement_facts.hql)
--         risk.risk_scores    (written by fraud_risk_scoring/score_transactions.hql)
-- Writes: mart.ops_summary    (partitioned by dt)

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 2000;

INSERT OVERWRITE TABLE mart.ops_summary
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    final.merchant_id,
    final.channel,
    final.txn_count,
    final.total_amount,
    final.settled_amount,
    final.avg_risk_score,
    final.p50_txn_amount,
    final.p95_txn_amount,
    final.amount_quartile,
    final.high_risk_count,
    final.settlement_lag_secs,
    udf_ops_status(
        final.txn_count,
        final.settled_amount,
        final.avg_risk_score
    )                                                AS ops_status,
    udf_sla_breach(
        final.settlement_lag_secs,
        final.high_risk_count,
        final.txn_count
    )                                                AS sla_breach_flag,
    final.dt
FROM (
    SELECT
        merchant_agg.merchant_id,
        merchant_agg.channel,
        merchant_agg.txn_count,
        merchant_agg.total_amount,
        merchant_agg.avg_risk_score,
        merchant_agg.high_risk_count,
        merchant_agg.p50_txn_amount,
        merchant_agg.p95_txn_amount,
        merchant_agg.dt,
        COALESCE(sf_agg.settled_amount, 0)           AS settled_amount,
        COALESCE(sf_agg.settlement_lag_secs, 0)      AS settlement_lag_secs,
        NTILE(4) OVER (
            PARTITION BY merchant_agg.channel
            ORDER BY merchant_agg.total_amount DESC
        )                                            AS amount_quartile
    FROM (
        -- Pre-aggregate transactions per merchant + channel to reduce fan-out in outer join
        -- PERCENTILE_APPROX is a plain aggregate; computed here alongside other aggregates
        SELECT
            t.merchant_id,
            t.channel,
            t.dt,
            COUNT(*)                                 AS txn_count,
            SUM(t.txn_amount)                        AS total_amount,
            AVG(rs.risk_score)                       AS avg_risk_score,
            SUM(CASE WHEN rs.risk_score > '${hiveconf:risk_threshold}' THEN 1 ELSE 0 END)
                                                     AS high_risk_count,
            PERCENTILE_APPROX(t.txn_amount, 0.50)   AS p50_txn_amount,
            PERCENTILE_APPROX(t.txn_amount, 0.95)   AS p95_txn_amount
        FROM raw.transactions t
        LEFT JOIN risk.risk_scores rs
            ON  t.txn_id = rs.txn_id
            AND rs.dt    = '${hiveconf:run_date}'
        WHERE t.dt = '${hiveconf:run_date}'
        GROUP BY
            t.merchant_id,
            t.channel,
            t.dt
    ) merchant_agg
    LEFT JOIN (
        -- Pre-aggregate settlement facts to get total settled amount and average processing lag
        SELECT
            sf.merchant_id,
            sf.channel,
            SUM(sf.txn_amount)                       AS settled_amount,
            AVG(
                UNIX_TIMESTAMP(sf.dt) -
                UNIX_TIMESTAMP(DATE_FORMAT(sf.txn_ts, 'yyyy-MM-dd'))
            ) * 86400                                AS settlement_lag_secs
        FROM settlement_facts sf
        WHERE sf.dt = '${hiveconf:run_date}'
          AND sf.status IN ('SETTLED', 'REVERSED')
        GROUP BY
            sf.merchant_id,
            sf.channel
    ) sf_agg
        ON  merchant_agg.merchant_id = sf_agg.merchant_id
        AND merchant_agg.channel     = sf_agg.channel
) final;
