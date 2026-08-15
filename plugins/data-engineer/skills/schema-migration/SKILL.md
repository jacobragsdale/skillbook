---
name: schema-migration
description: Safely verifies backward compatibility for database schema migrations before execution.
---

# Schema Migration Verifier

Analyze DDL scripts and Alembic/Flyway migrations for non-blocking execution.

## Instructions
1. Check for locks and table rewrites.
2. Verify all new columns have default values or are nullable.
3. Test down-migrations for clean rollbacks.
