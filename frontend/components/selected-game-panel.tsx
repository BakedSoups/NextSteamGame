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
  const primaryGenres = game.genres.primary.slice(0, 2)
  const signatureTags = game.tags.uniqueness.slice(0, 3)
  
  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      {/* Header Image */}
      <div className="relative aspect-[460/320] bg-muted">
        <Image
          src={heroImage}
          alt={game.title}
          fill
          className="object-cover scale-110 opacity-30 blur-sm"
          unoptimized
        />
        <Image
          src={heroImage}
          alt={game.title}
          fill
          className="object-contain object-center p-2"
          unoptimized
        />
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/40 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 p-4">
          <div className="rounded-2xl border border-border/60 bg-black/35 p-4 backdrop-blur-md">
            <div className="flex items-end gap-4">
              <div className="relative h-24 w-40 overflow-hidden rounded-xl border border-border/70 bg-black/40 shadow-[0_12px_30px_rgba(0,0,0,0.35)]">
                <Image
                  src={capsuleImage}
                  alt={game.title}
                  fill
                  className="object-cover"
                  unoptimized
                />
              </div>
              <div className="min-w-0 flex-1">
                {logoImage ? (
                  <div className="relative mb-3 h-14 w-full max-w-[280px]">
                    <Image
                      src={logoImage || IMAGE_FALLBACK}
                      alt={`${game.title} logo`}
                      fill
                      className="object-contain object-left"
                      unoptimized
                    />
                  </div>
                ) : (
                  <h2 className="text-2xl font-semibold text-white">{game.title}</h2>
                )}
                <div className="flex flex-wrap gap-2">
                  {primaryGenres.map((genre) => (
                    <span key={genre} className="rounded-full border border-white/15 bg-white/10 px-2.5 py-1 text-[11px] text-white/90">
                      {genre}
                    </span>
                  ))}
                  {game.category && (
                    <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2.5 py-1 text-[11px] text-cyan-100">
                      {game.category}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="mt-4">
              <div className="text-[10px] font-medium uppercase tracking-[0.24em] text-white/60">
                Why This Game Clicks
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {signatureTags.map((tag) => (
                  <span key={tag} className="rounded-full border border-white/10 bg-white/8 px-3 py-1 text-xs text-white/85">
                    {tag}
                  </span>
                ))}
                {signatureTags.length === 0 && (
                  <span className="text-xs text-white/70">{game.description}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        <div className="rounded-xl border border-border bg-secondary/20 p-3">
          <div className="text-[10px] font-medium uppercase tracking-[0.25em] text-muted-foreground">
            Profile Snapshot
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Primary</div>
              <div className="mt-1 text-sm font-medium text-foreground">
                {game.genres.primary.slice(0, 2).join(" · ") || "Unknown"}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Mood</div>
              <div className="mt-1 text-sm font-medium text-foreground">
                {game.tags.vibe.slice(0, 2).join(" · ") || "Unknown"}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Signature</div>
              <div className="mt-1 text-sm font-medium text-foreground">
                {game.category || "Unclassified"}
              </div>
            </div>
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
