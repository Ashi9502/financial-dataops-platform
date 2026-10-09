# Financial DataOps & Reconciliation Platform

A production-style local Data Engineering platform for incremental ingestion, warehouse modeling, data quality, financial reconciliation, orchestration, recovery testing, CI, and operational lineage.

> Built and validated locally with WSL2 and Docker. This is not presented as a production cloud deployment.

## Architecture

```text
PostgreSQL OLTP ─────┐
                     ├─> Apache Airflow
Partner CSV files ───┘        │
                              ├─> SeaweedFS (S3-compatible)
                              └─> Analytics PostgreSQL
                                         │
                                        dbt
                                         │
                              staging / intermediate / marts
                                         │
                         ┌───────────────┴───────────────┐
                         │                               │
                Great Expectations              Reconciliation

Airflow ──> OpenLineage ──> Marquez
GitHub Actions ──> pytest / dbt parse / Compose validation
```

## Technology

Python, PostgreSQL, Apache Airflow 3.3.2, dbt, Great Expectations, SeaweedFS, OpenLineage, Marquez, Docker Compose, Parquet, pytest, and GitHub Actions.

## Incremental Ingestion

Transactions use a composite extraction cursor:

```text
(updated_at, transaction_id)
```

The pipeline persists watermarks, writes incremental Parquet batches, UPSERTs latest-state records, and tracks processed batch objects.

Latest verified transaction count: **10,008**.

## Financial Reconciliation

Partner settlements are reconciled against expected aggregates derived from completed internal transactions.

Synthetic project rule:

```text
fee = gross_amount × 1.5%
net = gross_amount - fee
```

Supported statuses:

- MATCHED
- AMOUNT_MISMATCH
- COUNT_MISMATCH
- MISSING_SETTLEMENT
- MISSING_TRANSACTION

Verified baseline:

```text
Settlement rows:         1,533
Completed transactions:  8,015
Gross amount:             98,780,531.99
Fees:                      1,481,708.14
Net amount:               97,298,823.85
```

Settlement files use SHA-256 content-addressed object keys, and exact replays are detected through ledger and object-metadata verification.

## Reliability and Quality

Verified scenarios include:

- exact settlement replay
- historical backfill
- malformed-schema failure
- corrected-file recovery
- amount mismatch
- count mismatch
- missing settlement
- missing internal transaction
- Great Expectations failure propagation

Great Expectations currently runs **2 validations / 19 expectations**.

Final verified dbt build:

```text
11 models
89 data tests
PASS=100
WARN=0
ERROR=0
SKIP=0
TOTAL=100
```

## Airflow

Transaction DAG:

```text
extract_transactions
→ load_transactions
→ sync_reference_data
→ dbt_build
→ gx_quality_gate
```

Settlement DAG:

```text
load_settlement_file
→ dbt_reconciliation_build
→ reconciliation_assertions
```

## OpenLineage and Marquez

Verified Marquez jobs:

```text
settlement_reconciliation
settlement_reconciliation.load_settlement_file
settlement_reconciliation.dbt_reconciliation_build
settlement_reconciliation.reconciliation_assertions
```

The integration captures DAG/task execution metadata, run states, durations, parent relationships, and execution history. It does **not** claim table-level or column-level lineage.

## Tests and CI

Verified Python unit tests:

```text
8 passed
```

GitHub Actions validates:

- Python compilation
- pytest
- dbt parse
- Docker Compose configuration
- .env commit guard

Full database-backed integration validation is performed locally.

## Benchmark

Latest recorded local WSL2 benchmark:

```text
Python:       3.14.4
dbt results:  100
Models:       11
Tests:        89
Wall-clock:   48.038 seconds
```

dbt reported approximately **8.88 seconds** of internal execution time.

Benchmark artifact: `docs/benchmarks/dbt_build_local.json`.

This is a local development benchmark, not production throughput.

## Scope

- SeaweedFS provides local S3-compatible storage; this project does not claim AWS deployment.
- dbt marts currently rebuild from latest-state warehouse data.
- Great Expectations uses a local validation context.
- OpenLineage proof covers execution metadata rather than table/column lineage.
- Benchmark results are local WSL2 measurements.

The project focuses on operational Data Engineering behavior around incremental ingestion, replay-aware loading, reconciliation, data contracts, failure propagation, recovery, backfills, observability, testing, and CI.
