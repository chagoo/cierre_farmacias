"""Módulo para carga y manejo de archivos."""
from flask import Blueprint, render_template, request, redirect, url_for, flash

uploads_bp = Blueprint('uploads', __name__)


@uploads_bp.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Formulario simple para subir archivos.

    El procesamiento real de los archivos se moverá gradualmente desde el
    módulo monolítico original.
    """
    if request.method == 'POST':
        file = request.files.get('file')
        if file:
            flash(f'Se recibió el archivo {file.filename}', 'success')
        else:
            flash('No se seleccionó ningún archivo.', 'danger')
        return redirect(url_for('uploads.upload_file'))
    return render_template('upload.html')


@uploads_bp.route('/descargar/<path:filename>')
def download_file(filename):
    """Descarga un archivo previamente subido (pendiente de implementación)."""
    flash('Descarga no implementada.', 'warning')
    return redirect(url_for('uploads.upload_file'))
