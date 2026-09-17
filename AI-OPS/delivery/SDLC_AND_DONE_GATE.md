# SDLC and done gate

Software workflow (local controller):

1. Versioned requirements
2. DES-v1
3. Council → DES-v2
4. Broken implementation that fails the malformed-JSON test
5. Repair
6. Regression tests
7. Traceability
8. `RELEASE_CANDIDATE.md`
9. `OWNER_REVIEW` (not public deploy, not DONE)

`evaluate_autonomy_done` requires requirements, approved design, artifacts,
tests PASS, traceability PASS, and council PASS. A2/A3 still need owner
approval. Unknown evidence is not converted to PASS.

Child coding still goes through the Windows inbox `cursor_call` validator:
missing expected files are FAILED.
