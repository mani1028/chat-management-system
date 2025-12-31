(function() {
    // 1. Get Project ID and Backend URL reliably
    const myScript = document.currentScript || (function() {
        const scripts = document.getElementsByTagName('script');
        return scripts[scripts.length - 1];
    })();
    
    // [CRITICAL FIX] Dynamically determine the Backend URL
    const scriptUrl = new URL(myScript.src);
    const BACKEND_URL = scriptUrl.origin; 
    
    const queryString = myScript.src.split('?')[1];
    const urlParams = new URLSearchParams(queryString);
    const projectId = urlParams.get('project_id');

    if (!projectId) {
        console.error("CMR Widget Error: project_id is missing.");
        return;
    }

    // Inject Styles
    const style = document.createElement('style');
    style.innerHTML = `
        #cmr-widget-container { position: fixed; bottom: 20px; right: 20px; z-index: 9999; font-family: sans-serif; }
        #cmr-widget-button { background: #007bff; color: white; border: none; padding: 15px; border-radius: 50%; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width:60px; height:60px; font-size:24px; display:flex; align-items:center; justify-content:center; transition: transform 0.2s; }
        #cmr-widget-button:hover { transform: scale(1.1); }
        #cmr-chat-box { display: none; width: 350px; height: 450px; background: white; border: 1px solid #ccc; border-radius: 10px; flex-direction: column; box-shadow: 0 4px 12px rgba(0,0,0,0.2); overflow: hidden; margin-bottom: 10px; }
        #cmr-header { background: #007bff; color: white; padding: 15px; display: flex; justify-content: space-between; align-items: center; font-weight:bold; }
        #cmr-header-controls { display: flex; align-items: center; gap: 10px; }
        #cmr-reset-btn { font-size: 11px; background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 4px; cursor: pointer; display: none; font-weight: normal; }
        #cmr-reset-btn:hover { background: rgba(255,255,255,0.3); }
        #cmr-messages { flex: 1; padding: 15px; overflow-y: auto; background: #f9f9f9; display:flex; flex-direction:column; gap:8px; }
        #cmr-input-area { padding: 10px; border-top: 1px solid #eee; display: flex; background:white; }
        #cmr-input { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 20px; outline:none; }
        #cmr-input:disabled { background: #eee; cursor: not-allowed; }
        #cmr-send { margin-left: 5px; background: #007bff; color: white; border: none; padding: 8px 15px; border-radius: 20px; cursor: pointer; }
        #cmr-send:disabled { background: #ccc; cursor: not-allowed; }
        
        .cmr-msg { padding: 8px 12px; border-radius: 10px; max-width: 80%; font-size: 14px; line-height:1.4; }
        .cmr-msg-customer { background: #007bff; color: white; align-self: flex-end; border-bottom-right-radius: 2px; }
        .cmr-msg-agent { background: #e9ecef; color: #333; align-self: flex-start; border-bottom-left-radius: 2px; }
        .cmr-sys-msg { font-size:12px; color:#888; text-align:center; margin:10px 0; font-style:italic; }
        
        #cmr-start-form { padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        #cmr-start-form input { padding: 12px; border: 1px solid #ddd; border-radius: 4px; }
        #cmr-start-btn { background: #007bff; color: white; border: none; padding: 12px; border-radius: 4px; cursor: pointer; font-weight:bold; }
        #cmr-start-btn:disabled { background: #ccc; cursor: not-allowed; }
    `;
    document.head.appendChild(style);

    // Create UI
    const container = document.createElement('div');
    container.id = 'cmr-widget-container';
    container.innerHTML = `
        <div id="cmr-chat-box">
            <div id="cmr-header">
                <div id="cmr-header-controls">
                    <span>Chat Support</span>
                    <span id="cmr-reset-btn" title="Start a new chat">Start Over</span>
                </div>
                <span style="cursor:pointer; font-size:24px; line-height:20px;" id="cmr-close-btn">&times;</span>
            </div>
            <div id="cmr-start-form">
                <div style="text-align:center; margin-bottom:10px;">
                    <h3>Welcome!</h3>
                    <p style="color:#666; font-size:14px;">Please fill in your details to start chatting.</p>
                </div>
                <input type="text" id="cmr-name" placeholder="Your Name" required>
                <input type="email" id="cmr-email" placeholder="Your Email" required>
                <input type="text" id="cmr-initial-msg" placeholder="How can we help?" required>
                <button id="cmr-start-btn">Start Chat</button>
            </div>
            <div id="cmr-messages" style="display:none;"></div>
            <div id="cmr-input-area" style="display:none;">
                <input type="text" id="cmr-input" placeholder="Type a message...">
                <button id="cmr-send">Send</button>
            </div>
        </div>
        <button id="cmr-widget-button">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        </button>
    `;
    document.body.appendChild(container);

    // Socket Logic
    let socket;
    let chatId = localStorage.getItem(`cmr_chat_${projectId}`);
    let customerName = localStorage.getItem(`cmr_name_${projectId}`);

    // Load Socket.io script
    const script = document.createElement('script');
    script.src = "https://cdn.socket.io/4.0.0/socket.io.min.js";
    script.onload = initSocket;
    document.head.appendChild(script);

    function initSocket() {
        console.log("SocketIO Script Loaded. Initializing connection to:", BACKEND_URL);
        
        socket = io(BACKEND_URL, {
            transports: ['polling', 'websocket'] 
        });

        document.getElementById('cmr-widget-button').onclick = () => {
            const box = document.getElementById('cmr-chat-box');
            box.style.display = box.style.display === 'none' ? 'flex' : 'none';
        };
        
        document.getElementById('cmr-close-btn').onclick = () => {
            document.getElementById('cmr-chat-box').style.display = 'none';
        };

        // NEW: Manual Reset
        document.getElementById('cmr-reset-btn').onclick = resetChatSession;

        document.getElementById('cmr-start-btn').onclick = startChat;
        document.getElementById('cmr-send').onclick = sendMessage;
        
        document.getElementById('cmr-input').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') sendMessage();
        });

        socket.on('connect', () => {
            console.log("✅ CMR Widget Connected! Socket ID:", socket.id);
            if (chatId) {
                console.log("Rejoining previous chat session:", chatId);
                socket.emit('join_chat', { chat_id: chatId });
                showChatInterface();
            }
        });

        socket.on('connect_error', (err) => {
            console.error("❌ Socket Connection Error:", err);
        });

        socket.on('chat_created', (data) => {
            console.log("Chat created successfully:", data);
            
            // Reset Button State
            const btn = document.getElementById('cmr-start-btn');
            btn.innerText = "Start Chat";
            btn.disabled = false;

            chatId = data.chat_id;
            localStorage.setItem(`cmr_chat_${projectId}`, chatId);
            showChatInterface();
            
            if(data.status === 'queued') {
                appendSystemMessage("Searching for an agent... You are in the queue.");
            } else {
                appendSystemMessage("An agent has joined the chat.");
            }
        });
        
        // [NEW] Handle Loading History
        socket.on('chat_history', (data) => {
            console.log("Loading history...", data.history);
            // Clear current messages to avoid duplicates
            document.getElementById('cmr-messages').innerHTML = '';
            
            data.history.forEach(msg => {
                appendMessage(msg.message, msg.sender_type);
            });
        });
        
        socket.on('chat_error', (data) => {
            console.error("Chat Error Event:", data);
            alert("Error: " + data.msg);
            
            const btn = document.getElementById('cmr-start-btn');
            btn.innerText = "Start Chat";
            btn.disabled = false;
        });

        socket.on('new_message', (data) => {
            appendMessage(data.message, data.sender_type);
        });

        socket.on('agent_assigned', (data) => {
            appendSystemMessage(`<strong>${data.agent_name}</strong> has joined the chat.`);
        });

        socket.on('chat_closed', (data) => {
            appendSystemMessage("<strong>Chat ended.</strong> " + (data.msg || ""));
            
            // Cleanup session
            localStorage.removeItem(`cmr_chat_${projectId}`);
            chatId = null;

            const input = document.getElementById('cmr-input');
            const sendBtn = document.getElementById('cmr-send');
            if (input) {
                input.disabled = true;
                input.placeholder = "Chat closed.";
            }
            if (sendBtn) sendBtn.disabled = true;

            const restartBtn = document.createElement('button');
            restartBtn.innerText = "Start New Chat";
            restartBtn.style.cssText = "margin: 15px auto; display: block; background: #28a745; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold;";
            restartBtn.onclick = resetChatSession;

            const container = document.getElementById('cmr-messages');
            container.appendChild(restartBtn);
            container.scrollTop = container.scrollHeight;
        });
    }

    // [UPDATED] Reset now notifies server to close the chat
    function resetChatSession() {
        console.log("Resetting chat session...");
        
        // 1. Tell Server to Close Chat for Agent
        if (chatId) {
             socket.emit('client_end_chat', { chat_id: chatId });
        }
        
        localStorage.removeItem(`cmr_chat_${projectId}`);
        chatId = null;
        
        const input = document.getElementById('cmr-input');
        const sendBtn = document.getElementById('cmr-send');
        if (input) {
            input.value = "";
            input.disabled = false;
            input.placeholder = "Type a message...";
        }
        if (sendBtn) sendBtn.disabled = false;
        
        document.getElementById('cmr-messages').innerHTML = '';
        document.getElementById('cmr-messages').style.display = 'none';
        document.getElementById('cmr-input-area').style.display = 'none';
        document.getElementById('cmr-start-form').style.display = 'flex';
        document.getElementById('cmr-reset-btn').style.display = 'none';
    }

    function startChat() {
        const name = document.getElementById('cmr-name').value;
        const email = document.getElementById('cmr-email').value;
        const msg = document.getElementById('cmr-initial-msg').value;

        if(!name || !msg) return alert("Please fill name and message");

        if (!socket || !socket.connected) {
             console.log("Socket not connected yet, attempting connect...");
             socket.connect();
        }

        const btn = document.getElementById('cmr-start-btn');
        btn.innerText = "Starting...";
        btn.disabled = true;

        setTimeout(() => {
            if(btn.disabled && btn.innerText === "Starting...") {
                btn.disabled = false;
                btn.innerText = "Start Chat";
                console.warn("Socket Timeout triggered in UI");
                alert("Connection Timeout: Please check if the server is running and try again.");
            }
        }, 15000);

        customerName = name;
        localStorage.setItem(`cmr_name_${projectId}`, name);

        console.log("Sending create_chat request...", { project_id: projectId, name, email });
        socket.emit('create_chat', { 
            project_id: projectId, 
            name, email, message: msg 
        });
    }

    function showChatInterface() {
        document.getElementById('cmr-start-form').style.display = 'none';
        document.getElementById('cmr-messages').style.display = 'flex';
        document.getElementById('cmr-input-area').style.display = 'flex';
        document.getElementById('cmr-reset-btn').style.display = 'block';
    }

    function sendMessage() {
        const input = document.getElementById('cmr-input');
        const msg = input.value;
        if(!msg) return;

        socket.emit('client_message', {
            chat_id: chatId,
            message: msg,
            sender_name: customerName
        });
        input.value = '';
    }

    function appendMessage(msg, type) {
        const div = document.createElement('div');
        div.className = `cmr-msg cmr-msg-${type}`;
        div.innerText = msg;
        const container = document.getElementById('cmr-messages');
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }

    function appendSystemMessage(msg) {
        const div = document.createElement('div');
        div.className = `cmr-sys-msg`;
        div.innerHTML = msg;
        const container = document.getElementById('cmr-messages');
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }
})();