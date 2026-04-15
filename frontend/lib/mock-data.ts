import type { Game, RecommendedGame } from "./types"

export const mockGames: Game[] = [
  {
    id: 1,
    appId: "1623730",
    title: "Palworld",
    description: "Fight, tame, build, and work alongside mysterious creatures called Pals in this completely new multiplayer, open world survival and crafting game!",
    releaseDate: "Jan 19, 2024",
    category: "open world adventure",
    image: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/1623730/capsule_231x87.jpg",
    headerImage: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/1623730/header.jpg",
    genres: {
      primary: ["Action", "Adventure"],
      sub: ["Open World", "Sandbox", "Survival"],
      sub_sub: ["Exploration", "Content Collector", "Base Tactics"],
      traits: ["Non Linear", "Resource Gathering", "Crafting"]
    },
    tags: {
      mechanics: ["Creature Capture", "Base Building", "Combat Systems"],
      narrative: ["Environmental Storytelling", "Emergent Narrative"],
      vibe: ["Colorful", "Whimsical", "Expansive"],
      structure_loop: ["Survival Loop", "Collection Loop", "Crafting Loop"],
      uniqueness: ["Creature Workers", "Dark Comedy Undertones"],
      music: ["Orchestral", "Ambient", "Adventure"]
    }
  },
  {
    id: 2,
    appId: "892970",
    title: "Valheim",
    description: "A brutal exploration and survival game for 1-10 players, set in a procedurally-generated purgatory inspired by viking culture.",
    releaseDate: "Feb 2, 2021",
    category: "survival exploration",
    image: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/892970/capsule_231x87.jpg",
    headerImage: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/892970/header.jpg",
    genres: {
      primary: ["Action", "Adventure"],
      sub: ["Open World", "Survival"],
      sub_sub: ["Exploration", "Base Building"],
      traits: ["Co-op", "Crafting", "Combat"]
    },
    tags: {
      mechanics: ["Base Building", "Combat", "Sailing"],
      narrative: ["Norse Mythology", "Environmental"],
      vibe: ["Atmospheric", "Challenging", "Expansive"],
      structure_loop: ["Boss Progression", "Exploration Loop"],
      uniqueness: ["Viking Theme", "Physics Building"],
      music: ["Nordic", "Ambient", "Epic"]
    }
  },
  {
    id: 3,
    appId: "105600",
    title: "Terraria",
    description: "Dig, fight, explore, build! Nothing is impossible in this action-packed adventure game.",
    releaseDate: "May 16, 2011",
    category: "sandbox adventure",
    image: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/105600/capsule_231x87.jpg",
    headerImage: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/105600/header.jpg",
    genres: {
      primary: ["Action", "Adventure"],
      sub: ["Sandbox", "2D"],
      sub_sub: ["Mining", "Building", "Boss Fights"],
      traits: ["Pixel Art", "Procedural", "Multiplayer"]
    },
    tags: {
      mechanics: ["Mining", "Building", "Combat"],
      narrative: ["Discovery", "Progression"],
      vibe: ["Retro", "Colorful", "Chaotic"],
      structure_loop: ["Loot Loop", "Boss Progression"],
      uniqueness: ["2D Depth", "Item Variety"],
      music: ["Chiptune", "Ambient", "Boss Themes"]
    }
  },
  {
    id: 4,
    appId: "1145360",
    title: "Hades",
    description: "Defy the god of the dead as you hack and slash out of the Underworld in this rogue-like dungeon crawler.",
    releaseDate: "Sep 17, 2020",
    category: "roguelike action",
    image: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/1145360/capsule_231x87.jpg",
    headerImage: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/1145360/header.jpg",
    genres: {
      primary: ["Action", "RPG"],
      sub: ["Roguelike", "Hack and Slash"],
      sub_sub: ["Dungeon Crawler", "Story Rich"],
      traits: ["Fast-Paced", "Replayable", "Voice Acting"]
    },
    tags: {
      mechanics: ["Combat", "Upgrades", "Dialogue"],
      narrative: ["Greek Mythology", "Character Driven"],
      vibe: ["Stylish", "Intense", "Witty"],
      structure_loop: ["Run Loop", "Relationship Building"],
      uniqueness: ["Narrative Roguelike", "Art Style"],
      music: ["Rock", "Metal", "Orchestral"]
    }
  },
  {
    id: 5,
    appId: "251570",
    title: "7 Days to Die",
    description: "7 Days to Die is an open world survival horror game that uniquely combines first person shooter, survival horror, tower defense, and role-playing elements.",
    releaseDate: "Dec 13, 2013",
    category: "survival horror",
    image: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/251570/capsule_231x87.jpg",
    headerImage: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/251570/header.jpg",
    genres: {
      primary: ["Survival", "Horror"],
      sub: ["Open World", "Crafting"],
      sub_sub: ["Zombies", "Base Defense"],
      traits: ["Co-op", "Voxel", "Sandbox"]
    },
    tags: {
      mechanics: ["Base Building", "Looting", "Combat"],
      narrative: ["Post-Apocalyptic", "Environmental"],
      vibe: ["Tense", "Gritty", "Strategic"],
      structure_loop: ["7-Day Horde Cycle", "Survival Loop"],
      uniqueness: ["Voxel Destruction", "Horde Nights"],
      music: ["Dark Ambient", "Tension", "Horror"]
    }
  }
]

