from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecommendationWeights(BaseModel):
    model_config = ConfigDict(extra="ignore")

    match: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    appeal: dict[str, Any] | None = None
    tags: dict[str, dict[str, float]] | None = None
    genres: dict[str, Any] | None = None

    @field_validator("tags")
    @classmethod
    def clamp_tag_weights(cls, tags: dict[str, dict[str, float]] | None) -> dict[str, dict[str, float]] | None:
        if tags is None:
            return None
        return {
            context: {
                tag: max(0.0, weight)
                for tag, weight in entries.items()
            }
            for context, entries in tags.items()
        }


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    appid: int
    limit: int = Field(default=20, ge=1, le=50)
    weights: RecommendationWeights = Field(default_factory=RecommendationWeights)
