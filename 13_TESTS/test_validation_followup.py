"""Behavioral checks for the 2026-10-08 validation follow-up."""
from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from importlib.machinery import SourceFileLoader

ROOT = Path(__file__).resolve().parents[1]
AUTO = SourceFileLoader("neewa_autonomy", str(ROOT / "12_SCRIPTS" / "neewa_autonomy.py")).load_module()
MISSION = SourceFileLoader("neewa_mission", str(ROOT / "12_SCRIPTS" / "neewa_mission.py")).load_module()
ORCH = SourceFileLoader("neewa_orchestrate", str(ROOT / "12_SCRIPTS" / "neewa_orchestrate.py")).load_module()
WORKER = ROOT / "16_WINDOWS_CLIENT" / "worker"


class IndependentContractTests(unittest.TestCase):
    def test_independent_negative_path_evidence_survives_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = AUTO.create_parent_job("verify invalid input", workspace=str(root), root=root, origin="conversation")
            job.update(state="VALIDATING", workflow="sdlc", approval_level="A1",
                       requirements_version="REQ-v1", design_version="DES-v1",
                       active_child_id="JOB-TEST", independent_test_child_id="JOB-TEST", artifacts=["fixture"])
            job["validation"] = {"tests": "PASS", "council": "CHECKLIST_ONLY",
                                 "test_evidence": {"passed": True, "stdout": "1 passed"}}
            work = AUTO.job_workdir(job, root)
            AUTO.save_json(work / "requirements.json", {"requirements": [
                {"id": "REQ-NEG", "kind": "reliability", "check": "negative_path", "text": "reject invalid input"}]})
            AUTO.save_json(work / "design-v1.json", {"summary": "invalid input", "acceptance": ["REQ-NEG"]})
            receipt = {"passed": True, "collected": 1, "exit_code": 0,
                       "stdout_tail": "invalid input verified\n1 passed"}
            def submit(**kwargs):
                return {"job_id": kwargs["job_id"], "state": "DISPATCHED"}
            first = AUTO.advance_job(job, root=root, orch_submit=submit,
                orch_harvest=lambda *_: {"state": "COMPLETED", "independent_test": receipt})
            self.assertEqual(first["validation"]["traceability"], "PASS")
            # A persisted job may predate the harvest-time evidence-copy repair.
            first["validation"]["test_evidence"] = {"passed": True, "stdout": "1 passed"}
            second = AUTO.advance_job(first, root=root, orch_submit=submit,
                orch_harvest=lambda *_: {"state": "COMPLETED", "review_decision": "APPROVE"})
            self.assertEqual(second["state"], "OWNER_REVIEW", second.get("failure_reason"))
            self.assertEqual(second["validation"]["traceability"], "PASS")

    def test_traceability_failure_reports_exact_requirement_and_evidence(self):
        job = {"state": "VALIDATING", "validation": {"traceability": "FAIL", "traceability_rows": [
            {"requirement": "REQ-003", "check": "negative_path", "result": "FAIL", "evidence": ["negative-path not observed"]}]}}
        failure = next(row for row in AUTO.evaluate_autonomy_done(job) if row.startswith("requirements traceability"))
        self.assertIn("REQ-003", failure)
        self.assertIn("negative_path", failure)
        self.assertIn("negative-path not observed", failure)

    def test_review_receipt_is_forwarded_as_structured_worker_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = {"candidate_identity_schema": 2, "candidate_head": "abc", "transcript": "evidence.txt"}
            job = {"job_id": "JOB-REVIEW", "parent_objective": "verify a local change", "workspace": r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\canary",
                   "validation": {"independent_test_receipt": receipt}, "child_jobs": [], "_path": str(Path(tmp) / "JOB-REVIEW.json")}
            seen = {}
            def submit(**kwargs):
                seen.update(kwargs)
                return {"job_id": kwargs["job_id"], "state": "DISPATCHED"}
            AUTO._submit_codex_review(job, "review", inbox_root=None, orch_submit=submit)
            self.assertEqual(seen["test_receipt"], receipt)

    def test_review_prompt_keeps_receipt_tail_and_artifact_references(self):
        job = {"parent_objective": "Verify one error-handling stage", "artifacts": ["done/ui-evidence.png"],
               "repair_review_context": "Check the invalid-input objection", "validation": {
                   "independent_test_receipt": {"stdout_tail": "x" * 5000, "candidate_diff_sha256": "candidate-tail-hash"}}}
        prompt = AUTO.build_validation_prompt(job, {"requirements": ["invalid input"]}, {"summary": "current stage"})
        self.assertIn("candidate-tail-hash", prompt)
        self.assertIn("done/ui-evidence.png", prompt)
        self.assertIn("Check the invalid-input objection", prompt)
        self.assertIn("invalid input", prompt)
        self.assertIn("do not represent a narrow stage as full charter acceptance", prompt)

    def test_generated_unittest_job_has_structured_args(self):
        adapter = AUTO.resolve_test_adapter(
            r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\neewa-lifecycle-canary",
            "python -m unittest",
        )
        self.assertEqual(adapter["argv"], ["-m", "unittest"])
        self.assertEqual(adapter["cwd"], ".")
        self.assertEqual(adapter["id"], "lifecycle-canary-unittest")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = {
                "job_id": "JOB-IT",
                "parent_objective": "fixture",
                "workspace": r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\neewa-lifecycle-canary",
                "project_identity": {},
                "child_jobs": [],
                "_path": str(root / "JOB-IT.json"),
            }
            seen = {}

            def submit(**kwargs):
                seen.update(kwargs)
                return {"job_id": kwargs["job_id"], "state": "DISPATCHED"}

            AUTO._submit_independent_test(job, "python -m unittest", inbox_root=None, orch_submit=submit)
            self.assertEqual(seen["test_args"], ["-m", "unittest"])
            self.assertEqual(seen["test_cwd"], ".")
            self.assertTrue(seen["test_python"])
            saved = Path(job["_path"])
            self.assertEqual(saved.resolve().parent, root.resolve())
            self.assertTrue(saved.is_file())

    def test_absent_stdout_uses_independent_artifact(self):
        evidence = AUTO.parse_test_evidence("", {
            "independent_test": {
                "passed": True,
                "collected": 12,
                "exit_code": 0,
                "stdout_tail": "12 passed",
                "candidate_head": "abc",
            }
        })
        self.assertTrue(evidence["passed"])
        self.assertEqual(evidence["source"], "independent_test")
        self.assertEqual(evidence["collected"], 12)
        zero = AUTO.parse_test_evidence("", {"independent_test": {"passed": True, "collected": 0, "exit_code": 0}})
        self.assertFalse(zero["passed"])

    def test_sidecar_receipt_reaches_harvest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "done").mkdir()
            job_id = "JOB-IT1"
            (root / "done" / f"{job_id}.json").write_text(json.dumps({
                "job_id": job_id,
                "status": "COMPLETED",
                "artifact": f"{job_id}-independent-test.json",
            }), encoding="utf-8")
            (root / "done" / f"{job_id}-independent-test.json").write_text(json.dumps({
                "passed": True,
                "collected": 12,
                "exit_code": 0,
                "stdout_tail": "12 passed",
            }), encoding="utf-8")
            _folder, payload = ORCH.inspect_folders(job_id, root)
            self.assertEqual(payload["independent_test"]["collected"], 12)
            self.assertTrue(payload["test_results"]["passed"])

    def test_harvest_keeps_an_object_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "done").mkdir()
            (root / "records").mkdir()
            job_id = "JOB-RV1"
            (root / "records" / f"{job_id}.json").write_text(json.dumps({
                "job_id": job_id,
                "state": "DISPATCHED",
                "history": [],
            }), encoding="utf-8")
            (root / "done" / f"{job_id}.json").write_text(json.dumps({
                "job_id": job_id,
                "status": "COMPLETED",
                "review_decision": "OBJECT",
                "review_text": "Missing invalid-input evidence; DECISION: OBJECT",
                "review_task": "software_review",
                "model": "gpt-5.6-sol",
                "effort": "high",
            }), encoding="utf-8")
            record = ORCH.harvest(job_id, root)
            self.assertEqual(record["review_decision"], "OBJECT")
            self.assertEqual(record["model"], "gpt-5.6-sol")
            self.assertEqual(record["state"], "COMPLETED")
            self.assertIn("Missing invalid-input evidence", record["review_text"])
            record.pop("review_decision", None)
            record.pop("review_text", None)
            ORCH.save_record(record, root)
            again = ORCH.harvest(job_id, root)
            self.assertEqual(again["review_decision"], "OBJECT")
            self.assertEqual(again["state"], "COMPLETED")
            self.assertIn("Missing invalid-input evidence", again["review_text"])

    def test_object_review_fails_done_gate_and_mission_success(self):
        job = {
            "state": "VALIDATING",
            "approval_level": "A1",
            "requirements_version": "REQ-v1",
            "design_version": "DES-v1",
            "artifacts": ["x"],
            "validation": {
                "council": "CHECKLIST_ONLY",
                "tests": "PASS",
                "traceability": "PASS",
                "independent_rerun": "PASS",
                "review_decision": "OBJECT",
            },
        }
        failures = AUTO.evaluate_autonomy_done(job)
        self.assertTrue(any("did not approve" in item for item in failures))
        self.assertFalse(MISSION.job_meets_mission_success({
            "state": "OWNER_REVIEW",
            "validation": job["validation"],
        }))
        approved = dict(job)
        approved["state"] = "OWNER_REVIEW"
        approved["validation"] = dict(job["validation"])
        approved["validation"]["review_decision"] = "APPROVE"
        self.assertEqual(AUTO.evaluate_autonomy_done({**job, "validation": approved["validation"]}), [])
        self.assertTrue(MISSION.job_meets_mission_success(approved))

    def test_dispatched_consultation_is_not_consulted(self):
        def invoke(advisor, evidence):
            return {"status": "DISPATCHED", "response": {"job_id": "CONSULT-1", "decision": None, "approval": False}}

        receipt = MISSION.consult_advisors(
            {"hash": "abc", "repo": r"C:\Users\swap2\NEEWA-Personal\projects\ChakraOps"},
            invoke=True,
            invoke_fn=invoke,
            models=[{"id": "neewa-premium", "model": "gpt-5.6-sol", "provider": "openai", "status": "verified"}],
            providers=[{"id": "openai", "status": "active", "cost_class": "subscription"}],
        )
        self.assertEqual(receipt["consulted_count"], 0)

    def test_explicit_modify_existing_survives_sandbox_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = AUTO.create_parent_job(
                "Make canary.answer return 42",
                workspace=r"C:\Users\swap2\NEEWA-Personal\cursor-sandbox\neewa-lifecycle-canary",
                project_lifecycle="modify_existing",
                root=root,
            )
            self.assertEqual(job["project_lifecycle"], "modify_existing")
            AUTO.attach_project_identity(job)
            self.assertEqual(job["project_lifecycle"], "modify_existing")

    def test_charter_plan_has_more_than_the_first_two_stages(self):
        plan = MISSION.default_stage_plan("PRJ-CHAKRAOPS", "reconcile")
        self.assertGreater(len(plan), 2)
        self.assertEqual(plan[0]["id"], "orats_reconciliation")
        self.assertIn("no_signal_evidence", [stage["id"] for stage in plan])
        self.assertIn("traceability", [stage["id"] for stage in plan])

    def test_handoff_adopts_only_the_named_failed_mission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "autonomy"
            inbox = Path(tmp) / "inbox"
            root.mkdir()
            (inbox / "records").mkdir(parents=True)
            failed = {
                "mission_id": "MISSION-KEEP",
                "project_id": "PRJ-CHAKRAOPS",
                "state": "FAILED",
                "failure_reason": "MAX_REPAIR_CYCLES",
                "repair_cycles": 3,
                "auto_continue": True,
                "stage_plan": [{"id": "orats_reconciliation", "status": "in_progress", "objective": "orats"}],
                "history": [{"state": "FAILED", "at": "2026-10-08T17:17:04Z", "note": "MAX_REPAIR_CYCLES"}],
                "failure_history": [],
            }
            other = dict(failed)
            other["mission_id"] = "MISSION-OTHER"
            other["project_id"] = "PRJ-OTHER"
            (root / "MISSION-KEEP.json").write_text(json.dumps(failed), encoding="utf-8")
            (root / "MISSION-OTHER.json").write_text(json.dumps(other), encoding="utf-8")
            (inbox / "records" / "neewa-handoff-latest.json").write_text(json.dumps({
                "handoff_id": "handoff-1",
                "changed_condition": True,
                "adopt_mission_ids": ["MISSION-KEEP"],
            }), encoding="utf-8")
            adopted = MISSION.adopt_bridge_handoff(root, inbox)
            self.assertEqual([row["mission_id"] for row in adopted], ["MISSION-KEEP"])
            kept = json.loads((root / "MISSION-KEEP.json").read_text(encoding="utf-8"))
            untouched = json.loads((root / "MISSION-OTHER.json").read_text(encoding="utf-8"))
            self.assertEqual(kept["state"], "PLANNING")
            self.assertEqual(kept["terminal_result"], "FAILED")
            self.assertGreater(len(kept["stage_plan"]), 2)
            self.assertEqual(untouched["state"], "FAILED")
            again = MISSION.adopt_bridge_handoff(root, inbox)
            self.assertEqual(again, [])


