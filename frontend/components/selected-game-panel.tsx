"use client"

import type { Game } from "@/lib/types"
import Image from "next/image"

const IMAGE_FALLBACK = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='460' height='215'><rect width='100%' height='100%' fill='%2311161f'/></svg>"

interface SelectedGamePanelProps {
  game: Game | null
}

export function SelectedGamePanel({ game }: SelectedGamePanelProps) {
  if (!game) {
    return (
      <div className="bg-card border border-border rounded-lg p-8 text-center">
        <p className="text-sm text-muted-foreground">Select a game to analyze</p>
      </div>
    )
  }

  const heroImage = game.assets.libraryHero || game.assets.background || game.headerImage || IMAGE_FALLBACK
  const capsuleImage = game.assets.libraryCapsule || game.assets.capsuleV5 || game.image || IMAGE_FALLBACK
  const primaryGenres = game.genres.primary.slice(0, 2)
  const hasSemanticProfile = Object.values(game.tags).some((tags) => tags.length > 0)
  
  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      <div className="grid grid-cols-[112px_minmax(0,1fr)] gap-4 p-4">
        <div className="relative aspect-square overflow-hidden rounded-2xl bg-muted shadow-[0_18px_42px_rgba(0,0,0,0.28)]">
          <Image
            src={capsuleImage}
            alt={game.title}
            fill
            className="object-contain p-2"
            unoptimized
          />
        </div>

        <div className="min-w-0 self-end space-y-3">
          <h2 className="text-xl font-semibold text-foreground">{game.title}</h2>

          {(primaryGenres.length > 0 || game.category) ? (
            <p className="text-xs text-muted-foreground">
              {[...primaryGenres, game.category].filter(Boolean).join(" · ")}
            </p>
          ) : null}

          {!hasSemanticProfile ? (
            <div className="rounded-2xl border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs leading-5 text-amber-50/95">
              This game didn&apos;t have enough insightful reviews. If you want to change that, give this lovely game a review.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
