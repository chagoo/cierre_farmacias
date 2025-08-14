from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Inicie sesión','danger')
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)
    return wrapper

def nivel_acceso_required(level=2):
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if session.get('nivel_acceso') != level:
                flash('Sin permisos','danger')
                return redirect(url_for('auth.login'))
            return view(*args, **kwargs)
        return wrapper
    return deco
