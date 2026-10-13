import type { ContactNode, NodeCategory, TrustEdge } from '../../data/sampleData'

// ── Colour maps ────────────────────────────────────────────────────────────────

export const NODE_FILL: Record<NodeCategory, string> = {
  self:       '#10B981',
  trusted:    '#3B82F6',
  verified:   '#8B5CF6',
  unverified: '#EF4444',
  pending:    '#F59E0B',
}

export const NODE_STROKE: Record<NodeCategory, string> = {
  self:       '#34D399',
  trusted:    '#60A5FA',
  verified:   '#A78BFA',
  unverified: '#F87171',
  pending:    '#FCD34D',
}

export const EDGE_STROKE: Record<NodeCategory, string> = {
  self:       '#10B98130',
  trusted:    '#3B82F640',
  verified:   '#8B5CF640',
  unverified: '#EF444440',
  pending:    '#F59E0B40',
}

// ── Static layout positions (viewBox 700 × 420) ───────────────────────────────
// Calculated to avoid overlap and create a balanced radial layout.

export const NODE_LAYOUT: Record<string, { x: number; y: number }> = {
  'self':         { x: 350, y: 210 },
  'mother':       { x: 130, y:  90 },
  'brother':      { x: 130, y: 330 },
  'best-friend':  { x: 350, y:  60 },
  'bank-contact': { x: 570, y:  90 },
  'unknown':      { x: 570, y: 330 },
  'new-contact':  { x: 350, y: 360 },
}

// ── Sub-components ────────────────────────────────────────────────────────────

interface EdgeProps {
  edge: TrustEdge
  nodes: ContactNode[]
  layout: typeof NODE_LAYOUT
}

function GraphEdge({ edge, nodes, layout }: EdgeProps) {
  const src = layout[edge.source]
  const tgt = layout[edge.target]
  const targetNode = nodes.find(n => n.id === edge.target)
  if (!src || !tgt || !targetNode) return null

  const color = EDGE_STROKE[targetNode.category]

  return (
    <line
      x1={src.x} y1={src.y}
      x2={tgt.x} y2={tgt.y}
      stroke={color}
      strokeWidth={1.5}
    />
  )
}

interface NodeProps {
  node: ContactNode
  pos: { x: number; y: number }
  isSelected: boolean
  onSelect: (id: string) => void
}

function GraphNode({ node, pos, isSelected, onSelect }: NodeProps) {
  const isSelf = node.category === 'self'
  const r = isSelf ? 26 : 20
  const fill = NODE_FILL[node.category]
  const stroke = NODE_STROKE[node.category]

  return (
    <g
      transform={`translate(${pos.x},${pos.y})`}
      onClick={() => onSelect(node.id)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(node.id) } }}
      role="button"
      tabIndex={0}
      aria-label={`${node.label} — ${node.verificationStatus}`}
      aria-pressed={isSelected}
      style={{ cursor: 'pointer' }}
    >
      {/* Selection ring */}
      {isSelected && (
        <circle r={r + 7} fill="none" stroke={stroke} strokeWidth={1.5} opacity={0.5} />
      )}

      {/* Node circle */}
      <circle
        r={r}
        fill={`${fill}22`}
        stroke={stroke}
        strokeWidth={isSelected ? 2.5 : 1.75}
      />

      {/* Initial letter */}
      <text
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={isSelf ? 13 : 10}
        fontWeight="700"
        fill={stroke}
        fontFamily="Inter, sans-serif"
        style={{ pointerEvents: 'none', userSelect: 'none' }}
      >
        {node.label.charAt(0)}
      </text>

      {/* Name label below the circle */}
      <text
        textAnchor="middle"
        y={r + 14}
        fontSize={9}
        fill="#9CA3AF"
        fontFamily="Inter, sans-serif"
        style={{ pointerEvents: 'none', userSelect: 'none' }}
      >
        {node.label}
      </text>
    </g>
  )
}

// ── Main canvas ───────────────────────────────────────────────────────────────

interface TrustGraphCanvasProps {
  nodes: ContactNode[]
  edges: TrustEdge[]
  selectedId: string | null
  onSelectNode: (id: string | null) => void
}

export function TrustGraphCanvas({
  nodes,
  edges,
  selectedId,
  onSelectNode,
}: TrustGraphCanvasProps) {
  function handleBackgroundClick(e: React.MouseEvent<SVGSVGElement>) {
    if ((e.target as SVGElement).tagName === 'svg') onSelectNode(null)
  }

  return (
    <div className="tg-canvas-wrap" role="img" aria-label="Interactive trust relationship graph — illustrative demo data">
      <svg
        viewBox="0 0 700 420"
        className="tg-canvas"
        onClick={handleBackgroundClick}
        aria-label="Trust graph"
      >
        {/* Edges first so nodes render on top */}
        {edges.map((edge) => (
          <GraphEdge
            key={`${edge.source}-${edge.target}`}
            edge={edge}
            nodes={nodes}
            layout={NODE_LAYOUT}
          />
        ))}

        {/* Nodes */}
        {nodes.map((node) => {
          const pos = NODE_LAYOUT[node.id]
          if (!pos) return null
          return (
            <GraphNode
              key={node.id}
              node={node}
              pos={pos}
              isSelected={selectedId === node.id}
              onSelect={(id) => onSelectNode(id === selectedId ? null : id)}
            />
          )
        })}
      </svg>
    </div>
  )
}
