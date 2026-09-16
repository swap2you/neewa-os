# Project Registry — Initial

| Project | Priority | Purpose | First NEEWA role |
|---|---:|---|---|
| DAU Digital Media / Wani | P1 | Existing revenue/media production | automate production + QA + distribution prep |
| Aarohan CareerOS | P1 | career/services/revenue pipeline | complete outreach/services monetization |
| Bhava | P2 | devotional content/product platform | coding + content + audio + UAT orchestration |
| ChakraOps | P2 | trading research/decision-support system | engineering + validation; no autonomous live capital movement |
| NEEWA OS | P0 | orchestration platform | platform engineering |
| Revenue Research | P1 | identify practical monetization opportunities | premium research + opportunity scoring |

Each project gets its own `PROJECT.md`, `STATUS.md`, `DECISIONS.md`, and evidence directory when onboarded.

## Connection honesty (2026-09-16)

`11_CONFIG/projects.json` is a **registry**, not model training. A name in that file does not mean NEEWA is trained on the project or that files are retrieved automatically.

| Project | Registry | Connected retrieval | Notes |
| --- | --- | --- | --- |
| NEEWA OS | yes | PARTIAL — repo files exist under `08_PROJECTS/NEEWA_OS` and Git | Voice may cite files only if the agent reads them this turn |
| Wani / Aarohan / Bhava / ChakraOps / Revenue | yes (`status: defined`) | NOT CONNECTED as live memory | Do not invent project facts from the name alone |

Job state that is real lives under `04_MEMORY/jobs/` and `evidence/`. Session chat is not a durable project store.
