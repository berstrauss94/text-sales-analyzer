# -*- coding: utf-8 -*-
"""
analisis_sistema.py — Relevamiento automático del sistema (inventario con conteos).

QUE HACE
--------
Escanea el repositorio y produce un inventario EXACTO y actualizado: endpoints,
tablas PostgreSQL, modelos de ML, componentes, módulos de datos, proveedores de
IA, agentes/hooks/specs/steering de Kiro, versión actual y volumen de datos.

Está pensado para que, en cualquier versión futura del proyecto, se corra este
script y los números del "Análisis General Completo" salgan del código real, sin
contar nada a mano.

USO
---
    py scripts/analisis_sistema.py            # imprime el inventario en texto
    py scripts/analisis_sistema.py --json     # imprime el inventario en JSON

Es de SOLO LECTURA: no modifica ni la base ni el código. No requiere PostgreSQL
(los conteos salen del código fuente, no de la base en vivo).
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception:
        return ""


def _iter_files(rel_dir, exts):
    base = os.path.join(ROOT, rel_dir)
    out = []
    if not os.path.isdir(base):
        return out
    for root, _dirs, files in os.walk(base):
        # saltar caches
        if "__pycache__" in root:
            continue
        for f in files:
            if any(f.endswith(e) for e in exts):
                out.append(os.path.join(root, f))
    return out


def relevar():
    data = {}

    # --- Endpoints (rutas Flask en web_app.py) ---
    web = _read(os.path.join(ROOT, "web_app.py"))
    rutas = re.findall(r'@app\.route\(\s*["\']([^"\']+)["\']', web)
    data["endpoints_total"] = len(rutas)
    data["endpoints"] = sorted(set(rutas))

    # --- Version visible (versionBadge) ---
    m = re.search(r'>v(\d+\.\d+)', web)
    data["version"] = m.group(1) if m else "desconocida"

    # --- Tablas PostgreSQL (CREATE TABLE IF NOT EXISTS) ---
    tablas = set()
    for f in _iter_files("src", (".py",)):
        txt = _read(f)
        for t in re.findall(r'CREATE TABLE IF NOT EXISTS\s+(\w+)', txt):
            tablas.add(t)
    data["tablas_total"] = len(tablas)
    data["tablas"] = sorted(tablas)

    # --- Modelos de ML entrenados (models/*.joblib) ---
    modelos = [f for f in os.listdir(os.path.join(ROOT, "models"))
               if f.endswith(".joblib")] if os.path.isdir(os.path.join(ROOT, "models")) else []
    data["modelos_ml_total"] = len(modelos)
    data["modelos_ml"] = sorted(modelos)

    # --- Componentes de analisis (src/components/*.py sin __init__) ---
    comp = [os.path.basename(f) for f in _iter_files("src/components", (".py",))
            if not f.endswith("__init__.py")]
    data["componentes_total"] = len(comp)
    data["componentes"] = sorted(comp)

    # --- Modulos de datos *_pg ---
    pg = [os.path.basename(f) for f in _iter_files("src/users", (".py",))
          if f.endswith("_pg.py")]
    data["modulos_pg_total"] = len(pg)
    data["modulos_pg"] = sorted(pg)

    # --- Proveedores de IA (detectados en el codigo) ---
    proveedores = []
    if "GEMINI_API_KEY" in web or "GOOGLE_API_KEY" in web:
        proveedores.append("Google Gemini")
    if "OPENAI_API_KEY" in web:
        proveedores.append("OpenAI")
    data["ia_proveedores"] = proveedores

    # --- API publica (endpoints /api/v1/) ---
    data["api_publica"] = sorted([r for r in set(rutas) if r.startswith("/api/v1/")])

    # --- Kiro: agentes, hooks, specs, steering ---
    def _count_dir(rel, exts=None):
        base = os.path.join(ROOT, rel)
        if not os.path.isdir(base):
            return []
        out = []
        for f in os.listdir(base):
            full = os.path.join(base, f)
            if os.path.isfile(full) and (exts is None or any(f.endswith(e) for e in exts)):
                out.append(f)
            elif os.path.isdir(full):  # specs son carpetas
                out.append(f + "/")
        return sorted(out)

    data["kiro_agentes"] = _count_dir(".kiro/agents")
    data["kiro_hooks"] = _count_dir(".kiro/hooks")
    data["kiro_specs"] = [d for d in _count_dir(".kiro/specs") if d.endswith("/")]
    data["kiro_steering"] = _count_dir(".kiro/steering", (".md",))

    # --- Volumen de datos (si hay historial local JSON de muestra) ---
    # El conteo real de produccion sale de /admin/db-status; aqui no se consulta la base.
    data["nota_volumen"] = ("El volumen real de textos por usuario se obtiene en vivo "
                            "desde el endpoint /admin/db-status (requiere sesion admin).")

    return data


def imprimir(data):
    def linea(k, v):
        print(f"  {k}: {v}")
    print("=" * 64)
    print("  INVENTARIO DEL SISTEMA — Analizador de Textos")
    print("=" * 64)
    linea("Version visible", data["version"])
    print()
    linea("Endpoints (rutas)", data["endpoints_total"])
    linea("Tablas PostgreSQL", data["tablas_total"])
    linea("Modelos de ML", data["modelos_ml_total"])
    linea("Componentes de analisis", data["componentes_total"])
    linea("Modulos de datos *_pg", data["modulos_pg_total"])
    linea("Proveedores de IA", ", ".join(data["ia_proveedores"]) or "ninguno")
    linea("API publica", ", ".join(data["api_publica"]) or "ninguna")
    linea("Agentes de Kiro", len(data["kiro_agentes"]))
    linea("Hooks de Kiro", len(data["kiro_hooks"]))
    linea("Specs de Kiro", len(data["kiro_specs"]))
    linea("Steering de Kiro", len(data["kiro_steering"]))
    print()
    print("  Tablas:", ", ".join(data["tablas"]))
    print()
    print("  Modelos ML:", ", ".join(data["modelos_ml"]))
    print()
    print("  Agentes:", ", ".join(data["kiro_agentes"]))
    print("  Hooks:", ", ".join(data["kiro_hooks"]))
    print("  Specs:", ", ".join(data["kiro_specs"]))
    print("  Steering:", ", ".join(data["kiro_steering"]))
    print("=" * 64)
    print("  (Lista completa de endpoints: usar --json)")


if __name__ == "__main__":
    d = relevar()
    if "--json" in sys.argv:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        imprimir(d)
