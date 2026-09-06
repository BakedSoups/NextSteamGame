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
    } else if (e.key === "Enter" && filteredGames.length > 0) {
      handleSelect(filteredGames[Math.max(focusedIndex, 0)])
    } else if (e.key === "Escape") {
      setIsOpen(false)
      inputRef.current?.blur()
    }
  }

  return (
    <div className="group/search relative" ref={dropdownRef}>
      <div className="relative">
        <Search className="absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within/search:text-cyan-200" />
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
          placeholder="Search a game you already love…"
          aria-activedescendant={focusedIndex >= 0 ? `game-search-result-${filteredGames[focusedIndex]?.id}` : undefined}
          aria-autocomplete="list"
          aria-controls="game-search-results"
          aria-expanded={isOpen}
          role="combobox"
          className="h-16 w-full rounded-xl border border-white/16 bg-[#101d2a]/95 pl-12 pr-11 text-base text-foreground shadow-[0_20px_52px_rgba(0,0,0,0.32)] transition-all duration-300 placeholder:text-slate-400 focus:border-cyan-200/65 focus:outline-none focus:ring-2 focus:ring-cyan-300/20 focus:shadow-[0_0_0_1px_rgba(125,211,252,0.14),0_22px_64px_rgba(0,0,0,0.42),0_0_34px_rgba(56,189,248,0.13)] sm:h-20 sm:rounded-2xl sm:pl-14 sm:pr-12 sm:text-lg"
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
          className="search-results-enter fixed left-4 right-4 top-[var(--mobile-dropdown-top)] z-[90] max-h-[45dvh] overflow-hidden rounded-xl border border-cyan-200/20 bg-[#101d2a]/98 shadow-[0_28px_70px_rgba(0,0,0,0.5)] backdrop-blur-xl sm:absolute sm:left-0 sm:right-0 sm:top-full sm:z-50 sm:mt-3 sm:max-h-none sm:rounded-2xl"
          style={mobileDropdownStyle}
          id="game-search-results"
          role="listbox"
        >
          <div className="flex items-center justify-between border-b border-white/8 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
            <span>{filteredGames.length} {filteredGames.length === 1 ? "result" : "results"}</span>
          </div>
          <div className="max-h-[48dvh] overflow-y-auto custom-scrollbar sm:max-h-80">
            {filteredGames.map((game, index) => (
              <button
                key={game.id}
                id={`game-search-result-${game.id}`}
                onClick={() => handleSelect(game)}
                onMouseEnter={() => setFocusedIndex(index)}
                role="option"
                aria-selected={focusedIndex === index}
                style={{ animationDelay: `${Math.min(index * 28, 180)}ms` }}
                className={`search-result-enter group/result flex w-full items-center gap-3 border-l-2 px-3 py-3 text-left transition-all sm:gap-4 sm:px-4 sm:py-3.5 ${
                  focusedIndex === index 
                    ? "border-cyan-300 bg-cyan-300/10 shadow-[inset_12px_0_28px_rgba(34,211,238,0.04)]"
                    : "border-transparent hover:border-cyan-300/40 hover:bg-white/5"
                } ${selectedGame?.id === game.id ? "bg-secondary/30" : ""}`}
              >
                <div className="relative h-11 w-[74px] flex-shrink-0 overflow-hidden rounded-md border border-white/10 bg-muted shadow-[0_8px_18px_rgba(0,0,0,0.24)] sm:h-14 sm:w-24">
                  <Image
                    src={game.assets.libraryCapsule || game.assets.capsuleV5 || game.image || IMAGE_FALLBACK}
                    alt={game.title}
                    fill
                    className="object-cover transition-transform duration-300 group-hover/result:scale-[1.04]"
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
