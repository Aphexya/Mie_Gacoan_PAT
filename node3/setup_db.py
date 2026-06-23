import sqlite3
import sys

def setup_db(node_id="Node1"):
    conn = sqlite3.connect('gacoan_inventory.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Tabel User
    cursor.execute('''CREATE TABLE IF NOT EXISTS user (
        id_user     INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT UNIQUE,
        password    TEXT,
        asal_node   TEXT
    )''')

    # 2. Tabel Bahan Baku
    cursor.execute('''CREATE TABLE IF NOT EXISTS bahan_baku (
        id_bahan    INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_bahan  TEXT UNIQUE,
        satuan      TEXT,
        stok        INTEGER DEFAULT 100
    )''')

    # 3. Tabel Transaksi Header
    cursor.execute('''CREATE TABLE IF NOT EXISTS transaksi_header (
        asal_node       TEXT,
        id_lokal        INTEGER,
        id_user         INTEGER,
        tipe_transaksi  TEXT CHECK(tipe_transaksi IN ('IN','OUT','KASIR','REQ_PUSAT')),
        tanggal         DATETIME DEFAULT CURRENT_TIMESTAMP,
        sync_status      TEXT DEFAULT 'pending'
                        CHECK(sync_status IN ('pending','synced','failed')),
        synced_at       DATETIME,
        conflict_flag   INTEGER DEFAULT 0,
        PRIMARY KEY (asal_node, id_lokal),
        FOREIGN KEY (id_user) REFERENCES user(id_user)
    )''')

    # 4. Tabel Transaksi Detail
    cursor.execute('''CREATE TABLE IF NOT EXISTS transaksi_detail (
        id_detail   INTEGER PRIMARY KEY AUTOINCREMENT,
        asal_node   TEXT,
        id_lokal    INTEGER,
        id_bahan    INTEGER,
        jumlah      INTEGER, -- Diubah ke INTEGER agar tidak koma
        FOREIGN KEY (asal_node, id_lokal)
            REFERENCES transaksi_header(asal_node, id_lokal),
        FOREIGN KEY (id_bahan) REFERENCES bahan_baku(id_bahan)
    )''')

    # 5. Tabel Sync Queue
    cursor.execute('''CREATE TABLE IF NOT EXISTS sync_queue (
        id_queue     INTEGER PRIMARY KEY AUTOINCREMENT,
        asal_node    TEXT,
        id_lokal     INTEGER,
        payload      TEXT,
        created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
        attempts     INTEGER DEFAULT 0,
        status       TEXT DEFAULT 'pending'
                     CHECK(status IN ('pending','synced','failed')),
        last_attempt DATETIME
    )''')

    # 6. Tabel Menu
    cursor.execute('''CREATE TABLE IF NOT EXISTS menu (
        id_menu     INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_menu   TEXT UNIQUE,
        harga       INTEGER DEFAULT 0,
        aktif       INTEGER DEFAULT 1
    )''')

    # 7. Tabel Resep
    cursor.execute('''CREATE TABLE IF NOT EXISTS resep (
        id_resep    INTEGER PRIMARY KEY AUTOINCREMENT,
        id_menu     INTEGER,
        id_bahan    INTEGER,
        jumlah      INTEGER, -- Diubah ke INTEGER (Buat porsi angka bulat)
        FOREIGN KEY (id_menu)  REFERENCES menu(id_menu),
        FOREIGN KEY (id_bahan) REFERENCES bahan_baku(id_bahan)
    )''')

    # ── DATA MASTER BAHAN BAKU ────────────────────────────────
    # Stok awal saya naikkan sedikit karena sekarang pemakaiannya boros (1kg per porsi)
    bahan_list = [
        ('Mie Basah',       'Kg',   500),
        ('Mie Keriting',    'Kg',   500),
        ('Ayam Cincang',    'Kg',   500),
        ('Sambal Rawit',    'Kg',   500),
        ('Minyak Bawang',   'Liter', 500),
        ('Pangsit Goreng',  'Pcs',  1000),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO bahan_baku (nama_bahan, satuan, stok) VALUES (?,?,?)",
        bahan_list
    )

    # ── DATA MENU ────────────────────
    menus = [
        ('Mie Gacoan',  15000),
        ('Mie Hompimpa', 15000),
        ('Mie Suit',     13000),
    ]
    cursor.executemany("INSERT OR IGNORE INTO menu (nama_menu, harga) VALUES (?,?)", menus)

    # ── DATA USERS ────────────────────
    users = [
        ('admin_pusat',    '123', 'Node1'),
        ('admin_cabang_a', '123', 'Node2'),
        ('admin_cabang_b', '123', 'Node3'),
    ]
    cursor.executemany("INSERT OR IGNORE INTO user (username, password, asal_node) VALUES (?,?,?)", users)

    conn.commit()
    conn.close()
    print(f"✅ Database [{node_id}] Berhasil Dibuat dengan Resep Angka Bulat!")

if __name__ == '__main__':
    node = sys.argv[1] if len(sys.argv) > 1 else "Node1"
    setup_db(node)