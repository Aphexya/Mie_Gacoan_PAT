# 🍜 Sistem Manajemen Inventaris & Kasir Terdistribusi — Mie Gacoan

Aplikasi manajemen inventaris dan kasir terdistribusi untuk mensimulasikan operasional **Gudang Pusat (Node 1)** dan **dua Cabang (Node 2 & Node 3)** pada restoran Mie Gacoan.

Sistem ini menerapkan arsitektur **Offline-First** — setiap cabang punya database lokal sendiri dan tetap bisa beroperasi penuh walau koneksi ke server pusat terputus. Data disinkronkan ke pusat saat koneksi kembali tersedia.

---

## 🚀 Fitur Utama

### 1. Multi-Node Offline-First
Setiap cabang punya database SQLite sendiri yang sepenuhnya mandiri. Transaksi kasir tetap bisa berjalan normal walau server pusat mati.

### 2. Queue-Based Auto Sync
Setiap transaksi masuk ke tabel `sync_queue` di DB lokal dulu. Background worker thread otomatis cek koneksi dan kirim data pending ke server pusat setiap **30 detik**. Tombol **SYNC** juga tersedia untuk sync manual kapan saja.

### 3. Isolated Session per Node
Secret key Flask di-generate unik per node (`gacoan_Node2`, `gacoan_Node3`), sehingga sesi login di satu node tidak bentrok dengan node lain.

### 4. Composite Primary Key Anti-Konflik
Transaksi diidentifikasi dengan kombinasi `(asal_node, id_lokal)` — bukan integer auto-increment biasa. Node 2 dan Node 3 bisa sync bersamaan tanpa tabrakan Primary Key di server pusat.

### 5. Kasir Berbasis Resep (Bill of Materials)
Kasir pilih menu → sistem otomatis potong stok semua bahan sesuai resep dikali jumlah porsi. Tidak perlu input bahan satu per satu.

### 6. CRUD Bahan Baku & Menu di Server Pusat
Admin pusat bisa tambah, edit, hapus, dan restock bahan baku langsung dari dashboard. Pengelolaan menu beserta resepnya juga dilakukan di sini.

### 7. Pull Stok dari Server
Setiap kali cabang menekan SYNC, sistem tidak hanya push data ke server — tapi juga pull stok terbaru dari server ke DB lokal cabang agar semua node sinkron.

---

## 📂 Struktur Folder Proyek

```text
gacoan_system/
├── 📂 node1_server/               # SERVER PUSAT (PORT 5000)
│   ├── server_api.py              # File Utama Menjalankan Server Pusat
│   ├── gacoan_inventory.db        # Database Pusat
│   ├── 📂 routes/
│   │   ├── _api.py                # Endpoint API REST untuk Sinkronisasi
│   │   └── _web.py                # Rute UI Dasbor Web Pusat
│   └── 📂 templates/              # Tampilan HTML Server Pusat (Tombol ACC)
│
├── 📂 node2/                      # CABANG A (PORT 5001)
│   ├── app_cabang.py              # File Utama Menjalankan Cabang A & Worker
│   ├── gacoan_inventory.db        # Database Lokal Cabang A
│   ├── 📂 routes/
│   │   ├── _api_cabang.py         # Logika Transaksi Kasir & Potong Stok
│   │   └── _web_cabang.py         # Rute UI & Autentikasi Kasir Lokal
│   └── 📂 templates/              # Tampilan HTML Kasir Cabang A
│
└── 📂 node3/                      # CABANG B (PORT 5002)
    # [Struktur File Identik Dengan Node 2]
```

> **Catatan:** Semua node menggunakan file Python yang **sama** (`app_cabang.py`). Perbedaan perilaku (Node2 vs Node3) ditentukan oleh argumen saat dijalankan.

---

## 🛠️ Instalasi & Cara Menjalankan

### 1. Install Dependency

```bash
pip install flask requests
```

### 2. Setup Database (Jalankan di SETIAP Node)

```bash
# Di Node 1 (Server Pusat)
python setup_db.py Node1

# Di Node 2 (Cabang A)
python setup_db.py Node2

# Di Node 3 (Cabang B)
python setup_db.py Node3
```

