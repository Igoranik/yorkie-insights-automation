#!/usr/bin/env python3
"""Send the latest public Insights payload as a plain-text Gmail report."""

from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any


DEFAULT_ENDPOINT_PATH = "docs/api/insights/latest.json"
DEFAULT_SUBJECT = "YORKIE_INSIGHTS_UPDATE"

REPORT_FIELDS = (
    "id",
    "timestamp",
    "reach",
    "views",
    "likes",
    "comments",
    "saved",
    "shares",
    "ig_reels_avg_watch_time",
    "ig_reels_video_view_total_time",
    "reels_skip_rate",
    "metrics_status",
    "status",
    "status_reason",
    "permalink",
)


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Insights endpoint must contain a JSON object")

    generated_at = payload.get("generated_at")
    reels_count = payload.get("reels_count")
    items = payload.get("items")

    if not isinstance(generated_at, str) or not generated_at:
        raise ValueError("Insights endpoint has no valid generated_at")
    if not isinstance(reels_count, int) or isinstance(reels_count, bool):
        raise ValueError("Insights endpoint has no valid reels_count")
    if reels_count < 0:
        raise ValueError("Insights endpoint has a negative reels_count")
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise ValueError("Insights endpoint has no valid items array")
    if len(items) != reels_count:
        raise ValueError("Insights endpoint reels_count does not match items")

    return payload


def display_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_body(payload: dict[str, Any]) -> str:
    lines = [
        f"generated_at: {payload['generated_at']}",
        f"reels_count: {payload['reels_count']}",
    ]

    for index, item in enumerate(payload["items"], start=1):
        lines.extend(("", f"reel_{index}:"))
        for field in REPORT_FIELDS:
            if field in item:
                lines.append(f"{field}: {display_value(item[field])}")

    return "\n".join(lines) + "\n"


def build_message(
    payload: dict[str, Any], sender: str, recipient: str, subject: str
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(build_body(payload))
    return message


def send_message(message: EmailMessage, username: str, app_password: str) -> None:
    normalized_password = "".join(app_password.split())
    if not normalized_password:
        raise RuntimeError("GMAIL_APP_PASSWORD is empty")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as smtp:
        smtp.login(username, normalized_password)
        smtp.send_message(message)


def main() -> None:
    username = required_env("GMAIL_SMTP_USER")
    app_password = required_env("GMAIL_APP_PASSWORD")
    recipient = os.getenv("INSIGHTS_EMAIL_TO", "").strip() or username
    subject = os.getenv("INSIGHTS_EMAIL_SUBJECT", "").strip() or DEFAULT_SUBJECT
    endpoint_path = Path(os.getenv("PUBLIC_INSIGHTS_PATH", DEFAULT_ENDPOINT_PATH))

    payload = load_payload(endpoint_path)
    message = build_message(payload, username, recipient, subject)
    send_message(message, username, app_password)
    print(
        json.dumps(
            {
                "ok": True,
                "recipient": recipient,
                "subject": subject,
                "generated_at": payload["generated_at"],
                "reels_count": payload["reels_count"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
