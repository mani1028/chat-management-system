# **CMR Dashboard \- Real-Time Customer Support System**

**CMR Dashboard** is a lightweight, self-hosted customer support platform that enables businesses to embed a live chat widget on their websites and manage conversations through a centralized agent dashboard. Built with Flask, Socket.IO, and SQLite.

## **🚀 Features**

* **🔌 Easy Integration:** Drop a single \<script\> tag onto any website to enable live chat.  
* **⚡ Real-Time:** Instant messaging using WebSockets (Socket.IO).  
* **bust Agent Queue:** Automated queuing system distributes chats to available agents.  
* **📂 Multi-Project Support:** Manage multiple client websites from a single admin panel.  
* **📜 Chat History:** Persistent message history for both agents and customers.  
* **🔒 Role-Based Access:** Separate dashboards for Admins and Agents.

## **🛠️ Tech Stack**

* **Backend:** Python, Flask, Flask-SocketIO, Eventlet  
* **Database:** SQLite (file-based)  
* **Frontend:** HTML5, CSS3, Vanilla JavaScript (Widget)  
* **Server:** Gunicorn (Production WSGI)

## **📦 Installation & Setup**

### **Prerequisites**

* Python 3.8 or higher  
* pip (Python package manager)

### **1\. Clone the Repository**

git clone \[https://github.com/your-username/cmr-dashboard.git\](https://github.com/your-username/cmr-dashboard.git)  
cd cmr-dashboard

### **2\. Install Dependencies**

It is recommended to use a virtual environment.

python3 \-m venv venv  
source venv/bin/activate  \# On Windows use: venv\\Scripts\\activate  
pip install \-r requirements.txt

### **3\. Initialize the Database**

Run the application once to generate the cmr\_database.db file.

python app.py

*You should see "Database initialized at: ..." in the console.*

### **4\. Create an Admin Account**

1. Open your browser and go to http://localhost:5000/auth/register.  
2. Create your initial Admin account.  
3. Log in to access the Admin Dashboard.

## **💻 Usage Guide**

### **For Admins**

1. **Create a Project:** Go to the Admin Dashboard and create a new project (e.g., "Client Website A").  
2. **Create Agents:** Create agent accounts and assign them to the specific project.  
3. **Get Script:** Copy the integration code provided in the project list (e.g., ?project\_id=1).

### **For Clients (Integration)**

Add the following script to the \<body\> of the client's website:

\<script src="http://YOUR\_SERVER\_URL/static/chat-widget.js?project\_id=1"\>\</script\>

*Replace YOUR\_SERVER\_URL with your actual domain or IP, and project\_id with the ID from the admin panel.*

### **For Agents**

1. Log in at /auth/login.  
2. The dashboard shows "My Active Chats" and the "Queue".  
3. Click **Claim Now** on queued chats to start a conversation.

## **🚀 Production Deployment (VPS)**

Do not use python app.py in production. Use **Gunicorn**.

1. **Install Gunicorn:**  
   pip install gunicorn

2. **Run with Eventlet:**  
   gunicorn \--worker-class eventlet \-w 1 \--bind 0.0.0.0:5000 app:app

3. **Nginx (Recommended):** Set up Nginx as a reverse proxy to handle SSL and forward WebSocket traffic.

## **⚙️ Configuration**

* **Chat Limit:** You can manually set the maximum concurrent chats per agent in app.py:  
  MAX\_CHATS\_PER\_AGENT \= 5

* **Secret Key:** Set the SECRET\_KEY environment variable for security in production.

## **🤝 Contributing**

Contributions are welcome\! Please open an issue or submit a pull request.

## **📄 License**

This project is licensed under the MIT License.