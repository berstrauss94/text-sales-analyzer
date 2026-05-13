# -*- coding: utf-8 -*-
"""
History manager module.

Stores and retrieves analysis history per user, organized by
year → month → week → day.

Storage backend:
  - PostgreSQL when DATABASE_URL env var is set (production / Railway)
  - JSON files in usuarios/ directory as fallback (local development)

Public API is identical in both cases:
  add_entry(username, text, analysis, source, audio_filename, users_dir)
  get_history(username, users_dir) → nested dict
  get_flat_entries(username, limit, users_dir) → list
"""
from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

USERS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "usuarios"
)

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# ---------------------------------------------------------------------------
# PostgreSQL backend
# ---------------------------------------------------------------------------

_pg_conn = None          # module-level connection (lazy)
_use_pg: bool | None = None  # None = not yet determined


def _get_pg_conn():
    """Return a live psycopg2 connection, creating it if needed."""
    global _pg_conn
    try:
        import psycopg2
        import psycopg2.extras
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            return None
        # Railway sometimes gives postgres:// but psycopg2 needs postgresql://
        if db_url.startswith("postgres://"):
            db_url = "postgresql://" + db_url[len("postgres://"):]
        if _pg_conn is None or _pg_conn.closed:
            _pg_conn = psycopg2.connect(db_url)
            _pg_conn.autocommit = False
        # Quick liveness check
        try:
            _pg_conn.cursor().execute("SELECT 1")
        except Exception:
            _pg_conn = psycopg2.connect(db_url)
            _pg_conn.autocommit = False
        return _pg_conn
    except Exception as exc:
        logger.warning(f"PostgreSQL no disponible: {exc}")
        return None


