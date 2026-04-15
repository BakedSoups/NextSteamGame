"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight, Sliders, Puzzle, Sparkles, Grid3X3, Tag, Activity, Zap } from "lucide-react"
import type { Weights } from "@/lib/types"

interface ControlPanelProps {
  weights: Weights
  genreOptions: Weights["genres"]
  mode: "simple" | "advanced"
  onModeChange: (mode: "simple" | "advanced") => void
  onMatchWeightChange: (key: keyof Weights["match"], value: number) => void
  onContextWeightChange: (key: keyof Weights["context"], value: number) => void
  onAppealWeightChange: (key: keyof Weights["appeal"], value: number) => void
  onTagWeightChange: (context: keyof Weights["tags"], tag: string, value: number) => void
  onGenreToggle: (category: keyof Weights["genres"], genre: string) => void
  onSimpleIntentBoost: (intent: SimpleIntent) => void
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

export function ControlPanel({
  weights,
  genreOptions,
  mode,
  onModeChange,
  onMatchWeightChange,
  onContextWeightChange,
  onAppealWeightChange,
  onTagWeightChange,
  onGenreToggle,
  onSimpleIntentBoost,
}: ControlPanelProps) {
  const matchTotal = Object.values(weights.match).reduce((a, b) => a + b, 0)
  const contextTotal = Object.values(weights.context).reduce((a, b) => a + b, 0)

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
        <CollapsibleSection
          title="Quick Taste Shaping"
          icon={<Zap className="h-3.5 w-3.5" />}
          badge="Fast"
          defaultOpen={true}
        >
          <div className="space-y-4">
            <p className="text-[10px] text-muted-foreground">
              Click any intent to push the underlying scoring sliders without opening the full vector editor.
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
      )}

      {mode === "advanced" && (
        <>
      {/* Match Weighting */}
      <CollapsibleSection
        title="Match Weighting"
        icon={<Sliders className="h-3.5 w-3.5" />}
        badge={`${matchTotal}%`}
        defaultOpen={true}
      >
        <div className="space-y-3">
          {(Object.keys(weights.match) as (keyof Weights["match"])[]).map(key => (
            <WeightSlider
              key={key}
              label={key}
              value={weights.match[key]}
              onChange={(value) => onMatchWeightChange(key, value)}
            />
          ))}
          {matchTotal !== 100 && (
            <p className="text-[10px] text-destructive flex items-center gap-1">
              <span className="status-dot-red" />
              Weights should sum to 100%
            </p>
          )}
        </div>
      </CollapsibleSection>

      {/* Context Weighting */}
      <CollapsibleSection
        title="Vector Context Weighting"
        icon={<Puzzle className="h-3.5 w-3.5" />}
        badge={`${contextTotal}%`}
        defaultOpen={false}
      >
        <div className="space-y-3">
          {(Object.keys(weights.context) as (keyof Weights["context"])[]).map(key => (
            <WeightSlider
              key={key}
              label={key}
              value={weights.context[key]}
              onChange={(value) => onContextWeightChange(key, value)}
              color="accent"
            />
          ))}
        </div>
      </CollapsibleSection>

      {/* Appeal Axes */}
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

      {/* Genre Tree */}
      <CollapsibleSection
        title="Genre Tree"
        icon={<Grid3X3 className="h-3.5 w-3.5" />}
        badge={`${weights.genres.primary.length + weights.genres.sub.length + weights.genres.sub_sub.length + weights.genres.traits.length}`}
        defaultOpen={false}
      >
        <div className="space-y-4">
          {(Object.keys(genreOptions) as (keyof Weights["genres"])[]).map(category => (
            <div key={category}>
              <span className="terminal-label block mb-2 capitalize">
                {category.replace(/_/g, " ")}
              </span>
              <div className="flex flex-wrap gap-1">
                {genreOptions[category].map(genre => {
                  const isSelected = weights.genres[category].includes(genre)
                  return (
                    <button
                      key={genre}
                      onClick={() => onGenreToggle(category, genre)}
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

      {/* Tag Weighting - Advanced */}
      <CollapsibleSection
        title="Tag Weighting"
        icon={<Tag className="h-3.5 w-3.5" />}
        badge="Advanced"
        defaultOpen={false}
      >
        <div className="space-y-4">
          <p className="text-[10px] text-muted-foreground mb-2">
            Per-context tag weight distribution
          </p>
          {(Object.keys(weights.tags) as (keyof Weights["tags"])[]).map(context => (
            <div key={context} className="bg-secondary/30 rounded p-2 border border-border/50">
              <span className="terminal-label text-primary block mb-2 capitalize">
                {context.replace(/_/g, " ")}
              </span>
              <div className="space-y-2">
                {Object.entries(weights.tags[context]).map(([tag, value]) => (
                  <WeightSlider
                    key={tag}
                    label={tag}
                    value={value}
                    onChange={(nextValue) => onTagWeightChange(context, tag, nextValue)}
                    color={context === "music" ? "accent" : "primary"}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </CollapsibleSection>
        </>
      )}
    </div>
  )
}
