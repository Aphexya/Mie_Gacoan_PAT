"""
server_api.py — Node 1 (Server Pusat)
Jalankan: python server_api.py
Buka di browser: http://localhost:5000  atau  http://192.168.56.101:5000
"""

from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import sqlite3
import json
from datetime import datetime
import webbrowser
import threading
from routes._web import init_web_routes
from routes._api import init_api_routes

app = Flask(__name__)
app.secret_key = 'gacoan_secret_node1'
DB = 'gacoan_inventory.db'

# ── Helper DB ────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# Registrasi Rute dari file eksternal
init_web_routes(app, get_db)
init_api_routes(app, get_db)

# ══════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    def open_browser():
        import time; time.sleep(1.2)
        webbrowser.open('http://localhost:5000')

    threading.Thread(target=open_browser, daemon=True).start()
    print("\n" + "═"*50)
    print("  🍜  Mie Gacoan — Server Pusat (Node 1)")
    print("═"*50)
    print(f"  🌐  Lokal  : http://localhost:5000")
    print(f"  🌐  Jaringan: http://192.168.56.101:5000")
    print(f"  📡  API Sync: POST http://192.168.56.101:5000/sync")
    print("  ℹ️   Browser akan terbuka otomatis...")
    print("═"*50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False)