# Token Governor

Before every model job:
1. classify risk;
2. classify complexity;
3. estimate context size;
4. choose cheapest eligible tier;
5. check project/monthly budget;
6. set max output/retries;
7. attach project/job tags.

During job:
- monitor tokens/cost/latency;
- stop runaway loops;
- use cached/retrieved context instead of full-history replay;
- prefer tools/deterministic computation over LLM inference where appropriate.

After job:
- record actual cost;
- record outcome;
- update model-performance score.

## Retry policy
Normal maximum: 2.
Provider transport/rate-limit failover may retry according to configured gateway policy, but logical failure does not receive unlimited retries.
