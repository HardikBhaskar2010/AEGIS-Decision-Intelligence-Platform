# WORKFLOWS.md — User Flows & System Workflows

## Flow 1 — Ask a Question (primary demo flow)

```mermaid
sequenceDiagram
    actor U as City Ops Lead
    participant UI as Situation Room
    participant BE as FastAPI
    participant AG as ADK Agents
    participant BQ as BigQuery

    U->>UI: Types "What's happening in Sector 7?"
    UI->>BE: POST /api/v1/query
    BE->>AG: dispatch to Orchestrator
    AG->>BQ: Query Agent → MCP → SQL
    AG->>AG: Correlation Agent finds 3 signals
    AG->>AG: Forecast Agent projects risk
    AG->>AG: Narrative Agent synthesizes brief
    AG-->>BE: stream events + final brief
    BE-->>UI: WebSocket events (graph animates) + REST brief
    UI-->>U: Situation Brief card renders
```

## Flow 2 — What-If Simulation

```mermaid
sequenceDiagram
    actor U as City Ops Lead
    participant UI as What-If Panel
    participant BE as FastAPI
    participant F as Forecast Agent

    U->>UI: Drags "rainfall intensity +20%"
    UI->>BE: POST /api/v1/whatif
    BE->>F: re-run with adjusted param
    F-->>BE: adjusted risk score + narrative delta
    BE-->>UI: response (~2-3s)
    UI-->>U: Risk score + narrative update live
```

## Flow 3 — Scheduled Data Refresh (background system workflow)

```mermaid
flowchart LR
    CS[Cloud Scheduler — every 15 min] --> CF[Cloud Function: refresh job]
    CF --> GCS[(Cloud Storage landing)]
    GCS --> BQ1[(BigQuery raw)]
    BQ1 --> Clean[Scheduled cleaning query]
    Clean --> BQ2[(BigQuery core)]
    BQ2 --> Notify{New anomaly?}
    Notify -->|yes| PS[Pub/Sub: sector.alert] --> EV[Eventarc] --> FS[(Firestore: push to active sessions)]
    Notify -->|no| Idle[No-op]
```

## Flow 4 — Citizen Feedback Ingestion → Classification

```mermaid
sequenceDiagram
    participant Src as Seeded feedback source
    participant Ing as Ingestion job
    participant Gem as Gemini 3 Flash (batch classify)
    participant BQ as BigQuery core.citizen_feedback

    Src->>Ing: raw complaint text batch
    Ing->>Gem: classify(category, sentiment)
    Gem-->>Ing: labeled batch
    Ing->>BQ: insert labeled rows
```

## Demo Script (for the 3-minute submission video)

1. **(0:00–0:20)** Open Situation Room — map shows one amber sector. State the one-liner.
2. **(0:20–0:50)** Type the NL question → agent graph animates live → Situation Brief appears with confidence score.
3. **(0:50–1:20)** Expand generated SQL + signals — prove it's not hardcoded.
4. **(1:20–1:50)** Drag the what-if slider — risk score updates, narrative delta shown.
5. **(1:50–2:30)** Quick architecture flash (ARCHITECTURE.md diagram) — call out ADK 2.0, MCP, BigQuery, Gemini 3 by name.
6. **(2:30–3:00)** Close on impact statement — "built for cities in flood/monsoon-prone APAC regions where this decision currently takes a human 30+ minutes of cross-referencing dashboards."
