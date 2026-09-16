# Repository Assessment

Assessment date: 2026-09-16
Scope: all 89 non-`.git` files present before bootstrap (72,530 bytes), plus `~/.hermes/SOUL.md` and live system state.

## Already implemented

- frozen architecture, topology, model-routing, voice, worker, and multi-agent design;
- Constitution, risk classification, Council, Governor, Done Gate, research, kill-switch, and company authority policies;
- memory, job, documentation, incident, backup, cost/token, and provider-failover standards;
- setup guides, account checklists, project definitions, templates, example configuration, readiness scripts, and test plans;
- active Git repository and private remote tracking;
- live Hermes runtime, gateway, Nous OAuth, Docker engine, Tailscale, built-in memory/state, delegation tool, cron engine, and skills.

## Incomplete before bootstrap

- no executable NEEWA setup wizard or bootstrap script (the repository had setup documents only);
- no canonical live non-secret registries; only examples and Markdown tables;
- no executable job lifecycle, Governor gate, budget gate, Done Gate, or automated test suite;
- NEEWA OS itself had no project folder/status/runbook/evidence structure;
- MANIFEST.md omitted itself and the three `AI-OPS/company` governance files;
- no LiteLLM, Langfuse, OpenHands, Codex, Claude Code, Gemini CLI, voice front end, RunPod worker, or edge worker installed/configured;
- no Hermes cron jobs configured;
- Hermes memory provider was active, but MEMORY.md and USER.md had not yet been created;
- current Hermes Docker sandbox allowed network access and the credential-injection egress proxy was incomplete;
- no NemoClaw/OpenShell installation was detected.

## Obsolete, duplicated, or conflicting

- no byte-identical duplicate files were found;
- `11_CONFIG/niva_policy.example.yaml` uses the old name `niva`; it remains an example and is superseded by canonical `runtime.json`;
- the weekend checklist assumes a fresh server, while the observed server already satisfies the target CPU/RAM/disk, Docker, Tailscale, Git, and Hermes prerequisites;
- the setup guide calls for NemoClaw/OpenShell, LiteLLM, and Langfuse, but none were implemented;
- the repository calls Markdown/YAML/Git the durable project truth; Hermes chat memory is supplementary, not a replacement.

## Governance hierarchy used

1. `AI-OPS/company/OWNER.md`
2. `AI-OPS/company/APPROVAL_MATRIX.md`
3. `AI-OPS/company/POLICIES.md`
4. Constitution and governance documents
5. Architecture/setup/reference documents

No substantial architectural replacement was made.
