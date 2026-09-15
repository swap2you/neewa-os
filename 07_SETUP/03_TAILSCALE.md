# Step 3 — Tailscale

Purpose:
private connectivity between NEEWA-Core and approved owner/edge devices.

Actions:
- create tailnet;
- join NEEWA-Core;
- join ThinkPad as `neewa-edge-01`;
- use ACLs/tags;
- do not expose local development ports publicly.

Keep NEEWA's edge access scoped. Tailscale connectivity is not permission to control the entire Windows machine.
