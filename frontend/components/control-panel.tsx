"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight, Puzzle, Sparkles, Grid3X3, Activity, Zap } from "lucide-react"
import type { Game, Weights } from "@/lib/types"

interface ControlPanelProps {
  selectedGame: Game | null
  weights: Weights
  genreOptions: Weights["genres"]
  featuredTags: Array<{
    context: keyof Weights["tags"]
    label: string
    tags: string[]
  }>
  mode: "simple" | "advanced"
  onModeChange: (mode: "simple" | "advanced") => void
  onMatchWeightChange: (key: keyof Weights["match"], value: number) => void
  onContextWeightChange: (key: keyof Weights["context"], value: number) => void
  onAppealWeightChange: (key: keyof Weights["appeal"], value: number) => void
  onTagWeightChange: (context: keyof Weights["tags"], tag: string, value: number) => void
  onGenreToggle: (category: keyof Weights["genres"], genre: string) => void
  onSimpleIntentBoost: (intent: SimpleIntent) => void
  selectedSimpleTags: string[]
  onSimpleTagToggle: (context: keyof Weights["tags"], tag: string) => void
}

type SimpleIntent =
  | "mechanics"
  | "narrative"
  | "vibe"
  | "structure_loop"
  | "uniqueness"
  | "music"
  | "more_similar"
  | "more_surprising"
  | "more_story"
  | "more_competitive"

const SIMPLE_INTENTS: { key: SimpleIntent; label: string; hint: string }[] = [
  { key: "mechanics", label: "Mechanics", hint: "Lean harder into systems and verbs" },
  { key: "narrative", label: "Narrative", hint: "Push story and character presence" },
  { key: "vibe", label: "Vibe", hint: "Favor mood, tone, and atmosphere" },
  { key: "structure_loop", label: "Structure", hint: "Emphasize the core repeatable loop" },
  { key: "uniqueness", label: "Uniqueness", hint: "Bias toward unusual traits" },
  { key: "music", label: "Music", hint: "Give soundtrack and sonic identity more pull" },
  { key: "more_similar", label: "More Similar", hint: "Tighten the match around close neighbors" },
  { key: "more_surprising", label: "More Surprising", hint: "Loosen genre and reward novelty" },
  { key: "more_story", label: "More Story", hint: "Raise narrative focus and story signals" },
  { key: "more_competitive", label: "More Competitive", hint: "Bias toward pace, challenge, and intensity" },
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
  uniqueness: { stat: "BIZARRE", accent: "#fcd34d", glow: "rgba(252, 211, 77, 0.28)" },
  music: { stat: "RHYTHM", accent: "#f9a8d4", glow: "rgba(249, 168, 212, 0.3)" },
}

const GENRE_LEVELS: Array<{
  key: keyof Weights["genres"]
  label: string
  single: boolean
}> = [
  { key: "primary", label: "Primary Genre", single: true },
  { key: "sub", label: "Genre", single: true },
  { key: "sub_sub", label: "Sub-Genre", single: true },
  { key: "traits", label: "Traits", single: false },
]

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
        {badge && <span className="ml-auto data-value text-[10px]">{badge}</span>}
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
}

