# -*- coding: utf-8 -*-
"""
Red de seguridad de la capa de animacion / tutorial guiado.

Valida que CADA paso del recorrido guiado (TOUR_STEPS en web_app.py) apunte a un
elemento que realmente existe en el HTML embebido. Antes, agregar/renombrar un
boton dejaba pasos del tour apuntando a selectores inexistentes (el marco no
resaltaba nada). Este test lo detecta al instante, junto con los 103 tests.

Corre en el suite normal (y por ende antes de cada deploy).
"""
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_APP = os.path.join(BASE_DIR, "web_app.py")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_tour_selectors(src):
    """Devuelve la lista de valores `sel:` dentro del array TOUR_STEPS."""
    # Aislar el bloque del array TOUR_STEPS = [ ... ];
    m = re.search(r"TOUR_STEPS\s*=\s*\[(.*?)\];", src, re.DOTALL)
    assert m, "No se encontro el array TOUR_STEPS en web_app.py"
    block = m.group(1)
    # Extraer cada sel: '...'
    return re.findall(r"sel:\s*'([^']+)'", block)


def _selector_exists(src, sel):
    """True si el selector (id '#x' o clase '.x') aparece definido en el HTML."""
    if sel.startswith("#"):
        name = sel[1:]
        return (f'id="{name}"' in src) or (f"id='{name}'" in src)
    if sel.startswith("."):
        name = sel[1:]
        # Clase presente en algun class="..." (puede haber varias clases juntas).
        return bool(re.search(r'class="[^"]*\b' + re.escape(name) + r'\b[^"]*"', src))
    # Selector plano (tag u otro): aceptar si aparece textualmente.
    return sel in src


def test_all_tour_steps_point_to_existing_elements():
    """Cada paso del tutorial debe apuntar a un id/clase que exista en el HTML."""
    src = _read(WEB_APP)
    selectors = _extract_tour_selectors(src)
    assert selectors, "TOUR_STEPS no tiene pasos con 'sel'"
    faltantes = [s for s in selectors if not _selector_exists(src, s)]
    assert not faltantes, (
        "Pasos del tutorial que apuntan a elementos inexistentes "
        "(el marco no resaltaria nada): " + str(faltantes)
    )


def test_tour_overlay_and_controls_exist():
    """El overlay del tour y sus controles deben existir en el HTML."""
    src = _read(WEB_APP)
    for needed in ('id="tourOverlay"', 'id="tourSpotlight"', 'id="tourCard"',
                   'id="tourNextBtn"', 'id="tourPrevBtn"'):
        assert needed in src, f"Falta el elemento del tour: {needed}"


def test_tour_overlay_moves_to_body():
    """
    El overlay debe moverse al <body> en startTour() para que position:fixed no
    se rompa por ancestros con transform (bug ya vivido). Verifica que el fix siga.
    """
    src = _read(WEB_APP)
    assert "document.body.appendChild(ov)" in src, (
        "startTour() ya no mueve el overlay al body: el marco puede dislocarse "
        "si un ancestro tiene transform (position:fixed roto)."
    )
