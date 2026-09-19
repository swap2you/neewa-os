# Governed deploy sync

`deploy_sync.sh` is the host-side release executor for a validated immutable SHA.
It is intentionally not run from the Conversation sandbox.

Example administrator installation/execution after the file is present on the NEEWA host:

```bash
cd /opt/neewa/neewa-os
bash 12_SCRIPTS/deploy_sync.sh \
  --sha 1727ea62f2624643112798a7e55eeb13ee48227d \
  --release-root /opt/neewa/releases/neewa-os \
  --current-link /opt/neewa/neewa-os-current
```

The executor:

- fetches the exact SHA from the configured public repository;
- verifies the commit and clean staged tree;
- runs `neewa_ops validate` and the full unittest suite;
- refuses to overwrite a non-symlink current target;
- atomically switches the current symlink;
- optionally restarts one explicitly supplied service and rolls back on failed health;
- retains recent release directories.

It must be invoked by a reviewed host deployment service or administrator. The
Conversation sandbox cannot install or execute it against `/opt/neewa` because
that mount is read-only and does not expose host systemd.
