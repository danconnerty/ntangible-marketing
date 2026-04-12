#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.content_brain.bootstrap import DEFAULT_STORAGE_ROOT, persist_fetch_result
from app.content_brain.pdf_documents import build_research_pdf_item


@dataclass(frozen=True, slots=True)
class ResearchPdfSource:
    slug: str
    title: str
    published_at: datetime
    file_id: str

    @property
    def view_url(self) -> str:
        return f"https://drive.google.com/file/d/{self.file_id}/view?usp=sharing"

    @property
    def download_url(self) -> str:
        return f"https://drive.google.com/uc?export=download&id={self.file_id}"


RESEARCH_PDFS = [
    ResearchPdfSource(
        slug="research_alignment_index_pdf",
        title="The Science of Dyadic Congruence: Quantifying Coach-Player Alignment as a Determinant of Elite Performance",
        published_at=datetime(2026, 2, 4, tzinfo=UTC),
        file_id="17LjW7fip5Jw91lmeKc89mF5yu3__kNB5",
    ),
    ResearchPdfSource(
        slug="research_pressure_profiling_pdf",
        title="Individualized Pressure Profiling in Elite Sports",
        published_at=datetime(2025, 12, 9, tzinfo=UTC),
        file_id="1-nWGVn9teBVuhYqiKqhdNFdMvEt56MuU",
    ),
    ResearchPdfSource(
        slug="research_inter_rater_reliability_pdf",
        title="Inter-Rater Reliability Analysis of Assessment AI Scoring Method",
        published_at=datetime(2025, 9, 15, tzinfo=UTC),
        file_id="10fG01vUGZ8TOzHAijbq9F--NhTiobksb",
    ),
    ResearchPdfSource(
        slug="research_college_baseball_pdf",
        title="Predictive Findings of Clutch Performance in Collegiate Baseball",
        published_at=datetime(2025, 9, 15, tzinfo=UTC),
        file_id="1_LeTkmSa1edhFzmg6IhtUoLsiEJdKrPP",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest NTangible public research PDFs into the content brain store.")
    parser.add_argument(
        "--slug",
        action="append",
        help="Only ingest the provided research PDF slug. Repeat for multiple slugs.",
    )
    parser.add_argument(
        "--storage-root",
        default=str(DEFAULT_STORAGE_ROOT),
        help="Directory where raw, normalized, and run summary files are stored.",
    )
    return parser.parse_args()


def extract_pdf_text(pdf_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        completed = subprocess.run(
            ["pdftotext", tmp.name, "-"],
            capture_output=True,
            text=True,
            check=True,
        )
    return completed.stdout


def ingest_research_pdf(
    source: ResearchPdfSource,
    *,
    storage_root: Path,
    client: httpx.Client,
) -> dict[str, object]:
    response = client.get(source.download_url)
    response.raise_for_status()

    pdf_text = extract_pdf_text(response.content)
    item = build_research_pdf_item(
        pdf_text=pdf_text,
        source_url=source.view_url,
        source_slug=source.slug,
        title=source.title,
        published_at=source.published_at,
        file_id=source.file_id,
    )
    persisted = persist_fetch_result(
        storage_root=storage_root,
        target_slug=source.slug,
        source_url=source.view_url,
        content_type="application/pdf",
        raw_body=pdf_text,
        items=[item],
        fetched_at=datetime.now(UTC),
    )
    persisted["display_name"] = source.title
    return persisted


def main() -> None:
    args = parse_args()
    requested = set(args.slug or [])
    sources = [source for source in RESEARCH_PDFS if not requested or source.slug in requested]
    storage_root = Path(args.storage_root)

    results: list[dict[str, object]] = []
    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        for source in sources:
            results.append(ingest_research_pdf(source, storage_root=storage_root, client=client))

    print(
        json.dumps(
            {
                "storage_root": storage_root.as_posix(),
                "source_count": len(results),
                "results": results,
            },
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
