import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.content_brain.bootstrap import DEFAULT_STORAGE_ROOT, persist_fetch_result
from app.content_brain.linkedin_authenticated import build_linkedin_authenticated_post_items


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: rebuild_linkedin_authenticated_feed.py <captured_feed_json>")

    source_path = Path(sys.argv[1])
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    observed_at = datetime.now(UTC)
    items = build_linkedin_authenticated_post_items(payload, observed_at=observed_at)

    result = persist_fetch_result(
        storage_root=DEFAULT_STORAGE_ROOT,
        target_slug="ntangible_linkedin_posts_authenticated",
        source_url="https://www.linkedin.com/company/ntangible/posts/?feedView=all",
        content_type="application/json",
        raw_body=source_path.read_text(encoding="utf-8"),
        items=items,
        fetched_at=observed_at,
    )
    print(json.dumps({"item_count": len(items), **result}, indent=2))


if __name__ == "__main__":
    main()
