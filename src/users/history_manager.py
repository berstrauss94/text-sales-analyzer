# -*- coding: utf-8 -*-
"""
History manager module.

Stores and retrieves analysis history per user, organized by
year → month → week → day.
Each entry contains the original text (or transcription), the
analysis result and a timestamp.
"""
from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Any

USERS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "usuarios"
)

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def _history_file(username: str, users_dir: str = USERS_DIR) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in username)
    return os.path.join(users_dir, f"{safe}_historial.json")


def _load(username: str, users_dir: str = USERS_DIR) -> dict:
    path = _history_file(username, users_dir)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(username: str, data: dict, users_dir: str = USERS_DIR) -> None:
    os.makedirs(users_dir, exist_ok=True)
    path = _history_file(username, users_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_entry(
    username: str,
    text: str,
    analysis: dict,
    source: str = "text",          # "text" | "audio"
    audio_filename: str = "",
    users_dir: str = USERS_DIR,
) -> dict:
    """
    Add an analysis entry to the user's history.
    Returns the entry dict that was saved.
    """
    now = datetime.now(timezone.utc)

    year_key  = str(now.year)
    month_key = f"{now.month:02d}-{MONTH_NAMES[now.month]}"
    week_num  = now.isocalendar()[1]
    week_key  = f"Semana-{week_num:02d}"
    day_key   = now.strftime("%Y-%m-%d")   # e.g. "2026-05-02"
    day_label = now.strftime("%d/%m/%Y")   # e.g. "02/05/2026"

    entry: dict[str, Any] = {
        "id": now.strftime("%Y%m%d%H%M%S%f"),
        "timestamp": now.isoformat(),
        "source": source,
        "audio_filename": audio_filename,
        "text": text[:500] + ("…" if len(text) > 500 else ""),
        "text_full": text,
        "intent": analysis.get("intent", "UNKNOWN"),
        "intent_confidence": analysis.get("intent_confidence", 0.0),
        "sentiment": analysis.get("sentiment", "NEUTRAL"),
        "sentiment_confidence": analysis.get("sentiment_confidence", 0.0),
        "sales_concepts": analysis.get("sales_concepts", []),
        "real_estate_concepts": analysis.get("real_estate_concepts", []),
        "entities": analysis.get("entities", []),
        "commercial": analysis.get("commercial"),
        "day_label": day_label,
    }

    history = _load(username, users_dir)

    # Build nested structure: year → month → week → day → [entries]
    history.setdefault(year_key, {})
    history[year_key].setdefault(month_key, {})
    history[year_key][month_key].setdefault(week_key, {})
    history[year_key][month_key][week_key].setdefault(day_key, {
        "label": day_label,
        "entries": []
    })
    history[year_key][month_key][week_key][day_key]["entries"].append(entry)

    _save(username, history, users_dir)
    return entry


def get_history(username: str, users_dir: str = USERS_DIR) -> dict:
    """Return the full history tree for a user."""
    return _load(username, users_dir)


def get_flat_entries(
    username: str,
    limit: int = 50,
    users_dir: str = USERS_DIR,
) -> list[dict]:
    """
    Return the most recent `limit` entries as a flat list,
    sorted newest-first.
    """
    history = _load(username, users_dir)
    flat: list[dict] = []

    for year_data in history.values():
        for month_data in year_data.values():
            for week_data in month_data.values():
                for day_data in week_data.values():
                    flat.extend(day_data.get("entries", []))

    flat.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return flat[:limit]
