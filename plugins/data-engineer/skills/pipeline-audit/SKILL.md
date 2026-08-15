---
name: pipeline-audit
description: Audits data pipeline health, latency, record counts, and partition freshness.
---

# Pipeline Audit

Run end-to-end checks against data ingestion pipelines.

## Instructions
1. Inspect pipeline run metadata.
2. Query output partition counts via DuckDB MCP.
3. Validate row counts against source database records.
