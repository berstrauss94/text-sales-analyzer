"""
Model training script for the text sales and real estate analyzer.

Trains and serializes all ML models:
- TF-IDF Vectorizer (shared across all classifiers)
- Intent classifier (multi-class LogisticRegression)
- Sentiment classifier (multi-class LogisticRegression)
- Sales concept classifier (multi-label, one-vs-rest)
- Real estate concept classifier (multi-label, one-vs-rest)

Run with:
    python -m src.training.train_models
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.feature_extraction.text import TfidfVectorizer

# Ensure project root is on path when run as module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from data.training_data import (
    INTENT_DATA,
    SENTIMENT_DATA,
    SALES_CONCEPT_DATA,
    REAL_ESTATE_CONCEPT_DATA,
)

MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models"
)


def _ensure_models_dir() -> None:
    os.makedirs(MODELS_DIR, exist_ok=True)


def _save(obj, filename: str) -> None:
    path = os.path.join(MODELS_DIR, filename)
    joblib.dump(obj, path)
    print(f"  Saved: {path}")


def train_vectorizer(corpus: list[str]) -> TfidfVectorizer:
    """Train and return a fitted TF-IDF vectorizer on the full corpus."""
    print("Training TF-IDF Vectorizer...")
    tfidf = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=5000,
        sublinear_tf=True,
        strip_accents="unicode",
        analyzer="word",
        token_pattern=r"(?u)\b\w+\b",
    )
    tfidf.fit(corpus)
    return tfidf


def train_intent_classifier(
    tfidf: TfidfVectorizer,
) -> tuple[LogisticRegression, list[str]]:
    """Train a multi-class intent classifier."""
    print("Training Intent Classifier...")
    texts, labels = zip(*INTENT_DATA)
    X = tfidf.transform(texts)
    clf = LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs")
    clf.fit(X, labels)
    return clf, [str(c) for c in clf.classes_]


def train_sentiment_classifier(
    tfidf: TfidfVectorizer,
) -> tuple[LogisticRegression, list[str]]:
    """Train a multi-class sentiment classifier."""
    print("Training Sentiment Classifier...")
    texts, labels = zip(*SENTIMENT_DATA)
    X = tfidf.transform(texts)
    clf = LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs")
    clf.fit(X, labels)
    return clf, [str(c) for c in clf.classes_]


def train_concept_classifier(
    tfidf: TfidfVectorizer,
    concept_data: list[tuple[str, str]],
    name: str,
) -> tuple[OneVsRestClassifier, MultiLabelBinarizer]:
    """
    Train a multi-label concept classifier using One-vs-Rest strategy.

    Each text can belong to multiple concept classes simultaneously.
    """
    print(f"Training {name} Concept Classifier...")

    # Group texts by concept to build multi-label dataset
    # Each unique text gets all its associated labels
    text_to_labels: dict[str, list[str]] = {}
    for text, label in concept_data:
        if text not in text_to_labels:
            text_to_labels[text] = []
        text_to_labels[text].append(label)

    texts = list(text_to_labels.keys())
    label_lists = list(text_to_labels.values())

    mlb = MultiLabelBinarizer()
    Y = mlb.fit_transform(label_lists)

    X = tfidf.transform(texts)

    base_clf = LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs")
    clf = OneVsRestClassifier(base_clf)
    clf.fit(X, Y)

    return clf, mlb


def main() -> None:
    _ensure_models_dir()
    print(f"\n{'='*50}")
    print("Training all models for text-sales-real-estate-analyzer")
    print(f"{'='*50}\n")

    # Build full corpus from all training data
    all_texts = (
        [t for t, _ in INTENT_DATA]
        + [t for t, _ in SENTIMENT_DATA]
        + [t for t, _ in SALES_CONCEPT_DATA]
        + [t for t, _ in REAL_ESTATE_CONCEPT_DATA]
    )

    # 1. Train vectorizer on full corpus
    tfidf = train_vectorizer(all_texts)
    _save(tfidf, "vectorizer.joblib")

    # 2. Train intent classifier
    intent_clf, intent_classes = train_intent_classifier(tfidf)
    _save(intent_clf, "intent_classifier.joblib")
    _save(intent_classes, "intent_classes.joblib")
    print(f"  Intent classes: {intent_classes}")

    # 3. Train sentiment classifier
    sentiment_clf, sentiment_classes = train_sentiment_classifier(tfidf)
    _save(sentiment_clf, "sentiment_classifier.joblib")
    _save(sentiment_classes, "sentiment_classes.joblib")
    print(f"  Sentiment classes: {sentiment_classes}")

    # 4. Train sales concept classifier
    sales_clf, sales_mlb = train_concept_classifier(
        tfidf, SALES_CONCEPT_DATA, "Sales"
    )
    _save(sales_clf, "sales_concept_classifier.joblib")
    _save(sales_mlb, "sales_concept_mlb.joblib")
    print(f"  Sales concept classes: {list(sales_mlb.classes_)}")

    # 5. Train real estate concept classifier
    re_clf, re_mlb = train_concept_classifier(
        tfidf, REAL_ESTATE_CONCEPT_DATA, "Real Estate"
    )
    _save(re_clf, "real_estate_concept_classifier.joblib")
    _save(re_mlb, "real_estate_concept_mlb.joblib")
    print(f"  Real estate concept classes: {list(re_mlb.classes_)}")

    print(f"\n{'='*50}")
    print("All models trained and saved successfully.")
    print(f"Models directory: {MODELS_DIR}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
