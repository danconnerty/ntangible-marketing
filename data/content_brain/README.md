# Public Content Brain Storage

This directory is the bootstrap storage area for public-source NTangible ingestion.

Canonical storage model:
- Postgres tables store normalized metadata and relationships.
- Raw payloads are written to disk first so collection can start before a database is configured.

Directory layout:
- `raw/YYYY-MM-DD/*.html|xml|json|txt`
  - exact fetched payloads from public sources
- `normalized/YYYY-MM-DD/*.json`
  - parsed content items ready for import into Postgres or embeddings
- `runs/*.json`
  - ingestion run summaries, successes, and failures

Long-term relational tables:
- `content_source_target`
- `content_source_snapshot`
- `content_brain_item`
- `content_brain_asset`
- `content_brain_metric_snapshot`
