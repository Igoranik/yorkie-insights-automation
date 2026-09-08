#!/usr/bin/env python3
"""Build the public, read-only JSON endpoint from the newest Insights snapshot."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SNAPSHOT_NAME = re.compile(r"^reels_insights_(\d{8}T\d{6}Z)\.json$")

# Explicit allowlist: internal errors, credentials and future collector-only fields
# are never copied to the public endpoint by accident.
PUBLIC_FIELDS = (
    "id",
    "media_type",
    "media_product_type",
    "timestamp",
    "permalink",
    "caption",
    "reach",
    "views",
    "likes",
    "comments",
    "saved",
    "shares",
    "ig_reels_avg_watch_time",
    "ig_reels_video_view_total_time",
    "reels_skip_rate",
    "status",
)


def snapshot_stamp(path: Path) -> str:
    match = SNAPSHOT_NAME.fullmatch(path.name)
    if match is None:
        raise ValueError(f"Unsupported snapshot filename: {path.name}")
    return match.group(1)


def find_latest_snapshot(data_dir: Path) -> Path:
    candidates = [
        path
        for path in data_dir.glob("reels_insights_*.json")
        if SNAPSHOT_NAME.fullmatch(path.name)
    ]
    if not candidates:
        raise FileNotFoundError(f"No Insights snapshots found in {data_dir}")
    return max(candidates, key=snapshot_stamp)


def generated_at_from_path(path: Path) -> str:
    value = datetime.strptime(snapshot_stamp(path), "%Y%m%dT%H%M%SZ")
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)

    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"Expected a JSON array of objects in {path}")
    return value


def sanitize_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {field: row.get(field) for field in PUBLIC_FIELDS if field in row}
        for row in rows
    ]


def build_payload(snapshot: Path) -> dict[str, Any]:
    items = sanitize_rows(load_rows(snapshot))
    return {
        "ok": True,
        "schema_version": 1,
        "generated_at": generated_at_from_path(snapshot),
        "reels_count": len(items),
        "items": items,
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary_name = handle.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def main() -> None:
    data_dir = Path(os.getenv("OUTPUT_DIR", "data"))
    endpoint_path = Path(
        os.getenv("PUBLIC_INSIGHTS_PATH", "docs/api/insights/latest.json")
    )
    snapshot = find_latest_snapshot(data_dir)
    payload = build_payload(snapshot)
    write_json_atomic(endpoint_path, payload)
    print(
        json.dumps(
            {
                "ok": True,
                "endpoint": str(endpoint_path),
                "generated_at": payload["generated_at"],
                "reels_count": payload["reels_count"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
