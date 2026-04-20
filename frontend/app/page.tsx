"use client"

import { useEffect, useMemo, useState } from "react"
import { ArrowLeft, ArrowRight } from "lucide-react"
import steamLogo from "@/art_assets/Steam-Logo.png"
import gameShelfBackground from "@/art_assets/game_collection_background.webp"
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
type TagContextKey = keyof Weights["tags"]
type SimpleIntentKey =
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

function featuredTagGroups(game: Game | null): Array<{
  context: keyof Weights["tags"]
  label: string
  tags: string[]
}> {
  if (!game) {
    return []
  }

  return [
    { context: "uniqueness", label: "Signature", tags: game.tags.uniqueness.slice(0, 4) },
    { context: "vibe", label: "Mood", tags: game.tags.vibe.slice(0, 4) },
    { context: "mechanics", label: "Mechanics", tags: game.tags.mechanics.slice(0, 4) },
    { context: "music", label: "Sound", tags: game.tags.music.slice(0, 4) },
  ].filter((group) => group.tags.length > 0)
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

function simpleIntentHighlights(intent: SimpleIntentKey): TagContextKey[] {
  switch (intent) {
    case "mechanics":
      return ["mechanics"]
    case "narrative":
      return ["narrative"]
    case "vibe":
      return ["vibe"]
    case "structure_loop":
      return ["structure_loop"]
    case "uniqueness":
      return ["uniqueness"]
    case "music":
      return ["music"]
    case "more_similar":
      return ["mechanics", "structure_loop"]
    case "more_surprising":
      return ["uniqueness", "music"]
    case "more_story":
      return ["narrative"]
    case "more_competitive":
      return ["mechanics"]
  }
}

function reviewPositivePercent(game: RecommendedGame): number | null {
  const positive = game.reviewStats?.positive ?? 0
  const negative = game.reviewStats?.negative ?? 0
  const total = positive + negative
  if (total <= 0) {
    return null
  }
  return (positive / total) * 100
}

function reviewRelevanceScore(game: RecommendedGame): number | null {
  const positivity = reviewPositivePercent(game)
  if (positivity === null) {
    return null
  }
  const reviewCount = game.reviewStats?.reviewCount ?? 0
  const confidence = Math.min(Math.log10(reviewCount + 1) / 5, 1)
  return positivity * 0.72 + confidence * 100 * 0.28
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

export default function NextSteamGamePage() {
  const [screen, setScreen] = useState<Screen>("search")
  const [controlMode, setControlMode] = useState<"simple" | "advanced">("simple")
  const [selectedGame, setSelectedGame] = useState<Game | null>(null)
  const [selectedSimpleTags, setSelectedSimpleTags] = useState<string[]>([])
  const [simpleHighlightedContexts, setSimpleHighlightedContexts] = useState<TagContextKey[]>([])
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<Game[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [resultsLoading, setResultsLoading] = useState(false)
  const [resultsError, setResultsError] = useState<string | null>(null)
  const [rawRecommendations, setRawRecommendations] = useState<RecommendedGame[]>([])
  const [tagFilters, setTagFilters] = useState<TagFilters>({ include: [], exclude: [], minReviewPercent: 0, minReviewRelevance: 0 })
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
  const profileHeroImage =
    selectedGame?.assets.libraryHero ||
    selectedGame?.assets.background ||
    selectedGame?.headerImage ||
    selectedGame?.image ||
    ""
  const backgroundHeroHeight = 555
  const backgroundHeroZoom = 1.06
  const backgroundHeroPosition = "center 18%"
  const thumbnailWidth = 210
  const thumbnailHeight = 296 
  const thumbnailZoom = 1
  const thumbnailPosition = "center center"
  const thumbnailRadius = 2
  const profileLogoImage = selectedGame?.assets.logo || ""
  const profileCardImage =
    selectedGame?.assets.libraryCapsule ||
    selectedGame?.assets.capsuleV5 ||
    selectedGame?.image ||
    selectedGame?.headerImage ||
    ""

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
    setTagFilters({ include: [], exclude: [], minReviewPercent: 0, minReviewRelevance: 0 })
    setSelectedSimpleTags([])
    setSimpleHighlightedContexts([])
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

    const minReviewPercent = tagFilters.minReviewPercent ?? 0
    if (minReviewPercent > 0) {
      filtered = filtered.filter((rec) => {
        const percent = reviewPositivePercent(rec)
        return percent === null || percent >= minReviewPercent
      })
    }

    const minReviewRelevance = tagFilters.minReviewRelevance ?? 0
    if (minReviewRelevance > 0) {
      filtered = filtered.filter((rec) => {
        const relevance = reviewRelevanceScore(rec)
        return relevance === null || relevance >= minReviewRelevance
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

  const simpleFeaturedTags = useMemo(() => featuredTagGroups(selectedGame), [selectedGame])

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
    matchDelta = 14,
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

  const handleSimpleIntentBoost = (intent: SimpleIntentKey) => {
    setSimpleHighlightedContexts(simpleIntentHighlights(intent))
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

  const toggleSimpleTag = (context: keyof Weights["tags"], tag: string) => {
    const selectionKey = `${context}:${tag}`
    const isSelected = selectedSimpleTags.includes(selectionKey)
    setSimpleHighlightedContexts([context])

    setSelectedSimpleTags((prev) =>
      isSelected ? prev.filter((item) => item !== selectionKey) : [...prev, selectionKey],
    )

    if (isSelected) {
      if (selectedGame) {
        const baseWeights = buildWeightsFromGame(selectedGame)
        const originalValue = baseWeights.tags[context]?.[tag] ?? 0
        updateTagWeight(context, tag, originalValue)
      }
      return
    }

    const current = weights.tags[context]?.[tag] ?? 0
    const nextValue = Math.min(100, current + 18)
    updateTagWeight(context, tag, nextValue)

    if (context === "music") {
      applySimpleIntentBoost("music", "music", 8, 6)
    } else {
      const contextMap: Record<string, keyof Weights["context"]> = {
        mechanics: "mechanics",
        narrative: "narrative",
        vibe: "vibe",
        structure_loop: "structure_loop",
        uniqueness: "uniqueness",
        music: "music",
      }
      applySimpleIntentBoost(contextMap[context], "vector", 6, 4)
    }
  }

  const toggleGenre = (category: keyof Weights["genres"], genre: string) => {
    setWeights((prev) => {
      const current = prev.genres[category]
      const updated =
        category === "traits"
          ? (
              current.includes(genre)
                ? current.filter((g) => g !== genre)
                : [...current, genre]
            )
          : (current[0] === genre ? [] : [genre])
      return { ...prev, genres: { ...prev.genres, [category]: updated } }
    })
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="mx-auto max-w-[1800px] px-6 py-4">
          <div className="flex items-center gap-8">
            <div className="flex-1" />

            <div className="flex items-center gap-3">
              <button
                onClick={() => setScreen("search")}
                className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-border bg-background/60 p-2 text-sm text-foreground shadow-[0_10px_28px_rgba(0,0,0,0.18)] transition hover:bg-secondary/40"
                aria-label="Home"
                title="Home"
              >
                <img
                  src={steamLogo.src}
                  alt="Steam"
                  className="h-full w-full object-contain"
                />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className={screen === "search" ? "" : "mx-auto max-w-[1800px] px-3 py-8 md:px-4 xl:px-5"}>
        {screen === "search" && (
          <div className="relative min-h-[calc(100dvh-77px)] overflow-hidden">
            <img
              src={gameShelfBackground.src}
              alt=""
              className="absolute inset-0 h-full w-full object-cover"
            />
            <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(8,13,19,0.58),rgba(8,13,19,0.78)),linear-gradient(90deg,rgba(8,13,19,0.30),rgba(8,13,19,0.42))]" />
            <div className="relative z-10 flex min-h-[calc(100dvh-77px)] items-center justify-center px-12 py-12">
              <div className="w-full max-w-3xl text-center">
                <div className="flex items-center justify-center gap-4">
                  <h1 className="text-5xl font-semibold tracking-tight text-white md:text-6xl">
                    NextSteamGame
                  </h1>
                  <img
                    src={steamLogo.src}
                    alt="Steam"
                    className="h-12 w-12 object-contain md:h-14 md:w-14"
                  />
                </div>
                <p className="mx-auto mt-5 max-w-2xl text-base text-slate-200 md:text-lg">
                  Have fun exploring your taste in games. Start with one you already love, discover why it clicks, and find what to play next.
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
                {searchError && <p className="mt-4 text-sm text-red-300">{searchError}</p>}
              </div>
            </div>
          </div>
        )}

        {screen === "profile" && (
          <div className="relative -mx-6 -mt-8 overflow-hidden bg-[#121b27]">
              {profileHeroImage && (
                <>
                  <div className="absolute inset-x-0 top-0 flex items-start justify-center overflow-hidden" style={{ height: backgroundHeroHeight }}>
                    <img
                      src={profileHeroImage}
                      alt={selectedGame?.title || "Selected game"}
                      className="h-full w-full object-cover"
                      style={{
                        objectPosition: backgroundHeroPosition,
                        transform: `scale(${backgroundHeroZoom})`,
                        transformOrigin: "center top",
                      }}
                    />
                  </div>
                  <div
                    className="absolute inset-x-0 top-0 bg-[linear-gradient(180deg,rgba(9,14,20,0.02),rgba(9,14,20,0.10)_40%,rgba(9,14,20,0.26)_72%,rgba(9,14,20,0.66)_100%),linear-gradient(90deg,rgba(9,14,20,0.34)_0%,rgba(9,14,20,0.10)_36%,rgba(9,14,20,0.02)_68%,rgba(9,14,20,0.14)_100%)]"
                    style={{ height: backgroundHeroHeight }}
                  />
                  <div
                    className="absolute inset-x-0 h-40 bg-[linear-gradient(180deg,rgba(14,22,33,0)_0%,rgba(14,22,33,0.24)_34%,rgba(14,22,33,0.72)_100%)] blur-2xl"
                    style={{ top: backgroundHeroHeight - 64 }}
                  />
                </>
              )}

              <div className="relative z-10 px-4 py-6 md:px-5 md:py-8 xl:px-6 xl:py-10">
                <div className="flex flex-col gap-6 xl:gap-8">
                  <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
                    <div className="space-y-4">
                      <button
                        onClick={() => setScreen("search")}
                        className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/88 backdrop-blur hover:bg-white/10"
                      >
                        <ArrowLeft className="h-4 w-4" />
                        Back to Search
                      </button>
                    </div>

                    {profileLogoImage ? (
                      <div className="relative h-16 w-full max-w-[340px] self-start md:h-20">
                        <img
                          src={profileLogoImage}
                          alt={`${selectedGame?.title || "Selected game"} logo`}
                          className="h-full w-full object-contain object-left md:object-right drop-shadow-[0_10px_18px_rgba(0,0,0,0.28)]"
                        />
                      </div>
                    ) : (
                      <div className="h-16 w-full max-w-[340px] md:h-20" />
                    )}
                  </div>

                  <div className="grid items-end gap-6 xl:gap-8" style={{ gridTemplateColumns: `${thumbnailWidth}px minmax(0, 1fr)` }}>
                    <div
                      className="w-full self-end overflow-hidden shadow-[0_24px_44px_rgba(0,0,0,0.32)]"
                      style={{ maxWidth: `${thumbnailWidth}px`, borderRadius: `${thumbnailRadius}px` }}
                    >
                      {profileCardImage ? (
                        <div style={{ height: `${thumbnailHeight}px` }}>
                          <img
                            src={profileCardImage}
                            alt={selectedGame?.title || "Selected game"}
                            className="block h-full w-full object-cover"
                            style={{
                              borderRadius: `${thumbnailRadius}px`,
                              objectPosition: thumbnailPosition,
                              transform: `scale(${thumbnailZoom})`,
                              transformOrigin: "center center",
                            }}
                          />
                        </div>
                      ) : (
                        <div className="aspect-square" />
                      )}
                    </div>

                    <div className="min-w-0 pt-2">
                      <h2 className="text-4xl font-semibold tracking-tight text-white md:text-5xl">
                        {selectedGame?.title}
                      </h2>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {selectedGame?.genres.primary.slice(0, 2).map((genre) => (
                          <span
                            key={genre}
                            className="rounded-full border border-white/22 bg-white/12 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-white/95"
                          >
                            {genre}
                          </span>
                        ))}
                        {selectedGame?.category ? (
                          <span className="rounded-full border border-sky-300/32 bg-sky-400/18 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-sky-50">
                            {selectedGame.category}
                          </span>
                        ) : null}
                        <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-white/85">
                          AppID {selectedGame?.id}
                        </span>
                      </div>
                      <p className="mt-5 max-w-3xl text-sm leading-7 text-slate-300 md:text-[15px]">
                        Choose what you like. Start with the traits that make this game click, then switch to advanced mode when you want full control over vectors, match weighting, and detailed profile shaping.
                      </p>
                      <div className="mt-4 inline-flex items-center rounded-full border border-white/12 bg-sky-400/10 px-4 py-2 text-sm font-medium text-sky-100/95">
                        Simple mode for taste chips. Advanced mode for full vectors.
                      </div>
                    </div>
                  </div>

                  <ControlPanel
                    selectedGame={selectedGame}
                    weights={weights}
                    highlightedContexts={simpleHighlightedContexts}
                    genreOptions={genreOptions}
                    featuredTags={simpleFeaturedTags}
                    mode={controlMode}
                    onModeChange={setControlMode}
                    onMatchWeightChange={updateMatchWeight}
                    onContextWeightChange={updateContextWeight}
                    onAppealWeightChange={updateAppealWeight}
                    onTagWeightChange={updateTagWeight}
                    onGenreToggle={toggleGenre}
                    onSimpleIntentBoost={handleSimpleIntentBoost}
                    selectedSimpleTags={selectedSimpleTags}
                    onSimpleTagToggle={toggleSimpleTag}
                  />

                  <div className="flex justify-end pb-6">
                    <button
                      onClick={() => setScreen("results")}
                      className="inline-flex items-center gap-2 rounded-full bg-[linear-gradient(180deg,#8fd7ff,#66c0f4)] px-6 py-3 text-sm font-semibold text-slate-950 shadow-[0_20px_40px_rgba(26,159,255,0.24)] transition hover:-translate-y-0.5 hover:bg-[linear-gradient(180deg,#a8e1ff,#79cbfb)] hover:text-slate-950"
                    >
                      See Results
                      <ArrowRight className="h-4 w-4" />
                    </button>
                  </div>
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
                <div className="mt-2 text-lg font-semibold text-foreground">Refine the results</div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Keep adjusting the profile here to learn what matters most and steer the next set of matches.
                </p>
              </div>
              <ControlPanel
                selectedGame={selectedGame}
                weights={weights}
                highlightedContexts={simpleHighlightedContexts}
                resultsCompact={true}
                genreOptions={genreOptions}
                featuredTags={simpleFeaturedTags}
                mode={controlMode}
                onModeChange={setControlMode}
                onMatchWeightChange={updateMatchWeight}
                onContextWeightChange={updateContextWeight}
                onAppealWeightChange={updateAppealWeight}
                onTagWeightChange={updateTagWeight}
                onGenreToggle={toggleGenre}
                onSimpleIntentBoost={handleSimpleIntentBoost}
                selectedSimpleTags={selectedSimpleTags}
                onSimpleTagToggle={toggleSimpleTag}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
