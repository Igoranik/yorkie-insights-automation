#!/usr/bin/env python3

import csv
import json
import os
from pathlib import Path

DATA_DIR = Path(os.getenv("OUTPUT_DIR", "data"))
CSV_PATH = DATA_DIR / "reels_insights_latest.csv"

OUT_ANALYSIS = DATA_DIR / "analysis_latest.json"
OUT_QUEUE = DATA_DIR / "content_queue_recommendation.json"

# Не принимаем решения по слишком маленькой выборке.
MIN_VIEWS_FOR_DECISION = 30


def num(value):
    if value in (None, "", "None"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def classify(row):
    views = num(row.get("views")) or 0
    avg_watch_ms = num(row.get("ig_reels_avg_watch_time"))
    skip_rate = num(row.get("reels_skip_rate"))

    saved = num(row.get("saved")) or 0
    shares = num(row.get("shares")) or 0

    if views < MIN_VIEWS_FOR_DECISION:
        return {
            "status": "INSUFFICIENT_DATA",
            "reason": (
                f"Only {int(views)} views; "
                "wait before making content decisions."
            ),
        }

    strong_signals = []
    weak_signals = []

    if skip_rate is not None:
        if skip_rate <= 35:
            strong_signals.append("low_skip_rate")
        elif skip_rate >= 55:
            weak_signals.append("high_skip_rate")

    if avg_watch_ms is not None:
        if avg_watch_ms >= 5000:
            strong_signals.append("watch_time_5s_plus")
        elif avg_watch_ms < 3000:
            weak_signals.append("low_watch_time")

    if saved + shares >= 2:
        strong_signals.append("saves_shares_signal")

    if len(strong_signals) >= 2 and not weak_signals:
        status = "WINNER_CANDIDATE"
    elif weak_signals and not strong_signals:
        status = "WEAK_CANDIDATE"
    else:
        status = "WATCH"

    return {
        "status": status,
        "strong_signals": strong_signals,
        "weak_signals": weak_signals,
    }


def main():
    if not CSV_PATH.exists():
        raise SystemExit(f"Missing {CSV_PATH}")

    with CSV_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    analyzed = []

    for row in rows:
        result = classify(row)

        analyzed.append(
            {
                "id": row.get("id"),
                "timestamp": row.get("timestamp"),
                "permalink": row.get("permalink"),
                "views": num(row.get("views")),
                "reach": num(row.get("reach")),
                "avg_watch_time_ms": num(
                    row.get("ig_reels_avg_watch_time")
                ),
                "skip_rate": num(row.get("reels_skip_rate")),
                "saved": num(row.get("saved")),
                "shares": num(row.get("shares")),
                **result,
            }
        )

    counts = {}

    for reel in analyzed:
        status = reel["status"]
        counts[status] = counts.get(status, 0) + 1

    analysis = {
        "note": (
            "Project heuristic only; "
            "not an official Instagram score."
        ),
        "minimum_views_for_decision": MIN_VIEWS_FOR_DECISION,
        "counts": counts,
        "reels": analyzed,
    }

    if counts.get("WINNER_CANDIDATE", 0) > 0:
        queue_action = "SCALE_WINNER_FORMAT"
        guidance = (
            "Repeat the winning content mechanism "
            "with a new hook/topic while preserving "
            "the core structure."
        )

    elif counts.get("WEAK_CANDIDATE", 0) > 0:
        queue_action = "TEST_NEW_HOOK"
        guidance = (
            "Keep the topic if useful, but change "
            "the first-second hook and opening visual."
        )

    else:
        queue_action = "WAIT_FOR_MORE_DATA"
        guidance = (
            "Do not change the content plan yet; "
            "most samples are still too small."
        )

    queue = {
        "action": queue_action,
        "guidance": guidance,
        "decision_basis": counts,
        "safety_rule": (
            "Never promote/demote a format solely "
            "from fewer than 30 views."
        ),
    }

    OUT_ANALYSIS.write_text(
        json.dumps(
            analysis,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    OUT_QUEUE.write_text(
        json.dumps(
            queue,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "ok": True,
                "analyzed_reels": len(analyzed),
                "queue_action": queue_action,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
