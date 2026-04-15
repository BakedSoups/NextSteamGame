"use client"

import { useEffect, useMemo, useState } from "react"
import { ArrowLeft, ArrowRight } from "lucide-react"
import { SearchBar } from "@/components/search-bar"
import { SelectedGamePanel } from "@/components/selected-game-panel"
import { ControlPanel } from "@/components/control-panel"
import { RecommendationsPanel } from "@/components/recommendations-panel"
import { TagFilterPanel } from "@/components/tag-filter-panel"
import type { Game, RecommendedGame, TagFilters, Weights } from "@/lib/types"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"

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

type Screen = "search" | "profile" | "results"

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b))
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

function buildWeightsFromGame(game: Game): Weights {
  const liveWeights = game.weights ?? {}
  return {
    match: { ...DEFAULT_MATCH_WEIGHTS, ...(liveWeights.match ?? {}) },
    context: { ...DEFAULT_CONTEXT_WEIGHTS, ...(liveWeights.context ?? {}) },
    appeal: { ...DEFAULT_APPEAL_WEIGHTS, ...(liveWeights.appeal ?? {}) },
    tags: liveWeights.tags
      ? {
          mechanics: liveWeights.tags.mechanics ?? {},
          narrative: liveWeights.tags.narrative ?? {},
          vibe: liveWeights.tags.vibe ?? {},
          structure_loop: liveWeights.tags.structure_loop ?? {},
          uniqueness: liveWeights.tags.uniqueness ?? {},
          music: liveWeights.tags.music ?? {},
        }
      : buildTagWeights(game),
    genres: {
      primary: [...game.genres.primary],
      sub: [...game.genres.sub],
      sub_sub: [...game.genres.sub_sub],
      traits: [...game.genres.traits],
    },
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  })

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}

