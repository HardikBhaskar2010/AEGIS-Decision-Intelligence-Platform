# ARCHITECTURE.md — System Architecture

## 1. High-Level System Diagram

```mermaid
flowchart TB
    subgraph Client["Frontend — React/Vite PWA (Firebase Hosting)"]
        UI[Situation Room UI]
        Graph[React Flow — live agent graph]
        Map[MapLibre — situation map]
        Chat[NL query box]
    end

    subgraph Backend["FastAPI Backend — Cloud Run"]
        API[REST + WebSocket Gateway]
        Auth[Auth middleware]
    end

    subgraph Agents["ADK 2.0 Workflow Runtime — Agent Service (Cloud Run)"]
        Orch[Orchestrator Agent]
        Query[Query Agent]
        Corr[Correlation Agent]
        Fore[Forecast Agent]
        Narr[Narrative Agent]
    end

    subgraph Tools["MCP Tool Layer — Cloud API Registry"]
        MCPBQ[BigQuery MCP Connector]
        MCPMaps[Maps MCP Connector]
    end

    subgraph Data["Data Layer"]
        BQ[(BigQuery — analytics core)]
        FS[(Firestore — session/live state)]
        GCS[(Cloud Storage — seeded raw data)]
        VS[(Vector Search / RAG Engine — stretch)]
    end

    subgraph Models["Gemini Enterprise Agent Platform"]
        Flash[Gemini 3 Flash]
        Pro[Gemini 3.1 Pro]
    end

    Chat --> API
    API --> Auth --> Orch
    Orch --> Query --> MCPBQ --> BQ
    Orch --> Corr --> BQ
    Orch --> Fore --> BQ
    Orch --> Narr --> VS
    Query --> Flash
    Corr --> Flash
    Fore --> Flash
    Narr --> Pro
    Orch -. streamed events .-> API
    API -. Socket.IO .-> Graph
    API --> FS
    GCS --> BQ
    Corr --> Map
```

## 2. Component Breakdown

| Component | Responsibility |
|---|---|
| Situation Room UI | Primary screen: map + timeline + NL query box + Situation Brief panel |
| React Flow agent graph | Renders live node/edge state as ADK streams Workflow Runtime events over Socket.IO |
| FastAPI Gateway | Auth, request validation (Pydantic), REST endpoints, WebSocket bridge to agent events |
| Orchestrator Agent | Parses intent, decides which specialist agents to invoke, in what order (ADK Workflow graph) |
| Query Agent | Translates NL question → BigQuery SQL via MCP BigQuery connector, executes, returns rows |
| Correlation Agent | Runs statistical cross-domain correlation over returned data (e.g. complaint spike × weather event × outage report, same sector/time window) |
| Forecast Agent | Produces short-horizon risk trajectory + supports what-if re-runs with adjusted parameters |
| Narrative Agent | Synthesizes all agent outputs into an explainable Situation Brief with confidence score (Gemini 3.1 Pro, optionally RAG-grounded on policy docs) |

## 3. Authentication

MVP: single demo-account Firebase Auth (email/password or anonymous session) — enough to demonstrate a real auth boundary without burning hours on RBAC. Documented (not built): role-based access (citizen vs. official vs. admin) via Firebase custom claims + IAM-backed service-to-service auth between Cloud Run services.

## 4. Workflow Engine & Event System

- **ADK 2.0 Workflow Runtime** is the workflow engine — a graph-based execution engine (the same primitive used for retries, fan-out/fan-in, state) replaces any need for a bespoke workflow layer.
- Each node emits a structured event (`agent_start`, `tool_call`, `agent_result`) — the backend relays these over a WebSocket channel the frontend consumes to animate the React Flow graph in real time.
- **Stretch:** Pub/Sub + Eventarc for a scheduled re-ingestion trigger (Cloud Scheduler → Pub/Sub → Cloud Function → BigQuery load) — documented, not required for the live demo path.

## 5. Deployment Architecture

```mermaid
flowchart LR
    Dev[Local dev] -->|adk deploy / gcloud run deploy| CR1[Cloud Run: FastAPI backend]
    Dev -->|gcloud run deploy| CR2[Cloud Run: ADK agent service]
    Dev -->|firebase deploy| FH[Firebase Hosting: React PWA]
    CR1 <--> CR2
    CR1 --> BQ[(BigQuery)]
    CR1 --> FSDB[(Firestore)]
    SM[Secret Manager] -.-> CR1
    SM -.-> CR2
    CT[Cloud Trace / Logging] -.observability.- CR2
```

## 6. Monitoring & Security

| Concern | Approach |
|---|---|
| Observability | ADK 2.0's native OpenTelemetry hooks → Cloud Trace; structured logs → Cloud Logging |
| Secrets | Service account keys / API keys in Secret Manager, never in frontend bundle |
| Prompt injection | Model Armor-style input sanitization documented as a post-hackathon hardening step (see RISKS.md) |
| Least privilege | Cloud Run service accounts scoped to only BigQuery read + Firestore read/write, no broader project IAM |
| Data boundary | MCP BigQuery connector restricted to read-only, whitelisted dataset — agents cannot mutate source data |

## 7. Sequence Diagram — Query to Situation Brief

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI Gateway
    participant O as Orchestrator Agent
    participant Q as Query Agent
    participant C as Correlation Agent
    participant F as Forecast Agent
    participant N as Narrative Agent
    participant BQ as BigQuery (via MCP)

    U->>FE: "What's happening in Sector 7?"
    FE->>API: POST /query
    API->>O: dispatch(query)
    O->>Q: fetch relevant domain data
    Q->>BQ: NL→SQL (MCP tool call)
    BQ-->>Q: rows
    Q-->>O: structured data
    O->>C: correlate(data)
    C-->>O: correlation signals + severity
    O->>F: forecast(signals)
    F-->>O: risk trajectory
    O->>N: synthesize(data, correlation, forecast)
    N-->>O: Situation Brief + confidence score
    O-->>API: stream agent events + final brief
    API-->>FE: WebSocket events (live graph) + REST response (brief)
    FE-->>U: Animated agent graph + Situation Brief card
```

## 8. Entity Relationship Diagram (BigQuery core tables)

```mermaid
erDiagram
    SECTORS ||--o{ CITIZEN_FEEDBACK : reports
    SECTORS ||--o{ WEATHER_EVENTS : experiences
    SECTORS ||--o{ UTILITY_STATUS : has
    SECTORS ||--o{ TRANSIT_STATUS : has
    SECTORS ||--o{ SITUATION_BRIEFS : generates

    SECTORS {
      string sector_id PK
      string name
      float lat
      float lng
      int population
    }
    CITIZEN_FEEDBACK {
      string feedback_id PK
      string sector_id FK
      timestamp ts
      string category
      string sentiment
      string raw_text
    }
    WEATHER_EVENTS {
      string event_id PK
      string sector_id FK
      timestamp ts
      string event_type
      float severity
    }
    UTILITY_STATUS {
      string status_id PK
      string sector_id FK
      timestamp ts
      string utility_type
      string status
    }
    TRANSIT_STATUS {
      string status_id PK
      string sector_id FK
      timestamp ts
      string line_id
      string status
    }
    SITUATION_BRIEFS {
      string brief_id PK
      string sector_id FK
      timestamp ts
      float risk_score
      float confidence
      string recommendation
      string narrative
    }
```
