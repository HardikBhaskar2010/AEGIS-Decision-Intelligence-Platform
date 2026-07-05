import { useState, useEffect, useRef, useCallback } from 'react';
import { MaplibreMap } from './components/MaplibreMap';
import { AgentFlowGraph } from './components/AgentFlowGraph';
import { SituationBriefCard } from './components/SituationBriefCard';
import { HistoryConsole } from './components/HistoryConsole';
import type { Sector, SituationBrief, WhatIfResult, AgentEvent } from './components/types';
import { Play, ShieldCheck, Database, Terminal } from 'lucide-react';
import Lenis from '@studio-freight/lenis';

// Base API configurations
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

// Initial seed sectors to render on map before database queries or if offline
const SEED_SECTORS: Sector[] = [
  { sector_id: 'sector_7', name: 'Sector 7 - Downtown Core', lat: 12.9716, lng: 77.5946, population: 85000, risk_score: 0.18 },
  { sector_id: 'sector_3', name: 'Sector 3 - Industrial Zone', lat: 12.9250, lng: 77.5897, population: 42000, risk_score: 0.76 },
  { sector_id: 'sector_1', name: 'Sector 1 - Residential East', lat: 12.9562, lng: 77.7011, population: 120000, risk_score: 0.42 },
  { sector_id: 'sector_2', name: 'Sector 2 - Tech Park', lat: 12.8399, lng: 77.6770, population: 250000, risk_score: 0.22 },
  { sector_id: 'sector_4', name: 'Sector 4 - Commercial West', lat: 13.0298, lng: 77.5407, population: 175000, risk_score: 0.15 },
  { sector_id: 'sector_5', name: 'Sector 5 - Airport Road', lat: 13.1989, lng: 77.7068, population: 280000, risk_score: 0.31 },
  { sector_id: 'sector_6', name: 'Sector 6 - University Hub', lat: 12.9343, lng: 77.6055, population: 260000, risk_score: 0.28 },
  { sector_id: 'sector_8', name: 'Sector 8 - Logistics Park', lat: 13.0478, lng: 77.5255, population: 145000, risk_score: 0.19 },
  { sector_id: 'sector_9', name: 'Sector 9 - Medical District', lat: 12.9856, lng: 77.5361, population: 98000, risk_score: 0.25 },
  { sector_id: 'sector_10', name: 'Sector 10 - Tourism Zone', lat: 12.9719, lng: 77.6412, population: 15000, risk_score: 0.49 },
];

// Map of agent states structure
interface AgentStates {
  [key: string]: {
    state: 'idle' | 'active' | 'done';
    statusText: string;
  };
}

const INITIAL_AGENT_STATES: AgentStates = {
  orchestrator: { state: 'idle', statusText: 'Standby' },
  query: { state: 'idle', statusText: 'Standby' },
  correlation: { state: 'idle', statusText: 'Standby' },
  forecast: { state: 'idle', statusText: 'Standby' },
  narrative: { state: 'idle', statusText: 'Standby' },
};