export default function GameRecommendationLab() {
  const [screen, setScreen] = useState<Screen>("search")
  const [controlMode, setControlMode] = useState<"simple" | "advanced">("simple")
  const [selectedGame, setSelectedGame] = useState<Game | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<Game[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [resultsLoading, setResultsLoading] = useState(false)
  const [resultsError, setResultsError] = useState<string | null>(null)
  const [rawRecommendations, setRawRecommendations] = useState<RecommendedGame[]>([])
  const [tagFilters, setTagFilters] = useState<TagFilters>({ include: [], exclude: [] })
  const [weights, setWeights] = useState<Weights>({
    match: DEFAULT_MATCH_WEIGHTS,
    context: DEFAULT_CONTEXT_WEIGHTS,
    appeal: DEFAULT_APPEAL_WEIGHTS,
    tags: {
      mechanics: {},
      narrative: {},
      vibe: {},
      structure_loop: {},
      uniqueness: {},
      music: {},
    },
    genres: {
      primary: [],
      sub: [],
      sub_sub: [],
      traits: [],
    },
  })

  useEffect(() => {
    const query = searchQuery.trim()
    if (!query) {
      setSearchResults([])
      setSearchError(null)
      setSearchLoading(false)
      return
    }

    const timeoutId = window.setTimeout(async () => {
      try {
        setSearchLoading(true)
        setSearchError(null)
        const payload = await fetchJson<{ results: Game[] }>(`/api/search?q=${encodeURIComponent(query)}`)
        setSearchResults(payload.results)
      } catch (error) {
        setSearchError(error instanceof Error ? error.message : "Search failed")
      } finally {
        setSearchLoading(false)
      }
    }, 180)

    return () => window.clearTimeout(timeoutId)
  }, [searchQuery])

  useEffect(() => {
    if (!selectedGame) {
      return
    }
    setWeights(buildWeightsFromGame(selectedGame))
    setTagFilters({ include: [], exclude: [] })
  }, [selectedGame])

  useEffect(() => {
    if (screen !== "results" || !selectedGame) {
      return
    }

    let cancelled = false

    async function loadRecommendations() {
      try {
        setResultsLoading(true)
        setResultsError(null)
        const payload = await fetchJson<{ results: RecommendedGame[] }>("/api/recommendations", {
          method: "POST",
          body: JSON.stringify({
            appid: selectedGame.id,
            weights,
            limit: 24,
          }),
        })
        if (!cancelled) {
          setRawRecommendations(payload.results)
        }
      } catch (error) {
        if (!cancelled) {
          setResultsError(error instanceof Error ? error.message : "Recommendation load failed")
        }
      } finally {
        if (!cancelled) {
          setResultsLoading(false)
        }
      }
    }

    loadRecommendations()

    return () => {
      cancelled = true
    }
  }, [screen, selectedGame, weights])

  const recommendations = useMemo(() => {
    let filtered = rawRecommendations

    if (tagFilters.include.length > 0) {
      filtered = filtered.filter((rec) => {
        const allTags = [
          ...rec.tags.mechanics,
          ...rec.tags.narrative,
          ...rec.tags.vibe,
          ...rec.tags.structure_loop,
          ...rec.tags.uniqueness,
          ...rec.tags.music,
        ].map((tag) => tag.toLowerCase())

        return tagFilters.include.every((tag) =>
          allTags.some((candidate) => candidate.includes(tag.toLowerCase())),
        )
      })
    }

    if (tagFilters.exclude.length > 0) {
      filtered = filtered.filter((rec) => {
        const allTags = [
          ...rec.tags.mechanics,
          ...rec.tags.narrative,
          ...rec.tags.vibe,
          ...rec.tags.structure_loop,
          ...rec.tags.uniqueness,
          ...rec.tags.music,
        ].map((tag) => tag.toLowerCase())

        return !tagFilters.exclude.some((tag) =>
          allTags.some((candidate) => candidate.includes(tag.toLowerCase())),
        )
      })
    }

    return filtered
  }, [rawRecommendations, tagFilters])

  const genreOptions = useMemo<Weights["genres"]>(() => {
    const sourceGames = selectedGame ? [selectedGame, ...recommendations] : recommendations
    return {
      primary: uniqueSorted(sourceGames.flatMap((game) => game.genres.primary)),
      sub: uniqueSorted(sourceGames.flatMap((game) => game.genres.sub)),
      sub_sub: uniqueSorted(sourceGames.flatMap((game) => game.genres.sub_sub)),
      traits: uniqueSorted(sourceGames.flatMap((game) => game.genres.traits)),
    }
  }, [selectedGame, recommendations])

  const tagOptions = useMemo<Record<string, string[]>>(() => {
    const sourceGames = selectedGame ? [selectedGame, ...recommendations] : recommendations
    return {
      mechanics: uniqueSorted(sourceGames.flatMap((game) => game.tags.mechanics)),
      narrative: uniqueSorted(sourceGames.flatMap((game) => game.tags.narrative)),
      vibe: uniqueSorted(sourceGames.flatMap((game) => game.tags.vibe)),
      structure_loop: uniqueSorted(sourceGames.flatMap((game) => game.tags.structure_loop)),
      uniqueness: uniqueSorted(sourceGames.flatMap((game) => game.tags.uniqueness)),
      music: uniqueSorted(sourceGames.flatMap((game) => game.tags.music)),
    }
  }, [selectedGame, recommendations])

  const handleSelectGame = async (game: Game) => {
    try {
      const fullGame = await fetchJson<Game>(`/api/games/${game.id}`)
      setSelectedGame(fullGame)
      setScreen("profile")
      setSearchError(null)
    } catch (error) {
      setSearchError(error instanceof Error ? error.message : "Failed to load game")
    }
  }

  const updateMatchWeight = (key: keyof Weights["match"], value: number) => {
    setWeights((prev) => {
      const others = Object.keys(prev.match).filter((k) => k !== key) as (keyof Weights["match"])[]
      const remaining = 100 - value
      const otherTotal = others.reduce((sum, k) => sum + prev.match[k], 0)

      const newMatch = { ...prev.match, [key]: value }
      if (otherTotal > 0) {
        others.forEach((k) => {
          newMatch[k] = Math.max(0, Math.round((prev.match[k] / otherTotal) * remaining))
        })
      }

      const total = Object.values(newMatch).reduce((a, b) => a + b, 0)
      if (total !== 100 && others.length > 0) {
        const largestKey = others.reduce((a, b) => (newMatch[a] > newMatch[b] ? a : b))
        newMatch[largestKey] += 100 - total
      }

      return { ...prev, match: newMatch }
    })
  }

  const updateContextWeight = (key: keyof Weights["context"], value: number) => {
    setWeights((prev) => {
      const others = Object.keys(prev.context).filter((k) => k !== key) as (keyof Weights["context"])[]
      const remaining = 100 - value
      const otherTotal = others.reduce((sum, k) => sum + prev.context[k], 0)

      const newContext = { ...prev.context, [key]: value }
      if (otherTotal > 0) {
        others.forEach((k) => {
          newContext[k] = Math.max(0, Math.round((prev.context[k] / otherTotal) * remaining))
        })
      }

      const total = Object.values(newContext).reduce((a, b) => a + b, 0)
      if (total !== 100 && others.length > 0) {
        const largestKey = others.reduce((a, b) => (newContext[a] > newContext[b] ? a : b))
        newContext[largestKey] += 100 - total
      }

      return { ...prev, context: newContext }
    })
  }

  const updateAppealWeight = (key: keyof Weights["appeal"], value: number) => {
    setWeights((prev) => ({
      ...prev,
      appeal: { ...prev.appeal, [key]: value },
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
      | "more_competitive",
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
    setWeights((prev) => {
      const current = prev.genres[category]
      const updated = current.includes(genre)
        ? current.filter((g) => g !== genre)
        : [...current, genre]
      return { ...prev, genres: { ...prev.genres, [category]: updated } }
    })
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="mx-auto max-w-[1800px] px-6 py-4">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold text-foreground tracking-tight">Recommendation Lab</h1>
            </div>

            <div className="flex-1" />

            <div className="flex items-center gap-3">
              <button
                onClick={() => setScreen("search")}
                className="inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 text-sm text-foreground hover:bg-secondary/30"
              >
                Home
              </button>
              <div className="hidden lg:flex items-center gap-3 text-sm text-muted-foreground">
                <span>{searchResults.length} live matches</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1800px] px-6 py-8">
        {screen === "search" && (
          <div className="flex min-h-[70vh] items-center justify-center">
            <div className="w-full max-w-3xl text-center">
              <h1 className="text-5xl font-semibold tracking-tight text-foreground md:text-6xl">
                NextSteamGame!
              </h1>
              <p className="mx-auto mt-5 max-w-2xl text-base text-muted-foreground md:text-lg">
                find games based on a game you love and find your taste in video games on the way
              </p>
              <div className="mx-auto mt-10 max-w-2xl">
                <SearchBar
                  games={searchResults}
                  isLoading={searchLoading}
                  onQueryChange={setSearchQuery}
                  onSelect={handleSelectGame}
                  selectedGame={selectedGame}
                />
              </div>
              {searchError && <p className="mt-4 text-sm text-destructive">{searchError}</p>}
            </div>
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
                <div className="text-[11px] font-medium uppercase tracking-[0.25em] text-muted-foreground">Step 2</div>
                <h2 className="mt-3 text-2xl font-semibold text-foreground">Shape the live game profile</h2>
                <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
                  These controls are now reading the actual selected game payload from the API, including its real vector tags and soundtrack tags.
                </p>
              </div>

              <ControlPanel
                weights={weights}
                genreOptions={genreOptions}
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
                tagOptions={tagOptions}
                onFiltersChange={setTagFilters}
              />
            </div>

            <div className="space-y-4">
              {resultsError && <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">{resultsError}</div>}
              {resultsLoading && (
                <div className="rounded-xl border border-border bg-card/60 p-4 text-sm text-muted-foreground">
                  Loading recommendations from the live backend...
                </div>
              )}
              <RecommendationsPanel recommendations={recommendations} weights={weights} />
            </div>

            <div className="xl:sticky xl:top-24 xl:h-fit xl:max-h-[calc(100vh-7rem)] xl:overflow-y-auto custom-scrollbar pl-2">
              <div className="mb-4 rounded-2xl border border-border bg-card/60 p-4">
                <div className="text-[11px] font-medium uppercase tracking-[0.25em] text-muted-foreground">Step 3</div>
                <div className="mt-2 text-lg font-semibold text-foreground">Refine the live results</div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Adjusting these controls re-queries the recommendation API using the real game profile and retrieval pipeline.
                </p>
              </div>
              <ControlPanel
                weights={weights}
                genreOptions={genreOptions}
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
