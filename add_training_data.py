# -*- coding: utf-8 -*-
"""
Interactive tool for adding training data to the analyzer.

Allows adding new labeled examples to data/training_data.py
and optionally retraining the models immediately.

Run with:
    python add_training_data.py
"""
from __future__ import annotations

import sys
import os
import io
import ast
import re
import subprocess

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

TRAINING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "training_data.py")

# ---------------------------------------------------------------------------
# Valid labels per category
# ---------------------------------------------------------------------------

CATEGORIES = {
    "intent": {
        "list_name": "INTENT_DATA",
        "labels": ["OFFER", "INQUIRY", "NEGOTIATION", "CLOSING", "DESCRIPTION"],
        "description": "Intencion principal del texto",
    },
    "sentiment": {
        "list_name": "SENTIMENT_DATA",
        "labels": ["POSITIVE", "NEUTRAL", "NEGATIVE"],
        "description": "Tono emocional del texto",
    },
    "sales": {
        "list_name": "SALES_CONCEPT_DATA",
        "labels": ["offer", "discount", "commission", "closing", "prospect",
                   "objection", "follow_up", "negotiation"],
        "description": "Concepto de ventas presente en el texto",
    },
    "realestate": {
        "list_name": "REAL_ESTATE_CONCEPT_DATA",
        "labels": ["property_type", "price", "area_sqm", "bedrooms", "bathrooms",
                   "location", "amenities", "zoning", "condition"],
        "description": "Concepto de bienes raices presente en el texto",
    },
}

SEP = "=" * 60
THIN = "-" * 60


