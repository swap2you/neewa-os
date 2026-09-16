# Step 16 — Private Windows Desktop Connectivity

Selected path: Hermes Desktop SSH connection over Tailscale. It adds no public or host listener and needs no dashboard password. Desktop manages the tunnel and remote backend; normal use does not require a terminal.

Verified server prerequisites: Hermes `serve` exists; gateway is persistent under user systemd; Tailscale is active; SSH password authentication is disabled; no Tailscale Serve or Funnel endpoint is active.

The one-time Windows package is under `16_WINDOWS_CLIENT/`.

Future direct path, if eliminating Desktop's internal SSH tunnel is useful: supervise `hermes serve` on loopback, configure reviewed Hermes authentication, expose only through tailnet-private Tailscale Serve HTTPS, and verify Funnel is off plus HTTP/WebSocket tests pass. Never bind Hermes to all interfaces or publish 9119/8642.
