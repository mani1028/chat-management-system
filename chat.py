from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_login import login_required, current_user

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        from app import get_db as app_get_db
        db = app_get_db()
    return db

@chat_bp.route('/<int:chat_id>')
@login_required
def view_chat(chat_id):
    db = get_db()
    
    # 1. Fetch Chat
    chat = db.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    
    # 2. Handle 404 Case (Chat not found)
    if chat is None:
        flash("Error: Chat not found or has been deleted.")
        return redirect(url_for('agent.dashboard'))
    
    # 3. Security Check: Ensure Agent belongs to the same Project
    if current_user.role == 'agent':
        # Force integer conversion for strict comparison
        # This fixes issues where DB might return '1' (str) vs 1 (int)
        try:
            chat_project_id = int(chat['project_id'])
            user_project_id = int(current_user.project_id)
            
            if chat_project_id != user_project_id:
                flash("Unauthorized: You cannot access chats from another project.")
                return redirect(url_for('agent.dashboard'))
        except (ValueError, TypeError, KeyError) as e:
            # Fallback for data corruption
            print(f"Data Error in Chat View: {e}")
            flash("System Error: Invalid Project ID data.")
            return redirect(url_for('agent.dashboard'))

    messages = db.execute("SELECT * FROM messages WHERE chat_id = ? ORDER BY timestamp ASC", (chat_id,)).fetchall()
    
    return render_template('chat.html', chat=chat, messages=messages)