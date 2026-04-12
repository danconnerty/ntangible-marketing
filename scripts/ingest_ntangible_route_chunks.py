#!/usr/bin/env python3

import json
import re
from pathlib import Path

import httpx

from app.content_brain.bootstrap import DEFAULT_STORAGE_ROOT, ingest_targets
from app.content_brain.vite_chunks import extract_lazy_chunk_targets


HOME_URL = "https://ntangible.co/"


def main() -> None:
    with httpx.Client(follow_redirects=True, timeout=20.0) as client:
        home = client.get(HOME_URL)
        home.raise_for_status()
        match = re.search(r'src="(/assets/index-[^"]+\.js)"', home.text)
        if not match:
            raise RuntimeError("Could not find the NTangible main Vite bundle URL.")

        bundle_url = httpx.URL(HOME_URL).join(match.group(1))
        bundle = client.get(str(bundle_url))
        bundle.raise_for_status()

        targets = extract_lazy_chunk_targets(bundle.text, base_url="https://ntangible.co")
        summary = ingest_targets(targets, storage_root=Path(DEFAULT_STORAGE_ROOT), client=client)

    print(json.dumps(summary, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