class WindowsRunnerTests(unittest.TestCase):
    def _shell(self):
        if os.name != "nt":
            self.skipTest("Native Windows worker proof")
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            self.skipTest("PowerShell is required")
        return shell

    def _git(self, repo, *args):
        return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)

    def _repo(self, folder, mutate=False):
        repo = folder / "candidate with spaces"
        repo.mkdir()
        self._git(repo, "init")
        self._git(repo, "config", "user.name", "contract fixture")
        self._git(repo, "config", "user.email", "fixture@example.invalid")
        self._git(repo, "config", "core.autocrlf", "false")
        (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (repo / "value.txt").write_text("original\n", encoding="utf-8")
        action = "Path('value.txt').write_text('mutated')" if mutate else "self.assertEqual(42, 42)"
        (repo / "test_candidate.py").write_text(
            "import unittest\nfrom pathlib import Path\nclass Contract(unittest.TestCase):\n    def test_candidate(self):\n        " + action + "\n", encoding="utf-8")
        self._git(repo, "add", ".")
        self._git(repo, "commit", "-m", "candidate baseline")
        return repo

    def _powershell(self, folder, text):
        script = folder / "proof.ps1"
        script.write_text("$ErrorActionPreference = 'Stop'\n" + text, encoding="utf-8")
        ran = subprocess.run([self._shell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                             capture_output=True, text=True, timeout=90)
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        return ran.stdout

    def _receipt(self, folder, repo):
        out = folder / "bridge"
        out.mkdir()
        spec = folder / "job.json"
        spec.write_text(json.dumps({"job_id": "JOB-WINDOWS-CONTRACT", "repo": str(repo),
                                    "python": "python", "cwd": ".", "args": ["-m", "unittest"]}), encoding="utf-8")
        runner = WORKER / "Invoke-NeewaIndependentTest.ps1"
        self._powershell(folder, f"& '{runner}' -JobFile '{spec}' -OutDir '{out}'\n")
        return json.loads((out / "JOB-WINDOWS-CONTRACT-independent-test.json").read_text(encoding="utf-8-sig"))

    def test_git_identity_hashes_raw_staged_and_unstaged_diff(self):
        self._shell()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            repo = self._repo(folder)
            identity_file = folder / "identity.json"
            source = WORKER / "Invoke-NeewaIndependentTest.ps1"
            def identity():
                diagnostic = self._powershell(folder, f"$VerbosePreference = 'Continue'\n. '{source}'\nGet-NeewaRepoIdentity -Repo '{repo}' | ConvertTo-Json | Set-Content -LiteralPath '{identity_file}' -Encoding utf8\n")
                value = json.loads(identity_file.read_text(encoding="utf-8-sig"))
                self.assertTrue(value["head"], diagnostic)
                return value
            clean = identity()
            self.assertEqual(clean["diff_sha256"], hashlib.sha256(b"").hexdigest())
            (repo / "value.txt").write_text("staged\n", encoding="utf-8")
            self._git(repo, "add", "value.txt")
            (repo / "test_candidate.py").write_text((repo / "test_candidate.py").read_text() + "# unstaged\n", encoding="utf-8")
            dirty = identity()
            raw = self._git(repo, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--")
            self.assertEqual(dirty["diff_sha256"], hashlib.sha256(raw).hexdigest())
            (repo / "value.txt").write_bytes(b"non-UTF8 text: \x80\xff\n")
            raw = self._git(repo, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--")
            self.assertEqual(identity()["diff_sha256"], hashlib.sha256(raw).hexdigest())
            (repo / "untracked.txt").write_text("one", encoding="utf-8")
            first = identity()
            (repo / "untracked.txt").write_text("two", encoding="utf-8")
            second = identity()
            self.assertNotEqual(first["worktree_sha256"], second["worktree_sha256"])

    def test_test_transcript_is_readable_inside_unchanged_candidate(self):
        self._shell()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            repo = self._repo(folder)
            receipt = self._receipt(folder, repo)
            self.assertTrue(receipt["passed"], receipt)
            self.assertEqual(receipt["collected"], 1)
            self.assertTrue(receipt["candidate_stable"])
            transcript = Path(receipt["transcript"])
            self.assertTrue(transcript.resolve().is_relative_to(repo.resolve()),
                            f"transcript={transcript}; candidate={repo}")
            self.assertEqual(receipt["transcript_sha256"], hashlib.sha256(transcript.read_bytes()).hexdigest())
            self.assertEqual(self._git(repo, "status", "--porcelain"), b"")

    def test_passing_test_that_changes_candidate_is_rejected(self):
        self._shell()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            repo = self._repo(folder, mutate=True)
            receipt = self._receipt(folder, repo)
            self.assertFalse(receipt["passed"])
            self.assertFalse(receipt["candidate_stable"])
            self.assertEqual(receipt["failure_class"], "CANDIDATE_CHANGED")
            self.assertEqual(receipt["collected"], 1)

    def test_review_rechecks_transcript_after_model_returns(self):
        self._shell()
        for mutate in (False, True):
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                repo = self._repo(folder)
                receipt = self._receipt(folder, repo)
                scripts = folder / "worker"
                shutil.copytree(WORKER, scripts)
                (scripts / "NeewaPersonalWorkspace.ps1").write_text(
                    "function Resolve-ApprovedRepo { param($Requested) return $Requested }\n", encoding="utf-8")
                fake = folder / "mock-codex.ps1"
                fake.write_text("if ($args[0] -eq 'login') { 'Logged in using ChatGPT'; return }\n"
                    f"[System.IO.File]::WriteAllText('{folder / 'model-called.txt'}', 'called')\n"
                    "$i = [Array]::IndexOf($args, '-o')\n"
                    "[System.IO.File]::WriteAllText($args[$i + 1], 'DECISION: APPROVE')\n" +
                    (f"[System.IO.File]::AppendAllText('{receipt['transcript']}', 'changed during review')\n" if mutate else "") +
                    "$global:LASTEXITCODE = 0\n", encoding="utf-8")
                spec = folder / "review.json"
                spec.write_text(json.dumps({"job_id": "JOB-REVIEW", "repo": str(repo), "prompt": "review fixture",
                                            "test_receipt": receipt}), encoding="utf-8")
                result = folder / "review-result.json"
                diagnostic = self._powershell(folder,
                    f"$VerbosePreference = 'Continue'\nfunction Get-Command {{ [CmdletBinding()]param([string]$Name)\n"
                    f"if ($Name -eq 'codex') {{ return [pscustomobject]@{{ Source = '{fake}' }} }}\n"
                    "Microsoft.PowerShell.Core\\Get-Command $Name }\n" +
                    f"$job = Get-Content -Raw '{spec}' | ConvertFrom-Json\n"
                    f"& '{scripts / 'Invoke-NeewaCodexReview.ps1'}' -Job $job -JobsDir '{folder}' | ConvertTo-Json -Depth 10 | Set-Content '{result}' -Encoding utf8\n")
                reviewed = json.loads(result.read_text(encoding="utf-8-sig"))
                self.assertTrue((folder / "model-called.txt").is_file(), str(reviewed) + diagnostic)
                self.assertEqual(reviewed["status"], "FAILED" if mutate else "COMPLETED", reviewed)
                self.assertEqual(reviewed["review_decision"], None if mutate else "APPROVE")
                if mutate:
                    self.assertEqual(reviewed["failure_class"], "REVIEW_EVIDENCE_INVALID")
                    self.assertIn("during review", reviewed["reason"])

    def test_installed_script_parses_and_drains_both_streams(self):
        if os.name != "nt":
            self.skipTest("Windows runner proof")
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if shell is None:
            self.skipTest("PowerShell is required")
        script = WORKER / "Invoke-NeewaDrainedProcess.ps1"
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "drain.ps1"
            probe.write_text(
                "\n".join([
                    "$ErrorActionPreference = 'Stop'",
                    f". '{script}'",
                    "$psi = New-Object System.Diagnostics.ProcessStartInfo",
                    f"$psi.FileName = '{shell}'",
                    "$psi.Arguments = '-NoProfile -Command \"[Console]::Out.WriteLine((''x'' * 70000)); [Console]::Error.WriteLine((''y'' * 70000))\"'",
                    "$psi.UseShellExecute = $false",
                    "$psi.RedirectStandardOutput = $true",
                    "$psi.RedirectStandardError = $true",
                    "$psi.CreateNoWindow = $true",
                    "$result = Invoke-NeewaDrainedProcess -StartInfo $psi -TimeoutMs 20000",
                    "if ($result.TimedOut) { exit 2 }",
                    "if ($result.Stdout.Length -lt 60000) { exit 3 }",
                    "if ($result.Stderr.Length -lt 60000) { exit 4 }",
                    "$hang = New-Object System.Diagnostics.ProcessStartInfo",
                    f"$hang.FileName = '{shell}'",
                    "$hang.Arguments = '-NoProfile -Command \"Start-Sleep -Seconds 30\"'",
                    "$hang.UseShellExecute = $false",
                    "$hang.RedirectStandardOutput = $true",
                    "$hang.RedirectStandardError = $true",
                    "$hang.CreateNoWindow = $true",
                    "$timed = Invoke-NeewaDrainedProcess -StartInfo $hang -TimeoutMs 1500",
                    "if (-not $timed.TimedOut) { exit 5 }",
                    "",
                ]),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(probe)],
                capture_output=True,
                text=True,
                timeout=40,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()

