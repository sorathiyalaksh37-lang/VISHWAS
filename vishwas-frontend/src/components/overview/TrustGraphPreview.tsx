import { PREVIEW_CONTACTS, PREVIEW_EDGES, type NodeCategory } from '../../data/sampleData'

/** Pixel positions for the 5-node preview layout (SVG viewBox 360×200) */
const NODE_POS: Record<string, { x: number; y: number }> = {
  'self':         { x: 180, y: 100 },
  'family':       { x:  60, y:  48 },
  'friend':       { x:  60, y: 152 },
  'bank':         { x: 300, y:  48 },
  'unknown-prev': { x: 300, y: 152 },
}

const NODE_COLOR: Record<NodeCategory, string> = {
  self:       '#10B981',
  trusted:    '#3B82F6',
  verified:   '#8B5CF6',
  unverified: '#EF4444',
  pending:    '#F59E0B',
}

const EDGE_COLOR: Record<NodeCategory, string> = {
  self:       '#10B981',
  trusted:    '#3B82F650',
  verified:   '#8B5CF650',
  unverified: '#EF444450',
  pending:    '#F59E0B50',
}

const LEGEND = [
  { color: '#10B981', label: 'You (account)' },
  { color: '#3B82F6', label: 'Trusted' },
  { color: '#8B5CF6', label: 'Verified' },
  { color: '#EF4444', label: 'Unverified' },
]

/**
 * Small SVG relationship graph used on the Overview page.
 * Illustrative demo data — not real contacts.
 */
export function TrustGraphPreview() {
  const nodeMap = Object.fromEntries(PREVIEW_CONTACTS.map(n => [n.id, n]))

  return (
    <div className="tg-preview" aria-label="Trust graph preview — illustrative demo data">
      <svg
        viewBox="0 0 360 200"
        className="tg-preview__svg"
        aria-hidden="true"
        focusable="false"
      >
        {/* Edges */}
        {PREVIEW_EDGES.map((edge) => {
          const src = NODE_POS[edge.source]
          const tgt = NODE_POS[edge.target]
          const targetNode = nodeMap[edge.target]
          if (!src || !tgt || !targetNode) return null
          return (
            <line
              key={`${edge.source}-${edge.target}`}
              x1={src.x} y1={src.y}
              x2={tgt.x} y2={tgt.y}
              stroke={EDGE_COLOR[targetNode.category]}
              strokeWidth={1.5}
            />
          )
        })}

        {/* Nodes */}
        {PREVIEW_CONTACTS.map((node) => {
          const pos = NODE_POS[node.id]
          if (!pos) return null
          const isSelf = node.category === 'self'
          const r = isSelf ? 22 : 17
          const color = NODE_COLOR[node.category]
          return (
            <g key={node.id} transform={`translate(${pos.x},${pos.y})`}>
              <circle
                r={r}
                fill={`${color}20`}
                stroke={color}
                strokeWidth={isSelf ? 2 : 1.5}
              />
              {/* Icon letter */}
              <text
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={isSelf ? 11 : 9}
                fontWeight="700"
                fill={color}
                fontFamily="Inter, sans-serif"
              >
                {node.label.charAt(0)}
              </text>
              {/* Label below */}
              <text
                textAnchor="middle"
                y={r + 12}
                fontSize={8}
                fill="#9CA3AF"
                fontFamily="Inter, sans-serif"
              >
                {node.label}
              </text>
            </g>
          )
        })}
      </svg>

      {/* Legend */}
      <div className="tg-preview__legend" aria-label="Legend">
        {LEGEND.map(({ color, label }) => (
          <span key={label} className="tg-preview__legend-item">
            <span
              className="tg-preview__legend-dot"
              style={{ background: color }}
              aria-hidden="true"
            />
            {label}
          </span>
        ))}
      </div>
    </div>
  )
}
