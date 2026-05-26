-- build_sales_summary.hql
-- Owner: ecomm-analytics@ecommerce.io
-- Description: Builds the core e-commerce sales summary mart by joining enriched orders to
--              masked customers, product catalog, and live currency rates. Converts all sale
--              amounts to USD via the UDF, derives customer segments from a pre-aggregated
--              subquery, and computes country+category revenue aggregates alongside a
--              30-day rolling revenue window. Output is partitioned by run date and region.
-- Reads:  silver.orders_enriched      (written by silver_orders pipeline)
--         silver.customers_masked     (written by silver_customers pipeline)
--         bronze.products             (written by bronze_ingestion pipeline)
--         bronze.currency_rates       (written by bronze_ingestion pipeline)
-- Writes: mart.ecomm_sales_summary   (partitioned by dt, region)
--
-- Run: hive -hiveconf run_date=2024-01-15 -hiveconf region=EMEA -f build_sales_summary.hql

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 4000;
SET hive.exec.max.dynamic.partitions.pernode = 1000;
SET hive.auto.convert.join             = true;
SET hive.mapjoin.smalltable.filesize   = 134217728;
SET hive.map.aggr                      = true;
SET hive.groupby.skewindata            = true;

INSERT OVERWRITE TABLE mart.ecomm_sales_summary
PARTITION (dt = '${hiveconf:run_date}', region = '${hiveconf:region}')
SELECT
    revenue_window.order_number,
    revenue_window.order_date,
    revenue_window.order_mode,
    revenue_window.units,
    revenue_window.customer_name,
    revenue_window.city,
    revenue_window.country,
    revenue_window.customer_segment,
    revenue_window.product_name,
    revenue_window.product_category,
    revenue_window.sale_price,
    revenue_window.currency,
    revenue_window.sale_price_usd,
    revenue_window.revenue_usd,
    revenue_window.unique_buyers,
    revenue_window.avg_order_value,
    SUM(revenue_window.revenue_usd) OVER (
        PARTITION BY revenue_window.country
        ORDER BY revenue_window.order_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    )                                                   AS rolling_30d_revenue
FROM (
    -- Country + category aggregates alongside per-row columns.
    -- Window functions cannot be nested inside aggregates in HiveQL, so the
    -- SUM/COUNT/AVG group-by results are computed here and the rolling window
    -- is applied in the outer SELECT.
    SELECT
        o.order_number,
        o.order_date,
        o.order_mode,
        o.units,
        c.customer_name,
        c.city,
        c.country,
        segs.customer_segment,
        p.product_name,
        p.product_category,
        o.sale_price,
        o.currency,
        udf_sales_price_usd(
            o.currency,
            cr.rate_to_usd,
            o.sale_price
        )                                               AS sale_price_usd,
        SUM(
            udf_sales_price_usd(o.currency, cr.rate_to_usd, o.sale_price)
        ) OVER (
            PARTITION BY c.country, p.product_category
        )                                               AS revenue_usd,
        COUNT(DISTINCT o.customer_id) OVER (
            PARTITION BY c.country, p.product_category
        )                                               AS unique_buyers,
        AVG(
            udf_sales_price_usd(o.currency, cr.rate_to_usd, o.sale_price)
        ) OVER (
            PARTITION BY c.country, p.product_category
        )                                               AS avg_order_value
    FROM silver.orders_enriched o
    JOIN silver.customers_masked c
        ON  o.customer_id = c.customer_id
    JOIN bronze.products p
        ON  o.product_id  = p.product_id
    JOIN bronze.currency_rates cr
        ON  o.currency    = cr.currency_code
        AND cr.dt         = '${hiveconf:run_date}'
    LEFT JOIN (
        -- Derive the dominant segment label per customer from the segments table.
        -- A LEFT JOIN here means customers absent from the segments table still
        -- appear in the output with a NULL segment rather than being silently dropped.
        SELECT
            customer_id,
            country,
            customer_segment
        FROM silver.customer_segments
        WHERE dt = '${hiveconf:run_date}'
    ) segs
        ON  o.customer_id = segs.customer_id
    WHERE o.dt            = '${hiveconf:run_date}'
      AND o.order_status  != 'CANCELLED'
      AND o.sale_price    IS NOT NULL
      AND o.sale_price    > 0
      AND cr.rate_to_usd  > 0
) revenue_window;
