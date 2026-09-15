# Step 2 — AWS Lightsail NEEWA-Core

## Starting specification
- Ubuntu 24.04 LTS
- 4 vCPU
- 16 GB RAM
- 320 GB SSD
- static IP if required by the final connectivity design

## Why not 32 GB initially?
Current general-purpose Lightsail:
- 16 GB / 4 vCPU / 320 GB: about $84/month
- 32 GB / 8 vCPU / 640 GB: about $164/month

NEEWA-Core is an orchestration server. 16 GB already matches NVIDIA's recommended NemoClaw/Hermes host profile.

Upgrade only when metrics show sustained memory/CPU pressure.

## Important
Lightsail general-purpose instances have no GPU VRAM.
GPU workloads use RunPod/on-demand worker infrastructure.

## Hardening
- SSH keys only;
- disable password SSH;
- automatic security updates;
- host firewall;
- private Tailscale access;
- keep agent dashboard/gateway off the public Internet;
- snapshot after clean hardening.
