#!/usr/bin/env python3
"""
Process the body of a YORKIE_INSIGHTS_UPDATE email deterministically.

Important:
- Exact subject is required.
- event_id = sha256(raw email body bytes).
- No chat history or memory is read by this program.
- Duplicate suppression requires a persistent ledger shared by event runs.
- The payload is normalized only from the email body + explicit Content Queue file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from normalize_insights import normalize

EXPECTED_SUBJECT = "YORKIE_INSIGHTS_UPDATE"


def atomic_write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def read_ledger(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "processed_event_ids": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Ledger root must be an object")
    ids = data.get("processed_event_ids", [])
    if not isinstance(ids, list):
        raise ValueError("processed_event_ids must be an array")
    return {"schema_version": 1, "processed_event_ids": ids}


def process(subject: str, body_bytes: bytes, queue: dict, ledger: dict | None = None):
    if subject != EXPECTED_SUBJECT:
        return {
            "event_status": "REJECTED",
            "reason": "SUBJECT_MISMATCH",
            "expected_subject": EXPECTED_SUBJECT,
            "received_subject": subject,
        }, ledger

    event_id = "sha256:" + hashlib.sha256(body_bytes).hexdigest()

    if ledger is not None and event_id in ledger.get("processed_event_ids", []):
        return {
            "event_status": "DUPLICATE",
            "event_id": event_id,
            "action": "NO_NEW_PROCESSING",
        }, ledger

    try:
        text = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "event_status": "REJECTED",
            "event_id": event_id,
            "reason": "BODY_NOT_UTF8",
        }, ledger

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        return {
            "event_status": "REJECTED",
            "event_id": event_id,
            "reason": "BODY_NOT_VALID_JSON",
            "json_error": str(e),
        }, ledger

    try:
        normalized = normalize(payload, queue)
    except Exception as e:
        return {
            "event_status": "REJECTED",
            "event_id": event_id,
            "reason": "NORMALIZATION_FAILED",
            "error": str(e),
        }, ledger

    result = {
        "event_status": "ACCEPTED",
        "event_id": event_id,
        "subject": EXPECTED_SUBJECT,
        "normalized": normalized,
    }

    if ledger is not None:
        updated = {
            "schema_version": 1,
            "processed_event_ids": list(ledger.get("processed_event_ids", [])) + [event_id],
        }
    else:
        updated = ledger

    return result, updated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("body_file", help="File containing ONLY the received email body")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--queue", default=str(ROOT / "config" / "content_queue.json"))
    ap.add_argument("--ledger", default=None,
                    help="Persistent JSON ledger. Must be shared across event runs for deduplication.")
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    body_path = Path(args.body_file)
    body_bytes = body_path.read_bytes()

    queue_path = Path(args.queue)
    queue = json.loads(queue_path.read_text(encoding="utf-8")) if queue_path.exists() else {"items": []}

    ledger_path = Path(args.ledger) if args.ledger else None
    ledger = read_ledger(ledger_path) if ledger_path else None

    result, updated_ledger = process(args.subject, body_bytes, queue, ledger)

    # Write output before committing the ledger; if output fails, event is not marked processed.
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out == "-":
        print(rendered, end="")
    else:
        Path(args.out).write_text(rendered, encoding="utf-8")

    # Commit only accepted events after successful output.
    if ledger_path and result.get("event_status") == "ACCEPTED":
        atomic_write_json(ledger_path, updated_ledger)

    if result.get("event_status") == "REJECTED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
