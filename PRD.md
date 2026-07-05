# PRD.md — AEGIS: Decision Intelligence Platform
### Product Requirements Document
**Hackathon:** Google Cloud Gen AI Academy APAC — Cohort 2 Capstone Hackathon
**Team Name:** DecisionForge AI
**Members:** Lead Dev - Hardik Bhaskar. Design - Snehal Prince.
**Theme:** Unified Data Analytics & Intelligence (BigQuery + ADK + agentic data agents)
**Problem Statement:** AI for Better Living and Smarter Communities — Create a data intelligence tool people would actually use, and show how acceleration helps them make a faster or better decision.
**Build window:** 24 hours
---

## 0. One-liner

> **AEGIS turns scattered city/community data into a natural-language decision copilot** — ask it a question, it correlates transit, weather, utilities, health, and citizen-feedback data live in BigQuery, and hands back an explainable "Situation Brief" with a risk score, a recommendation, and a what-if simulator.

---

## Part 1 — Understanding the Real Ask

### 1.1 What are the judges actually asking for?

Strip the buzzwords and the brief (and the Academy's own framing — *"remove the friction of manually writing SQL and building static dashboards, shift to natural-language data discovery and real-time agent-driven insights"*) reduces to one sentence:

> **"Show us an agent that reasons over real data and produces a decision, not just a chart."**

Everything else — 12 data domains, digital twins, knowledge graphs — is *scope bait*. Judges from a data-analytics-themed Google Cloud cohort are grading on: does it touch BigQuery meaningfully, is there a real agent (not a prompt-wrapper), and does the output change what a human would do next.

### 1.2 What would an average submission look like?

| Trait | Why it's average |
|---|---|
| A Gemini chatbot bolted onto a dashboard | No agentic reasoning — just Q&A over a chart |
| One data source (e.g. just a CSV of complaints) | Doesn't demonstrate cross-domain correlation, the core "intelligence" claim |
| Single LLM call per query | No planning, no tool use, no multi-step reasoning — judges can tell instantly |
| A dashboard that looks like Power BI | Doesn't feel AI-native; looks like BI-with-a-chat-tab |
| No mention of *why* the model recommends something | Fails the "Explainable AI" ask outright |

### 1.3 What makes it outstanding?

1. **Visible agentic reasoning** — the judges should *see* the multi-agent graph fire, not just get a final answer (React Flow live agent visualization is a deliberate scoring lever here).
2. **Real BigQuery-native NL-to-insight**, not a static pre-baked query.
3. **Cross-domain correlation that a human wouldn't spot fast** — e.g. flooding + power outage + complaint spike in one sector = an emerging crisis, computed, not scripted.
4. **A decision, with a confidence score and an explanation**, not a chart.
5. **A what-if slider** — this single interaction usually separates top-3 finishes from the rest, because it's the only feature that visibly demonstrates "intelligence" over "retrieval."
6. **Uses the Academy's own new toys correctly** — ADK 2.0 Workflow Runtime, managed MCP servers, Gemini 3 family — signals the team didn't just skim last year's docs.

---

## Part 2 — Competitive Landscape & Gaps

| Platform | Strength | Where it falls short for this brief |
|---|---|---|
| Palantir Foundry | Best-in-class ontology + cross-domain fusion | Closed, enterprise-only, no consumer-grade conversational layer, impossible to replicate meaningfully in 24h |
| Microsoft Fabric | Unified data lake + BI | Still fundamentally dashboard-first, not decision-first |
| Databricks | Strong ML/analytics pipeline | No consumer-facing decision narrative, needs data scientists in the loop |
| Tableau AI / Power BI Copilot | NL-to-chart is mature | Stops at the chart — no recommendation, no simulation, no agentic tool use |
| Google Looker | Native BigQuery semantic layer | Strong at metrics, weak at cross-domain "what does this mean" narrative |
| ArcGIS | Best spatial engine | No generative reasoning layer, expensive/closed licensing |
| Splunk | Great anomaly detection on logs | Not built for civic/community multi-domain data, not conversational |
| Notion AI / Glean | Good for internal knowledge retrieval | Pure RAG-over-docs, no numeric/statistical reasoning over live data |
| Perplexity | Best consumer-facing cited-answer UX | No structured data / BigQuery grounding, no decision engine |

**The gap every one of these leaves open:** nobody combines *(a)* a conversational, agentic front door, *(b)* live cross-domain statistical correlation, and *(c)* an explainable, simulate-able recommendation, in one lightweight package. That gap is exactly AEGIS's wedge — and it's a wedge a team can occupy in 24 hours because it's about **orchestration and narrative**, not about building yet another BI engine from scratch.

---

## Part 4 — Ten Ideas, Ranked

Scored 1–10. **Hackathon Score** weights: visible agentic reasoning, GCP-native depth, demo punch, feasibility in 24h. **Business Potential** is directional, not load-bearing for hackathon scoring.

| # | Idea | Domains Used | Difficulty | Hackathon Score | Business Potential |
|---|---|---|---|---|---|
| 1 | **AEGIS** — Community/City decision-intelligence copilot with cross-domain correlation + what-if sim | Transit, weather, utilities, citizen feedback, disaster | Med | **9.4** | High (smart-city SaaS) |
| 2 | Personal Finance Decision Copilot (spend + macro data → life decisions) | Personal finance, economic indicators | Low | 7.8 | High (consumer fintech) |
| 3 | Hospital Capacity & Patient-Flow Intelligence Agent | Healthcare, staffing, weather (flu/heat correlation) | High | 8.2 | High (health-tech, but data access is a 24h blocker) |
| 4 | Energy Grid Load Forecasting + Outage Risk Agent | Energy, weather, infrastructure | Med | 7.6 | High (utilities) |
| 5 | Campus/University Operations Copilot (facilities + feedback + events) | Education, community programs, feedback | Low | 6.9 | Medium |
| 6 | Disaster Response Coordination Agent (multi-agency) | Disaster data, transportation, comms | High | 8.0 | Medium (gov sales cycle is long) |
| 7 | Small-Business Local Market Intelligence Agent | Social platforms, retail, community | Low | 6.5 | Medium |
| 8 | Public Transit Optimization Copilot | Transportation only | Low | 6.2 | Medium |
| 9 | Citizen Feedback Triage & Routing Agent (single domain) | Citizen feedback only | Low | 5.8 | Low (too narrow, feels like a ticketing tool) |
| 10 | Environmental/Air-Quality Early-Warning Agent | Environment, weather | Low | 6.4 | Medium |

---

## Part 5 — Chosen Idea & Why

**#1, AEGIS**, wins on every axis that matters for *this specific* hackathon:

- It naturally spans the brief's full data-source list (transit, weather, utilities, citizen feedback, disaster, community programs) **without needing real access to any of them** — synthetic-but-realistic seed data in BigQuery is fully legitimate for a 24h demo and judges expect it.
- It maps cleanly onto **all three Academy tracks at once**: BigQuery NL agents (Track 1), multimodal multi-source reasoning (Track 2), and ADK + MCP + AlloyDB-style orchestration (Track 3) — a cross-track submission reads as more technically ambitious without actually costing more build time, because it's the same core loop reused three ways.
- The "cross-domain correlation → explainable decision → what-if simulation" loop is a **three-act demo** (ask → see the agents reason → move the slider) that judges can grasp in under 90 seconds, which is what a 3-minute submission video needs.
- It avoids #3's and #6's fatal 24h flaw: **no real regulated data access is required to build a convincing MVP.**

Compared to #2 (finance) and #7 (retail), AEGIS demonstrates *civic/community impact* — an explicit judging criterion in APAC-region GenAI hackathons ("how does this benefit users and communities in the region") — which single-consumer ideas structurally cannot match.

---

## Goals & Non-Goals (24h MVP)

**Goals**
- Natural-language question → BigQuery-grounded, multi-agent-reasoned answer
- Visible live agent graph (React Flow) while the query executes
- One convincing cross-domain correlation, computed from real (seeded) BigQuery data
- One explainable Situation Brief with confidence score + recommended action
- One working what-if slider that re-runs the forecast agent

**Non-Goals (explicitly out of scope for 24h)**
- Real integrations with actual city/government APIs
- Auth/multi-tenant user management beyond a single demo login
- Mobile app / native clients
- Production-grade data governance, PII redaction pipelines (flagged in RISKS.md, not built)
- Digital twin / 3D visualization

---

## Personas & User Stories

| Persona | Story |
|---|---|
| **City Operations Lead** ("Priya") | "I want to ask 'what's happening in Sector 7 right now' and get a plain-English brief with a confidence score, not a dashboard I have to interpret myself." |
| **Community Program Manager** ("Arjun") | "I want to know *why* the model thinks a crisis is emerging, so I can defend the decision to my director." |
| **Judge / Evaluator** | "I want to see, within 60 seconds, that this isn't a chatbot wrapper — that there's real multi-agent tool use over real data." |

---

## Feature Prioritization (MoSCoW)

| Priority | Features |
|---|---|
| **Must Have** | NL query box; ADK orchestrator + 3 specialist agents; BigQuery grounding; live agent-graph visualization; one Situation Brief with confidence score; basic map + timeline view |
| **Should Have** | What-if simulator slider; citizen-feedback sentiment clustering; anomaly badge on the map |
| **Nice to Have** | Voice input (Gemini Live API); Memory Bank cross-session recall; RAG over policy PDFs |
| **Future** | Real data source integrations; multi-tenant auth; digital twin view; mobile app |

---

## Success Metrics (for the demo, not production KPIs)

- Time from question → first agent-graph node firing: **< 2s**
- Time from question → full Situation Brief: **< 12s**
- At least **1 genuine cross-domain correlation** surfaced live, not hardcoded
- Judges can articulate, unprompted, "this is doing more than one model call" — the qualitative bar that matters most
