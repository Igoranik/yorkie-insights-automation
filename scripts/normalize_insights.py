#!/usr/bin/env python3
"""
Yorkie Insights normalizer.

Rules:
- Never invent missing metrics.
- Preserve source values.
- Bind a Reel to Content Queue only by explicit reel_id or permalink.
- Unknown/unmatched items stay UNMATCHED.
- No winner/loser decision is made without an explicit policy.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
from validate_payload import validate_payload_bytes, SCHEMA_VERSION

METRICS = (
    "reach",
    "views",
    "likes",
    "comments",
    "saved",
    "shares",
    "ig_reels_avg_watch_time",
    "ig_reels_video_view_total_time",
    "reels_skip_rate",
)

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def queue_indexes(queue: Any):
    by_id = {}
    by_permalink = {}
    items = queue.get("items", []) if isinstance(queue, dict) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("reel_id", "")).strip()
        permalink = str(item.get("permalink", "")).strip()
        if rid:
            by_id[rid] = item
        if permalink:
            by_permalink[permalink] = item
    return by_id, by_permalink

def normalize_reel(reel: dict, by_id: dict, by_permalink: dict) -> dict:
    rid = str(reel.get("id", "")).strip()
    permalink = str(reel.get("permalink", "")).strip()

    out = {
        "reel_id": rid or None,
        "timestamp": reel.get("timestamp"),
        "permalink": permalink or None,
        "source_status": reel.get("status"),
        "metrics": {k: reel.get(k) for k in METRICS},
        "content_queue": {
            "match_status": "UNMATCHED",
            "queue_id": None,
            "matched_by": None,
        },
        "decision": {
            "status": "HOLD",
            "reason": "No explicit decision policy applied."
        }
    }

    match = None
    matched_by = None
    if rid and rid in by_id:
        match = by_id[rid]
        matched_by = "reel_id"
    elif permalink and permalink in by_permalink:
        match = by_permalink[permalink]
        matched_by = "permalink"

    if match:
        out["content_queue"] = {
            "match_status": "MATCHED",
            "queue_id": match.get("queue_id"),
            "matched_by": matched_by,
        }
        # Still HOLD: matching alone is not permission to infer performance rules.
        out["decision"] = {
            "status": "HOLD",
            "reason": "Matched to Content Queue; explicit decision policy is still required."
        }

    return out

def normalize(payload: dict, queue: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("latest.json root must be an object")
    for key in ("generated_at", "reels_count"):
        if key not in payload:
            raise ValueError(f"Missing required field: {key}")

    reels = payload.get("reels")
    if reels is None:
        # Support flat reel_1/reel_2/... shape without guessing order beyond numeric suffix.
        pairs = []
        for k, v in payload.items():
            if k.startswith("reel_") and isinstance(v, dict):
                try:
                    n = int(k.split("_", 1)[1])
                except ValueError:
                    continue
                pairs.append((n, v))
        reels = [v for _, v in sorted(pairs)]

    if not isinstance(reels, list):
        raise ValueError("Expected 'reels' array or reel_N objects")

    by_id, by_permalink = queue_indexes(queue)

    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": "YORKIE_INSIGHTS_UPDATE",
        "generated_at": payload.get("generated_at"),
        "reported_reels_count": payload.get("reels_count"),
        "parsed_reels_count": len(reels),
        "count_consistent": payload.get("reels_count") == len(reels),
        "reels": [normalize_reel(r, by_id, by_permalink) for r in reels],
        "safety": {
            "used_only_source_metrics": True,
            "unmatched_reels_block_strategy_change": True,
            "winner_loser_rules_applied": False,
        }
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("payload")
    ap.add_argument("--queue", default="config/content_queue.json")
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    payload = load_json(Path(args.payload))
    queue_path = Path(args.queue)
    queue = load_json(queue_path) if queue_path.exists() else {"items": []}
    result = normalize(payload, queue)

    data = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(data)
    else:
        Path(args.out).write_text(data + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
