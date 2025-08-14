from flask import Blueprint, jsonify, current_app
from cierre_farmacias.utils.decorators import login_required
import importlib

pdf_bp = Blueprint('pdf', __name__)

# Map logical names to existing script modules and their entry function
PDF_SCRIPTS = [
    ('cierre_farmacias.pdf_scripts.PDF7_Traspaso','actualizar_excel_y_generar_pdf', 'Template Traspasos.xlsx', 'solicitud_traspaso_tabla'),
    ('cierre_farmacias.pdf_scripts.PDF_BAJA','actualizar_excel_y_generar_pdf', 'Formatobajaactivo.xlsx', 'Formato Baja'),
    ('cierre_farmacias.pdf_scripts.PDF_Tecnico','actualizar_excel_y_generar_pdf', 'Informe Tecnico.xlsx', 'Informe Tecnico'),
    ('cierre_farmacias.pdf_scripts.PDF_Recoleccion','actualizar_excel_y_generar_pdf', 'Compromiso_Recoleccion.xlsx', 'Formato Recoleccion')
]

@pdf_bp.route('/PDF/<departamento>/<ceco>', methods=['POST'])
@login_required
def generar(departamento, ceco):
    errors = []
    generated = []
    base_upload = current_app.config['BASE_UPLOAD']
    base_templates = current_app.config['PDF_TEMPLATES_DIR']
    for module_name, fn_name, template_file, prefix in PDF_SCRIPTS:
        try:
            mod = importlib.import_module(module_name)
            fn = getattr(mod, fn_name)
            output_dir = fr"{base_upload}\{departamento}\{ceco}"
            template_path = fr"{base_templates}\{template_file}"
            fn(template_path, output_dir, departamento, ceco)
            generated.append(prefix)
        except Exception as e:
            errors.append(f"{module_name}: {e}")
    status = 'ok' if not errors else 'partial'
    return jsonify({'status': status, 'generated': generated, 'errors': errors})
