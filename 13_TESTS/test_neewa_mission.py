import json
import copy
import tempfile
import unittest
from unittest.mock import patch
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

    def test_chakraops_following_stages_dispatch_as_software_with_safety_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(Path(tmp), kind="sdlc", project_id="PRJ-CHAKRAOPS",
                workspace=r"C:\Users\swap2\NEEWA-Personal\projects\ChakraOps", objective="Repair ORATS with tests")
            for stage in mission["stage_plan"][1:]:
                with self.subTest(stage=stage["id"]):
                    job = self.auto.create_parent_job(stage["objective"], project_id=mission["project_id"],
                        workspace=mission["workspace"], root=root, mission_id=mission["mission_id"])
                    self.assertEqual(job["workflow"], "sdlc")
                    gate = self.auto.authorize_execution(approval_level="A1", owner_decision=None,
                        prompt=stage["objective"], repo=mission["workspace"], write=True)
                    self.assertTrue(gate["allowed"], gate)
                    bad = self.auto.authorize_execution(approval_level="A1", owner_decision=None,
                        prompt=stage["objective"] + " Place order now.", repo=mission["workspace"], write=True)
                    self.assertFalse(bad["allowed"])

    def test_stage_routing_migrates_only_unstarted_exact_legacy_objectives(self):
        old_text = dict(self.mission.CHAKRAOPS_STAGES)["no_signal_evidence"] + " Broker order actions stay denied."
        mission = {"project_id": "PRJ-CHAKRAOPS", "stage_plan": [
            {"id":"orats_reconciliation", "status":"in_progress", "objective":"Owner original"},
            {"id":"no_signal_evidence", "status":"not_started", "objective":old_text},
            {"id":"strategy_explanation", "status":"not_started", "objective":"Owner scoped custom objective"},
            {"id":"position_math", "status":"completed", "objective":"Preserved accepted objective"},
        ]}
        self.mission.ensure_stage_plan(mission)
        plan = {s["id"]:s for s in mission["stage_plan"]}
        self.assertTrue(plan["no_signal_evidence"]["objective"].startswith("Implement and verify"))
        self.assertEqual(plan["orats_reconciliation"]["objective"], "Owner original")
        self.assertEqual(plan["strategy_explanation"]["objective"], "Owner scoped custom objective")
        self.assertEqual(plan["position_math"]["objective"], "Preserved accepted objective")
        before = copy.deepcopy(mission)
        self.mission.ensure_stage_plan(mission)
        self.assertEqual(mission, before)

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

    def test_mission_success_requires_independent_validation_pass(self):
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
            self.assertEqual(job["origin"], "mission-supervisor")

            claimed = dict(job)
            claimed["state"] = "OWNER_REVIEW"
            claimed["validation"] = {"independent_rerun": "IMPLEMENTER_CLAIMED", "tests": "PASS"}
            self.auto.save_job(claimed)
            rejected = self._step(mission, root)
            self.assertEqual(rejected["state"], "RECOVERING")
            self.assertIn("independent_validation PASS", rejected.get("history", [{}])[-1].get("note", ""))

            passed = self.auto.resume_job(mission["active_job_id"], root)
            passed["state"] = "OWNER_REVIEW"
            passed["validation"] = {
                "independent_rerun": "PASS",
                "tests": "PASS",
                "traceability": "PASS",
                "council": "CHECKLIST_ONLY",
                "review_decision": "APPROVE",
            }
            passed["independent_validation"] = {"execution_phase": "independent_validation"}
            self.auto.save_job(passed)
            # Mission may be RECOVERING; reconcile success path should move to VALIDATING then OWNER_REVIEW.
            mission = rejected
            mission = self._step(mission, root)
            self.assertEqual(mission["state"], "VALIDATING")
            mission = self._step(mission, root)
            self.assertEqual(mission["state"], "OWNER_REVIEW")
            self.assertTrue(self.mission.job_meets_mission_success(passed))
            self.assertFalse(
                self.mission.job_meets_mission_success(
                    {"state": "OWNER_REVIEW", "validation": {"independent_rerun": "PASS", "review_decision": "OBJECT"}}
                )
            )
            self.assertFalse(
                self.mission.job_meets_mission_success(
                    {"state": "OWNER_REVIEW", "validation": {"independent_rerun": "IMPLEMENTER_CLAIMED"}}
                )
            )

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

    def test_review_objection_recovery_delivers_feedback_to_current_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(Path(tmp), kind="sdlc", objective="build a changelog CLI with tests")
            mission["stage_objective"] = "Verify CLI failure states"
            job = self._failed_owned_job(root, mission, "review", cls="REVIEW_OBJECTION")
            job["validation"] = {"review_decision": "OBJECT", "review_feedback": "Missing invalid-input test. Do not deploy to production.", "review_artifacts": ["done/review.txt"]}
            self.auto.save_job(job)
            updated = self._step(mission, root, worker_available=True)
            self.assertEqual(updated["state"], "PLANNING")
            self.assertIn("Verify CLI failure states", updated["repair_objective"])
            self.assertIn("Missing invalid-input test", updated["repair_review_context"])
            self.assertIn("done/review.txt", updated["repair_review_context"])
            self.assertNotIn("deploy to production", updated["repair_objective"])
            updated = self._step(updated, root)
            dispatched = self.auto.resume_job(updated["active_job_id"], root)
            self.assertEqual(dispatched["parent_objective"], updated["repair_objective"])
            self.assertEqual(dispatched["repair_review_context"], updated["repair_review_context"])
            requirements = self.auto.build_requirements(dispatched["parent_objective"], workspace=dispatched["workspace"])
            design = self.auto.initial_design(requirements, dispatched["parent_objective"])
            prompt = self.auto.build_worker_prompt(dispatched, requirements, design)
            self.assertIn("Missing invalid-input test", prompt)
            gate = self.auto.authorize_execution(approval_level="A1", prompt=prompt, repo=dispatched["workspace"], write=True)
            self.assertTrue(gate["allowed"], gate)
            self.assertEqual(job["state"], "FAILED")

    def test_changed_review_feedback_tail_is_new_recovery_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(Path(tmp), kind="sdlc", objective="build a CLI with tests")
            job = self._failed_owned_job(root, mission, "same-review", cls="REVIEW_OBJECTION")
            job["validation"] = {"review_feedback": "x" * 3000 + "first objection"}
            self.auto.save_job(job)
            first = self._step(mission, root, worker_available=True)
            self.assertEqual(first["state"], "PLANNING")
            changed = self._failed_owned_job(root, first, "same-review", cls="REVIEW_OBJECTION")
            changed["validation"] = {"review_feedback": "x" * 3000 + "new objection"}
            self.auto.save_job(changed)
            second = self._step(first, root, worker_available=True)
            self.assertEqual(second["state"], "PLANNING")
            self.assertEqual(second["repair_cycles"], 2)

    def test_missing_review_evidence_is_recoverable_without_approval(self):
        classified = self.mission.classify_failure({"state": "FAILED", "failure_class": "REVIEW_EVIDENCE_MISSING"})
        self.assertTrue(classified["recoverable"])
        self.assertFalse(self.mission.job_meets_mission_success({"state": "OWNER_REVIEW", "validation": {"independent_rerun": "PASS"}}))

    def _accepted_final_stage(self, tmp, state="OWNER_REVIEW"):
        root, mission = self._create(tmp, kind="sdlc", objective="build a CLI with tests")
        mission.update(state=state, active_stage_id="follow_through", stage_objective="Verify remaining acceptance",
                       repair_cycles=2, retry_count=7, terminal_result="OWNER_REVIEW")
        mission["stage_plan"] = [
            {"id": "delivery", "status": "completed", "objective": "Build CLI"},
            {"id": "follow_through", "status": "in_progress", "objective": "Verify remaining acceptance"},
        ]
        mission["failure_history"] = [{"reason": "preserved failure"}]
        job = self.auto.create_parent_job("Verify remaining acceptance", workspace=SANDBOX, root=root,
                                          mission_id=mission["mission_id"], origin="mission-supervisor")
        job.update(state="OWNER_REVIEW", validation={
            "independent_rerun": "PASS", "traceability": "PASS", "review_decision": "APPROVE",
            "independent_test_receipt": {"job_id": "IT-7", "collected": 7,
                                         "candidate_head": "a" * 40, "transcript_sha256": "b" * 64},
        })
        self.auto.save_job(job)
        mission["active_job_id"] = job["job_id"]
        mission["job_ids"] = [job["job_id"]]
        self.mission.save_mission(mission, root)
        return root, mission, job

    def test_accepted_final_stage_closes_during_validation_without_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission, job = self._accepted_final_stage(Path(tmp), state="VALIDATING")
            mission["auto_continue"] = False
            with patch.object(self.auto, "create_parent_job", side_effect=AssertionError("unexpected dispatch")):
                updated = self._step(mission, root)
            stage = updated["stage_plan"][-1]
            self.assertEqual(updated["state"], "OWNER_REVIEW")
            self.assertEqual(stage["status"], "completed")
            self.assertEqual(stage["completion_job_id"], job["job_id"])
            self.assertEqual(stage["completion_evidence"]["collected"], 7)

    def test_persisted_final_stage_reconciliation_is_idempotent_and_preserves_history_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission, job = self._accepted_final_stage(Path(tmp))
            before = copy.deepcopy(mission)
            with patch.object(self.auto, "create_parent_job", side_effect=AssertionError("unexpected dispatch")):
                self.mission.supervisor_once(root=root, auto=self.auto)
                repaired = self.mission.load_mission(mission["mission_id"], root)
                self.assertEqual(repaired["stage_plan"][-1]["status"], "completed")
                self.mission.supervisor_once(root=root, auto=self.auto)
                repeated = self.mission.load_mission(mission["mission_id"], root)
            self.assertEqual(repeated, repaired)
            for key in ("budget", "retry_count", "repair_cycles", "failure_history", "terminal_result", "job_ids"):
                self.assertEqual(repeated[key], before[key], key)
            report = json.loads((root / "work" / mission["mission_id"] / "final-report.json").read_text())
            self.assertEqual(report["stage_plan"][-1]["completion_job_id"], job["job_id"])

    def test_final_stage_rejects_wrong_or_incomplete_acceptance_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission, job = self._accepted_final_stage(Path(tmp))
            changes = (
                {"mission_id": "other-mission"}, {"mission_stage_id": "delivery"},
                {"parent_objective": "Build CLI"}, {"job_id": "other-job"},
                {"validation": {"independent_rerun": "IMPLEMENTER_CLAIMED", "traceability": "PASS", "review_decision": "APPROVE"}},
                {"validation": {"independent_rerun": "PASS", "traceability": "FAIL", "review_decision": "APPROVE"}},
                {"validation": {"independent_rerun": "PASS", "traceability": "PASS", "review_decision": "OBJECT"}},
            )
            for change in changes:
                with self.subTest(change=change):
                    candidate = dict(job, **change)
                    original = copy.deepcopy(mission)
                    self.assertFalse(self.mission.complete_accepted_stage(mission, candidate))
                    self.assertEqual(mission, original)
            self.assertFalse(self.mission.complete_accepted_stage(mission, None))

    def test_final_stage_reconciliation_does_not_reopen_historical_terminals_or_ambiguous_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission, job = self._accepted_final_stage(Path(tmp))
            for state in ("FAILED", "CANCELLED", "BLOCKED"):
                historical = copy.deepcopy(mission)
                historical["state"] = state
                self.assertFalse(self.mission.reconcile_final_stage(historical, root, self.auto))
                self.assertEqual(historical["stage_plan"][-1]["status"], "in_progress")
            mission["stage_plan"][0]["status"] = "in_progress"
            self.assertFalse(self.mission.complete_accepted_stage(mission, job))
            self.assertFalse(self.mission.reconcile_final_stage(mission, root, self.auto))

    def test_stage_advance_preserves_repair_history_and_starts_fresh_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(Path(tmp), kind="sdlc", objective="build a CLI with tests")
            mission.update(state="OWNER_REVIEW", auto_continue=True, repair_cycles=3, infrastructure_retries=2,
                           repair_objective="obsolete repair", last_failure_signature="old", last_evidence_hash="old", retry_count=5)
            mission["stage_plan"] = [{"id": "first", "status": "in_progress", "objective": "First stage"},
                                     {"id": "second", "status": "not_started", "objective": "Second stage"}]
            mission["failure_history"] = [{"reason": "old failure"}]
            updated = self.mission.advance_stage(mission, root)
            self.assertEqual(updated["repair_cycles"], 0)
            self.assertEqual(updated["infrastructure_retries"], 0)
            self.assertIsNone(updated.get("repair_objective"))
            self.assertIsNone(updated.get("last_evidence_hash"))
            self.assertEqual(updated["stage_plan"][0]["repair_summary"]["repair_cycles"], 3)
            self.assertEqual(updated["retry_count"], 5)
            self.assertEqual(updated["failure_history"], [{"reason": "old failure"}])
            updated = self._step(updated, root)
            self.assertEqual(self.auto.resume_job(updated["active_job_id"], root)["parent_objective"], "Second stage")

    def test_infrastructure_repair_is_dispatched_even_without_implementation_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(Path(tmp), kind="sdlc", objective="build a CLI with tests")
            mission["stage_objective"] = "Verify CLI error handling"
            mission["repair_review_context"] = "Existing open invalid-input objection"
            self._failed_owned_job(root, mission, "temp", cls="NO_USABLE_TEMP")
            updated = self._step(mission, root, worker_available=True)
            self.assertEqual(updated["repair_cycles"], 0)
            updated = self._step(updated, root)
            objective = self.auto.resume_job(updated["active_job_id"], root)["parent_objective"]
            self.assertIn("INFRASTRUCTURE RETRY", objective)
            self.assertIn("Verify CLI error handling", objective)
            self.assertEqual(self.auto.resume_job(updated["active_job_id"], root)["repair_review_context"],
                             "Existing open invalid-input objection")

    def test_wait_expiry_does_not_start_a_repair_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, mission = self._create(
                Path(tmp),
                kind="sdlc",
                objective="build a markdown changelog digest CLI with tests",
            )
            self._failed_owned_job(root, mission, "wait", cls="WAIT_EXPIRED")
            updated = self._step(mission, root, worker_available=True)
            self.assertEqual(updated["state"], "WAITING")
            self.assertEqual(int(updated.get("repair_cycles") or 0), 0)
            self.assertEqual(len(updated["job_ids"]), 1)

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


class MissionObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.mission = SourceFileLoader("neewa_mission_obs", str(MISSION_PY)).load_module()
        self.auto = SourceFileLoader("neewa_autonomy_obs", str(AUTO_PY)).load_module()
        self.inbox = SourceFileLoader(
            "windows_job_inbox_obs", str(ROOT / "12_SCRIPTS" / "windows_job_inbox.py")
        ).load_module()

    def _healthy(self, tmp: Path, *, heartbeat_at="2026-09-18T04:10:00Z"):
        inbox = tmp / "windows-jobs"
        root = inbox / "autonomy"
        (inbox / "done").mkdir(parents=True)
        (inbox / "inbox").mkdir()
        (inbox / "processing").mkdir()
        (inbox / "failed").mkdir()
        self.auto.save_json(root / "runner-heartbeat.json", {"at": heartbeat_at, "pid": 9})
        (inbox / "done" / "JOB-WORKER-RECEIPT.json").write_text("{}", encoding="utf-8")
        return inbox, root

    def test_healthy_host_visible_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, root = self._healthy(Path(tmp))
            report = self.mission.mission_preflight(
                root=root,
                inbox_root=inbox,
                auto=self.auto,
                now=self.mission.datetime.strptime("2026-09-18T04:10:10Z", "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=self.mission.timezone.utc
                ),
                systemd_state="active",
            )
            self.assertTrue(report["submission_safe"], report["blockers"])
            self.assertEqual(report["runner"]["state"], "active")
            self.assertFalse(report["runner"]["heartbeat_stale"])
            self.assertTrue(report["autonomy_storage"]["accessible"])
            self.assertEqual(report["windows_worker"]["status"], "idle")
            self.assertEqual(report["budget"]["provider_credits_remaining"], "UNKNOWN")
            self.assertTrue(report["budget"]["allows_next_cursor_call"])

    def test_stopped_runner_stale_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, root = self._healthy(Path(tmp), heartbeat_at="2026-09-18T03:00:00Z")
            report = self.mission.mission_preflight(
                root=root,
                inbox_root=inbox,
                auto=self.auto,
                now=self.mission.datetime.strptime("2026-09-18T04:10:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=self.mission.timezone.utc
                ),
                systemd_state="inactive",
            )
            self.assertFalse(report["submission_safe"])
            self.assertIn("RUNNER_HEARTBEAT_STALE", report["blockers"])

    def test_missing_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, root = self._healthy(Path(tmp))
            (root / "runner-heartbeat.json").unlink()
            report = self.mission.mission_preflight(
                root=root, inbox_root=inbox, auto=self.auto, systemd_state="unknown"
            )
            self.assertFalse(report["submission_safe"])
            self.assertIn("RUNNER_HEARTBEAT_MISSING", report["blockers"])

    def test_windows_worker_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, root = self._healthy(Path(tmp))
            report = self.mission.mission_preflight(
                root=root,
                inbox_root=Path(tmp) / "missing-worker-inbox",
                auto=self.auto,
                now=self.mission.datetime.strptime("2026-09-18T04:10:10Z", "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=self.mission.timezone.utc
                ),
                systemd_state="active",
            )
            self.assertFalse(report["windows_worker"]["accessible"])
            self.assertEqual(report["windows_worker"]["status"], "unavailable")
            self.assertIn("WINDOWS_WORKER_INBOX_UNAVAILABLE", report["blockers"])
            self.assertFalse(report["submission_safe"])

    def test_unknown_provider_balance_does_not_invent_credits(self):
        credits = self.mission._provider_credits()
        self.assertEqual(credits["remaining"], "UNKNOWN")
        self.assertFalse(credits["authoritative_balance"])
        with tempfile.TemporaryDirectory() as tmp:
            inbox, root = self._healthy(Path(tmp))
            report = self.mission.mission_preflight(
                root=root,
                inbox_root=inbox,
                auto=self.auto,
                now=self.mission.datetime.strptime("2026-09-18T04:10:10Z", "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=self.mission.timezone.utc
                ),
                systemd_state="active",
            )
            self.assertEqual(report["budget"]["provider_credits_remaining"], "UNKNOWN")
            self.assertIn("PROVIDER_CREDITS_UNKNOWN", report["warnings"])
            self.assertTrue(report["submission_safe"])

    def test_duplicate_mission_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobs"
            first = self.mission.create_mission(
                "overnight personal engineering",
                workspace=SANDBOX,
                root=root,
                kind="sdlc",
                auto=self.auto,
            )
            with self.assertRaises(self.mission.DuplicateMission) as raised:
                self.mission.create_mission(
                    "overnight personal engineering",
                    workspace=SANDBOX,
                    root=root,
                    kind="sdlc",
                    auto=self.auto,
                )
            self.assertEqual(raised.exception.existing["mission_id"], first["mission_id"])

    def test_unmounted_host_path_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox_ws = Path(tmp) / "workspace"
            sandbox_ws.mkdir()
            host_ws = Path(tmp) / "absent-host-workspace"
            self.assertTrue(
                self.inbox.in_conversation_sandbox(
                    sandbox_workspace=sandbox_ws, host_workspace=host_ws
                )
            )
            self.assertTrue(
                self.inbox.is_unmounted_host_inbox(
                    "/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs/autonomy",
                    sandbox_workspace=sandbox_ws,
                    host_workspace=host_ws,
                )
            )
            self.assertFalse(
                self.inbox.is_unmounted_host_inbox(
                    "/workspace/windows-jobs/autonomy",
                    sandbox_workspace=sandbox_ws,
                    host_workspace=host_ws,
                )
            )
            overlay = Path(tmp) / "fake-host-workspace"
            overlay.mkdir()
            self.assertTrue(
                self.inbox.in_conversation_sandbox(
                    sandbox_workspace=sandbox_ws, host_workspace=overlay
                )
            )
            self.assertFalse(
                self.inbox.in_conversation_sandbox(
                    sandbox_workspace=sandbox_ws, host_workspace=sandbox_ws
                )
            )

    def test_recovery_after_runner_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox, root = self._healthy(Path(tmp), heartbeat_at="2026-09-18T03:00:00Z")
            now = self.mission.datetime.strptime("2026-09-18T04:10:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=self.mission.timezone.utc
            )
            stopped = self.mission.mission_preflight(
                root=root, inbox_root=inbox, auto=self.auto, now=now, systemd_state="inactive"
            )
            self.assertFalse(stopped["submission_safe"])
            self.auto.save_json(root / "runner-heartbeat.json", {"at": "2026-09-18T04:10:00Z", "pid": 22})
            recovered = self.mission.mission_preflight(
                root=root,
                inbox_root=inbox,
                auto=self.auto,
                now=self.mission.datetime.strptime("2026-09-18T04:10:15Z", "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=self.mission.timezone.utc
                ),
                systemd_state="active",
            )
            self.assertTrue(recovered["submission_safe"], recovered["blockers"])
            self.mission.publish_status_snapshot(recovered, jobs_root=root)
            self.assertTrue((root / "conversation-status.json").is_file())


if __name__ == "__main__":
    unittest.main()

