"use client"

import { useState, useRef, useEffect, type CSSProperties } from "react"
import { Search, X } from "lucide-react"
import type { Game } from "@/lib/types"
import Image from "next/image"

const IMAGE_FALLBACK = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180'><rect width='100%' height='100%' fill='%2311161f'/></svg>"
const MAX_SEARCH_RESULTS = 20

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
  const [dropdownTop, setDropdownTop] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const filteredGames = query.length > 0 ? games.slice(0, MAX_SEARCH_RESULTS) : []
  const mobileDropdownStyle = { "--mobile-dropdown-top": `${dropdownTop}px` } as CSSProperties

  const updateDropdownTop = () => {
    const rect = inputRef.current?.getBoundingClientRect()
    if (rect) {
      setDropdownTop(rect.bottom + 8)
    }
  }

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    updateDropdownTop()
    window.addEventListener("resize", updateDropdownTop)
    window.addEventListener("scroll", updateDropdownTop, true)
    return () => {
      window.removeEventListener("resize", updateDropdownTop)
      window.removeEventListener("scroll", updateDropdownTop, true)
    }
  }, [isOpen, query])

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
        <Search className="absolute left-5 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            const nextQuery = e.target.value
            setQuery(nextQuery)
            onQueryChange?.(nextQuery)
            setIsOpen(true)
            updateDropdownTop()
            setFocusedIndex(-1)
          }}
          onFocus={() => {
            updateDropdownTop()
            if (query.length > 0) {
              setIsOpen(true)
            }
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search games..."
          className="h-14 w-full rounded-xl border border-border bg-card pl-12 pr-11 text-base text-foreground shadow-[0_18px_42px_rgba(0,0,0,0.18)] transition-all placeholder:text-muted-foreground focus:border-foreground/20 focus:outline-none focus:ring-2 focus:ring-ring/20 sm:h-18 sm:rounded-2xl sm:pl-14 sm:pr-12 sm:text-lg"
        />
        {query && (
          <button
            onClick={() => {
              setQuery("")
              onQueryChange?.("")
              inputRef.current?.focus()
            }}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {isOpen && filteredGames.length > 0 && (
        <div
          className="fixed left-4 right-4 top-[var(--mobile-dropdown-top)] z-[90] max-h-[45dvh] overflow-hidden rounded-xl border border-border bg-card shadow-[0_24px_60px_rgba(0,0,0,0.38)] sm:absolute sm:left-0 sm:right-0 sm:top-full sm:z-50 sm:mt-3 sm:max-h-none sm:rounded-2xl"
          style={mobileDropdownStyle}
        >
          <div className="max-h-[48dvh] overflow-y-auto custom-scrollbar sm:max-h-72">
            {filteredGames.map((game, index) => (
              <button
                key={game.id}
                onClick={() => handleSelect(game)}
                onMouseEnter={() => setFocusedIndex(index)}
                className={`flex w-full items-center gap-3 px-3 py-3 text-left transition-colors sm:gap-4 sm:px-4 sm:py-4 ${
                  focusedIndex === index 
                    ? "bg-secondary" 
                    : "hover:bg-secondary/50"
                } ${selectedGame?.id === game.id ? "bg-secondary/30" : ""}`}
              >
                <div className="relative h-10 w-16 flex-shrink-0 overflow-hidden rounded bg-muted sm:h-12 sm:w-20">
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
                    <span className="truncate text-sm font-medium text-foreground sm:text-base">{game.title}</span>
                    {selectedGame?.id === game.id && (
                      <span className="flex-shrink-0 px-1.5 py-0.5 text-xs bg-foreground text-background rounded">
                        Selected
                      </span>
                    )}
                  </div>
                  <span className="truncate text-xs text-muted-foreground sm:text-sm">{game.category}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {isOpen && query.length > 0 && filteredGames.length === 0 && (
        <div
          className="fixed left-4 right-4 top-[var(--mobile-dropdown-top)] z-[90] rounded-xl border border-border bg-card p-5 text-center shadow-[0_24px_60px_rgba(0,0,0,0.38)] sm:absolute sm:left-0 sm:right-0 sm:top-full sm:z-50 sm:mt-3 sm:rounded-2xl"
          style={mobileDropdownStyle}
        >
          <Search className="mx-auto mb-2 h-5 w-5 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{isLoading ? "Searching..." : "No games found"}</p>
        </div>
      )}
    </div>
  )
}
