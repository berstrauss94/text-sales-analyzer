# -*- coding: utf-8 -*-
"""
PostgreSQL-backed activity/usage audit log.

WHY THIS EXISTS
---------------
Administrators need to see, per user, whether the system is actually being used:
how many times each user logs in, roughly for how long, and which tools they use
on each text. Flask keeps no such record (no session timeout, no event log), so
this module persists every relevant event in a durable PostgreSQL table.

Events recorded (event_type):
  - 'login'  : the user authenticated and entered the system.
  - 'logout' : the user explicitly logged out (unreliable — many close the tab).
  - 'tool'   : the user used a tool (analyze, upload_audio, view/edit/print,
               delete, highlight-define, simulator, ...). The specific tool goes
               in the `tool` column, and the affected text in `entry_id`.

Session DURATION is derived (not stored): for each 'login' we look at the time
of the LAST activity of that same user before the next login, so a duration is
available even when the user never hits /logout.

It reuses the connection pool from history_manager so there is a single, tested
PostgreSQL access path. Everything is best-effort: logging an event must NEVER
break a user's action, so all writes are wrapped in try/except.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _conn():
    """Borrow a pooled connection (or None if PG is unavailable)."""
    try:
        from src.users.history_manager import _get_pg_conn
        return _get_pg_conn()
    except Exception:
        return None


def _release(conn, close: bool = False) -> None:
    try:
        from src.users.history_manager import _return_pg_conn
        _return_pg_conn(conn, close=close)
    except Exception:
        pass


def is_available() -> bool:
    try:
        from src.users.history_manager import _is_pg_available
        return bool(_is_pg_available())
    except Exception:
        return False


def _ensure_table(conn) -> None:
    """Create the activity_log table + index if they do not exist."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_log (
                id         BIGSERIAL   PRIMARY KEY,
                username   TEXT        NOT NULL,
                event_type TEXT        NOT NULL,
                tool       TEXT        NOT NULL DEFAULT '',
                entry_id   TEXT        NOT NULL DEFAULT '',
                detail     TEXT        NOT NULL DEFAULT '',
                ts         TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_user_ts "
            "ON activity_log (username, ts DESC)"
        )
    conn.commit()


def log_event(username: str, event_type: str, tool: str = "",
              entry_id: str = "", detail: str = "") -> bool:
    """
    Record one activity event. Best-effort: returns False (never raises) if PG
    is unavailable or the insert fails, so the caller's action is never blocked.
    """
    if not username or not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO activity_log (username, event_type, tool, entry_id, detail) "
                "VALUES (%s, %s, %s, %s, %s)",
                (username, event_type, tool or "", entry_id or "", detail or ""),
            )
        conn.commit()
        _release(conn)
        return True
    except Exception as exc:
        logger.error(f"activity_log insert error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def get_activity_summary(days: int = 90) -> dict:
    """
    Aggregate per-user activity over the last `days` days.

    Returns:
      {
        "ok": True,
        "since_days": days,
        "users": {
            username: {
                "logins": int,              # number of 'login' events
                "last_seen": iso str|None,  # timestamp of the most recent event
                "total_minutes": float,     # summed session durations (derived)
                "avg_session_minutes": float,
                "tools": { tool_name: count, ... },  # tool usage tally
                "events": int,              # total events recorded
            }, ...
        }
      }
    Session duration per login = time from that login to the last event that
    happens before the next login of the same user (capped so an abandoned tab
    does not inflate the number).
    """
    if not is_available():
        return {"ok": False, "reason": "pg_unavailable", "users": {}}
    conn = _conn()
    if conn is None:
        return {"ok": False, "reason": "no_conn", "users": {}}

    # A single login "session" is capped at this many minutes when we cannot see
    # an explicit logout (the user likely just closed the tab).
    SESSION_CAP_MIN = 45.0

    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT username, event_type, tool, ts
                FROM activity_log
                WHERE ts >= now() - (%s || ' days')::interval
                ORDER BY username ASC, ts ASC
                """,
                (str(int(days)),),
            )
            rows = cur.fetchall()
        _release(conn)
    except Exception as exc:
        logger.error(f"activity_log summary error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return {"ok": False, "reason": str(exc), "users": {}}

    users: dict = {}

    def _bucket(u: str) -> dict:
        return users.setdefault(u, {
            "logins": 0, "last_seen": None, "total_minutes": 0.0,
            "avg_session_minutes": 0.0, "tools": {}, "events": 0,
        })

    # Group events by user (rows already ordered by username, ts ASC).
    from itertools import groupby
    for username, group in groupby(rows, key=lambda r: r[0]):
        evts = list(group)
        b = _bucket(username)
        b["events"] = len(evts)
        b["last_seen"] = evts[-1][3].isoformat() if hasattr(evts[-1][3], "isoformat") else str(evts[-1][3])

        # Tool tally.
        for (_u, etype, tool, _ts) in evts:
            if etype == "login":
                b["logins"] += 1
            elif etype == "tool" and tool:
                b["tools"][tool] = b["tools"].get(tool, 0) + 1

        # Derive session durations: each login extends until the last event
        # before the next login (or the last event overall), capped.
        login_idx = [i for i, e in enumerate(evts) if e[1] == "login"]
        durations = []
        for k, start_i in enumerate(login_idx):
            end_bound = login_idx[k + 1] if k + 1 < len(login_idx) else len(evts)
            start_ts = evts[start_i][3]
            # last event strictly before the next login
            last_ts = evts[end_bound - 1][3]
            try:
                mins = (last_ts - start_ts).total_seconds() / 60.0
            except Exception:
                mins = 0.0
            if mins < 0:
                mins = 0.0
            if mins > SESSION_CAP_MIN:
                mins = SESSION_CAP_MIN
            durations.append(mins)
        if durations:
            b["total_minutes"] = round(sum(durations), 1)
            b["avg_session_minutes"] = round(sum(durations) / len(durations), 1)

    return {"ok": True, "since_days": int(days), "users": users}
