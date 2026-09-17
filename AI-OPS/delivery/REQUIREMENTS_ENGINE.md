# Requirements engine

Implemented in `12_SCRIPTS/neewa_autonomy.py` (`build_requirements`).

Each software job writes `requirements.json` with stable IDs (`REQ-001`…).
Fields kept separate:

- `original_objective`
- `clarifications`
- `implementation_decisions`
- `proposed_enhancements`
- `out_of_scope`

Traceability is `requirement → DES-v2 → status_app.py → test_status_app.py`
in `traceability.json`. A requirement without a result is not PASS.

The current software template is the project-status CLI used for the
acceptance scenario. Other domains use `11_CONFIG/domain_workflows.json`
for extra gates; they do not silently replace REQ IDs.