function WeightSlider({ label, value, onChange, max = 100, color = "primary", showPercentage = true }: WeightSliderProps) {
  const percentage = (value / max) * 100
  const thumbClass = color === "accent"
    ? "border-accent/70 bg-accent/15 shadow-[0_0_10px_var(--glow-green)]"
    : "border-primary/70 bg-primary/15 shadow-[0_0_10px_var(--glow-cyan)]"
  
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="terminal-label capitalize">{label.replace(/_/g, " ")}</span>
        <span className="data-value text-xs">
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
              style={{ width: `${percentage}%` }}
            />
            <div
              className={`absolute top-1/2 h-3 w-3 -translate-y-1/2 -translate-x-1/2 rounded-full border ${thumbClass}`}
              style={{ left: `${percentage}%` }}
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

interface VectorRadarCardProps {
  context: keyof Weights["tags"]
  label: string
  selectedGame: Game | null
  weights: Weights
  onContextWeightChange: (key: keyof Weights["context"], value: number) => void
  onTagWeightChange: (context: keyof Weights["tags"], tag: string, value: number) => void
  interactive?: boolean
}

function polarPoint(index: number, total: number, radius: number) {
  const angle = (-Math.PI / 2) + (index / total) * Math.PI * 2
  return {
    x: 80 + Math.cos(angle) * radius,
    y: 80 + Math.sin(angle) * radius,
  }
}

function VectorRadarCard({
  context,
  label,
  selectedGame,
  weights,
  onContextWeightChange,
  onTagWeightChange,
  interactive = true,
}: VectorRadarCardProps) {
  const visual = CONTEXT_VISUALS[context]
  const selectedTags = selectedGame?.tags[context] ?? []
  const fallbackTags = Object.entries(weights.tags[context])
    .sort((a, b) => b[1] - a[1])
    .map(([tag]) => tag)
  const axes = Array.from(new Set([...selectedTags, ...fallbackTags])).slice(0, 6)
  const axisLabels = axes.length > 0 ? axes : ["signal", "profile", "tone", "focus", "identity"]
  const values = axisLabels.map((axis) => Math.max(6, weights.tags[context][axis] ?? 12))
  const polygon = values
    .map((value, index) => {
      const point = polarPoint(index, values.length, 14 + (value / 100) * 42)
      return `${point.x},${point.y}`
    })
    .join(" ")
  const contextWeight = weights.context[context]
  const topTags = axisLabels.slice(0, 5)

  return (
    <div
      className="rounded-[26px] border p-5 shadow-[0_28px_80px_rgba(0,0,0,0.34)]"
      style={{
        borderColor: "rgba(255,255,255,0.08)",
        background: `linear-gradient(180deg, rgba(10,17,26,0.98), rgba(16,24,36,0.92)), radial-gradient(circle at top, ${visual.glow}, transparent 58%)`,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.32em]" style={{ color: visual.accent }}>
            {visual.stat}
          </div>
          <div className="mt-1 text-lg font-semibold text-white">{label}</div>
        </div>
        <div
          className="rounded-full border px-3 py-1 text-[11px] font-medium"
          style={{ borderColor: `${visual.accent}55`, color: visual.accent, backgroundColor: `${visual.accent}12` }}
        >
          {contextWeight}% pull
        </div>
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[220px_minmax(260px,1fr)]">
        <div className="relative mx-auto w-[200px] lg:mx-0">
          <svg viewBox="0 0 160 160" className="h-[180px] w-[180px] overflow-visible">
            {[22, 38, 54, 70].map((radius) => (
              <polygon
                key={radius}
                points={axisLabels.map((_, index) => {
                  const point = polarPoint(index, axisLabels.length, radius)
                  return `${point.x},${point.y}`
                }).join(" ")}
                fill="none"
                stroke="rgba(255,255,255,0.14)"
                strokeWidth="1"
              />
            ))}
            {axisLabels.map((_, index) => {
              const point = polarPoint(index, axisLabels.length, 76)
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
              points={polygon}
              fill={`${visual.accent}22`}
              stroke={visual.accent}
              strokeWidth="2.25"
              style={{ filter: `drop-shadow(0 0 10px ${visual.glow})` }}
            />
            {values.map((value, index) => {
              const point = polarPoint(index, values.length, 18 + (value / 100) * 52)
              return <circle key={`point-${index}`} cx={point.x} cy={point.y} r="2.75" fill={visual.accent} />
            })}
          </svg>
          {axisLabels.map((axis, index) => {
            const point = polarPoint(index, axisLabels.length, 96)
            return (
              <div
                key={`${axis}-label`}
                className="pointer-events-none absolute max-w-[96px] -translate-x-1/2 -translate-y-1/2 text-center text-[8px] leading-tight font-medium uppercase tracking-[0.12em] text-white/70"
                style={{ left: `${(point.x / 160) * 100}%`, top: `${(point.y / 160) * 100}%` }}
              >
                {axis.replace(/_/g, " ")}
              </div>
            )
          })}
        </div>

        <div className="space-y-3 min-w-0 pr-1">
          <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-3">
            <div className="text-[10px] uppercase tracking-[0.22em] text-white/45">
              {interactive ? "Influence readout" : "Live readout"}
            </div>
            <div className="mt-2 text-sm leading-6 text-white/82">
              {interactive ? (
                <>
                  The <span style={{ color: visual.accent }}>{label}</span> slider decides how much this vector matters in ranking.
                </>
              ) : (
                <>
                  <span style={{ color: visual.accent }}>{label}</span> reshapes live as you click simple-mode tags.
                </>
              )}
            </div>
          </div>
          {interactive ? (
            <>
              <WeightSlider
                label={`${label} influence`}
                value={contextWeight}
                onChange={(value) => onContextWeightChange(context, value)}
                color="accent"
              />
              <div className="space-y-2">
                {topTags.map((tag) => (
                  <WeightSlider
                    key={`${context}-${tag}`}
                    label={tag}
                    value={weights.tags[context][tag] ?? 0}
                    onChange={(value) => onTagWeightChange(context, tag, value)}
                    color={context === "music" ? "accent" : "primary"}
                  />
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-wrap gap-2">
              {topTags.map((tag) => (
                <span
                  key={`${context}-${tag}`}
                  className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-[10px] uppercase tracking-[0.12em] text-white/72"
                >
                  {tag.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function ControlPanel({
  selectedGame,
  weights,
  genreOptions,
  featuredTags,
  mode,
  onModeChange,
  onMatchWeightChange,
  onContextWeightChange,
  onAppealWeightChange,
  onTagWeightChange,
  onGenreToggle,
  onSimpleIntentBoost,
  selectedSimpleTags,
  onSimpleTagToggle,
}: ControlPanelProps) {
  const selectedSimpleLabels = selectedSimpleTags.map((entry) => {
    const [, ...tagParts] = entry.split(":")
    return tagParts.join(":")
  })

  return (
    <div className="space-y-3">
      {/* Active Formula Display */}
      <div className="panel p-3 glow-box">
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-3.5 h-3.5 text-primary" />
          <span className="terminal-label text-primary">Active Match Formula</span>
          <div className="ml-auto inline-flex rounded-full border border-border bg-secondary/40 p-0.5">
            <button
              onClick={() => onModeChange("simple")}
              className={`rounded-full px-2.5 py-1 text-[10px] transition-colors ${
                mode === "simple" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Simple
            </button>
            <button
              onClick={() => onModeChange("advanced")}
              className={`rounded-full px-2.5 py-1 text-[10px] transition-colors ${
                mode === "advanced" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Advanced
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 mb-3">
          {Object.entries(weights.match).map(([key, value]) => (
            <div key={key} className="flex items-center gap-1.5 px-2 py-1 bg-secondary rounded border border-border">
              <span className="terminal-label">{key}</span>
              <span className="data-value text-xs">{value}%</span>
            </div>
          ))}
        </div>
        <div className="h-px bg-border mb-3" />
        <div className="flex flex-wrap gap-1">
          {Object.entries(weights.context).map(([key, value]) => (
            <span key={key} className="tag-chip text-[9px]">
              {key.replace(/_/g, " ")} {value}%
            </span>
          ))}
        </div>
      </div>

      {mode === "simple" && (
        <div className="space-y-3">
          <div className="grid gap-5 2xl:grid-cols-2">
            {(Object.keys(weights.tags) as (keyof Weights["tags"])[]).map((context) => (
              <VectorRadarCard
                key={`simple-${context}`}
                context={context}
                label={context.replace(/_/g, " ")}
                selectedGame={selectedGame}
                weights={weights}
                onContextWeightChange={onContextWeightChange}
                onTagWeightChange={onTagWeightChange}
                interactive={false}
              />
            ))}
          </div>

          <CollapsibleSection
            title="Selected Words"
            icon={<Activity className="h-3.5 w-3.5" />}
            badge={selectedSimpleLabels.length > 0 ? String(selectedSimpleLabels.length) : "None"}
            defaultOpen={true}
          >
            {selectedSimpleLabels.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {selectedSimpleLabels.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-primary/40 bg-primary/12 px-3 py-1.5 text-xs text-foreground shadow-[0_0_10px_var(--glow-cyan)]"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-muted-foreground">
                Click words below and they will appear here while the radar shapes adjust live.
              </p>
            )}
          </CollapsibleSection>

          <CollapsibleSection
            title="What Do You Care About?"
            icon={<Zap className="h-3.5 w-3.5" />}
            badge="Tags"
            defaultOpen={true}
          >
            <div className="space-y-4">
              <p className="text-[10px] text-muted-foreground">
                Click the actual traits you care about. This pushes the real profile under the hood.
              </p>
              <div className="space-y-4">
                {featuredTags.map((group) => (
                  <div key={group.context}>
                    <div className="mb-2 text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                      {group.label}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {group.tags.map((tag) => {
                        const selectionKey = `${group.context}:${tag}`
                        const isSelected = selectedSimpleTags.includes(selectionKey)
                        return (
                        <button
                          key={selectionKey}
                          onClick={() => onSimpleTagToggle(group.context, tag)}
                          className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                            isSelected
                              ? "border-primary bg-primary/15 text-foreground shadow-[0_0_12px_var(--glow-cyan)]"
                              : "border-border bg-secondary/30 text-foreground hover:border-primary/60 hover:bg-secondary/60"
                          }`}
                        >
                          {tag}
                        </button>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CollapsibleSection>

          <CollapsibleSection
            title="Quick Taste Shaping"
            icon={<Zap className="h-3.5 w-3.5" />}
            badge="Fast"
            defaultOpen={false}
          >
            <div className="space-y-4">
              <p className="text-[10px] text-muted-foreground">
                Use broad presets if you want faster shaping before opening the full vector editor.
              </p>
              <div className="grid grid-cols-2 gap-2">
                {SIMPLE_INTENTS.map((intent) => (
                  <button
                    key={intent.key}
                    onClick={() => onSimpleIntentBoost(intent.key)}
                    className="rounded-2xl border border-border bg-secondary/30 px-3 py-2 text-left transition-colors hover:border-primary/60 hover:bg-secondary/60"
                  >
                    <div className="text-xs font-medium text-foreground">{intent.label}</div>
                    <div className="mt-1 text-[10px] text-muted-foreground">{intent.hint}</div>
                  </button>
                ))}
              </div>
            </div>
          </CollapsibleSection>
        </div>
      )}

      {mode === "advanced" && (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.18fr)_minmax(0,0.82fr)]">
          <div className="space-y-4 xl:sticky xl:top-24 xl:self-start">
            <div className="panel p-4 glow-box">
              <div className="flex items-center gap-2">
                <Puzzle className="h-4 w-4 text-primary" />
                <span className="terminal-label text-primary">Stand Stats</span>
              </div>
              <p className="mt-3 text-xs leading-6 text-muted-foreground">
                The left side is the selected game's vector silhouette. The right side is where you decide how strongly each vector and tag changes ranking.
              </p>
            </div>
            <div className="grid gap-5 2xl:grid-cols-2">
              {(Object.keys(weights.tags) as (keyof Weights["tags"])[]).map((context) => (
                <VectorRadarCard
                  key={context}
                  context={context}
                  label={context.replace(/_/g, " ")}
                  selectedGame={selectedGame}
                  weights={weights}
                  onContextWeightChange={onContextWeightChange}
                  onTagWeightChange={onTagWeightChange}
                />
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div className="panel p-4 glow-box-subtle">
              <div className="text-[10px] uppercase tracking-[0.3em] text-primary">How Influence Works</div>
              <p className="mt-3 text-sm leading-7 text-foreground/88">
                `Mechanics influence` means how much the mechanics vector contributes to the final recommendation score.
                Raise it when you want system feel, verbs, combat texture, and interaction style to matter more.
                Then use the mechanics tag sliders below to say which mechanics should define that shape.
              </p>
            </div>

            <CollapsibleSection
              title="Appeal Axes"
              icon={<Sparkles className="h-3.5 w-3.5" />}
              badge="Preference"
              defaultOpen={false}
            >
              <div className="space-y-3">
                <p className="text-[10px] text-muted-foreground mb-2">
                  Preference intensity on each axis (0-100)
                </p>
                {(Object.keys(weights.appeal) as (keyof Weights["appeal"])[]).map(key => (
                  <WeightSlider
                    key={key}
                    label={key}
                    value={weights.appeal[key]}
                    onChange={(value) => onAppealWeightChange(key, value)}
                  />
                ))}
              </div>
            </CollapsibleSection>

            <CollapsibleSection
              title="Genre Tree"
              icon={<Grid3X3 className="h-3.5 w-3.5" />}
              badge={`${weights.genres.primary.length + weights.genres.sub.length + weights.genres.sub_sub.length + weights.genres.traits.length}`}
              defaultOpen={true}
            >
              <div className="space-y-4">
                <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-3">
                  <div className="text-[10px] uppercase tracking-[0.24em] text-white/45">Current path</div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-white/85">
                    <span>{weights.genres.primary[0] || "Primary"}</span>
                    <span className="text-white/28">→</span>
                    <span>{weights.genres.sub[0] || "Genre"}</span>
                    <span className="text-white/28">→</span>
                    <span>{weights.genres.sub_sub[0] || "Sub-Genre"}</span>
                  </div>
                </div>

                {GENRE_LEVELS.map(({ key, label, single }) => (
                  <div key={key}>
                    <div className="mb-2 flex items-center gap-2">
                      <span className="terminal-label block">{label}</span>
                      <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                        {single ? "Single Select" : "Multi Select"}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {genreOptions[key].map((genre) => {
                        const isSelected = weights.genres[key].includes(genre)
                        return (
                          <button
                            key={genre}
                            onClick={() => onGenreToggle(key, genre)}
                            className={`tag-chip cursor-pointer ${isSelected ? "included" : ""}`}
                          >
                            {genre}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </CollapsibleSection>

          </div>
        </div>
      )}
    </div>
  )
}
