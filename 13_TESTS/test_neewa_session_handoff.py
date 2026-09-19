import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "12_SCRIPTS"))
import neewa_session_handoff as handoff


class SessionHandoffTests(unittest.TestCase):
    def make_checkpoint(self, directory):
        return handoff.create_checkpoint(
            directory,
            previous_session_id="session-old",
            new_session_id="session-new",
            objective="finish release",
            completed_work=["validated PR"],
            decisions=["do not duplicate jobs"],
            mission_job_ids=["MISSION-1", "JOB-1"],
            branches_commits_prs=["main@abc", "PR#9"],
            test_validation_evidence=["299 tests passed"],
            runtime_versions={"ubuntu_sha": "abc"},
            active_operations=["await host executor"],
            blockers=["host executor unavailable"],
            next_operation="persist exact administrator action",
            acceptance_criteria=["integrity verifies"],
            authoritative_receipts=["/workspace/receipt.json"],
            filename="checkpoint-test.json",
        )

    def test_restart_loads_latest_valid_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_checkpoint(tmp)
            loaded_path, payload = handoff.latest_valid_checkpoint(tmp)
            self.assertEqual(loaded_path, path)
            self.assertEqual(payload["new_session_id"], "session-new")

    def test_corrupted_checkpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_checkpoint(tmp)
            payload = json.loads(path.read_text())
            payload["next_operation"] = "tampered"
            path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                handoff.load_checkpoint(path)
            with self.assertRaises(FileNotFoundError):
                handoff.latest_valid_checkpoint(tmp)

    def test_successor_must_load_before_previous_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_checkpoint(tmp)
            with self.assertRaises(ValueError):
                handoff.close_previous_session(path, "session-new")
            handoff.confirm_successor(path, "session-new")
            closed = handoff.close_previous_session(path, "session-new")
            self.assertEqual(closed["previous_session_status"], "CLOSED")
            self.assertEqual(handoff.load_checkpoint(path)["successor_status"], "LOADED")

    def test_duplicate_live_jobs_block_new_work(self):
        result = handoff.reconcile_live_jobs([
            {"job_id": "JOB-1", "state": "RUNNING"},
            {"job_id": "JOB-1", "state": "QUEUED"},
            {"job_id": "JOB-2", "state": "DONE"},
        ])
        self.assertEqual(result["duplicate_ids"], ["JOB-1"])
        self.assertFalse(result["safe_to_start"])

    def test_secret_like_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                handoff.create_checkpoint(
                    tmp, previous_session_id="old", objective="x", completed_work=[], decisions=[],
                    mission_job_ids=[], branches_commits_prs=[], test_validation_evidence=[],
                    runtime_versions={"api" + "_key": "should-not-persist"}, active_operations=[], blockers=[],
                    next_operation="x", acceptance_criteria=[], authoritative_receipts=[],
                )


if __name__ == "__main__":
    unittest.main()