def _ensure_pg_table(conn) -> None:
    """Create the history table if it doesn't exist."""
    import psycopg2.extras
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id            TEXT        NOT NULL,
                username      TEXT        NOT NULL,
                timestamp     TIMESTAMPTZ NOT NULL,
                source        TEXT        NOT NULL DEFAULT 'text',
                audio_filename TEXT       NOT NULL DEFAULT '',
                text_short    TEXT        NOT NULL DEFAULT '',
                text_full     TEXT        NOT NULL DEFAULT '',
                intent        TEXT        NOT NULL DEFAULT 'UNKNOWN',
                intent_conf   REAL        NOT NULL DEFAULT 0,
                sentiment     TEXT        NOT NULL DEFAULT 'NEUTRAL',
                sentiment_conf REAL       NOT NULL DEFAULT 0,
                sales_concepts    JSONB   NOT NULL DEFAULT '[]',
                re_concepts       JSONB   NOT NULL DEFAULT '[]',
                entities          JSONB   NOT NULL DEFAULT '[]',
                commercial        JSONB,
                day_label     TEXT        NOT NULL DEFAULT '',
                PRIMARY KEY (id, username)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ah_username_ts
            ON analysis_history (username, timestamp DESC)
        """)
    conn.commit()


def _is_pg_available() -> bool:
    global _use_pg
    if _use_pg is not None:
        return _use_pg
    conn = _get_pg_conn()
    if conn is None:
        _use_pg = False
        return False
    try:
        _ensure_pg_table(conn)
        _use_pg = True
        logger.info("Historial: usando PostgreSQL.")
        return True
    except Exception as exc:
        logger.warning(f"No se pudo inicializar tabla PostgreSQL: {exc}")
        _use_pg = False
        return False


# ---------------------------------------------------------------------------
# JSON backend (local fallback)
# ---------------------------------------------------------------------------

def _history_file(username: str, users_dir: str = USERS_DIR) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in username)
    return os.path.join(users_dir, f"{safe}_historial.json")


def _load_json(username: str, users_dir: str = USERS_DIR) -> dict:
    path = _history_file(username, users_dir)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_json(username: str, data: dict, users_dir: str = USERS_DIR) -> None:
    os.makedirs(users_dir, exist_ok=True)
    path = _history_file(username, users_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Entry builder (shared)
# ---------------------------------------------------------------------------

def _build_entry(
    username: str,
    text: str,
    analysis: dict,
    source: str,
    audio_filename: str,
    now: datetime,
) -> dict[str, Any]:
    day_label = now.strftime("%d/%m/%Y")
    return {
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


def _entry_to_nested_keys(entry: dict, now: datetime) -> tuple[str, str, str, str, str]:
    """Return (year_key, month_key, week_key, day_key, day_label)."""
    year_key  = str(now.year)
    month_key = f"{now.month:02d}-{MONTH_NAMES[now.month]}"
    week_num  = now.isocalendar()[1]
    week_key  = f"Semana-{week_num:02d}"
    day_key   = now.strftime("%Y-%m-%d")
    day_label = now.strftime("%d/%m/%Y")
    return year_key, month_key, week_key, day_key, day_label


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_entry(
    username: str,
    text: str,
    analysis: dict,
    source: str = "text",
    audio_filename: str = "",
    users_dir: str = USERS_DIR,
    year: int | None = None,
    month: int | None = None,
    entry_name: str = "",
) -> dict:
    """
    Add an analysis entry to the user's history.
    If year/month are provided, they override the entry's date for categorization.
    Returns the entry dict that was saved.
    """
    now = datetime.now(timezone.utc)
    # If year/month provided, use them for categorization but keep real timestamp
    if year and month:
        cat_date = datetime(year, month, now.day if now.day <= 28 else 28,
                           now.hour, now.minute, now.second, tzinfo=timezone.utc)
    else:
        cat_date = now

    entry = _build_entry(username, text, analysis, source, audio_filename, now)
    # Add year/month/name metadata to entry
    if year:
        entry["year"] = year
    if month:
        entry["month"] = month
    if entry_name:
        entry["entry_name"] = entry_name

    try:
        if _is_pg_available():
            _pg_add_entry(entry, username)
            logger.info(f"PG: entrada guardada para {username} (id={entry['id'][:12]})")
        else:
            _json_add_entry(username, entry, cat_date, users_dir)
            logger.info(f"JSON: entrada guardada para {username}")
    except Exception as exc:
        logger.error(f"ERROR guardando entrada para {username}: {exc}")
        raise

    return entry


def get_history(username: str, users_dir: str = USERS_DIR) -> dict:
    """Return the full history tree for a user (year→month→week→day→entries)."""
    if _is_pg_available():
        return _pg_get_history(username)
    return _load_json(username, users_dir)


def get_flat_entries(
    username: str,
    limit: int = 50,
    users_dir: str = USERS_DIR,
) -> list[dict]:
    """Return the most recent `limit` entries as a flat list, newest-first."""
    if _is_pg_available():
        return _pg_get_flat(username, limit)
    return _json_get_flat(username, limit, users_dir)


def delete_entry(username: str, entry_id: str, users_dir: str = USERS_DIR) -> bool:
    """Delete an entry by ID from the user's history. Returns True if deleted."""
    if _is_pg_available():
        return _pg_delete_entry(username, entry_id)
    return _json_delete_entry(username, entry_id, users_dir)


def _pg_delete_entry(username: str, entry_id: str) -> bool:
    """Delete an entry from PostgreSQL."""
    conn = _get_pg_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM analysis_history WHERE username = %s AND id = %s",
                (username, entry_id)
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as exc:
        logger.error(f"PG delete error: {exc}")
        conn.rollback()
        return False


def _json_delete_entry(username: str, entry_id: str, users_dir: str) -> bool:
    """Delete an entry from JSON file storage."""
    import json
    history = _load_json(username, users_dir)
    if not history:
        return False

    # Walk the nested tree and find/remove the entry
    found = False
    for year_key, months in list(history.items()):
        if not isinstance(months, dict):
            continue
        for month_key, weeks in list(months.items()):
            if not isinstance(weeks, dict):
                continue
            for week_key, days in list(weeks.items()):
                if not isinstance(days, dict):
                    continue
                for day_key, day_data in list(days.items()):
                    if not isinstance(day_data, dict):
                        continue
                    entries = day_data.get("entries", [])
                    new_entries = [e for e in entries if e.get("id") != entry_id]
                    if len(new_entries) < len(entries):
                        day_data["entries"] = new_entries
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if found:
            break

    if found:
        _save_json(username, history, users_dir)
    return found


