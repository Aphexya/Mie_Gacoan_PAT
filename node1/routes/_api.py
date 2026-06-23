from flask import request, jsonify, session
import sqlite3
from datetime import datetime

def init_api_routes(app, get_db):
    
    @app.route('/api/bahan', methods=['GET'])
    def get_bahan():
        """GET semua bahan baku"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id_bahan, nama_bahan, satuan, stok FROM bahan_baku ORDER BY id_bahan")
        bahan = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify(bahan), 200

    @app.route('/api/bahan_pusat', methods=['GET'])
    def get_bahan_pusat():
        """GET stok bahan pusat (untuk ditampilkan di cabang)"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id_bahan, nama_bahan, satuan, stok FROM bahan_baku ORDER BY id_bahan")
        bahan = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify(bahan), 200

    @app.route('/api/bahan', methods=['POST'])
    def create_bahan():
        """POST create bahan baku baru"""
        if not session.get('logged_in'):
            return jsonify({"status": "error", "pesan": "Belum login"}), 401
        
        data = request.get_json()
        nama_bahan = data.get('nama_bahan', '').strip()
        satuan = data.get('satuan', '').strip()
        stok = int(data.get('stok', 0))
        
        if not nama_bahan or not satuan:
            return jsonify({"status": "error", "pesan": "Nama bahan dan satuan harus diisi"}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO bahan_baku (nama_bahan, satuan, stok) VALUES (?,?,?)",
                (nama_bahan, satuan, stok)
            )
            conn.commit()
            new_id = cursor.lastrowid
            conn.close()
            return jsonify({
                "status": "success",
                "pesan": "Bahan berhasil ditambahkan",
                "id_bahan": new_id
            }), 201
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({"status": "error", "pesan": "Nama bahan sudah ada"}), 409
        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({"status": "error", "pesan": str(e)}), 500

    @app.route('/api/bahan/<int:id_bahan>', methods=['PUT'])
    def update_bahan(id_bahan):
        """PUT update bahan baku"""
        if not session.get('logged_in'):
            return jsonify({"status": "error", "pesan": "Belum login"}), 401
        
        data = request.get_json()
        nama_bahan = data.get('nama_bahan', '').strip()
        satuan = data.get('satuan', '').strip()
        stok = int(data.get('stok', 0))
        
        if not nama_bahan or not satuan:
            return jsonify({"status": "error", "pesan": "Nama bahan dan satuan harus diisi"}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE bahan_baku SET nama_bahan=?, satuan=?, stok=? WHERE id_bahan=?",
                (nama_bahan, satuan, stok, id_bahan)
            )
            if cursor.rowcount == 0:
                conn.close()
                return jsonify({"status": "error", "pesan": "Bahan tidak ditemukan"}), 404
            conn.commit()
            conn.close()
            return jsonify({"status": "success", "pesan": "Bahan berhasil diupdate"}), 200
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({"status": "error", "pesan": "Nama bahan sudah ada"}), 409
        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({"status": "error", "pesan": str(e)}), 500

    @app.route('/api/bahan/<int:id_bahan>', methods=['DELETE'])
    def delete_bahan(id_bahan):
        """DELETE bahan baku"""
        if not session.get('logged_in'):
            return jsonify({"status": "error", "pesan": "Belum login"}), 401
        
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM transaksi_detail WHERE id_bahan=?", (id_bahan,))
            if cursor.fetchone()[0] > 0:
                conn.close()
                return jsonify({
                    "status": "error",
                    "pesan": "Bahan sedang digunakan di transaksi, tidak bisa dihapus"
                }), 409
            
            cursor.execute("DELETE FROM bahan_baku WHERE id_bahan=?", (id_bahan,))
            if cursor.rowcount == 0:
                conn.close()
                return jsonify({"status": "error", "pesan": "Bahan tidak ditemukan"}), 404
            conn.commit()
            conn.close()
            return jsonify({"status": "success", "pesan": "Bahan berhasil dihapus"}), 200
        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({"status": "error", "pesan": str(e)}), 500

    @app.route('/api/minta_bahan', methods=['POST'])
    def minta_bahan():
        data = request.get_json()
        conn = get_db(); c = conn.cursor()
        
        c.execute("SELECT nama_bahan, stok FROM bahan_baku WHERE id_bahan=?", (data['id_bahan'],))
        bahan = c.fetchone()
        
        if not bahan or bahan['stok'] < data['jumlah']:
            conn.close()
            return jsonify({"status": "failed", "pesan": "Stok Pusat Habis/Tidak Cukup"}), 400
        
        try:
            c.execute("UPDATE bahan_baku SET stok = stok - ? WHERE id_bahan=?", (data['jumlah'], data['id_bahan']))
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            id_l = c.execute("SELECT COALESCE(MAX(id_lokal),0)+1 FROM transaksi_header WHERE asal_node=?", (data['node_id'],)).fetchone()[0]
            
            c.execute("INSERT INTO transaksi_header (asal_node, id_lokal, id_user, tipe_transaksi, tanggal, sync_status) VALUES (?,?,?,?,?,?)",
                    (data['node_id'], id_l, 1, 'OUT', now, 'synced'))
            c.execute("INSERT INTO transaksi_detail (asal_node, id_lokal, id_bahan, jumlah) VALUES (?,?,?,?)",
                    (data['node_id'], id_l, data['id_bahan'], data['jumlah']))
            
            conn.commit()
            return jsonify({"status": "success", "pesan": "Bahan Disetujui & Dikirim"}), 200
        except Exception as e:
            conn.rollback()
            return jsonify({"status": "error", "pesan": str(e)}), 500
        finally:
            conn.close()

    @app.route('/api/ajukan_minta', methods=['POST'])
    def ajukan_minta():
        data = request.get_json()
        node_id = data.get('node_id')
        id_bahan = data.get('id_bahan')
        jumlah = data.get('jumlah')
        
        conn = get_db(); c = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Catat transaksi masuk ke pusat dengan status 'pending' (Belum memotong stok pusat)
            id_l = c.execute("SELECT COALESCE(MAX(id_lokal),0)+1 FROM transaksi_header WHERE asal_node=?", (node_id,)).fetchone()[0]
            
            c.execute('''INSERT INTO transaksi_header (asal_node, id_lokal, id_user, tipe_transaksi, tanggal, sync_status) 
                         VALUES (?,?,?,?,?,?)''',
                      (node_id, id_l, 1, 'REQ_PUSAT', now, 'pending'))
            
            c.execute("INSERT INTO transaksi_detail (asal_node, id_lokal, id_bahan, jumlah) VALUES (?,?,?,?)",
                      (node_id, id_l, id_bahan, jumlah))
            
            conn.commit()
            return jsonify({"status": "success", "pesan": "Pengajuan dicatat", "id_nota_pusat": id_l}), 200
        except Exception as e:
            conn.rollback()
            return jsonify({"status": "error", "pesan": str(e)}), 500
        finally:
            conn.close()

    @app.route('/api/acc_minta/<string:node_id>/<int:id_lokal>', methods=['POST'])
    def acc_minta(node_id, id_lokal):
        if not session.get('logged_in'):
            return jsonify({"status": "error", "pesan": "Belum login"}), 401
            
        conn = get_db(); c = conn.cursor()
        
        # Ambil detail bahan yang diminta
        c.execute("SELECT id_bahan, jumlah FROM transaksi_detail WHERE asal_node=? AND id_lokal=?", (node_id, id_lokal))
        detail = c.fetchone()
        
        if not detail:
            conn.close(); return jsonify({"status": "error", "pesan": "Data tidak ditemukan"}), 404
            
        # Cek ketersediaan stok di pusat
        c.execute("SELECT stok, nama_bahan FROM bahan_baku WHERE id_bahan=?", (detail['id_bahan'],))
        bahan_pusat = c.fetchone()
        
        if not bahan_pusat or bahan_pusat['stok'] < detail['jumlah']:
            conn.close(); return jsonify({"status": "error", "pesan": "Stok di Gudang Pusat tidak mencukupi!"}), 400
            
        try:
            # 1. Potong stok Gudang Pusat (Karena barang dikirim)
            c.execute("UPDATE bahan_baku SET stok = stok - ? WHERE id_bahan=?", (detail['jumlah'], detail['id_bahan']))
            
            # 2. Update status transaksi di pusat menjadi 'synced' (Berarti di-ACC) dan tipenya ganti jadi 'OUT' (Barang keluar dari pusat)
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute('''UPDATE transaksi_header 
                         SET sync_status='synced', tipe_transaksi='OUT', synced_at=? 
                         WHERE asal_node=? AND id_lokal=?''', (now, node_id, id_lokal))
            
            conn.commit()
            return jsonify({"status": "success", "pesan": "Permintaan berhasil disetujui & stok pusat dipotong."}), 200
        except Exception as e:
            conn.rollback()
            return jsonify({"status": "error", "pesan": str(e)}), 500
        finally:
            conn.close()

    @app.route('/api/tolak_minta/<string:node_id>/<int:id_lokal>', methods=['POST'])
    def tolak_minta(node_id, id_lokal):
        if not session.get('logged_in'):
            return jsonify({"status": "error", "pesan": "Belum login"}), 401
            
        conn = get_db(); c = conn.cursor()
        try:
            # Update status transaksi di pusat menjadi 'failed' (Berarti DITOLAK oleh admin)
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute('''UPDATE transaksi_header 
                         SET sync_status='failed', synced_at=? 
                         WHERE asal_node=? AND id_lokal=?''', (now, node_id, id_lokal))
            conn.commit()
            return jsonify({"status": "success", "pesan": "Permintaan berhasil ditolak."}), 200
        except Exception as e:
            conn.rollback()
            return jsonify({"status": "error", "pesan": str(e)}), 500
        finally:
            conn.close()

    @app.route('/api/cek_status_minta/<string:node_id>/<int:id_lokal>', methods=['GET'])
    def cek_status_minta(node_id, id_lokal):
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT sync_status FROM transaksi_header WHERE asal_node=? AND id_lokal=?", (node_id, id_lokal))
        res = c.fetchone()
        conn.close()
        
        if res:
            return jsonify({"status": "success", "sync_status": res['sync_status']}), 200
        return jsonify({"status": "error", "pesan": "Nota tidak ditemukan"}), 404

    @app.route('/ping', methods=['GET'])
    def ping():
        return jsonify({"status": "online", "server": "Node1-Pusat"}), 200

    @app.route('/sync', methods=['POST'])
    def terima_sync():
        data = request.get_json()
        if not data: return jsonify({"status": "error"}), 400

        asal_node = data.get('asal_node')
        id_lokal  = data.get('id_lokal')
        tipe_asal = data.get('tipe_transaksi')
        detail    = data.get('detail', [])
        
        tipe_server = 'OUT' if tipe_asal == 'IN' else tipe_asal 

        conn = get_db(); cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM transaksi_header WHERE asal_node=? AND id_lokal=?", (asal_node, id_lokal))
            if cursor.fetchone(): return jsonify({"status": "skip"}), 200

            cursor.execute('''INSERT INTO transaksi_header (asal_node, id_lokal, id_user, tipe_transaksi, tanggal, sync_status, synced_at)
                              VALUES (?,?,?,?,?,?,?)''', 
                           (asal_node, id_lokal, data.get('id_user'), tipe_server, data.get('tanggal'), 'synced', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            for item in detail:
                cursor.execute("INSERT INTO transaksi_detail (asal_node, id_lokal, id_bahan, jumlah) VALUES (?,?,?,?)",
                               (asal_node, id_lokal, item['id_bahan'], item['jumlah']))
                if tipe_server == 'OUT':
                    cursor.execute("UPDATE bahan_baku SET stok = stok - ? WHERE id_bahan=? AND stok >= ?",
                                   (item['jumlah'], item['id_bahan'], item['jumlah']))
            
            conn.commit(); return jsonify({"status": "success"}), 200
        except Exception as e:
            conn.rollback(); return jsonify({"status": "error", "pesan": str(e)}), 500
        finally: conn.close()