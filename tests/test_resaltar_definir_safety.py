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
        sess['username'] = 'BaronVonBerna'

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
        sess['username'] = 'BaronVonBerna'

    # This should at minimum not crash (returns [] locally since no PG)
    resp = client.get('/admin/user-texts/ContrerasCath?year=2026&month=')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'entries' in data


def test_resaltar_definir_is_in_separate_script_tag():
    """
    CRITICAL: Resaltar y Definir must be in its OWN <script> tag,
    separate from the main application script. This ensures that
    if it has a JS error, it does NOT break loadSavedTexts or other
    core functionality.
    """
    from web_app import app
    import re

    # Get the HTML template
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web_app.py'),
              'r', encoding='utf-8') as f:
        content = f.read()

    # Find the main HTML template
    marker = 'HTML = """'
    start = content.find(marker)
    end = content.find('"""', start + len(marker))
    html = content[start + len(marker):end]

    # Count script tags
    script_opens = [m.start() for m in re.finditer(r'<script', html)]
    script_closes = [m.start() for m in re.finditer(r'</script>', html)]

    assert len(script_opens) >= 2, (
        "Expected at least 2 <script> tags (main + resaltar-definir). "
        f"Found {len(script_opens)}. "
        "Resaltar y Definir MUST be in a separate script tag!"
    )

    # Find the Resaltar y Definir section
    rd_marker = 'RESALTAR Y DEFINIR'
    rd_pos = html.find(rd_marker)
    assert rd_pos > 0, "Could not find 'RESALTAR Y DEFINIR' in HTML template"

    # It must NOT be in the first script tag
    # The first script tag ends at the first </script>
    first_script_end = script_closes[0]
    assert rd_pos > first_script_end, (
        "CRITICAL: 'Resaltar y Definir' is inside the main <script> tag! "
        "It MUST be in a separate script tag to avoid breaking core features."
    )


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
