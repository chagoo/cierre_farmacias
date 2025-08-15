from flask import Blueprint, request, jsonify, render_template
from ..auth.routes import login_required
from ..extensions import db
from ..services.uploads import process_upload
from ..services.notifications import send_notification_email
from ..utils.files import allowed_file

bp = Blueprint('uploads', __name__)


@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
        file = request.files['file']
        tipo_general = request.form.get('tipo_general')

        if file.filename == '':
            return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
        if not tipo_general:
            return jsonify({'error': 'Debe seleccionar un Tipo General (Baja o Traspaso)'}), 400
        if file and allowed_file(file.filename):
            try:
                df = process_upload(file, tipo_general, db)
                notification_results = []
                for (ceco, departamento), group in df.groupby(['Ceco', 'Departamento']):
                    result = send_notification_email(ceco, departamento, db)
                    notification_results.append({'ceco': ceco, 'departamento': departamento, 'result': result})
                return jsonify({
                    'success': True,
                    'message': f'Se insertaron {len(df)} registros exitosamente',
                    'notifications': notification_results
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 500
    return render_template('index_excel_Monse5.html')
