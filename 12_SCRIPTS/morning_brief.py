#!/usr/bin/env python3
"""Emit a deterministic current NEEWA morning brief."""
import json,subprocess
from pathlib import Path
ROOT=Path('/opt/neewa/neewa-os')
def cmd(a):p=subprocess.run(a,capture_output=True,text=True,timeout=60);return p.returncode,p.stdout.strip()
def main():
 _,branch=cmd(['git','-C',str(ROOT),'status','--short','--branch']);_,gateway=cmd(['systemctl','--user','is-active','hermes-gateway.service']);_,docker=cmd(['systemctl','is-active','docker.service']);_,ollama=cmd(['systemctl','is-active','ollama.service']);_,tail=cmd(['systemctl','is-active','tailscaled.service']);_,swap=cmd(['swapon','--show','--noheadings']);jobs=json.loads((ROOT/'11_CONFIG/automation.json').read_text())['jobs'];models=json.loads((ROOT/'11_CONFIG/models.json').read_text())['models'];print('NEEWA MORNING BRIEF');print(f'Repository: {branch}');print(f'Services: gateway={gateway}, docker={docker}, ollama={ollama}, tailscale={tail}');print(f'Local fallback: {next(m["model"] for m in models if m["location"]=="local")}');print(f'Swap: {"active" if swap else "inactive"}');print(f'Scheduled jobs: {len(jobs)}');print('Owner action: run the Windows bootstrap and complete private Desktop sign-in.');return 0 if all(x=='active' for x in [gateway,docker,ollama,tail]) else 1
if __name__=='__main__':raise SystemExit(main())
