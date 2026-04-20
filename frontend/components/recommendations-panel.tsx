"use client"

import { useState } from "react"
import Image from "next/image"
import { ChevronDown, ChevronUp, Radar, Zap, Target, AudioLines } from "lucide-react"
import type { RecommendedGame, Weights } from "@/lib/types"
import { MATCH_LABELS } from "@/lib/score-labels"

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

interface RecommendationCardProps {
  game: RecommendedGame
  rank: number
  weights: Weights
}

function RecommendationCard({ game, rank, weights }: RecommendationCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const cardImage = game.assets.libraryCapsule || game.assets.capsuleV5 || game.image || IMAGE_FALLBACK
  const logoImage = game.assets.logo
  const scorePercentages = game.scorePercentages ?? {}
  
  return (
    <div className="panel overflow-hidden hover:glow-box transition-all corner-brackets">
      {/* Header */}
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

      {/* Mini Score Bars */}
      <div className="px-3 pb-2">
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
              <ScoreBar label="Gameplay" value={scorePercentages.vector ?? game.scores.vector} fillColor={MATCH_COLORS.vector} />
              <ScoreBar label="Genre" value={scorePercentages.genre ?? game.scores.genre} fillColor={MATCH_COLORS.genre} />
              <ScoreBar label="Appeal" value={scorePercentages.appeal ?? game.scores.appeal} fillColor={MATCH_COLORS.appeal} />
              <ScoreBar label="Music" value={scorePercentages.music ?? game.scores.music} fillColor={MATCH_COLORS.music} />
            </div>
          </div>

          {/* Context Breakdown */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <AudioLines className="h-3 w-3 text-accent" />
              <span className="terminal-label text-accent">Context Breakdown</span>
            </div>
            <div className="space-y-1.5">
              {Object.entries(game.contextScores).map(([key, value]) => (
                <ScoreBar key={key} label={key} value={value} max={30} color="accent" />
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

          {/* Soundtrack Tags */}
          <div>
            <span className="terminal-label block mb-2">Soundtrack Profile</span>
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

export function RecommendationsPanel({ recommendations, weights }: RecommendationsPanelProps) {
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
