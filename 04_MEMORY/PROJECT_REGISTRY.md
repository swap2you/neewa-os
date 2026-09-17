# Project Registry — Initial

Canonical machine index: `11_CONFIG/projects.json`.
Isolated agent context: `evidence/PROJECT_PORTFOLIO/<id>/` — one ID per session.

| Project | ID | Priority | Workspace tree | Purpose |
|---|---|---:|---|---|
| NEEWA OS | PRJ-NEEWA | P0 | `C:\Development\Workspace\NEEWA-OS` | governed chief-agent control plane |
| DAU Digital Media / Wani | PRJ-WANI | P1 | none inventoried | media production charter |
| Aarohan CareerOS | PRJ-AAROHAN | P1 | `C:\Development\Workspace\aarohan-careeros` | career/services pipeline |
| Revenue Research | PRJ-REVENUE | P1 | none inventoried | monetization research charter |
| Bhava | PRJ-BHAVA | P2 | none (charter only) | devotional product charter; not DevotionalRepo |
| ChakraOps | PRJ-CHAKRAOPS | P2 | `C:\Development\Workspace\ChakraOps` | trading research; no live capital |
| ChakraOps-dev | PRJ-CHAKRAOPS-DEV | P2 | `C:\Development\Workspace\ChakraOps-dev` | isolated non-git working copy |
| DevotionalRepo | PRJ-DEVOTIONAL | P2 | `C:\Development\Workspace\DevotionalRepo` | on-disk devotional/family workspace |
| KidsProjects | PRJ-KIDS | P2 | `C:\Development\Workspace\KidsProjects` | kids/education workspace |
| Manan | PRJ-MANAN | P2 | `C:\Development\Workspace\manan` | private Swadhyay workspace |
| SocialMediaManager | PRJ-SOCIAL | P2 | `C:\Development\Workspace\SocialMediaManager` | local social drafting |
| Zume | PRJ-ZUME | P1 | `C:\Development\Workspace\Zume` | local hiring CLI / study workspace |

Skipped (not projects): denied employer/fintech/trading trees and unclassified `Udemy-Yutube-repos`. See `11_CONFIG/projects.json` `skipped`.

Each inventoried project has `PROJECT.md` under `08_PROJECTS/` plus `evidence/PROJECT_PORTFOLIO/<id>/record.json` and `CONTEXT.md`.

## Connection honesty (2026-09-17)

`11_CONFIG/projects.json` is a **registry**, not model training. A name in that file does not mean NEEWA is trained on the project or that files are retrieved automatically.

| Project | Registry | Connected retrieval | Notes |
| --- | --- | --- | --- |
| NEEWA OS | yes | PARTIAL — repo files exist under `08_PROJECTS/NEEWA_OS` and Git | Voice may cite files only if the agent reads them this turn |
| Inventoried personal trees | yes | NOT auto-loaded | Use only `evidence/PROJECT_PORTFOLIO/<id>` in that session |
| Wani / Revenue / Bhava charters | yes (`status: defined`) | NOT CONNECTED as live memory | Do not invent project facts from the name alone |

Job state that is real lives under `04_MEMORY/jobs/` and `evidence/`. Session chat is not a durable project store.
