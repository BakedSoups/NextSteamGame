import type { Weights } from "@/lib/types"

export const MATCH_LABELS: Record<keyof Weights["match"], string> = {
  vector: "Mechanics",
  genre: "Genre",
  appeal: "Appeal",
  music: "Music",
}
