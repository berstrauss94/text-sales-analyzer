# -*- coding: utf-8 -*-
"""
restore_backup.py - Restaurar el sistema al estado estable del 25/08/2026.

Este script restaura el código al punto de backup donde:
- La carga de textos funciona correctamente
- Usuario LeivaMarina está creado (grupo Aguilas)
- "Resaltar y Definir" está desactivado (no rompe nada)
- PostgreSQL conecta correctamente con retry
- Diagnostico DB disponible en /admin/db-status

Uso:
    python restore_backup.py

Esto hace:
    1. Checkout a master
    2. Reset al tag backup-estable-2026-08-25
    3. Force push a GitHub
    4. Railway redespliega automáticamente

ADVERTENCIA: Esto descarta TODOS los cambios posteriores al backup.
"""
from __future__ import annotations
import subprocess
import sys


def run(cmd: str) -> tuple[int, str]:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


def main():
    print("=" * 60)
    print("  RESTAURACION DE BACKUP - 25/08/2026")
    print("=" * 60)
    print()
    print("  Este script restaurara el sistema al estado estable.")
    print("  Tag: backup-estable-2026-08-25")
    print()

    confirm = input("  Continuar? (si/no): ").strip().lower()
    if confirm not in ("si", "s", "yes", "y"):
        print("  Cancelado.")
        return

    print()
    print("  1. Cambiando a master...")
    code, out = run("git checkout master")
    if code != 0:
        print(f"     Error: {out}")
        sys.exit(1)
    print("     OK")

    print("  2. Reseteando al backup...")
    code, out = run("git reset --hard backup-estable-2026-08-25")
    if code != 0:
        print(f"     Error: {out}")
        sys.exit(1)
    print("     OK")

    print("  3. Subiendo a GitHub (force push)...")
    code, out = run("git push origin master --force")
    if code != 0:
        print(f"     Error: {out}")
        sys.exit(1)
    print("     OK")

    print("  4. Volviendo a develop...")
    run("git checkout develop")
    run("git reset --hard backup-estable-2026-08-25")

    print()
    print("=" * 60)
    print("  RESTAURACION COMPLETADA")
    print("  Railway redesplegara en 2-3 minutos.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
