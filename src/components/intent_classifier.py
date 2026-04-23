"""
Intent classifier component for the text sales and real estate analyzer.

Classifies the primary intent of a text into one of:
OFFER, INQUIRY, NEGOTIATION, CLOSING, DESCRIPTION, UNKNOWN
"""
from __future__ import annotations

import numpy as np

from src.models.data_models import IntentResult


INTENTS = ["OFFER", "INQUIRY", "NEGOTIATION", "CLOSING", "DESCRIPTION", "UNKNOWN"]
UNKNOWN_THRESHOLD = 0.3


class IntentClassifier:
    """
    Classifies the intent of a text using a trained ML model.

    Falls back to UNKNOWN with confidence 0.0 if the model fails
    or if no class exceeds the confidence threshold.
    """

    def __init__(self, model, classes: list[str]) -> None:
        """
        Args:
            model: A fitted scikit-learn classifier with predict_proba().
            classes: Ordered list of class labels matching model.classes_.
        """
        self._model = model
        self._classes = classes

    def predict(self, feature_vector) -> IntentResult:
        """
        Predict the intent of a text from its feature vector.

        Returns IntentResult with:
        - intent: the predicted class or UNKNOWN if below threshold
        - confidence: probability of the predicted class [0.0, 1.0]
        """
        try:
            probabilities = self._model.predict_proba(feature_vector)[0]
            max_prob = float(np.max(probabilities))
            max_idx = int(np.argmax(probabilities))

            if max_prob < UNKNOWN_THRESHOLD:
                return IntentResult(intent="UNKNOWN", confidence=0.0)

            predicted_class = self._classes[max_idx]
            # Ensure the class is a valid intent; map unknown classes to UNKNOWN
            if predicted_class not in INTENTS:
                return IntentResult(intent="UNKNOWN", confidence=0.0)

            return IntentResult(intent=predicted_class, confidence=round(max_prob, 4))

        except Exception:
            return IntentResult(intent="UNKNOWN", confidence=0.0)
