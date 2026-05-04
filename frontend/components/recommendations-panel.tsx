"use client"

import { useState } from "react"
import Image from "next/image"
import { ChevronDown, ChevronUp, Radar, Target, AudioLines } from "lucide-react"
import type { Game, RecommendedGame, Weights } from "@/lib/types"
import { MATCH_LABELS } from "@/lib/score-labels"

type VectorContextKey = "mechanics" | "narrative" | "vibe" | "structure_loop"

const VECTOR_CONTEXT_KEYS: VectorContextKey[] = [
  "mechanics",
  "narrative",
  "vibe",
  "structure_loop",
]

const TAG_SIGNAL_KEYS: Array<keyof RecommendedGame["contextScores"]> = [
  "identity",
  "setting",
  "music",
]

const IMAGE_FALLBACK = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180'><rect width='100%' height='100%' fill='%2311161f'/></svg>"

const MATCH_COLORS: Record<keyof Weights["match"], string> = {
  vector: "#7dd3fc",
  genre: "#86efac",
  appeal: "#fda4af",
  music: "#fcd34d",
}

const VECTOR_CONTEXT_COLORS: Record<VectorContextKey, string> = {
  mechanics: "#7dd3fc",
  narrative: "#c084fc",
  vibe: "#2dd4bf",
  structure_loop: "#f97316",
}

const TAG_SIGNAL_REQUEST_COLOR = "rgba(248, 113, 113, 0.28)"
const TAG_SIGNAL_REQUEST_BORDER = "rgba(248, 113, 113, 0.65)"
const TAG_SIGNAL_HIT_COLOR = "#7dd3fc"

interface RecommendationsPanelProps {
  recommendations: RecommendedGame[]
  weights: Weights
  selectedGame: Game | null
  onOpenSteam?: (game: RecommendedGame) => void
}

interface ScoreBarProps {
  label: string
  value: number
  max?: number
  color?: "primary" | "accent"
  fillColor?: string
}

function ScoreBar({ label, value, max = 100, color = "primary", fillColor }: ScoreBarProps) {
  const percentage = Math.min((Math.abs(value) / max) * 100, 100)
  const isNegative = value < 0
  
  return (
    <div className="flex items-center gap-2">
      <span className="terminal-label w-20 capitalize truncate">
        {label.replace(/_/g, " ")}
      </span>
      <div className="flex-1 progress-track">
        <div 
          className={isNegative ? "h-full bg-destructive" : color === "accent" ? "progress-fill-green" : "progress-fill"}
          style={{ width: `${percentage}%`, ...(fillColor ? { background: fillColor } : {}) }}
        />
      </div>
      <span className={`data-value text-[10px] w-12 text-right ${isNegative ? "text-destructive" : ""}`}>
        {value.toFixed(1)}%
      </span>
    </div>
  )
}

function formatReviewCount(count: number) {
  if (count >= 1_000_000) {
    return `${(count / 1_000_000).toFixed(count >= 10_000_000 ? 0 : 1)}m`
  }
  if (count >= 1_000) {
    return `${(count / 1_000).toFixed(count >= 10_000 ? 0 : 1)}k`
  }
  return String(count)
}

function reviewSummary(game: RecommendedGame) {
  const positive = game.reviewStats?.positive ?? 0
  const negative = game.reviewStats?.negative ?? 0
  const reviewCount = game.reviewStats?.reviewCount ?? positive + negative
  const total = positive + negative

  if (reviewCount <= 0 && total <= 0) {
    return null
  }

  const positivePercent = total > 0 ? Math.round((positive / total) * 100) : null

  return {
    positivePercent,
    reviewCount,
  }
}

