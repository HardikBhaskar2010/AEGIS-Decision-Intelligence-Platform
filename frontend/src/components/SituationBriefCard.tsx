import React, { useState, useEffect } from 'react';
import { ShieldAlert, AlertTriangle, CheckCircle, Database, Cpu, HelpCircle, Thermometer } from 'lucide-react';
import type { SituationBrief, WhatIfResult } from './types';

interface SituationBriefCardProps {
  brief: SituationBrief | null;
  sectorName?: string;
  isLoading: boolean;
  onWhatIfSubmit: (rainfallIntensity: number) => Promise<void>;
  whatIfResult: WhatIfResult | null;
  isWhatIfLoading: boolean;
  onResetWhatIf: () => void;
}

export const SituationBriefCard: React.FC<SituationBriefCardProps> = ({
  brief,
  sectorName,
  isLoading,
  onWhatIfSubmit,
  whatIfResult,
  isWhatIfLoading,
  onResetWhatIf,
}) => {
  const [rainfallVal, setRainfallVal] = useState<number>(50); // Default 50%
  const [sqlExpanded, setSqlExpanded] = useState<boolean>(false);
  const [signalsExpanded, setSignalsExpanded] = useState<boolean>(false);

  // Sync state if brief changes (reset what-if slider to baseline)
  useEffect(() => {
    setRainfallVal(50);
    onResetWhatIf();
  }, [brief, onResetWhatIf]);

  if (isLoading) {
    return (
      <div className="brief-card" style={{ justifyContent: 'center', alignItems: 'center', minHeight: '300px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
          <div className="status-dot active" style={{ width: '16px', height: '16px' }} />
          <span style={{ fontFamily: 'var(--font-heading)', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>
            SYNTHESIZING SITUATION BRIEF…
          </span>
        </div>
      </div>
    );
  }

  if (!brief) {
    return (
      <div className="brief-card" style={{ justifyContent: 'center', alignItems: 'center', minHeight: '300px', textAlign: 'center' }}>
        <div style={{ padding: '24px', color: 'var(--text-muted)' }}>
          <HelpCircle size={48} className="history-empty-icon" style={{ margin: '0 auto 16px', display: 'block' }} />
          <h3 style={{ color: 'var(--text-secondary)', marginBottom: '8px' }}>NO BRIEF SELECTED</h3>
          <p style={{ fontSize: '13px' }}>
            Submit a operational query or click on a map sector marker to run analysis and generate a situation room report.
          </p>
        </div>
      </div>
    );
  }

  const baseRisk = Math.round(brief.risk_score * 100);
  const confidence = Math.round(brief.confidence * 100);
  
  // Use what-if results if present
  const showWhatIf = whatIfResult !== null;
  const currentRisk = showWhatIf ? Math.round(whatIfResult.adjusted_risk_score * 100) : baseRisk;
  const riskColor = currentRisk < 35 ? '#3DD6A3' : currentRisk < 70 ? '#F0B429' : '#F0453A';
  const riskClass = currentRisk < 35 ? 'low' : currentRisk < 70 ? 'med' : 'high';

  // Format delta
  const deltaVal = showWhatIf ? Math.round(whatIfResult.delta * 100) : 0;
  const deltaText = deltaVal > 0 ? `+${deltaVal}%` : `${deltaVal}%`;
  const deltaColor = deltaVal > 0 ? 'var(--accent-high)' : deltaVal < 0 ? 'var(--accent-low)' : 'var(--text-secondary)';

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setRainfallVal(Number(e.target.value));
  };

  const handleSliderRelease = () => {
    onWhatIfSubmit(rainfallVal);
  };

  return (
    <div className={`brief-card ${riskClass}`} id={`brief-${brief.brief_id}`}>
      {/* Header section with sector name */}
      <div style={{ display: 'flex', justifyContent: 'between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', width: '100%' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="synthetic-badge">Synthetic Data System</span>
            {brief.generated_at && (
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)' }}>
                {new Date(brief.generated_at).toLocaleTimeString()}
              </span>
            )}
          </div>
          <h2 style={{ fontSize: '18px', marginTop: '4px', textTransform: 'uppercase' }}>
            Sector Analysis: {sectorName || brief.sector_id}
          </h2>
        </div>
        <div>
          {currentRisk >= 70 ? (
            <ShieldAlert color="var(--accent-high)" size={24} />
          ) : currentRisk >= 35 ? (
            <AlertTriangle color="var(--accent-med)" size={24} />
          ) : (
            <CheckCircle color="var(--accent-low)" size={24} />
          )}
        </div>
      </div>

      {/* Metrics Row */}
      <div className="brief-metrics-row">
        {/* Risk Score Gauge */}
        <div className="metric-gauge-wrapper">
          <span className="metric-label">Risk Index</span>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
            <span className="metric-value" style={{ color: riskColor }}>
              {currentRisk}%
            </span>
            {showWhatIf && (
              <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', fontWeight: 'bold', color: deltaColor }}>
                ({deltaText})
              </span>
            )}
          </div>
          <div className="metric-gauge-bar-outer">
            <div 
              className="metric-gauge-bar-inner" 
              style={{ 
                width: `${currentRisk}%`,
                background: riskColor,
                boxShadow: `0 0 10px ${riskColor}`
              }} 
            />
          </div>
        </div>

        {/* Confidence Rating Bar */}
        <div className="metric-gauge-wrapper">
          <span className="metric-label">Confidence Rating</span>
          <span className="metric-value" style={{ color: 'var(--text-primary)' }}>
            {confidence}%
          </span>
          <div className="metric-gauge-bar-outer">
            <div 
              className="metric-gauge-bar-inner" 
              style={{ 
                width: `${confidence}%`,
                background: 'linear-gradient(to right, var(--accent-blue), var(--accent-cyan))',
                boxShadow: '0 0 10px var(--accent-cyan)'
              }} 
            />
          </div>
        </div>
      </div>

      {/* Narrative block */}
      <div className="brief-narrative-section">
        <span className="brief-narrative-title">Situation Narrative</span>
        <p className="brief-narrative-text">
          {brief.narrative}
        </p>
        
        {/* What-If narrative delta overlay */}
        {showWhatIf && whatIfResult.narrative_delta && (
          <div style={{ marginTop: '10px', padding: '10px', borderLeft: '2px solid var(--accent-cyan)', background: 'rgba(0, 229, 255, 0.02)', borderRadius: '0 4px 4px 0' }}>
            <span style={{ fontSize: '11px', fontWeight: 'bold', textTransform: 'uppercase', color: 'var(--accent-cyan)', display: 'block', marginBottom: '2px' }}>
              What-If Simulation Trajectory
            </span>
            <p style={{ fontSize: '12.5px', color: 'var(--text-primary)', fontStyle: 'italic' }}>
              {whatIfResult.narrative_delta}
            </p>
          </div>
        )}
      </div>

      {/* Recommended Actions */}
      <div className="brief-rec-box">
        <div className="brief-rec-title">
          <Cpu size={14} />
          <span>Recommended Action</span>
        </div>
        <p className="brief-rec-text">
          {brief.recommendation}
        </p>
      </div>

      {/* What-If Slider Section */}
      <div style={{ borderTop: '1px solid var(--border-color)', borderBottom: '1px solid var(--border-color)', padding: '16px 0' }}>
        <div className="cyber-slider-container">
          <div className="cyber-slider-header">
            <span className="cyber-slider-label">What-If: Rainfall Intensity</span>
            <span className="cyber-slider-val">
              {isWhatIfLoading ? 'Simulating…' : `${rainfallVal}%`}
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={rainfallVal}
            onChange={handleSliderChange}
            onMouseUp={handleSliderRelease}
            onTouchEnd={handleSliderRelease}
            disabled={isWhatIfLoading}
            className="cyber-slider"
            id="whatif-rainfall-intensity"
            aria-label="What-If Rainfall Intensity"
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)' }}>
            <span>Dry (0%)</span>
            <span>Baseline (50%)</span>
            <span>Severe Deluge (100%)</span>
          </div>
        </div>
      </div>

      {/* Expandable SQL panel */}
      {brief.sources?.sql && (
        <div className="expandable-panel">
          <button 
            className="expandable-trigger"
            onClick={() => setSqlExpanded(!sqlExpanded)}
            id="btn-toggle-sql"
            aria-expanded={sqlExpanded}
            style={{ width: '100%', background: 'none', border: 'none', textAlign: 'left', padding: 0 }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Database size={13} />
              <span>Generated SQL Query</span>
            </span>
            <span>{sqlExpanded ? '▼' : '▶'}</span>
          </button>
          {sqlExpanded && (
            <div className="expandable-content">
              <pre className="sql-code">
                <code>{brief.sources.sql}</code>
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Expandable Signals panel */}
      {brief.sources?.signals_used && brief.sources.signals_used.length > 0 && (
        <div className="expandable-panel">
          <button 
            className="expandable-trigger"
            onClick={() => setSignalsExpanded(!signalsExpanded)}
            id="btn-toggle-signals"
            aria-expanded={signalsExpanded}
            style={{ width: '100%', background: 'none', border: 'none', textAlign: 'left', padding: 0 }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Thermometer size={13} />
              <span>Cross-Domain Active Signals ({brief.sources.signals_used.length})</span>
            </span>
            <span>{signalsExpanded ? '▼' : '▶'}</span>
          </button>
          {signalsExpanded && (
            <div className="expandable-content" style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {brief.sources.signals_used.map((sig, idx) => {
                const isFeedback = sig.toLowerCase().includes('feedback') || sig.toLowerCase().includes('citizen');
                return (
                  <span 
                    key={idx} 
                    style={{ 
                      fontSize: '11px',
                      fontFamily: 'var(--font-mono)',
                      padding: '2px 8px',
                      background: 'rgba(255,255,255,0.05)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px',
                      color: isFeedback ? 'var(--accent-med)' : 'var(--text-primary)'
                    }}
                  >
                    {sig} {isFeedback && <span style={{ fontSize: '8px', opacity: 0.8 }}>(SYNTHETIC)</span>}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
