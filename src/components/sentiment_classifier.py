"""
Sentiment classifier component for the text sales and real estate analyzer.

Classifies the emotional tone of a text into one of:
POSITIVE, NEUTRAL, NEGATIVE
"""
from __future__ import annotations

import numpy as np

from src.models.data_models import SentimentResult


SENTIMENTS = ["POSITIVE", "NEUTRAL", "NEGATIVE"]


class SentimentClassifier:
    """
    Classifies the sentiment of a text using a trained ML model.

    Falls back to NEUTRAL with confidence 0.0 if the model fails.
    Returns NEUTRAL with confidence 1.0 when no sentiment-bearing
    words are detected (handled by the model's probability output).
    """

    def __init__(self, model, classes: list[str]) -> None:
        """
        Args:
            model: A fitted scikit-learn classifier with predict_proba().
            classes: Ordered list of class labels matching model.classes_.
        """
        self._model = model
        self._classes = classes

    def predict(self, feature_vector) -> SentimentResult:
        """
        Predict the sentiment of a text from its feature vector.

        Returns SentimentResult with:
        - sentiment: the predicted class (POSITIVE, NEUTRAL, or NEGATIVE)
        - confidence: probability of the predicted class [0.0, 1.0]
        """
        try:
            probabilities = self._model.predict_proba(feature_vector)[0]
            max_prob = float(np.max(probabilities))
            max_idx = int(np.argmax(probabilities))

            predicted_class = self._classes[max_idx]

            # Ensure the class is a valid sentiment
            if predicted_class not in SENTIMENTS:
                return SentimentResult(sentiment="NEUTRAL", confidence=1.0)

            return SentimentResult(
                sentiment=predicted_class, confidence=round(max_prob, 4)
            )

        except Exception:
            return SentimentResult(sentiment="NEUTRAL", confidence=0.0)
