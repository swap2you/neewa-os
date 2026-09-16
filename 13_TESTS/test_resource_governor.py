import importlib.util,unittest,json,shutil,tempfile
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'12_SCRIPTS/resource_governor.py';S=importlib.util.spec_from_file_location('gov',P);gov=importlib.util.module_from_spec(S);S.loader.exec_module(gov)
class GovernorTests(unittest.TestCase):
 def test_offline_routes_local(self):self.assertEqual('neewa-local',gov.route(online=False)['model_id'])
 def test_local_privacy_routes_local(self):self.assertEqual('neewa-local',gov.route(privacy='local-only')['model_id'])
 def test_high_premium_routes_cloud(self):self.assertEqual('neewa-premium',gov.route(risk='high',quality='premium')['model_id'])
 def test_exceptional_blocks(self):self.assertEqual('BLOCKED',gov.route(quality='exceptional')['status'])
 def test_low_basic_prefers_free(self):self.assertEqual('neewa-local',gov.route()['model_id'])
 def test_validator_rejects_empty_approval_registry(self):
     validator_path=Path(__file__).resolve().parents[1]/"12_SCRIPTS/neewa_ops.py"
     spec=importlib.util.spec_from_file_location("validator",validator_path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
     with tempfile.TemporaryDirectory() as td:
         target=Path(td)/"repo"; shutil.copytree(mod.ROOT,target,ignore=shutil.ignore_patterns(".git","__pycache__"))
         data=json.loads((target/"11_CONFIG/approvals.json").read_text()); data["authorized"]=[]; (target/"11_CONFIG/approvals.json").write_text(json.dumps(data))
         result=mod.validate_repository(target,require_manifest=False); self.assertFalse(next(x for x in result["checks"] if x["name"]=="approvals:standing_authorization")["passed"])

 def test_validator_rejects_duplicate_worker_ids(self):
     validator_path=Path(__file__).resolve().parents[1]/"12_SCRIPTS/neewa_ops.py"
     spec=importlib.util.spec_from_file_location("validator2",validator_path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
     with tempfile.TemporaryDirectory() as td:
         target=Path(td)/"repo"; shutil.copytree(mod.ROOT,target,ignore=shutil.ignore_patterns(".git","__pycache__"))
         data=json.loads((target/"11_CONFIG/workers.json").read_text()); data["workers"][1]["id"]=data["workers"][0]["id"]; (target/"11_CONFIG/workers.json").write_text(json.dumps(data))
         result=mod.validate_repository(target,require_manifest=False); self.assertFalse(next(x for x in result["checks"] if x["name"]=="workers:unique_ids")["passed"])
if __name__=='__main__':unittest.main()
