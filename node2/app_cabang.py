"""
app_cabang.py — Node 2 (Cabang A) atau Node 3 (Cabang B)

Cara pakai:
  Node 2 → python app_cabang.py          (default: Node2, port 5001)
  Node 3 → python app_cabang.py Node3    (Node3, port 5002)

Buka di browser:
  Node 2 → http://localhost:5001
  Node 3 → http://localhost:5002
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import requests
import json
import threading
import time
import webbrowser
from datetime import datetime
from functools import wraps
from flask import (Flask, jsonify, request, render_template,
                   session, redirect, url_for)

from routes._web_cabang import init_web_cabang_routes
from routes._api_cabang import init_api_cabang_routes

# ── Konfigurasi Node ─────────────────────────────────────────────────
# Cara pakai:
#   python app_cabang.py Node2   → Cabang A (admin_cabang_a)
#   python app_cabang.py Node3   → Cabang B (admin_cabang_b)
#   python app_cabang.py         → akan ditanya interaktif
if len(sys.argv) > 1 and sys.argv[1] in ("Node2", "Node3"):
    NODE_ID = sys.argv[1]
else:
    print("\n" + "="*50)
    print("  SISTEM INVENTARIS MIE GACOAN — CABANG")
    print("="*50)
    print("  Pilih node yang akan dijalankan:")
    print("  [2] Node2 — Cabang A  (login: admin_cabang_a / 123)")
    print("  [3] Node3 — Cabang B  (login: admin_cabang_b / 123)")
    while True:
        pilihan = input("\n  Masukkan pilihan (2 atau 3): ").strip()
        if pilihan == "2":
            NODE_ID = "Node2"; break
        elif pilihan == "3":
            NODE_ID = "Node3"; break
        else:
            print("  Masukkan angka 2 atau 3 saja.")

NODE_NAME  = "Cabang A" if NODE_ID == "Node2" else "Cabang B"
PORT       = 5001        if NODE_ID == "Node2" else 5002
SERVER_URL = "http://192.168.56.101:5000"
# SERVER_URL = "http://localhost:5000"
DB         = 'gacoan_inventory.db'
SYNC_EVERY = 15   # detik

app = Flask(__name__)
app.secret_key = f'gacoan_secret_{NODE_ID}'
app.config['SESSION_COOKIE_NAME'] = f'gacoan_session_{NODE_ID}'

# ── Custom Login Decorator ───────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ── Helper DB ────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def cek_server():
    try:
        r = requests.get(f"{SERVER_URL}/ping", timeout=3)
        return r.status_code == 200
    except:
        return False

def hitung_pending():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sync_queue WHERE status='pending'")
    n = cursor.fetchone()[0]
    conn.close()
    return n

def next_id_lokal():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(MAX(id_lokal),0)+1 FROM transaksi_header WHERE asal_node=?",
        (NODE_ID,)
    )
    n = cursor.fetchone()[0]
    conn.close()
    return n

# ── Proses Sinkronisasi ──────────────────────────────────────────────
# ── Proses Sinkronisasi ──────────────────────────────────────────────
def jalankan_sync():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Ambil semua antrean pending
    cursor.execute(
        "SELECT * FROM sync_queue WHERE status='pending' ORDER BY id_queue ASC"
    )
    antrian = cursor.fetchall()

    berhasil = gagal = 0
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for item in antrian:
        payload_data = json.loads(item['payload'])
        
        # JALUR A: Jika di dalam payload ada bendera REQ_PUSAT, jalankan sinkronisasi pengajuan offline
        if payload_data.get('tipe_transaksi') == 'REQ_PUSAT':
            if cek_server():
                try:
                    res = requests.post(f"{SERVER_URL}/api/ajukan_minta", json={"node_id": payload_data['node_id'], "id_bahan": payload_data['id_bahan'], "jumlah": payload_data['jumlah']}, timeout=4)
                    if res.status_code == 200:
                        id_nota_pusat = res.json().get('id_nota_pusat')
                        cursor.execute("UPDATE sync_queue SET status='synced', last_attempt=? WHERE id_queue=?", (now, item['id_queue']))
                        cursor.execute("UPDATE transaksi_header SET synced_at=? WHERE asal_node=? AND id_lokal=?", (id_nota_pusat, NODE_ID, payload_data['id_lokal_cabang']))
                        berhasil += 1
                except:
                    gagal += 1
            continue # Lanjut ke antrean berikutnya

        # JALUR B: Transaksi Kasir / Penjualan Biasa
        try:
            res = requests.post(f"{SERVER_URL}/sync", json=payload_data, timeout=5)
            resp = res.json()
            if res.status_code == 200 and resp.get('status') in ('success', 'skip'):
                cursor.execute("UPDATE sync_queue SET status='synced', last_attempt=? WHERE id_queue=?", (now, item['id_queue']))
                cursor.execute("UPDATE transaksi_header SET sync_status='synced', synced_at=? WHERE asal_node=? AND id_lokal=?", (now, item['asal_node'], item['id_lokal']))
                berhasil += 1
        except:
            gagal += 1
    
    # 2. Cek status approval dari Server Pusat (ACC atau TOLAK)
    cursor.execute("SELECT id_lokal, synced_at FROM transaksi_header WHERE tipe_transaksi='REQ_PUSAT' AND sync_status='pending'")
    req_pending = cursor.fetchall()
    
    if req_pending and cek_server():
        for r in req_pending:
            try:
                id_pusat_asli = r['synced_at']
                if id_pusat_asli != 'OFFLINE': # Hanya cek jika sudah punya ID dari pusat
                    res = requests.get(f"{SERVER_URL}/api/cek_status_minta/{NODE_ID}/{id_pusat_asli}", timeout=3)
                    if res.status_code == 200:
                        status_pusat = res.json().get('sync_status')
                        
                        cursor.execute("SELECT id_bahan, jumlah FROM transaksi_detail WHERE asal_node=? AND id_lokal=?", (NODE_ID, r['id_lokal']))
                        dt = cursor.fetchone()
                        
                        if dt and status_pusat == 'synced':
                            cursor.execute("UPDATE transaksi_header SET sync_status='synced', tipe_transaksi='IN', synced_at=? WHERE asal_node=? AND id_lokal=?", (now, NODE_ID, r['id_lokal']))
                            cursor.execute("UPDATE bahan_baku SET stok = stok + ? WHERE id_bahan=?", (dt['jumlah'], dt['id_bahan']))
                            berhasil += 1
                            
                        elif dt and status_pusat == 'failed':
                            cursor.execute("UPDATE transaksi_header SET sync_status='failed', synced_at=? WHERE asal_node=? AND id_lokal=?", (now, NODE_ID, r['id_lokal']))
                            berhasil += 1
            except Exception as e:
                print(f"Gagal verifikasi nota #{r['id_lokal']}:", str(e))

    conn.commit()
    conn.close()
    return berhasil, gagal, "Proses sinkronisasi dan pengecekan approval selesai."

# ── Background Auto-Sync ─────────────────────────────────────────────
def auto_sync_worker():
    while True:
        time.sleep(SYNC_EVERY)
        if hitung_pending() > 0 and cek_server():
            print(f"[Auto-Sync {NODE_ID}] Mengirim data pending ke server...")
            b, g, _ = jalankan_sync()
            print(f"[Auto-Sync {NODE_ID}] ✅{b} berhasil | ❌{g} gagal")


# ══════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════

def render(template, **kwargs):
    """Helper render + injeksi konteks global."""
    return render_template(
        template,
        node_id=NODE_ID,
        node_name=NODE_NAME,
        server_online=cek_server(),
        pending_count=hitung_pending(),
        current_time=datetime.now().strftime('%d %b %Y %H:%M'), **kwargs
    )













# ── Helpers ──────────────────────────────────────────────────────────
def _get_riwayat(cursor):
    cursor.execute('''
        SELECT h.asal_node, h.id_lokal, h.tipe_transaksi,
               h.tanggal, h.sync_status, h.synced_at,
               GROUP_CONCAT(b.nama_bahan, ', ') AS detail_bahan, 
               SUM(d.jumlah) AS total_jumlah
        FROM transaksi_header h
        LEFT JOIN transaksi_detail d ON h.asal_node=d.asal_node AND h.id_lokal=d.id_lokal
        LEFT JOIN bahan_baku b ON d.id_bahan=b.id_bahan
        WHERE h.asal_node=?
        GROUP BY h.id_lokal
        ORDER BY h.tanggal DESC LIMIT 50
    ''', (NODE_ID,))
    return [dict(r) for r in cursor.fetchall()]

def _redirect_transaksi(msg, ok):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_bahan, nama_bahan, satuan, stok FROM bahan_baku")
    stok = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render('cabang.html', stok=stok,
                  flash_msg=msg, flash_ok=ok, active_tab='transaksi')

init_web_cabang_routes(app, get_db, render, NODE_ID, _get_riwayat)
init_api_cabang_routes(app, get_db, render, login_required, jalankan_sync, next_id_lokal, _get_riwayat, _redirect_transaksi, NODE_ID, SERVER_URL)

# ══════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    # Start auto-sync background thread
    threading.Thread(target=auto_sync_worker, daemon=True).start()

    def open_browser():
        time.sleep(1.2)
        webbrowser.open(f'http://localhost:{PORT}')
    threading.Thread(target=open_browser, daemon=True).start()

    print("\n" + "═"*50)
    print(f"  🏪  Mie Gacoan — {NODE_NAME} ({NODE_ID})")
    print("═"*50)
    print(f"  🌐  Lokal   : http://localhost:{PORT}")
    print(f"  🌐  Jaringan: http://192.168.56.{101 + int(NODE_ID[-1]) - 1}:{PORT}")
    print(f"  📡  Server  : {SERVER_URL}")
    print(f"  🔁  Auto-sync setiap {SYNC_EVERY} detik jika ada pending")
    print("  ℹ️   Browser akan terbuka otomatis...")
    print("═"*50 + "\n")

    app.run(host='0.0.0.0', port=PORT, debug=False)