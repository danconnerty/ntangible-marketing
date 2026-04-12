from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.content_brain.bootstrap import DEFAULT_STORAGE_ROOT, _persist_run_summary, persist_fetch_result
from app.content_brain.parsers import parse_payload
from app.content_brain.types import SourceTarget


RENDERER_SCRIPT = Path("scripts/render_page_with_playwright.mjs")
PLAYWRIGHT_RUNNER_DIR = Path("/tmp/ntangible-playwright-runner")
PLAYWRIGHT_BROWSERS_DIR = PLAYWRIGHT_RUNNER_DIR / "browsers"


def _ensure_playwright_runtime(runner_dir: Path = PLAYWRIGHT_RUNNER_DIR) -> Path:
    runner_dir.mkdir(parents=True, exist_ok=True)
    package_json = runner_dir / "package.json"
    if not package_json.exists():
        package_json.write_text('{"name":"ntangible-playwright-runner","private":true}\n', encoding="utf-8")

    playwright_module = runner_dir / "node_modules" / "playwright" / "index.mjs"
    if not playwright_module.exists():
        subprocess.run(
            ["npm", "install", "playwright"],
            check=True,
            cwd=runner_dir,
            capture_output=True,
            text=True,
        )

    browsers_dir = PLAYWRIGHT_BROWSERS_DIR
    browsers_dir.mkdir(parents=True, exist_ok=True)
    if not any(browsers_dir.iterdir()):
        env = os.environ.copy()
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir)
        subprocess.run(
            ["node", str(runner_dir / "node_modules" / "playwright" / "cli.js"), "install", "chromium"],
            check=True,
            cwd=runner_dir,
            capture_output=True,
            text=True,
            env=env,
        )

    return playwright_module


def build_playwright_command(
    *,
    renderer_script: Path,
    url: str,
    playwright_module: Path,
    render_options: dict[str, Any] | None = None,
) -> list[str]:
    command = [
        "node",
        str(renderer_script),
        url,
        str(playwright_module),
    ]
    if render_options:
        command.append(json.dumps(render_options, sort_keys=True, separators=(",", ":")))
    return command


def render_html_via_playwright(
    url: str,
    *,
    renderer_script: Path = RENDERER_SCRIPT,
    render_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    playwright_module = _ensure_playwright_runtime()
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_BROWSERS_DIR)
    completed = subprocess.run(
        build_playwright_command(
            renderer_script=renderer_script,
            url=url,
            playwright_module=playwright_module,
            render_options=render_options,
        ),
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout)


def ingest_rendered_targets(
    targets: list[SourceTarget],
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    fetched_at: datetime | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    default_fetched_at = fetched_at
    results: list[dict[str, Any]] = []

    for target in targets:
        current_fetched_at = default_fetched_at or datetime.now(UTC)
        try:
            render_options = target.metadata.get("render_options")
            if render_options:
                rendered = render_html_via_playwright(
                    target.url,
                    render_options=render_options,
                )
            else:
                rendered = render_html_via_playwright(target.url)
            raw_body = rendered["html"]
            source_url = rendered.get("final_url") or target.url
            content_type = rendered.get("content_type", "text/html; charset=utf-8")
            items = parse_payload(
                target.parser,
                raw_body,
                source_url=source_url,
                source_slug=target.slug,
            )
            result = persist_fetch_result(
                storage_root=storage_root,
                target_slug=target.slug,
                source_url=source_url,
                content_type=content_type,
                raw_body=raw_body,
                items=items,
                fetched_at=current_fetched_at,
            )
            result["display_name"] = target.display_name
            result["rendered"] = True
            results.append(result)
        except Exception as exc:  # pragma: no cover - exercised by live runs
            results.append(
                {
                    "target_slug": target.slug,
                    "source_url": target.url,
                    "display_name": target.display_name,
                    "rendered": True,
                    "error": str(exc),
                }
            )

    finished_at = datetime.now(UTC)
    run_summary_path = _persist_run_summary(
        storage_root,
        started_at=started_at,
        finished_at=finished_at,
        results=results,
    )
    return {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "storage_root": storage_root.as_posix(),
        "run_summary_path": run_summary_path,
        "results": results,
    }
