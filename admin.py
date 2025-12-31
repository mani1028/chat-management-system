from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        from app import get_db as app_get_db
        db = app_get_db()
    return db

@admin_bp.before_request
def admin_check():
    if not current_user.is_authenticated or current_user.role != 'admin':
        return redirect(url_for('auth.login'))

@admin_bp.route('/dashboard')
def dashboard():
    db = get_db()
    
    # 1. Stats Overview
    stats = {}
    stats['projects'] = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    stats['agents'] = db.execute("SELECT COUNT(*) FROM users WHERE role='agent'").fetchone()[0]
    stats['active_chats'] = db.execute("SELECT COUNT(*) FROM chats WHERE status='assigned'").fetchone()[0]
    
    # 2. Projects List
    projects = db.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()

    # 3. Agents List (With Project Name)
    agents = db.execute("""
        SELECT u.*, p.project_name 
        FROM users u 
        LEFT JOIN projects p ON u.project_id = p.id 
        WHERE u.role='agent'
    """).fetchall()

    # 4. Recent Chats (Global View)
    chats = db.execute("""
        SELECT c.*, p.project_name, u.name as agent_name 
        FROM chats c 
        JOIN projects p ON c.project_id = p.id
        LEFT JOIN users u ON c.assigned_agent_id = u.id 
        ORDER BY c.created_at DESC LIMIT 10
    """).fetchall()
    
    return render_template('admin_dashboard.html', stats=stats, projects=projects, agents=agents, chats=chats)

@admin_bp.route('/project/create', methods=['POST'])
def create_project():
    project_name = request.form['project_name']
    client_name = request.form['client_name']
    
    db = get_db()
    db.execute("INSERT INTO projects (project_name, client_name) VALUES (?, ?)", (project_name, client_name))
    db.commit()
    flash('Project created successfully.')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/agent/create', methods=['POST'])
def create_agent():
    name = request.form['name']
    email = request.form['email']
    password = generate_password_hash(request.form['password'])
    project_id = request.form['project_id']
    
    db = get_db()
    try:
        db.execute("INSERT INTO users (project_id, name, email, password, role) VALUES (?, ?, ?, ?, 'agent')",
                   (project_id, name, email, password))
        db.commit()
        flash('Agent created successfully.')
    except Exception as e:
        flash(f'Error creating agent: {e}')
        
    return redirect(url_for('admin.dashboard'))