def _save_json(username: str, data: dict, users_dir: str) -> None:
    """Save the full history tree to JSON."""
    import json
    user_dir = os.path.join(users_dir, username)
    path = os.path.join(user_dir, "history.json")
    os.makedirs(user_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# PostgreSQL implementation
# ---------------------------------------------------------------------------

def _pg_add_entry(entry: dict, username: str) -> None:
    import psycopg2.extras
    conn = _get_pg_conn()
    if conn is None:
        raise RuntimeError("PostgreSQL connection lost")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO analysis_history
                    (id, username, timestamp, source, audio_filename,
                     text_short, text_full, intent, intent_conf,
                     sentiment, sentiment_conf, sales_concepts, re_concepts,
                     entities, commercial, day_label)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id, username) DO NOTHING
            """, (
                entry["id"],
                username,
                entry["timestamp"],
                entry["source"],
                entry.get("audio_filename", ""),
                entry["text"],
                entry.get("text_full", entry["text"]),
                entry["intent"],
                entry.get("intent_confidence", 0.0),
                entry["sentiment"],
                entry.get("sentiment_confidence", 0.0),
                json.dumps(entry.get("sales_concepts", []), ensure_ascii=False),
                json.dumps(entry.get("real_estate_concepts", []), ensure_ascii=False),
                json.dumps(entry.get("entities", []), ensure_ascii=False),
                json.dumps(entry.get("commercial"), ensure_ascii=False) if entry.get("commercial") else None,
                entry.get("day_label", ""),
            ))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise exc


def _pg_row_to_entry(row) -> dict:
    """Convert a DB row (tuple) to an entry dict."""
    (eid, username, ts, source, audio_fn, text_short, text_full,
     intent, intent_conf, sentiment, sentiment_conf,
     sales, re_c, entities, commercial, day_label) = row

    ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

    # Extract year/month from timestamp for UI filtering
    entry_year = None
    entry_month = None
    if hasattr(ts, "year"):
        entry_year = ts.year
        entry_month = ts.month
    else:
        try:
            parsed_ts = datetime.fromisoformat(ts_str)
            entry_year = parsed_ts.year
            entry_month = parsed_ts.month
        except Exception:
            pass

    return {
        "id": eid,
        "timestamp": ts_str,
        "year": entry_year,
        "month": entry_month,
        "source": source,
        "audio_filename": audio_fn or "",
        "text": text_short,
        "text_full": text_full,
        "intent": intent,
        "intent_confidence": float(intent_conf),
        "sentiment": sentiment,
        "sentiment_confidence": float(sentiment_conf),
        "sales_concepts": sales if isinstance(sales, list) else json.loads(sales or "[]"),
        "real_estate_concepts": re_c if isinstance(re_c, list) else json.loads(re_c or "[]"),
        "entities": entities if isinstance(entities, list) else json.loads(entities or "[]"),
        "commercial": commercial if isinstance(commercial, (dict, type(None))) else json.loads(commercial or "null"),
        "day_label": day_label or "",
    }


def _pg_get_history(username: str) -> dict:
    conn = _get_pg_conn()
    if conn is None:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, timestamp, source, audio_filename,
                       text_short, text_full, intent, intent_conf,
                       sentiment, sentiment_conf, sales_concepts, re_concepts,
                       entities, commercial, day_label
                FROM analysis_history
                WHERE username = %s
                ORDER BY timestamp ASC
            """, (username,))
            rows = cur.fetchall()
    except Exception as exc:
        logger.error(f"Error leyendo historial PG: {exc}")
        return {}

    history: dict = {}
    for row in rows:
        entry = _pg_row_to_entry(row)
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
        except Exception:
            ts = datetime.now(timezone.utc)

        year_key  = str(ts.year)
        month_key = f"{ts.month:02d}-{MONTH_NAMES.get(ts.month, str(ts.month))}"
        week_num  = ts.isocalendar()[1]
        week_key  = f"Semana-{week_num:02d}"
        day_key   = ts.strftime("%Y-%m-%d")
        day_label = entry.get("day_label") or ts.strftime("%d/%m/%Y")

        history.setdefault(year_key, {})
        history[year_key].setdefault(month_key, {})
        history[year_key][month_key].setdefault(week_key, {})
        history[year_key][month_key][week_key].setdefault(day_key, {
            "label": day_label,
            "entries": []
        })
        history[year_key][month_key][week_key][day_key]["entries"].append(entry)

    return history


