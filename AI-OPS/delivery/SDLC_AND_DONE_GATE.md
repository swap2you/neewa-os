# SDLC and done gate

Production software path:

1. Versioned requirements derived from the objective
2. DES-v1 from those requirements
3. Council review of that design
4. Child Cursor job through the Windows worker
5. Automatic correction if the worker reports FAILED validation or tests fail
6. Independent traceability against expected paths and unittest evidence
7. Release candidate
8. OWNER_REVIEW (not public deploy, not DONE)

`--fixture demo-status` remains a local regression of the original canned CLI.

`evaluate_autonomy_done` requires requirements, approved design, artifacts,
tests PASS, traceability PASS, and council PASS. Unknown evidence is not PASS.
