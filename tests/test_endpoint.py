import json
import os
import tempfile
import unittest
from pathlib import Path

import endpoint


class EndpointTests(unittest.TestCase):
    def write_snapshot(self, directory: Path, stamp: str, rows: list[dict]) -> Path:
        path = directory / f"reels_insights_{stamp}.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        return path

    def test_latest_snapshot_uses_utc_filename_stamp(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            newest = self.write_snapshot(data_dir, "20260905T235542Z", [])
            older = self.write_snapshot(data_dir, "20260905T230900Z", [])
            os.utime(older, (newest.stat().st_mtime + 60,) * 2)

            self.assertEqual(endpoint.find_latest_snapshot(data_dir), newest)

    def test_public_payload_uses_allowlist_and_removes_errors_and_secrets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            snapshot = self.write_snapshot(
                data_dir,
                "20260905T235542Z",
                [
                    {
                        "id": "123",
                        "views": 10,
                        "caption": "Yorkie",
                        "views_error": "internal error",
                        "access_token": "must-not-leak",
                    }
                ],
            )

            payload = endpoint.build_payload(snapshot)

            self.assertEqual(payload["generated_at"], "2026-09-05T23:55:42Z")
            self.assertEqual(payload["reels_count"], 1)
            self.assertEqual(
                payload["items"],
                [{"id": "123", "caption": "Yorkie", "views": 10}],
            )

    def test_atomic_write_creates_valid_json(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "api" / "latest.json"
            payload = {"ok": True, "items": []}

            endpoint.write_json_atomic(destination, payload)

            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8")), payload
            )

    def test_invalid_snapshot_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "reels_insights_20260905T235542Z.json"
            path.write_text('{"not": "a list"}', encoding="utf-8")

            with self.assertRaises(ValueError):
                endpoint.build_payload(path)


if __name__ == "__main__":
    unittest.main()
