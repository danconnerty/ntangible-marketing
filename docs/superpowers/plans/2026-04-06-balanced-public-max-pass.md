# Balanced Public-Max Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maximize the recoverable public NTangible corpus while normalizing the stored records so agents can retrieve clean, consistent content and metadata.

**Architecture:** Keep the current file-backed content brain as the live store, add targeted public-source enrichment for the highest-yield missing surfaces, and normalize metadata into consistent item fields and metric snapshots. Prioritize sources already proven public and relevant: Google Drive research PDFs, public social post pages, and structured media references already embedded in the NTangible site.

**Tech Stack:** Python 3, httpx, FastAPI file-backed store, pytest, pdftotext, existing Playwright/browser capture helpers.

---

### Scope
- Ingest full text from the public Google Drive research PDFs.
- Preserve source titles/dates/URLs and extracted text in normalized records.
- Keep social item fields consistent: `author`, `published_at`, `metrics`, `summary`, `assets`.
- Verify dashboard/API returns the enriched data cleanly.
- Do not claim private analytics or hidden history we cannot recover publicly.
