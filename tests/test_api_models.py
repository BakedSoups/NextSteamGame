from __future__ import annotations

import unittest

from pydantic import ValidationError

from backend.api_models import RecommendationRequest


class RecommendationRequestTests(unittest.TestCase):
    def test_defaults_are_applied(self) -> None:
        request = RecommendationRequest.model_validate({"appid": "123"})

        self.assertEqual(request.appid, 123)
        self.assertEqual(request.limit, 20)
        self.assertIsNone(request.weights.tags)

    def test_limit_must_be_in_supported_range(self) -> None:
        with self.assertRaises(ValidationError):
            RecommendationRequest.model_validate({"appid": 123, "limit": 0})

        with self.assertRaises(ValidationError):
            RecommendationRequest.model_validate({"appid": 123, "limit": 51})

    def test_tag_weights_are_numeric_and_clamped(self) -> None:
        request = RecommendationRequest.model_validate(
            {
                "appid": 123,
                "weights": {
                    "tags": {
                        "mechanics": {
                            "Automation": "42.5",
                            "Penalty": -10,
                        },
                    },
                },
            }
        )

        self.assertEqual(request.weights.tags["mechanics"]["Automation"], 42.5)
        self.assertEqual(request.weights.tags["mechanics"]["Penalty"], 0.0)

    def test_invalid_tag_weight_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RecommendationRequest.model_validate(
                {
                    "appid": 123,
                    "weights": {
                        "tags": {
                            "mechanics": {
                                "Automation": "heavy",
                            },
                        },
                    },
                }
            )


if __name__ == "__main__":
    unittest.main()
