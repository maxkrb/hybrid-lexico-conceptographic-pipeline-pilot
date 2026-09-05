import unittest
from pathlib import Path
from urllib.parse import quote

from src.minimal_api import EvidenceStore, ROOT, dispatch_get


class MinimalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = EvidenceStore(ROOT)

    def test_frozen_dataset_counts(self):
        self.assertEqual(self.store.entry_count, 25)
        self.assertEqual(self.store.evidence_record_count, 840)
        self.assertEqual(self.store.release_id, "sum20-hist-ap-pilot-r001")

    def test_successful_evidence_bound_query(self):
        status, payload = dispatch_get(
            self.store,
            "/v1/entries/%D0%90%D0%9A%D0%A2?fields=lemma,pos,definition,examples&example_count=2",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["entry_id"], "sum20-hist-ap-003")
        self.assertEqual(len(payload["claims"]), 5)
        for claim in payload["claims"]:
            self.assertTrue(claim["evidence_id"].startswith("ev1-"))
            self.assertTrue(claim["json_pointer"].startswith("/"))
            self.assertEqual(len(claim["target_sha256"]), 64)

    def test_accent_insensitive_lookup(self):
        status, payload = dispatch_get(
            self.store,
            "/v1/entries/" + quote("АБА́К") + "?fields=lemma,definition",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["entry_id"], "sum20-hist-ap-001")

    def test_refuses_two_examples_when_only_one_is_evidenced(self):
        status, payload = dispatch_get(
            self.store,
            "/v1/entries/%D0%90%D0%91%D0%90%D0%9A?fields=examples&example_count=2",
        )
        self.assertEqual(status, 422)
        self.assertEqual(payload["status"], "refused")
        self.assertEqual(payload["reason"], "EVIDENCE_UNAVAILABLE")
        self.assertEqual(payload["requested_field"], "examples")
        self.assertEqual(payload["requested_count"], 2)
        self.assertEqual(payload["available_count"], 1)

    def test_evidence_resolver_round_trip(self):
        status, query = dispatch_get(
            self.store,
            "/v1/entries/%D0%90%D0%9A%D0%A2?fields=definition",
        )
        self.assertEqual(status, 200)
        claim = query["claims"][0]
        status, resolved = dispatch_get(
            self.store,
            "/v1/evidence/" + claim["evidence_id"],
        )
        self.assertEqual(status, 200)
        self.assertTrue(resolved["verified"])
        self.assertEqual(resolved["value"], claim["value"])
        self.assertEqual(resolved["record"]["json_pointer"], claim["json_pointer"])
        self.assertEqual(resolved["record"]["target_sha256"], claim["target_sha256"])

    def test_unsupported_field_is_not_misreported_as_missing_evidence(self):
        status, payload = dispatch_get(
            self.store,
            "/v1/entries/%D0%90%D0%9A%D0%A2?fields=morphology",
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["reason"], "UNSUPPORTED_FIELD")

    def test_unknown_entry(self):
        status, payload = dispatch_get(self.store, "/v1/entries/NOT-A-LEMMA")
        self.assertEqual(status, 404)
        self.assertEqual(payload["reason"], "ENTRY_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
