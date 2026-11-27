# Panduan SAFEWORK AI: dari uji model sampai menyala

Simpan sebagai `docs/PANDUAN_SAFEWORK.md`. Baca dari atas ke bawah; urutannya mengikuti urutan kerja. Dokumen ini menggantikan semua panduan terpisah sebelumnya.

## Isi

0. Gambaran besar
1. Urutan kerja
2. Uji alat peraga (kerjakan sekarang)
3. Belanja komponen
4. Apa dicolok ke mana
5. Merakit
6. Uji rakitan
7. Unggah firmware proyek
8. Menyalakan aplikasi
9. Mengemas jadi satu paket dan memasang di pos
10. Masalah umum
11. Yang belum ada

## 0. Gambaran besar

```
Pekerja (berdiri 1,5 sampai 2 m dari kamera)
   |
   v
[ PAKET DI POS ]                                      [ LAPTOP: aplikasi SAFEWORK AI ]
 Webcam 1080p ---+
                 +--- USB hub ==== 1 kabel USB ====   1. Ambil frame kamera
 ESP32 ----------+      (dua arah)                    2. Deteksi APD (YOLO11n v2, 14 kelas)
   |                                                  3. Aturan per profil + voting beberapa frame
   +--> 3 LED + buzzer                                4. Status: hijau / kuning / merah / FAULT
                                                      5. Dashboard + riwayat SQLite,
                                                         dan perintah ke ESP32 lewat serial
```

Cara kerjanya:

1. Webcam di paket menangkap pekerja. Videonya masuk ke laptop lewat satu kabel USB.
2. Di laptop, model YOLO11n v2 mencari APD (helm, rompi, sarung tangan, sepatu, kacamata, masker) dan pelanggarannya (`no_*`).
3. Aturan per profil (Pekerja Proyek Desa atau Penyemprot Pestisida) menilai dari beberapa frame: APD wajib harus punya bukti positif, bukti pelanggaran yang konsisten memberi merah, dan tanpa bukti memberi kuning.
4. Hasilnya tampil di dashboard (browser), tersimpan di riwayat SQLite, dan dikirim ke ESP32 lewat kabel USB yang sama.
5. ESP32 menyalakan lampu hijau, kuning, atau merah, dan buzzer.

Dua pengaman: kamera yang terputus lebih dari 3 detik menjadi `FAULT`, dan ESP32 yang tidak menerima heartbeat lebih dari 5 detik masuk kondisi aman sendiri.

Model dilatih sekali di Colab (hasilnya `best.pt`). Itu bukan bagian yang berjalan di pos.

Status desain: paket satu kabel (webcam eksternal dan ESP32 lewat hub di dalam kotak) sudah diputuskan. Yang masih menunggu pengujian dengan perangkat asli: pin firmware, pengenalan `mask` dan `no_mask` oleh `labels.py`, hasil uji alat peraga, dan peluncur `jalankan.py`.

## 1. Urutan kerja

1. Sekarang: uji model v2 dengan alat peraga di webcam laptop (bagian 2) dan pesan semua komponen, termasuk webcam, tripod, hub, dan kotak (bagian 3). Keduanya tidak saling menunggu.
2. Paket komponen datang: rakit di breadboard (bagian 5), uji rakitan (6), lalu unggah firmware proyek (7).
3. Kemas semuanya jadi satu paket dengan satu kabel ke laptop (bagian 9), lalu nyalakan dengan satu perintah (bagian 8).
4. Kirim ke chat: tabel hasil uji alat peraga, isi `firmware/esp32_indicator/`, dan `safework/labels.py`, supaya panduan dan README bisa disesuaikan.

## 2. Uji alat peraga (kerjakan sekarang)

Tujuan: memastikan warna di `--debug` benar sebelum ESP32 dipasang. Uji ini tidak butuh komponen IoT.

Persiapan:

- Satu orang di depan webcam, jarak 1,5 sampai 2 m, seluruh badan terlihat, cahaya dari depan, latar polos.
- Untuk mengganti profil di dashboard, atur token dulu: `$env:SAFEWORK_ADMIN_TOKEN = "token-rahasia"`
- Jalankan: `python -m safework --weights runs\ppe-v2-ft1\weights\best.pt --debug --roi "0.25,0,0.75,1"`
- Buka `http://127.0.0.1:8000`, pilih profil, lalu tunggu 3 detik di tiap pose sebelum mencatat.
- Arti warna: hijau = lengkap, kuning = belum pasti, merah = belum lengkap. Merah butuh beberapa detik karena voting beberapa frame.
- Tiap baris dicoba 10 kali (berdiri, keluar frame, masuk lagi). Isi kolom Hasil dengan hitungan, misalnya `8H 1K 1M`.

