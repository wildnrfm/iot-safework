# SAFEWORK AI — kerangka proyek

Pos Cek APD Cerdas: **webcam → YOLO → aturan profil → lampu/buzzer + dashboard**.
Kerangka ini disusun supaya semuanya bisa dikerjakan **di laptop dulu**. ESP32 dicolok belakangan tanpa
mengubah logika, karena lampu dan buzzer hanya diakses lewat satu antarmuka (`Indicator`).

## Status

Sudah diuji di lingkungan pembuatan (47 unit test dan simulasi): evaluator profil, state machine pos cek,
indikator virtual dan serial (memakai serial palsu), penyimpanan SQLite, pipeline simulasi dengan stream MJPEG,
logika JavaScript dashboard (DOM tiruan), dan logika firmware ESP32 (disimulasikan di PC).

**Belum diuji:** lapisan FastAPI/uvicorn (paketnya tidak tersedia di sana), model YOLO dan webcam sungguhan,
pyserial dengan board asli, dan sketsa di ESP32 sungguhan. Lihat "Hal pertama yang dicek" di bagian bawah.

## Coba sekarang (tanpa kamera, model, atau ESP32)

1. **Demo konsol** (hanya butuh Python 3.10+):

   ```bash
   python scripts/demo_console.py
   ```

   Contoh keluaran: `[ 1.0 dtk] HASIL: Lengkap.` → `lampu -> GREEN`, lalu `HASIL: Belum lengkap. Lengkapi: Masker.`
   → `lampu -> RED + buzzer 3 bip`, lalu `HASIL: Tidak dapat dipastikan.` → `lampu -> YELLOW`.

2. **Dashboard mode simulasi:**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate            # Windows. Linux/macOS: source .venv/bin/activate
   pip install -r requirements.txt
   python -m safework --fake
   ```

   Buka http://127.0.0.1:8000 dan klik **Aktifkan suara** (browser butuh satu klik sebelum boleh berbunyi).
   Hentikan dengan **Ctrl+C**. Log tiap permintaan HTTP dimatikan karena dashboard memanggil API dua kali per
   detik; tambahkan `--access-log` bila perlu.
   Skenario berganti otomatis: lengkap → APD terbukti tidak dipakai → APD tidak terlihat jelas.
   Mode simulasi memakai folder `data_sim/` sendiri, jadi riwayat dan ringkasan data nyata (`data/`) tidak tercampur.

3. **Tes:** `python -m unittest` (dijalankan dari folder `safework-ai`; tanpa argumen apa pun).

## Cara kerja

```
Camera ─► Detector (YOLO) ─► evaluate(profil) ─► Checkpoint ─► Indicator (lampu/buzzer)
                                                    │            ├─ VirtualIndicator (dashboard)
                                                    │            └─ SerialIndicator  (ESP32, USB)
                                                    └─► HistoryStore (SQLite) ─► API ─► dashboard
