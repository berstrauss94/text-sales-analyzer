# -*- coding: utf-8 -*-
"""
SCRIPT DE RESTAURACIÓN — Punto de respaldo: 2026-07-31

Al ejecutar este script, el proyecto volverá EXACTAMENTE al estado capturado
en la fecha indicada arriba. Esto incluye:

  - Rama: develop
  - Commit base: 4a657be (Hardening: pool PG, fix upload_audio, fix admin guards...)
  - Archivos modificados sin commitear:
      * src/components/commercial_analyzer.py (co-decisores, alertas, presupuesto - a medio terminar)
      * web_app.py (sin cambios funcionales extra vs commit)

Uso:
    py restore_backup_2026_07_31.py

Qué hace:
    1. Verifica que estés en el repositorio correcto
    2. Descarta TODOS los cambios no commiteados en working tree
    3. Vuelve a la rama develop
    4. Resetea al commit exacto 4a657be
    5. Reaaplica los cambios pendientes desde el stash guardado

Para crear el stash de respaldo (hacer UNA sola vez antes de tocar más cosas):
    git stash push -m "BACKUP-2026-07-31-estado-actual" -- src/components/commercial_analyzer.py web_app.py

IMPORTANTE: Este script es DESTRUCTIVO — borra cualquier cambio que no esté commiteado.
"""
from __future__ import annotations

import os
import sys
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
COMMIT_HASH = "4a657be8a8f510123819a220680b7e7b27c57596"
STASH_NAME = "BACKUP-2026-07-31-estado-actual"


def run(cmd: str, check: bool = True) -> str:
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=PROJECT_DIR
    )
    if check and result.returncode != 0:
        print(f"ERROR ejecutando: {cmd}")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
    return (result.stdout + result.stderr).strip()


def main():
    print("=" * 60)
    print("  RESTAURACIÓN DE BACKUP — 2026-07-31")
    print("=" * 60)
    print()

    # Verify we're in the right repo
    if not os.path.exists(os.path.join(PROJECT_DIR, "web_app.py")):
        print("ERROR: No se encontró web_app.py. ¿Estás en el directorio correcto?")
        sys.exit(1)

    # Confirm
    resp = input("⚠️  Esto descartará TODOS los cambios actuales. ¿Continuar? (si/no): ").strip().lower()
    if resp not in ("si", "sí", "s", "yes", "y"):
        print("Cancelado.")
        return

    print()
    print("1. Descartando cambios no commiteados...")
    run("git checkout -- .")
    run("git clean -fd .hypothesis/tmp/", check=False)

    print("2. Cambiando a rama develop...")
    run("git checkout develop")

    print("3. Reseteando al commit de referencia...")
    run(f"git reset --hard {COMMIT_HASH}")

    print("4. Buscando stash de backup...")
    stash_list = run("git stash list", check=False)
    stash_idx = None
    for line in stash_list.splitlines():
        if STASH_NAME in line:
            # Extract stash@{N}
            stash_idx = line.split(":")[0]
            break

    if stash_idx:
        print(f"   Encontrado: {stash_idx}")
        print("5. Aplicando cambios del stash...")
        run(f"git stash apply {stash_idx}")
        print()
        print("✅ RESTAURACIÓN COMPLETA")
        print("   El proyecto está exactamente como el 2026-07-31.")
    else:
        print("   ⚠️  No se encontró el stash de backup.")
        print("   El proyecto está en el commit limpio 4a657be.")
        print("   Los cambios pendientes de commercial_analyzer.py no se pudieron restaurar.")
        print()
        print("   Si necesitás los cambios pendientes, buscá manualmente:")
        print(f"     git stash list")
        print(f"     git stash apply stash@{{N}}")

    print()
    print("Estado final:")
    os.system(f'cd "{PROJECT_DIR}" && git status --short && git log --oneline -1')


if __name__ == "__main__":
    main()
