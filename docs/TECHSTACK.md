# TECHSTACK.md — Technology Decisions & Tradeoffs

> ⚠️ **Currency note (read this first):** As of Google Cloud NEXT '26, **"Vertex AI" no longer exists as a product name.** It was folded into the **Gemini Enterprise Agent Platform** (Model Garden, training, Agent Engine/Deployments, Agent Studio, RAG Engine, Vector Search, Search — all live under this one umbrella now; console redirects `Vertex AI` searches automatically). APIs and endpoints (`aiplatform.googleapis.com`) are unchanged, so existing tutorials/code still work — but say "Agent Platform" in your pitch, not "Vertex AI," or it reads as stale. This doc uses current names throughout.

---

## Frontend (Locked by Brief)

| Tech | Role | Notes |
|---|---|---|
| React 18 + Vite + TypeScript | App shell | Fast HMR, matches 24h velocity need |
| TailwindCSS + shadcn/ui + Radix UI | Design system | Premium feel without hand-rolled components |
| React Router | Routing | Situation Room / Agent Console / History |
| TanStack Query | Server-state cache | Wraps FastAPI + Socket.IO fallbacks |
| Zustand | Client/UI state | Lighter than Redux for a 24h build |
| Framer Motion + GSAP + Lenis | Motion & smooth-scroll | "Linear/Arc" feel per Part 10 |
| Recharts | Trend/forecast charts | Fast to wire, good defaults |
| React Hook Form + Zod | Forms + validation | What-if simulator inputs |
| **React Flow** | **Live agent-graph visualization** | The single highest-leverage UI element for judge impact — makes the multi-agent system *visible* |
| MapLibre GL | Situation map | Open-source, no Google Maps billing setup needed under time pressure |
| Socket.IO Client | Live agent-step streaming | Streams ADK Workflow Runtime events to the UI as they fire |
| PWA | Installable shell | Low cost, nice-to-have polish point |

No changes recommended here — the locked stack is genuinely good for this build and doesn't need re-litigating.

---

## Backend — Comparative Analysis

| Criterion | **FastAPI (Python)** | NestJS (TS) | Go Fiber | Rust Axum |
|---|---|---|---|---|
| Native ADK / Gemini SDK support | ✅ First-class, ADK is Python-native at core | ✅ ADK has a TS SDK (newer, less mature) | ⚠️ ADK Go exists (GA June 2026) but ecosystem younger | ❌ No official ADK/Google GenAI SDK |
| RAG / LangGraph / data-science interop | ✅ pandas, numpy, BigQuery client, all first-class | ⚠️ Possible but bridges back to Python for real analytics | ⚠️ Same issue, worse tooling | ❌ Poor fit |
| Async I/O for streaming agent steps | ✅ native `async def`, SSE/WebSockets easy | ✅ good | ✅ excellent (goroutines) | ✅ excellent |
| Raw throughput / latency | Good, not best | Good | Excellent | Best-in-class |
| Hackathon build speed (team, 24h) | **Fastest** — least boilerplate, most Stack Overflow / Gemini-assisted coverage | Medium — more scaffolding | Medium-slow — less AI-tooling maturity | Slowest — borrow-checker tax under time pressure |
| Deployment to Cloud Run | ✅ trivial | ✅ trivial | ✅ trivial | ✅ trivial |
| Maintainability at scale | Good with type hints + Pydantic | Excellent (DI, modules) | Good | Excellent |

**Decision: FastAPI.** For a data-analytics/agentic hackathon, the deciding factor isn't raw throughput — it's that **the entire AI stack (ADK, BigQuery client libraries, pandas-based enrichment, RAG Engine SDK) is Python-first**, and every hour spent bridging Go/Rust to Python for the actual "intelligence" work is an hour not spent on the demo. NestJS is the credible runner-up if this were a 2-week enterprise build with a team; it loses here purely on hackathon-speed grounds.

---

## Database — Comparative Analysis

