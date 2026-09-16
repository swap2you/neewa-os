# Step 18 — Local Model Fallback

Ollama 0.34.1 is enabled under systemd and bound to loopback only. Selected model: `qwen3:4b-instruct-2507-q4_K_M` (Apache-2.0, Q4_K_M, 2.5 GB artifact, tools advertised, 65,536 context, CPU-only).

Measured: direct cold exact-format response 18.0 seconds; generation 5.54 tokens/second; loaded footprint 12 GB; MemAvailable 2.4 GiB. An actual Hermes primary-failure test returned `FALLBACK VERIFIED` in 224 seconds. Eight GiB swap was added as OOM insurance and remained unused in the measured probe.

This is operational degraded service, not premium reasoning.

Rejected and removed: Qwen 3.5 4B (3.79 tokens/sec; 118 seconds for a tiny exact response) and Qwen 3.5 2B (7.76 tokens/sec but 231 seconds due 1,738 hidden reasoning tokens).

Rollback: remove the Hermes fallback; disable Ollama; remove the model; remove `/etc/systemd/system/ollama.service.d/neewa.conf`; for swap, run swapoff, restore the recorded `/etc/fstab.neewa-pre-swap-*`, then remove `/swapfile` only after verification.
