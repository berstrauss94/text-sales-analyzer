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
        dni: str,
        email: str,
        telefono: str = "",
        empresa: str = "",
        cargo: str = "",
    ) -> dict:
        """
        Register a new user.
        Returns {"ok": True} or {"ok": False, "error": "message"}.
        """
        # Validations
        if not username or len(username) < 3:
            return {"ok": False, "error": "El nombre de usuario debe tener al menos 3 caracteres."}
        if re.search(r'[^a-zA-Z0-9._-]', username):
            return {"ok": False, "error": "El usuario solo puede contener letras, numeros, puntos, guiones y guiones bajos."}
        if not password or len(password) < 6:
            return {"ok": False, "error": "La contrasena debe tener al menos 6 caracteres."}
        if not nombre.strip():
            return {"ok": False, "error": "El nombre es obligatorio."}
        if not apellido.strip():
            return {"ok": False, "error": "El apellido es obligatorio."}
        if not dni.strip():
            return {"ok": False, "error": "El DNI es obligatorio."}
        if self.user_exists(username):
            return {"ok": False, "error": f"El usuario '{username}' ya existe."}

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        password_hash = self._hash_password(password)

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
            f"Nombre            : {nombre}\n"
            f"Apellido          : {apellido}\n"
            f"DNI               : {dni}\n"
            f"Email             : {email}\n"
            f"Telefono          : {telefono}\n"
            f"\n"
            f"--- DATOS PROFESIONALES ---\n"
            f"Empresa           : {empresa}\n"
            f"Cargo             : {cargo}\n"
            f"\n"
            f"========================\n"
        )

        with open(self._user_file(username), "w", encoding="utf-8") as f:
            f.write(content)

        return {"ok": True, "username": username}

    def login(self, username: str, password: str) -> dict:
        """
        Authenticate a user.
        Returns {"ok": True, "username": ...} or {"ok": False, "error": ...}.
        """
        if not self.user_exists(username):
            return {"ok": False, "error": "Usuario o contrasena incorrectos."}

        password_hash = self._hash_password(password)

        with open(self._user_file(username), "r", encoding="utf-8") as f:
            content = f.read()

        if password_hash in content:
            return {"ok": True, "username": username}
        return {"ok": False, "error": "Usuario o contrasena incorrectos."}

    def list_users(self) -> list[str]:
        """Return list of registered usernames."""
        users = []
        for fname in os.listdir(self.users_dir):
            if fname.endswith(".txt") and fname != "README.txt":
                users.append(fname[:-4])
        return sorted(users)

    def get_user_info(self, username: str) -> str | None:
        """Return the raw text content of a user file."""
        path = self._user_file(username)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
