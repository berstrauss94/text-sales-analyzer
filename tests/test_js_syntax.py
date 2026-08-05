# -*- coding: utf-8 -*-
"""
Test that validates JavaScript syntax in web_app.py before deploy.
Prevents JS errors that break text loading and admin stats.
"""
import subprocess
import tempfile
import os


def test_javascript_syntax_is_valid():
    """Extract JS from web_app.py and validate with Node.js."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    web_app_path = os.path.join(base_dir, "web_app.py")

    with open(web_app_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract JS between <script> and </script>
    parts = content.split("<script>")
    assert len(parts) >= 2, "No <script> tag found in web_app.py"
    js_content = parts[1].split("</script>")[0]

    # Replace Jinja2 template syntax
    js_content = js_content.replace("{{ indicador_categorias_json | safe }}", "{}")

    # Write to temp file and validate
    temp_path = os.path.join(base_dir, "_validate_js_temp.js")
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(js_content)

    try:
        result = subprocess.run(
            ["node", "--check", temp_path],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"JavaScript syntax error:\n{result.stderr}"
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def test_no_emoji_in_js_strings():
    """Ensure no raw emoji characters in JS that could cause encoding issues."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    web_app_path = os.path.join(base_dir, "web_app.py")

    with open(web_app_path, "r", encoding="utf-8") as f:
        content = f.read()

    js_content = content.split("<script>")[1].split("</script>")[0]

    # Check for surrogate pairs that break JS
    problematic = []
    for i, char in enumerate(js_content):
        code = ord(char)
        if 0xD800 <= code <= 0xDFFF:
            line_num = js_content[:i].count('\n') + 1
            problematic.append(f"Line {line_num}: surrogate U+{code:04X}")

    assert not problematic, f"Surrogate pairs found in JS:\n" + "\n".join(problematic)


def test_loadSavedTexts_exists():
    """Verify loadSavedTexts function exists in the JS."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    web_app_path = os.path.join(base_dir, "web_app.py")

    with open(web_app_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "function loadSavedTexts" in content or "async function loadSavedTexts" in content, \
        "loadSavedTexts function not found — text loading will break"


def test_loadAdminStats_exists():
    """Verify loadAdminStats function exists in the JS."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    web_app_path = os.path.join(base_dir, "web_app.py")

    with open(web_app_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "function loadAdminStats" in content or "async function loadAdminStats" in content, \
        "loadAdminStats function not found — admin stats pie chart will break"