def read_input(prompt: str) -> str:
    """Read a line from stdin, stripping whitespace."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\nSaliendo...")
        sys.exit(0)


def count_examples(list_name: str) -> int:
    """Count how many examples exist in a given list in the training file."""
    try:
        with open(TRAINING_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        # Count occurrences of the pattern inside the list
        pattern = rf'{list_name}.*?= \[(.*?)\]'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            block = match.group(1)
            return block.count('",')  + (1 if block.strip().endswith('"') else 0)
    except Exception:
        pass
    return 0


def append_example(list_name: str, text: str, label: str) -> bool:
    """
    Append a new (text, label) tuple to the specified list in training_data.py.
    Inserts before the closing bracket of the list.
    Returns True on success.
    """
    try:
        with open(TRAINING_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # Find the list block and its closing bracket
        # Pattern: find "LIST_NAME: list[...] = [" then find its closing "]"
        list_start = content.find(f"{list_name}:")
        if list_start == -1:
            print(f"[ERROR] No se encontro la lista '{list_name}' en el archivo.")
            return False

        # Find the opening bracket of the list
        bracket_open = content.find("[", list_start)
        if bracket_open == -1:
            return False

        # Find the matching closing bracket
        depth = 0
        pos = bracket_open
        bracket_close = -1
        while pos < len(content):
            if content[pos] == "[":
                depth += 1
            elif content[pos] == "]":
                depth -= 1
                if depth == 0:
                    bracket_close = pos
                    break
            pos += 1

        if bracket_close == -1:
            print("[ERROR] No se pudo encontrar el cierre de la lista.")
            return False

        # Build the new entry line
        # Escape any single quotes in text
        safe_text = text.replace("\\", "\\\\").replace('"', '\\"')
        new_entry = f'    ("{safe_text}", "{label}"),\n'

        # Insert before the closing bracket
        new_content = content[:bracket_close] + new_entry + content[bracket_close:]

        with open(TRAINING_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)

        return True

    except Exception as e:
        print(f"[ERROR] No se pudo escribir en el archivo: {e}")
        return False


def retrain_models() -> bool:
    """Run the training script and return True if successful."""
    print("\nEntrenando modelos, por favor espere...")
    print(THIN)
    result = subprocess.run(
        [sys.executable, "-m", "src.training.train_models"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=False,
    )
    return result.returncode == 0


def show_stats() -> None:
    """Show current example counts per category."""
    print("\nEstado actual del corpus de entrenamiento:")
    print(THIN)
    for cat_key, cat in CATEGORIES.items():
        count = count_examples(cat["list_name"])
        print(f"  {cat_key:<12} ({cat['list_name']:<30}) : {count} ejemplos")
    print()


def select_category() -> tuple[str, dict] | None:
    """Prompt user to select a category. Returns (key, category_dict) or None."""
    print("\n  Categorias:")
    keys = list(CATEGORIES.keys())
    for i, key in enumerate(keys, 1):
        cat = CATEGORIES[key]
        print(f"    {i}. {key:<12} - {cat['description']}")
    print("    0. Cancelar")

    while True:
        choice = read_input("  Categoria (numero): ").strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(keys):
            key = keys[int(choice) - 1]
            return key, CATEGORIES[key]
        if choice.lower() in CATEGORIES:
            key = choice.lower()
            return key, CATEGORIES[key]
        print(f"  Escribe un numero del 1 al {len(keys)} o 0 para cancelar.")


def select_label(category: dict) -> str | None:
    """Prompt user to select a label. Returns label string or None."""
    labels = category["labels"]
    print(f"  Etiquetas para {category['list_name']}:")
    for i, label in enumerate(labels, 1):
        print(f"    {i}. {label}")
    print("    0. Cancelar")

    while True:
        choice = read_input("  Etiqueta (numero): ").strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(labels):
            return labels[int(choice) - 1]
        if choice.upper() in [l.upper() for l in labels]:
            for label in labels:
                if label.upper() == choice.upper():
                    return label
        print(f"  Escribe un numero del 1 al {len(labels)} o 0 para cancelar.")


def add_single_example() -> bool:
    """Interactive flow to add one example to ALL relevant categories at once."""
    print("\n" + THIN)
    print("AGREGAR NUEVO EJEMPLO (todas las categorias en una pasada)")
    print(THIN)

    # Get text
    text = read_input("Texto de ejemplo (o ENTER para cancelar): ")
    if not text:
        return False

    print(f"\nTexto: {text[:80]}{'...' if len(text) > 80 else ''}")
    print("\nAhora elige todas las categorias y etiquetas que aplican.")
    print("Puedes agregar tantas como quieras. Escribe 'FIN' cuando termines.\n")

    assignments: list[tuple[str, str, str]] = []  # (list_name, label, cat_key)

    while True:
        print(f"  Asignaciones actuales: {len(assignments)}")
        for a in assignments:
            print(f"    - {a[2]:<12} -> {a[1]}")

        add_more = read_input("\nAgregar categoria? (s/n): ").lower()
        if add_more not in ("s", "si", "y", "yes"):
            break

        result = select_category()
        if result is None:
            continue
        cat_key, category = result

        label = select_label(category)
        if label is None:
            continue

        # Check for duplicate
        if any(a[0] == category["list_name"] and a[1] == label for a in assignments):
            print(f"  Ya agregaste {cat_key} -> {label}.")
            continue

        assignments.append((category["list_name"], label, cat_key))
        print(f"  Agregado: {cat_key} -> {label}")

    if not assignments:
        print("  No se agregaron categorias. Cancelado.")
        return False

    # Confirm all
    print(f"\nResumen final:")
    print(f"  Texto: {text[:80]}{'...' if len(text) > 80 else ''}")
    print(f"  Se guardara en {len(assignments)} lista(s):")
    for list_name, label, cat_key in assignments:
        print(f"    - {cat_key:<12} -> {label}")

    confirm = read_input("\nConfirmar todo? (s/n): ").lower()
    if confirm not in ("s", "si", "y", "yes"):
        print("  Cancelado.")
        return False

    # Save all
    saved = 0
    for list_name, label, cat_key in assignments:
        if append_example(list_name, text, label):
            print(f"  Guardado: {cat_key} -> {label}")
            saved += 1
        else:
            print(f"  Error al guardar: {cat_key} -> {label}")

    print(f"\n  {saved}/{len(assignments)} entradas guardadas correctamente.")
    return saved > 0


def add_bulk_examples() -> int:
    """Add multiple texts, each with multiple category/label assignments."""
    print("\n" + THIN)
    print("AGREGAR MULTIPLES TEXTOS (cada uno con todas sus categorias)")
    print(THIN)
    print("Para cada texto podras asignar todas las categorias que apliquen.")
    print("Escribe 'FIN' como texto para terminar.\n")

    total_saved = 0
    text_count = 0

    while True:
        text_count += 1
        text = read_input(f"Texto {text_count} (o FIN para terminar): ")
        if text.upper() == "FIN" or text == "":
            break

        print(f"\nTexto: {text[:80]}{'...' if len(text) > 80 else ''}")
        assignments: list[tuple[str, str, str]] = []

        while True:
            print(f"  Asignaciones: {len(assignments)}")
            for a in assignments:
                print(f"    - {a[2]:<12} -> {a[1]}")

            add_more = read_input("  Agregar categoria? (s/n): ").lower()
            if add_more not in ("s", "si", "y", "yes"):
                break

            result = select_category()
            if result is None:
                continue
            cat_key, category = result

            label = select_label(category)
            if label is None:
                continue

            if any(a[0] == category["list_name"] and a[1] == label for a in assignments):
                print(f"  Ya agregaste {cat_key} -> {label}.")
                continue

            assignments.append((category["list_name"], label, cat_key))
            print(f"  Agregado: {cat_key} -> {label}")

        if not assignments:
            print("  Sin categorias, texto omitido.\n")
            text_count -= 1
            continue

        # Save all assignments for this text
        saved = 0
        for list_name, label, cat_key in assignments:
            if append_example(list_name, text, label):
                saved += 1
        total_saved += saved
        print(f"  {saved} entrada(s) guardada(s) para este texto.\n")

    print(f"\n  Total: {total_saved} entrada(s) guardada(s) en {text_count} texto(s).")
    return total_saved


def main() -> None:
    print("\n" + SEP)
    print("  HERRAMIENTA DE DATOS DE ENTRENAMIENTO")
    print("  Analizador de Textos - Ventas y Bienes Raices")
    print(SEP)

    while True:
        show_stats()
        print("Opciones:")
        print("  1. Agregar un texto (con todas sus categorias)")
        print("  2. Agregar multiples textos (cada uno con sus categorias)")
        print("  3. Reentrenar modelos con los datos actuales")
        print("  4. Agregar un texto y reentrenar inmediatamente")
        print("  0. Salir")

        choice = read_input("\nElige una opcion: ")

        if choice == "0":
            print("\nHasta luego.\n")
            break

        elif choice == "1":
            added = add_single_example()
            if added:
                retrain = read_input("\nReentrenar modelos ahora? (s/n): ").lower()
                if retrain in ("s", "si", "y", "yes"):
                    ok = retrain_models()
                    if ok:
                        print("\nModelos actualizados correctamente.")
                    else:
                        print("\n[ERROR] El entrenamiento fallo. Revisa los datos.")

        elif choice == "2":
            count = add_bulk_examples()
            if count > 0:
                retrain = read_input("\nReentrenar modelos ahora? (s/n): ").lower()
                if retrain in ("s", "si", "y", "yes"):
                    ok = retrain_models()
                    if ok:
                        print("\nModelos actualizados correctamente.")
                    else:
                        print("\n[ERROR] El entrenamiento fallo. Revisa los datos.")

        elif choice == "3":
            ok = retrain_models()
            if ok:
                print("\nModelos actualizados correctamente.")
            else:
                print("\n[ERROR] El entrenamiento fallo.")

        elif choice == "4":
            added = add_single_example()
            if added:
                ok = retrain_models()
                if ok:
                    print("\nModelos actualizados correctamente.")
                else:
                    print("\n[ERROR] El entrenamiento fallo.")

        else:
            print("  Opcion no valida.")

        print()


if __name__ == "__main__":
    main()