function SteamReviewBar({ positivePercent, reviewCount }: { positivePercent: number | null; reviewCount: number }) {
  const fill = positivePercent ?? 0

  return (
    <div className="min-w-[160px] flex-1 max-w-[240px]">
      <div className="mb-1 flex items-center justify-between gap-3 text-[10px]">
        <span className="text-slate-300/84">Steam reviews</span>
        <span className="text-[11px] font-semibold text-white tracking-[0.01em]">
          {positivePercent !== null ? `${positivePercent}% positive` : `${formatReviewCount(reviewCount)} reviews`}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/[0.08]">
        <div
          className="h-full rounded-full bg-[linear-gradient(90deg,rgba(125,211,252,0.72)_0%,rgba(125,211,252,0.92)_100%)]"
          style={{ width: `${fill}%` }}
        />
      </div>
      <div className="mt-1 text-right text-[10px] text-slate-400">
        {formatReviewCount(reviewCount)} total
      </div>
    </div>
  )
}

interface DonutSegment {
  label: string
  value: number
  color: string
}

function polarToCartesian(cx: number, cy: number, radius: number, angle: number) {
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  }
}

function describeMix(value: number) {
  if (value >= 45) return "dominant"
  if (value >= 25) return "strong"
  if (value >= 12) return "supporting"
  return "light"
}

