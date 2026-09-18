import json
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MISSION_PY = ROOT / "12_SCRIPTS" / "neewa_mission.py"
AUTO_PY = ROOT / "12_SCRIPTS" / "neewa_autonomy.py"
SANDBOX = r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox"


class MissionSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.mission = SourceFileLoader("neewa_mission_test", str(MISSION_PY)).load_module()
        self.auto = SourceFileLoader("neewa_autonomy_mission_test", str(AUTO_PY)).load_module()

    def _create(self, tmp: Path, **kwargs):
        root = tmp / "jobs"
        mission = self.mission.create_mission(
            kwargs.pop("objective", "Supervisor diagnostic: persist and report without Cursor."),
            workspace=kwargs.pop("workspace", SANDBOX),
            root=root,
            auto=self.auto,
            **kwargs,
        )
        return root, mission

    def _step(self, mission, root, **kwargs):
        return self.mission.step_mission(mission, root=root, auto=self.auto, **kwargs)

    def _drive_diagnostic(self, root, mission):
        for _ in range(8):
            mission = self._step(mission, root)
            if mission["state"] in self.mission.TERMINAL:
                break
        return mission

    def test_create_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(Path(tmp), kind="diagnostic")
            path = root / f"{mission['mission_id']}.json"
            self.assertTrue(path.is_file())
            loaded = self.mission.load_mission(mission["mission_id"], root)
            self.assertEqual(loaded["state"], "CREATED")
            self.assertEqual(loaded["owner_objective"], mission["owner_objective"])
            self.assertIsNone(loaded["active_job_id"])
            self.assertEqual(loaded["max_repair_cycles"], 3)

    def test_execution_after_conversation_termination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(Path(tmp), kind="diagnostic")
            mission_id = mission["mission_id"]
            del mission
            results = self.mission.supervisor_once(root=root, auto=self.auto)
            self.assertEqual(results[0]["mission_id"], mission_id)
            loaded = self.mission.load_mission(mission_id, root)
            self.assertEqual(loaded["state"], "PREFLIGHT")

    def test_recovery_after_runner_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(Path(tmp), kind="diagnostic")
            mission = self._step(mission, root)
            self.assertEqual(mission["state"], "PREFLIGHT")
            restarted = self.mission.load_mission(mission["mission_id"], root)
            restarted = self._step(restarted, root)
            self.assertEqual(restarted["state"], "PLANNING")

    def test_duplicate_dispatch_prevention(self):
        created = []

        def create_parent_job(objective, **kwargs):
            job = self.auto.create_parent_job(objective, **kwargs)
            created.append(job["job_id"])
            return job

        class Auto:
            def __getattr__(self, name):
                if name == "create_parent_job":
                    return create_parent_job
                return getattr(self.auto_mod, name)

        wrapper = Auto()
        wrapper.auto_mod = self.auto
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(
                Path(tmp),
                kind="sdlc",
                objective="build a markdown changelog digest CLI with tests",
            )
            mission = self.mission.step_mission(mission, root=root, auto=wrapper)
            mission = self.mission.step_mission(mission, root=root, auto=wrapper)
            self.assertEqual(mission["state"], "PLANNING")
            mission = self.mission.step_mission(mission, root=root, auto=wrapper)
            self.assertEqual(mission["state"], "EXECUTING")
            first = mission["active_job_id"]
            mission = self.mission.step_mission(mission, root=root, auto=wrapper)
            mission["state"] = "PLANNING"
            self.mission.save_mission(mission, root)
            mission = self.mission.step_mission(mission, root=root, auto=wrapper)
            self.assertEqual(mission["active_job_id"], first)
            self.assertEqual(created, [first])
            self.assertEqual(mission["job_ids"], [first])

    def test_cursor_delegation_creates_owned_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(
                Path(tmp),
                kind="sdlc",
                objective="build a markdown changelog digest CLI with tests",
            )
            for _ in range(3):
                mission = self._step(mission, root)
            self.assertEqual(mission["state"], "EXECUTING")
            job = self.auto.resume_job(mission["active_job_id"], root)
            self.assertEqual(job["mission_id"], mission["mission_id"])
            self.assertEqual(job["origin"], "mission-supervisor")
            self.assertTrue(str(job["job_id"]).startswith("JOB-"))

    def test_successful_validation_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            (root / "runner-heartbeat.json").parent.mkdir(parents=True, exist_ok=True)
            self.auto.save_json(root / "runner-heartbeat.json", {"at": "2026-09-18T04:00:00Z", "pid": 1})
            mission = self.mission.create_mission(
                "Supervisor diagnostic: persist and report without Cursor.",
                workspace=SANDBOX,
                root=root,
                kind="diagnostic",
                auto=self.auto,
            )
            mission = self._drive_diagnostic(root, mission)
            self.assertEqual(mission["state"], "OWNER_REVIEW")
            self.assertTrue(Path(mission["report_path"]).is_file())
            report = json.loads((root / "work" / mission["mission_id"] / "final-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["terminal_result"], "OWNER_REVIEW")

    def _failed_owned_job(self, root, mission, suffix, cls="VALIDATION"):
        job = self.auto.create_parent_job(
            mission["owner_objective"],
            workspace=mission.get("workspace"),
            root=root,
            origin="mission-supervisor",
            mission_id=mission["mission_id"],
        )
        job["state"] = "FAILED"
        job["failure_class"] = cls
        job["failure_reason"] = f"simulated-{suffix}"
        job["active_child_id"] = f"CHILD-{suffix}"
        self.auto.save_job(job)
        mission["active_job_id"] = job["job_id"]
        if job["job_id"] not in mission["job_ids"]:
            mission["job_ids"].append(job["job_id"])
        mission["state"] = "RECOVERING"
        self.mission.save_mission(mission, root)
        return job

    def test_recoverable_failure_starts_new_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(
                Path(tmp),
                kind="sdlc",
                objective="build a markdown changelog digest CLI with tests",
            )
            self._failed_owned_job(root, mission, "a")
            updated = self._step(mission, root, worker_available=True)
            self.assertEqual(updated["state"], "PLANNING")
            self.assertEqual(updated["repair_cycles"], 1)
            self.assertIsNone(updated["active_job_id"])
            updated = self._step(updated, root)
            self.assertEqual(updated["state"], "EXECUTING")
            self.assertEqual(len(updated["job_ids"]), 2)
            self.assertNotEqual(updated["job_ids"][0], updated["job_ids"][1])

    def test_repeated_identical_failure_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(
                Path(tmp),
                kind="sdlc",
                objective="build a markdown changelog digest CLI with tests",
            )
            self._failed_owned_job(root, mission, "same")
            first = self._step(mission, root, worker_available=True)
            self.assertEqual(first["state"], "PLANNING")
            self._failed_owned_job(root, first, "same")
            second = self._step(first, root, worker_available=True)
            self.assertEqual(second["state"], "FAILED")
            self.assertEqual(second["failure_reason"], "IDENTICAL_FAILURE_NO_NEW_EVIDENCE")

    def test_worker_unavailability_waits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(
                Path(tmp),
                kind="sdlc",
                objective="build a markdown changelog digest CLI with tests",
            )
            for _ in range(3):
                mission = self._step(mission, root, worker_available=True)
            self.assertEqual(mission["state"], "EXECUTING")
            job = self.auto.resume_job(mission["active_job_id"], root)
            job["state"] = "WAITING"
            job["failure_reason"] = "coding worker missing"
            self.auto.save_job(job)
            updated = self._step(mission, root, worker_available=False)
            self.assertEqual(updated["state"], "WAITING")
            parked = self._step(updated, root, worker_available=False)
            self.assertEqual(parked["state"], "WAITING")
            resumed = self._step(parked, root, worker_available=True)
            self.assertEqual(resumed["state"], "EXECUTING")
            self.assertEqual(resumed["active_job_id"], mission["active_job_id"])

    def test_credit_exhaustion_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(
                Path(tmp),
                kind="diagnostic",
                budget_ceiling=0,
            )
            mission = self._step(mission, root)
            mission = self._step(mission, root)
            self.assertEqual(mission["state"], "BLOCKED")
            self.assertEqual(mission["failure_reason"], "BUDGET_EXHAUSTED")

    def test_advisor_unavailability_is_reported(self):
        consult = self.mission.consult_advisors(
            {"hash": "abc", "classification": {"class": "VALIDATION"}},
            invoke=False,
        )
        roles = {row["role"]: row for row in consult["advisors"]}
        self.assertEqual(roles["claude-opus"]["status"], "UNAVAILABLE")
        self.assertIn("not listed", roles["claude-opus"]["reason"])
        self.assertEqual(roles["gpt-5.6-sol"]["status"], "CONFIGURED_NOT_INVOKED")
        self.assertEqual(roles["gpt-5.6-sol"]["id"], "neewa-premium")
        self.assertFalse(consult["fake_consultation"])
        exhausted = self.mission.consult_advisors(
            {"hash": "abc"},
            invoke=True,
            invoke_fn=lambda *_: {"status": "CONSULTED", "response": "should not run"},
            budget_ok=False,
        )
        sol = next(r for r in exhausted["advisors"] if r["role"] == "gpt-5.6-sol")
        self.assertEqual(sol["status"], "UNAVAILABLE")
        self.assertEqual(sol["reason"], "BUDGET_EXHAUSTED")
        self.assertIsNone(sol["response"])

    def test_three_cycle_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(
                Path(tmp),
                kind="sdlc",
                objective="build a markdown changelog digest CLI with tests",
            )
            for index in range(3):
                self._failed_owned_job(root, mission, f"cycle-{index}")
                mission = self._step(mission, root, worker_available=True)
                self.assertEqual(mission["state"], "PLANNING", mission.get("failure_reason"))
            self._failed_owned_job(root, mission, "cycle-final")
            mission = self._step(mission, root, worker_available=True)
            self.assertEqual(mission["state"], "FAILED")
            self.assertEqual(mission["failure_reason"], "MAX_REPAIR_CYCLES")
            self.assertEqual(mission["repair_cycles"], 3)

    def test_final_report_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(Path(tmp), kind="diagnostic")
            mission = self._drive_diagnostic(root, mission)
            md = Path(mission["report_path"])
            self.assertTrue(md.is_file())
            self.assertIn(mission["mission_id"], md.read_text(encoding="utf-8"))

    def test_does_not_reopen_historical_terminal_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(
                Path(tmp),
                kind="sdlc",
                objective="build a markdown changelog digest CLI with tests",
            )
            historical = self.auto.create_parent_job(
                "historical failed job",
                workspace=SANDBOX,
                root=root,
                origin="conversation",
            )
            historical["state"] = "FAILED"
            historical["failure_class"] = "VALIDATION"
            self.auto.save_job(historical)
            mission["active_job_id"] = historical["job_id"]
            self.mission.save_mission(mission, root)
            for _ in range(3):
                mission = self._step(mission, root)
            self.assertNotEqual(mission.get("active_job_id"), historical["job_id"])
            reloaded = self.auto.resume_job(historical["job_id"], root)
            self.assertEqual(reloaded["state"], "FAILED")

    def test_expired_lease_is_not_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(
                Path(tmp),
                kind="sdlc",
                objective="build a markdown changelog digest CLI with tests",
            )
            for _ in range(3):
                mission = self._step(mission, root)
            job = self.auto.resume_job(mission["active_job_id"], root)
            job["state"] = "EXECUTING"
            job["active_child_id"] = "JOB-LIVE"
            job["lease"] = {"owner": 1, "expires_at": "2000-01-01T00:00:00Z"}
            job["updated_at"] = self.auto.utc_now()
            self.auto.save_job(job)
            advanced = {"n": 0}

            def advance_job(current, **kwargs):
                advanced["n"] += 1
                return current

            class Auto:
                def __getattr__(self, name):
                    if name == "advance_job":
                        return advance_job
                    return getattr(self.auto_mod, name)

            wrapper = Auto()
            wrapper.auto_mod = self.auto
            updated = self.mission.step_mission(
                mission, root=root, auto=wrapper, worker_available=True
            )
            self.assertEqual(updated["state"], "EXECUTING")
            self.assertEqual(advanced["n"], 1)
            self.assertNotIn(updated["state"], {"FAILED", "RECOVERING"})

    def test_runner_once_runs_supervisor_and_skips_owned_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(Path(tmp), kind="diagnostic")
            owned = self.auto.create_parent_job(
                "owned by mission",
                workspace=SANDBOX,
                root=root,
                origin="mission-supervisor",
                mission_id=mission["mission_id"],
            )
            owned["state"] = "OWNER_REVIEW"
            self.auto.save_job(owned)
            standalone = self.auto.create_parent_job(
                "standalone conversation job",
                workspace=SANDBOX,
                root=root,
                origin="conversation",
            )
            results = self.auto.runner_once(
                root=root,
                orch_submit=lambda **k: {"job_id": k["job_id"], "state": "DISPATCHED"},
            )
            self.assertTrue(any(r.get("mission_id") == mission["mission_id"] for r in results))
            self.assertTrue(
                any(r.get("job_id") == owned["job_id"] and r.get("skipped") == "mission_owned" for r in results)
            )
            self.assertTrue(any(r.get("job_id") == standalone["job_id"] and not r.get("skipped") for r in results))
            loaded = self.mission.load_mission(mission["mission_id"], root)
            self.assertEqual(loaded["state"], "PREFLIGHT")

    def test_cost_unknown_blocks_without_switching_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(Path(tmp), kind="sdlc")
            mission["budget"]["ceiling"] = None
            self.mission.save_mission(mission, root)
            mission = self._step(mission, root)
            mission = self._step(mission, root)
            self.assertEqual(mission["state"], "BLOCKED")
            self.assertEqual(mission["failure_reason"], "COST_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