export const mockRecommendations: RecommendedGame[] = [
  {
    id: 101,
    appId: "1366540",
    title: "Blacksea Odyssey",
    description: "Enter the Blacksea Odyssey, a violent top-down rogue-lite space shooter run as RPG! Featuring with colossal creatures and nano technologies. Explore dangerous, mutate your weapons and blast your way through!",
    releaseDate: "Apr 14, 2016",
    category: "creature adventure",
    image: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/1366540/capsule_231x87.jpg",
    headerImage: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/1366540/header.jpg",
    genres: {
      primary: ["Action", "Adventure"],
      sub: ["Roguelike", "Shooter"],
      sub_sub: ["Space", "Boss Rush"],
      traits: ["Twin-Stick", "Upgrades", "Procedural"]
    },
    tags: {
      mechanics: ["Harpoon Combat", "Boss Hunting", "Upgrades"],
      narrative: ["Space Hunting", "Competition"],
      vibe: ["Intense", "Colorful", "Chaotic"],
      structure_loop: ["Hunt Loop", "Tournament"],
      uniqueness: ["Harpoon Mechanic", "Boss Dismemberment"],
      music: ["Electronic", "Intense", "Space"]
    },
    matchScore: 0.82,
    confidence: 1.016,
    scores: {
      total: 82,
      vector: 28.3,
      genre: 71.2,
      appeal: 24.5,
      music: 21.8
    },
    contextScores: {
      mechanics: 2.2,
      narrative: 3.8,
      vibe: 0.8,
      structure_loop: 0.8,
      uniqueness: 13.8,
      music: 0
    }
  },
  {
    id: 102,
    appId: "402710",
    title: "Memories of Mars",
    description: "Survive the extreme conditions on Mars. Compete or cooperate with others to gather resources, fill your base with equipment, and build your own equipment and build your base, scavenge from others and defend what is yours.",
    releaseDate: "Jun 5, 2018",
    category: "space survival scifi",
    image: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/402710/capsule_231x87.jpg",
    headerImage: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/402710/header.jpg",
    genres: {
      primary: ["Action", "Survival"],
      sub: ["Open World", "Multiplayer"],
      sub_sub: ["Sci-Fi", "Base Building"],
      traits: ["PvP", "Crafting", "Exploration"]
    },
    tags: {
      mechanics: ["Base Building", "Resource Gathering", "Combat"],
      narrative: ["Martian Mystery", "Survival Story"],
      vibe: ["Desolate", "Atmospheric", "Tense"],
      structure_loop: ["Season Wipe", "Base Defense"],
      uniqueness: ["Mars Setting", "FLOP System"],
      music: ["Sci-Fi Ambient", "Electronic", "Tension"]
    },
    matchScore: 0.79,
    confidence: 0.946,
    scores: {
      total: 79,
      vector: 14.4,
      genre: 65.1,
      appeal: 13.6,
      music: 17.9
    },
    contextScores: {
      mechanics: 1.8,
      narrative: 0.9,
      vibe: 0.9,
      structure_loop: 0.9,
      uniqueness: 0,
      music: 0
    }
  },
  {
    id: 103,
    appId: "526870",
    title: "Osiris: New Dawn",
    description: "Explore and survive on the surface of distant alien planets in Osiris: New Dawn, an exciting space survival adventure game with a focus on base building and creature hunting.",
    releaseDate: "Sep 28, 2016",
    category: "space survival sim",
    image: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/526870/capsule_231x87.jpg",
    headerImage: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/526870/header.jpg",
    genres: {
      primary: ["Survival", "Adventure"],
      sub: ["Open World", "Sci-Fi"],
      sub_sub: ["Space", "Exploration"],
      traits: ["Base Building", "Crafting", "Co-op"]
    },
    tags: {
      mechanics: ["Base Building", "Exploration", "Combat"],
      narrative: ["Space Colonization", "Discovery"],
      vibe: ["Atmospheric", "Alien", "Expansive"],
      structure_loop: ["Survival Loop", "Exploration"],
      uniqueness: ["Alien Planets", "Vehicle Building"],
      music: ["Sci-Fi", "Ambient", "Atmospheric"]
    },
    matchScore: 0.76,
    confidence: 1.12,
    scores: {
      total: 76,
      vector: 11.1,
      genre: 0.81,
      appeal: 88.6,
      music: 0.4
    },
    contextScores: {
      mechanics: 1.2,
      narrative: 26.5,
      vibe: 0.0,
      structure_loop: -3.1,
      uniqueness: 20,
      music: 0
    }
  },
  {
    id: 104,
    appId: "346110",
    title: "ARK: Survival Evolved",
    description: "Stranded on the shores of a mysterious island, you must learn to survive. Use your cunning to kill or tame the primeval creatures roaming the land.",
    releaseDate: "Aug 29, 2017",
    category: "dinosaur adventure",
    image: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/346110/capsule_231x87.jpg",
    headerImage: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/346110/header.jpg",
    genres: {
      primary: ["Action", "Adventure"],
      sub: ["Open World", "Survival"],
      sub_sub: ["Dinosaurs", "Taming"],
      traits: ["Multiplayer", "Base Building", "Crafting"]
    },
    tags: {
      mechanics: ["Taming", "Base Building", "Breeding"],
      narrative: ["Mystery Island", "Tek Lore"],
      vibe: ["Epic", "Dangerous", "Expansive"],
      structure_loop: ["Taming Loop", "Boss Ascension"],
      uniqueness: ["Dinosaur Taming", "Tek Tier"],
      music: ["Orchestral", "Epic", "Ambient"]
    },
    matchScore: 0.74,
    confidence: 0.89,
    scores: {
      total: 74,
      vector: 0.8,
      genre: 97.8,
      appeal: 0.8,
      music: 1.8
    },
    contextScores: {
      mechanics: 0.8,
      narrative: 1.8,
      vibe: 0.8,
      structure_loop: 0,
      uniqueness: 0,
      music: 0
    }
  },
  {
    id: 105,
    appId: "242760",
    title: "ASTRONEER",
    description: "Interact with strange worlds in a unique solar system, including deforming the environment. Build your base with a creativity tool and of structures of fusion. Play as a Minecraft Exploration meets low-poly survival.",
    releaseDate: "Feb 6, 2019",
    category: "creative exploration sim",
    image: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/361420/capsule_231x87.jpg",
    headerImage: "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/361420/header.jpg",
    genres: {
      primary: ["Adventure", "Sandbox"],
      sub: ["Open World", "Exploration"],
      sub_sub: ["Space", "Crafting"],
      traits: ["Co-op", "Relaxing", "Creative"]
    },
    tags: {
      mechanics: ["Terrain Deformation", "Crafting", "Exploration"],
      narrative: ["Space Discovery", "Wonder"],
      vibe: ["Colorful", "Relaxing", "Whimsical"],
      structure_loop: ["Exploration Loop", "Automation"],
      uniqueness: ["Terrain Tool", "Low Poly Art"],
      music: ["Ambient", "Synth", "Relaxing"]
    },
    matchScore: 0.71,
    confidence: 0.98,
    scores: {
      total: 71,
      vector: 3.8,
      genre: 88,
      appeal: 25.7,
      music: 0
    },
    contextScores: {
      mechanics: 0,
      narrative: 0,
      vibe: 0,
      structure_loop: 0,
      uniqueness: 0,
      music: 0
    }
  }
]

