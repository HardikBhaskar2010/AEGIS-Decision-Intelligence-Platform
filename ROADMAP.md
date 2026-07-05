# ROADMAP.md — Hackathon Plan & Future Roadmap

## Part 13 — Minimum Lovable Product by Time Budget

| Time budget | Scope |
|---|---|
| **24h (your budget, team)** | NL query → 4-agent ADK pipeline → BigQuery-grounded Situation Brief with confidence score → live React Flow agent graph → basic map + timeline → what-if slider. RAG, AlloyDB, Memory Bank, real integrations: **cut**. |
| 36h | 24h scope + RAG-grounded Narrative Agent (policy doc citations) + citizen-feedback clustering + polished motion/theming pass |
| 48h (team) | 36h scope + AlloyDB-backed agent memory/audit trail + role-based auth (citizen/official/admin) + Pub/Sub-driven live re-ingestion + a second seeded city for a "compare cities" view |

## 24-Hour Hour-by-Hour Plan (team)

| Hours | Work |
|---|---|
| 0–2 | GCP project setup, BigQuery datasets + schema, seed data generation script (use Gemini to help generate realistic synthetic rows fast) |
| 2–4 | Load seeded data into BigQuery; write + test the classification batch job (feedback → category/sentiment) |
| 4–8 | Build the 4 ADK agents (Query, Correlation, Forecast, Narrative) + Orchestrator workflow graph; get one hardcoded question working end-to-end in the terminal (`adk run`) before touching the UI |
| 8–10 | Wire MCP BigQuery connector properly (replace any direct client-library shortcut used in step 4–8) |
| 10–13 | FastAPI gateway: REST endpoints + WebSocket event relay; deploy early to Cloud Run to catch deployment issues while there's still slack time |
| 13–17 | Frontend: Situation Room shell, map, NL query box, Situation Brief card — get the *unstyled* end-to-end flow working first |
| 17–20 | React Flow live agent graph wired to the WebSocket stream — this is the highest-priority polish item, budget real time for it |
| 20–22 | What-if slider + styling pass (theme tokens from DESIGN.md), motion polish (Framer Motion/GSAP) |
| 22–23 | Record the 3-minute demo video per the script in WORKFLOWS.md; rehearse the live path at least twice |
| 23–24 | README, architecture diagram export, repo cleanup, submission form |

**Golden rule for a team 24h build:** get the ugly, unstyled, fully-wired version working end-to-end by hour 13. Everything after that is polish, and polish is the first thing to cut if you're behind — a working ugly demo beats a beautiful broken one, every time.

## Part 14 — Future Startup Potential

| Stage | Shape |
|---|---|
| **SaaS** | Multi-tenant AEGIS for mid-size city ops teams; per-seat + per-query pricing; plug-and-play data connectors for common municipal systems |
| **Enterprise Platform** | Utilities/transit authorities license the correlation + forecast engine standalone, integrated into existing SCADA/GIS systems via MCP connectors |
| **Smart City Platform** | Full digital-twin layer, cross-agency data-sharing agreements, real-time Pub/Sub ingestion replacing batch loads, AlloyDB-backed long-term agent memory across years of city history |
| **Government AI Platform** | Formal procurement track — compliance (data residency, audit logging via Cloud Trace), Model Armor-hardened input sanitization, human-in-the-loop approval gates before any recommendation reaches an actual dispatch system |

## Post-Hackathon Technical Debt (tracked, not hidden)

- Replace synthetic data with governed real feeds (see DATA.md)
- Add role-based auth (see ARCHITECTURE.md §3)
- Add AlloyDB-backed agent memory + audit trail (Track 3 depth)
- Formal bias/hallucination evaluation harness for the Narrative Agent
- Cost monitoring dashboard (Gemini 3.1 Pro usage is the main line item to watch)

## Why This Wins (Part 5 recap, judge-facing framing)

AEGIS is the rare hackathon idea that is simultaneously **the safest to demo** (synthetic data, no fragile third-party integrations) and **the most technically ambitious-looking** (visible multi-agent graph, MCP-governed tool use, cross-domain statistical correlation, explainable confidence scoring) — because the ambition lives in the *orchestration and reasoning layer*, which is exactly what a 24-hour team build can actually deliver well, rather than in data-integration breadth, which it can't.
