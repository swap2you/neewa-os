# Step 14 — Council + Done Gate

Implement risk-based Council selection.

Test cases:
1. low-risk deterministic task -> no expensive Council;
2. medium-risk task -> one independent reviewer;
3. high-risk architecture decision -> full Core Council;
4. writer and reviewer disagree -> Chair records dissent;
5. failed acceptance -> automatic rework;
6. repeated failure -> owner escalation;
7. evidence missing -> DONE denied.

Acceptance:
NEEWA cannot mark a test job complete until the Done Gate passes.
