# -*- coding: utf-8 -*-
"""
Tests de la funcionalidad "adjuntar foto" en el chat de consultas/sugerencias.

Enfoque acorde a la arquitectura del proyecto:
  - pytest, SIN depender de PostgreSQL (los tests corren en local sin DB).
  - La imagen viaja como data URL (base64) en el cuerpo JSON, NO como archivo
    multipart. No hay ORM (SQLAlchemy): se valida la logica pura y el endpoint.

Cubre:
  1. message_store_pg.sanitize_image: acepta 'data:image/...', rechaza formato
     invalido y valida el tope de tamano.
  2. /api/messages/send: exige sesion, rechaza texto vacio, y con un JSON valido
     (texto + imagen base64) responde sin crashear (sin PG devuelve ok=False,
     pero NUNCA error 500).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.users import message_store_pg as ms


# ── 1. Validacion pura de la imagen (sanitize_image) ───────────────────────

def test_sanitize_image_acepta_data_url_de_imagen():
    """Un data URL de imagen valido y dentro del tope se conserva tal cual."""
    img = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA=="
    assert ms.sanitize_image(img) == img


def test_sanitize_image_acepta_png():
    img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA="
    assert ms.sanitize_image(img) == img


def test_sanitize_image_rechaza_formato_invalido():
    """Cualquier cosa que no sea 'data:image/...' se descarta (devuelve '')."""
    assert ms.sanitize_image("data:text/html;base64,PHNjcmlwdD4=") == ""
    assert ms.sanitize_image("javascript:alert(1)") == ""
    assert ms.sanitize_image("http://ejemplo.com/foto.jpg") == ""
    assert ms.sanitize_image("no soy una imagen") == ""


def test_sanitize_image_vacia_devuelve_vacio():
    assert ms.sanitize_image("") == ""
    assert ms.sanitize_image(None) == ""
    assert ms.sanitize_image("   ") == ""


def test_sanitize_image_rechaza_por_tamano():
    """Una imagen que supera el tope se descarta, aunque el formato sea valido."""
    gigante = "data:image/jpeg;base64," + ("A" * (ms._MAX_IMAGE_CHARS + 10))
    assert ms.sanitize_image(gigante) == ""


def test_sanitize_image_acepta_justo_bajo_el_tope():
    """En el limite (por debajo del tope) se conserva."""
    # Construir un data URL cuyo largo total quede por debajo del tope.
    prefijo = "data:image/jpeg;base64,"
    relleno = "A" * (ms._MAX_IMAGE_CHARS - len(prefijo) - 1)
    img = prefijo + relleno
    assert len(img) < ms._MAX_IMAGE_CHARS
    assert ms.sanitize_image(img) == img


# ── 2. Endpoint /api/messages/send ─────────────────────────────────────────

def _client():
    from web_app import app
    app.config["TESTING"] = True
    return app.test_client()


def test_send_sin_sesion_devuelve_401():
    """Sin sesion iniciada, enviar un mensaje no esta autorizado."""
    client = _client()
    resp = client.post("/api/messages/send", json={"text": "hola"})
    assert resp.status_code == 401


def test_send_texto_vacio_devuelve_400():
    """Con sesion pero sin texto, es un pedido invalido."""
    client = _client()
    with client.session_transaction() as sess:
        sess["username"] = "ContrerasCath"
    resp = client.post("/api/messages/send", json={"text": "   "})
    assert resp.status_code == 400


def test_send_con_imagen_base64_no_crashea():
    """
    Con sesion, texto e imagen base64 valida, el endpoint responde sin crashear.
    Sin PG en local, add_message devuelve False -> {"ok": False}, pero el punto
    clave es que NUNCA da 500: el flujo de la imagen no rompe la peticion.
    """
    client = _client()
    with client.session_transaction() as sess:
        sess["username"] = "ContrerasCath"
    resp = client.post("/api/messages/send", json={
        "text": "No me carga el panel, adjunto captura",
        "kind": "ayuda",
        "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA=",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "ok" in data


def test_send_solo_texto_no_crashea():
    """La foto es OPCIONAL: enviar solo texto tambien responde 200 sin crashear."""
    client = _client()
    with client.session_transaction() as sess:
        sess["username"] = "ContrerasCath"
    resp = client.post("/api/messages/send", json={
        "text": "Tengo una sugerencia para el informe",
        "kind": "sugerencia",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "ok" in data