function App() {
  const [sectors, setSectors] = useState<Sector[]>(SEED_SECTORS);
  const [selectedSectorId, setSelectedSectorId] = useState<string | null>(null);
  const [activeBrief, setActiveBrief] = useState<SituationBrief | null>(null);
  const [isBriefLoading, setIsBriefLoading] = useState<boolean>(false);
  
  // What-If Simulation State
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResult | null>(null);
  const [isWhatIfLoading, setIsWhatIfLoading] = useState<boolean>(false);
  
  // Console History
  const [history, setHistory] = useState<SituationBrief[]>([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  
  // Prompt Input
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [sessionMode, setSessionMode] = useState<'live' | 'simulation'>('simulation');
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'offline'>('offline');
  const [sessionId, setSessionId] = useState<string>('');

  // Agent Node Execution Graph state
  const [agentStates, setAgentStates] = useState<AgentStates>(INITIAL_AGENT_STATES);

  const wsRef = useRef<WebSocket | null>(null);
  const lenisRef = useRef<Lenis | null>(null);

  // Initialize Session ID & Smooth Scrolling
  useEffect(() => {
    // Generate unique session ID for streaming
    const randomId = 'session_' + Math.random().toString(36).substring(2, 10);
    setSessionId(randomId);

    // Initialize smooth scrolling with Lenis
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      smoothWheel: true,
    });

    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);
    lenisRef.current = lenis;

    // Load initial history from localStorage if any
    const saved = localStorage.getItem('aegis_history');
    if (saved) {
      try {
        setHistory(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse saved history', e);
      }
    }

    return () => {
      lenis.destroy();
    };
  }, []);

  // Fetch live operational sectors from backend on load
  const fetchSectors = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/sectors`, {
        headers: { 'Authorization': 'Bearer mock_firebase_token' }
      });
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data) && data.length > 0) {
          setSectors(data);
        }
        setConnectionStatus('connected');
        setSessionMode('live');
      } else {
        setConnectionStatus('offline');
        setSessionMode('simulation');
      }
    } catch (e) {
      console.log('Backend not detected. Falling back to frontend simulation mode.');
      setConnectionStatus('offline');
      setSessionMode('simulation');
    }
  }, []);

  useEffect(() => {
    fetchSectors();
  }, [fetchSectors]);

  // Connect to websocket stream for session events
  const connectWebSocket = useCallback((id: string) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    try {
      const ws = new WebSocket(`${WS_BASE_URL}/ws/agent-events/${id}`);
      
      ws.onopen = () => {
        console.log('WS event stream connected:', id);
        setConnectionStatus('connected');
      };

      ws.onmessage = (event) => {
        try {
          const payload: AgentEvent = JSON.parse(event.data);
          handleAgentEvent(payload);
        } catch (err) {
          console.error('Failed to parse WS payload', err);
        }
      };

      ws.onclose = () => {
        console.log('WS event stream closed');
      };

      ws.onerror = () => {
        console.log('WS error encountered, falling back to simulated event emitters.');
      };

      wsRef.current = ws;
    } catch (e) {
      console.error('WebSocket connection failed:', e);
    }
  }, []);

  // Process a single agent state change event
  const handleAgentEvent = useCallback((event: AgentEvent) => {
    const agentKey = event.agent.toLowerCase();
    
    setAgentStates((prev) => {
      const updated = { ...prev };
      
      if (!updated[agentKey]) return prev;

      if (event.type === 'agent_start') {
        updated[agentKey] = {
          state: 'active',
          statusText: event.summary || 'Processing...',
        };
      } else if (event.type === 'tool_call') {
        updated[agentKey] = {
          state: 'active',
          statusText: `Tool: ${event.tool || 'Querying'}`,
        };
      } else if (event.type === 'agent_result' || event.type === 'final_brief') {
        updated[agentKey] = {
          state: 'done',
          statusText: event.summary || 'Complete',
        };
      }

      // If Orchestrator completes, mark everything else done if they were running
      if (agentKey === 'orchestrator' && event.type === 'final_brief') {
        Object.keys(updated).forEach(k => {
          if (updated[k].state === 'active') {
            updated[k] = { state: 'done', statusText: 'Complete' };
          }
        });
      }

      return updated;
    });
  }, []);

  // Local simulated WebSocket stream for standalone demo
  const runSimulatedAgentGraph = useCallback(async (sectorId: string) => {
    const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
    
    setAgentStates(INITIAL_AGENT_STATES);
    await sleep(200);

    // 1. Orchestrator Starts
    handleAgentEvent({
      type: 'agent_start',
      agent: 'Orchestrator',
      summary: 'Task routed. Generating execution plan...',
      ts: new Date().toISOString()
    });
    await sleep(1000);

    // 2. Query Agent Starts & runs SQL
    handleAgentEvent({
      type: 'agent_start',
      agent: 'Query',
      summary: 'Translating request to BigQuery SQL...',
      ts: new Date().toISOString()
    });
    await sleep(1200);
    handleAgentEvent({
      type: 'tool_call',
      agent: 'Query',
      tool: 'BigQuery.query_read_only',
      ts: new Date().toISOString()
    });
    await sleep(1500);
    handleAgentEvent({
      type: 'agent_result',
      agent: 'Query',
      summary: 'Retrieved 42 data rows.',
      ts: new Date().toISOString()
    });
    await sleep(800);

    // 3. Correlation Agent analyzes anomalies
    handleAgentEvent({
      type: 'agent_start',
      agent: 'Correlation',
      summary: 'Running multi-domain statistical z-score...',
      ts: new Date().toISOString()
    });
    await sleep(1800);
    handleAgentEvent({
      type: 'agent_result',
      agent: 'Correlation',
      summary: 'Identified rainfall-outage correlation.',
      ts: new Date().toISOString()
    });
    await sleep(800);

    // 4. Forecast Agent models risk trajectory
    handleAgentEvent({
      type: 'agent_start',
      agent: 'Forecast',
      summary: 'Calculating predictive time-series...',
      ts: new Date().toISOString()
    });
    await sleep(1500);
    handleAgentEvent({
      type: 'agent_result',
      agent: 'Forecast',
      summary: 'Trajectory forecasted.',
      ts: new Date().toISOString()
    });
    await sleep(600);

    // 5. Narrative Agent synthesizes report
    handleAgentEvent({
      type: 'agent_start',
      agent: 'Narrative',
      summary: 'Generating Gemini 3.1 Pro summary report...',
      ts: new Date().toISOString()
    });
    await sleep(2000);
    handleAgentEvent({
      type: 'agent_result',
      agent: 'Narrative',
      summary: 'Narrative report grounded.',
      ts: new Date().toISOString()
    });
    await sleep(600);

    // 6. Complete
    handleAgentEvent({
      type: 'final_brief',
      agent: 'Orchestrator',
      summary: 'Brief generated successfully.',
      ts: new Date().toISOString()
    });

    // Return mock brief
    const targetSector = SEED_SECTORS.find(s => s.sector_id === sectorId) || SEED_SECTORS[0];
    const risk = targetSector.risk_score;
    let narrative = `An inspection of the ${targetSector.name} sector indicates a nominal risk trajectory. Meteorological forecasts display clear skies with no immediate utility outages reported. Citizen feedback sentiments remain net neutral (72% positive). No corrective measures required.`;
    let recommendation = 'Maintain standard monitoring protocols. Inspect drainage systems in routine cycles.';

    if (risk >= 0.70) {
      narrative = `CRITICAL ALERT: Multi-domain anomaly detected in ${targetSector.name} (${sectorId}). Heavy rainfall (95mm/hr peak) has overloaded localized storm drains. This correlates directly with a sub-station utility outage (#OUT-9021) and an 82% spike in adverse citizen feedback complaints describing flooded basement car parks. Synthetic sentiment pass detects high distress levels.`;
      recommendation = 'Deploy emergency drainage crews to sector boundaries. Re-route heavy transit lanes around low-lying roads. Activate localized backup sub-stations.';
    } else if (risk >= 0.35) {
      narrative = `ELEVATED RISK: Minor anomalies observed in ${targetSector.name} (${sectorId}). Gen-AI sentiment rollup highlights citizen complaints regarding transit delays on line-B4. Local weather sensors indicate moderate storm bands passing through with a 45% chance of street-level ponding in the next 3 hours.`;
      recommendation = 'Pre-position transit response vehicles. Advise drivers to reduce speeds. Verify flood gate triggers.';
    }

    const mockBrief: SituationBrief = {
      brief_id: 'brief_' + Math.random().toString(36).substring(2, 10),
      sector_id: targetSector.sector_id,
      risk_score: risk,
      confidence: 0.85 + Math.random() * 0.1,
      recommendation,
      narrative,
      sources: {
        sql: `SELECT s.sector_id, w.severity, u.status, f.sentiment\nFROM \`aegis-platform.core.sectors\` s\nLEFT JOIN \`aegis-platform.core.weather_events\` w ON s.sector_id = w.sector_id\nLEFT JOIN \`aegis-platform.core.utility_status\` u ON s.sector_id = u.sector_id\nLEFT JOIN \`aegis-platform.core.citizen_feedback\` f ON s.sector_id = f.sector_id\nWHERE s.sector_id = '${sectorId}'\nORDER BY w.ts DESC LIMIT 10;`,
        signals_used: [
          'weather_sensor_level_8',
          'power_outage_node_B',
          'citizen_feedback_outage_sentiment',
          'transit_delay_log_L12'
        ]
      },
      generated_at: new Date().toISOString()
    };

    return mockBrief;
  }, [handleAgentEvent]);

  // Main operational query trigger
  const runOperationalQuery = async (queryText: string, targetSectorId: string) => {
    if (!targetSectorId) return;
    
    setIsBriefLoading(true);
    setWhatIfResult(null);
    setSearchQuery(queryText);

    if (sessionMode === 'live') {
      connectWebSocket(sessionId);
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer mock_firebase_token',
          },
          body: JSON.stringify({
            session_id: sessionId,
            question: queryText,
          }),
        });

        if (response.ok) {
          const brief: SituationBrief = await response.json();
          setActiveBrief(brief);
          updateHistory(brief);
          
          // Sync map sector risk
          setSectors(prev => prev.map(s => 
            s.sector_id === brief.sector_id ? { ...s, risk_score: brief.risk_score } : s
          ));
        } else {
          console.error('Workflow API failed, running simulation fallback.');
          const fallbackBrief = await runSimulatedAgentGraph(targetSectorId);
          setActiveBrief(fallbackBrief);
          updateHistory(fallbackBrief);
        }
      } catch (err) {
        console.error('Failed to connect to API, running simulation.');
        const fallbackBrief = await runSimulatedAgentGraph(targetSectorId);
        setActiveBrief(fallbackBrief);
        updateHistory(fallbackBrief);
      } finally {
        setIsBriefLoading(false);
      }
    } else {
      // Direct Simulation Mode
      const brief = await runSimulatedAgentGraph(targetSectorId);
      setActiveBrief(brief);
      updateHistory(brief);
      setIsBriefLoading(false);
    }
  };

  const updateHistory = (brief: SituationBrief) => {
    setHistory(prev => {
      // Remove duplicate of same sector to keep list clean
      const filtered = prev.filter(b => b.sector_id !== brief.sector_id);
      const updated = [brief, ...filtered].slice(0, 15); // Cap at 15 items
      localStorage.setItem('aegis_history', JSON.stringify(updated));
      return updated;
    });
  };

  // Run What-If simulation on Forecast agent
  const handleWhatIfSubmit = async (rainfallIntensity: number) => {
    if (!activeBrief) return;
    setIsWhatIfLoading(true);

    if (sessionMode === 'live') {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/whatif`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer mock_firebase_token',
          },
          body: JSON.stringify({
            brief_id: activeBrief.brief_id,
            adjustment: {
              rainfall_intensity_pct: rainfallIntensity / 100,
            },
          }),
        });

        if (response.ok) {
          const result: WhatIfResult = await response.json();
          setWhatIfResult(result);
        } else {
          // Simulation fallback for what-if
          await simulateWhatIf(rainfallIntensity);
        }
      } catch (e) {
        await simulateWhatIf(rainfallIntensity);
      } finally {
        setIsWhatIfLoading(false);
      }
    } else {
      await simulateWhatIf(rainfallIntensity);
      setIsWhatIfLoading(false);
    }
  };

  const simulateWhatIf = async (val: number) => {
    const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
    
    // Animate only Forecast and Narrative agents
    setAgentStates(prev => ({
      ...prev,
      forecast: { state: 'active', statusText: 'Recalculating Trajectory...' },
      narrative: { state: 'idle', statusText: 'Waiting...' }
    }));
    await sleep(1000);
    
    setAgentStates(prev => ({
      ...prev,
      forecast: { state: 'done', statusText: 'Trajectory updated.' },
      narrative: { state: 'active', statusText: 'Re-drafting delta...' }
    }));
    await sleep(1200);

    setAgentStates(prev => ({
      ...prev,
      narrative: { state: 'done', statusText: 'Delta synthesized.' }
    }));

    if (!activeBrief) return;

    // Calculate simulated results
    const baselineRainfall = 50;
    const deltaMultiplier = (val - baselineRainfall) / 100; // -0.5 to +0.5
    
    // Risk adjusts dynamically
    let adjustedRisk = Math.min(1.0, Math.max(0.0, activeBrief.risk_score + deltaMultiplier * 0.45));
    const delta = adjustedRisk - activeBrief.risk_score;

    let narrative_delta = '';
    if (val > 75) {
      narrative_delta = `Critical storm bands simulated. An increase of rainfall to ${val}% pushes the drainage systems past capacity, escalating flood triggers in the lower sectors. Trajectory indicates +${Math.round(delta*100)}% risk increase.`;
    } else if (val < 30) {
      narrative_delta = `Reduced precipitation simulated. Rainfall dialed down to ${val}%. Ponding levels recede completely, relieving pressure on primary retention structures. Risk drops by ${Math.abs(Math.round(delta*100))}%.`;
    } else {
      narrative_delta = `Nominal adjustments simulated. Rainfall levels maintained at ${val}% within safe containment limits. Operational risk is stabilized.`;
    }

    setWhatIfResult({
      brief_id: activeBrief.brief_id,
      adjusted_risk_score: adjustedRisk,
      delta,
      narrative_delta,
    });
  };

  const handleSelectSector = (sector: Sector) => {
    setSelectedSectorId(sector.sector_id);
    const mockQueryText = `Assess operational risk factors and anomalies in ${sector.name} sector.`;
    setSearchQuery(mockQueryText);
    runOperationalQuery(mockQueryText, sector.sector_id);
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    // Find if user query matches any sector name
    const text = searchQuery.toUpperCase();
    const matchedSector = sectors.find(s => 
      text.includes(s.sector_id) || 
      text.includes(s.name.toUpperCase().split(' ')[0])
    );

    const targetId = matchedSector ? matchedSector.sector_id : (selectedSectorId || 'JURONG');
    if (matchedSector) {
      setSelectedSectorId(matchedSector.sector_id);
    }
    
    runOperationalQuery(searchQuery, targetId);
  };

  const handleClearHistory = () => {
    setHistory([]);
    localStorage.removeItem('aegis_history');
  };

  const handleSelectBriefFromHistory = (brief: SituationBrief) => {
    setActiveBrief(brief);
    setSelectedSectorId(brief.sector_id);
    setSearchQuery(`Assess operational risk factors and anomalies in ${brief.sector_id} sector.`);
    setAgentStates(INITIAL_AGENT_STATES);
    setWhatIfResult(null);
  };

  return (
    <>
      {/* Top Operations Header */}
      <header className="dashboard-header">
        <div className="header-brand">
          <div className="brand-logo">A</div>
          <div>
            <h1 className="brand-title">AEGIS</h1>
            <p style={{ fontSize: '10px', color: 'var(--text-secondary)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Decision Intelligence Copilot
            </p>
          </div>
        </div>

        <div className="header-status">
          <div className="status-indicator">
            <span style={{ color: 'var(--text-muted)' }}>Connection:</span>
            <div className={`status-dot ${connectionStatus === 'connected' ? 'active' : 'error'}`} />
            <span style={{ color: connectionStatus === 'connected' ? 'var(--accent-cyan)' : 'var(--accent-high)', fontWeight: 'bold' }}>
              {connectionStatus === 'connected' ? 'ONLINE' : 'SANDBOXED'}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', fontFamily: 'var(--font-mono)', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-color)', borderRadius: '4px', padding: '4px 10px' }}>
            <span style={{ color: 'var(--text-muted)' }}>SESSION:</span>
            <span style={{ color: 'var(--text-primary)' }}>{sessionId}</span>
          </div>
        </div>
      </header>

      {/* Main Grid Layout */}
      <main className="dashboard-layout">
        
        {/* Dockable Sidebar drawer */}
        <HistoryConsole
          isOpen={isHistoryOpen}
          onToggle={() => setIsHistoryOpen(!isHistoryOpen)}
          history={history}
          activeBriefId={activeBrief?.brief_id || null}
          onSelectBrief={handleSelectBriefFromHistory}
          onClearHistory={handleClearHistory}
        />

        {/* Map Column */}
        <MaplibreMap
          sectors={sectors}
          selectedSectorId={selectedSectorId}
          onSelectSector={handleSelectSector}
        />

        {/* Copilot Sidebar Panel */}
        <div className="console-panel" id="copilot-console-panel">
          
          {/* Ask Copilot Form */}
          <section className="console-section">
            <div className="console-section-title">
              <Terminal size={14} color="var(--accent-cyan)" />
              <span>DECISION QUERY CONSOLE</span>
            </div>
            
            <form onSubmit={handleFormSubmit} className="query-form">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ask Aegis (e.g. 'Outage risk in Jurong', 'Marina Bay anomalies')"
                className="cyber-input"
                disabled={isBriefLoading}
                id="query-input-field"
              />
              <button
                type="submit"
                className="cyber-button"
                disabled={isBriefLoading || !searchQuery.trim()}
                id="btn-submit-query"
              >
                <Play size={14} />
                <span>RUN</span>
              </button>
            </form>
            
            {/* Quick Prompts */}
            <div style={{ display: 'flex', gap: '8px', marginTop: '10px', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => {
                  setSelectedSectorId('MARINA_BAY');
                  runOperationalQuery('Assess Marina Bay anomalous feedback and power surges', 'MARINA_BAY');
                }}
                className="cyber-input"
                style={{ fontSize: '11px', padding: '4px 8px', width: 'auto', background: 'rgba(255,255,255,0.02)', cursor: 'pointer', borderStyle: 'dashed' }}
                disabled={isBriefLoading}
              >
                Demo: Marina Bay Critical Outage
              </button>
              <button
                type="button"
                onClick={() => {
                  setSelectedSectorId('CHANGI');
                  runOperationalQuery('Evaluate weather impact on Changi Logistics corridors', 'CHANGI');
                }}
                className="cyber-input"
                style={{ fontSize: '11px', padding: '4px 8px', width: 'auto', background: 'rgba(255,255,255,0.02)', cursor: 'pointer', borderStyle: 'dashed' }}
                disabled={isBriefLoading}
              >
                Demo: Changi Storm Forecast
              </button>
            </div>
          </section>

          {/* Real-time Agent Pipeline Graph */}
          <section className="console-section" style={{ background: 'rgba(0,0,0,0.1)' }}>
            <div className="console-section-title" style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Database size={14} color="var(--accent-cyan)" />
                <span>ADK 2.0 MULTI-AGENT EXECUTION GRAPH</span>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {sessionMode === 'live' ? 'STREAM: WS/EVENTS' : 'MODE: EMULATED'}
              </div>
            </div>
            
            <AgentFlowGraph agentStates={agentStates} />
          </section>

          {/* Situation Report Card */}
          <section className="console-section" style={{ flex: 1 }}>
            <div className="console-section-title">
              <ShieldCheck size={14} color="var(--accent-cyan)" />
              <span>SITUATION ROOM REPORT</span>
            </div>

            <SituationBriefCard
              brief={activeBrief}
              sectorName={activeBrief ? sectors.find(s => s.sector_id === activeBrief.sector_id)?.name : undefined}
              isLoading={isBriefLoading}
              onWhatIfSubmit={handleWhatIfSubmit}
              whatIfResult={whatIfResult}
              isWhatIfLoading={isWhatIfLoading}
              onResetWhatIf={() => setWhatIfResult(null)}
            />
          </section>
        </div>
      </main>
    </>
  );
}

export default App;
