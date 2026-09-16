# Deferred NemoClaw / OpenShell Migration

Owner explicitly deferred installation tonight.

Potential benefits: policy-enforced network/credential boundaries, OpenShell credential handles, managed snapshots and lifecycle evidence.

Risks: second runtime plus k3s/OpenShell complexity, roughly 2.4 GB compressed image and runtime overhead, migration interruption/duplication, and a new onboarding trust boundary.

Future gate: preserve current evidence; re-check NVIDIA docs/installer; create `neewa-core` separately with Hermes Provider/Nous OAuth, loopback interfaces, no messaging, and reviewed restricted policy; validate provider, policy, network, snapshots, jobs and rollback; migrate only after independent review and an owner-approved maintenance window.

No NemoClaw, OpenShell, or k3s component was installed tonight.
