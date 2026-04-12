#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from app.content_brain.browser_capture import ingest_rendered_targets
from app.content_brain.bootstrap import DEFAULT_STORAGE_ROOT
from app.content_brain.sources import load_seed_targets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest browser-rendered public NTangible pages that need JavaScript execution."
    )
    parser.add_argument(
        "--slug",
        action="append",
        required=True,
        help="Target slug to ingest with a real browser. Repeat for multiple slugs.",
    )
    parser.add_argument(
        "--storage-root",
        default=str(DEFAULT_STORAGE_ROOT),
        help="Directory where raw, normalized, and run summary files are stored.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requested = set(args.slug)
    targets = [target for target in load_seed_targets() if target.slug in requested]
    summary = ingest_rendered_targets(targets, storage_root=Path(args.storage_root))
    print(json.dumps(summary, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
