"use client"

import { useEffect, useMemo, useState } from "react"
import { ArrowLeft, ArrowRight } from "lucide-react"
import { SearchBar } from "@/components/search-bar"
import { SelectedGamePanel } from "@/components/selected-game-panel"
import { ControlPanel } from "@/components/control-panel"
import { RecommendationsPanel } from "@/components/recommendations-panel"
import { TagFilterPanel } from "@/components/tag-filter-panel"
import { mockGames, mockRecommendations } from "@/lib/mock-data"
import type { Game, Weights, TagFilters } from "@/lib/types"

const DEFAULT_MATCH_WEIGHTS: Weights["match"] = {
  vector: 34,
  genre: 26,
  appeal: 22,
  music: 18,
}

const DEFAULT_CONTEXT_WEIGHTS: Weights["context"] = {
  mechanics: 33,
  narrative: 5,
  vibe: 9,
  structure_loop: 30,
  uniqueness: 13,
  music: 10,
}

const DEFAULT_APPEAL_WEIGHTS: Weights["appeal"] = {
  challenge: 50,
  complexity: 50,
  pace: 50,
  narrative_focus: 50,
  social_energy: 50,
  creativity: 50,
}

function normalizeToHundred(tags: string[]): Record<string, number> {
  if (tags.length === 0) {
    return {}
  }

  const base = Math.floor(100 / tags.length)
  const remainder = 100 - base * tags.length

  return tags.reduce<Record<string, number>>((acc, tag, index) => {
    acc[tag] = base + (index < remainder ? 1 : 0)
    return acc
  }, {})
}

function buildTagWeights(game: Game): Weights["tags"] {
  return {
    mechanics: normalizeToHundred(game.tags.mechanics),
    narrative: normalizeToHundred(game.tags.narrative),
    vibe: normalizeToHundred(game.tags.vibe),
    structure_loop: normalizeToHundred(game.tags.structure_loop),
    uniqueness: normalizeToHundred(game.tags.uniqueness),
    music: normalizeToHundred(game.tags.music),
  }
}

type Screen = "search" | "profile" | "results"

