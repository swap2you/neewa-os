import json
import os
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = SourceFileLoader("neewa_home_bridge_test", str(ROOT / "12_SCRIPTS" / "neewa_home_bridge.py")).load_module()
HEALTH = SourceFileLoader("neewa_app_health_test", str(ROOT / "12_SCRIPTS" / "neewa_app_health.py")).load_module()
AUTO = SourceFileLoader("neewa_autonomy_home_test", str(ROOT / "12_SCRIPTS" / "neewa_autonomy.py")).load_module()


class HomeBridgeTests(unittest.TestCase):
    def test_submit_creates_durable_mission_and_blocks_deploy(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NEEWA_HOME_SNAPSHOT_DIR"] = str(Path(tmp) / "snap")
            created = BRIDGE.submit(
                "Add a README note describing the current test helper. Do not deploy.",
                origin="home",
                workspace=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox",
                root=Path(tmp) / "jobs",
            )
            self.assertEqual(created["status"], "CREATED", created)
            self.assertTrue(created["mission"]["mission_id"].startswith("MISSION-"))
            self.assertEqual(created["mission"]["origin"], "home")
            self.assertFalse(created["authorization_bypass"])
            current = json.loads((Path(tmp) / "snap" / "current.json").read_text(encoding="utf-8"))
            self.assertEqual(current["mission_id"], created["mission"]["mission_id"])
            blocked = BRIDGE.submit(
                "deploy this to production",
                origin="home",
                root=Path(tmp) / "jobs2",
            )
            self.assertEqual(blocked["status"], "BLOCKED")
            self.assertIn(blocked.get("needed"), {"A2", "A3", "DENIED"})
            os.environ.pop("NEEWA_HOME_SNAPSHOT_DIR", None)

    def test_chatbot_origin_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NEEWA_HOME_SNAPSHOT_DIR"] = str(Path(tmp) / "snap")
            created = BRIDGE.submit(
                "Write a one-line comment in a personal sandbox note. Do not publish.",
                origin="chatbot",
                workspace=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox",
                root=Path(tmp) / "jobs",
            )
            self.assertEqual(created["status"], "CREATED", created)
            self.assertEqual(created["mission"]["origin"], "chatbot")
            os.environ.pop("NEEWA_HOME_SNAPSHOT_DIR", None)


class AppHealthTests(unittest.TestCase):
    def test_incident_is_sanitized_and_not_authorization(self):
        incident = HEALTH.capture_incident(
            source="frontend",
            message="boom api_key=sk-secret token=abc",
            stack="Error: boom",
            route="/neewa-home",
        )
        self.assertIn("[redacted]", incident["message"])
        self.assertNotIn("sk-secret", incident["message"])
        self.assertEqual(incident["authorization"], "NOT_GRANTED_BY_ERROR")
        self.assertFalse(incident["privileged"])
        plan = HEALTH.recovery_plan(incident, files=["16_WINDOWS_CLIENT/assets/neewa-command-center/plugin.js"], expected_base_sha="ab16982")
        self.assertFalse(plan["authorization_from_error"])
        self.assertFalse(plan["auto_merge"])
        self.assertTrue(plan["requires_independent_validation"])


class CouncilReceiptTests(unittest.TestCase):
    def test_council_holds_without_bound_receipt_and_passes_with_one(self):
        held = AUTO.run_council({"objective": "x", "changed_files": [], "acceptance": []})
        self.assertEqual(held["roles"]["IMPLEMENTER"]["may_certify_self"], False)
        self.assertEqual(held["roles"]["INDEPENDENT_TEST_VALIDATOR"]["decision"], "REQUIRED")
        self.assertEqual(held["roles"]["RELEASE_CONTROLLER"]["decision"], "HOLD_FOR_INDEPENDENT_VALIDATION")
        self.assertFalse(held["roles"]["INDEPENDENT_TEST_VALIDATOR"]["github_user"])
        passed = AUTO.run_council(
            {
                "objective": "x",
                "changed_files": [],
                "acceptance": [],
                "validation_receipt": {
                    "ok": True,
                    "result": "PASS",
                    "executor": "neewa-independent-validator",
                    "role": "INDEPENDENT_TEST_VALIDATOR",
                },
            }
        )
        self.assertEqual(passed["roles"]["INDEPENDENT_TEST_VALIDATOR"]["decision"], "PASS")
        self.assertEqual(passed["roles"]["RELEASE_CONTROLLER"]["decision"], "MERGE_ELIGIBLE")
        self.assertEqual(passed["independence_class"], "deterministic_only")


if __name__ == "__main__":
    unittest.main()
