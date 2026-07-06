import { useState, useEffect, useRef, useCallback } from 'react';
import { MaplibreMap }         from './components/MaplibreMap';
import { AgentFlowGraph }      from './components/AgentFlowGraph';
import { SituationBriefCard }  from './components/SituationBriefCard';
import { HistoryConsole }       from './components/HistoryConsole';
import type { Sector, SituationBrief, WhatIfResult, AgentEvent } from './components/types';
import { Play, ShieldCheck, Database, Terminal, History, Zap } from 'lucide-react';
import Lenis from '@studio-freight/lenis';
import gsap from 'gsap';

// ──────────────────────────────────────────────────────────────────────────
// Config
// ──────────────────────────────────────────────────────────────────────────
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE  = import.meta.env.VITE_WS_URL  || 'ws://localhost:8000';

// ──────────────────────────────────────────────────────────────────────────
// Seed Sectors — Singapore canonical (aligned with config.py)
// ──────────────────────────────────────────────────────────────────────────
const SEED_SECTORS: Sector[] = [
  { sector_id: 'sector_7',  name: 'Downtown / Civic Center',    lat: 1.2903,  lng: 103.8520, population:  85000, risk_score: 0.68 },
  { sector_id: 'sector_3',  name: 'Jurong Industrial',           lat: 1.3263,  lng: 103.7384, population:  95000, risk_score: 0.24 },
  { sector_id: 'sector_1',  name: 'Changi Logistics Hub',        lat: 1.3644,  lng: 103.9915, population: 120000, risk_score: 0.42 },
  { sector_id: 'sector_2',  name: 'Marina Bay Financial',        lat: 1.2798,  lng: 103.8514, population: 250000, risk_score: 0.19 },
  { sector_id: 'sector_4',  name: 'Woodlands Crossing',          lat: 1.4382,  lng: 103.7862, population: 175000, risk_score: 0.15 },
  { sector_id: 'sector_5',  name: 'Ang Mo Kio Heartland',        lat: 1.3691,  lng: 103.8454, population: 280000, risk_score: 0.31 },
  { sector_id: 'sector_6',  name: 'Bedok Waterfront',            lat: 1.3240,  lng: 103.9297, population: 260000, risk_score: 0.28 },
  { sector_id: 'sector_8',  name: 'Tampines Regional',           lat: 1.3496,  lng: 103.9568, population: 245000, risk_score: 0.22 },
  { sector_id: 'sector_9',  name: 'Queenstown Heritage',         lat: 1.2978,  lng: 103.8052, population:  98000, risk_score: 0.37 },
  { sector_id: 'sector_10', name: 'Sentosa Resort Island',       lat: 1.2494,  lng: 103.8303, population:  15000, risk_score: 0.55 },
];

// ──────────────────────────────────────────────────────────────────────────
// Agent State Types
// ──────────────────────────────────────────────────────────────────────────
interface AgentStates {
  [key: string]: { state: 'idle' | 'active' | 'done'; statusText: string };
}

const INITIAL_AGENT_STATES: AgentStates = {
  orchestrator: { state: 'idle', statusText: 'Standby' },
  query:        { state: 'idle', statusText: 'Standby' },
  correlation:  { state: 'idle', statusText: 'Standby' },
  forecast:     { state: 'idle', statusText: 'Standby' },
  narrative:    { state: 'idle', statusText: 'Standby' },
};

// ──────────────────────────────────────────────────────────────────────────
// Quick demo prompts
// ──────────────────────────────────────────────────────────────────────────
const DEMO_PROMPTS: { label: string; sector: string; query: string }[] = [
  { label: '🌧 Downtown Flood Alert',   sector: 'sector_7', query: 'Assess multi-domain risk and utility outages in Downtown Civic Center Sector 7' },
  { label: '⚡ Jurong Power Grid',       sector: 'sector_3', query: 'Evaluate power grid anomalies and industrial transit delays in Jurong Industrial Zone' },
  { label: '🛫 Changi Storm Forecast',  sector: 'sector_1', query: 'Forecast weather impact on Changi Logistics Hub sector operations' },
];

