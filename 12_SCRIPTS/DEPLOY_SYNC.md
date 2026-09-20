# Governed deploy sync

`deploy_sync.sh` is the host-side release executor for a validated immutable SHA.
It targets **user-scoped systemd** (`systemctl --user`) and is intentionally not
run from the Conversation sandbox or from Windows.

Install or migrate the user unit before the first governed deploy:

```bash
# Prefer the stable current symlink; the installer also accepts a legacy
# /opt/neewa/neewa-os tree or a SHA/checksum-named checkout as NEEWA_OS_ROOT.
NEEWA_OS_ROOT=/opt/neewa/neewa-os-current \
  bash 12_SCRIPTS/install_neewa_autonomy_runner.sh
```

The installer copies the unit to `~/.config/systemd/user/neewa-autonomy-runner.service`
(or `NEEWA_USER_UNIT_DIR`), rewrites legacy/checksum-named ExecStart paths onto
`/opt/neewa/neewa-os-current`, creates that symlink when a writable checkout exists,
then `daemon-reload`, `enable --now`, and restarts an existing unit.

Example administrator execution after the file is present on the NEEWA host:

```bash
cd /opt/neewa/neewa-os-current
bash 12_SCRIPTS/deploy_sync.sh \
  --sha 1727ea62f2624643112798a7e55eeb13ee48227d \
  --service neewa-autonomy-runner.service \
  --release-root /opt/neewa/releases/neewa-os \
  --current-link /opt/neewa/neewa-os-current
```

The executor:

- requires `systemctl --user`, `XDG_RUNTIME_DIR`, and linger enabled for the deploying user;
- verifies the installed unit under `~/.config/systemd/user/` (or `NEEWA_USER_UNIT_DIR`);
- checks unit ownership/permissions plus ExecStart/WorkingDirectory against the current symlink;
- fetches the exact SHA from the configured public repository;
- verifies the commit and clean staged tree;
- runs `neewa_ops validate` and the full unittest suite;
- refuses to overwrite a non-symlink current target;
- atomically switches the current symlink;
- reloads, enables, and restarts the explicitly supplied user service and rolls back on failed health/heartbeat;
- writes a deployment receipt and retains recent release directories.

It must be invoked by a reviewed host deployment service or administrator. The
Conversation sandbox cannot install or execute it against `/opt/neewa` because
that mount is read-only and does not expose host systemd.
