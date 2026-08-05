# -*- coding: utf-8 -*-
"""
Structural integrity tests — anti-regression layer.

These tests detect architectural regressions, broken contracts, and
infrastructure issues that would not be caught by unit/integration tests.
Run before every deploy: python -m pytest tests/test_structural_integrity.py -v

Protects against:
- Incomplete/broken route handlers (upload_audio add_entry call)
- Duplicate function definitions that silently overwrite critical logic
- Security regressions (unprotected admin endpoints)
- Required admin-only endpoints missing _is_admin() guard
- Pool connection double-release patterns
- JS SyntaxWarnings in embedded templates
- Dead/broken imports
- Critical function signatures changing
"""
from __future__ import annotations

import ast
import os
import re
import sys
import warnings

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_APP  = os.path.join(BASE_DIR, "web_app.py")
HIST_MGR = os.path.join(BASE_DIR, "src", "users", "history_manager.py")
SYNC_PL  = os.path.join(BASE_DIR, "src", "components", "sync_pipeline.py")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. No Python SyntaxWarnings in any source file
# ---------------------------------------------------------------------------

def test_no_syntax_warnings_web_app():
    """web_app.py must compile with zero SyntaxWarnings (escape sequences, etc)."""
    src = _read(WEB_APP)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        compile(src, "web_app.py", "exec")
    syntax_warns = [x for x in w if issubclass(x.category, SyntaxWarning)]
    assert not syntax_warns, (
        f"SyntaxWarnings found in web_app.py:\n"
        + "\n".join(f"  line {x.lineno}: {x.message}" for x in syntax_warns)
    )


def test_no_syntax_warnings_history_manager():
    """history_manager.py must compile with zero SyntaxWarnings."""
    src = _read(HIST_MGR)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        compile(src, "history_manager.py", "exec")
    syntax_warns = [x for x in w if issubclass(x.category, SyntaxWarning)]
    assert not syntax_warns, (
        f"SyntaxWarnings in history_manager.py: {syntax_warns}"
    )


# ---------------------------------------------------------------------------
# 2. No duplicate function definitions (the _save_json bug pattern)
# ---------------------------------------------------------------------------