### Uji dasar (ulangi untuk profil Pekerja Proyek Desa dan Penyemprot Pestisida)

| Pose | Diharapkan | Hasil (H/K/M dari 10) | Catatan |
| --- | --- | --- | --- |
| Semua APD wajib terpakai | hijau | | |
| Lepas satu APD wajib (ulangi untuk tiap APD) | merah atau kuning, tidak boleh hijau | | |
| Tidak ada orang di frame | bukan hijau | | |
| Semua APD terpakai, badan miring 45 derajat | hijau atau kuning | | |

### Uji jebakan (risiko hijau palsu)

APD palsu tidak boleh membuat item aslinya hijau. Beberapa jebakan ini nyata karena kelas `boots` di data PPEs berasal dari "sepatu" umum.

| Pengganti | Untuk item | Diharapkan | Hasil (H/K/M dari 10) | Catatan |
| --- | --- | --- | --- | --- |
| Kacamata biasa | goggles | tidak hijau | | |
| Sandal atau sepatu kets | boots | tidak hijau | | |
| Topi atau kupluk | helmet | tidak hijau | | |
| Kaus oranye tanpa pita reflektif | vest | tidak hijau | | |
| Tangan kosong | gloves | tidak hijau | | |
| Tangan atau syal menutup mulut | mask | tidak hijau | | |
| Masker dipasang di dagu | mask | tidak hijau | | |

### Uji positif masker

Pakai jenis masker yang benar-benar akan dipakai saat lomba. Item masker harus hijau.

| Jenis masker | Diharapkan | Hasil (H/K/M dari 10) | Catatan |
| --- | --- | --- | --- |
| Bedah | hijau | | |
| Kain | hijau | | |
| Respirator | hijau | | |

### Kriteria lolos (patokan awal)

- Hijau palsu (hijau padahal APD hilang atau palsu): 0 dari 10. Ini kesalahan paling berbahaya.
- Merah palsu (merah padahal lengkap): paling banyak 1 dari 10.
- Lengkap menjadi hijau: paling sedikit 9 dari 10.
- FPS di dashboard paling sedikit 5.

## 3. Belanja komponen

Webcam eksternal, hub, dan kotak adalah bagian dari paket satu kabel (bagian 4), jadi semuanya wajib kecuali yang ditandai opsional.

| Komponen | Jumlah | Catatan |
| --- | --- | --- |
| ESP32 DevKit V1, 30 pin, versi USB-C (ESP32-WROOM-32) | 1 | Versi 30 pin lebih ramping, di breadboard masih menyisakan satu baris lubang di tiap sisi. Versi 38 pin lebih lebar. Chip USB biasanya CP2102 atau CH9102. |
| Kabel USB-A ke USB-C (data), pendek 20 sampai 30 cm | 1 | Untuk ESP32 ke hub di dalam kotak. Harus kabel data, bukan kabel khusus charger. Kalau board tidak menyala dengan kabel USB-C ke USB-C, pakai USB-A ke USB-C. |
| LED 5 mm hijau, kuning, merah | 1 tiap warna | Beli 2 tiap warna sebagai cadangan. |
| Resistor 220 Ω, ¼ W | 3 | Beli 10. Pembatas arus LED. |
| Buzzer aktif 5 V | 1 | Tipe aktif berbunyi hanya dengan diberi tegangan. Hindari modul buzzer "low level trigger" karena logikanya terbalik. |
| Transistor NPN BC547 atau S8050 | 1 | Beli 3. Penggerak buzzer. Urutan kaki berbeda antar tipe, cek lembar data. |
| Resistor 1 kΩ, ¼ W | 1 | Beli 5. Untuk basis transistor. |
| Dioda 1N4148 atau 1N4007 | 1 | Opsional. Melindungi transistor dari lonjakan buzzer elektromagnetik. |
| Breadboard 830 lubang | 1 | Untuk uji dan rakitan awal. Sebelum dikemas, kabel jumper dikencangkan atau disolder supaya tidak lepas saat dipindah. |
| Kabel jumper male-to-male | 1 pak | |
| Webcam USB 1080p | 1 | Colokan USB-A. Lihat catatan webcam di bawah. |
| Tripod mini atau penjepit webcam | 1 | Sebagian webcam sudah termasuk tripod. |
| USB hub 4 port | 1 | Dipasang di dalam kotak. Pilih yang ramping dan berdaya (powered) bila memungkinkan. Bila laptop hanya punya port USB-C, pilih hub dengan colokan USB-C ke laptop atau siapkan adaptor. |
| Kotak proyek sekitar 20 x 15 x 8 cm | 1 | Tempat hub, ESP32, dan kabel. Harus muat hub dan gulungan kabel webcam. |
| Dudukan LED panel 5 mm | 3 | Opsional, supaya LED rapi di panel depan kotak. |
| Papan terminal ESP32 30 pin (screw terminal) | 1 | Opsional. ESP32 ditancapkan dan kabel dikencangkan dengan sekrup, jadi tidak mudah lepas. |
| Kabel ekstensi USB 2 sampai 3 m | 1 | Opsional, bila kabel hub terlalu pendek untuk menjangkau laptop. |

