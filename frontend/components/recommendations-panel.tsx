"use client"

import { memo, useState } from "react"
import Image from "next/image"
import { ChevronDown, ChevronUp, Radar, Target, AudioLines, ThumbsDown, ThumbsUp } from "lucide-react"
import type { Game, RecommendedGame, Weights } from "@/lib/types"
import { unique } from "@/lib/collections"
import { MATCH_LABELS } from "@/lib/score-labels"
import { useTimedToast } from "@/lib/use-timed-toast"

type VectorContextKey = "mechanics" | "narrative" | "vibe" | "structure_loop"
type TagContextKey = keyof Weights["tags"]
type MatchComponentKey = keyof Weights["match"]

const VECTOR_CONTEXT_KEYS: VectorContextKey[] = [
  "mechanics",
  "narrative",
  "vibe",
  "structure_loop",
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

const TAG_CONTEXT_LABELS: Record<TagContextKey, string> = {
  mechanics: "Mechanics",
  narrative: "Narrative",
  vibe: "Vibe",
  structure_loop: "Structure",
  identity: "Identity",
  setting: "Setting",
  music: "Music",
}

const TAG_CONTEXT_COMPONENT: Record<TagContextKey, MatchComponentKey> = {
  mechanics: "vector",
  narrative: "vector",
  vibe: "vector",
  structure_loop: "vector",
  identity: "appeal",
  setting: "appeal",
  music: "music",
}

const TAG_CONTEXT_COLORS: Record<TagContextKey, string> = {
  mechanics: "#7dd3fc",
  narrative: "#c084fc",
  vibe: "#2dd4bf",
  structure_loop: "#f97316",
  identity: "#fb7185",
  setting: "#60a5fa",
  music: "#fcd34d",
}

interface RecommendationsPanelProps {
  recommendations: RecommendedGame[]
  weights: Weights
  selectedGame: Game | null
  onOpenSteam?: (game: RecommendedGame, rank: number) => void
  onRecommendationFeedback?: (game: RecommendedGame, rank: number, feedback: "up" | "down") => void
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
      <span className={`data-value text-sm w-12 text-right ${isNegative ? "text-destructive" : ""}`}>
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

function normalizeTagMatchKey(tag: string) {
  return tag.trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ").toLowerCase()
}

function genreTokens(game: Pick<Game, "category" | "genres"> | null) {
  if (!game) {
    return []
  }
  return unique([
    game.category,
    ...game.genres.primary,
    ...game.genres.sub,
    ...game.genres.sub_sub,
    ...game.genres.traits,
  ].filter(Boolean))
}

function evidenceTags(influencedTags: string[], fallbackTags: string[], limit = 3, tunedTag?: string) {
  const influencedKeys = new Set(influencedTags.map(normalizeTagMatchKey))
  const tunedKey = tunedTag ? normalizeTagMatchKey(tunedTag) : null
  return unique([...influencedTags, ...fallbackTags])
    .slice(0, limit)
    .map((label) => ({
      label,
      influenced: influencedKeys.has(normalizeTagMatchKey(label)),
      tuned: tunedKey === normalizeTagMatchKey(label),
    }))
}

function changedTagWeight(context: TagContextKey, tag: string, weights: Weights, selectedGame: Game | null) {
  const requestedWeight = weights.tags[context]?.[tag] ?? 0
  const baselineEntries = selectedGame?.weights?.tags?.[context] ?? {}
  const normalizedKey = normalizeTagMatchKey(tag).replace(/\s+/g, "_")
  const legacyKey = tag.replace(/[\s-]+/g, "_").toLowerCase()
  const baselineWeight = baselineEntries[tag] ?? baselineEntries[normalizedKey] ?? baselineEntries[legacyKey] ?? 0
  const delta = requestedWeight - baselineWeight
  return delta > 1 ? { requestedWeight, delta } : null
}

function topRequestedTagMatch(game: RecommendedGame, weights: Weights, selectedGame: Game | null) {
  if (!selectedGame) {
    return null
  }

  const matchedTags = game.matchedTags ?? {
    mechanics: [],
    narrative: [],
    vibe: [],
    structure_loop: [],
    identity: [],
    setting: [],
    music: [],
  }

  const requestedByContext = (Object.keys(weights.tags) as TagContextKey[])
    .map((context) => {
      const changedWeights = Object.keys(weights.tags[context] ?? {})
        .map((tag) => changedTagWeight(context, tag, weights, selectedGame))
        .filter(Boolean)
      const maxRequestedWeight = Math.max(0, ...changedWeights.map((entry) => entry!.requestedWeight))
      const maxDelta = Math.max(0, ...changedWeights.map((entry) => entry!.delta))
      return { context, requestedWeight: maxRequestedWeight, delta: maxDelta }
    })
    .filter((item) => item.delta > 1)

  const exactMatches = requestedByContext
    .flatMap(({ context }) => {
      const matchedByKey = new Map((matchedTags[context] ?? []).map((tag) => [normalizeTagMatchKey(tag), tag]))
      const matches: Array<{
        context: TagContextKey
        component: MatchComponentKey
        tag: string
        requestedWeight: number
        contextHit: number
        componentShare: number
        exact: boolean
      }> = []

      for (const [tag] of Object.entries(weights.tags[context] ?? {})) {
        const changed = changedTagWeight(context, tag, weights, selectedGame)
        if (!changed) {
          continue
        }
        const matchedTag = matchedByKey.get(normalizeTagMatchKey(tag))
        if (!matchedTag) {
          continue
        }
        const component = TAG_CONTEXT_COMPONENT[context]
        matches.push({
          context,
          component,
          tag: matchedTag,
          requestedWeight: changed.requestedWeight,
          contextHit: game.contextScores[context] ?? 0,
          componentShare: game.scorePercentages?.[component] ?? game.scores[component] ?? 0,
          exact: true,
        })
      }
      return matches
    })
    .sort((a, b) => {
      if (b.requestedWeight !== a.requestedWeight) {
        return b.requestedWeight - a.requestedWeight
      }
      return b.contextHit - a.contextHit
    })

  if (exactMatches[0]) {
    return exactMatches[0]
  }

  for (const { context, requestedWeight } of requestedByContext.sort((a, b) => b.delta - a.delta)) {
    const matchedTag = matchedTags[context]?.[0]
    const contextHit = game.contextScores[context] ?? 0
    if (!matchedTag || contextHit <= 0) {
      continue
    }
    const component = TAG_CONTEXT_COMPONENT[context]
    return {
      context,
      component,
      tag: matchedTag,
      requestedWeight,
      contextHit,
      componentShare: game.scorePercentages?.[component] ?? game.scores[component] ?? 0,
      exact: false,
    }
  }

  return null
}

function profileCompareSections(selectedGame: Game | null, game: RecommendedGame) {
  const sections = [
    {
      label: "Genre",
      base: genreTokens(selectedGame),
      result: genreTokens(game),
    },
    {
      label: "Identity",
      base: selectedGame ? unique([
        selectedGame.identity?.signatureTag ?? "",
        ...(selectedGame.identity?.nicheAnchors ?? []),
        ...(selectedGame.identity?.identityTags ?? []),
        ...(selectedGame.identity?.microTags ?? []),
        ...selectedGame.tags.identity,
      ].filter(Boolean)) : [],
      result: unique([
        game.identity?.signatureTag ?? "",
        ...(game.identity?.nicheAnchors ?? []),
        ...(game.identity?.identityTags ?? []),
        ...(game.identity?.microTags ?? []),
        ...game.tags.identity,
      ].filter(Boolean)),
    },
    {
      label: "World",
      base: selectedGame ? unique([...(selectedGame.identity?.settingTags ?? []), ...selectedGame.tags.setting]) : [],
      result: unique([...(game.identity?.settingTags ?? []), ...game.tags.setting]),
    },
    {
      label: "Music",
      base: selectedGame ? unique([
        selectedGame.identity?.musicPrimary ?? "",
        selectedGame.identity?.musicSecondary ?? "",
        ...selectedGame.tags.music,
      ].filter(Boolean)) : [],
      result: unique([
        game.identity?.musicPrimary ?? "",
        game.identity?.musicSecondary ?? "",
        ...game.tags.music,
      ].filter(Boolean)),
    },
  ]

  return sections.map((section) => {
    const baseKeys = new Set(section.base.map(normalizeTagMatchKey))
    const resultKeys = new Set(section.result.map(normalizeTagMatchKey))
    return {
      label: section.label,
      shared: section.result.filter((tag) => baseKeys.has(normalizeTagMatchKey(tag))),
      baseOnly: section.base.filter((tag) => !resultKeys.has(normalizeTagMatchKey(tag))).slice(0, 5),
      resultOnly: section.result.filter((tag) => !baseKeys.has(normalizeTagMatchKey(tag))).slice(0, 5),
    }
  }).filter((section) => section.shared.length > 0 || section.baseOnly.length > 0 || section.resultOnly.length > 0)
}

function SteamReviewBar({ positivePercent, reviewCount }: { positivePercent: number | null; reviewCount: number }) {
  const fill = positivePercent ?? 0

  return (
    <div className="min-w-[160px] flex-1 max-w-[240px]">
      <div className="mb-1 flex items-center justify-between gap-3 text-sm">
        <span className="text-slate-300/84">Steam reviews</span>
        <span className="text-sm font-semibold text-white tracking-[0.01em]">
          {positivePercent !== null ? `${positivePercent}% positive` : `${formatReviewCount(reviewCount)} reviews`}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/[0.08]">
        <div
          className="h-full rounded-full bg-[linear-gradient(90deg,rgba(125,211,252,0.72)_0%,rgba(125,211,252,0.92)_100%)]"
          style={{ width: `${fill}%` }}
        />
      </div>
      <div className="mt-1 text-right text-sm text-slate-400">
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
        <div className={`mb-2 uppercase tracking-[0.14em] ${subdued ? "text-sm text-muted-foreground/80" : "text-sm text-muted-foreground"}`}>
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
              className={subdued ? "fill-white/90 text-sm font-medium" : "fill-white text-sm font-semibold"}
            >
              {centerLabel}
            </text>
          ) : null}
        </svg>

        <div className={`min-w-0 flex-1 space-y-1.5 ${inline ? "hidden" : ""}`}>
          {segments.map((segment) => (
            <div key={segment.label} className={`flex items-center justify-between gap-3 uppercase tracking-[0.1em] ${subdued ? "text-sm text-muted-foreground/78" : "text-sm text-muted-foreground"}`}>
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

function StructuralBars({ game, weights }: { game: RecommendedGame; weights: Weights }) {
  const axes = VECTOR_CONTEXT_KEYS

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4 text-sm uppercase tracking-[0.14em] text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full border border-pink-300/80 bg-pink-300/20" />
          <span>Requested</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-sky-300" />
          <span>Matched</span>
        </div>
      </div>
      <div className="space-y-4">
        {axes.map((axis) => (
          <div key={axis} className="space-y-2">
            <div className="flex items-center justify-between gap-3 text-sm text-slate-100">
              <div className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: VECTOR_CONTEXT_COLORS[axis], boxShadow: `0 0 8px ${VECTOR_CONTEXT_COLORS[axis]}` }}
                />
                <span className="font-semibold capitalize">{axis.replace(/_/g, " ")}</span>
              </div>
              <span className="shrink-0 text-sm font-semibold text-muted-foreground">
                req {weights.context[axis]}% / hit {game.contextScores[axis].toFixed(1)}%
              </span>
            </div>
            <div className="relative h-3 overflow-hidden rounded-full bg-white/8">
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
  onOpenSteam?: (game: RecommendedGame, rank: number) => void
  onFeedback?: (game: RecommendedGame, rank: number, feedback: "up" | "down") => void
}

const RecommendationCard = memo(function RecommendationCard({ game, rank, weights, selectedGame, highlights, onOpenSteam, onFeedback }: RecommendationCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [savedFeedback, setSavedFeedback] = useState<"up" | "down" | null>(null)
  const cardImage = game.headerImage || game.assets.header || game.assets.libraryCapsule || game.assets.capsuleV5 || game.image || IMAGE_FALLBACK
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
  const requestedTagMatch = topRequestedTagMatch(game, weights, selectedGame)
  const visibleHighlights = highlights.slice(0, 3)
  const primaryHighlight = visibleHighlights[0]
  const baseGenres = genreTokens(selectedGame)
  const resultGenres = genreTokens(game)
  const baseGenreKeys = new Set(baseGenres.map(normalizeTagMatchKey))
  const sharedGenres = resultGenres.filter((genre) => baseGenreKeys.has(normalizeTagMatchKey(genre))).slice(0, 4)
  const evidenceRows = [
    {
      label: "Structure",
      tags: evidenceTags(
        [...matchedTags.structure_loop, ...matchedTags.mechanics],
        [...game.tags.structure_loop, ...game.tags.mechanics],
        3,
        requestedTagMatch?.context === "structure_loop" || requestedTagMatch?.context === "mechanics"
          ? requestedTagMatch.tag
          : undefined,
      ),
    },
    {
      label: "Theme",
      tags: evidenceTags(
        [...matchedTags.identity, ...matchedTags.setting],
        [...game.tags.identity, ...game.tags.setting],
        3,
        requestedTagMatch?.context === "identity" || requestedTagMatch?.context === "setting"
          ? requestedTagMatch.tag
          : undefined,
      ),
    },
    {
      label: "Music",
      tags: evidenceTags(
        matchedTags.music,
        game.tags.music,
        3,
        requestedTagMatch?.context === "music" ? requestedTagMatch.tag : undefined,
      ),
    },
  ].filter((row) => row.tags.length > 0)
  const contextImpactRows = (Object.keys(weights.context) as TagContextKey[])
    .map((context) => {
      const requestedWeight = weights.context[context] ?? 0
      const contextHit = game.contextScores[context] ?? 0
      const impact = (requestedWeight * contextHit) / 100
      return {
        context,
        label: TAG_CONTEXT_LABELS[context],
        requestedWeight,
        contextHit,
        impact,
        color: TAG_CONTEXT_COLORS[context],
        tags: evidenceTags(matchedTags[context] ?? [], game.tags[context] ?? [], 3),
      }
    })
    .filter((row) => row.requestedWeight > 0 || row.contextHit > 0 || row.tags.length > 0)
    .sort((a, b) => b.impact - a.impact)
  const maxContextImpact = Math.max(1, ...contextImpactRows.map((row) => row.impact))
  const resultMixSegments: DonutSegment[] = [
    { label: MATCH_LABELS.vector, value: scorePercentages.vector ?? game.scores.vector, color: MATCH_COLORS.vector },
    { label: MATCH_LABELS.genre, value: scorePercentages.genre ?? game.scores.genre, color: MATCH_COLORS.genre },
    { label: MATCH_LABELS.appeal, value: scorePercentages.appeal ?? game.scores.appeal, color: MATCH_COLORS.appeal },
    { label: MATCH_LABELS.music, value: scorePercentages.music ?? game.scores.music, color: MATCH_COLORS.music },
  ]
  const steamReview = reviewSummary(game)
  const screenshots = (game.screenshots ?? []).filter(Boolean).slice(0, 3)
  const profileCompareRows = profileCompareSections(selectedGame, game)
  const saveFeedback = (feedback: "up" | "down") => {
    setSavedFeedback(feedback)
    onFeedback?.(game, rank, feedback)
  }
  
  return (
    <div className="panel relative overflow-hidden hover:glow-box transition-all">
      <div className="absolute right-3 top-3 z-10 flex flex-col items-end gap-1.5">
        <div className="inline-flex rounded-full border border-white/12 bg-black/45 p-1 shadow-[0_10px_24px_rgba(0,0,0,0.24)] backdrop-blur">
          <button
            type="button"
            onClick={() => saveFeedback("up")}
            aria-label={`Mark ${game.title} as a good recommendation`}
            className={`inline-flex h-8 w-8 items-center justify-center rounded-full transition ${
              savedFeedback === "up"
                ? "bg-emerald-300/22 text-emerald-100"
                : "text-slate-200/78 hover:bg-white/10 hover:text-white"
            }`}
          >
            <ThumbsUp className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => saveFeedback("down")}
            aria-label={`Mark ${game.title} as a bad recommendation`}
            className={`inline-flex h-8 w-8 items-center justify-center rounded-full transition ${
              savedFeedback === "down"
                ? "bg-rose-300/22 text-rose-100"
                : "text-slate-200/78 hover:bg-white/10 hover:text-white"
            }`}
          >
            <ThumbsDown className="h-4 w-4" />
          </button>
        </div>
      </div>
      {/* Header */}
      <a
        href={steamStoreUrl}
        target="_blank"
        rel="noreferrer"
        onClick={() => onOpenSteam?.(game, rank)}
        className="block border-b border-transparent transition-colors hover:bg-secondary/20"
        aria-label={`Open ${game.title} on Steam`}
      >
      <div className="flex flex-col gap-3 p-3 pr-24 sm:flex-row sm:gap-4 sm:pr-28">
        <div className="relative flex-shrink-0">
          <div className="h-32 w-full overflow-hidden rounded-lg border border-border bg-muted sm:h-[88px] sm:w-44">
            <Image
              src={cardImage}
              alt={game.title}
              width={192}
              height={144}
              className="object-contain w-full h-full scale-[0.92]"
              loading="lazy"
              sizes="(max-width: 640px) 100vw, 192px"
              unoptimized
            />
          </div>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-5">
            <div className="min-w-0 flex-1">
              <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
                <h4 className="min-w-0 text-base font-semibold text-foreground sm:truncate">{game.title}</h4>
                <span className="text-sm font-bold text-accent glow-text-subtle">
                  {(game.matchScore * 100).toFixed(0)}% match
                </span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="tag-chip">{game.category}</span>
                {primaryHighlight ? (
                  <span
                    className="rounded-full border border-amber-300/45 bg-amber-300/18 px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-amber-100 shadow-[0_0_12px_rgba(252,211,77,0.16)]"
                  >
                    {primaryHighlight}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="flex flex-col gap-2 sm:ml-auto sm:flex-shrink-0 sm:items-end sm:text-right">
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
        {screenshots.length > 0 && (
          <>
            <div className="mb-3 lg:hidden">
              <div className="flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                {screenshots.map((url, index) => (
                  <a
                    key={`${game.id}-card-shot-mobile-${index}`}
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="group min-w-[168px] overflow-hidden rounded-xl border border-white/10 bg-black/20"
                  >
                    <Image
                      src={url}
                      alt={`${game.title} screenshot ${index + 1}`}
                      width={320}
                      height={180}
                      className="h-24 w-[168px] object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                      loading="lazy"
                      sizes="168px"
                      unoptimized
                    />
                  </a>
                ))}
              </div>
            </div>
            <div className="mb-3 hidden lg:block">
              <div className="grid grid-cols-3 gap-3">
                {screenshots.map((url, index) => (
                  <a
                    key={`${game.id}-card-shot-${index}`}
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="group overflow-hidden rounded-xl border border-white/10 bg-black/20"
                  >
                    <Image
                      src={url}
                      alt={`${game.title} screenshot ${index + 1}`}
                      width={320}
                      height={180}
                      className="h-28 w-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                      loading="lazy"
                      sizes="(max-width: 1280px) 33vw, 320px"
                      unoptimized
                    />
                  </a>
                ))}
              </div>
            </div>
          </>
        )}

        {requestedTagMatch && (
          <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1 border-l-2 border-amber-300/60 pl-2 text-sm text-slate-200/84">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Boosted by
            </span>
            <span className="font-semibold text-slate-100">{requestedTagMatch.tag}</span>
            <span className="rounded-full border border-amber-300/35 bg-amber-300/10 px-2 py-0.5 text-xs font-semibold text-amber-50">
              {requestedTagMatch.exact ? `${Math.round(requestedTagMatch.requestedWeight)}% asked` : "closest hit"}
            </span>
            <span className="text-xs font-medium uppercase tracking-[0.1em] text-muted-foreground">
              {TAG_CONTEXT_LABELS[requestedTagMatch.context]} {requestedTagMatch.contextHit.toFixed(1)}%
            </span>
          </div>
        )}

        {evidenceRows.length > 0 && (
          <div className="mb-3">
            <div className="mb-2 text-sm uppercase tracking-[0.18em] text-muted-foreground">
              Match Receipt
            </div>
            <div className="grid items-start gap-2 md:grid-cols-2 2xl:grid-cols-4">
                {evidenceRows.map((row) => (
                  <div key={row.label} className="min-w-0 rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2">
                    <div className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      {row.label}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {row.tags.map((tag) => (
                        <span
                          key={`${row.label}-${tag.label}`}
                          className={tag.tuned
                            ? "max-w-full whitespace-normal break-words rounded-full border border-amber-300/60 bg-amber-300/16 px-2.5 py-1 text-sm font-semibold leading-5 text-amber-50 shadow-[0_0_12px_rgba(252,211,77,0.14)]"
                            : tag.influenced
                              ? "max-w-full whitespace-normal break-words rounded-full border border-sky-300/55 bg-sky-400/18 px-2.5 py-1 text-sm font-semibold leading-5 text-sky-50 shadow-[0_0_12px_rgba(56,189,248,0.14)]"
                              : "max-w-full whitespace-normal break-words rounded-full border border-white/14 bg-white/[0.075] px-2.5 py-1 text-sm font-medium leading-5 text-slate-100/88"
                          }
                          title={tag.tuned ? "Matched your tuning" : tag.influenced ? "Influenced this match" : "Result tag"}
                        >
                          {tag.label}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
                <div className="min-w-0 rounded-lg border border-emerald-300/18 bg-emerald-300/[0.045] px-3 py-2">
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      Genre
                    </div>
                    <span className="text-xs font-semibold text-emerald-100/80">
                      {sharedGenres.length} shared
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap gap-1.5">
                      {(sharedGenres.length > 0 ? sharedGenres : resultGenres.slice(0, 3)).map((genre) => (
                        <span key={`shared-${genre}`} className="max-w-full whitespace-normal break-words rounded-full border border-emerald-300/45 bg-emerald-300/14 px-2 py-0.5 text-xs font-semibold text-emerald-50">
                          {genre}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
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
        <div className="space-y-4 border-t border-border bg-secondary/10 p-3">
          <div className="rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3">
            <div className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              Store Description
            </div>
            <p className="text-sm leading-6 text-slate-200/84">
              {game.description}
            </p>
          </div>

          <div className="grid gap-3 xl:grid-cols-[minmax(220px,0.7fr)_minmax(0,1.3fr)]">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
              <div className="mb-3 flex items-center gap-2">
                <Radar className="h-3 w-3 text-primary" />
                <span className="terminal-label text-primary">Score Composition</span>
              </div>
              <DonutChart
                title="Match Breakdown"
                segments={resultMixSegments}
                centerLabel={`${Math.round(game.matchScore * 100)}%`}
                size={92}
                strokeWidth={11}
              />
            </div>

            <div className="grid gap-3 2xl:grid-cols-2">
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                <div className="mb-3 flex items-center gap-2">
                  <AudioLines className="h-3 w-3 text-accent" />
                  <span className="terminal-label text-accent">Gameplay Overlap</span>
                </div>
                {hasVectorOverlap ? (
                  selectedGame ? <StructuralBars game={game} weights={weights} /> : null
                ) : (
                  <div className="rounded-lg border border-white/10 bg-white/[0.03] px-4 py-4 text-sm leading-5 text-muted-foreground">
                    No meaningful 4-vector overlap was found here. This result is being carried by genre similarity, appeal alignment, or matched identity / setting / music tags instead.
                  </div>
                )}
              </div>

              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <span className="terminal-label text-accent">Rerank Tag Impact</span>
                  <span className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                    Weight x hit
                  </span>
                </div>
                <div className="space-y-3">
                  {contextImpactRows.map((row) => (
                    <div key={row.context} className="space-y-1.5">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-2">
                          <span
                            className="h-2.5 w-2.5 shrink-0 rounded-full"
                            style={{ backgroundColor: row.color, boxShadow: `0 0 8px ${row.color}` }}
                          />
                          <span className="truncate text-sm font-semibold text-slate-100">
                            {row.label}
                          </span>
                        </div>
                        <span className="shrink-0 text-sm font-semibold text-slate-100">
                          {row.impact.toFixed(1)}
                        </span>
                      </div>
                      <div className="grid grid-cols-[minmax(0,1fr)_92px] items-center gap-3">
                        <div className="relative h-2.5 overflow-hidden rounded-full bg-white/8">
                          <div
                            className="absolute inset-y-0 left-0 rounded-full opacity-95"
                            style={{
                              width: `${Math.min((row.impact / maxContextImpact) * 100, 100)}%`,
                              backgroundColor: row.color,
                              boxShadow: `0 0 10px ${row.color}`,
                            }}
                          />
                        </div>
                        <div className="text-right text-xs font-medium text-muted-foreground">
                          {row.requestedWeight}% x {row.contextHit.toFixed(0)}%
                        </div>
                      </div>
                      {row.tags.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {row.tags.map((tag) => (
                            <span
                              key={`${row.context}-${tag.label}`}
                              className={tag.influenced
                                ? "max-w-full whitespace-normal break-words rounded-full border border-sky-300/45 bg-sky-400/14 px-2 py-0.5 text-xs font-semibold text-sky-50"
                                : "max-w-full whitespace-normal break-words rounded-full border border-white/12 bg-white/[0.06] px-2 py-0.5 text-xs font-medium text-slate-100/80"
                              }
                              title={tag.influenced ? "Matched evidence tag" : "Result tag"}
                            >
                              {tag.label}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
              <span className="terminal-label mb-3 block text-accent">Matched Evidence</span>
              <div className="grid gap-3 md:grid-cols-2">
                {showIdentityMatches && (
                  <div>
                    <div className="mb-1 text-sm uppercase tracking-[0.16em] text-muted-foreground">Identity</div>
                    <div className="flex flex-wrap gap-1">
                      {matchedTags.identity.map((tag) => (
                        <span key={`identity-${tag}`} className="tag-chip included">{tag}</span>
                      ))}
                    </div>
                  </div>
                )}
                {showSettingMatches && (
                  <div>
                    <div className="mb-1 text-sm uppercase tracking-[0.16em] text-muted-foreground">Setting</div>
                    <div className="flex flex-wrap gap-1">
                      {matchedTags.setting.map((tag) => (
                        <span key={`setting-${tag}`} className="tag-chip">{tag}</span>
                      ))}
                    </div>
                  </div>
                )}
                {showStructureMatches && (
                  <div>
                    <div className="mb-1 text-sm uppercase tracking-[0.16em] text-muted-foreground">Structure & Mechanics</div>
                    <div className="flex flex-wrap gap-1">
                      {[...matchedTags.structure_loop, ...matchedTags.mechanics].map((tag) => (
                        <span key={`structure-${tag}`} className="tag-chip">{tag}</span>
                      ))}
                    </div>
                  </div>
                )}
                {showMusicMatches && (
                  <div>
                    <div className="mb-1 text-sm uppercase tracking-[0.16em] text-muted-foreground">Music</div>
                    <div className="flex flex-wrap gap-1">
                      {matchedTags.music.map((tag) => (
                        <span key={`music-${tag}`} className="tag-chip">{tag}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <span className="terminal-label block">Profile Comparison</span>
                <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-emerald-300" />
                    Shared
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-amber-300" />
                    Base
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-cyan-300" />
                    Result
                  </span>
                </div>
              </div>
              <div className="space-y-3">
                {profileCompareRows.map((row) => (
                  <div key={`profile-compare-${row.label}`} className="rounded-lg border border-white/10 bg-black/10 p-2.5">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="text-sm font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                        {row.label}
                      </div>
                      <span className="text-xs font-semibold text-emerald-100/80">
                        {row.shared.length} shared
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {row.shared.map((tag) => (
                        <span key={`${row.label}-shared-${tag}`} className="max-w-full whitespace-normal break-words rounded-full border border-emerald-300/45 bg-emerald-300/14 px-2 py-0.5 text-xs font-semibold text-emerald-50">
                          {tag}
                        </span>
                      ))}
                      {row.baseOnly.map((tag) => (
                        <span key={`${row.label}-base-${tag}`} className="max-w-full whitespace-normal break-words rounded-full border border-amber-300/35 bg-amber-300/10 px-2 py-0.5 text-xs font-medium text-amber-50/90">
                          {tag}
                        </span>
                      ))}
                      {row.resultOnly.map((tag) => (
                        <span key={`${row.label}-result-${tag}`} className="max-w-full whitespace-normal break-words rounded-full border border-cyan-300/35 bg-cyan-300/10 px-2 py-0.5 text-xs font-medium text-cyan-50/90">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
})

export function RecommendationsPanel({
  recommendations,
  weights,
  selectedGame,
  onOpenSteam,
  onRecommendationFeedback,
}: RecommendationsPanelProps) {
  const [visibleCount, setVisibleCount] = useState(8)
  const [showFeedbackToast, showFeedbackSavedToast] = useTimedToast()
  const visibleRecommendations = recommendations.slice(0, visibleCount)
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
  const handleFeedback = (game: RecommendedGame, rank: number, feedback: "up" | "down") => {
    showFeedbackSavedToast()
    onRecommendationFeedback?.(game, rank, feedback)
  }

  return (
    <div className="space-y-3">
      {showFeedbackToast ? (
        <div className="fixed bottom-6 left-1/2 z-[90] -translate-x-1/2 rounded-full border border-sky-200/30 bg-sky-950/92 px-4 py-2 text-sm font-semibold text-sky-50 shadow-[0_18px_42px_rgba(0,0,0,0.36)] backdrop-blur">
          Feedback saved!
        </div>
      ) : null}

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
              <p className="mt-1 text-base font-semibold text-slate-100">
                {recommendations.length} matches found!
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
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
        {visibleRecommendations.map((game, index) => (
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
            onFeedback={handleFeedback}
          />
            )
          })()
        ))}
      </div>

      {visibleCount < recommendations.length && (
        <div className="flex justify-center pt-2">
          <button
            onClick={() => setVisibleCount((current) => Math.min(current + 8, recommendations.length))}
            className="rounded-full border border-border bg-secondary/40 px-4 py-2 text-sm text-foreground transition-colors hover:bg-secondary/70"
          >
            Show More Results
          </button>
        </div>
      )}

      {recommendations.length === 0 && (
        <div className="panel p-8 text-center">
          <Target className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
          <span className="terminal-label block mb-1">No Matches Found</span>
          <p className="text-sm text-muted-foreground">Adjust filters or weights to find recommendations</p>
        </div>
      )}
    </div>
  )
}
