import React from 'react';
import { History, X, Trash2, Clock, Shield } from 'lucide-react';
import type { SituationBrief } from './types';

interface HistoryConsoleProps {
  isOpen: boolean;
  onToggle: () => void;
  history: SituationBrief[];
  activeBriefId: string | null;
  onSelectBrief: (brief: SituationBrief) => void;
  onClearHistory: () => void;
}

// ─── Risk helpers ──────────────────────────────────────────────
const getRiskColor = (score: number) =>
  score < 0.35 ? 'var(--risk-low)' : score < 0.70 ? 'var(--risk-med)' : 'var(--risk-high)';

const getRiskBg = (score: number) =>
  score < 0.35 ? 'rgba(61,214,163,0.1)' : score < 0.70 ? 'rgba(240,180,41,0.1)' : 'rgba(240,69,58,0.1)';

const getRiskLabel = (score: number) =>
  score < 0.35 ? 'LOW' : score < 0.70 ? 'MED' : 'HIGH';

// ─── Relative time helper ────────────────────────────────────────
const relTime = (iso?: string) => {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60)  return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60)  return `${mins}m ago`;
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

// ─── Main Component ──────────────────────────────────────────────
export const HistoryConsole: React.FC<HistoryConsoleProps> = ({
  isOpen,
  onToggle,
  history,
  activeBriefId,
  onSelectBrief,
  onClearHistory,
}) => {
  return (
    <div
      className={`history-sidebar-container ${isOpen ? 'open' : ''}`}
      id="history-console-sidebar"
    >
      {/* ── Collapse / Expand Tab ── */}
      <button
        className="history-sidebar-trigger"
        onClick={onToggle}
        title={isOpen ? 'Close session log' : 'Open session log'}
        aria-label="Toggle Session History"
        id="btn-toggle-history"
      >
        {isOpen ? <X size={18} /> : <History size={18} />}
      </button>

      {/* ── Header ── */}
      <div className="history-header">
        <div className="history-header-title">
          <History size={13} color="var(--accent-cyan)" />
          Session Log
          {history.length > 0 && (
            <span style={{
              fontSize: '9px',
              fontFamily: 'var(--font-mono)',
              padding: '1px 5px',
              borderRadius: '4px',
              background: 'var(--accent-cyan-dim)',
              color: 'var(--accent-cyan)',
              border: '1px solid var(--border-glow)',
            }}>
              {history.length}
            </span>
          )}
        </div>

        {history.length > 0 && (
          <button
            className="clear-btn"
            onClick={onClearHistory}
            title="Clear all history"
            aria-label="Clear History"
            id="btn-clear-history"
          >
            <Trash2 size={12} />
          </button>
        )}
      </div>

      {/* ── List ── */}
      <div className="history-list">
        {history.length === 0 ? (
          <div className="history-empty">
            <Clock size={28} strokeWidth={1.5} style={{ color: 'var(--text-muted)' }} />
            <p>No session briefs yet. Run a query to start populating the log.</p>
          </div>
        ) : (
          history.map((brief) => {
            const isActive  = activeBriefId === brief.brief_id;
            const riskColor = getRiskColor(brief.risk_score);
            const riskBg    = getRiskBg(brief.risk_score);
            const riskLabel = getRiskLabel(brief.risk_score);
            const riskPct   = Math.round(brief.risk_score * 100);

            return (
              <button
                key={brief.brief_id}
                className={`history-item ${isActive ? 'active' : ''}`}
                onClick={() => onSelectBrief(brief)}
                id={`history-item-${brief.brief_id}`}
              >
                {/* Sector name */}
                <div className="history-item-sector">
                  {brief.sector_id.replace('_', ' ').toUpperCase()}
                </div>

                {/* Meta row */}
                <div className="history-item-meta">
                  {/* Risk badge */}
                  <span
                    className="history-risk-badge"
                    style={{
                      color: riskColor,
                      background: riskBg,
                      border: `1px solid ${riskColor}33`,
                    }}
                  >
                    <Shield
                      size={8}
                      style={{ display: 'inline', marginRight: '3px', verticalAlign: 'middle' }}
                    />
                    {riskLabel} · {riskPct}%
                  </span>

                  {/* Timestamp */}
                  <span className="history-item-time">
                    {relTime(brief.generated_at)}
                  </span>
                </div>

                {/* Tiny risk bar */}
                <div style={{
                  height: '2px',
                  background: 'rgba(255,255,255,0.05)',
                  borderRadius: '99px',
                  overflow: 'hidden',
                  marginTop: '6px',
                }}>
                  <div style={{
                    width: `${riskPct}%`,
                    height: '100%',
                    background: riskColor,
                    borderRadius: '99px',
                    boxShadow: `0 0 4px ${riskColor}`,
                    transition: 'width 0.6s ease',
                  }} />
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
};
