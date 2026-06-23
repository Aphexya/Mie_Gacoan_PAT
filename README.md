# 🍜 Sistem Manajemen Inventaris & Kasir Terdistribusi — Mie Gacoan

Sistem ini merupakan aplikasi manajemen inventaris dan kasir terdistribusi yang dirancang untuk mensimulasikan operasional **Gudang Pusat (Node 1)** dan **Multi-Cabang (Node 2 & Node 3)** pada restoran Mie Gacoan. Proyek ini menerapkan arsitektur *Clean Architecture* modular serta protokol sinkronisasi berbasis konsensus untuk menjamin integritas data antar-node[cite: 8, 11].

---

## 🚀 Fitur Utama Sistem

1. **Multi-Node Terisolasi (Offline-First Design)**
   Setiap cabang memiliki database lokal (`sqlite3`) sendiri yang mandiri. Jika koneksi ke server pusat terputus, cabang tetap dapat menjalankan operasional kasir secara normal tanpa hambatan.
2. **Queue-Based Auto Synchronizer**
   Transaksi penjualan di kasir lokal akan masuk ke antrean (`sync_queue`). Sistem menjalankan *background thread worker* yang otomatis mendeteksi jaringan dan menyinkronkan data pending ke pusat setiap 15 detik.
3. **Isolated Session Domain**
   Keamanan sesi (*session cookie*) antar-node diisolasi secara ketat berdasarkan ID Node, sehingga pemicu *logout* otomatis akibat bentrok session tidak terjadi.
4. **Two-Phase Logistics Contract (Approval Request Restock)**
   Fitur pengajuan bahan baku antar-node yang aman. Cabang tidak dapat menambah stok secara sepihak. Permintaan harus didaftarkan ke pusat, diverifikasi oleh stok gudang utama, dan menunggu keputusan mutlak (**SETUJU** atau **TOLAK**) dari Admin Pusat sebelum cabang dapat menarik data mutasi tersebut[cite: 11, 12].

---

## 📂 Struktur Arsitektur Proyek

Proyek dipecah secara modular untuk mempermudah skalabilitas dan pemeliharaan kode:

```text
gacoan_system/
├── 📂 node1_server/               # SERVER PUSAT (PORT 5000)
│   ├── server_api.py              # File Utama Runner Server
│   ├── gacoan_pusat.db            # Database Pusat
│   ├── 📂 routes/
│   │   └── _api.py                # Endpoint API Gudang & Sinkronisasi
│   └── 📂 templates/              # UI Dashboard Pusat (ACC/Tolak Fitur)
│
├── 📂 node2/                      # CABANG A (PORT 5001)
│   ├── app_cabang.py              # Kontroler Utama & Background Worker
│   ├── gacoan_inventory.db        # Database Lokal Cabang A
│   ├── 📂 routes/
│   │   ├── __init__.py            # Python Package Marker
│   │   ├── _api_cabang.py         # Logika Transaksi & Proxy Restock
│   │   └── _web_cabang.py         # Rute UI & Autentikasi Cabang
│   └── 📂 templates/              # UI Dashboard Cabang A
│
└── 📂 node3/                      # CABANG B (PORT 5002)
    # [Struktur Modul Identik Dengan Node 2]

🛠️ Panduan Instalasi & Cara Menjalankan

### 1) Kebutuhan Environment
- Python 3.x
- Flask
- requests

### 2) Langkah Menjalankan Aplikasi (Simulasi 1 Laptop Lokal)
Buka 3 terminal terpisah pada VS Code, lalu jalankan perintah berikut secara berurutan:

#### Terminal 1 — Server Pusat (Node 1)
```bash
cd node1_server
python server_api.py
```
Akses UI: http://localhost:5000

#### Terminal 2 — Cabang A (Node 2)
```bash
cd node2
python app_cabang.py Node2
```
Akses UI: http://localhost:5001

#### Terminal 3 — Cabang B (Node 3)
```bash
cd node3
python app_cabang.py Node3
```
Akses UI: http://localhost:5002

### 🔑 Kredensial Login Demo
| Lingkup Node | Username | Password |
|---|---|---|
| Server Pusat (Node 1) | admin_pusat | 123 |
| Cabang A (Node 2) | admin_cabang_a | 123 |
| Cabang B (Node 3) | admin_cabang_b | 123 |

### 🧪 Skenario Pengujian Validasi (Untuk Demo Tugas Besar)

#### Skenario A: Siklus Kasir Offline & Auto-Sync
Lakukan transaksi pada Kasir Cabang A (localhost:5001). Stok bahan baku lokal cabang otomatis terpotong sesuai resep menu, dan muncul status **PENDING** pada topbar. Tunggu **15 detik**, background thread akan mengirimkan data tersebut ke pusat. Periksa Dashboard Pusat (localhost:5000), transaksi log **KASIR** dari Node 2 otomatis tercatat secara real-time.

#### Skenario B: Pengajuan Bahan Baku Berbasis Konsensus (Sukses/ACC)
Pada Dashboard Cabang, masuk ke tab **Restock**, pilih bahan baku dan kuantitas, lalu klik **Minta Bahan**. Status lokal tertulis **pending** (stok lokal cabang belum bertambah)[cite: 12].

Buka Dashboard Pusat, pada tabel **Log Transaksi Terbaru** akan muncul baris data **REQ_PUSAT** lengkap dengan kolom aksi khusus berisi dua tombol. Klik tombol **✓ SETUJU** di Server Pusat. Stok Gudang Pusat terpotong secara sah.

Kembali ke Dashboard Cabang, klik tombol **⟳ SYNC**[cite: 8]. Sistem akan memverifikasi status persetujuan, mengubah nota lokal menjadi **IN**, dan stok lokal cabang resmi bertambah[cite: 8].

#### Skenario C: Penolakan Pengajuan Bahan Baku (Gagal/Tolak)
Lakukan kembali pengajuan **Minta Bahan** dari cabang[cite: 12].

Pada Dashboard Pusat, klik tombol **✕ TOLAK**. Stok pusat aman (tidak terpotong). Kembali ke Dashboard Cabang, klik tombol **⟳ SYNC**[cite: 8]. Sistem cabang mendeteksi penolakan dari pusat, memperbarui status lokal menjadi **failed**, dan memblokir penambahan stok pada cabang demi menjaga validitas data inventaris[cite: 8].

#### Skenario D: Toleransi Kegagalan Jaringan (Fault Tolerance)
Matikan Server Pusat (Terminal 1 di-stop). Lakukan pengajuan restock dari cabang[cite: 12]. Sistem menangkap kegagalan koneksi lewat blok **try-except**, menampilkan pesan **"Server Pusat Offline!"**, serta mengamankan database lokal dari manipulasi stok sepihak[cite: 12].
