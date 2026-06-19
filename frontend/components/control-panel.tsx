"use client"

import { useState } from "react"
import { ArrowRight, Check, ChevronDown, ChevronRight, Puzzle, Sparkles, Grid3X3, Activity, Zap } from "lucide-react"
import type { Game, Weights } from "@/lib/types"
import { MATCH_LABELS } from "@/lib/score-labels"

const VECTOR_CONTEXT_KEYS: Array<keyof Weights["tags"]> = [
  "mechanics",
  "narrative",
  "vibe",
  "structure_loop",
]

const TAG_SIGNAL_CONTEXT_KEYS: Array<keyof Weights["tags"]> = [
  "identity",
  "setting",
  "music",
]

interface ControlPanelProps {
  selectedGame: Game | null
  weights: Weights
  highlightedContexts?: Array<keyof Weights["tags"]>
  resultsCompact?: boolean
  featuredTags: Array<{
    context: keyof Weights["tags"]
    label: string
    tags: string[]
  }>
  mode: "simple" | "advanced"
  onMatchWeightChange: (key: keyof Weights["match"], value: number) => void
  onContextWeightChange: (key: keyof Weights["context"], value: number) => void
  onAppealWeightChange: (key: keyof Weights["appeal"], value: number) => void
  onTagWeightChange: (context: keyof Weights["tags"], tag: string, value: number) => void
  onSimpleIntentBoost: (intent: SimpleIntent) => void
  selectedSimpleTags: string[]
  onSimpleTagToggle: (context: keyof Weights["tags"], tag: string) => void
}

type SimpleIntent =
  | "more_similar"
  | "more_different"
  | "better_gameplay"
  | "more_story"
  | "stronger_atmosphere"
  | "more_distinctive"

const SIMPLE_INTENTS: { key: SimpleIntent; label: string; hint: string }[] = [
  { key: "more_similar", label: "More Like This", hint: "Stay closer to the base game's structure and feel" },
  { key: "more_different", label: "More Different", hint: "Loosen the match and allow more novelty" },
  { key: "better_gameplay", label: "Emphasize Gameplay", hint: "Shift the match toward systems, structure, and play feel" },
  { key: "more_story", label: "Focus on Story", hint: "Shift the match toward story, character presence, and narrative pull" },
  { key: "stronger_atmosphere", label: "Emphasize Atmosphere", hint: "Shift the match toward mood, tone, and overall feel" },
  { key: "more_distinctive", label: "Focus on Identity", hint: "Shift the match toward signature traits and standout identity" },
]

const SIMPLE_CORE_VECTOR_INTENTS: SimpleIntent[] = [
  "more_similar",
  "better_gameplay",
  "more_story",
  "stronger_atmosphere",
]

const SIMPLE_TAG_SIGNAL_INTENTS: SimpleIntent[] = [
  "more_different",
  "more_distinctive",
]

const CONTEXT_VISUALS: Record<
  keyof Weights["tags"],
  {
    stat: string
    accent: string
    glow: string
  }
> = {
  mechanics: { stat: "POWER", accent: "#7dd3fc", glow: "rgba(125, 211, 252, 0.35)" },
  narrative: { stat: "RESOLVE", accent: "#fda4af", glow: "rgba(253, 164, 175, 0.28)" },
  vibe: { stat: "AURA", accent: "#c4b5fd", glow: "rgba(196, 181, 253, 0.3)" },
  structure_loop: { stat: "PRECISION", accent: "#86efac", glow: "rgba(134, 239, 172, 0.28)" },
  identity: { stat: "SIGNAL", accent: "#fcd34d", glow: "rgba(252, 211, 77, 0.28)" },
  setting: { stat: "WORLD", accent: "#60a5fa", glow: "rgba(96, 165, 250, 0.28)" },
  music: { stat: "RHYTHM", accent: "#f9a8d4", glow: "rgba(249, 168, 212, 0.3)" },
}

const MATCH_VISUALS: Record<keyof Weights["match"], { label: string; fill: string; glow: string }> = {
  vector: { label: MATCH_LABELS.vector, fill: "#7dd3fc", glow: "rgba(125, 211, 252, 0.35)" },
  genre: { label: MATCH_LABELS.genre, fill: "#86efac", glow: "rgba(134, 239, 172, 0.3)" },
  appeal: { label: MATCH_LABELS.appeal, fill: "#fda4af", glow: "rgba(253, 164, 175, 0.3)" },
  music: { label: MATCH_LABELS.music, fill: "#fcd34d", glow: "rgba(252, 211, 77, 0.3)" },
}

