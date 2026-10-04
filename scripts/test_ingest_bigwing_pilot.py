"""Safety checks for the small BigWing vector pilot."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock

import ingest_bigwing_pilot as pilot


class BigWingPilotTests(unittest.TestCase):
    @patch.object(pilot.subprocess, "run")
    def test_importer_preserves_admin_edits_and_deletions(self, run):
        run.return_value = Mock(stdout=(
            "00000000-0000-0000-0000-000000000001|hash|source|model\n"
            "00000000-0000-0000-0000-000000000001|MANAGED||\n"),
            returncode=0)
        existing = pilot.existing_hashes()
        self.assertEqual(existing["00000000-0000-0000-0000-000000000001"][0], "MANAGED")
        self.assertIn("the_x_manual_vector_history", run.call_args.kwargs["input"])
        pilot.import_rows([{"id": "00000000-0000-0000-0000-000000000002",
                            "content": "test", "metadata": {}, "embedding": [0.1]}])
        self.assertIn(b"WHERE NOT EXISTS", run.call_args.kwargs["input"])

    def test_passages_are_bounded_traceable_and_stable(self):
        record = {
            "name": "New GB350C", "url_year_hint": 2026,
            "source_url": "https://www.thaihonda.co.th/hondabigbike/motorcycle/classicbike/gb350c-2026",
            "source_sha256": "a" * 64,
            "specifications": [{"group": "Engine", "label": f"Field {i}", "value": "x" * 50}
                               for i in range(35)],
        }
        chunks = list(pilot.passages(record, "2026-10-03T00:00:00+00:00"))
        self.assertGreater(len(chunks), 1)
        self.assertEqual([chunk["id"] for chunk in chunks],
                         [chunk["id"] for chunk in pilot.passages(record, "2026-10-03T00:00:00+00:00")])
        self.assertTrue(all(len(chunk["content"]) <= pilot.MAX_CHARS for chunk in chunks))
        self.assertTrue(all("GB350C" in chunk["content"] and "2026" in chunk["content"]
                            and chunk["metadata"]["source_url"] == record["source_url"]
                            for chunk in chunks))
        self.assertEqual(sum(chunk["content"].count("Field ") for chunk in chunks), 35)

    def test_only_unflagged_records_with_matching_raw_hash_are_eligible(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            url = "https://www.thaihonda.co.th/hondabigbike/motorcycle/classicbike/gb350c-2026"
            path = pilot.cache_path(raw, url)
            path.write_bytes(b"source snapshot")
            record = {"name": "GB350C", "url_year_hint": 2026, "source_url": url,
                      "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "review_status": "pending", "review_flags": [],
                      "specifications": [{"group": "Engine", "label": "CC", "value": "348"}]}
            with patch.object(pilot, "RAW", raw):
                self.assertEqual(pilot.eligible_records({"records": [record]}), [record])
                flagged = {**record, "review_flags": ["year_not_in_url"]}
                stale = {**record, "source_sha256": "0" * 64}
                self.assertEqual(pilot.eligible_records({"records": [flagged, stale]}), [])
                unknown_year = {**record, "url_year_hint": None,
                                "review_flags": ["year_not_in_url"]}
                self.assertEqual(pilot.eligible_records({"records": [unknown_year]}, all_models=True),
                                 [unknown_year])
                passage = next(pilot.passages(unknown_year, "2026-10-03T00:00:00+00:00"))
                self.assertIsNone(passage["metadata"]["year"])
                self.assertIn("ไม่ระบุปี", passage["content"])


if __name__ == "__main__":
    unittest.main()