def _pg_get_flat(username: str, limit: int = 50) -> list[dict]:
    conn = _get_pg_conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, timestamp, source, audio_filename,
                       text_short, text_full, intent, intent_conf,
                       sentiment, sentiment_conf, sales_concepts, re_concepts,
                       entities, commercial, day_label
                FROM analysis_history
                WHERE username = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (username, limit))
            rows = cur.fetchall()
        return [_pg_row_to_entry(r) for r in rows]
    except Exception as exc:
        logger.error(f"Error leyendo flat PG: {exc}")
        return []


# ---------------------------------------------------------------------------
# JSON implementation
# ---------------------------------------------------------------------------

def _json_add_entry(
    username: str,
    entry: dict,
    now: datetime,
    users_dir: str,
) -> None:
    year_key, month_key, week_key, day_key, day_label = _entry_to_nested_keys(entry, now)
    history = _load_json(username, users_dir)
    history.setdefault(year_key, {})
    history[year_key].setdefault(month_key, {})
    history[year_key][month_key].setdefault(week_key, {})
    history[year_key][month_key][week_key].setdefault(day_key, {
        "label": day_label,
        "entries": []
    })
    history[year_key][month_key][week_key][day_key]["entries"].append(entry)
    _save_json(username, history, users_dir)


def _json_get_flat(
    username: str,
    limit: int = 50,
    users_dir: str = USERS_DIR,
) -> list[dict]:
    history = _load_json(username, users_dir)
    flat: list[dict] = []
    for year_data in history.values():
        for month_data in year_data.values():
            for week_data in month_data.values():
                for day_data in week_data.values():
                    flat.extend(day_data.get("entries", []))
    flat.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return flat[:limit]


# ---------------------------------------------------------------------------
# Migration: JSON → PostgreSQL
# ---------------------------------------------------------------------------

def migrate_json_to_pg(users_dir: str = USERS_DIR) -> dict:
    """
    One-time migration of all existing JSON history files into PostgreSQL.
    Safe to call multiple times — uses ON CONFLICT DO NOTHING.
    Returns a summary dict.
    """
    if not _is_pg_available():
        return {"skipped": True, "reason": "PostgreSQL not available"}

    summary = {"migrated": 0, "skipped": 0, "errors": 0, "users": []}

    if not os.path.exists(users_dir):
        return summary

    json_files = [
        f for f in os.listdir(users_dir)
        if f.endswith("_historial.json")
    ]

    for fname in json_files:
        username = fname.replace("_historial.json", "")
        path = os.path.join(users_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception as exc:
            logger.warning(f"No se pudo leer {fname}: {exc}")
            summary["errors"] += 1
            continue

        user_count = 0
        for year_data in history.values():
            for month_data in year_data.values():
                for week_data in month_data.values():
                    for day_data in week_data.values():
                        for entry in day_data.get("entries", []):
                            try:
                                _pg_add_entry(entry, username)
                                user_count += 1
                                summary["migrated"] += 1
                            except Exception as exc:
                                logger.warning(f"Error migrando entrada {entry.get('id')}: {exc}")
                                summary["errors"] += 1

        if user_count > 0:
            summary["users"].append({"username": username, "entries": user_count})
            logger.info(f"Migrado {username}: {user_count} entradas")

    logger.info(f"Migración JSON→PG completada: {summary}")
    return summary
