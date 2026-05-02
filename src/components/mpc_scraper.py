# -*- coding: utf-8 -*-
"""
Scraper para miprimercasa.ar — extrae transcripciones de la tabla
de grabaciones de vendedores.

Flujo real de la página (ASP.NET WebForms):
  1. GET  /acceso.aspx                          → obtener ViewState + tokens
  2. POST /acceso.aspx                          → login con otxtUsuario / otxtPass
  3. GET  /Administracion/GRABACIONAUDITORSUBE.aspx → página principal
  4. POST (postback __EVENTTARGET=oddlUltimosPeriodos, value=<id_periodo>) → filtrar mes
  5. POST (postback __EVENTTARGET=ogvGrabacionesRegistroTraer, Select$N)   → abrir fila
  6. Leer textarea ContentPlaceHolder1_otxtTranscripcion                   → transcripción

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

BASE_URL  = "https://www.miprimercasa.ar"
LOGIN_URL = f"{BASE_URL}/acceso.aspx"
LIST_URL  = f"{BASE_URL}/Administracion/GRABACIONAUDITORSUBE.aspx"

# Nombres exactos de los campos del formulario (ASP.NET WebForms)
_F_USUARIO   = "otxtUsuario"
_F_PASSWORD  = "otxtPass"
_F_BTN_LOGIN = "obutAcceder"
_F_PERIODO   = "ctl00$ContentPlaceHolder1$oddlUltimosPeriodos"
_F_VENDEDOR  = "ctl00$ContentPlaceHolder1$oddlVendedor"
_F_GRIDVIEW  = "ctl00$ContentPlaceHolder1$ogvGrabacionesRegistroTraer"
_F_TRANSCR   = "ContentPlaceHolder1_otxtTranscripcion"


class MPCScraper:
    """
    Scraper para la página de grabaciones de miprimercasa.ar.
    Mantiene una sesión HTTP autenticada durante toda la extracción.
    """

    def __init__(self) -> None:
        self._session: Optional[requests.Session] = None
        # Mapa nombre_mes → id_periodo, construido al hacer login
        self._periodo_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Credenciales
    # ------------------------------------------------------------------

    def _get_credentials(self) -> tuple[str, str]:
        username = os.environ.get("MPC_USERNAME", "").strip()
        password = os.environ.get("MPC_PASSWORD", "").strip()
        if not username or not password:
            raise EnvironmentError(
                "Variables de entorno MPC_USERNAME y MPC_PASSWORD no configuradas."
            )
        return username, password

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

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

        # GET login page → obtener ViewState y tokens ASP.NET
        resp = session.get(LOGIN_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        payload = self._extract_hidden_fields(soup)
        payload[_F_USUARIO]   = username
        payload[_F_PASSWORD]  = password
        payload[_F_BTN_LOGIN] = "Ingresar al Sistema"

        resp = session.post(LOGIN_URL, data=payload, timeout=30)
        resp.raise_for_status()

        # Verificar login exitoso: intentar acceder a la página de grabaciones
        test = session.get(LIST_URL, timeout=30)
        if "acceso.aspx" in test.url.lower():
            raise PermissionError(
                "Login fallido en miprimercasa.ar. "
                "Verificar MPC_USERNAME y MPC_PASSWORD."
            )

        self._session = session

        # Construir mapa de periodos desde el dropdown
        soup_list = BeautifulSoup(test.text, "html.parser")
        self._periodo_map = self._build_periodo_map(soup_list)
        logger.info(f"Login exitoso. Periodos disponibles: {list(self._periodo_map.keys())[:6]}...")
        return session

    # ------------------------------------------------------------------
    # Mapa de periodos
    # ------------------------------------------------------------------

    def _build_periodo_map(self, soup: BeautifulSoup) -> dict[str, str]:
        """
        Construye un mapa {nombre_periodo: id_periodo} desde el dropdown.
        Ej: {"Mayo 2026": "89", "Abril 2026": "88", ...}
        """
        mapping: dict[str, str] = {}
        sel = soup.find("select", {"name": _F_PERIODO}) or \
              soup.find("select", {"id": lambda x: x and "oddlUltimosPeriodos" in x})
        if sel:
            for opt in sel.find_all("option"):
                val  = opt.get("value", "").strip()
                text = opt.get_text(strip=True)
                if val and text:
                    mapping[text] = val
        return mapping

    def _periodo_id_for(self, month: int, year: int) -> Optional[str]:
        """
        Retorna el id del periodo para un mes/año dado.
        Busca en el mapa construido al hacer login.
        """
        month_names_es = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
        }
        key = f"{month_names_es[month]} {year}"
        return self._periodo_map.get(key)

    # ------------------------------------------------------------------
    # Extracción de registros por mes
    # ------------------------------------------------------------------

    def fetch_records(
        self,
        month: Optional[int] = None,
        year: Optional[int] = None,
    ) -> list[dict]:
        """
        Extrae todos los registros del mes/año indicado.
        Solo incluye registros con estado "Grabacion transcripta".

        Returns:
            Lista de dicts con: id, vendedor, fecha_grabacion, fecha_subida,
                                transcripcion (texto completo).
        """
        if self._session is None:
            self.login()

        now   = datetime.now()
        month = month or now.month
        year  = year  or now.year

        periodo_id = self._periodo_id_for(month, year)
        if not periodo_id:
            logger.warning(f"No se encontró periodo para {month}/{year} en el dropdown.")
            return []

        # GET página principal para obtener ViewState fresco
        resp = self._session.get(LIST_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # POST postback para filtrar por periodo
        payload = self._extract_hidden_fields(soup)
        payload[_F_PERIODO]        = periodo_id
        payload[_F_VENDEDOR]       = "0"  # TODOS
        payload["__EVENTTARGET"]   = _F_PERIODO
        payload["__EVENTARGUMENT"] = ""

        resp = self._session.post(LIST_URL, data=payload, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Parsear tabla para obtener lista de filas
        rows_meta = self._parse_table_rows(soup)
        logger.info(f"Periodo {month}/{year}: {len(rows_meta)} registros encontrados.")

        # Para cada fila con transcripción, hacer postback y obtener el texto
        records: list[dict] = []
        hidden_after_filter = self._extract_hidden_fields(soup)

        for idx, meta in enumerate(rows_meta):
            if "transcripta" not in meta.get("estado", "").lower():
                # Sin transcripción disponible — incluir sin texto
                meta["transcripcion"] = None
                records.append(meta)
                continue

            transcripcion = self._fetch_transcripcion(
                session_soup_hidden=hidden_after_filter,
                periodo_id=periodo_id,
                row_index=idx,
            )
            meta["transcripcion"] = transcripcion
            records.append(meta)

            # Refrescar hidden fields después de cada postback
            # (el ViewState cambia con cada request)
            resp_refresh = self._session.get(LIST_URL, timeout=30)
            soup_refresh = BeautifulSoup(resp_refresh.text, "html.parser")
            payload_refresh = self._extract_hidden_fields(soup_refresh)
            payload_refresh[_F_PERIODO]        = periodo_id
            payload_refresh[_F_VENDEDOR]       = "0"
            payload_refresh["__EVENTTARGET"]   = _F_PERIODO
            payload_refresh["__EVENTARGUMENT"] = ""
            resp_filter = self._session.post(LIST_URL, data=payload_refresh, timeout=30)
            soup_filter = BeautifulSoup(resp_filter.text, "html.parser")
            hidden_after_filter = self._extract_hidden_fields(soup_filter)

        logger.info(f"Periodo {month}/{year}: {sum(1 for r in records if r.get('transcripcion'))} con transcripción.")
        return records

    def _fetch_transcripcion(
        self,
        session_soup_hidden: dict,
        periodo_id: str,
        row_index: int,
    ) -> Optional[str]:
        """
        Hace el postback Select$N para abrir una fila y extrae la transcripción.
        """
        try:
            payload = dict(session_soup_hidden)
            payload[_F_PERIODO]        = periodo_id
            payload[_F_VENDEDOR]       = "0"
            payload["__EVENTTARGET"]   = _F_GRIDVIEW
            payload["__EVENTARGUMENT"] = f"Select${row_index}"

            resp = self._session.post(LIST_URL, data=payload, timeout=60)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            ta = soup.find("textarea", {"id": _F_TRANSCR}) or \
                 soup.find("textarea", {"name": lambda n: n and "otxtTranscripcion" in n})
            if ta:
                text = ta.get_text(separator=" ", strip=True)
                if len(text) > 10:
                    return text
        except Exception as exc:
            logger.warning(f"Error obteniendo transcripción fila {row_index}: {exc}")
        return None

    # ------------------------------------------------------------------
    # Extracción histórica (todos los meses desde from_month/from_year)
    # ------------------------------------------------------------------

    def fetch_all_records(self, from_year: int = 2026, from_month: int = 1) -> list[dict]:
        """
        Extrae todos los registros desde from_month/from_year hasta hoy.
        Solo procesa meses que existen en el dropdown de la página.
        """
        if self._session is None:
            self.login()

        now = datetime.now()
        all_records: list[dict] = []
        seen_ids: set[str] = set()

        y, m = from_year, from_month
        while (y, m) <= (now.year, now.month):
            periodo_id = self._periodo_id_for(m, y)
            if periodo_id:
                logger.info(f"Extrayendo {m}/{y} (periodo_id={periodo_id})...")
                try:
                    records = self.fetch_records(month=m, year=y)
                    new_count = 0
                    for r in records:
                        rid = r.get("id", "")
                        if rid and rid not in seen_ids:
                            seen_ids.add(rid)
                            all_records.append(r)
                            new_count += 1
                    logger.info(f"  {new_count} registros nuevos en {m}/{y}")
                except Exception as exc:
                    logger.warning(f"  Error extrayendo {m}/{y}: {exc}")
            else:
                logger.info(f"  Periodo {m}/{y} no disponible en el dropdown, omitiendo.")

            m += 1
            if m > 12:
                m = 1
                y += 1

        logger.info(f"Total registros extraídos: {len(all_records)}")
        return all_records

    # ------------------------------------------------------------------
    # Parseo de la tabla principal
    # ------------------------------------------------------------------

    def _parse_table_rows(self, soup: BeautifulSoup) -> list[dict]:
        """
        Parsea la tabla HTML y retorna lista de metadatos por fila.
        Columnas reales: '', id, Fecha Subida, idVendedor, Vendedor,
                         Fecha grabacion, Estado procesamiento, ...
        """
        records: list[dict] = []
        table = soup.find("table")
        if not table:
            return records

        rows = table.find_all("tr")
        if len(rows) < 2:
            return records

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 6:
                continue

            def cell(i: int) -> str:
                return cells[i].get_text(separator=" ", strip=True) if i < len(cells) else ""

            record_id  = cell(1)
            fecha_sub  = cell(2)
            vendedor   = cell(4)
            fecha_grab = cell(5)
            estado     = cell(6) if len(cells) > 6 else ""

            if not vendedor:
                continue

            records.append({
                "id":              record_id,
                "vendedor":        vendedor,
                "fecha_grabacion": fecha_grab,
                "fecha_subida":    fecha_sub,
                "estado":          estado,
                "archivo_local":   "",   # no disponible en esta tabla
            })

        return records

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_hidden_fields(self, soup: BeautifulSoup) -> dict:
        """Extrae todos los campos hidden del formulario ASP.NET."""
        fields: dict[str, str] = {}
        for inp in soup.find_all("input", {"type": "hidden"}):
            name = inp.get("name", "")
            if name:
                fields[name] = inp.get("value", "")
        return fields
