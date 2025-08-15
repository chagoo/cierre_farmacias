from flask import Blueprint, jsonify
from ..auth.routes import login_required
from ..extensions import db
from ..services.reports import fetch_data, fetch_summary

bp = Blueprint('reports', __name__)


@bp.route('/data')
@login_required
def data():
    return jsonify(fetch_data(db))


@bp.route('/summary')
@login_required
def summary():
    return jsonify(fetch_summary(db))