function DonutChart({
  title,
  segments,
  centerLabel,
  showCenterLabel = true,
  size = 86,
  strokeWidth = 11,
  subdued = false,
  inline = false,
}: {
  title: string
  segments: DonutSegment[]
  centerLabel: string
  showCenterLabel?: boolean
  size?: number
  strokeWidth?: number
  subdued?: boolean
  inline?: boolean
}) {
  const total = Math.max(segments.reduce((sum, segment) => sum + Math.max(0, segment.value), 0), 1)
  const radius = size / 2 - strokeWidth / 2 - 2
  const center = size / 2
  let cumulative = -Math.PI / 2

  return (
    <div className={inline ? "flex items-center gap-2" : `rounded-2xl p-3 ${subdued ? "border border-white/6 bg-white/[0.02]" : "border border-white/8 bg-white/[0.03]"}`}>
      {!inline ? (
        <div className={`mb-2 uppercase tracking-[0.14em] ${subdued ? "text-[9px] text-muted-foreground/80" : "text-[10px] text-muted-foreground"}`}>
          {title}
        </div>
      ) : null}
      <div className={`flex items-center gap-3 ${inline ? "min-w-0" : ""}`}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth={strokeWidth}
          />
          {segments.map((segment) => {
            const value = Math.max(0, segment.value)
            const angle = (value / total) * Math.PI * 2
            const start = cumulative
            const end = cumulative + angle
            cumulative = end

            if (angle <= 0.0001) {
              return null
            }

            const startPoint = polarToCartesian(center, center, radius, start)
            const endPoint = polarToCartesian(center, center, radius, end)
            const largeArcFlag = angle > Math.PI ? 1 : 0
            const d = [
              `M ${startPoint.x} ${startPoint.y}`,
              `A ${radius} ${radius} 0 ${largeArcFlag} 1 ${endPoint.x} ${endPoint.y}`,
            ].join(" ")

            return (
              <path
                key={segment.label}
                d={d}
                fill="none"
                stroke={segment.color}
                strokeWidth={strokeWidth}
                strokeLinecap="round"
              />
            )
          })}
          <circle cx={center} cy={center} r={radius - strokeWidth * 0.72} fill="rgba(12,18,27,0.96)" />
          {showCenterLabel ? (
            <text
              x={center}
              y={center}
              textAnchor="middle"
              dominantBaseline="central"
              className={subdued ? "fill-white/90 text-[10px] font-medium" : "fill-white text-[11px] font-semibold"}
            >
              {centerLabel}
            </text>
          ) : null}
        </svg>

        <div className={`min-w-0 flex-1 space-y-1.5 ${inline ? "hidden" : ""}`}>
          {segments.map((segment) => (
            <div key={segment.label} className={`flex items-center justify-between gap-3 uppercase tracking-[0.1em] ${subdued ? "text-[9px] text-muted-foreground/78" : "text-[10px] text-muted-foreground"}`}>
              <div className="flex min-w-0 items-center gap-2">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: segment.color, boxShadow: `0 0 8px ${segment.color}` }}
                />
                <span className="truncate">{segment.label}</span>
              </div>
              <span className={`shrink-0 ${subdued ? "text-foreground/82" : "text-foreground"}`}>{describeMix(segment.value)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function polarPoint(index: number, total: number, radius: number) {
  const angle = (-Math.PI / 2) + (index / total) * Math.PI * 2
  return {
    x: 80 + Math.cos(angle) * radius,
    y: 80 + Math.sin(angle) * radius,
  }
}

function StructuralRadar({ game, weights }: { game: RecommendedGame; weights: Weights }) {
  const axes = VECTOR_CONTEXT_KEYS
  const targetValues = axes.map((axis) => Math.max(8, weights.context[axis]))
  const matchedValues = axes.map((axis) => Math.max(8, Math.min(100, (game.contextScores[axis] / 30) * 100)))
  const targetPolygon = targetValues
    .map((value, index) => {
      const point = polarPoint(index, axes.length, 14 + (value / 100) * 56)
      return `${point.x},${point.y}`
    })
    .join(" ")
  const matchedPolygon = matchedValues
    .map((value, index) => {
      const point = polarPoint(index, axes.length, 14 + (value / 100) * 56)
      return `${point.x},${point.y}`
    })
    .join(" ")

  return (
    <div className="grid items-start gap-5 lg:grid-cols-[188px_minmax(0,1fr)]">
      <div className="mx-auto w-[188px]">
        <svg viewBox="0 0 160 160" className="h-[188px] w-[188px] overflow-visible">
          {[22, 38, 54, 70].map((radius) => (
            <polygon
              key={radius}
              points={axes.map((_, index) => {
                const point = polarPoint(index, axes.length, radius)
                return `${point.x},${point.y}`
              }).join(" ")}
              fill="none"
              stroke="rgba(255,255,255,0.14)"
              strokeWidth="1"
            />
          ))}
          {axes.map((_, index) => {
            const point = polarPoint(index, axes.length, 76)
            return (
              <line
                key={`axis-${index}`}
                x1="80"
                y1="80"
                x2={point.x}
                y2={point.y}
                stroke="rgba(255,255,255,0.12)"
                strokeWidth="1"
              />
            )
          })}
          <polygon
            points={targetPolygon}
            fill="rgba(249, 168, 212, 0.10)"
            stroke="rgba(249, 168, 212, 0.85)"
            strokeWidth="1.6"
            strokeDasharray="4 4"
          />
          <polygon
            points={matchedPolygon}
            fill="rgba(125, 211, 252, 0.18)"
            stroke="#7dd3fc"
            strokeWidth="2.25"
            style={{ filter: "drop-shadow(0 0 12px rgba(125, 211, 252, 0.35))" }}
          />
          {matchedValues.map((value, index) => {
            const point = polarPoint(index, matchedValues.length, 14 + (value / 100) * 56)
            return <circle key={`point-${index}`} cx={point.x} cy={point.y} r="3" fill="#7dd3fc" />
          })}
        </svg>
        <div className="mt-3 flex items-center justify-center gap-4 text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full border border-pink-300/80 bg-pink-300/20" />
            <span>Requested</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-sky-300" />
            <span>Matched</span>
          </div>
        </div>
      </div>
      <div className="space-y-3">
        {axes.map((axis) => (
          <div key={axis} className="space-y-1.5">
            <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.1em] text-muted-foreground">
              <div className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: VECTOR_CONTEXT_COLORS[axis], boxShadow: `0 0 8px ${VECTOR_CONTEXT_COLORS[axis]}` }}
                />
                <span>{axis.replace(/_/g, " ")}</span>
              </div>
              <span className="font-semibold text-foreground">
                req {weights.context[axis]}% / hit {game.contextScores[axis].toFixed(1)}%
              </span>
            </div>
            <div className="relative h-2 overflow-hidden rounded-full bg-white/8">
              <div
                className="absolute inset-y-0 left-0 rounded-full border border-pink-300/60 bg-pink-300/20"
                style={{ width: `${Math.min(weights.context[axis], 100)}%` }}
              />
              <div
                className="absolute inset-y-0 left-0 rounded-full"
                style={{
                  width: `${Math.min(Math.max(game.contextScores[axis], 0), 100)}%`,
                  backgroundColor: VECTOR_CONTEXT_COLORS[axis],
                  boxShadow: `0 0 10px ${VECTOR_CONTEXT_COLORS[axis]}`,
                  opacity: 0.95,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

interface RecommendationCardProps {
  game: RecommendedGame
  rank: number
  weights: Weights
  selectedGame: Game | null
  highlights: string[]
  onOpenSteam?: (game: RecommendedGame) => void
}

function RecommendationCard({ game, rank, weights, selectedGame, highlights, onOpenSteam }: RecommendationCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const cardImage = game.assets.libraryCapsule || game.assets.capsuleV5 || game.image || IMAGE_FALLBACK
  const logoImage = game.assets.logo
  const scorePercentages = game.scorePercentages ?? {}
  const steamStoreUrl = `https://store.steampowered.com/app/${game.appId}`
  const matchedTags = game.matchedTags ?? {
    mechanics: [],
    narrative: [],
    vibe: [],
    structure_loop: [],
    identity: [],
    setting: [],
    music: [],
  }
  const showIdentityMatches = matchedTags.identity.length >= 3
  const showSettingMatches = matchedTags.setting.length >= 3
  const showStructureMatches = (matchedTags.structure_loop.length + matchedTags.mechanics.length) >= 3
  const showMusicMatches = matchedTags.music.length >= 3
  const hasVectorOverlap = VECTOR_CONTEXT_KEYS.some((key) => game.contextScores[key] > 0)
  const reasonChips = [
    ...(showIdentityMatches ? matchedTags.identity : []),
    ...(showSettingMatches ? matchedTags.setting : []),
    ...(showStructureMatches ? [...matchedTags.structure_loop, ...matchedTags.mechanics] : []),
    ...(showMusicMatches ? matchedTags.music : []),
  ].filter((tag, index, array) => array.indexOf(tag) === index).slice(0, 6)
  const offerChips = [
    ...game.tags.identity,
    ...game.tags.setting,
    ...game.tags.music,
    ...game.tags.narrative,
    ...game.tags.vibe,
    ...game.tags.structure_loop,
    ...game.tags.mechanics,
  ]
    .filter((tag, index, array) => array.indexOf(tag) === index)
    .filter((tag) => !reasonChips.includes(tag))
    .slice(0, 6)
  const resultMixSegments: DonutSegment[] = [
    { label: MATCH_LABELS.vector, value: scorePercentages.vector ?? game.scores.vector, color: MATCH_COLORS.vector },
    { label: MATCH_LABELS.genre, value: scorePercentages.genre ?? game.scores.genre, color: MATCH_COLORS.genre },
    { label: MATCH_LABELS.appeal, value: scorePercentages.appeal ?? game.scores.appeal, color: MATCH_COLORS.appeal },
    { label: MATCH_LABELS.music, value: scorePercentages.music ?? game.scores.music, color: MATCH_COLORS.music },
  ]
  const steamReview = reviewSummary(game)
  
  return (
    <div className="panel overflow-hidden hover:glow-box transition-all">
      {/* Header */}
      <a
        href={steamStoreUrl}
        target="_blank"
        rel="noreferrer"
        onClick={() => onOpenSteam?.(game)}
        className="block border-b border-transparent transition-colors hover:bg-secondary/20"
        aria-label={`Open ${game.title} on Steam`}
      >
      <div className="flex gap-4 p-4">
        <div className="relative flex-shrink-0">
          <div className="h-20 w-40 rounded-xl overflow-hidden bg-muted border border-border">
            <Image
              src={cardImage}
              alt={game.title}
              width={160}
              height={80}
              className="object-cover w-full h-full"
              unoptimized
            />
            {logoImage ? (
              <div className="absolute inset-x-0 bottom-0 bg-[linear-gradient(180deg,rgba(7,10,15,0)_0%,rgba(7,10,15,0.82)_100%)] px-2 py-2">
                <div className="relative h-5 w-24 max-w-full">
                  <Image
                    src={logoImage}
                    alt={`${game.title} logo`}
                    fill
                    className="object-contain object-left"
                    unoptimized
                  />
                </div>
              </div>
            ) : null}
          </div>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-4">
            <div className="min-w-0 flex-1">
              <h4 className="text-sm font-medium text-foreground truncate">{game.title}</h4>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="tag-chip">{game.category}</span>
              </div>
            </div>

            <div className="ml-auto flex flex-shrink-0 flex-col items-end gap-2 text-right">
              <div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Match
                </div>
                <div>
                  <span className="text-lg font-bold text-accent glow-text-subtle">{(game.matchScore * 100).toFixed(0)}%</span>
                </div>
              </div>
              {highlights.length > 0 && (
                <div className="flex max-w-[190px] flex-wrap justify-end gap-1.5">
                  {highlights.map((label) => (
                    <span
                      key={label}
                      className="rounded-full border border-amber-300/45 bg-amber-300/18 px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.14em] text-amber-100 shadow-[0_0_12px_rgba(252,211,77,0.16)]"
                    >
                      {label}
                    </span>
                  ))}
                </div>
              )}
              {steamReview ? (
                <SteamReviewBar
                  positivePercent={steamReview.positivePercent}
                  reviewCount={steamReview.reviewCount}
                />
              ) : null}
            </div>
          </div>
        </div>

      </div>
      </a>

      <div className="px-3 pb-2">
        {(reasonChips.length > 0 || offerChips.length > 0) && (
          <div className="mb-3">
            <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Why It Matches
            </div>
            <div className="flex flex-wrap gap-1.5">
              {reasonChips.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-sky-300/40 bg-sky-400/14 px-2.5 py-1 text-[10px] font-medium text-sky-100 shadow-[0_0_12px_rgba(56,189,248,0.16)]"
                >
                  {tag}
                </span>
              ))}
              {offerChips.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-white/12 bg-white/[0.06] px-3 py-1.5 text-[11px] font-medium text-slate-100/92"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Expand Button */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-1.5 flex items-center justify-center gap-1.5 terminal-label hover:text-primary border-t border-border hover:bg-secondary/30 transition-colors"
      >
        {isExpanded ? (
          <>
            <span>Collapse Analysis</span>
            <ChevronUp className="h-3 w-3" />
          </>
        ) : (
          <>
            <span>Expand Analysis</span>
            <ChevronDown className="h-3 w-3" />
          </>
        )}
      </button>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="p-3 border-t border-border bg-secondary/10 space-y-4">
          {/* Description */}
          <p className="text-xs text-muted-foreground leading-relaxed">
            {game.description}
          </p>

          {/* Score Contributions */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Radar className="h-3 w-3 text-primary" />
              <span className="terminal-label text-primary">What Drove This Match</span>
            </div>
            <p className="mb-3 text-[11px] leading-5 text-muted-foreground">
              This breaks down what actually carried the recommendation score for this result.
            </p>
            <DonutChart
              title="Match Breakdown"
              segments={resultMixSegments}
              centerLabel={`${Math.round(game.matchScore * 100)}%`}
              size={92}
              strokeWidth={11}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <AudioLines className="h-3 w-3 text-accent" />
                  <span className="terminal-label text-accent">Gameplay Overlap</span>
                </div>
                {hasVectorOverlap ? (
                  <>
                    <p className="mb-3 text-[11px] leading-5 text-muted-foreground">
                      Pink is the gameplay shape you asked for. Blue is how this game overlaps across mechanics, narrative, vibe, and structure loop.
                    </p>
                    {selectedGame ? <StructuralRadar game={game} weights={weights} /> : null}
                  </>
                ) : (
                  <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4 text-[11px] leading-5 text-muted-foreground">
                    No meaningful 4-vector overlap was found here.
                    This result is being carried by genre similarity, appeal alignment, or matched identity / setting / music tags instead of core structural similarity.
                  </div>
                )}
              </div>

              <div>
                <span className="terminal-label block mb-2 text-accent">Tag Match</span>
                <p className="mb-3 text-[11px] leading-5 text-muted-foreground">
                  Red shows how much signal you asked for. Blue shows how much this game actually matched for identity, setting, and music.
                </p>
                <div className="mb-3 flex items-center gap-4 text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full border" style={{ borderColor: TAG_SIGNAL_REQUEST_BORDER, backgroundColor: TAG_SIGNAL_REQUEST_COLOR }} />
                    <span>Requested</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: TAG_SIGNAL_HIT_COLOR, boxShadow: `0 0 8px ${TAG_SIGNAL_HIT_COLOR}` }} />
                    <span>Matched</span>
                  </div>
                </div>
                <div className="space-y-3">
                  {TAG_SIGNAL_KEYS.map((key) => (
                    <div key={key} className="space-y-1.5">
                      <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.1em] text-muted-foreground">
                        <span>{key.replace(/_/g, " ")}</span>
                        <span className="font-semibold text-foreground">
                          req {weights.context[key]}% / hit {game.contextScores[key].toFixed(1)}%
                        </span>
                      </div>
                      <div className="relative h-2 overflow-hidden rounded-full bg-white/8">
                        <div
                          className="absolute inset-y-0 left-0 rounded-full border"
                          style={{
                            width: `${Math.min(weights.context[key], 100)}%`,
                            borderColor: TAG_SIGNAL_REQUEST_BORDER,
                            backgroundColor: TAG_SIGNAL_REQUEST_COLOR,
                          }}
                        />
                        <div
                          className="absolute inset-y-0 left-0 rounded-full"
                          style={{
                            width: `${Math.min(Math.max(game.contextScores[key], 0), 100)}%`,
                            backgroundColor: TAG_SIGNAL_HIT_COLOR,
                            boxShadow: `0 0 10px ${TAG_SIGNAL_HIT_COLOR}`,
                            opacity: 0.95,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <span className="terminal-label block mb-2 text-accent">Matched Tags</span>
                <div className="space-y-3">
                  {showIdentityMatches && (
                    <div>
                      <div className="mb-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Identity</div>
                      <div className="flex flex-wrap gap-1">
                        {matchedTags.identity.map((tag) => (
                          <span key={`identity-${tag}`} className="tag-chip included">{tag}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {showSettingMatches && (
                    <div>
                      <div className="mb-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Setting</div>
                      <div className="flex flex-wrap gap-1">
                        {matchedTags.setting.map((tag) => (
                          <span key={`setting-${tag}`} className="tag-chip">{tag}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {showStructureMatches && (
                    <div>
                      <div className="mb-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Structure & Mechanics</div>
                      <div className="flex flex-wrap gap-1">
                        {[...matchedTags.structure_loop, ...matchedTags.mechanics].map((tag) => (
                          <span key={`structure-${tag}`} className="tag-chip">{tag}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {showMusicMatches && (
                    <div>
                      <div className="mb-1 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Music</div>
                      <div className="flex flex-wrap gap-1">
                        {matchedTags.music.map((tag) => (
                          <span key={`music-${tag}`} className="tag-chip">{tag}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Genres */}
              <div>
                <span className="terminal-label block mb-2">Genre Match</span>
                <p className="mb-3 text-[11px] leading-5 text-muted-foreground">
                  Genre overlap acts like a strength multiplier. Strong primary and subgenre alignment makes the recommendation more reliable, while weaker genre overlap means the result is being carried more by structure or niche tags.
                </p>
                <div className="flex flex-wrap gap-1">
                  {game.genres.primary.map(g => (
                    <span key={g} className="tag-chip included">{g}</span>
                  ))}
                  {game.genres.sub.map(g => (
                    <span key={g} className="tag-chip">{g}</span>
                  ))}
                  {game.genres.sub_sub.slice(0, 3).map(g => (
                    <span key={g} className="tag-chip">{g}</span>
                  ))}
                </div>
              </div>

              {/* Full Tag Signals */}
              <div>
                <span className="terminal-label block mb-2">Theme & World</span>
                <div className="flex flex-wrap gap-1">
                  {game.tags.identity.slice(0, 4).map(tag => (
                    <span key={`identity-${tag}`} className="tag-chip">{tag}</span>
                  ))}
                  {game.tags.setting.slice(0, 4).map(tag => (
                    <span key={`setting-${tag}`} className="tag-chip">{tag}</span>
                  ))}
                </div>
              </div>

              <div>
                <span className="terminal-label block mb-2">Music Tags</span>
                <div className="flex flex-wrap gap-1">
                  {game.tags.music.map(tag => (
                    <span key={tag} className="tag-chip">{tag}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export function RecommendationsPanel({ recommendations, weights, selectedGame, onOpenSteam }: RecommendationsPanelProps) {
  const topOverallId = recommendations[0]?.id ?? null
  const topStructureId =
    recommendations.reduce<RecommendedGame | null>((best, game) => {
      const current = game.contextScores.mechanics + game.contextScores.narrative + game.contextScores.vibe + game.contextScores.structure_loop
      const bestValue = best
        ? best.contextScores.mechanics + best.contextScores.narrative + best.contextScores.vibe + best.contextScores.structure_loop
        : -1
      return current > bestValue ? game : best
    }, null)?.id ?? null
  const topTagId =
    recommendations.reduce<RecommendedGame | null>((best, game) => {
      const matchedTagCount =
        (game.matchedTags?.identity.length ?? 0) +
        (game.matchedTags?.setting.length ?? 0) +
        (game.matchedTags?.music.length ?? 0) +
        (game.matchedTags?.mechanics.length ?? 0) +
        (game.matchedTags?.structure_loop.length ?? 0)
      const bestCount = best
        ? (best.matchedTags?.identity.length ?? 0) +
          (best.matchedTags?.setting.length ?? 0) +
          (best.matchedTags?.music.length ?? 0) +
          (best.matchedTags?.mechanics.length ?? 0) +
          (best.matchedTags?.structure_loop.length ?? 0)
        : -1
      return matchedTagCount > bestCount ? game : best
    }, null)?.id ?? null
  const requestedMixSegments: DonutSegment[] = [
    { label: MATCH_LABELS.vector, value: weights.match.vector, color: MATCH_COLORS.vector },
    { label: MATCH_LABELS.genre, value: weights.match.genre, color: MATCH_COLORS.genre },
    { label: MATCH_LABELS.appeal, value: weights.match.appeal, color: MATCH_COLORS.appeal },
    { label: MATCH_LABELS.music, value: weights.match.music, color: MATCH_COLORS.music },
  ]

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="panel p-4 glow-box">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Radar className="h-5 w-5 text-primary" />
              <div className="status-dot absolute -top-0.5 -right-0.5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-foreground">Recommendations</h2>
              <p className="terminal-label">{recommendations.length} matches processed</p>
              <p className="mt-1 text-[12px] leading-6 text-slate-200/84">
                The small ring on each card shows what carried that result: gameplay fit, genre match, preference match, or music match.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden xl:block">
              <DonutChart
                title="Search Mix"
                segments={requestedMixSegments}
                centerLabel="Request"
                size={58}
                strokeWidth={7}
                subdued={true}
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="terminal-label">Sorted by</span>
              <span className="data-value bg-primary/10 px-2 py-0.5 rounded border border-primary/30">
                Match Score
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Cards */}
      <div className="space-y-2">
        {recommendations.map((game, index) => (
          (() => {
            const highlights: string[] = []
            if (game.id === topOverallId) highlights.push("overall most similar")
            if (game.id === topTagId) highlights.push("best tag match")
            if (game.id === topStructureId) highlights.push("strongest structure match")
            return (
          <RecommendationCard
            key={game.id}
            game={game}
            rank={index + 1}
            weights={weights}
            selectedGame={selectedGame}
            highlights={highlights}
            onOpenSteam={onOpenSteam}
          />
            )
          })()
        ))}
      </div>

      {recommendations.length === 0 && (
        <div className="panel p-8 text-center">
          <Target className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
          <span className="terminal-label block mb-1">No Matches Found</span>
          <p className="text-xs text-muted-foreground">Adjust filters or weights to find recommendations</p>
        </div>
      )}
    </div>
  )
}
