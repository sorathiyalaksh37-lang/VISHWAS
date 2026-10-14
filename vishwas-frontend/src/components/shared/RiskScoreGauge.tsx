import { useEffect, useState } from 'react'

/**
 * Risk Score Gauge Component
 * 
 * A semicircular speedometer-style gauge that displays a risk score from 0-100
 * with color-coded categories and an animated needle.
 */

interface RiskScoreGaugeProps {
  /** Risk score from 0 to 100 */
  score: number
  /** Show interactive test controls */
  showControls?: boolean
  /** Enable animation */
  animated?: boolean
  /** Custom width (default: 100%) */
  width?: number | string
  /** Custom height (default: auto) */
  height?: number | string
}

// Risk thresholds (configurable)
const RISK_THRESHOLDS = {
  LOW: 25,
  MEDIUM: 50,
  HIGH: 75,
  CRITICAL: 100,
} as const

// Risk categories with colors
const RISK_CATEGORIES = {
  LOW: { label: 'Low Risk', color: '#22C55E', range: [0, RISK_THRESHOLDS.LOW] },
  MEDIUM: { label: 'Medium Risk', color: '#F97316', range: [RISK_THRESHOLDS.LOW, RISK_THRESHOLDS.MEDIUM] },
  HIGH: { label: 'High Risk', color: '#EF4444', range: [RISK_THRESHOLDS.MEDIUM, RISK_THRESHOLDS.HIGH] },
  CRITICAL: { label: 'Critical Risk', color: '#991B1B', range: [RISK_THRESHOLDS.HIGH, RISK_THRESHOLDS.CRITICAL] },
} as const

type RiskCategory = keyof typeof RISK_CATEGORIES

function getRiskCategory(score: number): RiskCategory {
  if (score < RISK_THRESHOLDS.LOW) return 'LOW'
  if (score < RISK_THRESHOLDS.MEDIUM) return 'MEDIUM'
  if (score < RISK_THRESHOLDS.HIGH) return 'HIGH'
  return 'CRITICAL'
}

