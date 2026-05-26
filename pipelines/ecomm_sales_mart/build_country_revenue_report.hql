-- build_country_revenue_report.hql
-- Owner: ecomm-analytics@ecommerce.io
-- Description: Produces the final country-level revenue report mart by joining the daily
--              sales summary to web traffic statistics and customer segment metadata.
--              Applies revenue ranking, quartile bucketing, and period-over-period lag
--              window functions. A correlated subquery (wrapped in an outer WHERE filter
--              rather than QUALIFY, which is not valid HiveQL) identifies the top-revenue
--              product category per country and attaches it as a denormalised column.
-- Reads:  mart.ecomm_sales_summary    (written by ecomm_sales_mart/build_sales_summary.hql)
--         silver.traffic_stats        (written by silver_logs/compute_traffic_stats.hql)
--         silver.customer_segments    (written by silver_customers pipeline)
-- Writes: mart.country_revenue_report (partitioned by dt)
--
-- Run: hive -hiveconf run_date=2024-01-15 -f build_country_revenue_report.hql

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 2000;
SET hive.exec.max.dynamic.partitions.pernode = 500;
SET hive.auto.convert.join             = true;
SET hive.mapjoin.smalltable.filesize   = 134217728;
SET hive.map.aggr                      = true;

INSERT OVERWRITE TABLE mart.country_revenue_report
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    ranked.country_name,
    ranked.revenue_usd,
    ranked.unique_buyers,
    ranked.avg_order_value,
    ranked.rolling_30d_revenue,
    ranked.request_count,
    ranked.unique_visitors,
    ranked.dominant_segment,
    ranked.top_product_category,
    ranked.order_date,
    RANK() OVER (
        ORDER BY ranked.revenue_usd DESC
    )                                                   AS revenue_rank,
    NTILE(4) OVER (
        ORDER BY ranked.revenue_usd DESC
    )                                                   AS revenue_quartile,
    LAG(ranked.revenue_usd, 1) OVER (
        PARTITION BY ranked.country_name
        ORDER BY ranked.order_date
    )                                                   AS prev_period_revenue
FROM (
    -- Join the three source tables at country grain and attach the top product
    -- category per country from a pre-filtered subquery (rn = 1 pattern because
    -- HiveQL does not support QUALIFY).
    SELECT
        country_agg.country_name,
        country_agg.revenue_usd,
        country_agg.unique_buyers,
        country_agg.avg_order_value,
        country_agg.rolling_30d_revenue,
        country_agg.order_date,
        COALESCE(ts.request_count, 0)                   AS request_count,
        COALESCE(ts.unique_visitors, 0)                 AS unique_visitors,
        segs.dominant_segment,
        top_cat.product_category                        AS top_product_category
    FROM (
        -- Collapse the sales summary to one row per country per run date.
        -- rolling_30d_revenue is already a window result from the upstream mart;
        -- take the MAX to carry forward the most recent rolling value per country.
        SELECT
            s.country                                   AS country_name,
            SUM(s.revenue_usd)                          AS revenue_usd,
            COUNT(DISTINCT s.order_number)              AS unique_buyers,
            AVG(s.avg_order_value)                      AS avg_order_value,
            MAX(s.rolling_30d_revenue)                  AS rolling_30d_revenue,
            s.order_date
        FROM mart.ecomm_sales_summary s
        WHERE s.dt = '${hiveconf:run_date}'
        GROUP BY
            s.country,
            s.order_date
    ) country_agg
    LEFT JOIN (
        -- Traffic stats are already aggregated at country+response_code grain;
        -- roll up to pure country grain for the join.
        SELECT
            ts_inner.country_name,
            SUM(ts_inner.request_count)                 AS request_count,
            SUM(ts_inner.unique_visitors)               AS unique_visitors
        FROM silver.traffic_stats ts_inner
        WHERE ts_inner.dt = '${hiveconf:run_date}'
        GROUP BY
            ts_inner.country_name
    ) ts
        ON  country_agg.country_name = ts.country_name
    LEFT JOIN (
        -- Derive the single most common segment label per country.
        -- Use ROW_NUMBER rather than MAX/MIN so the result is deterministic
        -- when multiple segments have equal frequency.
        SELECT
            seg_ranked.country,
            seg_ranked.customer_segment                 AS dominant_segment
        FROM (
            SELECT
                seg_count.country,
                seg_count.customer_segment,
                ROW_NUMBER() OVER (
                    PARTITION BY seg_count.country
                    ORDER BY seg_count.segment_count DESC
                )                                       AS seg_rn
            FROM (
                SELECT
                    country,
                    customer_segment,
                    COUNT(*)                            AS segment_count
                FROM silver.customer_segments
                WHERE dt = '${hiveconf:run_date}'
                GROUP BY
                    country,
                    customer_segment
            ) seg_count
        ) seg_ranked
        WHERE seg_ranked.seg_rn = 1
    ) segs
        ON  country_agg.country_name = segs.country
    LEFT JOIN (
        -- Top product category per country by revenue_usd.
        -- ROW_NUMBER inside a subquery, filtered to rn = 1 in the outer WHERE,
        -- is the valid HiveQL substitute for QUALIFY.
        SELECT
            cat_ranked.country,
            cat_ranked.product_category
        FROM (
            SELECT
                cat_agg.country,
                cat_agg.product_category,
                ROW_NUMBER() OVER (
                    PARTITION BY cat_agg.country
                    ORDER BY cat_agg.cat_revenue DESC
                )                                       AS cat_rn
            FROM (
                SELECT
                    s_cat.country,
                    s_cat.product_category,
                    SUM(s_cat.revenue_usd)              AS cat_revenue
                FROM mart.ecomm_sales_summary s_cat
                WHERE s_cat.dt = '${hiveconf:run_date}'
                GROUP BY
                    s_cat.country,
                    s_cat.product_category
            ) cat_agg
        ) cat_ranked
        WHERE cat_ranked.cat_rn = 1
    ) top_cat
        ON  country_agg.country_name = top_cat.country
) ranked;
