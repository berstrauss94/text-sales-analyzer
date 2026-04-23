"""
Vectorizer component for the text sales and real estate analyzer.

Wraps scikit-learn's TfidfVectorizer to transform ParsedText into
numerical feature vectors suitable for ML model inference.
"""
from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer

from src.models.data_models import ParsedText


class Vectorizer:
    """
    Transforms text into TF-IDF feature vectors.

    In training: call fit() then vectorize().
    In inference: call vectorize() only (never fit again).
    """

    def __init__(self) -> None:
        self._tfidf = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=5000,
            sublinear_tf=True,
            strip_accents="unicode",
            analyzer="word",
            token_pattern=r"(?u)\b\w+\b",
        )
        self._fitted = False

    def fit(self, corpus: list[str]) -> None:
        """
        Fit the TF-IDF vectorizer on the training corpus.
        Only called during model training, never during inference.
        """
        self._tfidf.fit(corpus)
        self._fitted = True

    def vectorize(self, parsed_text: ParsedText):
        """
        Transform a ParsedText into a TF-IDF feature vector.

        Uses the joined token string for vectorization.
        Calls transform() only — never fit_transform() during inference.

        Returns a scipy sparse matrix (csr_matrix).
        """
        if not self._fitted:
            raise RuntimeError(
                "Vectorizer has not been fitted. Call fit() before vectorize()."
            )
        text = " ".join(parsed_text.tokens)
        return self._tfidf.transform([text])