| Option | Best for | Verdict for this build |
|---|---|---|
| **BigQuery** | Analytical queries over large multi-domain datasets, NL-to-SQL agents | **Core of the build.** This *is* the hackathon's named theme (Unified Data Analytics). All seeded domain data lives here; the NL agent queries it directly. |
| **Firestore** | Real-time operational state, low-latency reads | **Used for** live session state, chat history, agent-run status pushed to the frontend — its realtime listeners pair naturally with Socket.IO/UI state |
| PostgreSQL (vanilla) | General relational OLTP | Not needed — Firestore covers OLTP-lite needs with less setup ceremony |
| AlloyDB | Postgres-compatible, AI-optimized (native vector support, ADK's own preferred memory store) | **Stretch/Should-Have.** Ideal for agent memory + audit trail per Track 3 framing, but adds a Cloud SQL-adjacent provisioning step that isn't worth the risk in a 24h team run — documented, not built |
| Redis | Caching, pub/sub | Not needed at this scale; Firestore realtime covers the use case |
| Pinecone | Managed vector DB | Skipped — introduces an external vendor + API key dependency judges don't reward, when RAG Engine/Vector Search (Google-native) does the same job |
| Vertex/Agent Platform Vector Search | Managed, GCP-native vector search | **Stretch** — used only if RAG-over-policy-PDFs (Nice-to-Have) gets built; otherwise out of MVP scope |

**Decision: BigQuery (core) + Firestore (operational).** Everything else is a documented stretch goal, not a dependency for the demo to work.

---

## AI Stack — Comparative Analysis

| Option | Role considered | Verdict |
|---|---|---|
| **Gemini 3 Flash** | Primary reasoning model for fast agent steps (classification, correlation scoring, tool-call planning) | ✅ Chosen as default model — best latency/cost/reasoning balance for a live, multi-step demo |
| **Gemini 3.1 Pro** | Deep synthesis (final Situation Brief narrative, 1M-token context if RAG grows) | ✅ Chosen for the *final* narrative-generation step only, to keep per-query latency low elsewhere |
| **Google ADK 2.0** | Multi-agent orchestration | ✅ **Chosen as the orchestration backbone.** ADK 2.0's Workflow Runtime (graph-based execution: routing, fan-out/fan-in, retries) is a direct, native fit for "Orchestrator → 3 specialist agents → synthesis" and streams events the frontend can visualize live via React Flow |
| LangGraph | Alternative orchestrator | Strong option, but ADK is Google's own current-generation tool and demonstrates "used the sponsor's newest stack correctly" — a real, if soft, judging signal on a Google-run hackathon |
| CrewAI | Alternative orchestrator | Faster to prototype role-based crews, but weaker on structured graph execution / observability than ADK 2.0's Workflow Runtime; less GCP-native |
| **MCP (Model Context Protocol)** | Tool access layer | ✅ **Used via Google's managed MCP registry (Cloud API Registry)** — a BigQuery MCP connector gives agents governed, standardized data access instead of hand-rolled API glue. This is a brand-new (2026) capability; using it correctly is a differentiation point |
| **RAG (RAG Engine / Vector Search)** | Grounding over unstructured policy/report text | Should-Have — grounds the narrative agent in a handful of seeded "emergency response protocol" documents |
| Agentic AI / Multi-Agent Systems | Overall paradigm | ✅ Chosen over single-agent — see AI.md Part 7 for the full single-vs-multi-agent decision matrix |

**Final AI stack:** ADK 2.0 (Workflow Runtime) orchestrating 4 agents (Ingestion/Query, Correlation, Forecast, Narrative), Gemini 3 Flash for per-agent steps, Gemini 3.1 Pro for final synthesis, MCP-based BigQuery tool access, RAG Engine as a stretch grounding layer.

---

## Google Cloud Service Map (Part 3)

| Service | Where it's used |
|---|---|
| **BigQuery** | Core data warehouse for all seeded multi-domain datasets; NL-to-SQL query target |
| **Gemini Enterprise Agent Platform** (Model Garden + Agent Studio + Deployments) | Hosts Gemini models, deploys the ADK agent to a managed runtime |
| **Cloud Run** | Hosts the FastAPI backend + the deployed ADK agent service |
| **Firebase Hosting** | Serves the React/Vite PWA frontend |
| **Firestore** | Live session/operational state |
| **Cloud Storage** | Landing zone for seeded raw CSV/JSON domain data before BigQuery load |
| **Cloud Scheduler** | Triggers periodic (simulated) ingestion refresh |
| **Pub/Sub + Eventarc** | *Stretch* — event-driven re-ingestion trigger, documented not required for MVP |
| **Secret Manager** | API keys / service account credentials |
| **Cloud API Registry (managed MCP)** | Exposes BigQuery (and optionally Maps) as MCP tools for the agents |
| **RAG Engine / Vector Search** | *Stretch* — grounding for the Narrative agent over policy documents |
| **Cloud Trace / Cloud Logging** | Observability for ADK agent runs (native OpenTelemetry hooks) |

---

## Final Stack Summary

| Layer | Choice |
|---|---|
| Frontend | React + Vite + TS + Tailwind + shadcn/ui + React Flow + MapLibre + Socket.IO (as locked) |
| Backend | **FastAPI (Python 3.12)** |
| Primary data store | **BigQuery** |
| Operational store | **Firestore** |
| Orchestration | **Google ADK 2.0 (Workflow Runtime)** |
| Models | **Gemini 3 Flash** (agent steps) + **Gemini 3.1 Pro** (final synthesis) |
| Tool access | **MCP via Cloud API Registry** (BigQuery connector) |
| Grounding (stretch) | **RAG Engine / Vector Search** |
| Deployment | **Cloud Run** (backend/agent) + **Firebase Hosting** (frontend) |