export const genreOptions = {
  primary: ["Action", "Adventure", "RPG", "Strategy", "Simulation", "Puzzle", "Horror", "Sports"],
  sub: ["Open World", "Sandbox", "Survival", "Roguelike", "Shooter", "Platformer", "Fighting", "Racing"],
  sub_sub: ["Exploration", "Content Collector", "Base Tactics", "Dungeon Crawler", "Boss Rush", "Stealth", "Mining"],
  traits: ["Non Linear", "Resource Gathering", "Crafting", "Co-op", "Multiplayer", "Story Rich", "Replayable", "Procedural"]
}

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b))
}

const allGames = [...mockGames, ...mockRecommendations]

export const availableGenreOptions = {
  primary: uniqueSorted(allGames.flatMap((game) => game.genres.primary)),
  sub: uniqueSorted(allGames.flatMap((game) => game.genres.sub)),
  sub_sub: uniqueSorted(allGames.flatMap((game) => game.genres.sub_sub)),
  traits: uniqueSorted(allGames.flatMap((game) => game.genres.traits)),
}

export const availableTagOptions = {
  mechanics: uniqueSorted(allGames.flatMap((game) => game.tags.mechanics)),
  narrative: uniqueSorted(allGames.flatMap((game) => game.tags.narrative)),
  vibe: uniqueSorted(allGames.flatMap((game) => game.tags.vibe)),
  structure_loop: uniqueSorted(allGames.flatMap((game) => game.tags.structure_loop)),
  uniqueness: uniqueSorted(allGames.flatMap((game) => game.tags.uniqueness)),
  music: uniqueSorted(allGames.flatMap((game) => game.tags.music)),
}
