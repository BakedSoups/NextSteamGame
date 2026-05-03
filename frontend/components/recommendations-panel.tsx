"use client"

import { useState } from "react"
import Image from "next/image"
import { ChevronDown, ChevronUp, Radar, Zap, Target, AudioLines } from "lucide-react"
import type { Game, RecommendedGame, Weights } from "@/lib/types"
import { MATCH_LABELS } from "@/lib/score-labels"

const VECTOR_CONTEXT_KEYS: Array<keyof RecommendedGame["contextScores"]> = [
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

interface RecommendationsPanelProps {
  recommendations: RecommendedGame[]
  weights: Weights
  selectedGame: Game | null
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
    <div className="mx-auto w-[168px]">
      <svg viewBox="0 0 160 160" className="h-[168px] w-[168px] overflow-visible">
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
      <div className="mb-2 flex items-center justify-center gap-4 text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full border border-pink-300/80 bg-pink-300/20" />
          <span>Requested</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-sky-300" />
          <span>Matched</span>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        {axes.map((axis) => (
          <div key={axis} className="flex items-center justify-between rounded-full border border-white/8 bg-white/[0.03] px-2 py-1">
            <span>{axis.replace(/_/g, " ")}</span>
            <span className="text-foreground">{game.contextScores[axis].toFixed(1)}%</span>
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
}

function RecommendationCard({ game, rank, weights, selectedGame }: RecommendationCardProps) {
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
  const reasonChips = [
    ...(showIdentityMatches ? matchedTags.identity : []),
    ...(showSettingMatches ? matchedTags.setting : []),
    ...(showStructureMatches ? [...matchedTags.structure_loop, ...matchedTags.mechanics] : []),
    ...(showMusicMatches ? matchedTags.music : []),
  ].filter((tag, index, array) => array.indexOf(tag) === index).slice(0, 6)
  
  return (
    <div className="panel overflow-hidden hover:glow-box transition-all corner-brackets">
      {/* Header */}
      <a
        href={steamStoreUrl}
        target="_blank"
        rel="noreferrer"
        className="block border-b border-transparent transition-colors hover:bg-secondary/20"
        aria-label={`Open ${game.title} on Steam`}
      >
      <div className="flex gap-3 p-3">
        {/* Rank Badge & Image */}
        <div className="relative flex-shrink-0">
          <div className="rank-badge absolute -top-1 -left-1 z-10">
            #{rank}
          </div>
          <div className="w-24 h-16 rounded-xl overflow-hidden bg-muted border border-border">
            <Image
              src={cardImage}
              alt={game.title}
              width={96}
              height={64}
              className="object-cover w-full h-full"
              unoptimized
            />
          </div>
        </div>
        
        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              {logoImage ? (
                <div className="relative h-8 w-44 max-w-full">
                  <Image
                    src={logoImage}
                    alt={`${game.title} logo`}
                    fill
                    className="object-contain object-left"
                    unoptimized
                  />
                </div>
              ) : (
                <h4 className="text-sm font-medium text-foreground truncate">{game.title}</h4>
              )}
              <span className="tag-chip mt-1">{game.category}</span>
            </div>
            <div className="text-right flex-shrink-0">
              <div className="flex items-center gap-1">
                <Target className="h-3.5 w-3.5 text-accent" />
                <span className="text-lg font-bold text-accent glow-text-subtle">{(game.matchScore * 100).toFixed(0)}%</span>
              </div>
              <div className="flex items-center gap-1 terminal-label">
                <Zap className="h-2.5 w-2.5" />
                <span>x{game.confidence.toFixed(2)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      </a>

      {/* Mini Score Bars */}
      <div className="px-3 pb-2">
        {reasonChips.length > 0 && (
          <div className="mb-3">
            <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Why It Matches
            </div>
            <div className="flex flex-wrap gap-1.5">
              {reasonChips.map((tag) => (
                <span key={tag} className="tag-chip included">{tag}</span>
              ))}
            </div>
          </div>
        )}
        {selectedGame && (
          <div className="mb-3">
            <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Structural Overlap
            </div>
            <StructuralRadar game={game} weights={weights} />
          </div>
        )}
        <div className="flex gap-2">
          {[
            { key: "vector", value: scorePercentages.vector ?? game.scores.vector, weight: weights.match.vector },
            { key: "genre", value: scorePercentages.genre ?? game.scores.genre, weight: weights.match.genre },
            { key: "appeal", value: scorePercentages.appeal ?? game.scores.appeal, weight: weights.match.appeal },
            { key: "music", value: scorePercentages.music ?? game.scores.music, weight: weights.match.music }
          ].map(({ key, value, weight }) => (
            <div key={key} className="flex-1" title={`${MATCH_LABELS[key as keyof Weights["match"]]}: ${value.toFixed(1)}% (weight: ${weight}%)`}>
              <div className="progress-track mb-0.5">
                <div 
                  className="h-full rounded-full"
                  style={{ 
                    width: `${Math.min(value, 100)}%`,
                    opacity: 0.4 + (weight / 100) * 0.6,
                    background: MATCH_COLORS[key as keyof Weights["match"]],
                  }}
                />
              </div>
              <span className="terminal-label text-[8px] block text-center">{MATCH_LABELS[key as keyof Weights["match"]]}</span>
            </div>
          ))}
        </div>
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
              <span className="terminal-label text-primary">Score Contribution</span>
            </div>
            <div className="space-y-1.5">
              <ScoreBar label="Core Match" value={scorePercentages.vector ?? game.scores.vector} fillColor={MATCH_COLORS.vector} />
              <ScoreBar label="Genre" value={scorePercentages.genre ?? game.scores.genre} fillColor={MATCH_COLORS.genre} />
              <ScoreBar label="Appeal" value={scorePercentages.appeal ?? game.scores.appeal} fillColor={MATCH_COLORS.appeal} />
              <ScoreBar label="Music" value={scorePercentages.music ?? game.scores.music} fillColor={MATCH_COLORS.music} />
            </div>
          </div>

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

          {/* Structural Scan */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <AudioLines className="h-3 w-3 text-accent" />
              <span className="terminal-label text-accent">Structural Scan</span>
            </div>
            <StructuralRadar game={game} weights={weights} />
          </div>

          <div>
            <span className="terminal-label block mb-2 text-accent">Tag Signal Match</span>
            <div className="space-y-1.5">
              {TAG_SIGNAL_KEYS.map((key) => (
                <ScoreBar key={key} label={key} value={game.contextScores[key]} max={30} color="accent" />
              ))}
            </div>
          </div>

          {/* Genres */}
          <div>
            <span className="terminal-label block mb-2">Genre Classification</span>
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
            <span className="terminal-label block mb-2">Identity & Setting</span>
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
      )}
    </div>
  )
}

export function RecommendationsPanel({ recommendations, weights, selectedGame }: RecommendationsPanelProps) {
  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="panel p-4 glow-box">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Radar className="h-5 w-5 text-primary" />
              <div className="status-dot absolute -top-0.5 -right-0.5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-foreground">Analysis Results</h2>
              <p className="terminal-label">{recommendations.length} matches processed</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="terminal-label">Sorted by</span>
            <span className="data-value bg-primary/10 px-2 py-0.5 rounded border border-primary/30">
              Match Score
            </span>
          </div>
        </div>
      </div>

      {/* Cards */}
      <div className="space-y-2">
        {recommendations.map((game, index) => (
          <RecommendationCard
            key={game.id}
            game={game}
            rank={index + 1}
            weights={weights}
            selectedGame={selectedGame}
          />
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
