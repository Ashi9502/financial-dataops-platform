# Project 3 — Validation & Completion Plan

## Gate 1 — Infrastructure
- [ ] PostgreSQL source
- [ ] PostgreSQL analytics warehouse
- [ ] MinIO object storage
- [ ] Apache Airflow
- [ ] connectivity checks

## Gate 2 — Incremental ingestion
- [ ] transaction source tables
- [ ] settlement-file generator
- [ ] persisted high-watermark control
- [ ] immutable raw landing
- [ ] idempotent reruns

## Gate 3 — dbt warehouse
- [ ] staging models
- [ ] intermediate models
- [ ] dimensions
- [ ] facts
- [ ] SCD Type 2
- [ ] marts

## Gate 4 — Data quality
- [ ] null checks
- [ ] uniqueness checks
- [ ] accepted values
- [ ] referential integrity
- [ ] quarantine flow

## Gate 5 — Financial reconciliation
- [ ] matched settlements
- [ ] amount mismatch
- [ ] count mismatch
- [ ] missing settlement
- [ ] missing transaction

## Gate 6 — Reliability
- [ ] retries
- [ ] failure recovery
- [ ] date-range backfill
- [ ] late-arriving files
- [ ] schema evolution

## Gate 7 — Observability
- [ ] run metadata
- [ ] lineage
- [ ] operational evidence

## Gate 8 — CI & benchmark
- [ ] automated tests
- [ ] GitHub Actions
- [ ] measured batch sizes
- [ ] documented limitations

## Gate 9 — Portfolio polish
- [ ] README
- [ ] architecture diagram
- [ ] interview notes
- [ ] failure-scenario evidence
- [ ] final GitHub push
