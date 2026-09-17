# Design council

Production `run_council(design, requirements)` inspects the actual design blob:

- acceptance vs requirement IDs
- test component vs quality requirements
- error-handling vs reliability requirements
- filesystem scope vs security requirements
- extra paid installs

Each finding carries `evidence`. Material findings revise DES-v1 to DES-v2.
Zero material findings is allowed when the checklist passes; disagreement is
not invented.

The hardcoded malformed-JSON finding is fixture-only.
