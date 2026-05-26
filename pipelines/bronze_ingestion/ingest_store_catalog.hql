-- Owner: data-engineering@ecommerce.io
-- Reads: external.raw_customers, external.raw_products, external.raw_orders
-- Writes: bronze.store_customers, bronze.products, bronze.store_orders
--
-- Purpose: Ingests the three core e-commerce catalog tables — customers,
--          products, and orders — from their respective external source tables
--          into the bronze layer in a single coordinated run. No transformations
--          or PII masking are applied here; that happens in the silver layer.
--
-- Run: hive -hiveconf run_date=2024-01-15 -f ingest_store_catalog.hql

SET hive.exec.dynamic.partition=true;
SET hive.exec.dynamic.partition.mode=nonstrict;
SET hive.exec.max.dynamic.partitions=1000;
SET hive.exec.max.dynamic.partitions.pernode=500;

-- ============================================================
-- 1. Customers
-- ============================================================
INSERT OVERWRITE TABLE bronze.store_customers
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    customer_id,
    customer_name,
    address,
    city,
    postalcode,
    country,
    phone,
    email,
    credit_card
FROM
    external.raw_customers
WHERE
    customer_id IS NOT NULL;

-- ============================================================
-- 2. Products
-- ============================================================
INSERT OVERWRITE TABLE bronze.products
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    product_id,
    product_name,
    product_category
FROM
    external.raw_products
WHERE
    product_id IS NOT NULL;

-- ============================================================
-- 3. Orders
-- ============================================================
INSERT OVERWRITE TABLE bronze.store_orders
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    order_number,
    customer_id,
    product_id,
    order_date,
    units,
    sale_price,
    currency,
    order_mode
FROM
    external.raw_orders
WHERE
    order_number IS NOT NULL;
