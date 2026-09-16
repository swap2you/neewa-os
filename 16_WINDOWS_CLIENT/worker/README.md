# NEEWA Windows worker (P1)

Outbound / polling only. No public listener. No unrestricted shell.
Employer files are out of scope.

Allowlist (v1):

- `capability_inventory.ps1` — discovery only
- `run_personal_artifact.ps1` — writes one file under `%USERPROFILE%\NEEWA-Personal\jobs\`

Cursor remains the Git writer. NEEWA may request these scripts; it does not push.
