# Original User Request

## Initial Request — 2026-07-05T17:24:28+05:30

AEGIS is a decision-intelligence copilot for city operations, disaster responders, and utility managers. It turns scattered city/community data into a natural-language situation brief via a 5-agent pipeline orchestrated by ADK 2.0.

Working directory: c:\Users\sneha\Music\AEGIS Decision Intelligence Platform
Integrity mode: development

---

## Requirements

### R1. Data Layer & Seed Data Ingestion
- Create BigQuery datasets (`raw` and `core`) and Firestore collections.
- Define `core` tables partitioned by `ts` and clustered by `sector_id` matching exactly:
  - `core.sectors` (sector_id STRING, name STRING, lat FLOAT64, lng FLOAT64, population INT64)
  - `core.citizen_feedback` (feedback_id STRING, sector_id STRING, ts TIMESTAMP, category STRING, sentiment STRING, raw_text STRING)
  - `core.weather_events` (event_id STRING, sector_id STRING, ts TIMESTAMP, event_type STRING, severity FLOAT64)
  - `core.utility_status` (status_id STRING, sector_id STRING, ts TIMESTAMP, utility_type STRING, status STRING)
  - `core.transit_status` (status_id STRING, sector_id STRING, ts TIMESTAMP, line_id STRING, status STRING)
  - `core.situation_briefs` (brief_id STRING, sector_id STRING, ts TIMESTAMP, risk_score FLOAT64, confidence FLOAT64, recommendation STRING, narrative STRING)
- Seed synthetic data for sectors, transit, utility, and citizen feedback. Citizen feedback raw text should be LLM-generated and labeled as synthetic.
- Blend weather events with a real free-tier API pull (Open-Meteo) and seeded anomaly events.
- Ingestion pipeline: seed scripts → GCS landing → load raw → clean/enrich (run Gemini classification for sentiment/category at ingestion time) → summary rollup table.
- At least one sector must contain a multi-domain anomaly (e.g. heavy rain + utility outage + citizen complaints) for demo.

### R2. MCP Tool Layer
- Register a BigQuery MCP connector scoped as read-only on the `core` dataset.
- Programmatically verify that mutating queries (INSERT/DELETE) issued through the connector are blocked and rejected.

### R3. ADK Agents & Multi-Agent Workflow
- Build 5 distinct agents orchestrated by ADK 2.0 Workflow Runtime:
  1. **Orchestrator Agent** (Gemini 3 Flash): Routes/delegates using ADK Task API, aggregates results.
  2. **Query Agent** (Gemini 3 Flash): Translates NL query to SQL via MCP BigQuery connector, executes, returns rows.
  3. **Correlation Agent** (Gemini 3 Flash): Analyzes data to find cross-domain anomalies, computes statistical rolling z-score.
  4. **Forecast Agent** (Gemini 3 Flash): Time-series projection of risk score, handles parameterized what-if runs.
  5. **Narrative Agent** (Gemini 3.1 Pro): Synthesizes upstream outputs into a Situation Brief with confidence score and recommended action.
- Data Flow: `Query --data--> Correlation --signals--> Forecast --trajectory--> Narrative`, and `Query --data--> Narrative`.
- **Confidence Score Formula**: Deterministically computed in code (not LLM-rated) using:
  $$\text{Confidence} = w_1 \cdot \text{signal\_count} + w_2 \cdot \text{recency\_score} + w_3 \cdot \text{correlation\_strength}$$
  *Note: Pick concrete weights (e.g. 40%, 30%, 30%) and normalize the output to a 0–100 score.*
- **Narrative Grounding Constraint**: Post-validate that all IDs/values referenced in the narrative actually exist in upstream payloads; reject and retry on mismatch.
- **WebSocket Event Emitter**: Agents must emit events (`agent_start`, `tool_call`, `agent_result`, `final_brief`) during execution.

