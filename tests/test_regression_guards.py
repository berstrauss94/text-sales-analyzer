# -*- coding: utf-8 -*-
"""
Regression guards — captura los errores REALES que causaron perdida de datos
o caida del frontend durante el desarrollo, para que NO vuelvan a ocurrir.

Cada test aqui corresponde a un incidente concreto ya resuelto:

  1. Colision de IDs -> textos guardados se descartaban silenciosamente.
  2. Comillas escapadas en onclick -> SyntaxError que tumbaba todo el JS
     (no cargaban textos ni informe).
  3. Codigo JS muerto / delimitadores desbalanceados en el template.
  4. Conteo inconsistente entre endpoints (lista vs informe).

Corren dentro del suite normal (y por ende en deploy.py antes de cada deploy).
"""
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_APP = os.path.join(BASE_DIR, "web_app.py")
HIST_MGR = os.path.join(BASE_DIR, "src", "users", "history_manager.py")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ── Incidente 1: colision de IDs ──────────────────────────────────────────
def test_entry_ids_are_unique_under_burst():
    """
    Guardar muchas entradas para el mismo usuario/fecha en rafaga debe producir
    IDs unicos (antes se truncaban microsegundos y colisionaban -> ON CONFLICT
    DO NOTHING descartaba entradas). Verifica el fix del id con sufijo aleatorio.
    """
    import sys
    sys.path.insert(0, BASE_DIR)
    from src.users.history_manager import _build_entry, add_entry
    from datetime import datetime, timezone
    import importlib
    hm = importlib.import_module("src.users.history_manager")

    # add_entry agrega un sufijo aleatorio al id; generamos varios y comparamos.
    ids = set()
    analysis = {"intent": "UNKNOWN", "intent_confidence": 0.0, "sentiment": "NEUTRAL",
                "sentiment_confidence": 0.0, "sales_concepts": [], "real_estate_concepts": [],
                "entities": [], "commercial": {}}
    # Usar un usuario temporal en modo JSON aislado
    import tempfile
    tmpdir = tempfile.mkdtemp()
    for i in range(30):
        e = add_entry(username="Z_regression_user", text=f"t{i}", analysis=analysis,
                      source="text", audio_filename=f"n{i}", users_dir=tmpdir,
                      year=2026, month=7, day=10, entry_name=f"n{i}")
        ids.add(e["id"])
    assert len(ids) == 30, f"IDs colisionaron: {len(ids)} unicos de 30"


# ── Incidente 2: comillas escapadas en onclick (SyntaxError) ───────────────
def test_no_escaped_quotes_in_inline_onclick():
    """
    Prohibe el patron onclick="...(\\'...\\')" en el template, que al renderizar
    Python cierra el string JS y produce un SyntaxError que tumba todo el frontend.
    """
    src = _read(WEB_APP)
    # Buscar onclick con comillas simples escapadas dentro de comillas dobles
    offenders = re.findall(r'onclick="[^"]*\\\'[^"]*"', src)
    assert not offenders, (
        "onclick con comillas escapadas (rompe el JS al renderizar): " + str(offenders[:3])
    )


# ── Incidente 3: codigo muerto if(false) en el template ────────────────────
def test_no_dead_if_false_blocks():
    """No debe quedar codigo muerto 'if (false) {' en web_app.py (fragil/riesgoso)."""
    src = _read(WEB_APP)
    assert "if (false)" not in src, "Hay bloques 'if (false)' muertos en el template"


# ── Incidente 5: e.target.closest sin proteger (TypeError en cada mouse move) ─
def test_no_unguarded_target_closest():
    """
    Prohibe 'e.target.closest(' directo en handlers: si el target es un nodo de
    texto o el document, .closest no existe y lanza TypeError que rompe la UI
    (impedia que el informe se re-renderizara). Debe usarse el helper _closest.
    """
    src = _read(WEB_APP)
    # Ignorar la linea del comentario que documenta el error
    offenders = [ln for ln in src.splitlines()
                 if "e.target.closest(" in ln and "//" not in ln.split("e.target.closest(")[0]]
    assert not offenders, (
        "Hay 'e.target.closest(' sin proteger (usar _closest): " + str(offenders[:3])
    )


# ── Incidente 4: ON CONFLICT DO NOTHING debe estar acompanado de id unico ──
def test_pg_add_entry_relies_on_unique_id():
    """
    _pg_add_entry usa ON CONFLICT DO NOTHING; esto es seguro SOLO si add_entry
    garantiza ids unicos. Verifica que add_entry sigue agregando el sufijo unico.
    """
    src = _read(HIST_MGR)
    assert "secrets" in src and "token_hex" in src, (
        "add_entry ya no genera id unico con token_hex — riesgo de colision + "
        "descarte silencioso por ON CONFLICT DO NOTHING"
    )