> Perintah ini membuat file `gacoan_inventory.db` dengan skema tabel dan data master yang identik, tapi kredensial login terisolasi sesuai node masing-masing.

### 3. Jalankan Aplikasi

Buka **3 terminal terpisah**, jalankan berurutan:

#### Terminal 1 — Server Pusat (Node 1)
```bash
python server_api.py
```
Browser otomatis terbuka → `http://localhost:5000`
> Di VirtualBox: akses dari node lain via `http://192.168.56.101:5000`

#### Terminal 2 — Cabang A (Node 2)
```bash
python app_cabang.py Node2
```
Browser otomatis terbuka → `http://localhost:5001`

#### Terminal 3 — Cabang B (Node 3)
```bash
python app_cabang.py Node3
```
Browser otomatis terbuka → `http://localhost:5002`

> Kalau lupa argumennya, jalankan saja `python app_cabang.py` tanpa argumen — program akan tanya interaktif di terminal.

---

## 🔑 Kredensial Login

| Node | Username | Password |
|---|---|---|
| Server Pusat (Node 1) | `admin_pusat` | `123` |
| Cabang A (Node 2) | `admin_cabang_a` | `123` |
| Cabang B (Node 3) | `admin_cabang_b` | `123` |

---

## 📦 Data Master Bahan Baku

| ID | Nama Bahan | Satuan | Stok Awal |
|---|---|---|---|
| 1 | Mie Basah | Kg | 100 |
| 2 | Mie Keriting | Kg | 100 |
| 3 | Ayam Cincang | Kg | 100 |
| 4 | Sambal Rawit | Kg | 100 |
| 5 | Minyak Bawang | Liter | 100 |
| 6 | Pangsit Goreng | Pcs | 200 |

## 🍜 Menu & Resep

| Menu | Harga | Bahan & Jumlah per Porsi |
|---|---|---|
| Mie Gacoan | Rp 15.000 | Mie Basah 1Kg, Ayam Cincang 1Kg, Sambal Rawit 1Kg, Minyak Bawang 1L, Pangsit Goreng 1Pcs |
| Mie Hompimpa | Rp 15.000 | Mie Keriting 1Kg, Ayam Cincang 1Kg, Sambal Rawit 1Kg, Minyak Bawang 1L, Pangsit Goreng 1Pcs |
| Mie Suit | Rp 13.000 | Mie Basah 1Kg, Ayam Cincang 1Kg, Minyak Bawang 1L, Pangsit Goreng 1Pcs |

---

## 🧪 Skenario Pengujian (Demo PAT)

### Skenario 1 — Kasir Normal (Online)

1. Pastikan Node 1 sudah jalan
2. Login ke Node 2 → tab **🧾 Kasir Menu**
3. Pilih menu (contoh: Mie Gacoan), input porsi, klik **CATAT PENJUALAN**
4. Stok lokal langsung berkurang, status transaksi: `PENDING`
5. Klik tombol **⟳ SYNC** di topbar
6. Cek dashboard Node 1 → log transaksi KASIR dari Node 2 masuk, stok gudang berkurang

**Hasil yang diharapkan:** status berubah `pending` → `synced`, stok server terupdate ✅

---

### Skenario 2 — Offline (Server Dimatikan)

1. Stop Node 1 (Ctrl+C di terminal)
2. Di Node 2, lakukan beberapa transaksi kasir seperti biasa
3. Perhatikan topbar → indikator **Server OFFLINE** muncul (merah)
4. Cek tab **📋 Riwayat** → transaksi tersimpan dengan status `pending`

**Hasil yang diharapkan:** operasional kasir tetap jalan, tidak ada error, data aman di DB lokal ✅

---

### Skenario 3 — Sync Setelah Offline (Dua Cabang Bersamaan)

1. Jalankan kembali Node 1
2. Klik SYNC di Node 2, langsung klik SYNC juga di Node 3
3. Cek dashboard Node 1

