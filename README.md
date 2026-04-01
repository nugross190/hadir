# HADIR

**Hadirkan Administrasi Digital untuk Institusi dan Rekap**

Sistem pencatatan kehadiran guru dan siswa untuk SMAN 5 Garut. Dibangun untuk 3 staff admin yang mencatat presensi di 24–36 kelas setiap hari, dengan pengawasan dari kepala sekolah melalui dashboard.

Aplikasi ini berjalan di browser HP — tidak perlu install apapun.

---

## Cara Kerja Singkat

Setiap pagi, staff admin membuka HADIR di HP, login dengan PIN, lalu memasukkan kode 6 digit yang tampil di layar PC sekolah (bukti kehadiran fisik). Setelah itu, admin memilih kelas, mencatat status guru dan siswa satu per satu, lalu simpan. Kepala sekolah bisa memantau progres dan mengunduh laporan kapan saja.

---

## Siapa Mengakses Apa

### 👨‍💼 Kepala Sekolah

Login melalui halaman utama → pilih "Kepala Sekolah" → masukkan PIN.

Setelah login, masuk ke **Dashboard** yang menampilkan:
- **Ringkasan** — cakupan presensi hari ini, jumlah guru/siswa tercatat, aktivitas staff, tren 7 hari terakhir
- **Per Kelas** — persentase kehadiran setiap kelas pada tanggal tertentu
- **Laporan** — unduh 4 jenis laporan Excel (rekap harian, rekap guru, rekap siswa per kelas, akuntabilitas staff)
- **Kelola Siswa** — tambah, edit, pindah kelas, atau nonaktifkan siswa

### 📋 Admin Staff (3 orang)

Login melalui halaman utama → pilih "Admin" → pilih nama → masukkan PIN.

Setelah login, masuk ke **halaman input presensi**:
1. Masukkan kode TOTP 6 digit dari layar PC sekolah (membuktikan admin hadir secara fisik)
2. Pilih tanggal dan kelas yang ditugaskan
3. Pilih jadwal pelajaran (slot JP), catat status guru (hadir/tidak hadir/terlambat/sakit/izin)
4. Catat status setiap siswa di kelas tersebut
5. Simpan, lanjut ke kelas berikutnya
6. Selesai → klik ✓ untuk mengakhiri sesi

Admin juga bisa membuka **Dashboard terbatas** (hanya tab Per Kelas dan Laporan) melalui tombol "Dashboard" di halaman input.

Setiap admin hanya melihat kelas yang ditugaskan kepadanya:
- Admin 1 — Kelas X (A–H)
- Admin 2 — Kelas XI (E–L)
- Admin 3 — Kelas X (I–L) + Kelas XI (A–D)

Kelas XII tidak diinput karena sudah mengikuti ujian kelulusan.

### 🔐 Administrator (Pengelola Sistem)

Akses melalui tautan tersembunyi di halaman login → masukkan PIN administrator.

Masuk ke **Panel Administrator** yang berisi:
- Navigasi ke semua halaman (dashboard, input presensi, layar TOTP, login)
- Statistik sistem (jumlah guru, kelas, siswa, staff)
- Info kesehatan database dan versi sistem
- Daftar akun terdaftar
- Tombol seed data (hanya dijalankan sekali saat pertama deploy)

### 🖥️ Layar TOTP (PC Bel Sekolah)

Diakses melalui URL khusus dengan kunci rahasia: `/display?key=KUNCI_RAHASIA`

Menampilkan kode 6 digit yang berubah setiap 5 menit. Layar ini ditampilkan di PC yang ada di ruang guru atau pos piket. Staff admin harus memasukkan kode ini untuk memulai sesi pencatatan — ini adalah bukti bahwa admin benar-benar hadir di sekolah.

Tanpa parameter `?key=` yang benar, layar menampilkan "Akses ditolak".

---

## Laporan yang Dihasilkan

Semua laporan dapat diunduh sebagai file Excel (.xlsx) dari tab Laporan di dashboard.

**Rekap Harian** — seluruh kelas dalam satu hari: kelas, JP, guru, mapel, status guru, jumlah siswa per status.

**Rekap Kehadiran Guru** — ringkasan per guru dalam rentang waktu: berapa kali hadir, tidak hadir, terlambat, sakit, izin.

**Rekap Kehadiran Siswa** — per siswa dalam satu kelas dan rentang waktu: detail status kehadiran masing-masing siswa.

**Akuntabilitas Staff** — log aktivitas staff: kapan mulai sesi, kapan selesai, apakah TOTP terverifikasi, berapa sesi yang direkam.

---

## Untuk Non-Developer: Cara Deploy

HADIR sudah berjalan di cloud dan bisa diakses dari browser HP manapun. Jika Anda perlu mendeploy ulang atau memindahkan ke server lain:

1. Buat akun di platform hosting (Railway, Koyeb, atau Fly.io)
2. Buat database PostgreSQL
3. Hubungkan repository GitHub ini
4. Set environment variables:
   - `DATABASE_URL` — connection string dari database PostgreSQL
   - `OWNER_PIN` — PIN untuk akses administrator
   - `DISPLAY_KEY` — kunci rahasia untuk layar TOTP