export function RiskScoreGauge({
  score: inputScore,
  showControls = false,
  animated = true,
  width = '100%',
  height = 'auto',
}: RiskScoreGaugeProps) {
  // Clamp score to 0-100
  const score = Math.max(0, Math.min(100, inputScore))
  
  // State for animated score
  const [displayScore, setDisplayScore] = useState(animated ? 0 : score)
  const [testScore, setTestScore] = useState(score)

  // Animate score change
  useEffect(() => {
    if (!animated) {
      setDisplayScore(score)
      return
    }

    let startTime: number | null = null
    const duration = 1000 // 1 second animation
    const startScore = displayScore
    const endScore = score

    const animate = (timestamp: number) => {
      if (!startTime) startTime = timestamp
      const progress = Math.min((timestamp - startTime) / duration, 1)
      
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = startScore + (endScore - startScore) * eased
      
      setDisplayScore(current)

      if (progress < 1) {
        requestAnimationFrame(animate)
      }
    }

    requestAnimationFrame(animate)
  }, [score, animated])

  const category = getRiskCategory(displayScore)
  const categoryInfo = RISK_CATEGORIES[category]

  // SVG dimensions
  const svgWidth = 400
  const svgHeight = 240
  const centerX = svgWidth / 2
  const centerY = svgHeight - 40
  const radius = 140
  const strokeWidth = 32

  // Calculate angles (semicircle from -90 to +90 degrees)
  const startAngle = -180
  const endAngle = 0
  const totalAngle = endAngle - startAngle

  // Calculate needle angle based on score (0 = left, 100 = right)
  const needleAngle = startAngle + (totalAngle * displayScore) / 100

  // Create gauge segments
  const segments = [
    { category: 'LOW', start: 0, end: 25, color: RISK_CATEGORIES.LOW.color },
    { category: 'MEDIUM', start: 25, end: 50, color: RISK_CATEGORIES.MEDIUM.color },
    { category: 'HIGH', start: 50, end: 75, color: RISK_CATEGORIES.HIGH.color },
    { category: 'CRITICAL', start: 75, end: 100, color: RISK_CATEGORIES.CRITICAL.color },
  ]

  // Convert angle to radians
  const toRadians = (angle: number) => (angle * Math.PI) / 180

  // Create SVG arc path
  const createArcPath = (startPercent: number, endPercent: number) => {
    const startAng = startAngle + (totalAngle * startPercent) / 100
    const endAng = startAngle + (totalAngle * endPercent) / 100

    const startRad = toRadians(startAng)
    const endRad = toRadians(endAng)

    const x1 = centerX + radius * Math.cos(startRad)
    const y1 = centerY + radius * Math.sin(startRad)
    const x2 = centerX + radius * Math.cos(endRad)
    const y2 = centerY + radius * Math.sin(endRad)

    const largeArc = endPercent - startPercent > 50 ? 1 : 0

    return `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`
  }

  // Calculate needle position
  const needleRad = toRadians(needleAngle)
  const needleLength = radius - 10
  const needleX = centerX + needleLength * Math.cos(needleRad)
  const needleY = centerY + needleLength * Math.sin(needleRad)

  return (
    <div className="risk-score-gauge" style={{ width, height }}>
      {/* Heading */}
      <h2 className="risk-score-gauge__title">Risk Score</h2>

      {/* Gauge SVG */}
      <svg
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        className="risk-score-gauge__svg"
        role="img"
        aria-label={`Risk Score: ${Math.round(displayScore)} out of 100, ${categoryInfo.label}`}
      >
        {/* Gauge segments */}
        {segments.map((segment) => (
          <path
            key={segment.category}
            d={createArcPath(segment.start, segment.end)}
            fill="none"
            stroke={segment.color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            className="risk-score-gauge__segment"
          />
        ))}

        {/* Percentage labels on segments */}
        {segments.map((segment, index) => {
          const midPercent = (segment.start + segment.end) / 2
          const midAngle = startAngle + (totalAngle * midPercent) / 100
          const midRad = toRadians(midAngle)
          const labelRadius = radius + 35
          const labelX = centerX + labelRadius * Math.cos(midRad)
          const labelY = centerY + labelRadius * Math.sin(midRad)

          // Calculate segment percentage for display
          const segmentPercent = segment.end - segment.start

          return (
            <text
              key={`label-${segment.category}`}
              x={labelX}
              y={labelY}
              fill="#FFFFFF"
              fontSize="20"
              fontWeight="700"
              textAnchor="middle"
              dominantBaseline="middle"
              className="risk-score-gauge__label"
            >
              {segmentPercent}%
            </text>
          )
        })}

        {/* Needle base circle */}
        <circle
          cx={centerX}
          cy={centerY}
          r={12}
          fill="var(--color-text)"
          className="risk-score-gauge__needle-base"
        />

        {/* Needle */}
        <line
          x1={centerX}
          y1={centerY}
          x2={needleX}
          y2={needleY}
          stroke="var(--color-text)"
          strokeWidth="6"
          strokeLinecap="round"
          className="risk-score-gauge__needle"
          style={{
            transition: animated ? 'all 1s cubic-bezier(0.25, 0.46, 0.45, 0.94)' : 'none',
          }}
        />

        {/* Center pivot */}
        <circle
          cx={centerX}
          cy={centerY}
          r={8}
          fill="var(--color-accent)"
          className="risk-score-gauge__pivot"
        />

        {/* Score display */}
        <text
          x={centerX}
          y={centerY + 50}
          fill="var(--color-text)"
          fontSize="48"
          fontWeight="700"
          textAnchor="middle"
          className="risk-score-gauge__score"
        >
          {Math.round(displayScore)}
        </text>

        {/* Category label */}
        <text
          x={centerX}
          y={centerY + 80}
          fill={categoryInfo.color}
          fontSize="18"
          fontWeight="600"
          textAnchor="middle"
          className="risk-score-gauge__category"
        >
          {categoryInfo.label}
        </text>
      </svg>

      {/* Legend */}
      <div className="risk-score-gauge__legend">
        {Object.entries(RISK_CATEGORIES).map(([key, info]) => (
          <div key={key} className="risk-score-gauge__legend-item">
            <div
              className="risk-score-gauge__legend-color"
              style={{ backgroundColor: info.color }}
              aria-hidden="true"
            />
            <span className="risk-score-gauge__legend-label">{info.label}</span>
          </div>
        ))}
      </div>

      {/* Interactive controls for testing */}
      {showControls && (
        <div className="risk-score-gauge__controls">
          <label className="risk-score-gauge__control-label">
            Test Score: {Math.round(testScore)}
            <input
              type="range"
              min="0"
              max="100"
              value={testScore}
              onChange={(e) => setTestScore(Number(e.target.value))}
              className="risk-score-gauge__slider"
            />
          </label>
          <div className="risk-score-gauge__control-buttons">
            <button onClick={() => setTestScore(0)} className="btn-ghost btn-ghost--sm">0</button>
            <button onClick={() => setTestScore(24)} className="btn-ghost btn-ghost--sm">24</button>
            <button onClick={() => setTestScore(25)} className="btn-ghost btn-ghost--sm">25</button>
            <button onClick={() => setTestScore(49)} className="btn-ghost btn-ghost--sm">49</button>
            <button onClick={() => setTestScore(50)} className="btn-ghost btn-ghost--sm">50</button>
            <button onClick={() => setTestScore(74)} className="btn-ghost btn-ghost--sm">74</button>
            <button onClick={() => setTestScore(75)} className="btn-ghost btn-ghost--sm">75</button>
            <button onClick={() => setTestScore(100)} className="btn-ghost btn-ghost--sm">100</button>
          </div>
        </div>
      )}
    </div>
  )
}
