CREATE SCHEMA IF NOT EXISTS control;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE control.pipeline_watermarks (
    pipeline_name VARCHAR(100) PRIMARY KEY,
    last_watermark TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE control.pipeline_runs (
    run_id BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(30) NOT NULL,
    rows_read BIGINT DEFAULT 0,
    rows_written BIGINT DEFAULT 0,
    error_message TEXT
);

INSERT INTO control.pipeline_watermarks (
    pipeline_name,
    last_watermark
)
VALUES (
    'transactions_incremental',
    '1970-01-01 00:00:00+00'
)
ON CONFLICT (pipeline_name) DO NOTHING;

-- Raw transaction landing layer
CREATE TABLE IF NOT EXISTS raw.transactions (
    transaction_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    merchant_id BIGINT NOT NULL,
    transaction_ts TIMESTAMPTZ NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    currency CHAR(3) NOT NULL,
    status VARCHAR(30) NOT NULL,
    payment_method VARCHAR(30) NOT NULL,
    source_created_at TIMESTAMPTZ NOT NULL,
    source_updated_at TIMESTAMPTZ NOT NULL,
    source_object_key TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_transactions_source_updated_at
    ON raw.transactions(source_updated_at);

-- Ledger of raw objects already loaded into PostgreSQL.
CREATE TABLE IF NOT EXISTS control.ingested_files (
    pipeline_name VARCHAR(100) NOT NULL,
    object_key TEXT NOT NULL,
    etag TEXT,
    row_count BIGINT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (pipeline_name, object_key)
);

-- Reference-data landing layer
CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id BIGINT PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL,
    country_code CHAR(2) NOT NULL,
    source_created_at TIMESTAMPTZ NOT NULL,
    source_updated_at TIMESTAMPTZ NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw.merchants (
    merchant_id BIGINT PRIMARY KEY,
    merchant_name VARCHAR(150) NOT NULL,
    merchant_category VARCHAR(100) NOT NULL,
    country_code CHAR(2) NOT NULL,
    active BOOLEAN NOT NULL,
    source_created_at TIMESTAMPTZ NOT NULL,
    source_updated_at TIMESTAMPTZ NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Composite transaction watermark required by the
-- incremental ingestion implementation.
ALTER TABLE control.pipeline_watermarks
ADD COLUMN IF NOT EXISTS last_transaction_id
BIGINT NOT NULL DEFAULT 0;

-- Partner settlement landing layer
CREATE TABLE IF NOT EXISTS raw.settlements (
    raw_settlement_row_id BIGSERIAL PRIMARY KEY,
    settlement_id VARCHAR(100) NOT NULL,
    merchant_id BIGINT NOT NULL,
    settlement_date DATE NOT NULL,
    currency CHAR(3) NOT NULL,
    transaction_count BIGINT NOT NULL,
    gross_amount NUMERIC(18,2) NOT NULL,
    fees NUMERIC(18,2) NOT NULL,
    net_amount NUMERIC(18,2) NOT NULL,
    source_object_key TEXT NOT NULL,
    source_file_sha256 CHAR(64) NOT NULL,
    source_row_number BIGINT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (
        source_object_key,
        source_row_number
    )
);

CREATE INDEX IF NOT EXISTS idx_raw_settlements_settlement_id
ON raw.settlements(settlement_id);

CREATE INDEX IF NOT EXISTS idx_raw_settlements_grain
ON raw.settlements(
    merchant_id,
    settlement_date,
    currency
);

CREATE TABLE IF NOT EXISTS control.settlement_files (
    object_key TEXT PRIMARY KEY,
    content_sha256 CHAR(64) NOT NULL,
    row_count BIGINT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE raw.settlements
ADD COLUMN IF NOT EXISTS scenario VARCHAR(50);

UPDATE raw.settlements
SET scenario = 'baseline'
WHERE scenario IS NULL;

ALTER TABLE raw.settlements
ALTER COLUMN scenario SET NOT NULL;
