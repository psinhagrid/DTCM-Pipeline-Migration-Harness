-- curate_customer_segments.hql
-- Owner: customer-analytics-team
-- Reads:  silver.customers_masked  (written by silver_customers/mask_customer_pii.hql)
--         bronze.store_orders      (written by bronze_ingestion pipeline)
-- Writes: silver.customer_segments (partitioned by dt)
--
-- Purpose: Joins masked customer records with order history to compute per-customer
--          aggregates (order count, total spend, last order date). Assigns a spend-based
--          segment label (VIP / REGULAR / NEW) and a within-country spend rank via a
--          window function. Only customers with at least one order are included.
--
-- Run: hive -hiveconf run_date=2024-01-15 -f curate_customer_segments.hql

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 5000;
SET hive.exec.max.dynamic.partitions.pernode = 2500;

INSERT OVERWRITE TABLE silver.customer_segments
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    ranked.customer_id,
    ranked.customer_name,
    ranked.email,
    ranked.country,
    ranked.city,
    ranked.order_count,
    ranked.total_spend,
    ranked.last_order_date,
    CASE
        WHEN ranked.total_spend > 10000 THEN 'VIP'
        WHEN ranked.total_spend > 1000  THEN 'REGULAR'
        ELSE                                 'NEW'
    END                                                AS customer_segment,
    RANK() OVER (
        PARTITION BY ranked.country
        ORDER BY ranked.total_spend DESC
    )                                                  AS country_rank
FROM (
    SELECT
        c.customer_id,
        c.customer_name,
        c.email,
        c.country,
        c.city,
        COUNT(o.order_number)                          AS order_count,
        SUM(o.sale_price)                              AS total_spend,
        MAX(o.order_date)                              AS last_order_date
    FROM silver.customers_masked c
    JOIN bronze.store_orders o
        ON  c.customer_id = o.customer_id
        AND o.dt          = '${hiveconf:run_date}'
    WHERE
        c.dt = '${hiveconf:run_date}'
    GROUP BY
        c.customer_id,
        c.customer_name,
        c.email,
        c.country,
        c.city
    HAVING COUNT(o.order_number) >= 1
) ranked;
