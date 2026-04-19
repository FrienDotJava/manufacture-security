'use client'

import { useEffect, useRef, useState } from 'react';

export interface NodeRedNode {
  id: string;
  type: string;
  name?: string;
  x: number;
  y: number;
  wires: string[][];
  outputs?: number;
  [key: string]: unknown;
}

interface FlowGraphProps {
  nodes: NodeRedNode[];
  highlightedNodeId?: string;
}

const NODE_WIDTH = 140;
const NODE_HEIGHT = 44;
const PADDING = 60;

// Color per node type
function nodeColor(type: string): string {
  const map: Record<string, string> = {
    inject:    '#5aa5da',
    debug:     '#87a980',
    function:  '#fdd0a2',
    switch:    '#f4a460',
    change:    '#a6bbcf',
    template:  '#97c0a4',
    http:      '#c2868b',
    mqtt:      '#d8bfd8',
    websocket: '#9ecae1',
    tcp:       '#74c476',
    udp:       '#74c476',
    delay:     '#c7c7c7',
    trigger:   '#fd8d3c',
    comment:   '#ffffff',
  };
  return map[type] ?? '#c9c9ff';
}

function textColor(bg: string): string {
  // simple luminance check
  const hex = bg.replace('#', '');
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.55 ? '#333' : '#fff';
}

export default function FlowGraph({ nodes, highlightedNodeId }: FlowGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [tooltip, setTooltip] = useState<{ node: NodeRedNode; x: number; y: number } | null>(null);

  const safeNodes = Array.isArray(nodes) ? nodes : [];
  
  if (!safeNodes.length) return (
    <div className="text-sm text-gray-400 text-center py-8">No flow data</div>
  );

  // Compute canvas bounds from node coordinates
  const minX = Math.min(...safeNodes.map(n => n.x)) - PADDING;
  const minY = Math.min(...safeNodes.map(n => n.y)) - PADDING;
  const maxX = Math.max(...safeNodes.map(n => n.x)) + NODE_WIDTH + PADDING;
  const maxY = Math.max(...safeNodes.map(n => n.y)) + NODE_HEIGHT + PADDING;
  const vw = maxX - minX;
  const vh = maxY - minY;

  // Build id -> node map
  const nodeMap = new Map(safeNodes.map(n => [n.id, n]));

  // Build all wire connections: { fromId, portIndex, toId }
  const wires: { fromId: string; port: number; toId: string }[] = [];
  for (const node of safeNodes) {
    node.wires.forEach((targets, port) => {
      targets.forEach(toId => {
        wires.push({ fromId: node.id, port, toId });
      });
    });
  }

  function portY(node: NodeRedNode, port: number): number {
    const totalPorts = node.wires.length || 1;
    const step = NODE_HEIGHT / (totalPorts + 1);
    return node.y - minY + step * (port + 1);
  }

  return (
    <div className="relative w-full overflow-auto border border-border rounded-lg bg-gray-50 dark:bg-gray-900">
      <svg
        ref={svgRef}
        width="100%"
        viewBox={`0 0 ${vw} ${vh}`}
        style={{ minWidth: vw, display: 'block' }}
      >
        <defs>
          <marker id="nr-arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M2 1L8 5L2 9" fill="none" stroke="#888" strokeWidth="1.5"
              strokeLinecap="round" strokeLinejoin="round"/>
          </marker>
        </defs>

        {/* Wires */}
        {wires.map(({ fromId, port, toId }, i) => {
          const from = nodeMap.get(fromId);
          const to = nodeMap.get(toId);
          if (!from || !to) return null;

          const x1 = from.x - minX + NODE_WIDTH;
          const y1 = portY(from, port);
          const x2 = to.x - minX;
          const y2 = to.y - minY + NODE_HEIGHT / 2;
          const cx = (x1 + x2) / 2;

          return (
            <path
              key={i}
              d={`M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`}
              fill="none"
              stroke="#888"
              strokeWidth="1.5"
              markerEnd="url(#nr-arrow)"
            />
          );
        })}

        {/* Nodes */}
        {safeNodes.map(node => {
          const x = node.x - minX;
          const y = node.y - minY;
          const bg = nodeColor(node.type);
          const fg = textColor(bg);
          const label = node.name || node.type;
          const isHighlighted = node.id === highlightedNodeId;

          return (
            <g
              key={node.id}
              style={{ cursor: 'pointer' }}
              onMouseEnter={e => setTooltip({ node, x: e.clientX, y: e.clientY })}
              onMouseLeave={() => setTooltip(null)}
            >
              {/* Highlight ring */}
              {isHighlighted && (
                <rect
                  x={x - 4} y={y - 4}
                  width={NODE_WIDTH + 8} height={NODE_HEIGHT + 8}
                  rx="10" fill="none"
                  stroke="#ef4444" strokeWidth="2.5"
                  strokeDasharray="5 3"
                />
              )}

              {/* Node body */}
              <rect
                x={x} y={y}
                width={NODE_WIDTH} height={NODE_HEIGHT}
                rx="6"
                fill={bg}
                stroke={isHighlighted ? '#ef4444' : '#0002'}
                strokeWidth="1"
              />

              {/* Left port dot */}
              <circle cx={x} cy={y + NODE_HEIGHT / 2} r="5"
                fill="#fff" stroke="#0003" strokeWidth="1"/>

              {/* Right port dots (one per output) */}
              {node.wires.map((_, port) => (
                <circle
                  key={port}
                  cx={x + NODE_WIDTH}
                  cy={portY(node, port)}
                  r="5"
                  fill="#fff" stroke="#0003" strokeWidth="1"
                />
              ))}

              {/* Label */}
              <text
                x={x + NODE_WIDTH / 2}
                y={y + NODE_HEIGHT / 2}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize="12"
                fontFamily="monospace"
                fill={fg}
                fontWeight="500"
              >
                {label.length > 14 ? label.slice(0, 13) + '…' : label}
              </text>

              {/* Type badge */}
              <text
                x={x + NODE_WIDTH / 2}
                y={y + NODE_HEIGHT - 4}
                textAnchor="middle"
                dominantBaseline="auto"
                fontSize="9"
                fontFamily="monospace"
                fill={fg}
                opacity={0.6}
              >
                {node.type}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 bg-white border border-border rounded-lg shadow-lg p-3 text-xs font-mono max-w-xs pointer-events-none"
          style={{ left: tooltip.x + 12, top: tooltip.y + 12 }}
        >
          <p className="font-semibold text-sm mb-1">{tooltip.node.name || tooltip.node.type}</p>
          <p className="text-gray-500">id: {tooltip.node.id}</p>
          <p className="text-gray-500">type: {tooltip.node.type}</p>
          {tooltip.node.wires.length > 0 && (
            <p className="text-gray-500">outputs: {tooltip.node.wires.length}</p>
          )}
        </div>
      )}
    </div>
  );
}