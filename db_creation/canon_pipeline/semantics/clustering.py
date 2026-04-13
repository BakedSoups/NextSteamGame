from __future__ import annotations

from sklearn.metrics.pairwise import cosine_similarity


def connected_similarity_clusters(indices: list[int], embeddings, threshold: float) -> list[list[int]]:
    if not indices:
        return []
    if len(indices) == 1:
        return [indices]

    matrix = cosine_similarity(embeddings[indices], embeddings[indices])
    visited: set[int] = set()
    clusters: list[list[int]] = []

    for local_index in range(len(indices)):
        if local_index in visited:
            continue
        stack = [local_index]
        component: list[int] = []
        visited.add(local_index)
        while stack:
            current = stack.pop()
            component.append(indices[current])
            for other in range(len(indices)):
                if other in visited:
                    continue
                if matrix[current][other] >= threshold:
                    visited.add(other)
                    stack.append(other)
        clusters.append(component)
    return clusters
