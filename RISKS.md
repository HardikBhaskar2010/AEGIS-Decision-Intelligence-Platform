# RISKS.md — Risk Analysis & Mitigation

## Part 16 — Risk Matrix

| Risk | Category | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| Agent pipeline too slow for a live demo (judges watching a spinner) | Technical | Med | High | Cap Flash-model calls to short, narrow prompts; parallelize independent agent steps via Workflow Runtime fan-out; pre-warm Cloud Run instance before the demo (min-instances=1) |
| Narrative Agent hallucinates a correlation not actually in the data | AI hallucination | Med | High | Constrain Narrative Agent's prompt to only reference IDs/values present in upstream structured output (see AI.md); show generated SQL + signal IDs in-UI so any fabrication is visibly checkable |
| Confidence score becomes "vibes-based" (model just says a number) | AI hallucination | High if unaddressed | Med | Compute confidence **deterministically** from signal count / recency / statistical strength, not from an LLM self-rating (see AI.md) |
| Seeded data reads as fake/toy to judges | Credibility | Med | Med | Ground weather data in a real free-tier API where feasible; keep synthetic data internally consistent (same sector IDs, plausible timestamps) rather than random |
| Privacy — citizen feedback text resembling real complaints | Privacy | Low (synthetic data) | Med | Explicitly label all citizen feedback as synthetic in the repo README; document DLP-API redaction as the required step before any real-data integration |
| Bias in classification (e.g. sentiment model skewing by phrasing/dialect) | Bias | Med | Med | Document as a known limitation; recommend periodic classification audits + human-in-the-loop review before production use |
| Scalability — BigQuery cost/latency at real city scale | Scalability | Low (irrelevant at hackathon scale) | Med | Partition/cluster tables by `sector_id`/date in the production design; documented in DATA.md roadmap, not a 24h concern |
| Cost overrun from Gemini 3.1 Pro calls | Cost | Low | Low | Reserved for exactly one call per query (Narrative Agent only); Flash used everywhere else |
| MCP connector misconfigured, giving write access | Security | Low | High | Explicitly scope the BigQuery MCP connector to read-only, single dataset, verified before demo |
| Team time risk — stretch features (RAG, AlloyDB, Memory Bank) eat into Must-Have time | Execution | High | Med | Strict MoSCoW enforcement (PRD.md) — stretch items are cut first, not last, if behind schedule |
| Single point of failure — one Cloud Run instance, one demo path | Technical | Med | Med | Rehearse the exact demo query in advance; have a cached/recorded fallback response if live call fails during judging |

## Explainable AI — Design Commitment

Every risk score and recommendation must be traceable to specific rows/signals a judge (or a real city official) could independently verify — this is treated as a non-negotiable product requirement, not a nice-to-have, precisely because "explainable decisions" is an explicit ask in the original brief and a common failure point for GenAI hackathon submissions (see PRD.md 1.2).

## What We Are Explicitly NOT Solving in 24h (and say so, out loud, in the pitch)

- Real government data-sharing agreements / compliance review
- Multi-tenant security model
- Model drift monitoring / periodic re-evaluation cadence
- Full bias audit of the classification pipeline

Naming these explicitly in the pitch reads as engineering maturity, not as a weakness — judges consistently reward teams who show they know where their own edges are.
