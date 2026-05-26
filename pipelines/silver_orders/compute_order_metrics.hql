-- compute_order_metrics.hql
-- Owner: commerce-data-team
-- Reads:  silver.orders_enriched    (written by silver_orders/enrich_orders_currency.hql)
--         silver.customer_segments  (written by silver_customers/curate_customer_segments.hql)
-- Writes: silver.order_metrics      (partitioned by dt)
--
-- Purpose: Enriches each order row with customer segment metadata and three window-based
--          metrics: a running cumulative spend per customer, the previous order value via
--          LAG, and a recency rank (1 = most recent). Also joins a product-level order
--          frequency subquery so downstream models can weight orders by catalogue
--          popularity without a separate aggregation step.
--
-- Run: hive -hiveconf run_date=2024-01-15 -f compute_order_metrics.hql

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 5000;
SET hive.exec.max.dynamic.partitions.pernode = 2500;

INSERT OVERWRITE TABLE silver.order_metrics
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    windowed.order_number,
    windowed.customer_id,
    windowed.product_id,
    windowed.order_date,
    windowed.units,
    windowed.sale_price,
    windowed.currency,
    windowed.sale_price_usd,
    windowed.customer_segment,
    windowed.country_rank,
    windowed.total_spend,
    SUM(windowed.sale_price_usd) OVER (
        PARTITION BY windowed.customer_id
        ORDER BY windowed.order_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                  AS cumulative_spend,
    LAG(windowed.sale_price_usd, 1) OVER (
        PARTITION BY windowed.customer_id
        ORDER BY windowed.order_date
    )                                                  AS prev_order_value,
    ROW_NUMBER() OVER (
        PARTITION BY windowed.customer_id
        ORDER BY windowed.order_date DESC
    )                                                  AS order_recency_rank,
    prod_counts.product_order_count
FROM (
    SELECT
        oe.order_number,
        oe.customer_id,
        oe.product_id,
        oe.order_date,
        oe.units,
        oe.sale_price,
        oe.currency,
        oe.sale_price_usd,
        cs.customer_segment,
        cs.country_rank,
        cs.total_spend
    FROM silver.orders_enriched oe
    JOIN silver.customer_segments cs
        ON  oe.customer_id = cs.customer_id
        AND cs.dt          = '${hiveconf:run_date}'
    WHERE
        oe.dt = '${hiveconf:run_date}'
) windowed
JOIN (
    SELECT
        product_id,
        COUNT(*) AS product_order_count
    FROM silver.orders_enriched
    WHERE dt = '${hiveconf:run_date}'
    GROUP BY product_id
) prod_counts
    ON windowed.product_id = prod_counts.product_id;