// ──────────────────────────────────────────────────────────────────────────
// App
// ──────────────────────────────────────────────────────────────────────────
function App() {
  const [sectors,         setSectors]         = useState<Sector[]>(SEED_SECTORS);
  const [selectedId,      setSelectedId]      = useState<string | null>(null);
  const [activeBrief,     setActiveBrief]     = useState<SituationBrief | null>(null);
  const [briefLoading,    setBriefLoading]    = useState(false);
  const [whatIfResult,    setWhatIfResult]    = useState<WhatIfResult | null>(null);
  const [whatIfLoading,   setWhatIfLoading]   = useState(false);
  const [history,         setHistory]         = useState<SituationBrief[]>([]);
  const [historyOpen,     setHistoryOpen]     = useState(false);
  const [searchQuery,     setSearchQuery]     = useState('');
  const [sessionMode,     setSessionMode]     = useState<'live' | 'simulation'>('simulation');
  const [connStatus,      setConnStatus]      = useState<'connected' | 'offline'>('offline');
  const [sessionId,       setSessionId]       = useState('');
  const [agentStates,     setAgentStates]     = useState<AgentStates>(INITIAL_AGENT_STATES);

  const wsRef      = useRef<WebSocket | null>(null);
  const lenisRef   = useRef<Lenis | null>(null);
  const headerRef  = useRef<HTMLElement>(null);
  const consoleRef = useRef<HTMLDivElement>(null);

  // ── Init: session ID, Lenis smooth scroll, GSAP header animation ────────
  useEffect(() => {
    setSessionId('session_' + Math.random().toString(36).substring(2, 10));

    // Smooth scroll for console panel
    if (consoleRef.current) {
      const lenis = new Lenis({
        wrapper: consoleRef.current,
        content: consoleRef.current,
        duration: 1.1,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        orientation: 'vertical',
        smoothWheel: true,
      });
      const raf = (time: number) => { lenis.raf(time); requestAnimationFrame(raf); };
      requestAnimationFrame(raf);
      lenisRef.current = lenis;
    }

    // GSAP header slide-in on mount
    if (headerRef.current) {
      gsap.fromTo(headerRef.current,
        { y: -60, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.7, ease: 'power3.out', delay: 0.1 }
      );
    }

    // Load persisted history
    const saved = localStorage.getItem('aegis_history');
    if (saved) {
      try { setHistory(JSON.parse(saved)); } catch { /* ignore */ }
    }

    return () => { lenisRef.current?.destroy(); };
  }, []);

  // ── Fetch live sectors ───────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const resp = await fetch(`${API_BASE}/api/v1/sectors`, {
          headers: { Authorization: 'Bearer mock-test-token-key' },
        });
        if (resp.ok) {
          const data = await resp.json();
          if (Array.isArray(data) && data.length > 0) setSectors(data);
          setConnStatus('connected');
          setSessionMode('live');
        }
      } catch {
        setConnStatus('offline');
        setSessionMode('simulation');
      }
    })();
  }, []);

  // ── WebSocket: agent event stream ────────────────────────────────────────
  const handleAgentEvent = useCallback((ev: AgentEvent) => {
    const key = ev.agent.toLowerCase();
    setAgentStates(prev => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      if (ev.type === 'agent_start') {
        next[key] = { state: 'active', statusText: ev.summary || 'Processing…' };
      } else if (ev.type === 'tool_call') {
        next[key] = { state: 'active', statusText: `Tool: ${ev.tool || 'Querying'}` };
      } else if (ev.type === 'agent_result' || ev.type === 'final_brief') {
        next[key] = { state: 'done', statusText: ev.summary || 'Complete' };
      }
      return next;
    });
  }, []);

  const connectWS = useCallback((id: string) => {
    wsRef.current?.close();
    try {
      const ws = new WebSocket(`${WS_BASE}/ws/agent-events/${id}`);
      ws.onmessage = (e) => {
        try { handleAgentEvent(JSON.parse(e.data)); } catch { /* ignore */ }
      };
      wsRef.current = ws;
    } catch { /* fallback to simulation */ }
  }, [handleAgentEvent]);

  // ── Simulated agent animation (offline mode) ─────────────────────────────
  const runSimulatedGraph = useCallback(async (sectorId: string): Promise<SituationBrief> => {
    const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));

    setAgentStates(INITIAL_AGENT_STATES);
    await sleep(200);

    const steps: [string, string, string, number][] = [
      ['agent_start',  'Orchestrator', 'Routing task to specialist agents…',     800],
      ['agent_start',  'Query',        'Translating NL → BigQuery SQL…',         1000],
      ['tool_call',    'Query',        'BigQuery.query_read_only',                1200],
      ['agent_result', 'Query',        '42 rows retrieved across 4 domains.',    600],
      ['agent_start',  'Correlation',  'Running z-score anomaly detection…',     1400],
      ['agent_result', 'Correlation',  '3 corroborating signals found.',         600],
      ['agent_start',  'Forecast',     'Calculating predictive time-series…',    1200],
      ['agent_result', 'Forecast',     'Risk trajectory forecasted: +12%/hr.',   500],
      ['agent_start',  'Narrative',    'Synthesizing brief (Gemini 3.1 Pro)…',   1600],
      ['agent_result', 'Narrative',    'Narrative grounded and validated.',       500],
      ['final_brief',  'Orchestrator', 'Brief generated successfully.',           0],
    ];

    for (const [type, agent, summary, delay] of steps) {
      handleAgentEvent({ type: type as AgentEvent['type'], agent, summary, ts: new Date().toISOString() });
      if (delay) await sleep(delay);
    }

    // Build mock brief
    const sector = SEED_SECTORS.find(s => s.sector_id === sectorId) ?? SEED_SECTORS[0];
    const risk   = sector.risk_score;

    let narrative = '';
    let recommendation = '';

    if (risk >= 0.70) {
      narrative = `CRITICAL: Multi-domain cascading failure detected in ${sector.name}. Heavy rainfall (95mm/hr) has overwhelmed storm drains — correlating directly with sub-station utility outage #OUT-9021 and an 82% spike in citizen distress reports (waterlogging, power loss). Three independent signals converge on the same 3-hour window.`;
      recommendation = 'Deploy emergency drainage crews to sector boundaries | Re-route heavy transit lanes | Activate backup sub-stations within 2 hours | Issue civic alert to residents';
    } else if (risk >= 0.35) {
      narrative = `ELEVATED: Minor anomalies detected in ${sector.name}. Sentiment analysis surfaces complaints regarding transit delays on line-B4. Local sensors indicate moderate storm bands passing — 45% probability of street-level ponding within 3 hours. Utility status nominal but flagged for monitoring.`;
      recommendation = 'Pre-position response vehicles at sector entry points | Advise reduced transit speeds | Verify flood gate triggers | Monitor utility telemetry';
    } else {
      narrative = `NOMINAL: ${sector.name} displays stable operational metrics. Weather sensors indicate clear conditions, utility infrastructure is fully operational, and citizen feedback sentiment is 78% positive. No corrective action required.`;
      recommendation = 'Maintain standard automated monitoring | Schedule routine drainage inspection next cycle';
    }

    return {
      brief_id: 'brief_' + Math.random().toString(36).substring(2, 10),
      sector_id: sector.sector_id,
      risk_score: risk,
      confidence: 0.85 + Math.random() * 0.12,
      recommendation,
      narrative,
      sources: {
        sql: `SELECT s.sector_id, w.event_type, w.severity, u.status, u.utility_type,\n       t.status AS transit_status, COUNT(f.feedback_id) AS feedback_count\nFROM \`aegis-core.sectors\` s\nLEFT JOIN \`aegis-core.weather_events\`  w ON s.sector_id = w.sector_id AND w.ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 6 HOUR)\nLEFT JOIN \`aegis-core.utility_status\` u ON s.sector_id = u.sector_id\nLEFT JOIN \`aegis-core.transit_delays\` t ON s.sector_id = t.sector_id\nLEFT JOIN \`aegis-core.citizen_feedback\` f ON s.sector_id = f.sector_id AND f.ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 3 HOUR)\nWHERE s.sector_id = '${sectorId}'\nGROUP BY 1, 2, 3, 4, 5, 6\nORDER BY w.severity DESC LIMIT 10;`,
        signals_used: ['weather_sensor_storm', 'utility_power_substation', 'transit_delay_log', 'citizen_feedback_sentiment'],
      },
      generated_at: new Date().toISOString(),
    };
  }, [handleAgentEvent]);

  // ── Main query runner ────────────────────────────────────────────────────
  const runQuery = async (queryText: string, sectorId: string) => {
    if (!sectorId || briefLoading) return;

    setBriefLoading(true);
    setWhatIfResult(null);
    setSearchQuery(queryText);
    setSelectedId(sectorId);

    let brief: SituationBrief;

    if (sessionMode === 'live') {
      connectWS(sessionId);
      try {
        const resp = await fetch(`${API_BASE}/api/v1/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer mock-test-token-key',
          },
          body: JSON.stringify({ session_id: sessionId, question: queryText }),
        });
        if (resp.ok) {
          brief = await resp.json();
        } else {
          brief = await runSimulatedGraph(sectorId);
        }
      } catch {
        brief = await runSimulatedGraph(sectorId);
      }
    } else {
      brief = await runSimulatedGraph(sectorId);
    }

    setActiveBrief(brief);

    // Sync map risk
    setSectors(prev => prev.map(s =>
      s.sector_id === brief.sector_id ? { ...s, risk_score: brief.risk_score } : s
    ));

    // Persist history
    setHistory(prev => {
      const filtered = prev.filter(b => b.sector_id !== brief.sector_id);
      const updated = [brief, ...filtered].slice(0, 15);
      localStorage.setItem('aegis_history', JSON.stringify(updated));
      return updated;
    });

    setBriefLoading(false);
  };

  // ── What-If simulation ───────────────────────────────────────────────────
  const handleWhatIf = async (rainfall: number) => {
    if (!activeBrief) return;
    setWhatIfLoading(true);

    if (sessionMode === 'live' && activeBrief.brief_id.startsWith('brief_')) {
      // Only call API for real briefs
      try {
        const resp = await fetch(`${API_BASE}/api/v1/whatif`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer mock-test-token-key' },
          body: JSON.stringify({
            brief_id: activeBrief.brief_id,
            adjustment: { rainfall_intensity_pct: rainfall },
          }),
        });
        if (resp.ok) {
          setWhatIfResult(await resp.json());
          setWhatIfLoading(false);
          return;
        }
      } catch { /* fall through to simulation */ }
    }

    // Simulated what-if
    const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));
    setAgentStates(prev => ({ ...prev, forecast: { state: 'active', statusText: 'Re-calculating trajectory…' } }));
    await sleep(900);
    setAgentStates(prev => ({ ...prev, forecast: { state: 'done', statusText: 'Trajectory updated.' }, narrative: { state: 'active', statusText: 'Re-synthesizing delta…' } }));
    await sleep(1000);
    setAgentStates(prev => ({ ...prev, narrative: { state: 'done', statusText: 'Delta synthesized.' } }));

    const base   = activeBrief.risk_score;
    const delta  = (rainfall - 50) / 100 * 0.45;
    const adj    = Math.min(1.0, Math.max(0.0, base + delta));

    setWhatIfResult({
      brief_id: activeBrief.brief_id,
      adjusted_risk_score: adj,
      delta: adj - base,
      narrative_delta: rainfall > 70
        ? `Critical storm bands simulated at ${rainfall}% intensity. Drainage systems overwhelmed — flood triggers activated in lower zones. Risk escalates +${Math.round((adj - base) * 100)}%.`
        : rainfall < 30
        ? `Reduced precipitation at ${rainfall}%. Ponding levels recede — street flooding risk normalized. Risk reduced by ${Math.abs(Math.round((adj - base) * 100))}%.`
        : `Nominal rainfall at ${rainfall}%. Operational parameters stabilized within safe containment thresholds.`,
    });

    setWhatIfLoading(false);
  };

  // ── Sector click from map ────────────────────────────────────────────────
  const handleSelectSector = (sector: Sector) => {
    const q = `Assess operational risk and anomalies in ${sector.name} sector`;
    runQuery(q, sector.sector_id);
  };

  // ── Form submit ──────────────────────────────────────────────────────────
  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;

    const lower  = q.toLowerCase();
    const match  = sectors.find(s =>
      lower.includes(s.sector_id) ||
      lower.includes(s.name.toLowerCase().split(' ')[0]) ||
      lower.includes(s.sector_id.replace('sector_', 'sector '))
    );
    const target = match?.sector_id ?? selectedId ?? 'sector_7';
    if (match) setSelectedId(match.sector_id);
    runQuery(q, target);
  };

  // ──────────────────────────────────────────────────────────────────────────
  // Render
  // ──────────────────────────────────────────────────────────────────────────
  return (
    <>
      {/* ── HEADER ── */}
      <header className="dashboard-header" ref={headerRef}>
        <div className="header-brand">
          <div className="brand-logo">A</div>
          <div className="brand-text">
            <div className="brand-title">AEGIS</div>
            <div className="brand-subtitle">Decision Intelligence Platform</div>
          </div>
        </div>

        <div className="header-right">
          {/* Connection status */}
          <div className={`status-pill ${connStatus === 'connected' ? 'online' : 'offline'}`}>
            <div className="dot" />
            {connStatus === 'connected' ? 'LIVE' : 'SANDBOX'}
          </div>

          {/* Session badge */}
          <div className="session-badge" title={sessionId}>
            <span style={{ color: 'var(--text-muted)' }}>SID</span>
            <span>{sessionId}</span>
          </div>

          {/* History toggle */}
          <button
            className={`header-icon-btn ${historyOpen ? 'active' : ''}`}
            onClick={() => setHistoryOpen(!historyOpen)}
            title="Toggle session log"
            aria-label="Toggle session history"
            id="btn-toggle-history-header"
          >
            <History size={16} />
          </button>
        </div>
      </header>

      {/* ── MAIN LAYOUT ── */}
      <main className="dashboard-layout">

        {/* ── History Sidebar ── */}
        <HistoryConsole
          isOpen={historyOpen}
          onToggle={() => setHistoryOpen(!historyOpen)}
          history={history}
          activeBriefId={activeBrief?.brief_id ?? null}
          onSelectBrief={(brief) => {
            setActiveBrief(brief);
            setSelectedId(brief.sector_id);
            setSearchQuery(`Assess ${brief.sector_id} sector status`);
            setAgentStates(INITIAL_AGENT_STATES);
            setWhatIfResult(null);
          }}
          onClearHistory={() => {
            setHistory([]);
            localStorage.removeItem('aegis_history');
          }}
        />

        {/* ── Map ── */}
        <MaplibreMap
          sectors={sectors}
          selectedSectorId={selectedId}
          onSelectSector={handleSelectSector}
        />

        {/* ── Copilot Console Panel ── */}
        <div className="console-panel" ref={consoleRef} id="copilot-console-panel">

          {/* ── Query Section ── */}
          <div className="console-section">
            <div className="console-section-header">
              <div className="console-section-title">
                <Terminal size={12} className="icon-accent" />
                Decision Query Console
              </div>
              <span className={`console-badge ${sessionMode === 'live' ? 'live' : 'sim'}`}>
                {sessionMode === 'live' ? 'LIVE' : 'EMULATED'}
              </span>
            </div>

            <form onSubmit={handleFormSubmit} className="query-form">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ask AEGIS… e.g. 'Outage risk in Jurong'"
                className="cyber-input"
                disabled={briefLoading}
                id="query-input-field"
                autoComplete="off"
              />
              <button
                type="submit"
                className="cyber-button"
                disabled={briefLoading || !searchQuery.trim()}
                id="btn-submit-query"
              >
                {briefLoading
                  ? <span className="spinner" />
                  : <Play size={13} />
                }
                <span>{briefLoading ? 'Running' : 'RUN'}</span>
              </button>
            </form>

            {/* Quick demo chips */}
            <div className="prompt-chips">
              {DEMO_PROMPTS.map((p) => (
                <button
                  key={p.sector}
                  className="prompt-chip"
                  disabled={briefLoading}
                  onClick={() => runQuery(p.query, p.sector)}
                  id={`demo-chip-${p.sector}`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* ── Agent Graph Section ── */}
          <div className="console-section">
            <div className="console-section-header">
              <div className="console-section-title">
                <Zap size={12} className="icon-accent" />
                ADK 2.0 Multi-Agent Graph
              </div>
              <span style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
                {sessionMode === 'live' ? 'WS · STREAMING' : 'EMULATED'}
              </span>
            </div>
            <AgentFlowGraph agentStates={agentStates} />
          </div>

          {/* ── Situation Brief Section ── */}
          <div className="console-section" style={{ flex: 1 }}>
            <div className="console-section-header">
              <div className="console-section-title">
                <ShieldCheck size={12} className="icon-accent" />
                Situation Room Brief
              </div>
              {activeBrief && (
                <span style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {activeBrief.brief_id}
                </span>
              )}
            </div>

            <SituationBriefCard
              brief={activeBrief}
              sectorName={activeBrief ? sectors.find(s => s.sector_id === activeBrief.sector_id)?.name : undefined}
              isLoading={briefLoading}
              onWhatIfSubmit={handleWhatIf}
              whatIfResult={whatIfResult}
              isWhatIfLoading={whatIfLoading}
              onResetWhatIf={() => setWhatIfResult(null)}
            />
          </div>

        </div>{/* /console-panel */}
      </main>
    </>
  );
}

export default App;
