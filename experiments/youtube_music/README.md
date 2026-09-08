# YouTube Music Identity Experiment

Experimental pipeline for enriching a Steam game with evidence-based music tags.
It is deliberately isolated from the production database pipeline.

## Flow

1. Resolve the game name from its Steam appid or accept a supplied name.
2. Use the YouTube Data API to search for official soundtrack playlists first.
3. Expand playlist items, fetch video statistics in batches, and rank plausible
   tracks using source, duration, title, and popularity evidence.
4. Prefer publisher and official music channels, deduplicate track names, and
   reject long-form mixes. Each selection records confidence and provenance.
5. If no plausible soundtrack is found, select a long-play or walkthrough candidate.
6. Analyze authorized local WAV audio. For walkthroughs, detect musical change
   points before classification; for OST tracks, classify representative windows.
7. Aggregate instrument and genre evidence into a JSON report.

The YouTube Data API supplies metadata only. This experiment does not download
YouTube media. Pass audio you own, created, or otherwise have permission to
analyze with `--audio`.

## Models

The classifier adapter targets Essentia's pretrained Discogs-EffNet models. They
provide music-style embeddings and downstream genre/instrument classifiers. A
model is injected behind a small protocol so YAMNet or another CNN can be tested
later without rewriting discovery and segmentation.

## Usage

```bash
export YOUTUBE_API_KEY=...
python -m experiments.youtube_music.cli discover --appid 1113000 --game "Persona 4 Golden"

# API-key-free metadata fallback
python -m experiments.youtube_music.cli scrape --appid 1113000 --game "Persona 4 Golden"

# Download the official Essentia model graphs and label metadata
python -m experiments.youtube_music.cli download-models

# Only use this for media you own or have permission to analyze
python -m experiments.youtube_music.cli acquire \
  --manifest experiments/youtube_music/output/1113000.discovery.json \
  --confirm-authorized

# Classify one or more authorized 16 kHz WAV files and aggregate the evidence
python -m experiments.youtube_music.cli classify --appid 1113000 \
  --audio experiments/youtube_music/audio_cache/*.wav

# Or run classification in the isolated Python 3.11 Essentia container
experiments/youtube_music/run_classifier.sh classify --appid 1113000 \
  --audio experiments/youtube_music/audio_cache/track.wav

python -m experiments.youtube_music.cli analyze \
  --manifest experiments/youtube_music/output/1113000.discovery.json \
  --audio path/to/authorized-audio.wav \
  --source-kind walkthrough
```

Discovery uses `search.list`, `playlistItems.list`, and batched `videos.list`
statistics. Search is quota-expensive, so manifests are cached under `output/`.
The `scrape` command uses yt-dlp for metadata only and does not require an API
key. Audio acquisition is a separate command with an explicit rights-confirmation
flag. Generated manifests, audio, and model files are excluded from Git.

## Current status

- YouTube OST/playlist/walkthrough discovery: implemented
- source-aware top-three ranking, deduplication, and provenance: implemented
- WAV decoding and change-point segmentation: implemented
- classifier interface and deterministic spectral baseline: implemented
- Essentia CNN adapter: implemented; TensorFlow-enabled Essentia is required
- official model download, multi-track genre/instrument classification, and
  evidence aggregation: implemented
- production DB integration: intentionally not implemented