```

* **Satu pekerja** dievaluasi: orang terbesar di frame (pos cek, satu orang di penanda).
* **Per APD wajib** (`evaluator.py`): *terpenuhi* bila APD terlihat di zona tubuhnya; *tidak terpenuhi* hanya bila
  kelas "tidak dipakai" (`no_helmet`, `no_gloves`, ...) terdeteksi; selain itu *tidak dapat dipastikan*.
  Bukti yang bertentangan juga dianggap tidak pasti. APD opsional tidak memengaruhi hasil.
* **Hasil akhir:** ada yang tidak terpenuhi → **Belum lengkap** (merah + buzzer); tidak ada tetapi ada yang tidak pasti
  → **Tidak dapat dipastikan** (kuning); selain itu **Lengkap** (hijau).
* **Konfirmasi** (`checkpoint.py`, asimetris): *terpenuhi* bila APD terlihat pada `confirm_frames` evaluasi
  berturut-turut; *tidak terpenuhi* bila bukti "tidak dipakai" muncul minimal `violation_votes` kali dalam
  `window_frames` evaluasi terakhir dan lebih banyak daripada bukti terpenuhi (tidak perlu berturut-turut, karena
  recall kelas `no_*` model baseline hanya ±0,27–0,65 per frame). Hasil keluar setelah minimal `min_check_seconds`
  bila semua APD wajib sudah pasti, atau paling lama `check_seconds`.
* **Siklus:** Menunggu → Memeriksa → Hasil (ditahan `hold_seconds`) → Menunggu. Hasil belum lengkap diperiksa
  ulang otomatis selama pekerja masih di depan kamera. Setelah hasil lengkap, pemeriksaan berikutnya menunggu
  pekerja pergi. Hasil tidak diputuskan saat pekerja sudah tidak terlihat.
* **Mode aman:** kamera terputus lebih dari 3 detik → `FAULT` (kuning berkedip), tidak pernah menampilkan "Lengkap".
  ESP32 juga masuk mode aman sendiri bila laptop diam lebih dari 5 detik.

Ambang keyakinan bisa diatur dari baris perintah: `--conf-pos` (APD terpasang, bawaan 0,5: ketat karena salah hijau
berbahaya), `--conf-neg` (kelas "tidak dipakai", bawaan 0,35: lebih longgar karena recall model rendah; dijaga
pemungutan suara), dan `--conf-person` (0,5).

Angka-angkanya ada di `CheckpointConfig` (`safework/checkpoint.py`), `RunnerConfig`, dan `config.py`.
Zona tubuh dan alias nama kelas dataset ada di `safework/labels.py`.

## Struktur

```
safework/
  labels.py        label kanonis, alias nama kelas dataset, zona tubuh
  schemas.py       tipe data (Detection, Profile, ItemResult, CheckResult, ...)
  profiles.py      profil pekerjaan + penyimpanan JSON (data/profiles.json)
  evaluator.py     hasil deteksi satu frame -> status per APD (fungsi murni)
  checkpoint.py    mesin status pos cek (waktu lewat argumen, mudah diuji)
  messages.py      teks yang tampil di layar
  indicators/      base.py (antarmuka), virtual.py, serial_esp32.py
  detectors.py     pembungkus YOLO (Ultralytics) -> label kanonis
  sources.py       kamera OpenCV (MJPG 720p, buka ulang otomatis)
  fakes.py         kamera dan detektor palsu (simulasi dan tes)
  render.py        kotak deteksi + JPEG untuk stream
  runner.py        pipeline satu thread: kamera -> ... -> indikator + riwayat
  storage.py       riwayat SQLite (tanpa video)
  service.py       logika API tanpa framework web
  app.py           FastAPI: membungkus service + menyajikan dashboard
static/index.html  dashboard sederhana (ganti dengan Next.js bila mau)
firmware/esp32_indicator/esp32_indicator.ino
scripts/           demo_console.py, benchmark_fps.py, capture_photos.py
docs/              TRAIN.md, local-dataset.example.yaml
tests/             unittest (tanpa paket tambahan)
```

## Indicator: virtual sekarang, ESP32 nanti

Semua kode memanggil `indicator.show_status(status)` atau `indicator.set_lamp(Lamp.RED)`. Implementasinya:

```python
from safework.indicators import MultiIndicator, SerialIndicator, VirtualIndicator

