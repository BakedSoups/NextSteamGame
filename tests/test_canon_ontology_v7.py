from db_creation.canon_group_pipeline.v7_experiment.ontology_v7 import (
    Judgment,
    OllamaClient,
    TagPair,
    cosine,
    evaluate,
)


class FakeClient(OllamaClient):
    def embed(self, texts, model):
        return [[1.0, float(index)] for index, _ in enumerate(texts)]

    def judge_pairs(self, pairs, model):
        return [
            Judgment("synonym", 0.96, "same", "genre", "genre", "platformer"),
            Judgment("related", 0.99, "siblings", "genre", "genre", ""),
        ]


def test_cosine_identity():
    assert cosine([1, 2, 3], [1, 2, 3]) == 1.0


def test_only_high_confidence_synonyms_are_replacements():
    report = evaluate(
        [
            TagPair("platformer", "Platformer", "genre", "synonym"),
            TagPair("first-person shooter", "third-person shooter", "genre", "related"),
        ],
        FakeClient(),
        "fake-embed",
        "fake-judge",
    )

    assert report["metrics"]["dangerous_false_merges"] == 0
    assert report["metrics"]["merge_decision_accuracy"] == 1.0
    assert report["metrics"]["safe_merge_precision"] == 1.0
    assert report["results"][0]["safe_to_replace"] is True
    assert report["results"][1]["safe_to_replace"] is False