### Harga

Dari listing Tokopedia yang kutemukan:

- ESP32 DevKit V1 30 pin sekitar Rp69.000 sampai Rp120.000, termasuk versi USB-C.
- Buzzer aktif 5 V sekitar Rp2.450 sampai Rp5.700.
- Webcam 1080p murah sekitar Rp80.000 sampai Rp195.000 (kualitas bervariasi, sebagian fokus manual), kelas menengah sekitar Rp350.000 sampai Rp470.000, dan Logitech C920e sekitar Rp800.000 sampai Rp1,6 juta (di luar anggaran).

Komponen lain hanya perkiraan kasar (belum dicek): hub Rp30.000 sampai Rp100.000, kotak proyek Rp30.000 sampai Rp80.000, kabel USB data, breadboard, dan jumper masing-masing Rp10.000 sampai Rp35.000, sedangkan LED, resistor, transistor, dan dudukan LED total di bawah Rp25.000.

Perkiraan total: sekitar Rp550.000 sampai Rp900.000 dengan webcam kelas menengah, atau sekitar Rp290.000 sampai Rp650.000 dengan webcam murah. Keduanya di bawah batas anggaran Rp1 juta, tetapi yang pertama mendekati batas. Kalau anggaran mepet, pilih webcam yang lebih murah dan lewati papan terminal. Hindari paket starter kit lengkap yang harganya ratusan ribu: kebanyakan isinya tidak terpakai.

### Catatan webcam

Webcam eksternal bagian dari paket karena posisinya bisa diatur terpisah dari laptop: sekitar setinggi dada sampai bahu dengan seluruh badan terlihat dari jarak 1,5 sampai 2 m. Webcam USB 1080p juga biasanya lebih tajam untuk benda kecil seperti masker, kacamata, dan sarung tangan.

Yang dicari: resolusi 1080p, sudut pandang lebar (sekitar 78 derajat atau lebih), autofokus lebih baik daripada fokus manual, dan colokan USB-A. Kabel webcam akan digulung di dalam kotak, jadi panjang kabel 1,4 sampai 2 m tidak masalah.

## 4. Apa dicolok ke mana: paket satu kabel

Tujuannya satu paket utuh: hanya satu kabel USB dari paket ke laptop, dan kamera serta indikator (ESP32) langsung berfungsi bersamaan.

```
Laptop --1 kabel USB--> [ KOTAK PAKET ]
                          hub USB (di dalam kotak)
                           +-- webcam (di atas kotak, kabelnya masuk ke dalam)
                           +-- ESP32 --> 3 LED (panel depan) + buzzer
```

Kamera tidak dicolok ke ESP32. Keduanya dicolok ke hub di dalam kotak, dan hub itu satu-satunya yang tersambung ke laptop. Aplikasi membaca kamera lewat USB dan mengirim perintah lampu serta buzzer ke ESP32 lewat USB serial, jadi tidak ada perubahan kode di aplikasi.

Untuk uji alat peraga sekarang (bagian 2), paketnya belum ada: pakai webcam laptop, dan ESP32 saja bila sudah ada.

