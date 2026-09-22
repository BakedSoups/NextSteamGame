"use client"

import { useState, useMemo, type CSSProperties } from "react"
import { Check, Search, X, Filter, ChevronDown, ChevronRight, ListFilter, Gamepad, MessageSquareText, Cloud, Repeat, BadgeInfo, Globe2, Volume2, type LucideIcon } from "lucide-react"

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
  identity: "Identity",
  setting: "Setting",
  music: "Music"
}

const CATEGORY_VISUALS: Record<string, { icon: LucideIcon; accent: string }> = {
  mechanics: { icon: Gamepad, accent: "#66c0f4" },
  narrative: { icon: MessageSquareText, accent: "#66c0f4" },
  vibe: { icon: Cloud, accent: "#66c0f4" },
  structure_loop: { icon: Repeat, accent: "#66c0f4" },
  identity: { icon: BadgeInfo, accent: "#66c0f4" },
  setting: { icon: Globe2, accent: "#66c0f4" },
  music: { icon: Volume2, accent: "#66c0f4" },
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

  const setReviewThreshold = (field: "minReviewPercent" | "minReviewRelevance", rawValue: string) => {
    const parsed = Number(rawValue)
    const value = Number.isFinite(parsed) ? Math.min(100, Math.max(0, Math.round(parsed))) : 0
    onFiltersChange({ ...filters, [field]: value })
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
        <ListFilter className="w-3.5 h-3.5 text-primary" />
        <span className="text-sm font-medium text-foreground">Micro Tag Filters</span>
        {activeFilterCount > 0 ? <span className="ml-auto data-value">{activeFilterCount} active</span> : <span className="ml-auto" />}
      </div>

      {filters.include.length > 0 ? (
        <div className="border-t border-border/50 px-3 py-2">
          <div className="flex flex-wrap gap-1.5">
            {filters.include.slice(0, 5).map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => toggleIncludeTag(tag)}
                className="rounded-full border border-amber-300/65 bg-amber-300/18 px-2.5 py-1 text-sm font-semibold text-amber-50 shadow-[0_0_12px_rgba(252,211,77,0.12)] transition hover:border-destructive/50 hover:text-destructive"
                title={`Remove ${tag}`}
              >
                {tag}
              </button>
            ))}
            {filters.include.length > 5 ? (
              <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-sm text-muted-foreground">
                +{filters.include.length - 5}
              </span>
            ) : null}
            <button
              type="button"
              onClick={clearAllFilters}
              className="rounded-full border border-white/10 px-2.5 py-1 text-sm text-muted-foreground transition hover:border-destructive/50 hover:text-destructive"
            >
              Clear
            </button>
          </div>
        </div>
      ) : null}

      {/* Search Input */}
      <div className="border-b border-border p-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="filter --tag [query]"
            className="w-full rounded border border-border bg-input py-1.5 pl-8 pr-8 font-mono text-sm text-foreground transition-all placeholder:text-muted-foreground/50 focus:border-primary focus:outline-none"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-primary"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {/* Tag Categories */}
      <div className="max-h-64 overflow-y-auto custom-scrollbar">
        {Object.entries(filteredTags).map(([category, tags]) => {
          const visual = CATEGORY_VISUALS[category] ?? CATEGORY_VISUALS.mechanics
          const CategoryIcon = visual.icon
          const selectedCount = tags.filter((tag) => filters.include.includes(tag)).length
          const categoryStyle = { "--tag-accent": visual.accent } as CSSProperties

          return <div key={category} className="border-b border-border/50 last:border-b-0" style={categoryStyle}>
            <button
              onClick={() => toggleCategory(category)}
              className="w-full flex items-center justify-between px-3 py-2 hover:bg-secondary/30 transition-colors"
            >
              <span className="flex min-w-0 items-center gap-2 text-sm font-medium text-foreground">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center text-slate-400" style={{ color: visual.accent }}>
                  <CategoryIcon className="h-3.5 w-3.5" strokeWidth={1.7} />
                </span>
                <span>{CATEGORY_LABELS[category] ?? category}</span>
              </span>
              <div className="flex items-center gap-2">
                {selectedCount > 0 ? <span className="rounded-full border border-amber-300/40 bg-amber-300/14 px-1.5 py-0.5 text-[10px] font-bold text-amber-100">{selectedCount} ON</span> : null}
                <span className="terminal-label">{tags.length}</span>
                {expandedCategories.includes(category) ? (
                  <ChevronDown className="w-3.5 h-3.5 text-primary" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                )}
              </div>
            </button>
            
            {expandedCategories.includes(category) && (
              <div className="filter-category-options px-3 pb-2.5 pt-1">
                <div className="space-y-1">
                  {tags.map(tag => {
                    const isIncluded = filters.include.includes(tag)
                    
                    return (
                      <button
                        key={tag}
                        onClick={() => toggleIncludeTag(tag)}
                        aria-pressed={isIncluded}
                        className={`filter-tag-button ${
                          isIncluded ? "included" : ""
                        }`}
                      >
                        <span className="filter-tag-accent" aria-hidden="true" />
                        <span className="min-w-0 flex-1 truncate leading-4" title={tag}>{tag}</span>
                        <span className="filter-tag-arrow" aria-hidden="true">
                          {isIncluded ? <Check className="h-3.5 w-3.5" /> : <span className="h-1.5 w-1.5 rounded-full bg-current opacity-40" />}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        })}
        
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
            <span className="text-sm font-medium text-foreground">Minimum Positive Reviews</span>
            <label className="review-threshold-input" aria-label="Minimum positive review percentage">
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                inputMode="numeric"
                value={Math.round(filters.minReviewPercent ?? 0)}
                onChange={(event) => setReviewThreshold("minReviewPercent", event.target.value)}
              />
              <span>%</span>
            </label>
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
          <p className="mt-2 text-sm text-muted-foreground">
            Hide games below this Steam positive review percentage.
          </p>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">Review Quality Floor</span>
            <label className="review-threshold-input" aria-label="Review quality floor percentage">
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                inputMode="numeric"
                value={Math.round(filters.minReviewRelevance ?? 0)}
                onChange={(event) => setReviewThreshold("minReviewRelevance", event.target.value)}
              />
              <span>%</span>
            </label>
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
          <p className="mt-2 text-sm text-muted-foreground">
            Hide games with weaker or low-volume review signals.
          </p>
        </div>
      </div>
    </div>
  )
}
