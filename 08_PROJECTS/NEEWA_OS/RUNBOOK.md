# NEEWA OS Runbook

From the repository root:

1. `./12_SCRIPTS/bootstrap.sh`
2. `python3 12_SCRIPTS/neewa_ops.py validate`
3. `python3 -m unittest discover -s 13_TESTS -p 'test_*.py' -v`
4. Read `15_BOOTSTRAP/VALIDATION_REPORT.md` before enabling external integrations.

The scripts do not read or print secret values. Runtime configuration containing credentials remains under the protected Hermes or provider secret store.

Rollback:
- repository changes: `git revert <bootstrap-commit>` after review;
- Hermes config: restore the timestamped `~/.hermes/config.yaml.pre-neewa-bootstrap-*` backup and restart the relevant Hermes process;
- generated local evidence can be archived before removal.
