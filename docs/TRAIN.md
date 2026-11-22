# Melatih model APD

Catatan: perintah di bawah belum dijalankan di lingkungan pembuatan kerangka ini (tanpa internet dan GPU).
Cocokkan dengan dokumentasi Ultralytics yang terbaru bila ada perbedaan.

## 0. Siapkan
```bash
pip install -r requirements-ai.txt
python scripts/benchmark_fps.py --weights yolo11n.pt      # ukur FPS di laptopmu lebih dulu
```
Tanpa GPU, latih di Google Colab atau Kaggle (pilih runtime GPU), lalu unduh `best.pt`.

## 1. Model dasar dari Construction-PPE
```bash
yolo detect train data=construction-ppe.yaml model=yolo11n.pt epochs=100 imgsz=640 project=runs name=ppe-v1
```
Dataset diunduh otomatis. Versi November 2026: 1.000 gambar (800 latih, 200 validasi, tanpa test split), 12 kelas:
helmet, gloves, vest, boots, goggles, Person, no_helmet, no_goggle, no_gloves, no_boots, no_vest, forklift.
Tidak ada `mask`/`no_mask`; `forklift` diabaikan oleh `safework/labels.py`. Lisensi dataset CC BY 4.0 (beri atribusi).
Versi lama dataset (1.416 gambar, 11 kelas, AGPL-3.0) masih ada terpisah dengan urutan kelas berbeda, jadi cetak
`model.names` untuk memastikan.

## 2. Evaluasi per kelas
```bash
yolo detect val model=runs/ppe-v1/weights/best.pt data=construction-ppe.yaml
```
Lihat precision/recall per kelas dan confusion matrix. Catat kelas yang paling sering salah.
Satu hal yang diperiksa khusus: seberapa sering `no_*` muncul padahal APD dipakai (alarm palsu).

### Hasil baseline kita (14 November 2026)
YOLO11n, 100 epoch, Colab T4; dievaluasi pada 200 gambar validasi (angka sedikit optimistis karena validasi juga
memilih bobot terbaik): mAP50 0,765 dan mAP50-95 0,545.

| Kelas | Presisi | Recall | AP50 |
|---|---|---|---|
| helmet / gloves / vest / boots / goggles | 0,87–0,96 | 0,67–0,95 | 0,77–0,94 |
| no_helmet | 0,875 | 0,570 | 0,662 |
| no_gloves | 0,897 | 0,557 | 0,647 |
| no_boots | 0,821 | 0,646 | 0,706 |
| no_vest | 0,869 | 0,610 | 0,720 |
| **no_goggle** | 0,686 | **0,268** | 0,366 |

Artinya: APD terpasang terdeteksi baik dan alarm `no_*` yang muncul umumnya benar (presisi tinggi), tetapi hanya
±55–65% pelanggaran yang tertangkap per frame (kacamata hanya 27%). Karena itu `checkpoint.py` memakai pemungutan suara
untuk pelanggaran, bukan deteksi berturut-turut. Perbaikan utama datang dari foto lokal (bagian 3), terutama `no_goggle`.

## 3. Tambah data lokal (inilah yang paling menentukan hasil di hari penilaian)
1. Foto di latar dan pencahayaan demo dengan alat peraga: `python scripts/capture_photos.py --scene lengkap`.
2. Ambil contoh lengkap dan tidak lengkap, dari beberapa orang, jarak, dan sudut.
3. Anotasi dengan alat seperti CVAT atau Label Studio memakai daftar kelas di `docs/local-dataset.example.yaml`.
   Wajib menambah `mask` dan `no_mask` (tidak ada di Construction-PPE). Untuk APD lain, tambah contoh `no_*`
   sebanyak mungkin, terutama `no_goggle` (recall baseline hanya 0,27).
4. Salin konfigurasi contoh lalu ubah path datanya:
```powershell
Copy-Item docs/local-dataset.example.yaml docs/local-dataset.yaml
```
Kemudian latih ulang dari bobot sebelumnya:
```bash
yolo detect train data=docs/local-dataset.yaml model=runs/ppe-v1/weights/best.pt epochs=60 imgsz=640 project=runs name=ppe-v2-local
```
Bobot hasil ada di `runs/ppe-v2-local/weights/best.pt`. Pisahkan data uji berdasarkan orang atau sesi, bukan
acak antar foto, supaya hasil uji tidak terlalu optimis.

## 4. Menggabungkan dataset (hati-hati)
Dataset tanpa kelas "tidak dipakai" (mis. PPE_Detection) jangan langsung dicampur dengan yang memilikinya.
APD yang tidak dipakai pada gambar dari dataset tanpa label itu akan terbaca sebagai latar belakang dan menekan
deteksi `no_*`. Pilihan: relabel sebagian gambar, hanya ambil kelas positif yang tidak ada di dataset utama
(mis. mask), atau isi kelas `no_*` dari data lokal.

## 5. Pakai di aplikasi

```bash
python -m safework --weights runs/ppe-v2-local/weights/best.pt --serial COM5
```
Bila memakai notebook v2, bobot fine-tune berada di `runs/ppe-v2-ft1/weights/best.pt`; eksperimen
yang dilatih dari YOLO11n berada di `runs/ppe-v2-yolo11n/weights/best.pt`. Arsip eksperimen terpilih
beserta konfigurasi, checkpoint, metrik, dan plot disimpan di repository.
Bila nama kelas model berbeda, tambahkan alias di `safework/labels.py` (ALIASES). Kelas yang tidak dikenal
diabaikan, dan APD yang kelasnya tidak ada pada model otomatis berstatus "tidak dapat dipastikan".
Periksa lisensi sebelum dikembangkan menjadi produk: pustaka Ultralytics AGPL-3.0; dataset Construction-PPE
(versi November 2026) CC BY 4.0 dan wajib diberi atribusi.
