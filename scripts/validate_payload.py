#!/usr/bin/env python3
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

EVENT_TYPE = "YORKIE_INSIGHTS_UPDATE"
SOURCE_PATH = "api/insights/latest.json"
SCHEMA_VERSION = "YORKIE_INSIGHTS_PAYLOAD_COMPAT_V1"

REEL_REQUIRED = ("id", "timestamp", "permalink")
NUMERIC_OR_NULL = (
    "reach", "views", "likes", "comments", "saved", "shares",
    "ig_reels_avg_watch_time", "ig_reels_video_view_total_time",
    "reels_skip_rate",
)

def _fail(msg: str) -> None:
    raise ValueError(msg)

def extract_reels(data: dict[str, Any]) -> list[dict[str, Any]]:
    if "items" in data:
        items = data["items"]
        if not isinstance(items, list):
            _fail("'items' must be an array")
        if not items:
            _fail("'items' must not be empty")
        if not all(isinstance(x, dict) for x in items):
            _fail("every item in 'items' must be an object")
        return items

    if "reels" in data:
        reels = data["reels"]
        if not isinstance(reels, list):
            _fail("'reels' must be an array")
        if not all(isinstance(x, dict) for x in reels):
            _fail("every item in 'reels' must be an object")
        return reels

    numbered = []
    for k, v in data.items():
        m = re.fullmatch(r"reel_(\d+)", k)
        if m:
            if not isinstance(v, dict):
                _fail(f"{k} must be an object")
            numbered.append((int(m.group(1)), v))

    numbered.sort(key=lambda x: x[0])
    if not numbered and data.get("reels_count") != 0:
        _fail("no 'reels' array or reel_N objects found")

    expected = list(range(1, len(numbered) + 1))
    actual = [n for n, _ in numbered]
    if actual != expected:
        _fail(f"reel_N keys must be contiguous from reel_1; got {actual}")

    return [v for _, v in numbered]

def validate_payload_bytes(raw: bytes) -> dict[str, Any]:
    if not raw.strip():
        _fail("latest.json is empty")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        _fail(f"latest.json is not UTF-8: {e}")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        _fail(f"latest.json is not valid JSON: {e}")

    if not isinstance(data, dict):
        _fail("latest.json root must be an object")

    if "items" in data:
        if data.get("ok") is not True:
            _fail("items payload: ok must be true")
        schema_version = data.get("schema_version")
        if isinstance(schema_version, bool) or schema_version != 1:
            _fail("items payload: schema_version must be 1")

    generated_at = data.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        _fail("generated_at must be a non-empty string")
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        _fail("generated_at must be ISO-8601 compatible")

    reels_count = data.get("reels_count")
    if isinstance(reels_count, bool) or not isinstance(reels_count, int) or reels_count < 0:
        _fail("reels_count must be a non-negative integer")

    reels = extract_reels(data)
    if len(reels) != reels_count:
        _fail(f"reels_count={reels_count} but parsed {len(reels)} reels")

    seen_ids = set()
    seen_links = set()

    for i, reel in enumerate(reels, start=1):
        for key in REEL_REQUIRED:
            value = reel.get(key)
            if not isinstance(value, str) or not value.strip():
                _fail(f"reel {i}: {key} must be a non-empty string")

        rid = reel["id"].strip()
        permalink = reel["permalink"].strip()

        if rid in seen_ids:
            _fail(f"duplicate reel id: {rid}")
        if permalink in seen_links:
            _fail(f"duplicate permalink: {permalink}")
        seen_ids.add(rid)
        seen_links.add(permalink)

        if not permalink.startswith("https://www.instagram.com/reel/"):
            _fail(f"reel {i}: permalink is not an Instagram Reel URL")

        for key in NUMERIC_OR_NULL:
            if key in reel:
                value = reel[key]
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                    _fail(f"reel {i}: {key} must be numeric or null")

        if "status" in reel and reel["status"] is not None and not isinstance(reel["status"], str):
            _fail(f"reel {i}: status must be string or null")

    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": EVENT_TYPE,
        "source_path": SOURCE_PATH,
        "generated_at": generated_at,
        "reels_count": reels_count,
        "payload": data,
        "reels": reels,
    }

def source_event_id(raw: bytes, generated_at: str) -> str:
    material = (
        EVENT_TYPE.encode("utf-8") + b"\0" +
        SOURCE_PATH.encode("utf-8") + b"\0" +
        generated_at.encode("utf-8") + b"\0" +
        raw
    )
    return "sha256:" + __import__("hashlib").sha256(material).hexdigest()

def validate_file(path: Path) -> dict[str, Any]:
    return validate_payload_bytes(path.read_bytes())

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    args = ap.parse_args()
    result = validate_file(Path(args.path))
    print(json.dumps({
        "status": "PASS",
        "schema_version": result["schema_version"],
        "event_type": result["event_type"],
        "source_path": result["source_path"],
        "generated_at": result["generated_at"],
        "reels_count": result["reels_count"],
    }, ensure_ascii=False))
