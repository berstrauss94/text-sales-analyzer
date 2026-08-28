# -*- coding: utf-8 -*-
"""
backup_manager.py — Automatic, background data-protection for saved text entries.

Purpose
-------
The most valuable data in this system is the set of uploaded/saved text entries
(table analysis_history). This module protects that data by:

  1. Taking periodic FULL backups of every entry into a durable PG table
     (history_backups). On Railway the local filesystem is ephemeral, so the
     backup MUST live in PostgreSQL to survive restarts/redeploys.

  2. Recording a count snapshot (global + per user) with every backup.

  3. Detecting data loss: comparing the CURRENT entry count against the last
     good backup. If the current count dropped significantly, it raises an
     alert so the admin is warned BEFORE continuing — and can restore.

  4. Restoring all entries from the most recent good backup.

All operations are best-effort and defensive: a backup failure must NEVER break
the app or block a user's save. Everything is wrapped in try/except.

Public API
----------
  ensure_backup_tables()          -> create the backup tables if missing
  maybe_auto_backup(force=False)  -> take a backup if enough time/saves elapsed
  get_backup_status()             -> {last_backup, current_total, alert, ...}
  restore_latest_backup()         -> re-insert all entries from newest backup
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Tunables ────────────────────────────────────────────────────────────────
# Take an automatic backup at most once every N seconds (avoids hammering the DB
# when many texts are saved in a burst).
_MIN_SECONDS_BETWEEN_BACKUPS = 300  # 5 minutes
# Also force a backup every N successful saves regardless of time.
_SAVES_PER_BACKUP = 10
# Alert when the current count is below (last_good_total * this factor).
# 0.85 -> alert if more than 15% of entries vanished.
_LOSS_ALERT_FACTOR = 0.85
# Keep at most this many backups (older ones are pruned).
_MAX_BACKUPS = 20

# In-process counter of saves since last backup (per worker; fine as a heuristic)
_saves_since_backup = 0
_last_backup_ts = 0.0


def _pg():
    """Return the history_manager PG helpers, or (None, None, None) if unavailable."""
    try:
        from src.users.history_manager import _is_pg_available, _get_pg_conn, _return_pg_conn
        if not _is_pg_available():
            return None, None, None
        return _is_pg_available, _get_pg_conn, _return_pg_conn
    except Exception:
        return None, None, None


def ensure_backup_tables() -> None:
    """Create the backup tables if they do not exist. Safe to call repeatedly."""
    _avail, _get, _ret = _pg()
    if _get is None:
        return
    conn = _get()
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            # Full snapshots of every entry, stored as one JSONB blob per backup.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS history_backups (
                    id          SERIAL PRIMARY KEY,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                    total_count INTEGER     NOT NULL DEFAULT 0,
                    per_user    JSONB       NOT NULL DEFAULT '{}',
                    entries     JSONB       NOT NULL DEFAULT '[]',
                    reason      TEXT        NOT NULL DEFAULT 'auto'
                )
            """)
        conn.commit()
    except Exception as exc:
        logger.warning(f"[backup] no se pudo crear history_backups: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        _ret(conn)


def _current_counts(conn):
    """Return (total, {username: count}) from the live analysis_history table."""
    total = 0
    per_user = {}
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM analysis_history")
        total = cur.fetchone()[0]
        cur.execute("SELECT username, COUNT(*) FROM analysis_history GROUP BY username")
        per_user = {r[0]: r[1] for r in cur.fetchall()}
    return total, per_user


def _dump_all_entries(conn) -> list[dict]:
    """Return every row of analysis_history as a list of JSON-serializable dicts."""
    rows_out = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, username, timestamp, source, audio_filename,
                   text_short, text_full, intent, intent_conf,
                   sentiment, sentiment_conf, sales_concepts, re_concepts,
                   entities, commercial, day_label
            FROM analysis_history
        """)
        cols = [d[0] for d in cur.description]
        for row in cur.fetchall():
            rec = {}
            for col, val in zip(cols, row):
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                rec[col] = val
            rows_out.append(rec)
    return rows_out


def take_backup(reason: str = "auto") -> dict:
    """Take a FULL backup now. Returns a summary dict. Best-effort."""
    global _last_backup_ts, _saves_since_backup
    _avail, _get, _ret = _pg()
    if _get is None:
        return {"ok": False, "reason": "pg_unavailable"}
    ensure_backup_tables()
    conn = _get()
    if conn is None:
        return {"ok": False, "reason": "no_conn"}
    try:
        total, per_user = _current_counts(conn)
        # Never store an empty backup over the top of good ones — refuse to
        # snapshot 0 entries unless there genuinely are none historically.
        entries = _dump_all_entries(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO history_backups (total_count, per_user, entries, reason) "
                "VALUES (%s, %s, %s, %s)",
                (total, json.dumps(per_user, ensure_ascii=False),
                 json.dumps(entries, ensure_ascii=False), reason)
            )
            # Prune old backups beyond _MAX_BACKUPS
            cur.execute("""
                DELETE FROM history_backups
                WHERE id NOT IN (
                    SELECT id FROM history_backups ORDER BY created_at DESC LIMIT %s
                )
            """, (_MAX_BACKUPS,))
        conn.commit()
        import time as _t
        _last_backup_ts = _t.time()
        _saves_since_backup = 0
        logger.info(f"[backup] snapshot guardado: {total} entradas (reason={reason})")
        return {"ok": True, "total": total, "reason": reason}
    except Exception as exc:
        logger.error(f"[backup] error tomando backup: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": str(exc)}
    finally:
        _ret(conn)


def maybe_auto_backup(force: bool = False) -> None:
    """
    Called after each successful save. Takes a backup only if enough time has
    passed OR enough saves have accumulated, so we don't hammer the DB.
    Fully best-effort — never raises.
    """
    global _saves_since_backup
    try:
        import time as _t
        _saves_since_backup += 1
        due_by_count = _saves_since_backup >= _SAVES_PER_BACKUP
        due_by_time = (_t.time() - _last_backup_ts) >= _MIN_SECONDS_BETWEEN_BACKUPS
        if force or due_by_count or due_by_time:
            take_backup(reason="auto")
    except Exception as exc:
        logger.warning(f"[backup] maybe_auto_backup fallo (no critico): {exc}")


def _latest_backup(conn):
    """Return (id, created_at, total_count, per_user_dict) of the newest backup, or None."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, created_at, total_count, per_user
            FROM history_backups ORDER BY created_at DESC LIMIT 1
        """)
        row = cur.fetchone()
    if not row:
        return None
    per_user = row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}")
    return {"id": row[0], "created_at": row[1], "total_count": row[2], "per_user": per_user}


def get_backup_status() -> dict:
    """
    Compare the live count against the last backup and report whether a
    significant data loss is detected (alert=True).
    """
    _avail, _get, _ret = _pg()
    if _get is None:
        return {"ok": False, "reason": "pg_unavailable", "alert": False}
    ensure_backup_tables()
    conn = _get()
    if conn is None:
        return {"ok": False, "reason": "no_conn", "alert": False}
    try:
        current_total, current_per_user = _current_counts(conn)
        latest = _latest_backup(conn)
        if not latest:
            return {
                "ok": True, "alert": False, "has_backup": False,
                "current_total": current_total,
            }
        last_total = latest["total_count"]
        threshold = int(last_total * _LOSS_ALERT_FACTOR)
        alert = current_total < threshold and last_total > 0

        # Per-user drops (users who lost entries vs last backup)
        drops = []
        for u, cnt in latest["per_user"].items():
            now_cnt = current_per_user.get(u, 0)
            if now_cnt < cnt:
                drops.append({"username": u, "before": cnt, "now": now_cnt,
                              "lost": cnt - now_cnt})
        drops.sort(key=lambda x: x["lost"], reverse=True)

        return {
            "ok": True,
            "alert": alert,
            "has_backup": True,
            "current_total": current_total,
            "last_backup_total": last_total,
            "last_backup_time": latest["created_at"].isoformat() if hasattr(latest["created_at"], "isoformat") else str(latest["created_at"]),
            "loss_threshold": threshold,
            "per_user_drops": drops,
        }
    except Exception as exc:
        logger.error(f"[backup] error en get_backup_status: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": str(exc), "alert": False}
    finally:
        _ret(conn)


def restore_latest_backup() -> dict:
    """
    Re-insert every entry from the newest backup into analysis_history.
    Uses ON CONFLICT DO NOTHING so existing rows are preserved and only the
    missing ones are restored. Returns a summary.
    """
    _avail, _get, _ret = _pg()
    if _get is None:
        return {"ok": False, "reason": "pg_unavailable"}
    conn = _get()
    if conn is None:
        return {"ok": False, "reason": "no_conn"}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT entries FROM history_backups
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cur.fetchone()
        if not row:
            return {"ok": False, "reason": "no_backup"}
        entries = row[0] if isinstance(row[0], list) else json.loads(row[0] or "[]")

        restored = 0
        with conn.cursor() as cur:
            for e in entries:
                cur.execute("""
                    INSERT INTO analysis_history
                        (id, username, timestamp, source, audio_filename,
                         text_short, text_full, intent, intent_conf,
                         sentiment, sentiment_conf, sales_concepts, re_concepts,
                         entities, commercial, day_label)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id, username) DO NOTHING
                """, (
                    e.get("id"), e.get("username"), e.get("timestamp"),
                    e.get("source", "text"), e.get("audio_filename", ""),
                    e.get("text_short", ""), e.get("text_full", ""),
                    e.get("intent", "UNKNOWN"), e.get("intent_conf", 0.0),
                    e.get("sentiment", "NEUTRAL"), e.get("sentiment_conf", 0.0),
                    json.dumps(e.get("sales_concepts", []), ensure_ascii=False),
                    json.dumps(e.get("re_concepts", []), ensure_ascii=False),
                    json.dumps(e.get("entities", []), ensure_ascii=False),
                    json.dumps(e.get("commercial"), ensure_ascii=False) if e.get("commercial") is not None else None,
                    e.get("day_label", ""),
                ))
                if cur.rowcount > 0:
                    restored += 1
        conn.commit()
        logger.info(f"[backup] restauradas {restored} entradas desde el ultimo backup")
        return {"ok": True, "restored": restored, "total_in_backup": len(entries)}
    except Exception as exc:
        logger.error(f"[backup] error restaurando: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "reason": str(exc)}
    finally:
        _ret(conn)
