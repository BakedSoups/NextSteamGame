from db_creation.canon_group_pipeline.v7_experiment.ontology_v7 import TagPair
from db_creation.canon_group_pipeline.v7_experiment.ontology_v71 import (
    deterministic_decision,
    validated_canonical_label,
)


def test_spelling_variant_is_deterministically_equivalent():
    decision = deterministic_decision(TagPair("collectible hunting", "collectable hunting", "mechanics"))
    assert decision is not None
    assert decision.equivalent
    assert decision.source == "normalizer"


def test_franchise_specific_term_cannot_replace_generic_term():
    decision = deterministic_decision(TagPair("character fusions", "persona fusion system", "micro_tags"))
    assert decision is not None
    assert not decision.equivalent
    assert decision.blocker == "franchise_specificity"


def test_conflicting_genres_are_blocked():
    decision = deterministic_decision(TagPair("platformer", "arcade racing", "genre_tree.primary"))
    assert decision is not None
    assert not decision.equivalent
    assert decision.blocker == "meaningful_qualifier" or decision.blocker == "conflicting_head_concept"


def test_clean_semantic_pair_reaches_model():
    assert deterministic_decision(TagPair("farming systems", "farming mechanic", "mechanics")) is None


def test_label_validator_prevents_broadening():
    pair = TagPair("collectible hunting", "collectable hunting", "mechanics")
    assert validated_canonical_label(pair, "collecting") == "collectible hunting"


def test_label_validator_prevents_word_substitution():
    pair = TagPair("bombastic soundtrack", "bombastic music", "music")
    assert validated_canonical_label(pair, "epic soundtrack") == "bombastic soundtrack"
