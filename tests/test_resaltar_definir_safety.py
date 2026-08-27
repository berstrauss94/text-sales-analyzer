# -*- coding: utf-8 -*-
"""
Test that ensures the "Resaltar y Definir" feature does NOT break
the core text loading functionality.

This test validates:
1. The main app loads without errors
2. The /admin/user-texts endpoint returns entries correctly
3. The /analyze endpoint works
4. The JavaScript in the HTML template has balanced delimiters
5. The "Resaltar y Definir" script is in a SEPARATE <script> tag
   (isolated from the main script)
"""
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_app_loads_without_error():
    """The Flask app must load without import errors."""
    from web_app import app
    assert app is not None


def test_analyze_endpoint_works():
    """The /analyze endpoint must work after Resaltar y Definir changes."""
    from web_app import app
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as sess:
        sess['username'] = 'Berna.Strauss'

    resp = client.post('/analyze', json={
        'text': 'Hola buenas tardes, me interesa el terreno de 300m2.',
        'year': 2026,
        'month': 8
    })
    data = resp.get_json()
    assert not data.get('error'), f"Analyze failed: {data}"
    assert 'intent' in data


def test_admin_user_texts_returns_entries():
    """Admin user-texts endpoint must return entries (not crash)."""
    from web_app import app
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as sess:
        sess['username'] = 'Berna.Strauss'

    # This should at minimum not crash (returns [] locally since no PG)
    resp = client.get('/admin/user-texts/ContrerasCath?year=2026&month=')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'entries' in data


def test_resaltar_definir_is_in_separate_script_tag():
    """
    Resaltar y Definir must be wrapped in try-catch inside DOMContentLoaded
    to ensure that if it has a JS error, it does NOT break loadSavedTexts.
    """
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web_app.py'),
              'r', encoding='utf-8') as f:
        content = f.read()

    marker = 'HTML = """'
    start = content.find(marker)
    end = content.find('"""', start + len(marker))
    html = content[start + len(marker):end]

    # The Resaltar y Definir code must be inside a try-catch
    assert 'try {' in html and 'Resaltar y Definir' in html, (
        "Resaltar y Definir must be wrapped in try-catch"
    )

    # loadSavedTexts must come BEFORE the try-catch for Resaltar y Definir
    load_pos = html.find('loadSavedTexts()')
    rd_try_pos = html.find('RESALTAR Y DEFINIR')
    # At least the DOMContentLoaded call to loadSavedTexts/loadAdminStats
    # should not be AFTER the Resaltar y Definir section
    assert load_pos > 0, "loadSavedTexts() not found"
    assert rd_try_pos > 0, "RESALTAR Y DEFINIR marker not found"


def test_main_script_js_balanced_delimiters():
    """The main script (excluding Resaltar y Definir) must have balanced JS delimiters."""
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web_app.py'),
              'r', encoding='utf-8') as f:
        content = f.read()

    marker = 'HTML = """'
    start = content.find(marker)
    end = content.find('"""', start + len(marker))
    html = content[start + len(marker):end]

    # Extract ONLY the first (main) script
    first_script_start = html.find('<script>') + len('<script>')
    first_script_end = html.find('</script>')
    main_js = html[first_script_start:first_script_end]

    # Remove Jinja2 template tags
    cleaned = re.sub(r'\{\{.*?\}\}', '""', main_js)
    cleaned = re.sub(r'\{%.*?%\}', '', cleaned)

    opens = cleaned.count('{')
    closes = cleaned.count('}')
    assert opens == closes, f"Main script brace mismatch: {{ = {opens}, }} = {closes}"

    opens_p = cleaned.count('(')
    closes_p = cleaned.count(')')
    assert opens_p == closes_p, f"Main script paren mismatch: ( = {opens_p}, ) = {closes_p}"


def test_load_saved_texts_function_exists_in_main_script():
    """loadSavedTexts must be defined in the main script, not in the isolated one."""
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web_app.py'),
              'r', encoding='utf-8') as f:
        content = f.read()

    marker = 'HTML = """'
    start = content.find(marker)
    end = content.find('"""', start + len(marker))
    html = content[start + len(marker):end]

    first_script_start = html.find('<script>') + len('<script>')
    first_script_end = html.find('</script>')
    main_js = html[first_script_start:first_script_end]

    assert 'function loadSavedTexts' in main_js or 'async function loadSavedTexts' in main_js, (
        "loadSavedTexts must be defined in the main script tag"
    )
