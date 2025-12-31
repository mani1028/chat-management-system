from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_login import login_required, current_user

agent_bp = Blueprint('agent', __name__, url_prefix='/agent')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        from app import get_db as app_get_db
        db = app_get_db()
    return db

@agent_bp.before_request
def agent_check():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

@agent_bp.route('/dashboard')
def dashboard():
    db = get_db()
    
    # AUTO-FIX: If agent accesses dashboard, FORCE status to 'online'
    if current_user.status != 'online':
        db.execute("UPDATE users SET status = 'online' WHERE id = ?", (current_user.id,))
        db.commit()
        current_user.status = 'online' # Update local object for this request
    
    # SCOPE: Agent only sees chats for THEIR project
    my_project_id = current_user.project_id
    
    # Get Project Info
    project = db.execute("SELECT * FROM projects WHERE id = ?", (my_project_id,)).fetchone()
    if not project:
        flash("Error: You are assigned to a project that does not exist.")
        return redirect(url_for('auth.login'))

    # Active Chats assigned to ME
    my_chats = db.execute('''
        SELECT * FROM chats 
        WHERE assigned_agent_id = ? AND status IN ('assigned', 'open')
        ORDER BY created_at DESC
    ''', (current_user.id,)).fetchall()
    
    # Waiting Queue (Unassigned chats in MY project)
    queue = db.execute('''
        SELECT * FROM chats 
        WHERE project_id = ? AND status = 'queued'
        ORDER BY created_at ASC
    ''', (my_project_id,)).fetchall()
    
    return render_template('agent_dashboard.html', my_chats=my_chats, queue=queue, project=project)

@agent_bp.route('/claim/<int:chat_id>')
def claim_chat(chat_id):
    db = get_db()
    
    # Ensure chat belongs to agent's project
    chat = db.execute("SELECT * FROM chats WHERE id = ? AND project_id = ?", (chat_id, current_user.project_id)).fetchone()
    
    if chat and chat['status'] == 'queued':
        db.execute("UPDATE chats SET status = 'assigned', assigned_agent_id = ? WHERE id = ?", (current_user.id, chat_id))
        db.commit()
        
    return redirect(url_for('agent.dashboard'))

@agent_bp.route('/close/<int:chat_id>')
def close_chat(chat_id):
    db = get_db()
    
    # 1. Update DB Status to 'closed'
    db.execute('''
        UPDATE chats 
        SET status = 'closed' 
        WHERE id = ? AND assigned_agent_id = ?
    ''', (chat_id, current_user.id))
    db.commit()

    # 2. [NEW] Notify the Widget via SocketIO that the chat is over
    try:
        # Import inside function to avoid circular import with app.py
        from app import socketio 
        print(f"[AGENT] Closing chat {chat_id}, emitting event...")
        socketio.emit('chat_closed', {'msg': 'Agent has ended the chat session.'}, room=chat_id)
    except Exception as e:
        print(f"Error emitting chat_closed: {e}")

    return redirect(url_for('agent.dashboard'))