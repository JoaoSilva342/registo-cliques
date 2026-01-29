Aplicacao de Cliques (Click Tracker Application)
Overview
A Flask web application that tracks button clicks with a SQLite database backend. Users can click on 4 different buttons, and the application records each click with a timestamp and daily sequential number.

Project Structure
/
├── aplicacao.py          # Main Flask application
├── requirements.txt      # Python dependencies
├── static/
│   ├── estilo.css       # CSS styles
│   └── script.js        # Frontend JavaScript
├── templates/
│   └── pagina_inicial.html  # Main HTML template
└── cliques.db           # SQLite database (auto-created)
Tech Stack
Backend: Python 3.11 with Flask 3.0.3
Database: SQLite (file-based)
Frontend: HTML, CSS, JavaScript
Running the Application
The application runs on port 5000 with the command:

python aplicacao.py
API Endpoints
GET / - Main page with button interface
POST /clique - Register a button click (JSON body: {"botao": "Botão 1"})
GET /contagens_hoje - Get today's click counts per button
GET /hoje - Get last 20 clicks from today
Database Schema
The cliques table stores:

id - Auto-increment primary key
botao - Button name (Botão 1-4)
sequencial - Daily sequential number
data - Date (YYYY-MM-DD)
hora - Time (HH:MM)
