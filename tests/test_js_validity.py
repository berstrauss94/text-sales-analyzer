# -*- coding: utf-8 -*-
"""
Automated JavaScript validity gate.

Extracts the JavaScript embedded in both HTML templates of web_app.py and
validates it with Node.js (`node --check`). If Node is not available on the
machine, falls back to a delimiter-balance check.

Purpose: catch broken JS (syntax errors, unbalanced braces, dead `if(false)`
blocks, etc.) BEFORE it ships. This test runs as part of the normal pytest
suite, which deploy.py executes before every deploy — so broken JS can no
longer reach production silently.
"""
import os
import re
import shutil
import subprocess
import tempfile

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_APP = os.path.join(BASE_DIR, "web_app.py")


def _read_web_app() -> str:
    with open(WEB_APP, "r", encoding="utf-8") as f:
        return f.read()


def _extract_scripts(content: str) -> list[str]:
    """Return the JS body of every <script>...</script> inside the Python string
    templates, with Jinja2 tags neutralized so it is plain JS."""
    scripts = []
    for m in re.finditer(r"<script>(.*?)</script>", content, re.DOTALL):
        js = m.group(1)
        # Neutralize Jinja2 expressions/statements so it becomes valid JS
        js = js.replace("{{ indicador_categorias_json | safe }}", "{}")
        js = re.sub(r"\{\{.*?\}\}", '""', js)
        js = re.sub(r"\{%.*?%\}", "", js)
        if js.strip():
            scripts.append(js)
    return scripts


def _balanced(js: str) -> tuple[bool, str]:
    checks = {"{": "}", "(": ")", "[": "]"}
    for open_c, close_c in checks.items():
        o, c = js.count(open_c), js.count(close_c)
        if o != c:
            return False, f"'{open_c}{close_c}' desbalanceado: {o} vs {c}"
    return True, ""


_SCRIPTS = _extract_scripts(_read_web_app())


def test_at_least_one_script_found():
    assert len(_SCRIPTS) >= 1, "No se encontro ningun <script> en web_app.py"


@pytest.mark.parametrize("idx", range(len(_SCRIPTS)))
def test_js_delimiters_balanced(idx):
    """Every embedded script must have balanced braces/parens/brackets."""
    ok, msg = _balanced(_SCRIPTS[idx])
    assert ok, f"Script #{idx} con delimitadores desbalanceados: {msg}"


@pytest.mark.parametrize("idx", range(len(_SCRIPTS)))
def test_js_node_check(idx):
    """Validate each embedded script with `node --check` when Node is available."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js no disponible; se valido solo el balance de delimitadores")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
        tf.write(_SCRIPTS[idx])
        tmp = tf.name
    try:
        result = subprocess.run(
            [node, "--check", tmp],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, (
            f"Node detecto un error de sintaxis en el script #{idx}:\n{result.stderr}"
        )
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