**Hasil yang diharapkan:** semua data dari Node 2 dan Node 3 masuk tanpa konflik ID, tidak ada duplikat, stok gudang berkurang sesuai total dari kedua cabang ✅

---

### Skenario 4 — Stok Lokal Tidak Cukup

1. Di Node 2, input penjualan dengan jumlah porsi yang sangat besar (melebihi stok)
2. Klik CATAT PENJUALAN

**Hasil yang diharapkan:** transaksi **ditolak**, muncul pesan error spesifik menyebut nama bahan yang kurang, stok tidak berubah, tidak ada yang masuk ke `sync_queue` ✅

---

## 🗄️ Skema Database

Semua node menggunakan skema tabel yang identik:

| Tabel | Fungsi |
|---|---|
| `user` | Data login per node (terisolasi berdasarkan asal_node) |
| `bahan_baku` | Master data bahan baku + stok real-time lokal |
| `menu` | Daftar menu yang bisa dijual (sync dari server) |
| `resep` | Mapping menu → bahan baku + kuantitas per porsi |
| `transaksi_header` | Header transaksi dengan Composite PK `(asal_node, id_lokal)` |
| `transaksi_detail` | Detail bahan per transaksi |
| `sync_queue` | Antrian sinkronisasi ke server (status: pending/synced/failed) |

---

## 🔄 Alur Sinkronisasi

```
[Cabang Input Transaksi]
        │
        ▼
[Simpan ke DB Lokal]  ←── Langsung, tidak butuh internet
[Update Stok Lokal ]
[Masuk sync_queue  ]  status: PENDING
        │
        ▼ (klik SYNC atau auto setiap 30 detik)
[Push ke POST /sync server pusat]
        │
        ├── Sukses → status: SYNCED, stok server diupdate
        │            + pull stok terbaru ke DB lokal
        │
        └── Gagal  → status: tetap PENDING, dicoba lagi
                     di siklus berikutnya (idempotent)
```

---

## 🌐 API Endpoints (Node 1)

| Method | Endpoint | Fungsi |
|---|---|---|
| `GET` | `/ping` | Cek status server online/offline |
| `GET` | `/stok` | Ambil stok terkini semua bahan baku |
| `GET` | `/menu_list` | Ambil daftar menu aktif + resepnya |
| `POST` | `/sync` | Terima data transaksi dari cabang |
| `GET` | `/` | Dashboard monitoring server pusat |
| `POST` | `/bahan/tambah` | Tambah bahan baku baru |
| `POST` | `/bahan/edit` | Edit data bahan baku |
| `POST` | `/bahan/hapus/<id>` | Hapus bahan baku |
| `POST` | `/bahan/restock` | Tambah stok bahan baku |
| `POST` | `/menu/tambah` | Tambah menu + resep baru |
| `POST` | `/menu/hapus/<id>` | Hapus menu |
| `POST` | `/menu/toggle/<id>` | Aktifkan/nonaktifkan menu |

---

## ⚙️ Konfigurasi VirtualBox (Pengujian Multi-VM)

Untuk pengujian di 3 VM terpisah, ubah `SERVER_URL` di `app_cabang.py`:

```python
# Baris ini di app_cabang.py
SERVER_URL = "http://192.168.56.101:5000"  # IP Node 1 di jaringan Host-Only
```

Pastikan semua VM menggunakan **Host-Only Adapter** di VirtualBox agar bisa saling berkomunikasi.

| Node | IP (Host-Only) | Port |
|---|---|---|
| Node 1 — Server Pusat | 192.168.56.101 | 5000 |
| Node 2 — Cabang A | 192.168.56.102 | 5001 |
| Node 3 — Cabang B | 192.168.56.103 | 5002 |

---

## 👤 Info Proyek

| | |
|---|---|
| **Mata Kuliah** | Pengembangan Aplikasi Terdistribusi (A) |
| **Dosen Pengampu** | Dr. Meidya Koeshardianto, S.Si., MT |
| **Penyusun** | Ahmad Afha Assalami (230411100124) |
| **Program Studi** | Teknik Informatika — Universitas Trunojoyo Madura |
| **Tahun** | 2026 |