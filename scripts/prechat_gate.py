#!/usr/bin/env python3
"""
Pre-chat idempotency gate.
This gate may inspect Gmail transport metadata, but the NEW CHAT input remains body-only.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from tempfile import NamedTemporaryFile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_payload import (
    EVENT_TYPE, SOURCE_PATH, SCHEMA_VERSION,
    validate_payload_bytes, source_event_id,
)

def read_ledger(path: Path) -> dict:
    if not path.exists():
        return {
            "schema_version": 2,
            "provider_message_ids": [],
            "source_event_ids": [],
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": 2,
        "provider_message_ids": list(data.get("provider_message_ids", [])),
        "source_event_ids": list(data.get("source_event_ids", [])),
    }

def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
        tmp = Path(f.name)
    tmp.replace(path)

def gate(subject: str, raw_body: bytes, ledger: dict, provider_message_id: str | None = None):
    if subject != EVENT_TYPE:
        return {
            "gate_status": "REJECTED",
            "reason": "SUBJECT_MISMATCH",
        }, ledger

    try:
        validated = validate_payload_bytes(raw_body)
    except Exception as e:
        return {
            "gate_status": "REJECTED",
            "reason": "INVALID_PAYLOAD",
            "error": str(e),
        }, ledger

    sid = source_event_id(raw_body, validated["generated_at"])
    mid = (provider_message_id or "").strip() or None

    if mid and mid in ledger["provider_message_ids"]:
        return {
            "gate_status": "DUPLICATE",
            "duplicate_by": "provider_message_id",
            "provider_message_id": mid,
            "source_event_id": sid,
            "action": "DO_NOT_CREATE_NEW_CHAT",
        }, ledger

    if sid in ledger["source_event_ids"]:
        return {
            "gate_status": "DUPLICATE",
            "duplicate_by": "source_event_id",
            "provider_message_id": mid,
            "source_event_id": sid,
            "action": "DO_NOT_CREATE_NEW_CHAT",
        }, ledger

    new_ledger = {
        "schema_version": 2,
        "provider_message_ids": ledger["provider_message_ids"] + ([mid] if mid else []),
        "source_event_ids": ledger["source_event_ids"] + [sid],
    }

    return {
        "gate_status": "ALLOW_NEW_CHAT",
        "provider_message_id": mid,
        "source_event_id": sid,
        "event_type": EVENT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source_path": SOURCE_PATH,
        "generated_at": validated["generated_at"],
        "new_chat_input": "RAW_EMAIL_BODY_ONLY",
    }, new_ledger

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("body_file")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--provider-message-id")
    ap.add_argument("--ledger", required=True)
    args = ap.parse_args()

    raw = Path(args.body_file).read_bytes()
    ledger_path = Path(args.ledger)
    ledger = read_ledger(ledger_path)
    result, updated = gate(args.subject, raw, ledger, args.provider_message_id)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["gate_status"] == "ALLOW_NEW_CHAT":
        atomic_write(ledger_path, updated)
        return
    if result["gate_status"] == "DUPLICATE":
        return
    raise SystemExit(2)

if __name__ == "__main__":
    main()
