import { unique } from "@/lib/collections"
import type { Game, RecommendedGame, Weights } from "@/lib/types"

type TagContextKey = keyof Weights["tags"]
type MatchComponentKey = keyof Weights["match"]

const TAG_CONTEXT_COMPONENT: Record<TagContextKey, MatchComponentKey> = {
  mechanics: "vector",
  narrative: "vector",
  vibe: "vector",
  structure_loop: "vector",
  identity: "appeal",
  setting: "appeal",
  music: "music",
}

export function formatReviewCount(count: number) {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(count >= 10_000_000 ? 0 : 1)}m`
  if (count >= 1_000) return `${(count / 1_000).toFixed(count >= 10_000 ? 0 : 1)}k`
  return String(count)
}

export function reviewSummary(game: RecommendedGame) {
  const positive = game.reviewStats?.positive ?? 0
  const negative = game.reviewStats?.negative ?? 0
  const reviewCount = game.reviewStats?.reviewCount ?? positive + negative
  const total = positive + negative
  if (reviewCount <= 0 && total <= 0) return null
  return { positivePercent: total > 0 ? Math.round((positive / total) * 100) : null, reviewCount }
}

export function normalizeTagMatchKey(tag: string) {
  return tag.trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ").toLowerCase()
}

export function genreTokens(game: Pick<Game, "category" | "genres"> | null) {
  if (!game) return []
  return unique([
    game.category,
    ...game.genres.primary,
    ...game.genres.sub,
    ...game.genres.sub_sub,
    ...game.genres.traits,
  ].filter(Boolean))
}

function tagsMatch(left: string, right: string) {
  const leftKey = normalizeTagMatchKey(left)
  const rightKey = normalizeTagMatchKey(right)
  return leftKey === rightKey || leftKey.includes(rightKey) || rightKey.includes(leftKey)
}

export function evidenceTags(
  influencedTags: string[],
  fallbackTags: string[],
  limit = 3,
  tunedTag?: string,
  highlightedTags: string[] = [],
) {
  const influencedKeys = new Set(influencedTags.map(normalizeTagMatchKey))
  const tunedKey = tunedTag ? normalizeTagMatchKey(tunedTag) : null
  const tags = unique([...influencedTags, ...fallbackTags])
  const selectedTags = tags.filter((label) => highlightedTags.some((selectedTag) => tagsMatch(label, selectedTag)))
  const remainingTags = tags.filter((label) => !selectedTags.includes(label))
  return [...selectedTags, ...remainingTags].slice(0, limit).map((label) => ({
    label,
    influenced: influencedKeys.has(normalizeTagMatchKey(label)),
    tuned: tunedKey === normalizeTagMatchKey(label),
    selected: highlightedTags.some((selectedTag) => tagsMatch(label, selectedTag)),
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

export function topRequestedTagMatch(game: RecommendedGame, weights: Weights, selectedGame: Game | null) {
  if (!selectedGame) return null
  const matchedTags = game.matchedTags ?? {
    mechanics: [], narrative: [], vibe: [], structure_loop: [], identity: [], setting: [], music: [],
  }
  const requestedByContext = (Object.keys(weights.tags) as TagContextKey[])
    .map((context) => {
      const changedWeights = Object.keys(weights.tags[context] ?? {})
        .map((tag) => changedTagWeight(context, tag, weights, selectedGame))
        .filter(Boolean)
      return {
        context,
        requestedWeight: Math.max(0, ...changedWeights.map((entry) => entry!.requestedWeight)),
        delta: Math.max(0, ...changedWeights.map((entry) => entry!.delta)),
      }
    })
    .filter((item) => item.delta > 1)

  const exactMatches = requestedByContext.flatMap(({ context }) => {
    const matchedByKey = new Map((matchedTags[context] ?? []).map((tag) => [normalizeTagMatchKey(tag), tag]))
    return Object.keys(weights.tags[context] ?? {}).flatMap((tag) => {
      const changed = changedTagWeight(context, tag, weights, selectedGame)
      const matchedTag = matchedByKey.get(normalizeTagMatchKey(tag))
      if (!changed || !matchedTag) return []
      const component = TAG_CONTEXT_COMPONENT[context]
      return [{
        context,
        component,
        tag: matchedTag,
        requestedWeight: changed.requestedWeight,
        contextHit: game.contextScores[context] ?? 0,
        componentShare: game.scorePercentages?.[component] ?? game.scores[component] ?? 0,
        exact: true,
      }]
    })
  }).sort((a, b) => b.requestedWeight - a.requestedWeight || b.contextHit - a.contextHit)

  if (exactMatches[0]) return exactMatches[0]
  for (const { context, requestedWeight } of requestedByContext.sort((a, b) => b.delta - a.delta)) {
    const matchedTag = matchedTags[context]?.[0]
    const contextHit = game.contextScores[context] ?? 0
    if (!matchedTag || contextHit <= 0) continue
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

export function profileCompareSections(selectedGame: Game | null, game: RecommendedGame) {
  const sections = [
    { label: "Genre", base: genreTokens(selectedGame), result: genreTokens(game) },
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
  }).filter((section) => section.shared.length || section.baseOnly.length || section.resultOnly.length)
}
