from flask import request, session, redirect, url_for

def init_web_cabang_routes(app, get_db, render, NODE_ID, _get_riwayat):
    @app.route('/')
    def index():
        if not session.get('logged_in'):
            return render('cabang.html')

        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Ambil data Stok Lokal
        cursor.execute("SELECT id_bahan, nama_bahan, satuan, stok FROM bahan_baku")
        stok = [dict(r) for r in cursor.fetchall()]
        
        # 2. Ambil data Menu (PENTING: Agar dropdown kasir terisi)
        cursor.execute("SELECT id_menu, nama_menu, harga FROM menu WHERE aktif=1")
        menus = [dict(r) for r in cursor.fetchall()]
        
        # 3. Ambil data Riwayat
        riwayat = _get_riwayat(cursor)
        
        conn.close()

        # Pastikan menus_lokal dikirim ke template
        return render('cabang.html', 
                    stok=stok, 
                    menus_lokal=menus, 
                    riwayat=riwayat, 
                    active_tab='stok')

    @app.route('/login', methods=['POST'])
    def login():
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM user WHERE username=? AND password=? AND asal_node=?",
            (username, password, NODE_ID)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session['logged_in'] = True
            session['username']  = username
            session['id_user']   = user['id_user']
            return redirect(url_for('index'))

        return render('cabang.html', error='Username/password salah atau bukan node ini.')


    @app.route('/logout', methods=['POST'])
    def logout():
        session.clear()
        return redirect(url_for('index'))

    @app.route('/riwayat')
    def riwayat():
        if not session.get('logged_in'):
            return redirect(url_for('index'))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id_bahan, nama_bahan, satuan, stok FROM bahan_baku")
        stok = [dict(r) for r in cursor.fetchall()]
        riwayat = _get_riwayat(cursor)
        conn.close()

        return render('cabang.html', stok=stok, riwayat=riwayat, active_tab='riwayat')
