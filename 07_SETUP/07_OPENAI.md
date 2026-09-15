# Step 7 — OpenAI Platform

Purpose:
- GPT-5.6 Sol High for premium reasoning;
- GPT-5.6 Luna for low-cost workload;
- GPT-Live-1 for primary voice;
- Astra only for exceptional escalation.

Actions:
- create/confirm OpenAI Platform organization/project;
- configure billing;
- set a low starting budget/alert;
- create project-scoped API credential;
- store credential in secret store, never Git.

Initial API planning cap: $60/month.

Model aliases in LiteLLM should hide raw model IDs from project workflows so upgrades do not require rewriting every skill.
