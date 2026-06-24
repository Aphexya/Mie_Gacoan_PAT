from flask import request, render_template, session, redirect, url_for
import json 

def init_web_routes(app, get_db):

    @app.route('/', methods=['GET'])
    def index():
        if not session.get('logged_in'):
            return render_template('server_dashboard.html')

        conn = get_db()
        cursor = conn.cursor()

        # Stats ringkas
        cursor.execute("SELECT COUNT(*) FROM transaksi_header")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM transaksi_header WHERE sync_status='synced'")
        synced = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM transaksi_header WHERE sync_status='pending'")
        pending = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM bahan_baku")
        bahan = cursor.fetchone()[0]
        stats = dict(total=total, synced=synced, pending=pending, bahan=bahan)

        # Stok gudang
        cursor.execute("SELECT id_bahan, nama_bahan, satuan, stok FROM bahan_baku")
        stok = [dict(r) for r in cursor.fetchall()]

        # Ringkasan per cabang
        cursor.execute('''
            SELECT asal_node,
                   COUNT(*) AS total,
                   SUM(CASE WHEN sync_status='synced'  THEN 1 ELSE 0 END) AS synced,
                   SUM(CASE WHEN sync_status='pending' THEN 1 ELSE 0 END) AS pending
            FROM transaksi_header GROUP BY asal_node
        ''')
        cabang_summary = [dict(r) for r in cursor.fetchall()]

        # UPDATE BARIS LOG 20 TERBARU
        cursor.execute('''
            SELECT h.asal_node, h.id_lokal, h.tipe_transaksi,
                   h.tanggal, h.sync_status, h.synced_at, u.username,
                   (SELECT GROUP_CONCAT(b.nama_bahan || ' (' || d.jumlah || ' ' || b.satuan || ')', ', ')
                    FROM transaksi_detail d
                    JOIN bahan_baku b ON d.id_bahan = b.id_bahan
                    WHERE d.asal_node = h.asal_node AND d.id_lokal = h.id_lokal) AS detail_request
            FROM transaksi_header h
            LEFT JOIN user u ON h.id_user = u.id_user
            ORDER BY h.tanggal DESC LIMIT 20
        ''')
        log = [dict(r) for r in cursor.fetchall()]

        # UPDATE BARIS SEMUA TRANSAKSI
        cursor.execute('''
            SELECT h.asal_node, h.id_lokal, h.tipe_transaksi,
                   h.tanggal, h.sync_status, h.synced_at, u.username,
                   (SELECT GROUP_CONCAT(b.nama_bahan || ' (' || d.jumlah || ' ' || b.satuan || ')', ', ')
                    FROM transaksi_detail d
                    JOIN bahan_baku b ON d.id_bahan = b.id_bahan
                    WHERE d.asal_node = h.asal_node AND d.id_lokal = h.id_lokal) AS detail_request
            FROM transaksi_header h
            LEFT JOIN user u ON h.id_user = u.id_user
            ORDER BY h.tanggal DESC
        ''')
        all_transaksi = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return render_template('server_dashboard.html',
            stats=stats, stok=stok, cabang_summary=cabang_summary,
            log=log, all_transaksi=all_transaksi)


    @app.route('/login', methods=['POST'])
    def login():
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM user WHERE username=? AND password=? AND asal_node='Node1'",
            (username, password)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session['logged_in'] = True
            session['username']  = username
            session['id_user']   = user['id_user']
            return redirect(url_for('index'))
        return render_template('server_dashboard.html', error='Username atau password salah!')


    @app.route('/logout', methods=['POST'])
    def logout():
        session.clear()
        return redirect(url_for('index'))