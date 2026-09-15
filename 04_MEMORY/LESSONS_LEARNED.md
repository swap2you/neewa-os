# Lessons Learned

## LL-001 — Do not equate more agents with more productivity
Permanent bot fleets create context/token overhead. Prefer one chief agent plus temporary workers.

## LL-002 — Deployment topology is a first-class architecture decision
For always-on assistants, evaluate local, managed cloud, self-hosted VPS, sandboxing, recovery, and edge-worker access before choosing a runtime.

## LL-003 — Quota exhaustion must never become total-system downtime
Every critical function requires an approved fallback or an explicit degraded mode.

## LL-004 — Independent validation matters
Implementation agents cannot be the only source of proof.

## LL-005 — Social-media claims are leads, not architecture evidence
Validate against official docs, source code, security advisories, current pricing, and real constraints.
