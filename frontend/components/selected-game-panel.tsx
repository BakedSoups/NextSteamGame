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
  const logoImage = game.assets.logo
  const badgeImage = capsuleImage || heroImage || IMAGE_FALLBACK
  
  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      {/* Header Image */}
      <div className="relative aspect-[460/215] bg-muted">
        <Image
          src={heroImage}
          alt={game.title}
          fill
          className="object-cover"
          unoptimized
        />
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/25 to-transparent" />
        <div className="absolute left-4 bottom-4 right-4 flex items-end gap-3">
          <div className="relative h-14 w-14 overflow-hidden rounded-xl border border-border/70 bg-black/30">
            <Image
              src={badgeImage}
              alt={game.title}
              fill
              className="object-cover"
              unoptimized
            />
          </div>
          <div className="min-w-0 flex-1">
            {logoImage ? (
              <div className="relative mb-2 h-10 w-full max-w-[220px]">
                <Image
                  src={logoImage || IMAGE_FALLBACK}
                  alt={`${game.title} logo`}
                  fill
                  className="object-contain object-left"
                  unoptimized
                />
              </div>
            ) : (
              <h2 className="text-lg font-semibold text-white">{game.title}</h2>
            )}
            <div className="flex items-center gap-2 text-xs text-white/80">
              <span>{game.category}</span>
              <span>·</span>
              <span>{game.releaseDate}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        <div className="relative aspect-[460/120] overflow-hidden rounded-xl border border-border bg-muted">
          <Image
            src={capsuleImage}
            alt={game.title}
            fill
            className="object-cover"
            unoptimized
          />
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
