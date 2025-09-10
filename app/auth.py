"""Rutas relacionadas con autenticación de usuarios."""
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from sqlalchemy import text
from werkzeug.security import check_password_hash
import hashlib
import re

from . import db


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Formulario de inicio de sesión."""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Usuario y contraseña requeridos", "danger")
            return redirect(url_for("auth.login"))
        query = text(
            """
            SELECT [Usuario], CAST([Password] AS NVARCHAR(256)) AS Password,
                   [Nivel Acceso], [Nombre], [Apellido Paterno], [Correo]
            FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
            WHERE [Usuario] = :u
            """
        )
        try:
            with db.engine.connect() as conn:
                row = conn.execute(query, {"u": username}).fetchone()
            if row:
                stored_pw = (row.Password or "").strip()
                valid = False
                try:
                    if stored_pw:
                        valid = check_password_hash(stored_pw, password)
                except Exception:
                    valid = False
                if not valid and stored_pw:
                    cand = stored_pw[2:] if stored_pw.lower().startswith("0x") else stored_pw
                    if re.fullmatch(r"[A-Fa-f0-9]{64}", cand or ""):
                        sha_hex = hashlib.sha256(password.encode("utf-8")).hexdigest()
                        if sha_hex.lower() == cand.lower():
                            valid = True
                if not valid and stored_pw == password:
                    valid = True
                if valid:
                    nivel = int(row[2])
                    if nivel == 2:
                        session["user_id"] = row[0]
                        session["nombre_completo"] = f"{row[3]} {row[4]}"
                        session["nivel_acceso"] = nivel
                        session["email"] = row[5]
                        return redirect(url_for("auth.dashboard"))
                    flash("No tiene permisos para acceder al sistema", "danger")
                else:
                    flash("Usuario o contraseña incorrectos", "danger")
            else:
                flash("Usuario o contraseña incorrectos", "danger")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        return redirect(url_for("auth.login"))
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Cierra la sesión del usuario actual."""
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/")
def index():
    """Redirige a la página de login por defecto."""
    return redirect(url_for("auth.login"))


@auth_bp.route("/dashboard")
def dashboard():
    """Panel principal tras autenticación."""
    if "user_id" in session and session.get("nivel_acceso") == 2:
        return render_template("dashboard2.html")
    flash("Acceso no autorizado", "danger")
    return redirect(url_for("auth.login"))