Kamera dan ESP32 tidak bisa disatukan jadi satu perangkat tanpa mengubah desain. ESP32-CAM memang menggabungkan keduanya, tetapi kameranya jauh di bawah webcam 1080p untuk masker dan kacamata dari jarak 1,5 sampai 2 m, videonya lewat Wi-Fi (bukan USB), board dasarnya tidak punya port USB bawaan, dan aplikasi sekarang membaca kamera USB lewat `--camera` serta indikator lewat serial. Jadi kode, firmware, dan alur fail-safe (heartbeat serial, kondisi `FAULT`) harus diubah. Paket hub di dalam kotak memberi hasil yang sama (satu kabel) tanpa risiko itu.

## 5. Merakit

Panduan ini mengikuti desain indikator di README: tiga lampu (hijau, kuning, merah) dan satu buzzer. Buka dulu sketch di `firmware/esp32_indicator/` dan cocokkan. Kalau yang dipakai berbeda (misalnya LED RGB atau relay), jangan merakit dulu dan kirim sketch-nya ke chat.

### Pin yang dipakai

Pilih salah satu:

- A. Ikuti pin di sketch. Buka file `.ino` di `firmware/esp32_indicator/`, cari konstanta pin di bagian atas (`#define` atau `const int`), lalu rakit ke pin itu.
- B. Rakit di pin rekomendasi di bawah, lalu ubah konstanta pin di sketch supaya sama.

| Fungsi | Pin rekomendasi |
| --- | --- |
| LED hijau | GPIO 25 |
| LED kuning | GPIO 26 |
| LED merah | GPIO 27 |
| Buzzer (lewat transistor) | GPIO 14 |

Hindari GPIO 0, 2, 5, 12, dan 15 (pin boot, bisa mengganggu proses menyala), GPIO 1 dan 3 (dipakai USB serial ke aplikasi), GPIO 6 sampai 11 (terhubung ke flash), dan GPIO 34 sampai 39 (hanya input).

### Skema

```
GPIO 25 --[220 ohm]--(LED hijau)--+
GPIO 26 --[220 ohm]--(LED kuning)-+--> GND
GPIO 27 --[220 ohm]--(LED merah)--+
        kaki panjang LED menghadap resistor

5V (VIN) ---------------------+
                              |
                        [BUZZER aktif 5V]   plus (+) ke atas, minus (-) ke bawah
                              |
                              C
GPIO 14 --[1 kohm]-- B  [TRANSISTOR NPN]
                              E
                              |
                             GND
```

### Langkah merakit (USB belum dicolok)

1. Pasang ESP32 melintang di celah tengah breadboard, colokan USB menghadap tepi.
2. Hubungkan satu pin GND ESP32 ke rel biru (minus) breadboard, dan pin 5V (berlabel VIN) ke rel merah (plus).
3. LED: urutannya GPIO, resistor 220 Ω, LED, lalu rel GND. Kaki panjang LED (anoda) menghadap resistor, kaki pendek (sisi datar) ke GND.
4. Buzzer: kaki plus ke rel 5 V. Kaki minus ke kaki kolektor transistor.
5. Transistor: emitor ke rel GND. Basis ke pin GPIO buzzer lewat resistor 1 kΩ. Untuk BC547 dengan sisi datar menghadap kamu dan kaki ke bawah, urutan kiri ke kanan adalah kolektor, basis, emitor. Untuk S8050 urutannya emitor, basis, kolektor. Selalu cek lembar data tipe yang kamu beli.
6. Dioda (opsional): sejajar dengan buzzer, pita (katoda) ke rel 5 V dan ujung lainnya ke kolektor.
7. Periksa ulang: polaritas LED, urutan kaki transistor, dan tidak ada kabel yang menyambung 5 V langsung ke GND. Baru colok USB.

## 6. Uji rakitan

Uji ini memastikan LED dan buzzer benar sebelum memakai firmware proyek.

1. Pasang Arduino IDE 2.x. Di Boards Manager pasang paket "esp32" dari Espressif Systems.
2. Buat sketch baru, tempel kode di bawah, dan sesuaikan empat konstanta pin dengan rakitanmu.
3. Pilih Tools > Board > ESP32 Dev Module dan port COM ESP32, lalu Upload. Bila muncul "Connecting...", tahan tombol BOOT di board sampai unggahan mulai.
4. Hasil yang benar: LED hijau, kuning, merah menyala bergantian satu detik, lalu buzzer berbunyi tiga kali, berulang terus.