export default function GameRecommendationLab() {
  const [selectedGame, setSelectedGame] = useState<Game | null>(mockGames[0])
  const [tagFilters, setTagFilters] = useState<TagFilters>({ include: [], exclude: [] })
  const [controlMode, setControlMode] = useState<"simple" | "advanced">("simple")
  const [screen, setScreen] = useState<Screen>("search")
  const [weights, setWeights] = useState<Weights>({
    match: DEFAULT_MATCH_WEIGHTS,
    context: DEFAULT_CONTEXT_WEIGHTS,
    appeal: DEFAULT_APPEAL_WEIGHTS,
    tags: buildTagWeights(mockGames[0]),
    genres: mockGames[0].genres,
  })

  useEffect(() => {
    if (!selectedGame) {
      return
    }
    setWeights((prev) => ({
      ...prev,
      tags: buildTagWeights(selectedGame),
      genres: selectedGame.genres,
    }))
  }, [selectedGame])

  const recommendations = useMemo(() => {
    let filtered = mockRecommendations
    
    if (tagFilters.include.length > 0) {
      filtered = filtered.filter(rec => {
        const allTags = [
          ...rec.tags.mechanics,
          ...rec.tags.narrative,
          ...rec.tags.vibe,
          ...rec.tags.structure_loop,
          ...rec.tags.uniqueness,
          ...rec.tags.music
        ].map(t => t.toLowerCase())
        
        return tagFilters.include.every(tag => 
          allTags.some(t => t.includes(tag.toLowerCase()))
        )
      })
    }
    
    if (tagFilters.exclude.length > 0) {
      filtered = filtered.filter(rec => {
        const allTags = [
          ...rec.tags.mechanics,
          ...rec.tags.narrative,
          ...rec.tags.vibe,
          ...rec.tags.structure_loop,
          ...rec.tags.uniqueness,
          ...rec.tags.music
        ].map(t => t.toLowerCase())
        
        return !tagFilters.exclude.some(tag => 
          allTags.some(t => t.includes(tag.toLowerCase()))
        )
      })
    }
    
    return filtered.map(rec => ({
      ...rec,
      scores: {
        ...rec.scores,
        vector: rec.scores.vector * (weights.match.vector / DEFAULT_MATCH_WEIGHTS.vector),
        genre: rec.scores.genre * (weights.match.genre / DEFAULT_MATCH_WEIGHTS.genre),
        appeal: rec.scores.appeal * (weights.match.appeal / DEFAULT_MATCH_WEIGHTS.appeal),
        music: rec.scores.music * (weights.match.music / DEFAULT_MATCH_WEIGHTS.music)
      }
    })).sort((a, b) => {
      const aTotal = a.scores.vector + a.scores.genre + a.scores.appeal + a.scores.music
      const bTotal = b.scores.vector + b.scores.genre + b.scores.appeal + b.scores.music
      return bTotal - aTotal
    })
  }, [weights, tagFilters])

  const handleSelectGame = (game: Game) => {
    setSelectedGame(game)
    setScreen("profile")
  }

  const updateMatchWeight = (key: keyof Weights["match"], value: number) => {
    setWeights(prev => {
      const others = Object.keys(prev.match).filter(k => k !== key) as (keyof Weights["match"])[]
      const remaining = 100 - value
      const otherTotal = others.reduce((sum, k) => sum + prev.match[k], 0)
      
      const newMatch = { ...prev.match, [key]: value }
      if (otherTotal > 0) {
        others.forEach(k => {
          newMatch[k] = Math.max(0, Math.round((prev.match[k] / otherTotal) * remaining))
        })
      }
      
      const total = Object.values(newMatch).reduce((a, b) => a + b, 0)
      if (total !== 100) {
        const largestKey = others.reduce((a, b) => newMatch[a] > newMatch[b] ? a : b)
        newMatch[largestKey] += 100 - total
      }
      
      return { ...prev, match: newMatch }
    })
  }

  const updateContextWeight = (key: keyof Weights["context"], value: number) => {
    setWeights(prev => {
      const others = Object.keys(prev.context).filter(k => k !== key) as (keyof Weights["context"])[]
      const remaining = 100 - value
      const otherTotal = others.reduce((sum, k) => sum + prev.context[k], 0)
      
      const newContext = { ...prev.context, [key]: value }
      if (otherTotal > 0) {
        others.forEach(k => {
          newContext[k] = Math.max(0, Math.round((prev.context[k] / otherTotal) * remaining))
        })
      }
      
      const total = Object.values(newContext).reduce((a, b) => a + b, 0)
      if (total !== 100) {
        const largestKey = others.reduce((a, b) => newContext[a] > newContext[b] ? a : b)
        newContext[largestKey] += 100 - total
      }
      
      return { ...prev, context: newContext }
    })
  }

  const updateAppealWeight = (key: keyof Weights["appeal"], value: number) => {
    setWeights(prev => ({
      ...prev,
      appeal: { ...prev.appeal, [key]: value }
    }))
  }

  const applySimpleIntentBoost = (
    contextKey: keyof Weights["context"] | null,
    matchKey: keyof Weights["match"] | null,
    contextDelta = 12,
    matchDelta = 8,
    appealUpdates: Partial<Weights["appeal"]> = {},
  ) => {
    setWeights((prev) => {
      const next = {
        ...prev,
        match: { ...prev.match },
        context: { ...prev.context },
        appeal: { ...prev.appeal, ...appealUpdates },
      }

      if (contextKey) {
        const others = Object.keys(next.context).filter((key) => key !== contextKey) as (keyof Weights["context"])[]
        const target = Math.min(100, next.context[contextKey] + contextDelta)
        const remaining = 100 - target
        const otherTotal = others.reduce((sum, key) => sum + next.context[key], 0)
        next.context[contextKey] = target
        if (otherTotal > 0) {
          for (const key of others) {
            next.context[key] = Math.max(0, Math.round((prev.context[key] / otherTotal) * remaining))
          }
        }
        const total = Object.values(next.context).reduce((sum, value) => sum + value, 0)
        if (total !== 100 && others.length > 0) {
          const largestKey = others.reduce((a, b) => (next.context[a] > next.context[b] ? a : b))
          next.context[largestKey] += 100 - total
        }
      }

      if (matchKey) {
        const others = Object.keys(next.match).filter((key) => key !== matchKey) as (keyof Weights["match"])[]
        const target = Math.min(100, next.match[matchKey] + matchDelta)
        const remaining = 100 - target
        const otherTotal = others.reduce((sum, key) => sum + next.match[key], 0)
        next.match[matchKey] = target
        if (otherTotal > 0) {
          for (const key of others) {
            next.match[key] = Math.max(0, Math.round((prev.match[key] / otherTotal) * remaining))
          }
        }
        const total = Object.values(next.match).reduce((sum, value) => sum + value, 0)
        if (total !== 100 && others.length > 0) {
          const largestKey = others.reduce((a, b) => (next.match[a] > next.match[b] ? a : b))
          next.match[largestKey] += 100 - total
        }
      }

      return next
    })
  }

  const handleSimpleIntentBoost = (
    intent:
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
  ) => {
    switch (intent) {
      case "mechanics":
      case "narrative":
      case "vibe":
      case "structure_loop":
      case "uniqueness":
      case "music":
        applySimpleIntentBoost(intent, "vector")
        return
      case "more_similar":
        applySimpleIntentBoost("mechanics", "vector", 10, 10)
        return
      case "more_surprising":
        applySimpleIntentBoost("uniqueness", "music", 14, 8, { creativity: 70 })
        return
      case "more_story":
        applySimpleIntentBoost("narrative", "appeal", 14, 8, { narrative_focus: 80 })
        return
      case "more_competitive":
        applySimpleIntentBoost("mechanics", "genre", 10, 8, {
          challenge: 78,
          pace: 75,
          social_energy: 68,
        })
        return
    }
  }

  const updateTagWeight = (context: keyof Weights["tags"], tag: string, value: number) => {
    setWeights((prev) => {
      const currentContext = prev.tags[context]
      const others = Object.keys(currentContext).filter((key) => key !== tag)
      const remaining = 100 - value
      const otherTotal = others.reduce((sum, key) => sum + currentContext[key], 0)

      const nextContext = { ...currentContext, [tag]: value }
      if (others.length > 0 && otherTotal > 0) {
        for (const key of others) {
          nextContext[key] = Math.max(0, Math.round((currentContext[key] / otherTotal) * remaining))
        }
      }

      const total = Object.values(nextContext).reduce((sum, item) => sum + item, 0)
      if (total !== 100 && others.length > 0) {
        const largestKey = others.reduce((a, b) => (nextContext[a] > nextContext[b] ? a : b))
        nextContext[largestKey] += 100 - total
      }

      return {
        ...prev,
        tags: {
          ...prev.tags,
          [context]: nextContext,
        },
      }
    })
  }

  const toggleGenre = (category: keyof Weights["genres"], genre: string) => {
    setWeights(prev => {
      const current = prev.genres[category]
      const updated = current.includes(genre)
        ? current.filter(g => g !== genre)
        : [...current, genre]
      return { ...prev, genres: { ...prev.genres, [category]: updated } }
    })
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="mx-auto max-w-[1800px] px-6 py-4">
          <div className="flex items-center gap-8">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold text-foreground tracking-tight">Recommendation Lab</h1>
            </div>

            {/* Search */}
            <div className="flex-1 max-w-lg">
              <SearchBar 
                games={mockGames} 
                onSelect={handleSelectGame}
                selectedGame={selectedGame}
              />
            </div>

            {/* Status */}
            <div className="hidden lg:flex items-center gap-3 text-sm text-muted-foreground">
              <span>{mockGames.length} games indexed</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-[1800px] px-6 py-8">
        {screen === "search" && (
          <div className="mx-auto max-w-4xl rounded-[2rem] border border-border bg-card/60 px-8 py-12 shadow-[0_20px_80px_rgba(0,0,0,0.25)]">
            <div className="mx-auto max-w-3xl text-center">
              <div className="text-[11px] font-medium uppercase tracking-[0.3em] text-muted-foreground">
                Step 1
              </div>
              <h2 className="mt-4 text-4xl font-semibold tracking-tight text-foreground md:text-5xl">
                Find the game first
              </h2>
              <p className="mt-4 text-base text-muted-foreground md:text-lg">
                Start with the Steam game you want to use as the reference profile. Once you pick it, you’ll move to the tuning screen.
              </p>
            </div>
            <div className="mx-auto mt-10 max-w-2xl">
              <SearchBar
                games={mockGames}
                onSelect={handleSelectGame}
                selectedGame={selectedGame}
              />
            </div>
            {selectedGame && (
              <div className="mx-auto mt-10 max-w-2xl">
                <div className="rounded-2xl border border-border bg-secondary/20 p-5 text-left">
                  <div className="text-[11px] font-medium uppercase tracking-[0.25em] text-muted-foreground">
                    Selected
                  </div>
                  <div className="mt-2 text-xl font-semibold text-foreground">{selectedGame.title}</div>
                  <p className="mt-2 text-sm text-muted-foreground">{selectedGame.description}</p>
                  <button
                    onClick={() => setScreen("profile")}
                    className="mt-5 inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm text-primary-foreground"
                  >
                    Continue to Tuning
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {screen === "profile" && (
          <div className="grid grid-cols-1 gap-8 xl:grid-cols-[340px_minmax(0,1fr)]">
            <div className="space-y-6 xl:sticky xl:top-24 xl:h-fit">
              <button
                onClick={() => setScreen("search")}
                className="inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 text-sm text-foreground hover:bg-secondary/30"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to Search
              </button>
              <SelectedGamePanel game={selectedGame} />
            </div>

            <div className="space-y-6">
              <div className="rounded-3xl border border-border bg-card/60 p-6">
                <div className="text-[11px] font-medium uppercase tracking-[0.25em] text-muted-foreground">
                  Step 2
                </div>
                <h2 className="mt-3 text-2xl font-semibold text-foreground">Shape the game profile</h2>
                <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
                  Tune the match formula, context weighting, tags, genres, and appeal before you look at results.
                </p>
              </div>

              <ControlPanel
                weights={weights}
                mode={controlMode}
                onModeChange={setControlMode}
                onMatchWeightChange={updateMatchWeight}
                onContextWeightChange={updateContextWeight}
                onAppealWeightChange={updateAppealWeight}
                onTagWeightChange={updateTagWeight}
                onGenreToggle={toggleGenre}
                onSimpleIntentBoost={handleSimpleIntentBoost}
              />

              <div className="flex justify-end">
                <button
                  onClick={() => setScreen("results")}
                  className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm text-primary-foreground"
                >
                  See Results
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {screen === "results" && (
          <div className="grid grid-cols-1 gap-8 xl:grid-cols-[340px_1fr_360px]">
            <div className="space-y-6 xl:sticky xl:top-24 xl:h-fit xl:max-h-[calc(100vh-7rem)] xl:overflow-y-auto custom-scrollbar pr-2">
              <button
                onClick={() => setScreen("profile")}
                className="inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 text-sm text-foreground hover:bg-secondary/30"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to Tuning
              </button>
              <SelectedGamePanel game={selectedGame} />
              <TagFilterPanel
                filters={tagFilters}
                onFiltersChange={setTagFilters}
              />
            </div>

            <div>
              <RecommendationsPanel
                recommendations={recommendations}
                weights={weights}
              />
            </div>

            <div className="xl:sticky xl:top-24 xl:h-fit xl:max-h-[calc(100vh-7rem)] xl:overflow-y-auto custom-scrollbar pl-2">
              <div className="mb-4 rounded-2xl border border-border bg-card/60 p-4">
                <div className="text-[11px] font-medium uppercase tracking-[0.25em] text-muted-foreground">
                  Step 3
                </div>
                <div className="mt-2 text-lg font-semibold text-foreground">Refine the results</div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Keep adjusting simple or advanced controls here and the recommendation list will follow.
                </p>
              </div>
              <ControlPanel
                weights={weights}
                mode={controlMode}
                onModeChange={setControlMode}
                onMatchWeightChange={updateMatchWeight}
                onContextWeightChange={updateContextWeight}
                onAppealWeightChange={updateAppealWeight}
                onTagWeightChange={updateTagWeight}
                onGenreToggle={toggleGenre}
                onSimpleIntentBoost={handleSimpleIntentBoost}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
