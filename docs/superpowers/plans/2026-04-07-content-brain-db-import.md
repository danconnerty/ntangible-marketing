# Content Brain DB Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the existing file-backed content-brain corpus into the SQLAlchemy/Alembic content-brain tables so the dataset exists in the configured database.

**Architecture:** Keep file-backed ingestion as-is and add a one-shot sync layer that reads the latest normalized/raw files, maps them into the existing `content_source_target`, `content_source_snapshot`, `content_brain_item`, `content_brain_asset`, and `content_brain_metric_snapshot` tables, and upserts records by `slug` and `canonical_key`. The import script will run after migrations, commit once, and print row counts for verification.

**Tech Stack:** Python 3, SQLAlchemy ORM, Alembic, pytest, existing content-brain file store.

---

### Scope
- Add a DB sync module for the current content-brain file store.
- Add focused tests for payload mapping and raw snapshot path resolution.
- Add a one-shot import script.
- Run Alembic migrations and import the current public corpus into the configured database.
- Verify DB row counts after import.