```cpp
// Uji rakitan SAFEWORK AI (tanpa aplikasi). Sesuaikan pin dengan rakitanmu.
const int PIN_HIJAU  = 25;
const int PIN_KUNING = 26;
const int PIN_MERAH  = 27;
const int PIN_BUZZER = 14;   // lewat transistor NPN: HIGH = bunyi

const int LED_PIN[] = {PIN_HIJAU, PIN_KUNING, PIN_MERAH};
const char* LED_NAMA[] = {"hijau", "kuning", "merah"};

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 3; i++) {
    pinMode(LED_PIN[i], OUTPUT);
    digitalWrite(LED_PIN[i], LOW);
  }
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  Serial.println("Uji rakitan dimulai");
}

void loop() {
  for (int i = 0; i < 3; i++) {
    Serial.printf("LED %s menyala\n", LED_NAMA[i]);
    digitalWrite(LED_PIN[i], HIGH);
    delay(1000);
    digitalWrite(LED_PIN[i], LOW);
    delay(300);
  }
  Serial.println("Buzzer berbunyi 3 kali");
  for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_BUZZER, HIGH);
    delay(200);
    digitalWrite(PIN_BUZZER, LOW);
    delay(200);
  }
  delay(1500);
}
```

## 7. Unggah firmware proyek

Buka sketch di `firmware/esp32_indicator/`, pastikan pinnya sama dengan rakitan, lalu Upload dengan langkah yang sama seperti bagian 6. Tutup Serial Monitor sebelum menjalankan aplikasi, karena satu port COM hanya bisa dipakai satu program.

## 8. Menyalakan aplikasi

### Cara satu perintah (disarankan)

Simpan `jalankan.py` sebagai `scripts/jalankan.py`. Peluncur ini mendeteksi ESP32 dan kamera otomatis, membuat token admin acak untuk sesi itu, lalu menjalankan aplikasi dengan opsi yang sesuai README.

1. Colok satu kabel dari paket ke laptop.
2. Buka PowerShell di folder proyek dan aktifkan environment: `.\.venv\Scripts\Activate.ps1`
3. Jalankan: `python scripts\jalankan.py`
4. Peluncur mencetak kamera dan port yang dipilih serta token admin. Catat token itu: dipakai untuk mengganti profil dan uji indikator di dashboard.
5. Buka `http://127.0.0.1:8000` di browser dan pilih profil.
6. Berdiri 1,5 sampai 2 m dari kamera dengan seluruh badan terlihat. Lampu dan buzzer di paket mengikuti hasil di dashboard.
7. Di dashboard, jalankan uji indikator dan pastikan hijau, kuning, merah, buzzer, dan kondisi `FAULT` sesuai yang diharapkan.

Opsi peluncur: `--dry-run` (hanya cetak perintah), `--camera N` dan `--serial COMx` (paksa pilihan), `--tanpa-indikator` (tanpa ESP32), `--debug`, dan `--weights lokasi\best.pt`.

Cara deteksi: ESP32 dikenali dari chip USB-serialnya (CP210x, CH340 atau CH9102, FTDI); bila ada beberapa, dipilih nomor COM tertinggi. Kamera yang dipilih adalah yang resolusinya terbesar, dan bila sama, yang nomornya lebih tinggi. Bila salah pilih, paksa dengan `--camera N`. Peluncur ini baru diuji dengan data tiruan, belum dengan perangkat asli.

### Cara manual (cadangan)

1. Cari nomor port ESP32 di Device Manager > Ports (COM & LPT), misalnya `COM5`. Kamera bawaan biasanya nomor `0`; webcam eksternal bisa `0` atau `1`.
2. Buka PowerShell di folder proyek, lalu aktifkan environment: `.\.venv\Scripts\Activate.ps1`
3. Atur token untuk sesi ini: `$env:SAFEWORK_ADMIN_TOKEN = "token-rahasia"`
4. Jalankan, sesuaikan nomor kamera dan port:

```
python -m safework --weights runs\ppe-v2-ft1\weights\best.pt --camera 0 --serial COM5 --roi "0.25,0,0.75,1" --debug
```

### Mematikan

1. Tekan `Ctrl+C` di PowerShell.
2. ESP32 yang tidak menerima heartbeat lebih dari 5 detik masuk kondisi aman sendiri. Setelah itu USB boleh dicabut. Untuk menguji kondisi aman, hentikan aplikasi lalu tunggu lebih dari 5 detik dan amati ESP32.

Cadangan demo: `python -m safework --fake` menjalankan dashboard simulasi tanpa webcam dan ESP32.

## 9. Mengemas jadi satu paket dan memasang di pos

