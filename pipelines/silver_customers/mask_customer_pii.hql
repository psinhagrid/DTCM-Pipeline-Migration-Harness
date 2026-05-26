-- mask_customer_pii.hql
-- Owner: data-privacy-team
-- Reads:  bronze.store_customers  (written by bronze_ingestion pipeline)
-- Writes: silver.customers_masked (partitioned by dt)
--
-- Purpose: Applies PII masking UDFs to sensitive customer fields (phone, address,
--          credit_card) and standardises the country code via udf_curate_country.
--          Rows without a valid customer_id or email are excluded to prevent
--          unidentifiable records from propagating into the silver layer.
--
-- Run: hive -hiveconf run_date=2024-01-15 -f mask_customer_pii.hql

SET hive.exec.dynamic.partition        = true;
SET hive.exec.dynamic.partition.mode   = nonstrict;
SET hive.exec.max.dynamic.partitions   = 5000;
SET hive.exec.max.dynamic.partitions.pernode = 2500;

INSERT OVERWRITE TABLE silver.customers_masked
PARTITION (dt = '${hiveconf:run_date}')
SELECT
    customer_id,
    customer_name,
    city,
    postalcode,
    email,
    udf_mask_pii(phone)          AS phone,
    udf_mask_pii(address)        AS address,
    udf_mask_pii(credit_card)    AS credit_card,
    udf_curate_country(country)  AS country
FROM
    bronze.store_customers
WHERE
    dt            = '${hiveconf:run_date}'
    AND customer_id IS NOT NULL
    AND email       IS NOT NULL
    AND email       != '';
