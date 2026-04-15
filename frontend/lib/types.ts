export interface Game {
  id: number
  appId: string
  title: string
  description: string
  releaseDate: string
  category: string
  image: string
  headerImage: string
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
    uniqueness: string[]
    music: string[]
  }
}

export interface RecommendedGame extends Game {
  matchScore: number
  confidence: number
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
    uniqueness: number
    music: number
  }
}

export interface TagFilters {
  include: string[]
  exclude: string[]
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
    uniqueness: number
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
    uniqueness: Record<string, number>
    music: Record<string, number>
  }
  genres: {
    primary: string[]
    sub: string[]
    sub_sub: string[]
    traits: string[]
  }
}
