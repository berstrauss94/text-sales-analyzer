# -*- coding: utf-8 -*-
"""
User management module.

Handles user registration, authentication and storage.
Each user is stored as a plain text file in the /usuarios folder.
Passwords are hashed with SHA-256 — never stored in plain text.
"""
from __future__ import annotations

import os
import hashlib
import re
from datetime import datetime, timezone
from dataclasses import dataclass


USERS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "usuarios"
)


@dataclass
class User:
    username: str
    nombre: str
    apellido: str
    dni: str
    email: str
    telefono: str
    empresa: str
    cargo: str
    created_at: str


class UserManager:
    """Manages user registration and authentication."""

    def __init__(self, users_dir: str = USERS_DIR) -> None:
        self.users_dir = users_dir
        os.makedirs(users_dir, exist_ok=True)

    def _user_file(self, username: str) -> str:
        safe = re.sub(r'[^a-zA-Z0-9_-]', '_', username)
        return os.path.join(self.users_dir, f"{safe}.txt")

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def user_exists(self, username: str) -> bool:
        return os.path.exists(self._user_file(username))

    def register(
        self,
        username: str,
        password: str,
        nombre: str,
        apellido: str,
        email: str,
        celular: str,
        direccion: str,
        segundo_nombre: str = "",
        tercer_nombre: str = "",
        segundo_apellido: str = "",
        empresa: str = "",
        cargo: str = "",
    ) -> dict:
        """
        Register a new user.
        Returns {"ok": True} or {"ok": False, "error": "message"}.
        """
        # Validations
        if not username or len(username) < 8:
            return {"ok": False, "error": "El usuario debe tener al menos 8 caracteres."}
        if re.search(r'[^a-zA-Z0-9._-]', username):
            return {"ok": False, "error": "El usuario solo puede contener letras, numeros, puntos, guiones y guiones bajos."}
        if not any(c.isupper() for c in username):
            return {"ok": False, "error": "El usuario debe contener al menos una letra mayuscula."}
        if not password or len(password) < 8:
            return {"ok": False, "error": "La contrasena debe tener al menos 8 caracteres."}
        if not any(c.isupper() for c in password):
            return {"ok": False, "error": "La contrasena debe contener al menos una letra mayuscula."}
        if not nombre.strip():
            return {"ok": False, "error": "El nombre es obligatorio."}
        if not apellido.strip():
            return {"ok": False, "error": "El apellido es obligatorio."}
        if not email.strip():
            return {"ok": False, "error": "El correo electronico es obligatorio."}
        if not celular.strip():
            return {"ok": False, "error": "El numero de celular es obligatorio."}
        if not direccion.strip():
            return {"ok": False, "error": "La direccion es obligatoria."}
        if self.user_exists(username):
            return {"ok": False, "error": f"El usuario '{username}' ya existe."}

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        password_hash = self._hash_password(password)

        # Build full name
        nombre_completo_parts = [nombre]
        if segundo_nombre.strip():
            nombre_completo_parts.append(segundo_nombre)
        if tercer_nombre.strip():
            nombre_completo_parts.append(tercer_nombre)
        nombre_completo = " ".join(nombre_completo_parts)

        apellido_completo_parts = [apellido]
        if segundo_apellido.strip():
            apellido_completo_parts.append(segundo_apellido)
        apellido_completo = " ".join(apellido_completo_parts)

        # Write user file
        content = (
            f"=== FICHA DE USUARIO ===\n"
            f"Fecha de registro : {now}\n"
            f"\n"
            f"--- DATOS DE ACCESO ---\n"
            f"Usuario           : {username}\n"
            f"Contrasena (hash) : {password_hash}\n"
            f"\n"
            f"--- DATOS PERSONALES ---\n"
            f"Nombre            : {nombre_completo}\n"
            f"Apellido          : {apellido_completo}\n"
            f"Celular           : {celular}\n"
            f"Email             : {email}\n"
            f"Direccion         : {direccion}\n"
            f"\n"
            f"--- DATOS PROFESIONALES ---\n"
            f"Empresa           : {empresa}\n"
            f"Cargo             : {cargo}\n"
            f"\n"
            f"========================\n"
        )

        with open(self._user_file(username), "w", encoding="utf-8") as f:
            f.write(content)

        # Persist the account in PostgreSQL too so it survives Railway redeploys
        # (the .txt above lives on the ephemeral filesystem). Best-effort: if PG
        # is unavailable (local dev) we still succeed via the .txt file.
        try:
            from src.users import user_store_pg
            user_store_pg.upsert_user(username, password_hash, content)
        except Exception:
            pass

        return {"ok": True, "username": username}

    def login(self, username: str, password: str) -> dict:
        """
        Authenticate a user.
        Returns {"ok": True, "username": ...} or {"ok": False, "error": ...}.
        """
        password_hash = self._hash_password(password)

        # Primary source: local .txt credential file (fast, dev-friendly).
        # Fallback: PostgreSQL app_users, for accounts whose .txt was wiped on a
        # Railway redeploy. Without this, a persisted user could not log back in.
        if not self.user_exists(username):
            try:
                from src.users import user_store_pg
                pg_user = user_store_pg.get_user(username)
            except Exception:
                pg_user = None
            if pg_user and pg_user.get("password_hash") == password_hash:
                # Rehydrate the local .txt cache so subsequent reads work offline.
                try:
                    with open(self._user_file(username), "w", encoding="utf-8") as f:
                        f.write(pg_user.get("ficha", ""))
                except Exception:
                    pass
                return {"ok": True, "username": username}
            return {"ok": False, "error": "Usuario o contrasena incorrectos."}

        with open(self._user_file(username), "r", encoding="utf-8") as f:
            content = f.read()

        # Extract stored hash from the dedicated field to avoid false positives
        # if the hash happens to appear in another field (empresa, direccion, etc.)
        stored_hash = None
        for line in content.splitlines():
            if line.startswith("Contrasena (hash)"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    stored_hash = parts[1].strip()
                break

        if stored_hash is not None and stored_hash == password_hash:
            return {"ok": True, "username": username}
        # Legacy fallback: files written before this fix used a looser check
        if stored_hash is None and password_hash in content:
            return {"ok": True, "username": username}
        return {"ok": False, "error": "Usuario o contrasena incorrectos."}

    def list_users(self) -> list[str]:
        """
        Return the list of registered usernames.

        Combines two sources so no seller ever disappears from the list:
          1. Local usuarios/*.txt credential files (fast, but EPHEMERAL on
             Railway — wiped on every redeploy).
          2. Every username that has saved texts in PostgreSQL (PERSISTENT).

        A seller registered after the last deploy keeps only their PG entries;
        including PG usernames here means they still show up in the list even
        though their .txt was lost on redeploy.
        """
        users: set[str] = set()

        # 1. Local .txt credential files
        try:
            for fname in os.listdir(self.users_dir):
                if fname.endswith(".txt") and fname != "README.txt":
                    users.add(fname[:-4])
        except FileNotFoundError:
            pass

        # 2. Usernames that have entries persisted in PostgreSQL
        try:
            from src.users.history_manager import get_all_usernames_with_entries
            for name in get_all_usernames_with_entries():
                if name:
                    users.add(name)
        except Exception:
            # PG unavailable (local dev) — fall back to just the .txt files
            pass

        # 3. Accounts persisted in app_users (may exist without any texts yet)
        try:
            from src.users import user_store_pg
            for name in user_store_pg.list_usernames():
                if name:
                    users.add(name)
        except Exception:
            pass

        return sorted(users)

    def get_user_info(self, username: str) -> str | None:
        """Return the raw ficha text of a user (.txt first, PG fallback)."""
        path = self._user_file(username)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        # Fallback: the ficha persisted in PostgreSQL (survives redeploys).
        try:
            from src.users import user_store_pg
            pg_user = user_store_pg.get_user(username)
            if pg_user and pg_user.get("ficha"):
                return pg_user["ficha"]
        except Exception:
            pass
        return None
