#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from app.content_brain.bootstrap import DEFAULT_STORAGE_ROOT, ingest_targets
from app.content_brain.sources import load_seed_targets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap public-source NTangible content ingestion.")
    parser.add_argument(
        "--slug",
        action="append",
        help="Only ingest the provided target slug. Repeat for multiple slugs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of configured targets to ingest.",
    )
    parser.add_argument(
        "--storage-root",
        default=str(DEFAULT_STORAGE_ROOT),
        help="Directory where raw, normalized, and run summary files are stored.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = load_seed_targets()

    if args.slug:
        requested = set(args.slug)
        targets = [target for target in targets if target.slug in requested]

    if args.limit is not None:
        targets = targets[: args.limit]

    summary = ingest_targets(targets, storage_root=Path(args.storage_root))
    print(json.dumps(summary, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
