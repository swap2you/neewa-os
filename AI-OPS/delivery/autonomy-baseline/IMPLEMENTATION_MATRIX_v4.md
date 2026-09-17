# Implementation matrix — autonomy v4 (additive)

Each P0 has an observable check. v3 REQ IDs remain normative.

| Pathway | P0 check | Evidence |
| --- | --- | --- |
| Intake | Conversation submit returns job_id | hermes stdout |
| Project routing | registry access_stage + canonical path | resolve_project() tests + live job workspace |
| Requirements | objective + stack, not status/changelog/Ganesh clone | requirements.json source_class + stack field |
| Architecture | compatible with inspected stack | design.stack / test_command |
| Review | deterministic_only labeled | council.json independence_class |
| Approval | A2/A3 blocked; job JSON untrusted | authorize tests |
| Lifecycle | valid transitions + unique IDs | unit tests |
| Dispatch | cursor_call child on approved path | child record selected_worker |
| Artifacts | paths exist under workspace | independent validator / artifact_paths |
| Per-REQ validation | ac/check/result | traceability.json rows |
| Correction | real fail → bounded retry → stop on stagnation | retry_history |
| Cost | reserve + tokens vs conservative USD | budget.invocations |
| Restart | active_child_id not duplicated | unit + live runner |
| Reporting | OWNER_REVIEW not DONE | parent state |
| Voice | PENDING_PHYSICAL | skill text |
| Onboarding | DISCOVERED cannot A1-write | Vāṇī/Bhāva BLOCKED test |
| Failed cases | denied repo, forged approval, missing tests | NEG tests |
