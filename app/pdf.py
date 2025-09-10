"""Generación de archivos PDF."""
from flask import Blueprint, request, flash, redirect, url_for

pdf_bp = Blueprint('pdf', __name__)


@pdf_bp.route('/PDF/<departamento>/<ceco>', methods=['POST'])
def generar_pdf(departamento, ceco):
    """Genera un PDF para la combinación departamento/ceco.

    Esta función es un contenedor y debe completarse con la lógica existente
    en el módulo original.
    """
    flash('Generación de PDF no implementada.', 'warning')
    return redirect(url_for('uploads.upload_file'))
