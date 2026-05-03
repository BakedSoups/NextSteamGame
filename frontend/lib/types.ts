export interface Game {
  id: number
  appId: string
  title: string
  description: string
  releaseDate: string
  category: string
  image: string
  headerImage: string
  assets: {
    header: string
    capsule: string
    capsuleV5: string
    background: string
    backgroundRaw: string
    logo: string
    libraryHero: string
    libraryCapsule: string
  }
  genres: {
    primary: string[]
    sub: string[]
    sub_sub: string[]
    traits: string[]
  }
  tags: {
    mechanics: string[]
    narrative: string[]
    vibe: string[]
    structure_loop: string[]
    identity: string[]
    setting: string[]
    music: string[]
  }
  weights?: Partial<Weights>
  metadata?: Record<string, unknown>
}

export interface RecommendedGame extends Game {
  matchScore: number
  confidence: number
  reviewStats: {
    positive: number
    negative: number
    reviewCount: number
  }
  scores: {
    total: number
    vector: number
    genre: number
    appeal: number
    music: number
  }
  contextScores: {
    mechanics: number
    narrative: number
    vibe: number
    structure_loop: number
    identity: number
    setting: number
    music: number
  }
  scorePercentages?: Record<string, number>
}

export interface TagFilters {
  include: string[]
  exclude: string[]
  minReviewPercent?: number
  minReviewRelevance?: number
}

export interface Weights {
  match: {
    vector: number
    genre: number
    appeal: number
    music: number
  }
  context: {
    mechanics: number
    narrative: number
    vibe: number
    structure_loop: number
    identity: number
    setting: number
    music: number
  }
  appeal: {
    challenge: number
    complexity: number
    pace: number
    narrative_focus: number
    social_energy: number
    creativity: number
  }
  tags: {
    mechanics: Record<string, number>
    narrative: Record<string, number>
    vibe: Record<string, number>
    structure_loop: Record<string, number>
    identity: Record<string, number>
    setting: Record<string, number>
    music: Record<string, number>
  }
  genres: {
    primary: string[]
    sub: string[]
    sub_sub: string[]
    traits: string[]
  }
}
