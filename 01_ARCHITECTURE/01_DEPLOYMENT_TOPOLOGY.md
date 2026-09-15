# Deployment Topology

## NEEWA-CORE
AWS Lightsail Ubuntu 24.04 LTS.

Starting size:
- 4 vCPU
- 16 GB RAM
- 320 GB SSD

Reason:
NVIDIA recommends 4+ vCPU, 16 GB RAM, and 40 GB free disk for NemoClaw/Hermes headless use. This server runs the control plane, not heavyweight local inference.

## Important: RAM is not VRAM

Lightsail general-purpose instances do not provide NVIDIA GPU VRAM.

Moving from 16 GB to 32 GB Lightsail:
- 16 GB: about $84/month
- 32 GB: about $164/month

It improves CPU/RAM headroom, but does not make large GPU models possible.

Recommendation:
Start at 16 GB. Upgrade to 32 GB only if measured memory pressure justifies it.

## Storage

320 GB is enough for:
- runtime images;
- logs;
- databases;
- structured memory;
- configuration;
- temporary artifacts.

Do not use the control server as the media archive.

Large assets:
- project repositories: Git + local edge as appropriate;
- backups: encrypted object/off-machine storage;
- media: project storage/Drive/S3 as selected later;
- large GPU models: ephemeral GPU worker cache or dedicated storage.

## NEEWA-EDGE-01
Owner ThinkPad:
- existing local repos;
- local developer tools;
- coding subscriptions;
- local models;
- media tools.

Only approved project workspaces are exposed to NEEWA workers.
