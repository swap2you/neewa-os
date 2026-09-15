# Governor / Watchdog

The Governor is outside NEEWA's normal reasoning loop.

## Monitors
- API spend;
- token rate;
- concurrency;
- retry count;
- job duration;
- storage growth;
- network destinations;
- tool errors;
- unexpected privilege requests;
- repeated identical actions;
- model/provider failure;
- Council disagreement;
- acceptance-gate failures.

## Global modes
### RUN
Normal governed operation.

### PAUSE
No new jobs start. Current safe jobs checkpoint and stop.

### LOCKDOWN
- revoke/disable NEEWA worker execution;
- disable virtual model keys where supported;
- block sandbox egress except recovery;
- stop ephemeral workers;
- preserve logs/evidence;
- notify owner.

NEEWA cannot override LOCKDOWN through prompting.

## Automatic lockdown triggers
Configure conservatively:
- detected credential leakage;
- unexpected outbound destination;
- uncontrolled cost spike;
- repeated privilege escalation;
- destructive action outside policy;
- integrity failure in core configuration.
