from flask import request, jsonify, session, redirect, url_for
import json
import requests
from datetime import datetime

def init_api_cabang_routes(app, get_db, render, login_required, jalankan_sync, next_id_lokal, _get_riwayat, _redirect_transaksi, NODE_ID, SERVER_URL):

    @app.route('/transaksi', methods=['POST'])
    def transaksi():
        if not session.get('logged_in'):
            return redirect(url_for('index'))

        # Ambil tipe dari form (IN atau OUT)
        tipe = request.form.get('tipe', 'OUT') 
        id_bahan_list = request.form.getlist('id_bahan[]')
        jumlah_list   = request.form.getlist('jumlah[]')

        if not id_bahan_list:
            return _redirect_transaksi("Tidak ada bahan dipilih.", False)

        conn = get_db()
        cursor = conn.cursor()

        # Validasi semua item dulu sebelum simpan
        items = []
        for ib, jm in zip(id_bahan_list, jumlah_list):
            try:
                ib = int(ib); jm = int(jm)
            except:
                conn.close()
                return _redirect_transaksi("Input tidak valid.", False)

            cursor.execute("SELECT nama_bahan, stok FROM bahan_baku WHERE id_bahan=?", (ib,))
            bahan = cursor.fetchone()
            if not bahan:
                conn.close()
                return _redirect_transaksi(f"Bahan ID {ib} tidak ditemukan.", False)

            if tipe == 'OUT' and jm > bahan['stok']:
                conn.close()
                return _redirect_transaksi(
                    f"❌ Stok '{bahan['nama_bahan']}' tidak cukup! "
                    f"Tersedia: {bahan['stok']}, diminta: {jm}.", False
                )
            items.append({'id_bahan': ib, 'jumlah': jm, 'nama': bahan['nama_bahan']})

        # Simpan transaksi OUT saja (penjualan di cabang)
        id_lokal = next_id_lokal()
        tanggal  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        id_user  = session['id_user']

        # Simpan transaksi sesuai tipe yang dipilih (IN atau OUT)
        cursor.execute('''
            INSERT INTO transaksi_header
                (asal_node, id_lokal, id_user, tipe_transaksi, tanggal, sync_status)
            VALUES (?,?,?,?,?,?)
        ''', (NODE_ID, id_lokal, id_user, tipe, tanggal, 'pending')) # Menggunakan variabel 'tipe'

        for item in items:
            cursor.execute('''
                INSERT INTO transaksi_detail (asal_node, id_lokal, id_bahan, jumlah)
                VALUES (?,?,?,?)
            ''', (NODE_ID, id_lokal, item['id_bahan'], item['jumlah']))

            # Logika stok lokal: IN menambah, OUT mengurangi
            if tipe == 'IN':
                cursor.execute("UPDATE bahan_baku SET stok = stok + ? WHERE id_bahan=?", (item['jumlah'], item['id_bahan']))
            else:
                cursor.execute("UPDATE bahan_baku SET stok = stok - ? WHERE id_bahan=?", (item['jumlah'], item['id_bahan']))

        # 💡 LOGIKA BARU: Tetap pakai status 'pending' agar lolos CHECK constraint database
        if tipe == 'IN':
            payload = json.dumps({
                "node_id": NODE_ID,
                "id_bahan": items[0]['id_bahan'], 
                "jumlah": items[0]['jumlah'],
                "id_lokal_cabang": id_lokal,
                "tipe_transaksi": "REQ_PUSAT"  # 👈 Tanda khusus diselipkan di dalam payload
            })
            cursor.execute('''
                INSERT INTO sync_queue (asal_node, id_lokal, payload, status)
                VALUES (?,?,?,?)
            ''', (NODE_ID, id_lokal, payload, 'pending')) # 👈 Diubah kembali jadi 'pending'
            
            cursor.execute('''
                UPDATE transaksi_header 
                SET tipe_transaksi='REQ_PUSAT', sync_status='pending', synced_at='OFFLINE'
                WHERE asal_node=? AND id_lokal=?
            ''', (NODE_ID, id_lokal))
        else:
            # Jika memilih KELUAR (Pemakaian/Kasir), biarkan pakai logika lamamu (Langsung Sync)
            payload = json.dumps({
                "asal_node":      NODE_ID,
                "id_lokal":       id_lokal,
                "id_user":        id_user,
                "tipe_transaksi": tipe,
                "tanggal":        tanggal,
                "detail":         [{"id_bahan": i['id_bahan'], "jumlah": i['jumlah']} for i in items]
            })
            cursor.execute('''
                INSERT INTO sync_queue (asal_node, id_lokal, payload, status)
                VALUES (?,?,?,?)
            ''', (NODE_ID, id_lokal, payload, 'pending'))

        conn.commit()
        conn.close()

        nama_list = ", ".join(i['nama'] for i in items)
        return _redirect_transaksi(
            f"✅ Penjualan [{NODE_ID}-#{id_lokal}] tersimpan! "
            f"Bahan: {nama_list}. Status: PENDING sync.", True
        )
    

    @app.route('/do_sync', methods=['POST'])
    def do_sync():
        if not session.get('logged_in'):
            return redirect(url_for('index'))

        berhasil, gagal, pesan = jalankan_sync()
        msg = f"Sync selesai: {berhasil} berhasil, {gagal} gagal. {pesan}"

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id_bahan, nama_bahan, satuan, stok FROM bahan_baku")
        stok = [dict(r) for r in cursor.fetchall()]
        riwayat = _get_riwayat(cursor)
        conn.close()

        return render('cabang.html', stok=stok, riwayat=riwayat,
                    sync_msg=msg, active_tab='riwayat')

    @app.route('/minta_bahan', methods=['POST'])
    @login_required
    def route_minta_bahan():
        id_b = request.form.get('id_bahan')
        qty = int(request.form.get('jumlah'))
        
        conn = get_db(); c = conn.cursor()
        id_l = c.execute("SELECT COALESCE(MAX(id_lokal),0)+1 FROM transaksi_header WHERE asal_node=?", (NODE_ID,)).fetchone()[0]
        now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Coba kirim langsung ke pusat dulu
            res = requests.post(f"{SERVER_URL}/api/ajukan_minta", 
                                json={"node_id": NODE_ID, "id_bahan": id_b, "jumlah": qty}, 
                                timeout=4)
            
            if res.status_code == 200:
                id_nota_pusat = res.json().get('id_nota_pusat')
                # ONLINE: Catat lokal dengan referensi ID pusat di kolom synced_at
                c.execute("INSERT INTO transaksi_header (asal_node, id_lokal, id_user, tipe_transaksi, sync_status, tanggal, synced_at) VALUES (?,?,?,?,?,?,?)",
                        (NODE_ID, id_l, session['id_user'], 'REQ_PUSAT', 'pending', now_time, id_nota_pusat))
                session['flash'] = "Permintaan diajukan secara Online! Menunggu ACC dari Pusat."; session['flash_ok'] = True
            else:
                session['flash'] = f"Gagal: {res.json().get('pesan')}"; session['flash_ok'] = False
                conn.close(); return redirect(url_for('index'))
                
        except Exception as e:
            # 🔴 OFFLINE HANDLING: Server mati? Tetap catat di database lokal cabang!
            # Karena offline dan belum punya ID pusat, kita taruh nilai 'OFFLINE' sementara di synced_at
            c.execute("INSERT INTO transaksi_header (asal_node, id_lokal, id_user, tipe_transaksi, sync_status, tanggal, synced_at) VALUES (?,?,?,?,?,?,?)",
                    (NODE_ID, id_l, session['id_user'], 'REQ_PUSAT', 'pending', now_time, 'OFFLINE'))
            
            # Masukkan data ini ke sync_queue agar dikirim otomatis ke /api/ajukan_minta saat pusat online
            payload = json.dumps({"node_id": NODE_ID, "id_bahan": id_b, "jumlah": qty, "id_lokal_cabang": id_l})
            c.execute("INSERT INTO sync_queue (asal_node, id_lokal, payload, status) VALUES (?,?,?,?)", 
                      (NODE_ID, id_l, payload, 'pending_request'))
            
            session['flash'] = "Server Pusat Offline! Pengajuan disimpan lokal & akan dikirim otomatis saat online."; session['flash_ok'] = True
            
        c.execute("INSERT INTO transaksi_detail (asal_node, id_lokal, id_bahan, jumlah) VALUES (?,?,?,?)", (NODE_ID, id_l, id_b, qty))
        conn.commit(); conn.close()
        return redirect(url_for('index'))

    @app.route('/api/proxy_stok_pusat')
    def proxy_stok_pusat():
        try:
            r = requests.get(f"{SERVER_URL}/api/bahan_pusat", timeout=3)
            return jsonify(r.json()), r.status_code
        except:
            return jsonify([]), 500
        
    @app.route('/sync_master', methods=['POST'])
    def sync_master():
        try:
            # Ambil data terbaru dari API pusat
            res = requests.get(f"{SERVER_URL}/api/bahan_pusat", timeout=5)
            if res.status_code == 200:
                bahan_pusat = res.json()
                conn = get_db(); c = conn.cursor()
                for b in bahan_pusat:
                    # Masukkan jika belum ada, abaikan jika sudah ada
                    c.execute("INSERT OR IGNORE INTO bahan_baku (id_bahan, nama_bahan, satuan, stok) VALUES (?,?,?,?)",
                            (b['id_bahan'], b['nama_bahan'], b['satuan'], 0))
                conn.commit(); conn.close()
                session['flash'] = "Daftar Bahan Berhasil Diperbarui!"; return redirect('/')
        except:
            session['flash'] = "Gagal terhubung ke Server!"; return redirect('/')

    @app.route('/kasir', methods=['POST'])
    @login_required
    def kasir():
        id_menu = request.form.get('id_menu')
        jumlah = int(request.form.get('jumlah', 1))
        
        conn = get_db(); c = conn.cursor()
        # Ambil data menu
        c.execute("SELECT nama_menu, harga FROM menu WHERE id_menu=?", (id_menu,))
        menu = c.fetchone()
        
        # Ambil resep (PENTING: Pastikan data resep sudah ada di DB)
        c.execute('''SELECT r.id_bahan, b.nama_bahan, b.stok, r.jumlah as per_porsi
                    FROM resep r JOIN bahan_baku b ON r.id_bahan = b.id_bahan
                    WHERE r.id_menu = ?''', (id_menu,))
        resep = c.fetchall()

        if not resep:
            conn.close()
            session['flash'] = "Gagal: Resep menu ini belum diatur di database!"; return redirect('/')

        # Cek Stok
        for r in resep:
            if r['stok'] < (r['per_porsi'] * jumlah):
                conn.close()
                session['flash'] = f"Stok {r['nama_bahan']} tidak cukup!"; return redirect('/')

        id_l = next_id_lokal()
        tgl = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Simpan Transaksi KASIR
        c.execute("INSERT INTO transaksi_header (asal_node, id_lokal, id_user, tipe_transaksi, tanggal) VALUES (?,?,?,?,?)",
                (NODE_ID, id_l, session['id_user'], 'KASIR', tgl))
        
        detail_payload = []
        for r in resep:
            qty_pakai = r['per_porsi'] * jumlah
            c.execute("INSERT INTO transaksi_detail (asal_node, id_lokal, id_bahan, jumlah) VALUES (?,?,?,?)",
                    (NODE_ID, id_l, r['id_bahan'], qty_pakai))
            # Update Stok (PENTING: Gunakan COMMIT setelah ini)
            c.execute("UPDATE bahan_baku SET stok = stok - ? WHERE id_bahan=?", (qty_pakai, r['id_bahan']))
            detail_payload.append({"id_bahan": r['id_bahan'], "jumlah": qty_pakai})

        # Antrean Sinkronisasi 
        payload = json.dumps({
            "asal_node": NODE_ID, 
            "id_lokal": id_l, 
            "id_user": session['id_user'], 
            "tipe_transaksi": "KASIR", 
            "tanggal": tgl, 
            "detail": detail_payload
        })
        
        # Di sini kita tambahkan kolom 'status' dan nilai 'pending'
        c.execute('''
            INSERT INTO sync_queue (asal_node, id_lokal, payload, status) 
            VALUES (?,?,?,?)
        ''', (NODE_ID, id_l, payload, 'pending'))
        
        conn.commit(); conn.close()
        session['flash'] = f"Berhasil Jual {jumlah} {menu['nama_menu']}!"; return redirect('/')
