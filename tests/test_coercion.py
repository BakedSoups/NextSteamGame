import unittest

from backend.coercion import normalize_search_text, unique_appids


class CoercionTests(unittest.TestCase):
    def test_ids_preserve_first_seen_order_after_coercion(self):
        self.assertEqual(unique_appids(["20", None, 10, "bad", 20, "010", " 30 "]), [20, 10, 30])
        self.assertEqual(unique_appids([]), [])

    def test_search_normalization_preserves_index_compatibility(self):
        for raw, expected in [
            ("  HALF-Life: 2! ", "half life 2"),
            ("Baldur's Gate 3", "baldur s gate 3"),
            ("!!!", ""), ("Pokémon", "pok mon"),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_search_text(raw), expected)
