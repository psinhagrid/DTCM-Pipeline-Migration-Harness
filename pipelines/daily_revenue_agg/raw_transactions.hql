-- raw_transactions.hql
-- Source: ANA cluster / Hive warehouse
-- Owner: data-platform-team
-- Ingested via Kafka → Hive bridge, refreshed hourly

CREATE TABLE IF NOT EXISTS raw_transactions (
    txn_id        STRING         COMMENT 'Unique transaction identifier',
    merchant_id   STRING         COMMENT 'Merchant entity ID',
    txn_amount    DECIMAL(18, 2) COMMENT 'Transaction amount in source currency',
    txn_currency  STRING         COMMENT 'ISO 4217 currency code',
    txn_ts        TIMESTAMP      COMMENT 'Transaction timestamp UTC',
    status        STRING         COMMENT 'SETTLED | PENDING | FAILED | REVERSED',
    channel       STRING         COMMENT 'POS | ONLINE | MOBILE | ATM',
    region        STRING         COMMENT 'Geographic region code'
)
PARTITIONED BY (dt STRING, region STRING)
STORED AS ORC
TBLPROPERTIES (
    'transactional' = 'false',
    'orc.compress'  = 'SNAPPY'
);
