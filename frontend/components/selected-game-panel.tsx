"use client"

import type { Game } from "@/lib/types"
import Image from "next/image"

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

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      {/* Header Image */}
      <div className="relative aspect-[460/215] bg-muted">
        <Image
          src={game.headerImage}
          alt={game.title}
          fill
          className="object-cover"
          unoptimized
        />
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Title & Meta */}
        <div>
          <h2 className="text-base font-semibold text-foreground">{game.title}</h2>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-muted-foreground">{game.category}</span>
            <span className="text-muted-foreground">·</span>
            <span className="text-xs text-muted-foreground">{game.releaseDate}</span>
          </div>
        </div>

        {/* Description */}
        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">
          {game.description}
        </p>

        {/* Genres */}
        <div className="space-y-3">
          <div>
            <span className="text-xs font-medium text-foreground">Genres</span>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {game.genres.primary.map(genre => (
                <span key={genre} className="px-2 py-0.5 text-xs bg-foreground text-background rounded">
                  {genre}
                </span>
              ))}
              {game.genres.sub.slice(0, 3).map(genre => (
                <span key={genre} className="px-2 py-0.5 text-xs bg-secondary text-secondary-foreground rounded">
                  {genre}
                </span>
              ))}
            </div>
          </div>
          
          <div>
            <span className="text-xs font-medium text-foreground">Tags</span>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {[...game.tags.mechanics, ...game.tags.vibe].slice(0, 5).map(tag => (
                <span key={tag} className="px-2 py-0.5 text-xs bg-secondary text-muted-foreground rounded">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
