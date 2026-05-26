-- enrich_orders_currency.hql
-- Owner: commerce-data-team
-- Reads:  bronze.store_orders    (written by bronze_ingestion pipeline)
--         bronze.currency_rates  (written by bronze_ingestion/ingest_currency_rates.hql)
-- Writes: silver.orders_enriched (partitioned by dt)
--
-- Purpose: Joins raw orders with the daily currency rate snapshot to append a
--          USD-normalised sale price via udf_sales_price_usd. Standardises the
--          order_date string from MM/dd/yyyy to ISO yyyy-MM-dd. Rows flagged with
--          order_mode = 'DELETE' are excluded to prevent logical deletes from
--          polluting downstream aggregations.
--
-- Run: hive -hiveconf run_date=2024-01-15 -f enrich_orders_currency.hql

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 5000;
SET hive.exec.max.dynamic.partitions.pernode = 2500;

INSERT OVERWRITE TABLE silver.orders_enriched
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    o.order_number,
    o.customer_id,
    o.product_id,
    from_unixtime(
        unix_timestamp(o.order_date, 'MM/dd/yyyy'),
        'yyyy-MM-dd'
    )                                                  AS order_date,
    o.units,
    o.sale_price,
    o.currency,
    o.order_mode,
    udf_sales_price_usd(
        o.currency,
        cr.rate_to_usd,
        o.sale_price
    )                                                  AS sale_price_usd
FROM
    bronze.store_orders o
JOIN bronze.currency_rates cr
    ON  o.currency       = cr.currency_code
    AND cr.effective_date = '${hiveconf:run_date}'
    AND cr.dt             = '${hiveconf:run_date}'
WHERE
    o.dt         = '${hiveconf:run_date}'
    AND o.order_mode != 'DELETE';
