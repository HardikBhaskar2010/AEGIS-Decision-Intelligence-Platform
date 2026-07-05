# E2E Test Infrastructure & Architecture Design (TEST_INFRA.md)

## 1. Executive Summary
This document outlines the End-to-End (E2E) testing infrastructure and architecture for the **AEGIS Decision Intelligence Platform**, which is deployed on the **Gemini Enterprise Agent Platform**.
The E2E test suite validates core capabilities across the entire system topology—spanning natural language queries, real-time WebSocket agent execution streams, What-If simulation parameters, sector mapping APIs, and persistent session history—under mock/offline conditions.

---

## 2. Test Runner & Libraries
The testing suite relies on standard Python testing frameworks configured to handle asynchronous operations and WebSocket networking:
- **Core Test Runner**: `pytest`
- **Asynchronous Test Support**: `pytest-asyncio` for async FastAPI endpoints and WebSocket event streams.
- **REST client**: `httpx` (async) for making HTTP requests to the FastAPI gateway.
- **WebSocket client**: `websockets` (or FastAPI's built-in TestClient websocket support) for event-stream verification.
- **Mocking and Spies**: `pytest-mock` for testing isolation where necessary.

---

## 3. Directory Layout & Organization
All E2E testing resources are organized under the `tests/e2e/` folder to maintain clean boundaries:
```
tests/e2e/
├── conftest.py            # Shared fixtures (http client, WS client, db setup, JWT generator)
├── pytest.ini             # Pytest config (asyncio mode, markers)
├── requirements-test.txt  # Test dependencies
├── mock_server/           # Local simulated environment for offline development/CI
│   ├── app.py             # Simulated FastAPI backend and ADK workflows
│   └── datasets/          # Simulated JSON datasets (weather, utility, transit, feedback)
├── tier_1_feature/        # Tier 1: Happy-path feature coverage (>=25 tests)
├── tier_2_boundary/       # Tier 2: Boundary & Corner Cases (>=25 tests)
├── tier_3_cross/          # Tier 3: Cross-Feature State Combinations (>=5 tests)
├── tier_4_scenarios/      # Tier 4: Real-world Civic Disaster Scenarios (>=5 tests)
└── utils/                 # Shared helper functions (Auth helper, DB assertions, custom schemas)
```

---

## 4. Mocking & Offline Execution Strategy
To guarantee deterministic execution in CI/CD without model invocation costs or database credentials:
- **Agent Orchestrator**: Mock ADK 2.0 Agent execution and stream WebSocket event sequences (`agent_start`, `tool_call`, `agent_result`, `final_brief`) matching input keywords.
- **BigQuery / MCP**: Local SQLite database mimicking BigQuery table schemas (`CITIZEN_FEEDBACK`, `WEATHER_EVENTS`, `UTILITY_STATUS`, `TRANSIT_STATUS`).
- **Firestore**: Use the official Google Cloud Firestore Emulator or a local file-based mock cache to store session state and query logs.
- **Firebase Auth**: Bypass JWT validation in the `TESTING` environment using mock JWT tokens signed with a local test key.

---

## 5. Multi-Tier Test Suite Definition
We target **5 core features**:
1. **NL Query Engine** (`POST /api/v1/query`)
2. **WebSocket Live Event Stream** (`WS /ws/agent-events/{session_id}`)
3. **What-If Simulation** (`POST /api/v1/whatif`)
4. **Sector Status & Map API** (`GET /api/v1/sectors` and `GET /api/v1/briefs/{sector_id}`)
5. **Session History** (`GET /api/v1/history/{session_id}`)

### Test Case Targets & Verification Details
- **Tier 1 (Feature Coverage)**: 5 features * 5 tests/feature = 25 tests total.
  * *NL Query Engine*: Validates query parser, response payload schema, database query mapping, confidence score, and sources structure.
  * *WebSocket Live Event Stream*: Validates WS connection, state transitions (`agent_start` -> `tool_call` -> `agent_result` -> `final_brief`), session filtering, payload validation, and client disconnection handling.
  * *What-If Simulation*: Validates simulation calculation, risk score delta computation, response structure, narrative delta text generation, and range limits.
  * *Sector Status & Map API*: Validates sector coordinates, sector list payload, brief details mapping, risk level colors, and missing sector error handling.
  * *Session History*: Validates saving brief history, retrieving briefs list, order of entries, payload mapping, and empty history scenario.

- **Tier 2 (Boundary & Corner Cases)**: 5 features * 5 tests/feature = 25 tests total.
  * *NL Query Engine*: Empty/whitespace queries, SQL injection inputs, extremely long queries, unknown sectors, and model failure simulation.
  * *WebSocket Live Event Stream*: Invalid session IDs, concurrent connections to the same session, connection dropout recovery, rapid repeated connections, and high-frequency message streams.
  * *What-If Simulation*: Negative rainfall adjustments, extreme values (e.g., +1000%), missing fields in the payload, non-existent brief IDs, and invalid input types.
  * *Sector Status & Map API*: Non-existent sector requests, invalid coordinates format, empty database states, sectors with zero population, and race conditions on sector briefs.
  * *Session History*: Invalid session ID structure, duplicate session storage, history size limits (overflow), fetching deleted session, and concurrent history writes.

- **Tier 3 (Cross-Feature Combinations)**: 5 tests asserting WebSocket/REST synchronicity, history update persistence, session isolation, and database mutations.
  * *Test 1 (REST-WebSocket Sync)*: Assert that calling `POST /api/v1/query` triggers the appropriate sequence of events on the corresponding `WS /ws/agent-events/{session_id}` connection.
  * *Test 2 (History Mutation Persistence)*: Assert that queries run via `/api/v1/query` immediately populate `GET /api/v1/history/{session_id}`.
  * *Test 3 (What-If Mutation Linkage)*: Assert that running a What-If simulation updates the sector's cached brief and is reflected in subsequent map brief lookups.
  * *Test 4 (Session Isolation)*: Ensure data and event streams for `session_A` are completely isolated from `session_B`.
  * *Test 5 (Mock DB Update Propagation)*: Dynamically insert new simulated weather events into the SQLite mock DB and verify that a subsequent NL query correctly registers and analyzes the new data.

- **Tier 4 (Real-world Application Scenarios)**: 5 comprehensive scenarios:
  1. *Multi-domain cascading failure*: Heavy rainfall + electrical substation failure in Sector 7 leads to a major transit delay and a spike in citizen complaints.
  2. *Active disaster simulation & What-If risk escalation*: A localized flood warning is raised; a What-If rainfall increase triggers a cascading risk increase to 95%.
  3. *Citizen complaint spike & transit delay correlation*: Rapid citizen reports of transit bus delays result in an automated correlation signal and a transit rerouting recommendation.
  4. *Outage resolution & risk normalization*: Utility status updates from "FAILED" to "OPERATIONAL" triggers a risk reduction cascade, updating the map.
  5. *Multi-session concurrent operator actions*: Two separate operators run parallel simulations in different sectors simultaneously, verifying concurrency and database consistency.
