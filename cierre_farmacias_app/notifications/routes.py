from flask import Blueprint, request, jsonify
from ..auth.routes import login_required
from ..extensions import db
from ..services.notifications import send_notification_email

bp = Blueprint('notifications', __name__)


@bp.route('/send_notifications', methods=['POST'])
@login_required
def send_notifications():
    data = request.get_json() or {}
    ceco = data.get('ceco')
    departamento = data.get('departamento')
    if not ceco or not departamento:
        return jsonify({'error': 'CECO y Departamento son requeridos'}), 400
    result = send_notification_email(ceco, departamento, db)
    return jsonify(result)