### R4. FastAPI Backend Gateway
- Implement REST endpoints matching API.md exactly:
  - `POST /api/v1/query`: Input `{session_id, question}`, triggers ADK workflow, returns full Situation Brief.
  - `GET /api/v1/briefs/{sector_id}`: Fetch latest brief.
  - `GET /api/v1/sectors`: List sectors with coordinates and risk-level status.
  - `POST /api/v1/whatif`: Input `{brief_id, adjustment: {rainfall_intensity_pct}}`, re-runs ONLY Forecast Agent, returns updated risk and narrative delta in <3s.
  - `GET /api/v1/history/{session_id}`: Returns prior briefs/queries.
  - `WS /ws/agent-events/{session_id}`: WebSocket endpoint to stream agent events.
  - `GET /healthz`: Health check.
- Auth: Firebase Auth ID token verification via `Authorization: Bearer <token>` in middleware.

### R5. Interactive React Frontend UI
- Desktop Situation Room layout (Map on left, Copilot Console on right, Timeline at bottom).
- **MapLibre GL Map**: Plots sectors color-coded by risk level (Low: `#3DD6A3`, Med: `#F0B429`, High: `#F0453A`).
- **React Flow Agent Graph**: Visualizes live agent execution in real-time by mapping WebSocket events to node state transitions (`idle` → `active` → `done`).
- **Situation Brief Card**: Displays risk score, confidence score, narrative, recommended action, expandable panels for the generated SQL and raw signals used, and the what-if parameter slider.
- Styling: Cyberpunk dark command center base theme (`--bg-base: #0B0E14`, `--bg-panel: #12161F`).

### R6. GCP Deployment & Least-Privilege IAM Infrastructure
- Enable required APIs (BigQuery, Cloud Run, Firestore, Cloud Storage, Secret Manager, Cloud Build, Firebase Hosting, Gemini Enterprise Agent Platform / Agent Engine APIs).
- Create two distinct least-privilege service accounts:
  1. **FastAPI backend service account**: Permitted only to read/write Firestore, read Secret Manager, and invoke the ADK Agent Service. No broader project IAM.
  2. **ADK Agent service account**: Scoped to BigQuery **read-only** on the AEGIS dataset only, Vertex AI / Agent Platform model access, and Secret Manager access. No broader project IAM.
- Deploy the backend as two separate Cloud Run services (one for FastAPI gateway, one for ADK agent service).
- Set `min-instances=1` on the ADK agent Cloud Run service to eliminate demo cold-start latency.
- Store sensitive API keys, service credentials, and secrets in GCP Secret Manager, not in code or environment variables.
- Deploy the React PWA frontend to Firebase Hosting.

---

## Acceptance Criteria

### Technical & Agent Verification
- [ ] Asking a natural-language query triggers the 5-agent pipeline and returns a Situation Brief in <12 seconds.
- [ ] React Flow agent graph animates node-by-node from the WebSocket events.
- [ ] Time from submitting a question → first agent-graph node firing: < 2s.
- [ ] What-if slider re-runs Forecast Agent only, returning updated risk score and narrative delta in <3 seconds.
- [ ] The MCP BigQuery tool verifies read-only access: queries like `INSERT`/`DELETE` are rejected.
- [ ] Confidence score is calculated via deterministic code logic; no LLM self-estimation is used.
- [ ] Narrative agent output is programmatically verified to only cite IDs present in the upstream agent payloads.
- [ ] Pre-warm agent Cloud Run service instance (`min-instances=1`) is active and verified.
- [ ] At least 1 genuine cross-domain correlation (e.g. citizen feedback complaints spike + weather event + utility outage in the same sector/window) is computed live from seeded BigQuery data, not hardcoded.
- [ ] All citizen feedback data is labeled as synthetic in the UI and codebase.

---

## Out of Scope (Cut / Documented Not Built)
- **RAG Grounding**: Cut for MVP stability.
- **Sentiment Clustering & Anomaly Badges on Map**: Cut for MVP speed.
- **Naming Protocol**: Refer to the platform as the **"Gemini Enterprise Agent Platform"** (never "Vertex AI") in code comments, READMEs, and UI copy.
- **Working Directory**: Confirming `c:\Users\sneha\Music\AEGIS Decision Intelligence Platform` is the target repository workspace (corresponds to active workspace `HardikBhaskar2010/AEGIS-Decision-Intelligence-Platform`).
