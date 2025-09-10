"""Rutas relacionadas con autenticación de usuarios."""
from flask import Blueprint, render_template, request, redirect, url_for, flash

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Formulario de inicio de sesión.

    La lógica real de autenticación se migrará desde el módulo original
    posteriormente. De momento solo muestra la plantilla de login y
    redirige a sí misma cuando se envía el formulario.
    """
    if request.method == 'POST':
        flash('Autenticación no implementada en este módulo.', 'warning')
        return redirect(url_for('auth.login'))
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """Cierra la sesión del usuario actual."""
    flash('Logout no implementado.', 'warning')
    return redirect(url_for('auth.login'))
