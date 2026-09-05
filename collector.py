#!/usr/bin/env python3
import os, json, csv
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

GRAPH_BASE = "https://graph.facebook.com"
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v26.0")
IG_USER_ID = os.environ["IG_USER_ID"]
ACCESS_TOKEN = os.environ["META_ACCESS_TOKEN"]
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "data")

MEDIA_FIELDS = "id,media_type,media_product_type,timestamp,permalink,caption"

METRICS = [
    "reach",
    "views",
    "likes",
    "comments",
    "saved",
    "shares",
    "ig_reels_avg_watch_time",
    "ig_reels_video_view_total_time",
    "reels_skip_rate",
]

def graph_get(path, params):
    params = dict(params)
    params["access_token"] = ACCESS_TOKEN
    url = f"{GRAPH_BASE}/{GRAPH_VERSION}/{path.lstrip('/')}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "YorkieInsightsAutomation/3.0"})
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Graph API HTTP {e.code}: {body}") from e

def metric_value(item):
    values = item.get("values") or []
    return values[0].get("value") if values else None

def fetch_single_metric(media_id, metric):
    data = graph_get(
        f"{media_id}/insights",
        {"metric": metric}
    ).get("data", [])
    if not data:
        return None
    return metric_value(data[0])

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    media = graph_get(
        f"{IG_USER_ID}/media",
        {"fields": MEDIA_FIELDS, "limit": 25}
    ).get("data", [])

    rows = []

    for m in media:
        if m.get("media_product_type") != "REELS":
            continue

        row = dict(m)

        for metric in METRICS:
            try:
                row[metric] = fetch_single_metric(m["id"], metric)
            except Exception as e:
                row[metric] = None
                row[f"{metric}_error"] = str(e)

        views = row.get("views") or 0
        skip = row.get("reels_skip_rate")

        if views < 30:
            row["status"] = "INSUFFICIENT_DATA"
        elif skip is not None and float(skip) <= 35:
            row["status"] = "WINNER_CANDIDATE"
        else:
            row["status"] = "WATCH"

        rows.append(row)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with open(f"{OUTPUT_DIR}/reels_insights_{stamp}.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    fields = [
        "id", "timestamp", "permalink",
        "reach", "views", "likes", "comments", "saved", "shares",
        "ig_reels_avg_watch_time", "ig_reels_video_view_total_time",
        "reels_skip_rate", "status", "caption"
    ]

    with open(f"{OUTPUT_DIR}/reels_insights_latest.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(json.dumps({
        "ok": True,
        "reels_processed": len(rows),
        "generated_at": stamp
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
