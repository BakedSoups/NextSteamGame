import {
  BadgeInfo,
  BookOpen,
  Gamepad,
  Gauge,
  ScanLine,
  Shuffle,
  type LucideIcon,
} from "lucide-react"
import { MATCH_LABELS } from "@/lib/score-labels"
import type { Weights } from "@/lib/types"

export type SimpleIntent =
  | "more_similar"
  | "more_different"
  | "better_gameplay"
  | "more_story"
  | "stronger_atmosphere"
  | "more_distinctive"

export const VECTOR_CONTEXT_KEYS: Array<keyof Weights["tags"]> = [
  "mechanics",
  "narrative",
  "vibe",
  "structure_loop",
]

export const TAG_SIGNAL_CONTEXT_KEYS: Array<keyof Weights["tags"]> = ["identity", "setting", "music"]

export const SIMPLE_INTENTS: { key: SimpleIntent; label: string; hint: string; icon: LucideIcon }[] = [
  { key: "more_similar", label: "More Like This", hint: "Stay closer to the base game's structure and feel", icon: ScanLine },
  { key: "better_gameplay", label: "Emphasize Gameplay", hint: "Shift the match toward systems, structure, and play feel", icon: Gamepad },
  { key: "more_story", label: "Focus on Story", hint: "Shift the match toward story, character presence, and narrative pull", icon: BookOpen },
  { key: "stronger_atmosphere", label: "Emphasize Atmosphere", hint: "Shift the match toward mood, tone, and overall feel", icon: Gauge },
  { key: "more_different", label: "More Different", hint: "Loosen the match and allow more novelty", icon: Shuffle },
  { key: "more_distinctive", label: "Focus on Identity", hint: "Shift the match toward signature traits and standout identity", icon: BadgeInfo },
]

export const CONTEXT_VISUALS: Record<keyof Weights["tags"], { stat: string; accent: string; glow: string }> = {
  mechanics: { stat: "POWER", accent: "#7dd3fc", glow: "rgba(125, 211, 252, 0.35)" },
  narrative: { stat: "RESOLVE", accent: "#fda4af", glow: "rgba(253, 164, 175, 0.28)" },
  vibe: { stat: "AURA", accent: "#c4b5fd", glow: "rgba(196, 181, 253, 0.3)" },
  structure_loop: { stat: "PRECISION", accent: "#86efac", glow: "rgba(134, 239, 172, 0.28)" },
  identity: { stat: "SIGNAL", accent: "#fcd34d", glow: "rgba(252, 211, 77, 0.28)" },
  setting: { stat: "WORLD", accent: "#60a5fa", glow: "rgba(96, 165, 250, 0.28)" },
  music: { stat: "RHYTHM", accent: "#f9a8d4", glow: "rgba(249, 168, 212, 0.3)" },
}

export const MATCH_VISUALS: Record<keyof Weights["match"], { label: string; fill: string; glow: string }> = {
  vector: { label: MATCH_LABELS.vector, fill: "#7dd3fc", glow: "rgba(125, 211, 252, 0.35)" },
  genre: { label: MATCH_LABELS.genre, fill: "#86efac", glow: "rgba(134, 239, 172, 0.3)" },
  appeal: { label: MATCH_LABELS.appeal, fill: "#fda4af", glow: "rgba(253, 164, 175, 0.3)" },
  music: { label: MATCH_LABELS.music, fill: "#fcd34d", glow: "rgba(252, 211, 77, 0.3)" },
}

export const VECTOR_INFLUENCE_COLORS: Record<keyof Weights["context"], { fill: string; glow: string }> = {
  mechanics: { fill: "#7dd3fc", glow: "rgba(125, 211, 252, 0.35)" },
  narrative: { fill: "#c084fc", glow: "rgba(192, 132, 252, 0.30)" },
  vibe: { fill: "#2dd4bf", glow: "rgba(45, 212, 191, 0.30)" },
  structure_loop: { fill: "#f97316", glow: "rgba(249, 115, 22, 0.28)" },
  identity: { fill: "#fb7185", glow: "rgba(251, 113, 133, 0.30)" },
  setting: { fill: "#60a5fa", glow: "rgba(96, 165, 250, 0.30)" },
  music: { fill: "#fcd34d", glow: "rgba(252, 211, 77, 0.3)" },
}

export const TAG_CONTEXT_ACCENTS: Record<keyof Weights["tags"], string> = {
  mechanics: "#7dd3fc",
  narrative: "#fda4af",
  vibe: "#2dd4bf",
  structure_loop: "#86efac",
  identity: "#fcd34d",
  setting: "#60a5fa",
  music: "#f9a8d4",
}
