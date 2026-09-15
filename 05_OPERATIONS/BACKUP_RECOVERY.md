# Backup and Recovery

## What must be recoverable
- NEEWA constitution;
- structured memory;
- project registry;
- decisions;
- skills;
- budget config;
- model routing;
- Council/Done-Gate config;
- infrastructure-as-code/config;
- job/evidence records.

## Backups
- private Git for configuration/docs;
- encrypted off-host backup for state requiring persistence;
- server snapshots before upgrades;
- local/offline copy of recovery codes.

## Recovery acceptance
A clean replacement server must be able to:
1. install runtime;
2. restore configuration/memory;
3. reconnect providers with freshly supplied secrets;
4. reproduce current project status;
5. resume without relying on old chat UI history.
