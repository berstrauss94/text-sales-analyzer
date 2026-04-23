# -*- coding: utf-8 -*-
"""
Sistema de respaldo y control de versiones del proyecto.

Comandos disponibles:
    python backup.py save "descripcion"   - Guarda cambios en develop
    python backup.py promote              - Promueve develop a master (si demo pasa)
    python backup.py restore              - Restaura desde master si algo falla
    python backup.py status               - Muestra estado actual
    python backup.py log                  - Muestra historial de cambios
"""
from __future__ import annotations

import sys
import os
import io
import subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SEP = "=" * 60
THIN = "-" * 60


def run(cmd: str) -> tuple[int, str]:
    """Run a shell command and return (exit_code, output)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


def current_branch() -> str:
    _, out = run("git branch --show-current")
    return out.strip()


def verify_system() -> bool:
    """Run demo to verify the system works correctly."""
    print("Verificando que el sistema funciona...")
    code, out = run("python demo.py")
    if code == 0:
        print("  Sistema verificado correctamente.")
        return True
    else:
        print(f"  ERROR: El sistema tiene problemas.")
        print(f"  {out[:200]}")
        return False


def cmd_save(description: str) -> None:
    """Save current changes to develop branch."""
    print(f"\n{SEP}")
    print("GUARDANDO CAMBIOS EN DEVELOP")
    print(SEP)

    branch = current_branch()
    if branch != "develop":
        print(f"  Cambiando a rama develop...")
        code, out = run("git checkout develop")
        if code != 0:
            print(f"  ERROR: {out}")
            return

    code, out = run("git add .")
    if code != 0:
        print(f"  ERROR al agregar archivos: {out}")
        return

    code, out = run(f'git commit -m "{description}"')
    if code != 0:
        if "nothing to commit" in out:
            print("  No hay cambios nuevos para guardar.")
        else:
            print(f"  ERROR al hacer commit: {out}")
        return

    print(f"  Cambios guardados: {description}")
    print(f"  Rama: develop")


def cmd_promote() -> None:
    """Promote develop to master after verification."""
    print(f"\n{SEP}")
    print("PROMOVIENDO DEVELOP A MASTER")
    print(SEP)

    # First verify the system works
    if not verify_system():
        print("\n  No se puede promover a master porque el sistema tiene errores.")
        print("  Corrige los errores primero y vuelve a intentarlo.")
        return

    # Save any pending changes
    run("git add .")
    run('git commit -m "Auto-save antes de promover a master"')

    # Merge to master
    print("\n  Fusionando develop en master...")
    code, out = run("git checkout master")
    if code != 0:
        print(f"  ERROR: {out}")
        return

    code, out = run("git merge develop --no-ff -m 'Promovido desde develop - sistema verificado'")
    if code != 0:
        print(f"  ERROR al fusionar: {out}")
        run("git checkout develop")
        return

    run("git checkout develop")
    print("  Master actualizado correctamente.")
    print("  La base estable ahora incluye los ultimos cambios verificados.")


def cmd_restore() -> None:
    """Restore develop from master."""
    print(f"\n{SEP}")
    print("RESTAURANDO DESDE MASTER")
    print(SEP)

    print("  Esto descartara todos los cambios en develop")
    print("  y restaurara la ultima version estable de master.")
    confirm = input("  Confirmar? (s/n): ").strip().lower()
    if confirm not in ("s", "si", "y", "yes"):
        print("  Cancelado.")
        return

    run("git checkout master")
    code, out = run("git branch -D develop")
    code, out = run("git checkout -b develop")
    if code == 0:
        print("  Develop restaurado desde master correctamente.")
    else:
        print(f"  ERROR: {out}")


def cmd_status() -> None:
    """Show current git status."""
    print(f"\n{SEP}")
    print("ESTADO ACTUAL")
    print(SEP)

    _, branch = run("git branch --show-current")
    print(f"  Rama actual: {branch}")

    _, status = run("git status --short")
    if status:
        print(f"\n  Archivos modificados:")
        for line in status.split("\n"):
            print(f"    {line}")
    else:
        print("  Sin cambios pendientes.")

    print(f"\n  Ultimos commits:")
    _, log = run("git log --oneline -5")
    for line in log.split("\n"):
        print(f"    {line}")


def cmd_log() -> None:
    """Show commit history."""
    print(f"\n{SEP}")
    print("HISTORIAL DE CAMBIOS")
    print(SEP)
    _, log = run("git log --oneline --all --graph -20")
    print(log)


def main() -> None:
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        return

    command = args[0].lower()

    if command == "save":
        description = args[1] if len(args) > 1 else "Actualizacion sin descripcion"
        cmd_save(description)
    elif command == "promote":
        cmd_promote()
    elif command == "restore":
        cmd_restore()
    elif command == "status":
        cmd_status()
    elif command == "log":
        cmd_log()
    else:
        print(f"Comando no reconocido: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
