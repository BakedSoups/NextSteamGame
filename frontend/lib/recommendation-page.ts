import type { Game, RecommendedGame, Weights } from "@/lib/types"

export type TagContextKey = keyof Weights["tags"]
export type SimpleIntentKey =
  | "more_similar"
  | "more_different"
  | "better_gameplay"
  | "more_story"
  | "stronger_atmosphere"
  | "more_distinctive"

export const DEFAULT_MATCH_WEIGHTS: Weights["match"] = {
  vector: 34,
  genre: 26,
  appeal: 22,
  music: 18,
}

export const DEFAULT_CONTEXT_WEIGHTS: Weights["context"] = {
  mechanics: 20,
  narrative: 8,
  vibe: 10,
  structure_loop: 18,
  identity: 18,
  setting: 13,
  music: 13,
}

export const DEFAULT_APPEAL_WEIGHTS: Weights["appeal"] = {
  challenge: 50,
  complexity: 50,
  pace: 50,
  narrative_focus: 50,
  social_energy: 50,
  creativity: 50,
}

export const VECTOR_CONTEXT_KEYS: TagContextKey[] = ["mechanics", "narrative", "vibe", "structure_loop"]
export const SIGNAL_CONTEXT_KEYS: TagContextKey[] = ["identity", "setting", "music"]

export function frequentTags(games: Game[], select: (game: Game) => string[], minimumCount = 3): string[] {
  const counts = new Map<string, number>()
  for (const game of games) {
    for (const tag of new Set(select(game).filter(Boolean))) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1)
    }
  }
  return Array.from(counts.entries())
    .filter(([, count]) => count >= minimumCount)
    .map(([tag]) => tag)
    .sort((a, b) => a.localeCompare(b))
}

function normalizeToHundred(tags: string[]): Record<string, number> {
  if (tags.length === 0) return {}
  const base = Math.floor(100 / tags.length)
  const remainder = 100 - base * tags.length
  return tags.reduce<Record<string, number>>((weights, tag, index) => {
    weights[tag] = base + (index < remainder ? 1 : 0)
    return weights
  }, {})
}

function normalizeTagKey(tag: string): string {
  return tag.replace(/[\s-]+/g, "_").toLowerCase()
}

function displayTagWeights(tags: string[], liveWeights?: Record<string, number>): Record<string, number> {
  const fallbackWeights = normalizeToHundred(tags)
  const rawWeights = liveWeights ?? {}
  const normalizedEntries = Object.entries(rawWeights).reduce<Record<string, number>>((weights, [tag, value]) => {
    weights[normalizeTagKey(tag)] = value
    return weights
  }, {})
  const resolved = tags.reduce<Record<string, number>>((weights, tag) => {
    weights[tag] = rawWeights[tag] ?? normalizedEntries[normalizeTagKey(tag)] ?? fallbackWeights[tag] ?? 0
    return weights
  }, {})
  for (const [tag, value] of Object.entries(rawWeights)) {
    const displayTag = tag.replace(/_/g, " ")
    if (!(displayTag in resolved) && !(tag in resolved)) resolved[displayTag] = value
  }
  return resolved
}

export function featuredTagGroups(game: Game | null) {
  if (!game) return []
  const groups: Array<{ context: TagContextKey; label: string; tags: string[] }> = [
    { context: "identity", label: "Signature Hook", tags: game.identity?.signatureTag ? [game.identity.signatureTag] : [] },
    { context: "identity", label: "Identity Anchors", tags: game.identity?.nicheAnchors.slice(0, 6) ?? [] },
    {
      context: "identity",
      label: "Identity Details",
      tags: Array.from(new Set([...(game.identity?.identityTags ?? []), ...(game.identity?.microTags ?? [])])).slice(0, 6),
    },
    { context: "setting", label: "World / Setting", tags: game.tags.setting.slice(0, 6) },
    { context: "music", label: "Music", tags: game.tags.music.slice(0, 6) },
    { context: "narrative", label: "Narrative", tags: game.tags.narrative.slice(0, 3) },
    { context: "vibe", label: "Vibe", tags: game.tags.vibe.slice(0, 3) },
    { context: "structure_loop", label: "Structure", tags: game.tags.structure_loop.slice(0, 3) },
    { context: "mechanics", label: "Mechanics", tags: game.tags.mechanics.slice(0, 3) },
  ]
  return groups.filter((group) => group.tags.length > 0)
}

export function hasSemanticProfile(game: Game | null): boolean {
  return Boolean(game && Object.values(game.tags).some((tags) => tags.length > 0))
}

export function buildWeightsFromGame(game: Game): Weights {
  const liveWeights = game.weights ?? {}
  return {
    match: { ...DEFAULT_MATCH_WEIGHTS, ...(liveWeights.match ?? {}) },
    context: { ...DEFAULT_CONTEXT_WEIGHTS, ...(liveWeights.context ?? {}) },
    appeal: { ...DEFAULT_APPEAL_WEIGHTS, ...(liveWeights.appeal ?? {}) },
    tags: {
      mechanics: displayTagWeights(game.tags.mechanics, liveWeights.tags?.mechanics),
      narrative: displayTagWeights(game.tags.narrative, liveWeights.tags?.narrative),
      vibe: displayTagWeights(game.tags.vibe, liveWeights.tags?.vibe),
      structure_loop: displayTagWeights(game.tags.structure_loop, liveWeights.tags?.structure_loop),
      identity: displayTagWeights(game.tags.identity, liveWeights.tags?.identity),
      setting: displayTagWeights(game.tags.setting, liveWeights.tags?.setting),
      music: displayTagWeights(game.tags.music, liveWeights.tags?.music),
    },
    genres: {
      primary: [...game.genres.primary],
      sub: [...game.genres.sub],
      sub_sub: [...game.genres.sub_sub],
      traits: [...game.genres.traits],
    },
  }
}

export function simpleIntentHighlights(intent: SimpleIntentKey): TagContextKey[] {
  switch (intent) {
    case "more_similar": return ["mechanics", "structure_loop"]
    case "more_different": return ["identity", "setting", "music"]
    case "better_gameplay": return ["mechanics", "structure_loop"]
    case "more_story": return ["narrative"]
    case "stronger_atmosphere": return ["vibe", "music"]
    case "more_distinctive": return ["identity", "setting"]
  }
}

export function reviewPositivePercent(game: RecommendedGame): number | null {
  const positive = game.reviewStats?.positive ?? 0
  const negative = game.reviewStats?.negative ?? 0
  const total = positive + negative
  return total > 0 ? (positive / total) * 100 : null
}

export function reviewRelevanceScore(game: RecommendedGame): number | null {
  const positivity = reviewPositivePercent(game)
  if (positivity === null) return null
  const confidence = Math.min(Math.log10((game.reviewStats?.reviewCount ?? 0) + 1) / 5, 1)
  return positivity * 0.72 + confidence * 100 * 0.28
}

export function steamStoreUrl(game: Game | null): string {
  return game ? `https://store.steampowered.com/app/${game.id}` : "https://store.steampowered.com/"
}
