# Project: AEGIS Decision Intelligence Platform

## Architecture
AEGIS is built using a microservice-inspired layout on Google Cloud Platform:
- **Frontend**: A React PWA using MapLibre GL for geographic visualization and React Flow for real-time multi-agent execution graphs.
- **Backend (FastAPI Gateway)**: Handles user requests, Firebase Auth token validation, session management in Firestore, and WebSockets to stream agent execution events to the frontend.
- **Agent Layer (ADK 2.0)**: Deployed on the Gemini Enterprise Agent Platform. An Orchestrator Agent manages the graph execution of four specialist agents (Query, Correlation, Forecast, Narrative).
- **Tool Layer**: Managed MCP BigQuery Connector provides read-only analytical access to BQ datasets.
- **Data Layer**: BigQuery stores the multi-domain historical and raw data, Firestore stores real-time states and session history, and Cloud Storage is the landing zone for seed data.

```
[User] <--> [React Frontend]
                 | (REST & WebSockets)
                 v
        [FastAPI Backend] <--> [Firestore]
                 |
                 v
      [ADK 2.0 Agent Service]
        |-- Orchestrator Agent
        |-- Query Agent <--> [MCP BigQuery Connector] <--> [BigQuery]
        |-- Correlation Agent <--> [BigQuery]
        |-- Forecast Agent <--> [BigQuery]
        `-- Narrative Agent (Gemini 3.1 Pro)
```

## Code Layout
- `backend/` — Backend services
  - `backend/gateway/` — FastAPI backend gateway (endpoints, auth, WebSockets)
  - `backend/agents/` — ADK 2.0 multi-agent implementation and workflows
  - `backend/tools/` — MCP Connector registrations and security policies
  - `backend/data/` — BigQuery schemas, ingestion scripts, Open-Meteo integration
- `frontend/` — React/Vite/TS PWA frontend
  - `frontend/src/components/` — React Flow graph, MapLibre map, Situation Brief, What-If slider
  - `frontend/src/store/` — Zustand global states
- `tests/` — Testing suites
  - `tests/e2e/` — E2E test suite (Tiers 1-4)
  - `tests/unit/` — Service unit tests

## Milestones
| # | Name | Scope | Dependencies | Status | Conversation ID |
|---|------|-------|--------------|--------|-----------------|
| 1 | M1: Data Layer & Seeding | BQ raw/core datasets, seeding pipelines, Open-Meteo blending, Gemini sentiment pass | None | IN_PROGRESS | 427c9f03-7bfd-478f-a48b-f9c4e2169fbb |
| 2 | M2: MCP BQ Connector | Read-only BigQuery MCP registration & programmatic blocker tests | M1 | PLANNED | TBD |
| 3 | M3: ADK Agent Workflow | 5 ADK agents, confidence score, narrative grounding, WebSocket emitters | M2 | PLANNED | TBD |
| 4 | M4: FastAPI Backend Gateway | REST and WebSocket endpoints, Firebase Auth middleware | M3 | PLANNED | TBD |
| 5 | M5: React Frontend UI | Situation Room desktop layout, MapLibre, React Flow, Dark Cyberpunk styling | M4 | PLANNED | TBD |
| 6 | M6: Least-Privilege GCP Infrastructure | GCP deployment (Cloud Run, Hosting, IAM, Secret Manager) & final E2E test verification | M5, M_E2E_3 | PLANNED | TBD |
| E2E | E2E Testing Track | Requirement-driven test suite (Tiers 1-4) publishing TEST_READY.md | None | IN_PROGRESS | e5390d24-428d-44a9-a5fd-67ee21d10042 |

## Interface Contracts
### FastAPI Gateway ↔ ADK Agent Service
- **Invoke Workflow**:
  - Request: `POST /api/v1/query` with body `{ session_id: STRING, question: STRING }`
  - Response: `{ brief_id: STRING, sector_id: STRING, risk_score: FLOAT, confidence: FLOAT, recommendation: STRING, narrative: STRING, sources: { sql: STRING, signals_used: ARRAY }, generated_at: TIMESTAMP }`
- **Invoke What-If**:
  - Request: `POST /api/v1/whatif` with body `{ brief_id: STRING, adjustment: { rainfall_intensity_pct: FLOAT } }`
  - Response: `{ brief_id: STRING, adjusted_risk_score: FLOAT, delta: FLOAT, narrative_delta: STRING }`
- **Agent Event Stream**:
  - WebSocket: `/ws/agent-events/{session_id}`
  - Payloads: `{ type: "agent_start" | "tool_call" | "agent_result" | "final_brief", agent: STRING, tool: STRING (optional), detail: STRING (optional), summary: STRING (optional), ts: TIMESTAMP }`
