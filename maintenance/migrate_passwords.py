"""
Password migration tool

Capabilities:
- Detect passwords already hashed by Werkzeug (scrypt/pbkdf2) -> leave as-is.
- Detect SHA2_256 passwords stored as HEX (64 hex chars, with or without 0x) -> reset to a random temporary password and store a secure Werkzeug hash.
- Detect legacy plaintext -> hash the same plaintext so users keep their password.

Outputs a CSV with the actions taken so admins can notify temporary passwords.

Usage (PowerShell):
  # Dry run (no changes)
  .\Scripts\python.exe .\maintenance\migrate_passwords.py --dry-run

  # Apply changes
  .\Scripts\python.exe .\maintenance\migrate_passwords.py --apply

Environment variables required (same as app): DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD
Optionally: DEFAULT_TEMP_PASSWORD (to use a fixed temp password instead of random)
"""

from __future__ import annotations

import csv
import os
import re
import secrets
import string
from datetime import datetime

from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def db_url() -> str:
    server = os.getenv("DB_SERVER", "")
    name = os.getenv("DB_NAME", "")
    user = os.getenv("DB_USER", "")
    pwd = os.getenv("DB_PASSWORD", "")
    if not all([server, name, user, pwd]):
        raise RuntimeError("Faltan variables de entorno DB_SERVER, DB_NAME, DB_USER o DB_PASSWORD")
    return f"mssql+pyodbc://{user}:{pwd}@{server}/{name}?driver=ODBC+Driver+17+for+SQL+Server"


def is_werkzeug_hash(pw: str) -> bool:
    return pw.startswith("pbkdf2:") or pw.startswith("scrypt:")


def is_sha256_hex(pw: str) -> bool:
    if not pw:
        return False
    p = pw[2:] if pw.lower().startswith("0x") else pw
    return re.fullmatch(r"[A-Fa-f0-9]{64}", p) is not None


def gen_temp_password(length: int = 12) -> str:
    # A-Z a-z 0-9 + some symbols
    alphabet = string.ascii_letters + string.digits + "!@#$%*?"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main(apply: bool = False) -> None:
    engine = create_engine(db_url(), future=True)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(os.getcwd(), f"migrated_passwords_{now}.csv")

    rows_changed = 0
    records: list[dict] = []
    default_temp = os.getenv("DEFAULT_TEMP_PASSWORD", "")

    with engine.begin() as conn:
        res = conn.execute(text(
            """
            SELECT id, [Usuario], [Correo], CAST([Password] AS NVARCHAR(256)) AS Password
            FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
            """
        ))
        for r in res:
            user_id = r.id
            usuario = r.Usuario
            correo = r.Correo
            pw = (r.Password or "").strip()

            action = "skip"
            new_hash = None
            temp_password = ""

            if not pw:
                # No password set -> set temp
                action = "reset_temp"
                temp_password = default_temp or gen_temp_password()
                new_hash = generate_password_hash(temp_password)
            elif is_werkzeug_hash(pw):
                action = "already_hashed"
            elif is_sha256_hex(pw):
                action = "reset_temp"
                temp_password = default_temp or gen_temp_password()
                new_hash = generate_password_hash(temp_password)
            else:
                # Assume legacy plaintext -> hash as-is so it keeps working
                action = "hashed_plaintext"
                new_hash = generate_password_hash(pw)

            if apply and new_hash:
                conn.execute(
                    text("UPDATE [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web] SET [Password]=:pw WHERE id=:id"),
                    {"pw": new_hash, "id": int(user_id)},
                )
                rows_changed += 1

            if action != "already_hashed":
                records.append(
                    {
                        "id": user_id,
                        "usuario": usuario,
                        "correo": correo,
                        "action": action,
                        "temp_password": temp_password,
                    }
                )

    # Always write the CSV to review what would happen
    if records:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["id", "usuario", "correo", "action", "temp_password"])
            w.writeheader()
            w.writerows(records)

    print(f"Reporte: {out_path}")
    if apply:
        print(f"Filas actualizadas: {rows_changed}")
    else:
        print("DRY RUN: no se aplicaron cambios. Ejecute con --apply para escribir.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrar contraseñas a hashes de Werkzeug")
    parser.add_argument("--apply", action="store_true", help="Aplicar cambios (por defecto solo dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Forzar dry-run (no cambios)")
    args = parser.parse_args()

    apply_changes = bool(args.apply and not args.dry_run)
    main(apply=apply_changes)