indicator = MultiIndicator([VirtualIndicator()])                            # sekarang
indicator = MultiIndicator([VirtualIndicator(), SerialIndicator("COM5")])   # setelah ESP32 datang
```

Dari baris perintah cukup tambah `--serial COM5` (Linux: `/dev/ttyUSB0`). `MultiIndicator` menjaga satu indikator yang
gagal tidak menjatuhkan yang lain, jadi dashboard tetap hidup walau kabel ESP32 dicabut.

### Protokol USB Serial (115200 baud, ASCII, satu baris per perintah)

| Laptop → ESP32 | Arti |
|---|---|
| `GREEN` / `YELLOW` / `RED` | lampu menyala; `RED` juga membunyikan buzzer 3 kali |
| `OFF` | semua mati (menunggu/memeriksa) |
| `FAULT` | kuning berkedip (kamera bermasalah) |
| `TEST` | hijau → kuning → merah + bip, lalu kembali ke keadaan semula |
| `PING` | heartbeat tiap 1 detik; dibalas `PONG` |

ESP32 membalas `READY` saat boot, `OK`, `PONG`, atau `ERR`. Bila 5 detik tidak ada perintah, ESP32 masuk mode aman
(kuning berkedip) dan lampu hijau lama padam.

### Pengkabelan dan unggah firmware

```
GPIO25 → 220–330 Ω → LED hijau  → GND        GPIO33 → 1 kΩ → basis NPN (2N2222/BC547/S8050)
GPIO26 → 220–330 Ω → LED kuning → GND        emitor → GND, kolektor → buzzer (−), buzzer (+) → VIN (5V)
GPIO27 → 220–330 Ω → LED merah  → GND
```

1. Arduino IDE → Boards Manager → pasang **esp32 by Espressif Systems** → board **ESP32 Dev Module**.
2. Buka `firmware/esp32_indicator/esp32_indicator.ino` → Upload (pakai kabel USB **data**, bukan kabel charge-only).
3. Serial Monitor 115200 baud, akhiran **Newline**: kirim `PING` → `PONG`, lalu `GREEN`, `RED`, `TEST`.
4. **Tutup Serial Monitor** sebelum menjalankan aplikasi (satu port hanya bisa dipakai satu program).

## API

| Endpoint | Fungsi |
|---|---|
| `GET /api/state` | keadaan terkini (fase, status, APD, lampu, FPS, status ESP32) |
| `GET /api/profiles` · `POST /api/profiles` · `DELETE /api/profiles/{id}` | daftar, simpan, hapus profil |
| `POST /api/profiles/active` | ganti profil aktif `{ "id": "..." }` |
| `GET /api/history?limit=50` · `GET /api/summary` · `GET /api/history.csv` | riwayat, ringkasan, ekspor CSV |
| `POST /api/indicator/test` | uji lampu dan buzzer |
| `GET /stream.mjpg` | video dengan kotak deteksi |

Contoh profil: `{"id": "bengkel", "name": "Bengkel", "rules": [{"item": "goggles", "requirement": "wajib"}]}`.
Nilai `item`: `helmet vest gloves boots goggles mask`. Nilai `requirement`: `wajib opsional tidak_diperlukan`.

## Menguji di pos (supaya hasilnya bisa dipercaya)

Rancangannya: **satu pekerja berdiri di penanda 1,5–2 m dari kamera, seluruh tubuh (kepala sampai kaki) terlihat**,
latar polos, cahaya terang dari depan. Zona APD (`ZONES` di `labels.py`) dihitung dari tinggi kotak `person`, jadi
uji sambil duduk dekat kamera (hanya kepala dan bahu) atau dengan latar berantakan bisa memberi hasil yang benar
karena alasan yang salah. Tiga alat bantu:

* **Tampilan bukti.** Kotak **tebal** = dipakai sebagai bukti (orang yang dinilai, atau APD yang lolos ambang dan zona).
  Kotak **tipis berlatar abu-abu** = terdeteksi tetapi diabaikan. Bila hasil dashboard tidak sesuai, lihat kotak mana
  yang tebal.
* **`--debug`**: menggambar zona tiap APD pada profil aktif (kotak kuning) supaya terlihat apakah APD jatuh di zonanya.
* **`--roi "x1,y1,x2,y2"`**: area pemeriksaan sebagai pecahan 0–1 dari frame, mis. `--roi "0.25,0,0.75,1"` hanya
  menilai bagian tengah (pakai tanda kutip di PowerShell). Deteksi di luar area (rak, baju tergantung, orang lain) dibuang.

```powershell
python -m safework --weights runs\ppe-v1\weights\best.pt --debug --roi "0.25,0,0.75,1"
```

Dengan `--roi`, hanya area itu yang dikirim ke model (frame dipotong), jadi objek kecil seperti sarung tangan tampak
lebih besar bagi model dan latar berantakan tidak ikut. Matikan dengan `--no-roi-crop` (ROI lalu hanya menyaring hasil).

**Kamera laptop kurang bagus?** Urutan perbaikan dari yang paling murah: (1) lampu terang dari depan dan jangan
membelakangi jendela; (2) berdiri lebih dekat (±1,5 m) dan pakai `--roi` agar tangan lebih besar di mata model;
(3) webcam USB eksternal 1080p yang sudutnya tidak terlalu lebar (sekitar 70–80°, supaya orang tidak mengecil) dan
bagus di cahaya redup. Sarung tangan dan kacamata paling cepat gagal karena ukurannya kecil di gambar.

## Model baseline (14 November 2026)

YOLO11n dilatih 100 epoch di Colab T4 pada Construction-PPE versi November 2026 (1.000 gambar, 12 kelas):
mAP50 0,765 / mAP50-95 0,545 pada 200 gambar validasi (sedikit optimistis). APD terpasang terdeteksi baik
(AP50 0,77–0,94); kelas `no_*` lebih lemah (AP50 0,37–0,72, recall 0,27–0,65; terendah `no_goggle`). Konsekuensinya:
sebagian pelanggaran nyata akan tampil kuning ("Tidak dapat dipastikan") alih-alih merah sampai ada foto lokal.
Tidak ada kelas `mask`, jadi profil Penyemprot Pestisida selalu kuning sampai model dilatih ulang dengan data lokal;
uji dulu dengan profil Pekerja Proyek Desa. Rincian: `docs/TRAIN.md`.

## Rencana minggu ini (laptop dulu)

- [ ] `python -m safework --fake` jalan, dashboard terbuka, suara berfungsi.
- [ ] `pip install -r requirements-ai.txt`, lalu `python scripts/benchmark_fps.py` (ukur FPS; 5 FPS sudah cukup).
      Bobot `yolo11n.pt` diunduh otomatis saat pertama kali dipakai, jadi butuh internet sekali.
- [ ] Latih model dasar dari Construction-PPE (`docs/TRAIN.md`), catat kelas yang sering salah.
- [ ] `python -m safework --weights runs/ppe-v1/weights/best.pt` dengan webcam laptop dan alat peraga APD.
- [ ] Mulai kumpulkan foto lokal (`scripts/capture_photos.py`); anotasinya paling memakan waktu.
- [ ] **Pesan hardware paling lambat sekitar 17–20 November** (ESP32, kabel USB data, buzzer, LED, transistor, breadboard).

## Keamanan dan privasi

* Server hanya mendengarkan `127.0.0.1`. Jangan ubah ke `0.0.0.0` tanpa autentikasi dan enkripsi.
* Atur `SAFEWORK_ADMIN_TOKEN` agar perubahan profil dan uji alarm meminta token (header `X-Admin-Token`).
  Tanpa token, semua perubahan diizinkan (cukup untuk demo lokal).
* Video tidak disimpan. Riwayat hanya berisi waktu, profil, hasil, dan APD yang kurang, dihapus otomatis setelah
  `retention_days` (30 hari). Pasang pemberitahuan kamera di lokasi dan minta persetujuan pekerja.
* Hasil adalah **pengingat**, bukan dasar sanksi dan bukan pengganti penilaian K3.

## Hal pertama yang dicek saat dijalankan di laptopmu

1. `python -m safework --fake` benar-benar jalan (lapisan FastAPI belum diuji di tempat pembuatan). Bila ada galat
   impor atau versi, tempelkan pesan galatnya ke chat.
2. Nama kelas model barumu cocok dengan `ALIASES` di `labels.py` (`benchmark_fps.py` mencetak daftar kelas model).
3. Di Windows, bila kamera lambat terbuka atau gambarnya tidak muncul, coba `--camera-backend dshow`; bila ada beberapa
   kamera, coba `--camera 1`.
4. Zona tubuh di `ZONES` (`labels.py`) cocok dengan jarak dan sudut kameramu. Bila helm atau sepatu sering dianggap
   "tidak terlihat" padahal terdeteksi, longgarkan zonanya.
5. Sketsa ESP32 di board asli: `PING` → `PONG`, tiga bip saat `RED`, dan kuning berkedip setelah 5 detik tanpa perintah.
