import eventlet
eventlet.monkey_patch() # Must be the very first line

import sqlite3
import os
import traceback
from flask import Flask, g, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_login import LoginManager

# --- CONFIGURATION ---
app = Flask(__name__)

# [FIX] Use Environment Variable for security (with fallback for dev)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'project_cmr_secret_key_dev_fallback')

# Absolute path to DB to prevent path errors
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'cmr_database.db')
app.config['DATABASE'] = DB_PATH

# Initialize SocketIO with aggressive logging for debugging
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=True, engineio_logger=True)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

# --- DATABASE HELPERS ---

def get_db():
    """Request-based DB connection (for Flask routes)"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db

def get_socket_db():
    """Socket-based DB connection (Thread-safe)"""
    try:
        # check_same_thread=False is REQUIRED for SocketIO eventlet threads
        db = sqlite3.connect(app.config['DATABASE'], check_same_thread=False)
        db.row_factory = sqlite3.Row
        return db
    except Exception as e:
        print(f"[CRITICAL DB ERROR] {e}")
        return None

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Define Tables
        tables = [
            '''CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                client_name TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER, 
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'agent')),
                status TEXT DEFAULT 'offline',
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )''',
            '''CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                customer_name TEXT,
                customer_email TEXT,
                status TEXT DEFAULT 'queued',
                assigned_agent_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(assigned_agent_id) REFERENCES users(id),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )''',
            '''CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                sender_type TEXT NOT NULL, 
                sender_name TEXT,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(chat_id) REFERENCES chats(id)
            )'''
        ]
        
        for table in tables:
            cursor.execute(table)
            
        db.commit()
        print(f"Database initialized at: {DB_PATH}")

# --- AUTH LOADER ---
from auth import User
@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    try:
        cur = db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cur.fetchone()
        if user:
            return User(user['id'], user['email'], user['name'], user['role'], user['project_id'], user['status'])
    except:
        pass
    return None

# --- BLUEPRINTS ---
from auth import auth_bp
from admin import admin_bp
from agent import agent_bp
from chat import chat_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(agent_bp)
app.register_blueprint(chat_bp)

@app.route('/test')
def test_page():
    db = get_db()
    projects = db.execute("SELECT * FROM projects").fetchall()
    return render_template('test.html', projects=projects)


# ==========================================
#        SOCKET.IO EVENT HANDLERS
# ==========================================

# [CONFIG] Change this number to manually control chat limit per agent
MAX_CHATS_PER_AGENT = 3

def find_best_agent(db, project_id):
    print(f"[LOGIC] Finding best agent for Project ID: {project_id}...")
    query = '''
        SELECT u.id, u.name, COUNT(c.id) as active_count
        FROM users u
        LEFT JOIN chats c ON u.id = c.assigned_agent_id AND c.status = 'assigned'
        WHERE u.project_id = ? AND u.role = 'agent' AND u.status = 'online'
        GROUP BY u.id
        ORDER BY active_count ASC
    '''
    try:
        agents = db.execute(query, (project_id,)).fetchall()
        
        available_agents = []
        for a in agents:
             # Handle Row object vs Tuple access
             try:
                 count = a['active_count']
             except (IndexError, KeyError):
                 count = a[2] if len(a) > 2 else 0

             if count < MAX_CHATS_PER_AGENT:
                 available_agents.append(a)
                 
        if available_agents:
            chosen = available_agents[0]
            print(f"[LOGIC] Selected Agent: {chosen['name']} (ID: {chosen['id']})")
            return chosen
    except Exception as e:
        print(f"[ERROR] Error finding agent: {e}")
    
    return None

@socketio.on('connect')
def handle_connect():
    print(f"[SOCKET] Client connected: {request.sid}")

@socketio.on('join_chat')
def handle_join_chat(data):
    chat_id = data.get('chat_id')
    
    # [FIX] Validate Chat Status on Join & Load History
    db = get_socket_db()
    if db and chat_id:
        chat = db.execute("SELECT status FROM chats WHERE id = ?", (chat_id,)).fetchone()
        
        # If chat is closed, REJECT the join and force client reset
        if chat and chat['status'] == 'closed':
            db.close()
            print(f"[SOCKET] Refusing join for closed chat {chat_id}")
            emit('chat_closed', {'msg': 'This session has expired.'}, room=request.sid)
            return

        # [NEW] INSTANT LOAD: Send previous messages immediately
        try:
            msgs = db.execute("SELECT sender_type, message, sender_name FROM messages WHERE chat_id = ? ORDER BY timestamp ASC", (chat_id,)).fetchall()
            history = [{'sender_type': m['sender_type'], 'message': m['message'], 'sender_name': m['sender_name']} for m in msgs]
            emit('chat_history', {'history': history}, room=request.sid)
        except Exception as e:
            print(f"Error loading history: {e}")

        db.close()

    if chat_id:
        join_room(chat_id)
        print(f"[SOCKET] Client {request.sid} joined room: {chat_id}")

@socketio.on('create_chat')
def handle_create_chat(data):
    print(f"\n[SOCKET] >>> create_chat EVENT RECEIVED from {request.sid}")
    
    project_id_raw = data.get('project_id')
    name = data.get('name')
    email = data.get('email')
    initial_msg = data.get('message')
    
    db = get_socket_db()
    if not db:
        emit('chat_error', {'msg': 'Database Connection Failed'})
        return
    
    try:
        try:
            project_id = int(project_id_raw)
        except (ValueError, TypeError):
            emit('chat_error', {'msg': 'Invalid Project ID format'})
            return

        # 1. Check Project Exists
        project = db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            emit('chat_error', {'msg': 'Project ID not found.'})
            return
            
        # 2. Assign Agent Logic
        agent = None
        status = 'queued'
        agent_id = None
        
        try:
            agent = find_best_agent(db, project_id)
            if agent:
                status = 'assigned'
                agent_id = agent['id']
        except Exception as e:
            print(f"[WARNING] Agent assignment failed: {e}")
        
        # 3. Create Chat
        cur = db.execute("INSERT INTO chats (project_id, customer_name, customer_email, status, assigned_agent_id) VALUES (?, ?, ?, ?, ?)", 
                    (project_id, name, email, status, agent_id))
        chat_id = cur.lastrowid
        
        # 4. Save Message
        db.execute("INSERT INTO messages (chat_id, sender_type, sender_name, message) VALUES (?, 'customer', ?, ?)", 
                   (chat_id, name, initial_msg))
        db.commit()
        
        # 5. Join Room & Notify
        join_room(chat_id)
        
        emit('chat_created', {'chat_id': chat_id, 'status': status}) 
        
        # [NEW] Instant Echo: Show the user their own message immediately
        socketio.emit('new_message', {'sender_type': 'customer', 'sender_name': name, 'message': initial_msg}, room=chat_id)
        
        # Notify Agents
        if agent and agent_id:
            socketio.emit('dashboard_update', {'msg': 'New Chat Assigned'}, room=f"agent_{agent_id}")
            socketio.emit('agent_assigned', {'agent_name': agent['name']}, room=chat_id)
        elif status == 'queued':
            socketio.emit('dashboard_update', {'msg': 'New Chat in Queue'}, room=f"project_{project_id}")

    except Exception as e:
        print(f"[CRITICAL ERROR] create_chat failed: {e}")
        traceback.print_exc()
        emit('chat_error', {'msg': 'Server Error'})
    finally:
        db.close()

# [NEW] Handle when User clicks "Start Over" (ends the chat on server)
@socketio.on('client_end_chat')
def handle_client_end_chat(data):
    chat_id = data.get('chat_id')
    db = get_socket_db()
    if not db: return

    try:
        # 1. Get Chat Info
        chat = db.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        
        if chat and chat['status'] != 'closed':
            # 2. Update status to closed
            db.execute("UPDATE chats SET status = 'closed' WHERE id = ?", (chat_id,))
            db.commit()
            
            # 3. Notify assigned agent to update their dashboard
            if chat['assigned_agent_id']:
                socketio.emit('dashboard_update', {'msg': 'User ended chat'}, room=f"agent_{chat['assigned_agent_id']}")
                # Also notify the specific chat room
                socketio.emit('chat_closed', {'msg': 'User ended the session.'}, room=chat_id)
                
            print(f"[SOCKET] Chat {chat_id} ended by client.")
            
    except Exception as e:
        print(f"Error ending chat: {e}")
    finally:
        db.close()

@socketio.on('agent_claim_chat')
def handle_agent_claim(data):
    chat_id = data.get('chat_id')
    agent_id = data.get('agent_id')
    
    db = get_socket_db()
    if not db: return

    try:
        chat = db.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        if chat and chat['status'] == 'queued':
            agent = db.execute("SELECT name, project_id FROM users WHERE id = ?", (agent_id,)).fetchone()
            
            db.execute("UPDATE chats SET status = 'assigned', assigned_agent_id = ? WHERE id = ?", (agent_id, chat_id))
            db.commit()
            
            if agent and agent['project_id']:
                socketio.emit('dashboard_update', {'msg': 'Chat Claimed'}, room=f"project_{agent['project_id']}")
            
            socketio.emit('agent_assigned', {'agent_name': agent['name']}, room=chat_id)
            emit('claim_success', {'chat_id': chat_id}, room=request.sid)

    except Exception as e:
        print(f"Error claiming chat: {e}")
        traceback.print_exc()
    finally:
        db.close()

@socketio.on('client_message')
def handle_client_message(data):
    handle_message(data, 'customer')

@socketio.on('agent_message')
def handle_agent_message(data):
    handle_message(data, 'agent')

def handle_message(data, sender_type):
    chat_id = data.get('chat_id')
    message = data.get('message')
    sender_name = data.get('sender_name')
    
    if not message: return 

    db = get_socket_db()
    if not db: return

    try:
        db.execute("INSERT INTO messages (chat_id, sender_type, sender_name, message) VALUES (?, ?, ?, ?)", 
                (chat_id, sender_type, sender_name, message))
        db.commit()
        socketio.emit('new_message', {'sender_type': sender_type, 'sender_name': sender_name, 'message': message}, room=chat_id)
    except Exception as e:
        print(f"Message Error: {e}")
    finally:
        db.close()

@socketio.on('register_agent_socket')
def register_agent(data):
    agent_id = data.get('agent_id')
    if agent_id:
        try:
            agent_id = int(agent_id)
            join_room(f"agent_{agent_id}")
            
            db = get_socket_db()
            if db:
                user = db.execute("SELECT project_id FROM users WHERE id = ?", (agent_id,)).fetchone()
                if user and user['project_id']:
                    join_room(f"project_{user['project_id']}")
                db.close()
        except Exception as e:
            print(f"Agent Reg Error: {e}")

# --- ENTRY POINT ---
if __name__ == '__main__':
    init_db()
    # [FIX] Do not force debug=True in production. 
    debug_mode = os.environ.get('FLASK_DEBUG', 'False') == 'True'
    print(f"Starting CMR Dashboard on http://localhost:5000 (PID: {os.getpid()})")
    socketio.run(app, debug=debug_mode, port=5000)