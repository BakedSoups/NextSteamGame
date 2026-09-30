/** Rebalance one slider's group while preserving the ratios of its peers. */
export function updatePercentWeight<K extends string>(
  current: Record<K, number>,
  key: K,
  value: number,
  group: readonly K[] = Object.keys(current) as K[],
): Record<K, number> {
  const others = group.filter((item) => item !== key)
  const remaining = 100 - value
  const otherTotal = others.reduce((sum, item) => sum + current[item], 0)
  const next: Record<K, number> = { ...current, [key]: value }

  if (otherTotal > 0) {
    for (const item of others) {
      next[item] = Math.max(0, Math.round((current[item] / otherTotal) * remaining))
    }
  }

  // Keep integer sliders at exactly 100 without moving the slider being dragged.
  // If all peers were zero, the last peer receives the remainder (legacy behavior).
  const total = group.reduce((sum, item) => sum + next[item], 0)
  if (total !== 100 && others.length > 0) {
    const largestKey = others.reduce((a, b) => (next[a] > next[b] ? a : b))
    next[largestKey] += 100 - total
  }
  return next
}
