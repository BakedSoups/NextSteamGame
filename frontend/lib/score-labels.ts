import type { Weights } from "@/lib/types"

export const MATCH_LABELS: Record<keyof Weights["match"], string> = {
  vector: "Gameplay Fit",
  genre: "Genre Match",
  appeal: "Preference Match",
  music: "Music Match",
}
