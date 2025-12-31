from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

class User(UserMixin):
    def __init__(self, id, email, name, role, project_id, status='offline'):
        self.id = id
        self.email = email
        self.name = name
        self.role = role
        self.project_id = project_id
        self.status = status

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        from app import get_db as app_get_db
        db = app_get_db()
    return db

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """ Registers the main ADMIN account only. """
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        password = generate_password_hash(request.form['password'])
        
        db = get_db()
        try:
            # Create Main Admin (project_id is NULL)
            db.execute("INSERT INTO users (project_id, email, name, password, role, status) VALUES (NULL, ?, ?, ?, 'admin', 'offline')",
                       (email, name, password))
            db.commit()
            
            flash('Admin account created! Please login.')
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash(f'Error: {str(e)}')
            
    return render_template('register.html')

@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db()
        try:
            cur = db.execute("SELECT * FROM users WHERE email = ?", (email,))
            user_data = cur.fetchone()
            
            if user_data and check_password_hash(user_data['password'], password):
                # AUTOMATION: Set status to 'online' on login
                if user_data['role'] == 'agent':
                    db.execute("UPDATE users SET status = 'online' WHERE id = ?", (user_data['id'],))
                    db.commit()
                    # Update local variable to reflect new status immediately
                    status = 'online'
                else:
                    status = user_data['status']

                user = User(user_data['id'], user_data['email'], user_data['name'], user_data['role'], user_data['project_id'], status)
                login_user(user)
                
                if user.role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('agent.dashboard'))
            
            flash('Invalid email or password')
        except Exception as e:
            flash(f"Login Error: {e}")
        
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # AUTOMATION: Set status to 'offline' on logout
    if current_user.role == 'agent':
        db = get_db()
        db.execute("UPDATE users SET status = 'offline' WHERE id = ?", (current_user.id,))
        db.commit()

    logout_user()
    return redirect(url_for('auth.login'))