-- flag_orphan_orders.hql
-- Owner: data-quality-team
-- Reads:  silver.orders_enriched   (written by silver_orders/enrich_orders_currency.hql)
--         bronze.products           (written by bronze_ingestion pipeline)
--         silver.customers_masked   (written by silver_customers/mask_customer_pii.hql)
-- Writes: silver.orphan_orders      (partitioned by dt)
--
-- Purpose: Identifies enriched orders that reference a product not present in the
--          current-day bronze product catalogue, or whose customer_id has no
--          corresponding masked customer record. Each orphaned row is tagged with
--          a human-readable orphan_reason for downstream triage. Orders that are
--          orphaned on both dimensions receive the combined label.
--
-- Run: hive -hiveconf run_date=2024-01-15 -f flag_orphan_orders.hql

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 5000;
SET hive.exec.max.dynamic.partitions.pernode = 2500;

INSERT OVERWRITE TABLE silver.orphan_orders
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    oe.order_number,
    oe.customer_id,
    oe.product_id,
    oe.order_date,
    CASE
        WHEN p.product_id IS NULL AND cm.customer_id IS NULL
            THEN 'MISSING_PRODUCT|MISSING_CUSTOMER'
        WHEN p.product_id IS NULL
            THEN 'MISSING_PRODUCT'
        WHEN cm.customer_id IS NULL
            THEN 'MISSING_CUSTOMER'
        ELSE NULL
    END                                                AS orphan_reason,
    '${hiveconf:run_date}'                             AS detected_dt
FROM
    silver.orders_enriched oe
LEFT JOIN (
    SELECT DISTINCT product_id
    FROM   bronze.products
    WHERE  dt = '${hiveconf:run_date}'
) p
    ON oe.product_id = p.product_id
LEFT JOIN silver.customers_masked cm
    ON  oe.customer_id = cm.customer_id
    AND cm.dt          = '${hiveconf:run_date}'
WHERE
    oe.dt = '${hiveconf:run_date}'
    AND (
        p.product_id   IS NULL
        OR cm.customer_id IS NULL
    );
