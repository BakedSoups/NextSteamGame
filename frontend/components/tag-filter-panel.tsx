"use client"

import { useState, useMemo } from "react"
import { Search, X, Filter, ChevronDown, ChevronRight, Crosshair } from "lucide-react"

interface TagFilterState {
  include: string[]
  exclude: string[]
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
    onFiltersChange({ include: [], exclude: [] })
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

  const activeFilterCount = filters.include.length + filters.exclude.length

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
    </div>
  )
}
