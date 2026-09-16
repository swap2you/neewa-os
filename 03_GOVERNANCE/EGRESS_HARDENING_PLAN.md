# Docker Egress Hardening Plan

Global `terminal.docker_network=false` is explicitly deferred because working tools need outbound access.

Worker classes:
- Offline: deterministic tests, parsing, local inference, secret scans, vendored builds.
- Allowlisted: packages, official docs, GitHub, approved provider APIs.
- Interactive browser: research and owner-approved sign-ins through Hermes browser/vault boundaries.

Target: run offline jobs with `--network none`; use pinned iron-proxy credential injection when supported API credentials exist; allowlist only required hosts; deny metadata/link-local/private/CGNAT upstreams; never forward cloud signing credentials; record each job's network class and destinations.

Current state: Hermes Docker tools use bridge networking, no provider API keys were found in its `.env`, and incomplete iron-proxy setup is disabled. Hardening is deferred, not marked complete.
