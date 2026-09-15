# Incident Runbook

Severity:
- P0: security compromise, uncontrolled spend, destructive action, core unavailable.
- P1: major project blocked or repeated incorrect autonomous behavior.
- P2: provider failure with fallback available.
- P3: minor workflow defect.

P0:
- automatic/owner LOCKDOWN;
- preserve evidence;
- rotate exposed secrets;
- restore known-good snapshot;
- independent review before RUN.

Every incident gets:
- timeline;
- trigger;
- blast radius;
- root cause;
- remediation;
- prevention test.
