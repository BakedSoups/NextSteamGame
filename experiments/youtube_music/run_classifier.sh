#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
image="steam-recommender-music-classifier"

if ! docker image inspect "$image" >/dev/null 2>&1; then
  docker build -t "$image" -f "$repo_root/experiments/youtube_music/Dockerfile" "$repo_root"
fi
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$repo_root:/app" \
  "$image" "$@"
