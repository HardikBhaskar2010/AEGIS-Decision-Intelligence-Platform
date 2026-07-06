import React, { useMemo, useEffect, useRef } from 'react';
import {
  ReactFlow,
  Handle,
  Position,
  ConnectionLineType,
  Background,
  BackgroundVariant,
} from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import { Cpu, Database, GitMerge, TrendingUp, FileText } from 'lucide-react';

// ──────────────────────────────────────────────────────────────
// Agent Node Data Model
// ──────────────────────────────────────────────────────────────
interface AgentNodeData {
  label: string;
  state: 'idle' | 'active' | 'done';
  statusText?: string;
  role: string;
  icon: React.ReactNode;
}

// ──────────────────────────────────────────────────────────────
// Custom Agent Node Component
// ──────────────────────────────────────────────────────────────
const AgentNode: React.FC<{ data: AgentNodeData }> = ({ data }) => {
  const pulseRef = useRef<HTMLDivElement>(null);

  const stateConfig = {
    idle:   { color: '#484F58', glow: 'rgba(72,79,88,0.2)',    ring: 'rgba(72,79,88,0.15)'  },
    active: { color: '#00E5FF', glow: 'rgba(0,229,255,0.35)',  ring: 'rgba(0,229,255,0.2)'  },
    done:   { color: '#3DD6A3', glow: 'rgba(61,214,163,0.3)',  ring: 'rgba(61,214,163,0.15)' },
  };

  const cfg = stateConfig[data.state];

  return (
    <div
      ref={pulseRef}
      className={`custom-agent-node ${data.state}`}
      style={{ '--node-color': cfg.color } as React.CSSProperties}
    >
      {/* Input handle */}
      <Handle
        type="target"
        position={Position.Top}
        style={{
          background: cfg.color,
          border: `2px solid ${cfg.color}`,
          width: '7px',
          height: '7px',
          boxShadow: `0 0 8px ${cfg.color}`,
          top: '-4px',
        }}
      />

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '9px' }}>
        {/* Icon badge */}
        <div style={{
          width: '28px',
          height: '28px',
          borderRadius: '7px',
          background: `rgba(${data.state === 'idle' ? '72,79,88' : data.state === 'active' ? '0,229,255' : '61,214,163'}, 0.12)`,
          border: `1px solid ${cfg.color}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          color: cfg.color,
          transition: 'all 0.3s ease',
          boxShadow: data.state === 'idle' ? 'none' : `0 0 10px ${cfg.glow}`,
        }}>
          {data.icon}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="node-role" style={{ color: data.state === 'idle' ? '#484F58' : data.state === 'active' ? 'rgba(0,229,255,0.6)' : 'rgba(61,214,163,0.6)' }}>
            {data.role}
          </div>
          <div className="node-title" style={{ color: data.state === 'idle' ? '#6B7280' : data.state === 'active' ? '#00E5FF' : '#3DD6A3' }}>
            {data.label}
          </div>
          <div className="node-status" style={{ color: data.state === 'idle' ? '#484F58' : cfg.color }}>
            {data.state === 'active' && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <span style={{
                  display: 'inline-block', width: '5px', height: '5px', borderRadius: '50%',
                  background: 'currentColor', animation: 'pulse-dot 1.2s ease-in-out infinite'
                }} />
                {data.statusText || 'Processing…'}
              </span>
            )}
            {data.state === 'done' && `✓ ${data.statusText || 'Complete'}`}
            {data.state === 'idle' && (data.statusText || 'Standby')}
          </div>
        </div>
      </div>

      {/* Output handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          background: cfg.color,
          border: `2px solid ${cfg.color}`,
          width: '7px',
          height: '7px',
          boxShadow: `0 0 8px ${cfg.color}`,
          bottom: '-4px',
        }}
      />
    </div>
  );
};

// ──────────────────────────────────────────────────────────────
// Agent Graph Props
// ──────────────────────────────────────────────────────────────
interface AgentFlowGraphProps {
  agentStates: {
    [key: string]: {
      state: 'idle' | 'active' | 'done';
      statusText?: string;
    };
  };
}

// ──────────────────────────────────────────────────────────────
// Main Graph Component
// ──────────────────────────────────────────────────────────────
export const AgentFlowGraph: React.FC<AgentFlowGraphProps> = ({ agentStates }) => {
  const nodeTypes = useMemo(() => ({ agentNode: AgentNode }), []);

  const nodes: Node[] = useMemo(() => [
    {
      id: 'orchestrator',
      type: 'agentNode',
      position: { x: 172, y: 8 },
      data: {
        label: 'Orchestrator',
        role: 'Gemini 3 Flash',
        icon: <GitMerge size={14} />,
        state: agentStates.orchestrator?.state || 'idle',
        statusText: agentStates.orchestrator?.statusText || 'Standby',
      },
    },
    {
      id: 'query',
      type: 'agentNode',
      position: { x: 0, y: 105 },
      data: {
        label: 'Query Agent',
        role: 'SQL Engine',
        icon: <Database size={14} />,
        state: agentStates.query?.state || 'idle',
        statusText: agentStates.query?.statusText || 'Standby',
      },
    },
    {
      id: 'correlation',
      type: 'agentNode',
      position: { x: 172, y: 105 },
      data: {
        label: 'Correlation',
        role: 'Anomaly Detector',
        icon: <TrendingUp size={14} />,
        state: agentStates.correlation?.state || 'idle',
        statusText: agentStates.correlation?.statusText || 'Standby',
      },
    },
    {
      id: 'forecast',
      type: 'agentNode',
      position: { x: 344, y: 105 },
      data: {
        label: 'Forecast Agent',
        role: 'Predictive Model',
        icon: <Cpu size={14} />,
        state: agentStates.forecast?.state || 'idle',
        statusText: agentStates.forecast?.statusText || 'Standby',
      },
    },
    {
      id: 'narrative',
      type: 'agentNode',
      position: { x: 172, y: 202 },
      data: {
        label: 'Narrative Agent',
        role: 'Gemini 3.1 Pro',
        icon: <FileText size={14} />,
        state: agentStates.narrative?.state || 'idle',
        statusText: agentStates.narrative?.statusText || 'Standby',
      },
    },
  ], [agentStates]);

  const edges: Edge[] = useMemo(() => {
    const isActive = (src: string, tgt: string) => {
      const s = agentStates[src]?.state;
      const t = agentStates[tgt]?.state;
      return (s === 'active' || s === 'done') && t === 'active';
    };
    const isDone = (src: string, tgt: string) =>
      agentStates[src]?.state === 'done' && agentStates[tgt]?.state === 'done';

    const cls = (src: string, tgt: string) =>
      isActive(src, tgt) ? 'active' : isDone(src, tgt) ? 'done' : '';

    const edgeStyle = (src: string, tgt: string) => ({
      stroke: isActive(src, tgt) ? '#00E5FF' : isDone(src, tgt) ? '#3DD6A3' : 'rgba(255,255,255,0.1)',
      strokeWidth: isActive(src, tgt) ? 2 : 1.5,
    });

    const defs: [string, string, string][] = [
      ['o-q',  'orchestrator', 'query'],
      ['o-c',  'orchestrator', 'correlation'],
      ['o-f',  'orchestrator', 'forecast'],
      ['o-n',  'orchestrator', 'narrative'],
      ['q-c',  'query',        'correlation'],
      ['c-f',  'correlation',  'forecast'],
      ['f-n',  'forecast',     'narrative'],
      ['q-n',  'query',        'narrative'],
    ];

    return defs.map(([id, source, target]) => ({
      id,
      source,
      target,
      animated: isActive(source, target),
      className: cls(source, target),
      style: edgeStyle(source, target),
    }));
  }, [agentStates]);

  return (
    <div className="react-flow-container" id="agent-graph-viewport">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        connectionLineType={ConnectionLineType.SmoothStep}
        fitView
        fitViewOptions={{ padding: 0.18, maxZoom: 1 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        preventScrolling={true}
        style={{ width: '100%', height: '100%' }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={18}
          size={1}
          color="rgba(255,255,255,0.04)"
        />
      </ReactFlow>
    </div>
  );
};
