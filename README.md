# SAFEWORK AI

Prototipe pos cek APD berbasis webcam, YOLO, dashboard lokal, penyimpanan SQLite, dan indikator lampu/buzzer ESP32.
Hasil aplikasi adalah pengingat bagi pekerja, bukan pengganti penilaian risiko, pengawas K3, atau keputusan sanksi.

## Status

- 64 unit test lulus.
- Mode simulasi `--fake` lulus untuk dashboard, stream MJPEG, profil, dan riwayat SQLite.
- YOLO11n diukur ±107 ms per frame pada CPU laptop, sekitar 9,3 FPS.
- Model baseline `ppe-v1` dilatih pada Colab T4.
- Webcam sungguhan, ESP32, pyserial, dan alat peraga belum divalidasi sebagai satu unit.

## Persyaratan

- Windows 10/11 atau Linux
- Python 3.10 atau lebih baru
- Webcam untuk mode nyata
- ESP32 untuk indikator lampu/buzzer

## Instalasi

Gunakan `.venv` sebagai environment tunggal untuk semua perintah:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-ai.txt
pip install -e ".[dev]"
```

Mode simulasi tidak memerlukan webcam atau Ultralytics:

```powershell
pip install -r requirements.txt
python -m safework --fake
```

Buka `http://127.0.0.1:8000`, lalu hentikan aplikasi dengan `Ctrl+C`.

## Jalankan Mode Nyata

```powershell
python -m safework --weights runs\ppe-v1\weights\best.pt --camera 0 --debug
```

Gunakan model v2 hasil notebook setelah latihan selesai:

```powershell
python -m safework --weights runs\ppe-v2-yolo11n\weights\best.pt --debug
```

Opsi yang berguna:

```text
--camera 1                 pilih kamera lain
--camera-backend dshow     paksa DirectShow di Windows
--serial COM5              hubungkan ESP32
--roi "0.25,0,0.75,1"      batasi area pemeriksaan
--no-roi-crop              gunakan ROI sebagai filter, bukan pemotongan model
--fps 10                   tetapkan target pemrosesan
```

## Cara Kerja

```text
Kamera -> YOLO -> Evaluasi profil -> State checkpoint -> Lampu/buzzer -> Dashboard
                                      |
                                      -> Riwayat SQLite
```

- Orang terbesar dalam ROI dipilih sebagai subjek pemeriksaan.
- APD wajib harus memiliki bukti positif atau dinilai tidak dapat dipastikan.
- Bukti `no_*` memerlukan voting dalam beberapa frame sebelum menghasilkan "Belum lengkap".
- Kamera terputus lebih dari 3 detik menghasilkan kondisi aman `FAULT`.
- ESP32 berhenti menerima heartbeat lebih dari 5 detik lalu masuk kondisi aman sendiri.

Konfigurasi threshold, zona tubuh, dan alias kelas berada di `safework/config.py`, `safework/labels.py`,
dan `safework/checkpoint.py`.

## Struktur

```text
safework/
  app.py                 endpoint FastAPI dan lifecycle server
  bootstrap.py           pembentukan layanan dari konfigurasi
  checkpoint.py          state machine pemeriksaan
  evaluator.py           evaluasi satu frame
  runner.py              thread pipeline webcam/deteksi
  storage.py             riwayat SQLite
  indicators/            virtual dan ESP32 serial
  profiles.py            profil APD

static/                  dashboard web
firmware/                firmware ESP32
scripts/                 utilitas benchmark dan pengambilan foto
tests/                   unit test
docs/
  TRAIN.md               prosedur pelatihan baseline
  notebooks/             train_ppe_v1_colab.ipynb, train_ppe_v2_colab.ipynb
  local-dataset.example.yaml
data/                    profil dan riwayat lokal (tidak masuk Git)
runs/                    output latihan dan bobot model (tidak masuk Git)
```

Data runtime, dataset lokal, environment virtual, dan output latihan diabaikan Git melalui `.gitignore`.

## Testing

```powershell
python -m unittest
ruff check --select E4,E7,E9,F safework scripts tests
```

## Pelatihan Model

Model baseline tersedia di `runs/ppe-v1/weights/best.pt`.
Notebook gabungan model v2 berada di [docs/notebooks/train_ppe_v2_colab.ipynb](docs/notebooks/train_ppe_v2_colab.ipynb).

Hasil eksperimen v2 saat ini berada di `runs/ppe-v2-yolo11n/weights/best.pt`.
Evaluasi awal mendapatkan mAP50 0,763 pada Construction-PPE (baseline 0,770) dan 0,357 pada PPEs test.
Namun, data latih tidak memiliki label `mask` maupun `no_mask`, sehingga AP50 kedua kelas tersebut 0.
Model ini **belum layak untuk pemeriksaan masker**; pertahankan baseline v1 untuk kelas lainnya.

Notebook v2 menggabungkan Construction-PPE dan PPEs Dataset menjadi 14 kelas. Sebelum memakai hasil latihan
berikutnya, pastikan ringkasan notebook menunjukkan contoh `mask` dan `no_mask` pada data latih.
Gunakan bobot v2 secara eksplisit dengan:

```text
runs/ppe-v2-yolo11n/weights/best.pt
```

Setelah pelatihan, validasi terlebih dahulu:

```powershell
python scripts\benchmark_fps.py --weights runs\ppe-v2-yolo11n\weights\best.pt
python -m safework --weights runs\ppe-v2-yolo11n\weights\best.pt --debug --roi "0.25,0,0.75,1"
```

Nama model baru `mask` dan `no_mask` harus cocok dengan `ALIASES` di `safework/labels.py`.

## Sumber Data dan Lisensi

- Construction-PPE, Ultralytics, CC BY 4.0:
  <https://docs.ultralytics.com/datasets/detect/construction-ppe>
- PPEs Dataset, Roboflow Universe, CC BY 4.0:
  <https://universe.roboflow.com/personal-protective-equipment/ppes-kaxsi>
- Salinan dataset PPEs di Hugging Face:
  <https://huggingface.co/datasets/keremberke/protective-equipment-detection>
- Teks lisensi CC BY 4.0:
  <https://creativecommons.org/licenses/by/4.0/>

Pustaka Ultralytics berlisensi AGPL-3.0. Lisensi distribusi SAFEWORK AI dan atribusi model/dataset harus
ditinjau pemilik proyek sebelum deployment komersial.

## Keamanan dan Privasi

- Server default hanya mendengarkan `127.0.0.1`.
- Tetapkan `SAFEWORK_ADMIN_TOKEN` sebelum mengizinkan perubahan profil atau uji indikator.
- Di PowerShell, atur token untuk sesi saat ini dengan `$env:SAFEWORK_ADMIN_TOKEN = "token-rahasia"`.
- Jangan expose dashboard ke jaringan tanpa autentikasi dan enkripsi.
- Video tidak disimpan. Hanya waktu, profil, hasil, dan APD yang kurang disimpan di SQLite.
- Kamera harus diberi pemberitahuan kepada pekerja dan persetujuan harus diperoleh sesuai kebutuhan lokal.

## Kontributor

Ikuti [CONTRIBUTING.md](CONTRIBUTING.md). Laporkan masalah keamanan melalui [SECURITY.md](SECURITY.md).
