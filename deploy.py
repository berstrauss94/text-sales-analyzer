# -*- coding: utf-8 -*-
"""
deploy.py - Script de despliegue automatico completo.

Ejecuta en orden:
1. Verifica sintaxis del codigo
2. Corre los tests
3. Reentrena los modelos (opcional)
4. Guarda en git (develop)
5. Promueve a master
6. Sube a GitHub (Railway redespliega automaticamente)

Uso:
    python deploy.py "descripcion del cambio"
    python deploy.py "descripcion" --retrain     (incluye reentrenamiento)
    python deploy.py --status                    (solo muestra estado)
"""
from __future__ import annotations

import sys
import os
import io
import subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SEP = "=" * 60
THIN = "-" * 60


def run(cmd: str, capture: bool = False) -> tuple[int, str]:
    result = subprocess.run(
        cmd, shell=True, capture_output=capture, text=True,
        cwd=PROJECT_DIR
    )
    output = (result.stdout + result.stderr).strip() if capture else ""
    return result.returncode, output


def step(msg: str) -> None:
    print(f"\n{THIN}\n  {msg}\n{THIN}")


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


def main() -> None:
    args = sys.argv[1:]
    retrain = "--retrain" in args
    status_only = "--status" in args
    description = next((a for a in args if not a.startswith("--")), "Actualizacion automatica")

    print(f"\n{SEP}")
    print("  DESPLIEGUE AUTOMATICO - Analizador de Textos")
    print(SEP)

    if status_only:
        run("git status")
        run("git log --oneline -5")
        return

    # Step 1: Syntax check
    step("1. Verificando sintaxis del codigo...")
    code, out = run("python -m py_compile src/analyzer.py src/factory.py src/components/commercial_analyzer.py web_app.py", capture=True)
    if code != 0:
        fail("Error de sintaxis detectado:")
        print(out)
        sys.exit(1)
    ok("Sintaxis correcta")

    # Step 2: Run tests
    step("2. Ejecutando tests...")
    code, out = run("python -m pytest tests/ -q", capture=True)
    if code != 0:
        fail("Tests fallaron:")
        print(out)
        sys.exit(1)
    ok("Todos los tests pasan")

    # Step 3: Retrain models (optional)
    if retrain:
        step("3. Reentrenando modelos ML...")
        code, out = run("python -m src.training.train_models", capture=True)
        if code != 0:
            fail("Error en entrenamiento:")
            print(out)
            sys.exit(1)
        ok("Modelos reentrenados")
    else:
        print("\n  (Reentrenamiento omitido. Usa --retrain para incluirlo)")

    # Step 4: Git save to develop
    step("4. Guardando cambios en develop...")
    run("git checkout develop")
    run("git add .")
    code, out = run(f'git commit -m "{description}"', capture=True)
    if "nothing to commit" in out:
        print("  Sin cambios nuevos para guardar.")
    else:
        ok(f"Commit: {description}")

    # Step 5: Promote to master
    step("5. Promoviendo a master...")
    run("git checkout master")
    code, out = run(f'git merge develop --no-ff -m "Deploy: {description}"', capture=True)
    if code != 0:
        fail("Error en merge:")
        print(out)
        run("git checkout develop")
        sys.exit(1)
    ok("Master actualizado")

    # Step 6: Push to GitHub
    step("6. Subiendo a GitHub (Railway redespliega automaticamente)...")
    code, out = run("git push origin master", capture=True)
    if code != 0:
        fail("Error en push:")
        print(out)
        sys.exit(1)
    ok("Codigo subido a GitHub")

    # Return to develop
    run("git checkout develop")

    print(f"\n{SEP}")
    print("  DESPLIEGUE COMPLETADO")
    print(f"  Railway redesplegara en 2-3 minutos.")
    print(SEP + "\n")


if __name__ == "__main__":
    main()
