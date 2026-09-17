# Personal project access

Canonical registry: `11_CONFIG/projects.json`.
Read-only inventory: `workspace_inventory` A0.
Cursor writes: approved repo names in `cursor-call-policy.json` plus
`%USERPROFILE%\NEEWA-Personal\cursor-sandbox`.

## Stages

`DISCOVERED → INVENTORIED → ACCESS_APPROVED → CONNECTED → BUILD_VERIFIED → DELEGATION_VERIFIED`

A registry row is not proof the project is fully integrated.

| ID | Name | Stage | A1 development |
| --- | --- | --- | --- |
| PRJ-NEEWA | NEEWA OS | CONNECTED | yes |
| PRJ-AAROHAN | Aarohan CareerOS | ACCESS_APPROVED | yes |
| PRJ-CHAKRAOPS | ChakraOps | ACCESS_APPROVED | yes |
| PRJ-CHAKRAOPS-DEV | ChakraOps-dev | ACCESS_APPROVED | yes |
| PRJ-DEVOTIONAL | DevotionalRepo | ACCESS_APPROVED | yes |
| PRJ-KIDS | KidsProjects | ACCESS_APPROVED | yes |
| PRJ-MANAN | Manan | ACCESS_APPROVED | yes |
| PRJ-SOCIAL | SocialMediaManager | ACCESS_APPROVED | yes |
| PRJ-ZUME | Zume | ACCESS_APPROVED | yes |
| PRJ-WANI | Wani | DISCOVERED | no |
| PRJ-REVENUE | Revenue Research | DISCOVERED | no |
| PRJ-BHAVA | Bhava | DISCOVERED | no |

Science Quest is a **child folder** of KidsProjects (`C:\Development\Workspace\KidsProjects\ScienceQuest`).
It is inventoried by name only. It is not a separately connected production root.

Denied employer/fintech/trading trees remain skipped. Raw inventory JSON stays
under `%USERPROFILE%\NEEWA-Personal\inventory` unless specifically transferred.

Routine A1 coding, tests, and docs on an ACCESS_APPROVED or CONNECTED personal
root do not re-prompt. Publishing, production, spending, and destructive
actions remain A2/A3.
