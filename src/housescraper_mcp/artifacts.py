"""Structured artifact snapshots for local debugging."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _default_root() -> Path:
    configured = os.environ.get("HOUSESCRAPER_ARTIFACTS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.cwd() / "artifacts").resolve()


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^\w-]+", "-", value.strip(), flags=re.UNICODE).strip("-")
    return slug or "artifact"


class ArtifactStore:
    """Persist probe/search snapshots so failures are easier to inspect later."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or _default_root()).resolve()

    def write_probe_snapshot(self, requested_platform: str, payload: dict[str, Any]) -> str:
        return self._write_json_snapshot("probe", requested_platform, payload)

    def write_baseline_report(self, city: str, payload: dict[str, Any]) -> str:
        return self._write_json_snapshot("baseline", city, payload)

    def _write_json_snapshot(self, category: str, slug: str, payload: dict[str, Any]) -> str:
        directory = self.root / category
        directory.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{timestamp}_{_safe_slug(slug)}.json"
        path = directory / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
