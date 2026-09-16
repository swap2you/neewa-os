# Cua Driver on neewa-edge-01

## Why `hermes computer-use install` failed

`hermes computer-use install` downloads GitHub `install.ps1` and invokes it
in memory. That script then `Invoke-RestMethod https://cua.ai/driver/_install-common.psm1`.
On this workstation `cua.ai` is NXDOMAIN (not TLS, not proxy). GitHub,
`raw.githubusercontent.com`, and `api.github.com` return HTTPS 200.

The official fix is to run `install.ps1` from disk next to
`_install-common.psm1` so the LocalDir import skips cua.ai. The release zip
is still `https://github.com/trycua/cua/releases/download/cua-driver-rs-v0.28.2/cua-driver-rs-0.28.2-windows-x86_64.zip`.

## Installed evidence

- Version: `cua-driver 0.28.2`
- Binary: `%LOCALAPPDATA%\Programs\Cua\cua-driver\bin\cua-driver.exe`
- Packages: `%USERPROFILE%\.cua-driver\packages\releases\0.28.2-x86_64-pc-windows-msvc\`
- install.ps1 SHA256: `3e770fa8c351b80db99ae6b080f696a22f844534498bf44d45816cbd05eb0c3f`
- Zip SHA256: `3c1fcf10ff9513b94e4af78ad6a216ab62aa95b2c9a3b70dfbdba9f04e021533`

## Commands actually used

```
cua-driver --version
cua-driver doctor --json
cua-driver status
cua-driver serve --permission-mode standard
cua-driver call <tool> '<json>'
cua-driver telemetry disable
cua-driver mcp-config --client cursor   # preview only; not merged
```

`mcp-config` exists. There is no separate `cua-driver mcp-config` installer
payload beyond printing client snippets.

## Permission boundary

The Calculator 6×7=42 test used **background** UIA clicks on the Calculator
window only, then closed that window. Settings (same ApplicationFrameHost)
was left untouched.

Bounded mode cannot isolate Calculator from Settings via `executable` because
both are UWP frames of `ApplicationFrameHost.exe`. The worker therefore does
not allow that executable. Enforced scope is the script allowlist plus
`%USERPROFILE%\NEEWA-Personal`.

## Uninstall

Official `uninstall.ps1` from the same GitHub release. NEEWA HKCU Run
entries: `Register-NeewaWindowsStartup.ps1 -Remove`.
