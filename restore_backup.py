# -*- coding: utf-8 -*-
"""
restore_backup.py - Restaurar el CODIGO al ultimo estado estable conocido.

Punto de restauracion actual: backup-estable-2026-08-29-v8.3
Ese backup incluye:
- Carga de textos funcionando (SyntaxError del banner de backup resuelto)
- Backups automaticos de DATOS activos (cada 10 guardados / 5 min) + Auto-Fix
- Deteccion de perdida con alerta admin y restauracion entrada por entrada
- Informe con filtros de periodo (Enero a la fecha, mes, semanas)
- Impresion del informe en hoja blanca con colores (numeros, grafico azul,
  palabras resaltadas); cuadrilla meses celeste, total verde/amarillo y donut
  blanco aplicados SOLO al imprimir (la pantalla mantiene el tema oscuro)
- Fix e.target.closest (helper _closest) en handlers delegados
- Layout responsive (movil/tablet/PC/TV)
- Gate de validez de JavaScript + regression guards (103 tests)

Uso:
    python restore_backup.py

Esto hace:
    1. Checkout a master
    2. Reset al tag BACKUP_TAG
    3. Force push a GitHub
    4. Railway redespliega automaticamente

ADVERTENCIA: Esto descarta TODOS los cambios de codigo posteriores al backup.
Los DATOS (textos en PostgreSQL) NO se tocan — eso lo maneja el Auto-Fix.
"""
from __future__ import annotations
import subprocess
import sys


def run(cmd: str) -> tuple[int, str]:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


# Punto de restauracion actual. Actualizar cuando se cree un nuevo backup estable.
BACKUP_TAG = "backup-estable-2026-08-29-v8.3"


def main():
    print("=" * 60)
    print("  RESTAURACION DE BACKUP")
    print("=" * 60)
    print()
    print("  Este script restaurara el CODIGO al estado estable.")
    print(f"  Tag: {BACKUP_TAG}")
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
    code, out = run(f"git reset --hard {BACKUP_TAG}")
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
    run(f"git reset --hard {BACKUP_TAG}")

    print()
    print("=" * 60)
    print("  RESTAURACION COMPLETADA")
    print("  Railway redesplegara en 2-3 minutos.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