const VECTOR_INFLUENCE_COLORS: Record<keyof Weights["context"], { fill: string; glow: string }> = {
  mechanics: { fill: "#7dd3fc", glow: "rgba(125, 211, 252, 0.35)" },
  narrative: { fill: "#c084fc", glow: "rgba(192, 132, 252, 0.30)" },
  vibe: { fill: "#2dd4bf", glow: "rgba(45, 212, 191, 0.30)" },
  structure_loop: { fill: "#f97316", glow: "rgba(249, 115, 22, 0.28)" },
  identity: { fill: "#fb7185", glow: "rgba(251, 113, 133, 0.30)" },
  setting: { fill: "#60a5fa", glow: "rgba(96, 165, 250, 0.30)" },
  music: { fill: "#fcd34d", glow: "rgba(252, 211, 77, 0.3)" },
}

const TAG_CONTEXT_ACCENTS: Record<keyof Weights["tags"], string> = {
  mechanics: "#7dd3fc",
  narrative: "#fda4af",
  vibe: "#2dd4bf",
  structure_loop: "#86efac",
  identity: "#fcd34d",
  setting: "#60a5fa",
  music: "#f9a8d4",
}

interface CollapsibleSectionProps {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
  defaultOpen?: boolean
  badge?: string
}

function CollapsibleSection({ title, icon, children, defaultOpen = true, badge }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  
  return (
    <div className="panel overflow-hidden glow-box-subtle">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full panel-header cursor-pointer hover:bg-secondary/30 transition-colors"
      >
        <div className="text-primary">{icon}</div>
        <span className="text-xs font-medium text-foreground">{title}</span>
        {badge && <span className="ml-auto data-value text-xs">{badge}</span>}
        {isOpen ? (
          <ChevronDown className="h-3.5 w-3.5 text-primary ml-2" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground ml-2" />
        )}
      </button>
      {isOpen && (
        <div className="p-3 border-t border-border/50">
          {children}
        </div>
      )}
    </div>
  )
}

interface WeightSliderProps {
  label: string
  value: number
  onChange: (value: number) => void
  max?: number
  color?: "primary" | "accent"
  showPercentage?: boolean
  fillColor?: string
  thumbColor?: string
}

function WeightSlider({
  label,
  value,
  onChange,
  max = 100,
  color = "primary",
  showPercentage = true,
  fillColor,
  thumbColor,
}: WeightSliderProps) {
  const percentage = (value / max) * 100
  const thumbClass = color === "accent"
    ? "border-accent/70 bg-accent/15 shadow-[0_0_10px_var(--glow-green)]"
    : "border-primary/70 bg-primary/15 shadow-[0_0_10px_var(--glow-cyan)]"
  
  return (
    <div className="space-y-1.5">
      <div className="flex items-start justify-between gap-2">
        <span className="terminal-label min-w-0 flex-1 pr-2 text-left normal-case tracking-[0.08em] break-words">
          {label.replace(/_/g, " ")}
        </span>
        <span className="data-value shrink-0 text-xs">
          {showPercentage ? `${value}%` : value}
        </span>
      </div>
      <div className="relative flex items-center gap-2">
        {/* Start dot */}
        <div className="w-1.5 h-1.5 rounded-sm bg-muted-foreground/30 flex-shrink-0" />
        
        {/* Slider track */}
        <div className="relative flex-1">
          <div className="progress-track overflow-visible">
            <div 
              className={color === "accent" ? "progress-fill-green" : "progress-fill"}
              style={fillColor ? { width: `${percentage}%`, background: fillColor } : { width: `${percentage}%` }}
            />
            <div
              className={`absolute top-1/2 h-3 w-3 -translate-y-1/2 -translate-x-1/2 rounded-full border ${thumbClass}`}
              style={thumbColor ? { left: `${percentage}%`, borderColor: thumbColor, backgroundColor: `${thumbColor}22`, boxShadow: `0 0 10px ${thumbColor}` } : { left: `${percentage}%` }}
              aria-hidden="true"
            />
          </div>
          <input
            type="range"
            min={0}
            max={max}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
        </div>
      </div>
    </div>
  )
}

