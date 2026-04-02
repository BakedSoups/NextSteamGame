import random
from typing import Dict, List


def sample_reviews(results: Dict, per_category: int = 12, max_total: int = 40) -> List[str]:
    pool = []

    for category in ["descriptive", "artistic", "music"]:
        if category in results:
            pool.extend(results[category][:per_category])

    seen = set()
    unique = []

    for review_data in pool:
        text = review_data["review"].strip()
        if text not in seen:
            seen.add(text)
            unique.append(text)

    random.shuffle(unique)
    return unique[:max_total]

