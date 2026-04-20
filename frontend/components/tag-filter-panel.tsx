"use client"

import { useState, useMemo } from "react"
import { Search, X, Filter, ChevronDown, ChevronRight, Crosshair } from "lucide-react"

interface TagFilterState {
  include: string[]
  exclude: string[]
  minReviewPercent?: number
  minReviewRelevance?: number
}

interface TagFilterPanelProps {
  filters: TagFilterState
  tagOptions: Record<string, string[]>
  onFiltersChange: (filters: TagFilterState) => void
}

const CATEGORY_LABELS: Record<string, string> = {
  mechanics: "Mechanics",
  narrative: "Narrative",
  vibe: "Vibe",
  structure_loop: "Structure",
  uniqueness: "Uniqueness",
  music: "Music"
}

export function TagFilterPanel({ filters, tagOptions, onFiltersChange }: TagFilterPanelProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [expandedCategories, setExpandedCategories] = useState<string[]>(["mechanics", "vibe"])
  
  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => 
      prev.includes(category) 
        ? prev.filter(c => c !== category)
        : [...prev, category]
    )
  }

  const toggleIncludeTag = (tag: string) => {
    if (filters.include.includes(tag)) {
      onFiltersChange({ ...filters, include: filters.include.filter(t => t !== tag) })
      return
    }
    onFiltersChange({
      include: [...filters.include, tag],
      exclude: filters.exclude.filter(t => t !== tag),
    })
  }

  const clearAllFilters = () => {
    onFiltersChange({ include: [], exclude: [], minReviewPercent: 0, minReviewRelevance: 0 })
  }

  const filteredTags = useMemo(() => {
    if (!searchQuery.trim()) return tagOptions
    
    const query = searchQuery.toLowerCase()
    const result: Record<string, string[]> = {}
    
    Object.entries(tagOptions).forEach(([category, tags]) => {
      const filtered = tags
        .filter(tag => tag.toLowerCase().includes(query))
        .sort((a, b) => {
          const aSelected = filters.include.includes(a) ? 1 : 0
          const bSelected = filters.include.includes(b) ? 1 : 0
          return bSelected - aSelected || a.localeCompare(b)
        })
      if (filtered.length > 0) {
        result[category] = filtered
      }
    })
    
    return result
  }, [searchQuery, filters.include, tagOptions])

  const activeFilterCount =
    filters.include.length +
    filters.exclude.length +
    ((filters.minReviewPercent ?? 0) > 0 ? 1 : 0) +
    ((filters.minReviewRelevance ?? 0) > 0 ? 1 : 0)

  return (
    <div className="panel overflow-hidden glow-box-subtle">
      {/* Header */}
      <div className="panel-header">
        <Crosshair className="w-3.5 h-3.5 text-primary" />
        <span className="text-xs font-medium text-foreground">Micro Tag Filters</span>
        {activeFilterCount > 0 && (
          <>
            <span className="ml-auto data-value">{activeFilterCount} active</span>
            <button
              onClick={clearAllFilters}
              className="text-[10px] text-muted-foreground hover:text-destructive transition-colors ml-2"
            >
              CLEAR
            </button>
          </>
        )}
      </div>
      
      {/* Search Input */}
      <div className="p-3 border-b border-border">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="filter --tag [query]"
            className="w-full pl-8 pr-8 py-1.5 text-xs font-mono bg-input border border-border rounded text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-primary"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* Tag Categories */}
      <div className="max-h-64 overflow-y-auto custom-scrollbar">
        {Object.entries(filteredTags).map(([category, tags]) => (
          <div key={category} className="border-b border-border/50 last:border-b-0">
            <button
              onClick={() => toggleCategory(category)}
              className="w-full flex items-center justify-between px-3 py-2 hover:bg-secondary/30 transition-colors"
            >
              <span className="text-xs font-medium text-foreground">
                {CATEGORY_LABELS[category]}
              </span>
              <div className="flex items-center gap-2">
                <span className="terminal-label">{tags.length}</span>
                {expandedCategories.includes(category) ? (
                  <ChevronDown className="w-3.5 h-3.5 text-primary" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                )}
              </div>
            </button>
            
            {expandedCategories.includes(category) && (
              <div className="px-3 pb-2.5">
                <div className="flex flex-wrap gap-1">
                  {tags.map(tag => {
                    const isIncluded = filters.include.includes(tag)
                    
                    return (
                      <button
                        key={tag}
                        onClick={() => toggleIncludeTag(tag)}
                        className={`tag-chip cursor-pointer ${
                          isIncluded ? "included" : ""
                        }`}
                      >
                        <span>{tag}</span>
                        {isIncluded && <X className="w-2.5 h-2.5" />}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        ))}
        
        {Object.keys(filteredTags).length === 0 && (
          <div className="p-4 text-center">
            <Filter className="w-5 h-5 mx-auto text-muted-foreground/40 mb-2" />
            <span className="terminal-label">No Matching Tags</span>
          </div>
        )}
      </div>

      <div className="border-t border-border/60 p-3 space-y-4">
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-medium text-foreground">Positive Review Floor</span>
            <span className="data-value text-[10px]">{Math.round(filters.minReviewPercent ?? 0)}%</span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            value={filters.minReviewPercent ?? 0}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                minReviewPercent: Number(e.target.value),
              })
            }
            className="w-full"
          />
          <p className="mt-2 text-[10px] text-muted-foreground">
            Hide games below this Steam positive review percentage.
          </p>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-medium text-foreground">Review Relevance Floor</span>
            <span className="data-value text-[10px]">{Math.round(filters.minReviewRelevance ?? 0)}</span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            value={filters.minReviewRelevance ?? 0}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                minReviewRelevance: Number(e.target.value),
              })
            }
            className="w-full"
          />
          <p className="mt-2 text-[10px] text-muted-foreground">
            Hide games that do not meet the blended review relevance score based on positivity and review volume.
          </p>
        </div>
      </div>
    </div>
  )
}
