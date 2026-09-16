# NEEWA Windows Bootstrap

Run `Install-NEEWA.ps1` from PowerShell 7 (`pwsh`) or Windows PowerShell 5.1 on Swapnil's personal Windows 10/11 PC. Prefer `pwsh -File .\Install-NEEWA.ps1 -ConfirmPersonalDevice`. It confirms the trust boundary, installs/checks Tailscale, downloads and Authenticode-validates the official Nous Research Hermes Desktop installer, installs NEEWA visual assets, creates per-user startup, tests private SSH reachability, and writes exact connection steps.

No password, API key, SSH key, Tailscale auth key, token, or cookie is included.

Preferred connection: Hermes Desktop → Settings → Gateways → Add connection → SSH → `ubuntu@neewa-core-01:22`. Desktop manages the Tailscale-private tunnel; normal use does not require a terminal or a public endpoint.

Physical Windows validation remains: Tailscale identity approval, SSH host trust/key, microphone permission, Desktop connection test, acoustic wake phrase, and speaker playback.
