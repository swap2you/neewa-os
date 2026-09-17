# Design council

Implemented as local review roles in `run_council`, not six paid model calls.

Roles: solution architect, implementation engineer, quality engineer,
security/privacy, UX/product, cost/operations.

One bounded round. Material findings revise DES-v1 to DES-v2.
The project-status design is challenged on malformed JSON (REQ-003).
That finding is written to `council.json` and must exist for council PASS.

Independence here is role checklists plus a real failing test later, not
repeated sampling of the same model. High-risk work can still add a
separate Cursor `--mode ask` review via `neewa_orchestrate.py`.
