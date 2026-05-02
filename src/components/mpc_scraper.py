# -*- coding: utf-8 -*-
"""
Scraper para miprimercasa.ar — extrae transcripciones de la tabla
de grabaciones de vendedores.

Columnas extraídas:
  - id            : identificador único del registro
  - vendedor      : nombre del vendedor (ej. "ROA ANGELES GISELLE")
  - fecha_grabacion: fecha/hora de grabación
  - fecha_subida  : fecha/hora de subida
  - archivo_local : nombre del cliente/entrevista (ej. "(7)ENTREVISTA CON ANDREA")
  - transcripcion : texto completo de la transcripción

Credenciales via variables de entorno:
  MPC_USERNAME, MPC_PASSWORD
"""
from __future__ import annotations

import os
import re
import logging
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL   = "https://www.miprimercasa.ar"
LOGIN_URL  = f"{BASE_URL}/Administracion/Login.aspx"
LIST_URL   = f"{BASE_URL}/Administracion/GRABACIONAUDITORSUBE.aspx"
DETAIL_URL = f"{BASE_URL}/Administracion/GRABACIONAUDITORSUBEDETALLE.aspx"


class MPCScraper:
    """
    Scraper para la página de grabaciones de miprimercasa.ar.
    Mantiene una sesión HTTP autenticada durante toda la extracción.
    """

    def __init__(self) -> None:
        self._session: Optional[requests.Session] = None

    # ------------------------------------------------------------------
    # Autenticación
    # ------------------------------------------------------------------

    def _get_credentials(self) -> tuple[str, str]:
        username = os.environ.get("MPC_USERNAME", "").strip()
        password = os.environ.get("MPC_PASSWORD", "").strip()
        if not username or not password:
            raise EnvironmentError(
                "Variables de entorno MPC_USERNAME y MPC_PASSWORD no configuradas."
            )
        return username, password

    def login(self) -> requests.Session:
        """Realiza el login y retorna la sesión autenticada."""
        username, password = self._get_credentials()
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })

        # GET login page para obtener ViewState y tokens ASP.NET
        resp = session.get(LOGIN_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        payload = self._extract_aspnet_fields(soup)
        payload.update({
            "txtUsuario": username,
            "txtPassword": password,
        })

        # Buscar el botón de submit
        btn = soup.find("input", {"type": "submit"})
        if btn and btn.get("name"):
            payload[btn["name"]] = btn.get("value", "Ingresar")

        resp = session.post(LOGIN_URL, data=payload, timeout=30)
        resp.raise_for_status()

        # Verificar que el login fue exitoso (no redirigió de vuelta al login)
        if "Login.aspx" in resp.url or "fuera de Sesión" in resp.text:
            raise PermissionError(
                "Login fallido en miprimercasa.ar. "
                "Verificar MPC_USERNAME y MPC_PASSWORD."
            )

        self._session = session
        logger.info("Login exitoso en miprimercasa.ar")
        return session

    # ------------------------------------------------------------------
    # Extracción de la tabla principal
    # ------------------------------------------------------------------

    def fetch_records(
        self,
        month: Optional[int] = None,
        year: Optional[int] = None,
        vendedor_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Extrae todos los registros de la tabla de grabaciones.

        Args:
            month: mes a filtrar (1-12). None = mes actual.
            year:  año a filtrar. None = año actual.
            vendedor_id: ID del vendedor para filtrar. None = TODOS.

        Returns:
            Lista de dicts con los campos extraídos.
        """
        if self._session is None:
            self.login()

        now = datetime.now()
        month = month or now.month
        year  = year  or now.year

        # GET página principal
        resp = self._session.get(LIST_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Construir payload para filtrar por mes/año
        payload = self._extract_aspnet_fields(soup)

        # Buscar el dropdown de mes/año y el de vendedor
        month_str = f"{month}/{year}"  # formato "4/2026"
        self._set_dropdown(payload, soup, ["ddlMes", "DropDownList1"], month_str)
        if vendedor_id:
            self._set_dropdown(payload, soup, ["ddlVendedor", "DropDownList2"], vendedor_id)

        # Buscar botón de filtrar/buscar
        btn = soup.find("input", {"type": "submit", "value": re.compile(r"Buscar|Filtrar|Ver", re.I)})
        if btn and btn.get("name"):
            payload[btn["name"]] = btn.get("value", "Ver")

        resp = self._session.post(LIST_URL, data=payload, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        return self._parse_table(soup)

    def fetch_all_records(self, from_year: int = 2026, from_month: int = 1) -> list[dict]:
        """
        Extrae todos los registros desde from_month/from_year hasta hoy.
        """
        if self._session is None:
            self.login()

        now = datetime.now()
        all_records: list[dict] = []
        seen_ids: set[str] = set()

        y, m = from_year, from_month
        while (y, m) <= (now.year, now.month):
            logger.info(f"Extrayendo registros de {m}/{y}...")
            try:
                records = self.fetch_records(month=m, year=y)
                for r in records:
                    if r.get("id") and r["id"] not in seen_ids:
                        seen_ids.add(r["id"])
                        all_records.append(r)
                logger.info(f"  {len(records)} registros encontrados en {m}/{y}")
            except Exception as exc:
                logger.warning(f"  Error extrayendo {m}/{y}: {exc}")

            m += 1
            if m > 12:
                m = 1
                y += 1

        logger.info(f"Total registros extraídos: {len(all_records)}")
        return all_records

    def fetch_transcription(self, record_id: str) -> Optional[str]:
        """
        Extrae el texto completo de la transcripción para un registro dado.
        Intenta obtenerlo desde la página de detalle.
        """
        if self._session is None:
            self.login()

        try:
            url = f"{DETAIL_URL}?id={record_id}"
            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Buscar el área de texto con la transcripción
            for selector in [
                {"name": "txtTranscripcion"},
                {"id": "txtTranscripcion"},
                {"class": re.compile(r"transcri", re.I)},
            ]:
                el = soup.find(["textarea", "div", "p", "span"], selector)
                if el and el.get_text(strip=True):
                    return el.get_text(separator=" ", strip=True)

            # Fallback: buscar el textarea más grande
            textareas = soup.find_all("textarea")
            if textareas:
                longest = max(textareas, key=lambda t: len(t.get_text()))
                text = longest.get_text(separator=" ", strip=True)
                if len(text) > 20:
                    return text

        except Exception as exc:
            logger.warning(f"No se pudo obtener transcripción para id={record_id}: {exc}")

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_table(self, soup: BeautifulSoup) -> list[dict]:
        """Parsea la tabla HTML y retorna lista de registros."""
        records = []

        table = soup.find("table")
        if not table:
            logger.warning("No se encontró tabla en la página")
            return records

        rows = table.find_all("tr")
        if len(rows) < 2:
            return records

        # Detectar índices de columnas desde el header
        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
        col = self._detect_columns(headers)

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            def cell(idx: Optional[int]) -> str:
                if idx is None or idx >= len(cells):
                    return ""
                return cells[idx].get_text(separator=" ", strip=True)

            record_id = cell(col.get("id"))
            vendedor  = cell(col.get("vendedor"))
            fecha_grab = cell(col.get("fecha_grabacion"))
            fecha_sub  = cell(col.get("fecha_subida"))
            archivo    = cell(col.get("archivo"))
            arch_local = cell(col.get("archivo_local"))
            estado     = cell(col.get("estado"))

            # Solo procesar registros con transcripción disponible
            if "transcripta" not in estado.lower() and estado:
                pass  # incluir todos de todas formas

            if not vendedor:
                continue

            # Extraer link de detalle si existe
            link = row.find("a", href=re.compile(r"DETALLE|detalle|id=", re.I))
            detail_url = link["href"] if link else None

            records.append({
                "id": record_id,
                "vendedor": vendedor,
                "fecha_grabacion": fecha_grab,
                "fecha_subida": fecha_sub,
                "archivo": archivo,
                "archivo_local": arch_local,
                "estado": estado,
                "detail_url": detail_url,
            })

        return records

    def _detect_columns(self, headers: list[str]) -> dict[str, int]:
        """Detecta los índices de columnas por nombre."""
        col: dict[str, int] = {}
        patterns = {
            "id":              ["id"],
            "vendedor":        ["vendedor"],
            "fecha_grabacion": ["fecha grabacion", "fecha_grabacion", "grabacion"],
            "fecha_subida":    ["fecha subida", "fecha_subida", "subida"],
            "archivo":         ["archivo"],
            "archivo_local":   ["archivo local", "archivo_local", "local"],
            "estado":          ["estado"],
        }
        for key, candidates in patterns.items():
            for i, h in enumerate(headers):
                if any(c in h for c in candidates):
                    if key not in col:
                        col[key] = i
        return col

    def _extract_aspnet_fields(self, soup: BeautifulSoup) -> dict:
        """Extrae campos ocultos de ASP.NET (ViewState, EventValidation, etc.)."""
        fields = {}
        for inp in soup.find_all("input", {"type": "hidden"}):
            name = inp.get("name", "")
            if name:
                fields[name] = inp.get("value", "")
        return fields

    def _set_dropdown(
        self,
        payload: dict,
        soup: BeautifulSoup,
        names: list[str],
        value: str,
    ) -> None:
        """Intenta setear el valor de un dropdown en el payload."""
        for name in names:
            sel = soup.find("select", {"name": name}) or soup.find("select", {"id": name})
            if sel:
                payload[name] = value
                return
        # Si no encontró el select, igual lo agrega
        if names:
            payload[names[0]] = value