5. Setelah deploy berhasil, buka `/panel` dan jalankan "Seed Data" untuk mengisi data awal
6. Bagikan URL ke staff admin dan kepala sekolah

Data awal yang di-seed: 67 guru, 36 kelas, 795 slot jadwal, 1.256 siswa, 3 akun admin + 1 akun kepala sekolah.

---

## Data Sekolah

| Data | Jumlah | Sumber |
|------|--------|--------|
| Guru | 67 | Data Kode Guru sekolah |
| Kelas | 36 | X (A–L), XI (A–L), XII (A–L) |
| Jadwal | 795 slot/minggu | Jadwal pelajaran sekolah |
| Siswa | 1.256 | Data e-RAPOR / roster kelas |
| Staff Admin | 3 | Petugas piket administrasi |

---

## Informasi Teknis

### Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy 2.0, Uvicorn
- **Database**: PostgreSQL
- **Frontend**: Vanilla HTML/CSS/JS (mobile-first, tanpa framework)
- **Deploy**: Docker → Railway/Koyeb/Fly.io

### Struktur Proyek

```
hadir/
├── main.py                    # Entry point FastAPI + route definitions
├── config.py                  # Database URL, TOTP config, constants
├── database.py                # SQLAlchemy engine + session
├── seed.py                    # Seed script (lokal)
│
├── models/
│   ├── staff.py               # Admin staff (PIN login)
│   ├── teacher.py             # Guru (kode, nama, NIP)
│   ├── school.py              # Class + Student
│   ├── schedule.py            # ScheduleSlot (jadwal mingguan)
│   └── attendance.py          # RecordingSession, AttendanceSession,
│                              # TeacherAttendanceRecord, StudentAttendanceRecord
│
├── routers/
│   ├── auth.py                # Login + owner auth + staff management
│   ├── totp.py                # TOTP display + validation
│   ├── attendance.py          # Recording flow
│   ├── dashboard.py           # Dashboard JSON API
│   ├── reports.py             # Excel report generation
│   └── students.py            # Student CRUD
│
├── services/
│   ├── auth_service.py        # PIN verification
│   ├── totp_service.py        # HMAC-based TOTP generation
│   ├── attendance_service.py  # Attendance recording logic
│   └── report_service.py      # Report data queries
│
├── frontend/
│   ├── login.html             # Halaman login (role selection)
│   ├── index.html             # Input presensi (admin)
│   ├── dashboard.html         # Dashboard (semua role)
│   ├── panel.html             # Panel administrator
│   └── display.html           # Layar TOTP (PC sekolah)
│
├── seed_data/                 # JSON files untuk data awal
├── Dockerfile                 # Container config
├── requirements.txt           # Python dependencies
└── railway.json               # Railway deploy config
```

### Alur Data

```
Staff login → PIN verify → TOTP verify → RecordingSession dimulai
                                              │
                              AttendanceSession (per slot per tanggal)
                                 ├── TeacherAttendanceRecord (1:1)
                                 └── StudentAttendanceRecord (1:N, per siswa)
```

### Halaman & Route

| Route | Halaman | Akses |
|-------|---------|-------|
| `/` atau `/login` | Login | Semua |
| `/input` | Input presensi | Admin (setelah login) |
| `/dashboard` | Dashboard | Kepala sekolah, admin (terbatas), owner |
| `/panel` | Panel administrator | Owner (setelah login) |
| `/display?key=xxx` | Layar TOTP | PC sekolah (butuh kunci) |

### API Endpoints

| Method | Path | Fungsi |
|--------|------|--------|
| POST | `/auth/login` | Login staff (PIN) |
| POST | `/auth/owner-login` | Login administrator |
| GET | `/auth/staff` | Daftar akun staff |
| POST | `/auth/add-staff?key=xxx` | Tambah akun baru |
| GET | `/totp/display?key=xxx` | Data TOTP untuk layar |
| POST | `/totp/validate` | Validasi kode TOTP |
| POST | `/attendance/session/start` | Mulai sesi recording |
| POST | `/attendance/record` | Simpan presensi |
| GET | `/dashboard/summary` | Data ringkasan |
| GET | `/dashboard/class-stats` | Statistik per kelas |
| GET | `/dashboard/weekly-trend` | Tren mingguan |
| GET | `/reports/daily-recap` | Download Excel rekap harian |
| GET | `/reports/teacher-summary` | Download Excel rekap guru |
| GET | `/reports/student-summary` | Download Excel rekap siswa |
| GET | `/reports/staff-accountability` | Download Excel akuntabilitas |
| GET | `/students/by-class/{id}` | Daftar siswa per kelas |
| PUT | `/students/{id}` | Edit data siswa |
| POST | `/students/` | Tambah siswa baru |
| DELETE | `/students/{id}` | Nonaktifkan siswa |
| POST | `/students/{id}/move` | Pindah kelas |

### Environment Variables

| Variable | Fungsi | Contoh |
|----------|--------|--------|
| `DATABASE_URL` | Connection string PostgreSQL | `postgresql://user:pass@host:5432/hadir` |
| `OWNER_PIN` | PIN administrator | `firman2026` |
| `DISPLAY_KEY` | Kunci akses layar TOTP | `sman5-secret-2026` |

---

*Dibangun untuk SMAN 5 Garut oleh Firman Nugraha, M.Pd.*
