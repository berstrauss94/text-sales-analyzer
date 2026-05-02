# -*- coding: utf-8 -*-
"""
Pipeline de sincronización de transcripciones desde miprimercasa.ar.

Orquesta: Scraper → Vendor Mapping → Analyzer → HistoryManager
Incluye deduplicación persistente y logging estructurado.
"""
from __future__ import annotations

import os
import json
import re
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Rutas de archivos de configuración/estado
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
CONFIG_DIR   = os.path.join(BASE_DIR, "config")
MAPPING_FILE = os.path.join(CONFIG_DIR, "vendor_mapping.json")
DEDUP_FILE   = os.path.join(CONFIG_DIR, "sync_dedup.json")
LOG_FILE     = os.path.join(CONFIG_DIR, "sync_log.json")

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


class SyncPipeline:
    """
    Orquestador de sincronización de transcripciones.
    Usa las instancias de analyzer e history_manager ya inicializadas en Flask.
    """

    def __init__(self, analyzer, add_entry_fn) -> None:
        """
        Args:
            analyzer:      instancia de Analyzer ya inicializada
            add_entry_fn:  función add_entry de history_manager
        """
        self._analyzer    = analyzer
        self._add_entry   = add_entry_fn
        os.makedirs(CONFIG_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Punto de entrada principal
    # ------------------------------------------------------------------

    def run(self, historical: bool = False) -> dict:
        """
        Ejecuta el ciclo completo de sincronización.

        Args:
            historical: si True, extrae desde Enero 2026 hasta hoy.
                        si False, solo el mes actual.

        Returns:
            Resumen de la ejecución.
        """
        summary = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "processed": 0,
            "skipped_dedup": 0,
            "skipped_no_mapping": 0,
            "skipped_no_transcription": 0,
            "errors": 0,
            "unmapped_vendors": [],
        }

        try:
            mapping = self._load_mapping()
        except Exception as exc:
            msg = f"Error cargando vendor_mapping.json: {exc}"
            logger.error(msg)
            self._log_run({**summary, "error": msg})
            return summary

        try:
            from src.components.mpc_scraper import MPCScraper
            scraper = MPCScraper()
            scraper.login()

            if historical:
                records = scraper.fetch_all_records(from_year=2026, from_month=1)
            else:
                records = scraper.fetch_records()

        except EnvironmentError as exc:
            msg = f"Credenciales no configuradas: {exc}"
            logger.error(msg)
            self._log_run({**summary, "error": msg})
            return summary
        except PermissionError as exc:
            msg = f"Login fallido: {exc}"
            logger.error(msg)
            self._log_run({**summary, "error": msg})
            return summary
        except Exception as exc:
            msg = f"Error en scraping: {exc}"
            logger.error(msg)
            self._log_run({**summary, "error": msg})
            return summary

        dedup = self._load_dedup()

        for record in records:
            try:
                result = self._process_record(record, mapping, dedup, scraper)
                if result == "processed":
                    summary["processed"] += 1
                elif result == "dedup":
                    summary["skipped_dedup"] += 1
                elif result == "no_mapping":
                    summary["skipped_no_mapping"] += 1
                    vendor = record.get("vendedor", "")
                    if vendor and vendor not in summary["unmapped_vendors"]:
                        summary["unmapped_vendors"].append(vendor)
                elif result == "no_transcription":
                    summary["skipped_no_transcription"] += 1
            except Exception as exc:
                logger.error(f"Error procesando registro {record.get('id')}: {exc}")
                summary["errors"] += 1

        self._save_dedup(dedup)
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        self._log_run(summary)
        logger.info(f"Sync completado: {summary}")
        return summary

    # ------------------------------------------------------------------
    # Procesamiento de un registro
    # ------------------------------------------------------------------

    def _process_record(
        self,
        record: dict,
        mapping: dict,
        dedup: set,
        scraper,
    ) -> str:
        """Procesa un registro individual. Retorna el resultado."""

        record_id = record.get("id", "")
        vendedor  = record.get("vendedor", "").strip()

        # Deduplicación
        dedup_key = self._make_dedup_key(record)
        if dedup_key in dedup:
            return "dedup"

        # Mapeo de vendedor
        username = self._resolve_username(vendedor, mapping)
        if not username:
            logger.info(f"Vendedor sin mapeo: '{vendedor}'")
            return "no_mapping"

        # Obtener transcripción
        transcription_text = self._get_transcription_text(record, scraper)
        if not transcription_text or len(transcription_text.strip()) < 10:
            logger.info(f"Sin transcripción para id={record_id}")
            return "no_transcription"

        # Analizar
        from src.models.data_models import AnalysisError
        result = self._analyzer.analyze(transcription_text)

        if isinstance(result, AnalysisError):
            logger.warning(f"Error de análisis para id={record_id}: {result.error_message}")
            return "no_transcription"

        # Construir analysis_dict compatible con add_entry
        analysis_dict = self._build_analysis_dict(result)

        # Determinar timestamp original de grabación
        timestamp = self._parse_fecha(record.get("fecha_grabacion", ""))

        # Título del cliente extraído del archivo local
        archivo_local = record.get("archivo_local", "")
        client_title  = self._extract_client_title(archivo_local)

        # Guardar en historial con timestamp original
        self._add_entry_with_timestamp(
            username=username,
            text=transcription_text,
            analysis=analysis_dict,
            source="sync",
            audio_filename=client_title,
            timestamp=timestamp,
        )

        dedup.add(dedup_key)
        logger.info(f"Procesado: vendedor='{vendedor}' → usuario='{username}', cliente='{client_title}'")
        return "processed"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_transcription_text(self, record: dict, scraper) -> Optional[str]:
        """Obtiene el texto de transcripción del registro."""
        # Primero intentar desde el campo directo si ya está en el record
        if record.get("transcripcion"):
            return record["transcripcion"]

        # Intentar desde la página de detalle
        record_id = record.get("id", "")
        if record_id:
            return scraper.fetch_transcription(record_id)

        return None

    def _resolve_username(self, vendedor: str, mapping: dict) -> Optional[str]:
        """Resuelve el username del analizador para un nombre de vendedor."""
        # Búsqueda exacta
        if vendedor in mapping:
            return mapping[vendedor]

        # Búsqueda normalizada (sin tildes, uppercase)
        vendedor_norm = self._normalize(vendedor)
        for key, username in mapping.items():
            if self._normalize(key) == vendedor_norm:
                return username

        return None

    def _normalize(self, text: str) -> str:
        """Normaliza texto: uppercase, sin tildes."""
        replacements = {
            "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
            "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
            "ñ": "n", "Ñ": "N",
        }
        result = text.upper()
        for src, dst in replacements.items():
            result = result.replace(src.upper(), dst.upper())
        return result.strip()

    def _make_dedup_key(self, record: dict) -> str:
        """Genera una clave única para deduplicación."""
        record_id = record.get("id", "")
        if record_id:
            return f"id:{record_id}"
        # Fallback: vendedor + fecha
        vendedor = record.get("vendedor", "")
        fecha    = record.get("fecha_grabacion", "")
        return f"vf:{vendedor}:{fecha}"

    def _parse_fecha(self, fecha_str: str) -> Optional[datetime]:
        """Parsea una fecha en varios formatos posibles."""
        if not fecha_str:
            return None
        formats = [
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(fecha_str.strip(), fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def _extract_client_title(self, archivo_local: str) -> str:
        """
        Extrae el título del cliente del nombre del archivo local.
        Ej: "(7)ENTREVISTA CON ANDREA" → "ENTREVISTA CON ANDREA"
        """
        if not archivo_local:
            return ""
        # Quitar prefijo numérico entre paréntesis: "(7)"
        title = re.sub(r"^\(\d+\)\s*", "", archivo_local.strip())
        return title.strip()

    def _build_analysis_dict(self, result) -> dict:
        """Construye el dict de análisis compatible con add_entry."""
        return {
            "intent": result.intent,
            "intent_confidence": result.intent_confidence,
            "sentiment": result.sentiment,
            "sentiment_confidence": result.sentiment_confidence,
            "sales_concepts": [
                {"concept": c.concept, "confidence": c.confidence, "source_text": c.source_text}
                for c in result.sales_concepts
            ],
            "real_estate_concepts": [
                {"concept": c.concept, "confidence": c.confidence, "source_text": c.source_text}
                for c in result.real_estate_concepts
            ],
            "entities": [
                {"concept": e.concept, "raw_value": e.raw_value,
                 "numeric_value": e.numeric_value, "unit": e.unit}
                for e in result.entities
            ],
            "commercial": None,
        }

    def _add_entry_with_timestamp(
        self,
        username: str,
        text: str,
        analysis: dict,
        source: str,
        audio_filename: str,
        timestamp: Optional[datetime],
    ) -> None:
        """
        Llama a add_entry pero usando el timestamp original de grabación
        en lugar del timestamp actual.
        """
        if timestamp is None:
            # Sin timestamp original → usar ahora
            self._add_entry(
                username=username,
                text=text,
                analysis=analysis,
                source=source,
                audio_filename=audio_filename,
            )
            return

        # Parchear temporalmente la función datetime.now en history_manager
        # usando el timestamp original para que la entrada quede en la fecha correcta
        import src.users.history_manager as hm
        from unittest.mock import patch

        mock_dt = datetime(
            timestamp.year, timestamp.month, timestamp.day,
            timestamp.hour, timestamp.minute, timestamp.second,
            tzinfo=timezone.utc
        )

        class _MockDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return mock_dt

        with patch.object(hm, "datetime", _MockDatetime):
            self._add_entry(
                username=username,
                text=text,
                analysis=analysis,
                source=source,
                audio_filename=audio_filename,
            )

    # ------------------------------------------------------------------
    # Persistencia de dedup y log
    # ------------------------------------------------------------------

    def _load_dedup(self) -> set:
        if not os.path.exists(DEDUP_FILE):
            return set()
        try:
            with open(DEDUP_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()

    def _save_dedup(self, dedup: set) -> None:
        with open(DEDUP_FILE, "w", encoding="utf-8") as f:
            json.dump(list(dedup), f, ensure_ascii=False)

    def _load_mapping(self) -> dict:
        if not os.path.exists(MAPPING_FILE):
            raise FileNotFoundError(f"No se encontró {MAPPING_FILE}")
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("vendor_mapping.json debe ser un objeto JSON")
        return data

    def _log_run(self, summary: dict) -> None:
        """Agrega una entrada al log de sincronizaciones."""
        try:
            logs = []
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            logs.append(summary)
            # Mantener solo los últimos 100 logs
            logs = logs[-100:]
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning(f"No se pudo guardar sync_log: {exc}")