Kerjakan setelah rakitan di breadboard lolos uji (bagian 6) dan aplikasi menyala (bagian 8).

1. Siapkan kotak: lubang untuk tiga LED di panel depan (dudukan LED 5 mm), celah untuk suara buzzer, satu lubang untuk kabel USB yang keluar ke laptop, dan satu lubang untuk kabel webcam yang masuk.
2. Tempel hub di dasar kotak dengan double tape atau velcro.
3. Pasang ESP32 beserta rangkaiannya di dalam kotak dengan double tape atau penyangga. Kencangkan kabel jumper atau solder ke papan perf; atau pakai papan terminal ESP32 supaya kabel tidak lepas saat kotak dipindah.
4. Colok ESP32 ke hub dengan kabel USB pendek.
5. Pasang webcam di atas kotak (penjepit atau tripod mini yang dilem atau dibaut). Masukkan kabelnya lewat lubang, colok ke hub, dan gulung sisa kabel di dalam kotak.
6. Keluarkan satu kabel dari hub ke laptop. Pasang penahan tarikan (cable tie di dalam kotak) supaya colokan tidak tertarik. Kalau kabelnya kurang panjang, pakai kabel ekstensi USB.
7. Letakkan kotak setinggi dada (meja atau tiang), webcam menghadap pekerja pada jarak 1,5 sampai 2 m dengan seluruh badan terlihat dan cahaya dari depan. Lampu menghadap pekerja, setinggi mata.
8. Uji satu kabel: cabut semuanya dari laptop, colok satu kabel dari paket, lalu jalankan `python scripts\jalankan.py`. Kamera dan indikator harus langsung berfungsi.

Tips: selalu pakai port hub yang sama dan beri label, serta hindari menutup lubang udara hub kalau kotaknya kecil.

## 10. Masalah umum

| Gejala | Penyebab atau tindakan |
| --- | --- |
| Port COM tidak muncul | Kabel USB hanya untuk charge, driver CP210x atau CH9102 belum terpasang, atau coba port USB lain |
| Board tidak menyala dengan kabel USB-C ke USB-C | Coba kabel USB-A ke USB-C |
| Upload macet di "Connecting..." | Tahan tombol BOOT saat unggah, atau ganti kabel dan port |
| LED tidak menyala | Polaritas LED terbalik, pin berbeda dari sketch, atau resistor tidak tersambung |
| Buzzer berbunyi terus atau tidak berbunyi | Kaki transistor tertukar, buzzer pasif (butuh sinyal nada), atau modul low level trigger yang logikanya terbalik |
| ESP32 tidak mau menyala saat rangkaian terpasang | Ada beban di pin boot (0, 2, 5, 12, 15) |
| Kamera tidak terbuka atau gambar hitam | Coba `--camera 1`, tambahkan `--camera-backend dshow`, dan tutup aplikasi lain yang memakai kamera (Zoom, Teams, Camera) |
| Status `FAULT` | Kamera terputus lebih dari 3 detik. Cek kabel dan hub, lalu colok ulang |
| Lampu dan buzzer tidak berubah | Pastikan `--serial COMx` benar dan Serial Monitor Arduino IDE sudah ditutup |
| Tidak bisa ganti profil atau uji indikator | Token belum diatur sebelum menjalankan aplikasi |
| FPS rendah | Turunkan `--fps 10` dan tutup aplikasi lain |
| Peluncur memilih kamera yang salah | Jalankan dengan `--camera 0` atau `--camera 1` |
| Peluncur tidak menemukan ESP32 | Cek kabel, hub, dan driver; atau pakai `--serial COMx` dari Device Manager |
| Port COM berubah setelah ganti port hub | Peluncur mendeteksinya lagi otomatis. Untuk cara manual, cek nomor port yang baru |

## 11. Yang belum ada

- README final dengan hasil `ppe-v2-ft1`. Teksnya menunggu hasil bagian 2.
- Panduan rakit yang pasti cocok dengan pin firmware. Menunggu isi `firmware/esp32_indicator/`.
- Melatih ulang model (hanya bila perlu, misalnya setelah menambah foto lokal): pakai `docs/notebooks/train_ppe_v2_colab.ipynb` dan ubah `RUN_TAG` untuk latihan baru.
- Peluncur `scripts/jalankan.py` dan seluruh paket satu kabel belum diuji dengan perangkat asli. Kirim hasilnya ke chat bila ada yang tidak sesuai.
