from functools import wraps
from flask import session, redirect, url_for, g
from api.models import User

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        user = User.query.filter_by(email=session['user']['email']).first()
        if not user:
            return redirect(url_for('login'))
        g.user = user
        return func(*args, **kwargs)
    return wrapper

def token_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user' not in session or 'token' not in session:
            return redirect(url_for('login'))
        user = User.query.filter_by(email=session['user']['email']).first()
        if not user:
            return redirect(url_for('login'))
        g.user = user
        return func(*args, **kwargs)
    return wrapper