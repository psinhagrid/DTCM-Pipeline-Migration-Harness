-- merchant_profiles.hql
-- Merchant dimension table — updated daily from CRM sync feed
-- Owner: merchant-data-team

CREATE TABLE IF NOT EXISTS merchant_profiles (
    merchant_id   STRING         COMMENT 'Merchant entity ID',
    merchant_name STRING,
    tier_code     STRING         COMMENT 'GOLD | SILVER | BRONZE',
    region_code   STRING,
    onboard_date  DATE,
    is_active     BOOLEAN,
    contract_type STRING,
    credit_limit  DECIMAL(18, 2),
    account_mgr   STRING,
    updated_ts    TIMESTAMP
)
PARTITIONED BY (dt STRING)
STORED AS ORC
TBLPROPERTIES ('transactional' = 'false');
