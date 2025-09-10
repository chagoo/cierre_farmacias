"""Rutas de administración del sistema."""
from flask import Blueprint, render_template, flash

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/usuarios')
def listar_usuarios():
    """Muestra la lista de usuarios registrados."""
    flash('Listado de usuarios no implementado.', 'warning')
    return render_template('Usuarios.html', usuarios=[])


@admin_bp.route('/accesos', methods=['GET', 'POST'])
def gestionar_accesos():
    """Administración básica de accesos."""
    flash('Administración de accesos no implementada.', 'warning')
    return render_template('accesos.html')
