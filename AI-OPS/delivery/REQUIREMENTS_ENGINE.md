# Requirements engine

Production: `build_requirements(objective)` derives REQ IDs from the owner's
text (product slug, clauses, implied CLI/read/print/test/security contracts).
Source class is `DERIVED_FROM_OBJECTIVE`.

The project-status JSON requirements live only in
`12_SCRIPTS/neewa_autonomy_fixture.py` (`source_class=FIXTURE`).

Traceability requires per-requirement evidence (implementation path, unittest
source, workspace scope). Missing tests are `NOT RUN` or `FAIL`, never silent PASS.
