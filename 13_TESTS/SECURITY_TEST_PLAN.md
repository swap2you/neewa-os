# Security Test Plan

- Verify public inbound ports are minimized.
- Verify private Tailscale admin route.
- Verify SSH password login disabled.
- Verify sandbox deny-by-default egress.
- Verify secrets absent from Git.
- Verify scoped model keys.
- Verify observability redaction.
- Verify edge worker does not expose entire Windows host.
- Verify employer devices/accounts are not connected.
- Verify LOCKDOWN disables execution.
- Verify restore from known-good snapshot.
- Check current NemoClaw/Hermes security advisories before every platform upgrade.