function SummaryVectorBar({ weights }: { weights: Weights["context"] }) {
  const segments = VECTOR_CONTEXT_KEYS.map((key) => ({
    key,
    label: key.replace(/_/g, " "),
    value: Math.max(0, weights[key]),
    color: VECTOR_INFLUENCE_COLORS[key].fill,
  }))
  const total = Math.max(segments.reduce((sum, segment) => sum + segment.value, 0), 1)
  let labelOffset = 0
  let barOffset = 0

  return (
    <div className="space-y-2">
      <div className="relative h-5">
        {segments.map((segment) => {
          const left = labelOffset
          labelOffset += (segment.value / total) * 100
          return (
            <div
              key={`label-${segment.key}`}
              className="absolute top-0 -translate-x-0 text-xs font-medium capitalize tracking-[0.08em] text-slate-100/92 whitespace-nowrap"
              style={{ left: `${Math.min(left, 94)}%` }}
            >
              {segment.label}
            </div>
          )
        })}
      </div>

      <div className="relative h-3 overflow-hidden rounded-full bg-white/[0.06]">
        {segments.map((segment) => {
          if (segment.value <= 0) {
            return null
          }
          const left = barOffset
          const width = (segment.value / total) * 100
          barOffset += width
          return (
            <div
              key={`bar-${segment.key}`}
              className="absolute inset-y-0"
              style={{
                left: `${left}%`,
                width: `${width}%`,
                backgroundColor: segment.color,
                boxShadow: `0 0 12px ${segment.color}`,
              }}
            />
          )
        })}
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs uppercase tracking-[0.12em] text-muted-foreground">
        {segments.map((segment) => (
          <div key={`meta-${segment.key}`} className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: segment.color }} />
            <span>{segment.label}</span>
            <span className="text-slate-200/88">{segment.value}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function PreferenceTagButton({
  context,
  tag,
  selected,
  onClick,
}: {
  context: keyof Weights["tags"]
  tag: string
  selected: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`preference-chip ${selected ? "selected" : ""}`}
    >
      <span
        className="preference-chip-marker"
        style={{
          backgroundColor: TAG_CONTEXT_ACCENTS[context],
          boxShadow: `0 0 10px ${TAG_CONTEXT_ACCENTS[context]}`,
        }}
        aria-hidden="true"
      />
      <span className="min-w-0 break-words leading-4">{tag}</span>
      <span className="preference-chip-icon" aria-hidden="true">
        {selected ? <Check className="h-3.5 w-3.5" /> : <ArrowRight className="h-3.5 w-3.5" />}
      </span>
    </button>
  )
}

interface VectorControlCardProps {
  context: keyof Weights["tags"]
  label: string
  selectedGame: Game | null
  weights: Weights
  visibleTags?: string[]
  onContextWeightChange: (key: keyof Weights["context"], value: number) => void
  onTagWeightChange: (context: keyof Weights["tags"], tag: string, value: number) => void
  interactive?: boolean
  highlighted?: boolean
}

function VectorControlCard({
  context,
  label,
  selectedGame,
  weights,
  visibleTags = [],
  onContextWeightChange,
  onTagWeightChange,
  interactive = true,
  highlighted = false,
}: VectorControlCardProps) {
  const visual = CONTEXT_VISUALS[context]
  const selectedTags = selectedGame?.tags[context] ?? []
  const allowSimpleTagShape =
    !interactive && VECTOR_CONTEXT_KEYS.includes(context as keyof Weights["context"])
  const baselineTagWeights = selectedTags.length > 0
    ? selectedTags.reduce<Record<string, number>>((acc, tag, index) => {
        const base = Math.floor(100 / selectedTags.length)
        const remainder = 100 - base * selectedTags.length
        acc[tag] = base + (index < remainder ? 1 : 0)
        return acc
      }, {})
    : {}
  const fallbackTags = Object.entries(weights.tags[context])
    .sort((a, b) => b[1] - a[1])
    .map(([tag]) => tag)
  const radarAxisLimit = 3
  const simpleVisibleAxes = visibleTags.slice(0, radarAxisLimit)
  const axes = interactive
    ? Array.from(new Set([...selectedTags, ...fallbackTags])).slice(0, radarAxisLimit)
    : simpleVisibleAxes.length > 0
      ? Array.from(new Set([...simpleVisibleAxes, ...selectedTags, ...fallbackTags])).slice(0, radarAxisLimit)
      : Array.from(new Set([...selectedTags, ...fallbackTags])).slice(0, radarAxisLimit)
  const axisLabels = axes.length > 0 ? axes : ["signal", "profile", "tone", "focus", "identity"]
  const contextWeight = weights.context[context]
  const values = axisLabels.map((axis) =>
    Math.max(
      0,
      interactive
        ? (weights.tags[context][axis] ?? 0)
        : allowSimpleTagShape
          ? Math.min(100, Math.max(weights.tags[context][axis] ?? 0, baselineTagWeights[axis] ?? 0))
          : Math.min(100, baselineTagWeights[axis] ?? 0),
    ),
  )
  const topTags = axisLabels.slice(0, 5)
  const weightedChips = axisLabels.map((axis, index) => ({ tag: axis, value: values[index] ?? 0 }))

  if (!interactive) {
    return (
      <div
        className="min-w-0 overflow-hidden rounded-[24px] border p-5 shadow-[0_28px_80px_rgba(0,0,0,0.28)]"
        style={{
          borderColor: highlighted ? `${visual.accent}88` : "rgba(255,255,255,0.08)",
          background: `linear-gradient(180deg, rgba(10,17,26,0.98), rgba(16,24,36,0.92)), radial-gradient(circle at top left, ${highlighted ? visual.glow.replace("0.", "0.5") : visual.glow}, transparent 56%)`,
          boxShadow: highlighted
            ? `0 0 0 1px ${visual.accent}55, 0 0 24px ${visual.glow}, 0 28px 80px rgba(0,0,0,0.28)`
            : "0 28px 80px rgba(0,0,0,0.28)",
        }}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-lg font-semibold text-white">{label}</div>
          </div>
          <div
            className="rounded-full border px-3 py-1 text-xs font-medium"
            style={{ borderColor: `${visual.accent}55`, color: visual.accent, backgroundColor: `${visual.accent}12` }}
          >
            {contextWeight}% pull
          </div>
        </div>

        <div className="mt-5 grid gap-2.5">
          {weightedChips.map(({ tag, value }) => {
            const strength = Math.max(8, Math.min(100, value))
            return (
              <label
                key={`${context}-${tag}`}
                className="group relative block min-h-[46px] cursor-ew-resize overflow-hidden rounded-2xl border bg-white/[0.035] px-3.5 py-2.5 transition-colors hover:bg-white/[0.06]"
                style={{
                  borderColor: `${visual.accent}4d`,
                }}
              >
                <div
                  className="absolute inset-y-0 left-0 rounded-2xl transition-[width] duration-500 ease-out"
                  style={{
                    width: `${strength}%`,
                    background: `linear-gradient(90deg, ${visual.accent}40, ${visual.accent}14)`,
                  }}
                />
                <div className="relative flex min-w-0 items-center justify-between gap-3">
                  <div className="min-w-0 truncate text-[12px] font-semibold text-slate-50">
                    {tag.replace(/_/g, " ")}
                  </div>
                  <div
                    className="shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold"
                    style={{ borderColor: `${visual.accent}55`, color: visual.accent, backgroundColor: `${visual.accent}12` }}
                  >
                    {Math.round(value)}
                  </div>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={Math.round(value)}
                  onChange={(event) => onTagWeightChange(context, tag, Number(event.target.value))}
                  className="absolute inset-0 h-full w-full cursor-ew-resize opacity-0"
                  aria-label={`${tag.replace(/_/g, " ")} weight`}
                />
              </label>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div
      className="min-w-0 overflow-hidden rounded-[24px] border p-5 shadow-[0_28px_80px_rgba(0,0,0,0.28)]"
      style={{
        borderColor: highlighted ? `${visual.accent}88` : "rgba(255,255,255,0.08)",
        background: `linear-gradient(180deg, rgba(10,17,26,0.98), rgba(16,24,36,0.92)), radial-gradient(circle at top left, ${highlighted ? visual.glow.replace("0.", "0.48") : visual.glow}, transparent 58%)`,
        boxShadow: highlighted
          ? `0 0 0 1px ${visual.accent}55, 0 0 24px ${visual.glow}, 0 28px 80px rgba(0,0,0,0.28)`
          : "0 28px 80px rgba(0,0,0,0.28)",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-lg font-semibold text-white">{label}</div>
        </div>
        <div
          className="rounded-full border px-3 py-1 text-xs font-medium"
          style={{ borderColor: `${visual.accent}55`, color: visual.accent, backgroundColor: `${visual.accent}12` }}
        >
          {contextWeight}% pull
        </div>
      </div>

      <div className="mt-5 min-w-0 space-y-3">
        <WeightSlider
          label={`${label} influence`}
          value={contextWeight}
          onChange={(value) => onContextWeightChange(context, value)}
          fillColor={VECTOR_INFLUENCE_COLORS[context].fill}
          thumbColor={VECTOR_INFLUENCE_COLORS[context].fill}
        />
        <div className="min-w-0 space-y-2">
          {topTags.map((tag) => (
            <WeightSlider
              key={`${context}-${tag}`}
              label={tag}
              value={weights.tags[context][tag] ?? 0}
              onChange={(value) => onTagWeightChange(context, tag, value)}
              fillColor={VECTOR_INFLUENCE_COLORS[context].fill}
              thumbColor={VECTOR_INFLUENCE_COLORS[context].fill}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function SignalTagMenus({
  groups,
  selectedSimpleTags,
  onSimpleTagToggle,
}: {
  groups: Array<{
    context: keyof Weights["tags"]
    label: string
    tags: string[]
  }>
  selectedSimpleTags: string[]
  onSimpleTagToggle: (context: keyof Weights["tags"], tag: string) => void
}) {
  return (
    <div className="space-y-5">
      <p className="text-base leading-6 text-slate-200/82">
        Click what you want to see most in the recommendations.
      </p>
      {groups.map((group) => {
        const selectedCount = group.tags.filter((tag) =>
          selectedSimpleTags.includes(`${group.context}:${tag}`),
        ).length

        return (
          <div key={`${group.context}-${group.label}`}>
            <div className="mb-2 flex items-center justify-between gap-3">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-200/82">
                {group.label}
              </div>
              <div className="rounded-full border border-amber-200/20 bg-amber-200/10 px-2 py-0.5 text-xs tracking-[0.12em] text-amber-100/85">
                {selectedCount > 0 ? `${selectedCount} active` : `${group.tags.length} tags`}
              </div>
            </div>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {group.tags.map((tag) => {
                const selectionKey = `${group.context}:${tag}`
                const isSelected = selectedSimpleTags.includes(selectionKey)
                return (
                  <button
                    key={selectionKey}
                    type="button"
                    onClick={() => onSimpleTagToggle(group.context, tag)}
                    aria-pressed={isSelected}
                    className={`signal-tag-button ${isSelected ? "selected" : ""}`}
                  >
                    <span className="min-w-0 break-words leading-4">{tag}</span>
                    <span className="ml-auto shrink-0" aria-hidden="true">
                      {isSelected ? <Check className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function ControlPanel({
  selectedGame,
  weights,
  highlightedContexts = [],
  resultsCompact = false,
  featuredTags,
  mode,
  onMatchWeightChange,
  onContextWeightChange,
  onAppealWeightChange,
  onTagWeightChange,
  onSimpleIntentBoost,
  selectedSimpleTags,
  onSimpleTagToggle,
}: ControlPanelProps) {
  const coreVectorIntents = SIMPLE_INTENTS.filter((intent) => SIMPLE_CORE_VECTOR_INTENTS.includes(intent.key))
  const tagSignalIntents = SIMPLE_INTENTS.filter((intent) => SIMPLE_TAG_SIGNAL_INTENTS.includes(intent.key))
  const vectorFeaturedGroups = featuredTags.filter((group) => VECTOR_CONTEXT_KEYS.includes(group.context))
  const signalFeaturedGroups = featuredTags.filter((group) => TAG_SIGNAL_CONTEXT_KEYS.includes(group.context))
  const activeSignalTags = Object.entries(weights.tags)
    .flatMap(([context, tagMap]) =>
      Object.entries(tagMap).map(([tag, value]) => ({
        key: `${context}:${tag}`,
        tag,
        value,
      })),
    )
    .filter((entry) => entry.value > 0)
    .sort((left, right) => right.value - left.value)
    .slice(0, 8)
    .map((entry) => entry.tag)
  const activeCoreVectors = VECTOR_CONTEXT_KEYS
    .filter((key) => weights.context[key] > 0)
    .sort((left, right) => weights.context[right] - weights.context[left])
    .slice(0, 4)
  const genrePathSummary = [weights.genres.primary[0], weights.genres.sub[0], weights.genres.sub_sub[0]]
    .filter(Boolean)
    .join(" → ")

  return (
    <div className="space-y-3">
      {mode === "advanced" && (
        <div className="panel p-3 glow-box">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-3.5 h-3.5 text-primary" />
            <span className="terminal-label text-primary">Your Search</span>
            <span className="ml-auto data-value text-xs">
              {mode === "advanced" ? "Advanced" : "Simple"}
            </span>
          </div>
          <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
            What You&apos;re Chasing
          </div>
          <div className="space-y-2">
            <p className="hidden text-[12px] leading-6 text-slate-100/90 xl:block">
              Vectors shape the kind of game structure you want. Tags tell the system which exact reasons to chase.
            </p>
            <div className="space-y-3">
              <div>
                <div className="mb-2 text-xs uppercase tracking-[0.22em] text-muted-foreground">
                  How This Game Feels
                </div>
                <div className="xl:hidden">
                  <p className="mb-4 text-[13px] leading-6 text-slate-100/90">
                    Slide what you want to prioritize, then tap tags below to refine the search.
                  </p>
                  <div className="space-y-4">
                    {VECTOR_CONTEXT_KEYS.map((context) => (
                      <WeightSlider
                        key={`mobile-summary-${context}`}
                        label={context.replace(/_/g, " ")}
                        value={weights.context[context]}
                        onChange={(value) => onContextWeightChange(context, value)}
                        fillColor={VECTOR_INFLUENCE_COLORS[context].fill}
                        thumbColor={VECTOR_INFLUENCE_COLORS[context].fill}
                      />
                    ))}
                  </div>
                </div>
                <div className="hidden xl:block">
                  <SummaryVectorBar weights={weights.context} />
                </div>
              </div>
              <div className="hidden xl:block">
                <div className="mb-2 text-xs uppercase tracking-[0.22em] text-muted-foreground">
                  Active Tags
                </div>
                {activeSignalTags.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {activeSignalTags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full border border-sky-200/70 bg-sky-300/20 px-3 py-1.5 text-xs font-semibold text-sky-50 shadow-[0_0_18px_rgba(56,189,248,0.24)]"
                      >
                        + {tag}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-white/10 bg-white/[0.035] px-3 py-2 text-xs text-slate-300/72">
                    No tags selected yet.
                  </div>
                )}
              </div>
            </div>
          </div>
          {mode === "advanced" && (genrePathSummary || weights.genres.traits.length > 0) && (
            <>
              <div className="h-px bg-border my-3" />
              <div className="space-y-2">
                {genrePathSummary && (
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    Genre Path: <span className="text-foreground">{genrePathSummary}</span>
                  </div>
                )}
                {weights.genres.traits.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {weights.genres.traits.map((trait) => (
                      <span key={trait} className="tag-chip text-xs">
                        {trait}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
          {mode === "advanced" && (
            <>
              <div className="h-px bg-border my-3" />
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    What Matters Most
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(Object.keys(weights.match) as (keyof Weights["match"])[]).map((key) => (
                      <div key={key} className="flex items-center gap-1.5 rounded-full border border-white/8 bg-white/[0.03] px-2.5 py-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: MATCH_VISUALS[key].fill, boxShadow: `0 0 10px ${MATCH_VISUALS[key].glow}` }}
                        />
                        <span>{MATCH_VISUALS[key].label}</span>
                        <span className="text-foreground">{weights.match[key]}%</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    How It Plays
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {VECTOR_CONTEXT_KEYS.map((key) => (
                      <div key={key} className="flex items-center gap-1.5 rounded-full border border-white/8 bg-white/[0.03] px-2.5 py-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{
                            backgroundColor: VECTOR_INFLUENCE_COLORS[key].fill,
                            boxShadow: `0 0 10px ${VECTOR_INFLUENCE_COLORS[key].glow}`,
                          }}
                        />
                        <span>{key.replace(/_/g, " ")}</span>
                        <span className="text-foreground">{weights.context[key]}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {resultsCompact && mode === "simple" && (
        <CollapsibleSection
          title="Quick Taste Shaping"
          icon={<span className="h-3.5 w-3.5" aria-hidden="true" />}
          defaultOpen={true}
        >
          <div className="space-y-4">
            <p className="text-xs leading-5 text-slate-100/88">
              Use a few broad presets to push the match in clearly different directions.
            </p>
            <div className="space-y-3">
              <div>
                <div className="mb-2 text-xs uppercase tracking-[0.22em] text-muted-foreground">
                  How It Plays
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {coreVectorIntents.map((intent) => (
                    <button
                      key={intent.key}
                      onClick={() => onSimpleIntentBoost(intent.key)}
                      className="rounded-2xl border border-white/12 bg-white/[0.06] px-3 py-2.5 text-left transition-colors hover:border-primary/60 hover:bg-white/[0.10]"
                    >
                      <div className="text-[13px] font-medium text-slate-50">{intent.label}</div>
                      <div className="mt-1 text-xs leading-5 text-slate-200/82">{intent.hint}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.22em] text-muted-foreground">
                    Broader Direction
                  </div>
                <div className="grid grid-cols-2 gap-2">
                  {tagSignalIntents.map((intent) => (
                    <button
                      key={intent.key}
                      onClick={() => onSimpleIntentBoost(intent.key)}
                      className="rounded-2xl border border-white/12 bg-white/[0.06] px-3 py-2.5 text-left transition-colors hover:border-primary/60 hover:bg-white/[0.10]"
                    >
                      <div className="text-[13px] font-medium text-slate-50">{intent.label}</div>
                      <div className="mt-1 text-xs leading-5 text-slate-200/82">{intent.hint}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </CollapsibleSection>
      )}

      {!resultsCompact && mode === "simple" && (
        <>
          <div className="space-y-4 xl:hidden">
            <div className="hidden">
              <div className="panel-header">
                <div className="text-primary">
                  <Zap className="h-3.5 w-3.5" />
                </div>
                <span className="text-xs font-medium text-foreground">Quick Direction</span>
              </div>
              <div className="border-t border-border/50 p-3">
                <div className="space-y-4">
                  <p className="text-[12px] leading-6 text-slate-100/90">
                    Pick the kind of match you want, then tap traits below to push the search toward the parts of this game you care about most.
                  </p>
                  <div className="grid gap-2">
                    {SIMPLE_INTENTS.map((intent) => (
                      <button
                        key={intent.key}
                        onClick={() => onSimpleIntentBoost(intent.key)}
                        className="rounded-2xl border border-sky-300/22 bg-sky-400/10 px-4 py-3.5 text-left shadow-[0_0_18px_rgba(56,189,248,0.08)] transition-colors hover:border-sky-300/55 hover:bg-sky-400/16"
                      >
                        <div className="text-[13px] font-semibold text-slate-50">{intent.label}</div>
                        <div className="mt-1 text-xs leading-5 text-slate-200/82">{intent.hint}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="panel overflow-hidden glow-box-subtle">
              <div className="panel-header">
                <div className="text-primary">
                  <Zap className="h-3.5 w-3.5" />
                </div>
                <span className="text-xs font-medium text-foreground">Theme / World Signals</span>
              </div>
              <div className="border-t border-border/50 p-3">
                <SignalTagMenus
                  groups={signalFeaturedGroups}
                  selectedSimpleTags={selectedSimpleTags}
                  onSimpleTagToggle={onSimpleTagToggle}
                />
              </div>
            </div>
          </div>

          <div className="hidden xl:block space-y-4">
            <div className="space-y-4">
              <div className="panel p-4 glow-box">
                <div className="flex items-center gap-2">
                  <Puzzle className="h-4 w-4 text-primary" />
                  <span className="terminal-label text-primary">Base Gameplay Shape</span>
                </div>
                <p className="mt-3 text-base leading-7 text-slate-100/90">
                  These are the default settings from the game you picked. Slide a bar if those are the reasons you like it, or keep scrolling for theme, world, and music signals.
                </p>
              </div>
              <div className="grid gap-5 2xl:grid-cols-2">
                {VECTOR_CONTEXT_KEYS.map((context) => (
                  <VectorControlCard
                    key={`simple-${context}`}
                    context={context}
                    label={context.replace(/_/g, " ")}
                    selectedGame={selectedGame}
                    weights={weights}
                    visibleTags={featuredTags.find((group) => group.context === context)?.tags ?? []}
                    onContextWeightChange={onContextWeightChange}
                    onTagWeightChange={onTagWeightChange}
                    interactive={false}
                    highlighted={highlightedContexts.includes(context)}
                  />
                ))}
              </div>
            </div>

            <div>
              <div className="panel overflow-hidden glow-box-subtle">
                <div className="panel-header">
                  <div className="text-primary">
                    <Zap className="h-3.5 w-3.5" />
                  </div>
                  <span className="text-xs font-medium text-foreground">Theme / World Signals</span>
                </div>
                <div className="border-t border-border/50 p-3">
                  <SignalTagMenus
                    groups={signalFeaturedGroups}
                    selectedSimpleTags={selectedSimpleTags}
                    onSimpleTagToggle={onSimpleTagToggle}
                  />
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {!resultsCompact && mode === "advanced" && (
        <>
          <div className="space-y-4 xl:hidden">
            <div className="panel p-4 glow-box">
              <div className="flex items-center gap-2">
                <Puzzle className="h-4 w-4 text-primary" />
                <span className="terminal-label text-primary">How It Plays</span>
              </div>
              <p className="mt-3 text-xs leading-6 text-muted-foreground">
                Adjust how much each gameplay dimension and theme should matter, without the chart-heavy desktop view.
              </p>
              <div className="mt-4">
                <SummaryVectorBar weights={weights.context} />
              </div>
            </div>

            <div className="panel overflow-hidden glow-box-subtle">
              <div className="panel-header">
                <div className="text-primary">
                  <Grid3X3 className="h-3.5 w-3.5" />
                </div>
                <span className="text-xs font-medium text-foreground">Active Reasons</span>
              </div>
              <div className="border-t border-border/50 p-3">
                <div className="flex flex-wrap gap-2">
                  {activeSignalTags.length > 0 ? activeSignalTags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full border border-sky-300/30 bg-sky-400/12 px-3 py-1.5 text-xs font-medium text-sky-50 shadow-[0_0_14px_rgba(56,189,248,0.16)]"
                    >
                      {tag}
                    </span>
                  )) : (
                    <p className="text-xs text-muted-foreground">
                      No active tags yet. Adjust weights below to shape the match.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="hidden xl:grid gap-4 xl:grid-cols-[minmax(0,1.18fr)_minmax(0,0.82fr)]">
            <div className="space-y-4 xl:sticky xl:top-24 xl:self-start">
              <div className="panel p-4 glow-box">
                <div className="flex items-center gap-2">
                  <Puzzle className="h-4 w-4 text-primary" />
                  <span className="terminal-label text-primary">How It Plays</span>
                </div>
                <p className="mt-3 text-xs leading-6 text-muted-foreground">
                  The left side shows the four gameplay dimensions. The right side lets you rebalance those dimensions and the themes layered on top of them.
                </p>
              </div>
              <div className="grid gap-5 2xl:grid-cols-2">
                {VECTOR_CONTEXT_KEYS.map((context) => (
                  <VectorControlCard
                    key={context}
                    context={context}
                    label={context.replace(/_/g, " ")}
                    selectedGame={selectedGame}
                    weights={weights}
                    onContextWeightChange={onContextWeightChange}
                    onTagWeightChange={onTagWeightChange}
                    highlighted={highlightedContexts.includes(context)}
                  />
                ))}
              </div>
            </div>

            <div className="space-y-4">
            <div className="panel p-4 glow-box-subtle">
              <div className="text-xs uppercase tracking-[0.3em] text-primary">How Influence Works</div>
              <p className="mt-3 text-sm leading-7 text-foreground/88">
                `Mechanics influence` means how much the mechanics vector contributes to the final recommendation score.
                Raise it when you want system feel, verbs, combat texture, and interaction style to matter more.
                Then use the mechanics tag sliders below to say which mechanics should define that shape.
              </p>
            </div>

            <div className="panel overflow-hidden glow-box-subtle">
              <div className="panel-header">
                <div className="text-primary">
                  <Zap className="h-3.5 w-3.5" />
                </div>
                <span className="text-xs font-medium text-foreground">What Matters Most</span>
                <span className="ml-auto data-value text-xs">Direct Control</span>
              </div>
              <div className="border-t border-border/50 p-3">
                <div className="space-y-3">
                  <p className="mb-2 text-xs text-muted-foreground">
                    This changes how much each ranking component contributes to the final recommendation score.
                  </p>
                  {(Object.keys(weights.match) as (keyof Weights["match"])[]).map((key) => (
                    <WeightSlider
                      key={key}
                      label={MATCH_VISUALS[key].label}
                      value={weights.match[key]}
                      onChange={(value) => onMatchWeightChange(key, value)}
                      fillColor={MATCH_VISUALS[key].fill}
                      thumbColor={MATCH_VISUALS[key].fill}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div className="panel overflow-hidden glow-box-subtle">
              <div className="panel-header">
                <div className="text-primary">
                  <Sparkles className="h-3.5 w-3.5" />
                </div>
                <span className="text-xs font-medium text-foreground">Play Style</span>
                <span className="ml-auto data-value text-xs">Preference</span>
              </div>
              <div className="border-t border-border/50 p-3">
                <div className="space-y-3">
                  <p className="mb-2 text-xs text-muted-foreground">
                    Preference intensity on each axis (0-100)
                  </p>
                  {(Object.keys(weights.appeal) as (keyof Weights["appeal"])[]).map((key) => (
                    <WeightSlider
                      key={key}
                      label={key}
                      value={weights.appeal[key]}
                      onChange={(value) => onAppealWeightChange(key, value)}
                    />
                  ))}
                </div>
              </div>
            </div>

            {activeSignalTags.length > 0 && (
              <div className="panel overflow-hidden glow-box-subtle">
                <div className="panel-header">
                  <div className="text-primary">
                    <Grid3X3 className="h-3.5 w-3.5" />
                  </div>
                  <span className="text-xs font-medium text-foreground">Active Reasons</span>
                  <span className="ml-auto data-value text-xs">Active Reasons</span>
                </div>
                <div className="border-t border-border/50 p-3">
                  <div className="flex flex-wrap gap-2">
                    {activeSignalTags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full border border-sky-300/30 bg-sky-400/12 px-3 py-1.5 text-xs font-medium text-sky-50 shadow-[0_0_14px_rgba(56,189,248,0.16)]"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div className="panel overflow-hidden glow-box-subtle">
              <div className="panel-header">
                <div className="text-primary">
                  <Grid3X3 className="h-3.5 w-3.5" />
                </div>
                <span className="text-xs font-medium text-foreground">How Strong Each Theme Is</span>
                <span className="ml-auto data-value text-xs">Theme / World / Music</span>
              </div>
              <div className="border-t border-border/50 p-3 space-y-5">
                {TAG_SIGNAL_CONTEXT_KEYS.map((context) => {
                  const tags = Object.entries(weights.tags[context])
                    .sort((left, right) => right[1] - left[1])
                    .slice(0, 5)
                  return (
                    <div key={context} className="space-y-3">
                      <WeightSlider
                        label={`${context.replace(/_/g, " ")} influence`}
                        value={weights.context[context]}
                        onChange={(value) => onContextWeightChange(context, value)}
                        color="accent"
                      />
                      {tags.length > 0 ? (
                        <div className="space-y-2">
                          {tags.map(([tag, value]) => (
                            <WeightSlider
                              key={`${context}-${tag}`}
                              label={tag}
                              value={value}
                              onChange={(next) => onTagWeightChange(context, tag, next)}
                              color="accent"
                            />
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          No active {context.replace(/_/g, " ")} tags on the selected game.
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
          </div>
        </>
      )}
    </div>
  )
}
