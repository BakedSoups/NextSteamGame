"use client"

import { useState, useRef, useEffect } from "react"
import { Search, X } from "lucide-react"
import type { Game } from "@/lib/types"
import Image from "next/image"

const IMAGE_FALLBACK = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180'><rect width='100%' height='100%' fill='%2311161f'/></svg>"

interface SearchBarProps {
  games: Game[]
  isLoading?: boolean
  onQueryChange?: (query: string) => void
  onSelect: (game: Game) => void
  selectedGame: Game | null
}

export function SearchBar({ games, isLoading = false, onQueryChange, onSelect, selectedGame }: SearchBarProps) {
  const [query, setQuery] = useState("")
  const [isOpen, setIsOpen] = useState(false)
  const [focusedIndex, setFocusedIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const filteredGames = query.length > 0 ? games.slice(0, 8) : []

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleSelect = (game: Game) => {
    onSelect(game)
    setQuery("")
    onQueryChange?.("")
    setIsOpen(false)
    setFocusedIndex(-1)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setFocusedIndex(prev => Math.min(prev + 1, filteredGames.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setFocusedIndex(prev => Math.max(prev - 1, 0))
    } else if (e.key === "Enter" && focusedIndex >= 0) {
      handleSelect(filteredGames[focusedIndex])
    } else if (e.key === "Escape") {
      setIsOpen(false)
      inputRef.current?.blur()
    }
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            const nextQuery = e.target.value
            setQuery(nextQuery)
            onQueryChange?.(nextQuery)
            setIsOpen(true)
            setFocusedIndex(-1)
          }}
          onFocus={() => query.length > 0 && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search games..."
          className="w-full h-10 pl-10 pr-9 bg-card border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/20 focus:border-foreground/20 transition-all"
        />
        {query && (
          <button
            onClick={() => {
              setQuery("")
              onQueryChange?.("")
              inputRef.current?.focus()
            }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {isOpen && filteredGames.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg overflow-hidden shadow-lg z-50">
          <div className="max-h-80 overflow-y-auto">
            {filteredGames.map((game, index) => (
              <button
                key={game.id}
                onClick={() => handleSelect(game)}
                onMouseEnter={() => setFocusedIndex(index)}
                className={`w-full flex items-center gap-3 p-3 text-left transition-colors ${
                  focusedIndex === index 
                    ? "bg-secondary" 
                    : "hover:bg-secondary/50"
                } ${selectedGame?.id === game.id ? "bg-secondary/30" : ""}`}
              >
                <div className="relative w-14 h-8 rounded overflow-hidden bg-muted flex-shrink-0">
                  <Image
                    src={game.assets.libraryCapsule || game.assets.capsuleV5 || game.image || IMAGE_FALLBACK}
                    alt={game.title}
                    fill
                    className="object-cover"
                    unoptimized
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground truncate">{game.title}</span>
                    {selectedGame?.id === game.id && (
                      <span className="flex-shrink-0 px-1.5 py-0.5 text-[10px] bg-foreground text-background rounded">
                        Selected
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground">{game.category}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {isOpen && query.length > 0 && filteredGames.length === 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg p-4 text-center shadow-lg z-50">
          <Search className="h-5 w-5 mx-auto text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">{isLoading ? "Searching..." : "No games found"}</p>
        </div>
      )}
    </div>
  )
}
