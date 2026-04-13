from __future__ import annotations

from sentence_transformers import SentenceTransformer


def load_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def encode_tags(model: SentenceTransformer, tags: list[str]):
    return model.encode(
        tags,
        batch_size=256,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