def _get_function_definitions(path: str) -> list[tuple[str, int]]:
    """Return list of (name, lineno) for all top-level function defs."""
    src = _read(path)
    tree = ast.parse(src)
    return [(node.name, node.lineno) for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def test_no_duplicate_function_definitions_history_manager():
    """No function should be defined twice in history_manager (the _save_json bug)."""
    defs = _get_function_definitions(HIST_MGR)
    names = [name for name, _ in defs]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, (
        f"Duplicate function definitions in history_manager.py: {duplicates}\n"
        "This silently overwrites the first definition — likely a bug."
    )


def test_no_duplicate_function_definitions_web_app():
    """No route handler or critical function should be defined twice in web_app."""
    defs = _get_function_definitions(WEB_APP)
    names = [name for name, _ in defs]
    # Only check non-private, non-trivial names (routes, helpers)
    public_names = [n for n in names if not n.startswith("_")]
    duplicates = {n for n in public_names if public_names.count(n) > 1}
    assert not duplicates, (
        f"Duplicate public function definitions in web_app.py: {duplicates}"
    )


# ---------------------------------------------------------------------------
# 3. upload_audio add_entry has all required arguments
# ---------------------------------------------------------------------------

def test_upload_audio_add_entry_has_required_args():
    """
    The add_entry() call in /upload-audio must include username, text, and analysis.
    A previous bug had it called with only source= and audio_filename=, which
    silently saved nothing and would crash at runtime.
    """
    src = _read(WEB_APP)
    # Find the upload_audio function body
    assert "def upload_audio" in src, "upload_audio route not found"

    # Extract the section between upload_audio and the next route
    start = src.index("def upload_audio")
    end_markers = [m.start() for m in re.finditer(r"\n@app\.route", src[start:]) if m.start() > 0]
    func_body = src[start : start + end_markers[0]] if end_markers else src[start:]

    # Verify the add_entry call in that function has the required args
    assert "username=session" in func_body, (
        "add_entry() in upload_audio is missing username= — audio analysis won't be saved"
    )
    assert "text=transcribed_text" in func_body, (
        "add_entry() in upload_audio is missing text= — audio analysis won't be saved"
    )
    assert "analysis=analysis_dict" in func_body, (
        "add_entry() in upload_audio is missing analysis= — audio analysis won't be saved"
    )


# ---------------------------------------------------------------------------
# 4. Admin-only endpoints must be protected
# ---------------------------------------------------------------------------

ADMIN_ENDPOINTS = [
    "debug_sync_one",
    "admin_users_list",
    "admin_user_texts",
    "admin_stats",
    "admin_sync",
    "admin_sync_log",
]


def test_admin_endpoints_have_is_admin_guard():
    """All admin route handlers must call _is_admin() before doing any work."""
    src = _read(WEB_APP)
    tree = ast.parse(src)

    # Find all function definitions and their body source
    func_lines: dict[str, tuple[int, int]] = {}
    source_lines = src.splitlines()
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for func in funcs:
        end = func.end_lineno if hasattr(func, "end_lineno") else func.lineno + 50
        func_lines[func.name] = (func.lineno, end)

    missing_guard = []
    for endpoint in ADMIN_ENDPOINTS:
        if endpoint not in func_lines:
            continue  # endpoint might not exist yet
        start, end = func_lines[endpoint]
        body = "\n".join(source_lines[start - 1 : end])
        if "_is_admin()" not in body:
            missing_guard.append(endpoint)

    assert not missing_guard, (
        f"Admin endpoints missing _is_admin() guard: {missing_guard}\n"
        "Anyone logged in can access these — this is a security regression."
    )


# ---------------------------------------------------------------------------
# 5. No connection double-release in PG functions
# ---------------------------------------------------------------------------

def test_pg_functions_no_double_release():
    """
    PG functions must NOT call _return_pg_conn both in except AND finally
    on the same conn variable without setting conn = None in between.
    This causes pool exhaustion / 'connection already returned' errors.
    """
    src = _read(HIST_MGR)
    # Simple heuristic: in any block between 'def _pg_' and next 'def ',
    # if both 'close=True' and 'finally:' with _return_pg_conn appear,
    # there must be 'conn = None' to prevent double-release.
    pg_funcs = re.split(r'\ndef _pg_', src)
    double_release_funcs = []

    for func_chunk in pg_funcs[1:]:  # skip everything before first _pg_ func
        func_name = func_chunk.split("(")[0]
        # End at next top-level function definition
        end_match = re.search(r'\ndef [a-zA-Z_]', func_chunk)
        body = func_chunk[: end_match.start()] if end_match else func_chunk

        has_close_true = "_return_pg_conn(conn, close=True)" in body
        has_finally_return = ("finally:" in body and "_return_pg_conn(conn)" in body)

        if has_close_true and has_finally_return:
            # This is only safe if conn is set to None in the except block
            if "conn = None" not in body:
                double_release_funcs.append(f"_pg_{func_name}")

    assert not double_release_funcs, (
        f"PG functions with potential double-release (missing conn = None): "
        f"{double_release_funcs}"
    )


# ---------------------------------------------------------------------------
# 6. _is_pg_available() must release connection via _return_pg_conn
# ---------------------------------------------------------------------------

def test_is_pg_available_releases_connection():
    """_is_pg_available must always call _return_pg_conn (via finally or explicit)."""
    src = _read(HIST_MGR)
    # Find _is_pg_available body
    match = re.search(r'def _is_pg_available\(\)(.*?)(?=\ndef |\Z)', src, re.DOTALL)
    assert match, "_is_pg_available not found"
    body = match.group(1)
    assert "_return_pg_conn" in body or "finally" in body, (
        "_is_pg_available() does not release the connection — pool leak on startup"
    )


# ---------------------------------------------------------------------------
# 7. deploy.py runs tests before promoting to master
# ---------------------------------------------------------------------------

def test_deploy_runs_tests_before_merge():
    """deploy.py must run pytest before merging to master."""
    deploy_path = os.path.join(BASE_DIR, "deploy.py")
    if not os.path.exists(deploy_path):
        return  # deploy.py is optional
    src = _read(deploy_path)
    assert "pytest" in src, "deploy.py does not run pytest before deploying"
    # Verify pytest comes before merge
    pytest_pos = src.index("pytest")
    merge_pos  = src.index("merge") if "merge" in src else len(src)
    assert pytest_pos < merge_pos, (
        "deploy.py runs git merge BEFORE running tests — tests should come first"
    )


# ---------------------------------------------------------------------------
# 8. SECRET_KEY handling: no random token in production path
# ---------------------------------------------------------------------------

def test_secret_key_stable_in_dev_not_random():
    """
    In the dev branch, secret_key should use a stable fallback, not
    secrets.token_hex(32) which generates a new key on every restart.
    """
    src = _read(WEB_APP)
    # Find the secret_key assignment
    sk_match = re.search(r'app\.secret_key\s*=\s*(.+)', src)
    assert sk_match, "app.secret_key assignment not found"
    rhs = sk_match.group(1)
    # It should NOT be a bare secrets.token_hex call (would regenerate each restart)
    assert "secrets.token_hex(32)" not in rhs or "_SECRET_KEY" in rhs, (
        "app.secret_key is set directly to secrets.token_hex(32) which regenerates "
        "on every restart, invalidating all user sessions."
    )


# ---------------------------------------------------------------------------
# 9. Critical API endpoints exist
# ---------------------------------------------------------------------------

CRITICAL_ROUTES = [
    '"/analyze"',
    '"/saved-texts"',
    '"/history"',
    '"/login"',
    '"/logout"',
    '"/upload-audio"',
    '"/delete-entry/',
    '"/saved-text/',
    '"/admin/stats/',
]


def test_critical_routes_all_present():
    """All critical API routes must be present in web_app.py."""
    src = _read(WEB_APP)
    missing = [r for r in CRITICAL_ROUTES if r not in src]
    assert not missing, f"Critical routes missing from web_app.py: {missing}"


# ---------------------------------------------------------------------------
# 10. No open-ended except clauses that swallow all errors silently
#     in critical save paths
# ---------------------------------------------------------------------------

def test_add_entry_errors_are_raised():
    """
    add_entry() in history_manager must re-raise on failure, not silently swallow.
    Silent failures mean data loss with no indication to the user.
    """
    src = _read(HIST_MGR)
    # Find add_entry function body
    match = re.search(r'def add_entry\((.*?)(?=\ndef |\Z)', src, re.DOTALL)
    assert match, "add_entry() not found in history_manager.py"
    body = match.group(0)
    # The function should raise on error, not just log and return None
    assert "raise" in body, (
        "add_entry() does not re-raise exceptions — save failures are silent"
    )
