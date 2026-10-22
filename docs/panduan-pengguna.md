# Panduan Pengguna Bibliomap

Panduan ini mengikuti satu alur kerja utuh: dari mengunduh data di basis
data pustaka sampai menghasilkan gambar peta dan tabel untuk manuskrip.

Bibliomap tidak membutuhkan R maupun Java. Semua berjalan di browser.

**Daftar isi**

1. [Menyiapkan data di basis data pustaka](#1-menyiapkan-data-di-basis-data-pustaka)
2. [Membuat workspace dan mengimpor](#2-membuat-workspace-dan-mengimpor)
3. [Meninjau duplikat](#3-meninjau-duplikat)
4. [Menerapkan filter](#4-menerapkan-filter)
5. [Membaca statistik](#5-membaca-statistik)
6. [Membuat peta ilmu pengetahuan](#6-membuat-peta-ilmu-pengetahuan)
7. [Mengekspor hasil](#7-mengekspor-hasil)
8. [Diagram PRISMA](#8-diagram-prisma)
9. [Masalah yang sering terjadi](#9-masalah-yang-sering-terjadi)
10. [Apa yang dilaporkan di bagian Metode](#10-apa-yang-dilaporkan-di-bagian-metode)

---

## 1. Menyiapkan data di basis data pustaka

Mutu analisis ditentukan oleh kelengkapan ekspor. Pilih opsi yang
menyertakan abstrak dan daftar referensi; tanpa referensi, jaringan
co-citation dan bibliographic coupling tidak bisa dibuat.

| Basis data | Langkah ekspor | Catatan |
| --- | --- | --- |
| Web of Science | Export → **Plain text file** atau **BibTeX**, pilih **Full Record and Cited References** | "Full Record" saja tidak memuat referensi |
| Scopus | Export → **CSV** atau **BibTeX**, centang **All information** | Tanpa ini, abstrak dan referensi kosong |
| PubMed | Send to → File → format **PubMed** | Menghasilkan berkas `.nbib` |
| Lens.org | Export → **CSV** | |
| OpenAlex | Tidak perlu diunduh: cari langsung dari dalam Bibliomap | |
| Zotero, Mendeley, EndNote | Export → **RIS** | |

Batas unduhan tiap basis data berbeda, biasanya 500–2.000 rekaman sekali
unduh. Unduh beberapa berkas lalu impor semuanya ke satu workspace;
Bibliomap menggabungkannya dan membuang duplikatnya.

> **Lisensi data.** Ekspor Scopus dan Web of Science terikat ketentuan
> langganan institusi Anda. Data tetap berada di workspace Anda sendiri dan
> Bibliomap tidak membagikannya.

---

## 2. Membuat workspace dan mengimpor

Workspace adalah wadah satu proyek tinjauan: berisi semua impor, keputusan
duplikat, dan filter Anda.

1. Buka Bibliomap. Workspace baru dibuat otomatis.
2. **Simpan tautan halamannya.** Alamatnya mengandung `?ws=...`, dan itulah
   satu-satunya cara membuka kembali workspace yang sama. Belum ada sistem
   akun, jadi siapa pun yang punya tautan itu bisa membukanya.
3. Di tab **Impor**, pilih berkas lalu klik **Impor**. Formatnya dideteksi
   otomatis dari isi berkas, bukan dari nama berkasnya.
4. Ulangi untuk setiap berkas.

### Mencari langsung di OpenAlex

OpenAlex adalah basis data terbuka berisi lebih dari 250 juta karya, bebas
dipakai tanpa langganan.

1. Di tab **Impor**, bagian **Cari di OpenAlex**, isi kata kunci. Query
   mendukung `AND`, `OR`, `NOT`, tanda kutip untuk frasa, dan tanda kurung.
   Contoh: `motorcycle AND (helmet OR "head injury")`.
2. Atur rentang tahun, jenis dokumen, dan bahasa bila perlu.
3. Klik **Hitung hasil** lebih dulu. Bibliomap menampilkan jumlah karya yang
   cocok dan perkiraan biayanya, sehingga Anda bisa mempersempit query
   sebelum mengimpor ribuan rekaman.
4. Klik **Impor**.

**URL query** yang ditampilkan sebaiknya Anda salin ke catatan. URL itulah
yang membuat pencarian Anda dapat diulang orang lain, dan layak dicantumkan
di bagian Metode.

### Memberi nama sumber

Berkas RIS dan BibTeX bisa berasal dari basis data mana pun, sehingga
Bibliomap memberinya nama berkas. Klik nama tersebut di daftar
**Sumber yang sudah diimpor** untuk menggantinya, misalnya menjadi
`Embase` atau `Scopus`. Nama ini yang muncul di diagram PRISMA.

---

## 3. Meninjau duplikat

Satu studi yang sama hampir selalu muncul di beberapa basis data. Bibliomap
menggabungkannya menjadi satu rekaman, dan rekaman gabungan itu mengambil
field terlengkap dari setiap salinan.

**Digabung otomatis** bila DOI-nya sama dan judulnya mirip, atau bila
judulnya hampir identik dengan tahun dan penulis pertama yang sama.

**Masuk antrean tinjauan** bila hasilnya meragukan:

| Situasi | Contoh |
| --- | --- |
| DOI sama, judul berbeda | Beberapa bab berbagi satu DOI buku |
| DOI berbeda, judul identik | Pracetak dan versi terbit, atau cetak ulang di jurnal lain |
| Judul mirip 92–98% | Beda ejaan, atau judul yang direvisi |
| Judul satu adalah awal judul lain | Satu basis data memotong subjudul |

Di tab **Duplikat**, kedua rekaman ditampilkan berdampingan dengan field
yang berbeda disorot. Tekan **D** untuk menandainya duplikat atau **N**
untuk bukan duplikat; tombolnya juga tersedia. Keputusan Anda selalu
mengalahkan aturan otomatis dan bisa dibatalkan.

> Pada pengujian dengan 1.165 rekaman nyata dari WoS, Scopus, dan PubMed,
> 443 duplikat tergabung tanpa satu pun kesalahan, dan hanya 10 pasangan
> yang perlu ditinjau manual.

---

## 4. Menerapkan filter

Tab **Filter & data** menyaring rekaman berdasarkan tahun, jenis dokumen,
bahasa, jumlah sitasi minimal, dan keharusan ada abstrak.

**Rekaman dengan nilai kosong tidak dibuang.** Rekaman tanpa tahun tidak
tersaring oleh filter tahun, karena membuang studi hanya karena satu basis
data tidak mengisi field akan mengubah hasil tinjauan Anda tanpa alasan.

Rekaman yang tersaring tidak dihapus. Semuanya tercatat di diagram PRISMA
sebagai "ditandai tidak layak oleh alat otomatis", lengkap dengan
alasannya, dan bisa dilihat di sub-tab **Tersaring**.

---

## 5. Membaca statistik

Tab **Statistik** dihitung dari rekaman yang lolos filter, setelah duplikat
digabung.

**Ringkasan** memuat jumlah dokumen, sumber, penulis, periode, pertumbuhan
tahunan, dan indeks kolaborasi.

**Peringkat** tersedia untuk sumber, penulis, afiliasi, negara, dan kata
kunci, masing-masing dengan:

- **h-index**: jumlah h karya yang masing-masing disitasi minimal h kali.
- **g-index**: selalu ≥ h-index, dan memberi bobot lebih pada karya yang
  sangat banyak disitasi.
- **m-index**: h-index dibagi jumlah tahun sejak publikasi pertama, sehingga
  peneliti muda bisa dibandingkan dengan yang sudah lama berkarier.

**Hukum Lotka** menggambarkan produktivitas penulis. Teorinya memperkirakan
proporsi penulis dengan n publikasi sebanding dengan 1/n^β, dengan β sekitar
2 di banyak bidang. Nilai R² yang tinggi berarti korpus Anda mengikuti pola
itu.

**Hukum Bradford** mengurutkan jurnal dari yang paling produktif lalu
membaginya menjadi tiga zona dengan jumlah artikel hampir sama. Zona 1
berisi jurnal inti bidang tersebut, biasanya hanya segelintir judul.

> Dokumen tanpa nama jurnal, misalnya buku, dikeluarkan dari analisis
> Bradford karena hukum ini membicarakan sebaran artikel di jurnal.
> Jumlahnya dilaporkan terpisah.

### Normalisasi nama

Nama penulis ditulis berbeda di tiap basis data: `Santoso, Budi`,
`Santoso B`, dan `Budi Santoso` dianggap orang yang sama. Kuncinya adalah
nama belakang ditambah seluruh inisial, sehingga `Lee SH` dan `Lee SJ`
tetap dibedakan sebagai dua orang.

Nama negara diambil dari daftar tertutup, sehingga nama kota atau negara
bagian tidak ikut terhitung sebagai negara.

---

## 6. Membuat peta ilmu pengetahuan

Di peta, node yang berdekatan berarti sering muncul bersama, dan warnanya
menandai klaster hasil algoritma Leiden.

### Memilih jenis jaringan

| Jenis | Menjawab pertanyaan | Unit yang tersedia |
| --- | --- | --- |
| Co-authorship | Siapa bekerja sama dengan siapa | Penulis, afiliasi, negara |
| Co-occurrence kata kunci | Tema apa yang dibahas bersamaan | Kata kunci penulis atau indeks |
| Sitasi langsung | Karya mana mengutip karya mana | Dokumen |
| Bibliographic coupling | Karya mana berbagi daftar pustaka; menunjukkan kedekatan **saat ini** | Dokumen, sumber, penulis, afiliasi, negara |
| Co-citation | Karya mana dikutip bersamaan; menunjukkan **fondasi intelektual** bidang | Referensi |

### Mengatur ambang

- **Minimal kemunculan**: naikkan bila peta terlalu padat. Untuk korpus
  beberapa ratus rekaman, nilai 5 biasanya pas untuk penulis dan kata kunci.
- **Normalisasi**: *Association strength* adalah yang dianjurkan dan menjadi
  bawaan. Nilai ini membandingkan kemunculan bersama yang teramati dengan
  yang diharapkan bila kaitannya acak, sehingga istilah yang sangat sering
  muncul tidak mendominasi peta.
- **Resolusi klaster**: naikkan untuk mendapat klaster lebih kecil dan lebih
  banyak; turunkan untuk klaster yang lebih besar.
- **Batas tautan digambar**: hanya memengaruhi gambar. Klaster dan tata
  letak tetap memakai seluruh tautan.

### Membaca peta

- Klik node untuk melihat jumlah dokumen, sitasi, dan kekuatan tautannya.
- Kolom **Cari node** menyorot node yang namanya cocok.
- Node yang berada jauh di tepi adalah item yang hampir tidak berkaitan
  dengan apa pun. Posisinya memang di pinggir, bukan kesalahan.
- Kelompok kecil yang terpisah dari gumpalan utama adalah komponen
  terputus, misalnya tim penulis yang tidak pernah menulis bersama
  kelompok lain.

Tata letaknya deterministik: data yang sama dengan pengaturan yang sama
selalu menghasilkan peta yang sama.

---

## 7. Mengekspor hasil

### Gambar peta

Tersedia di tab **Peta**, bagian **Ekspor peta**.

- **PNG** untuk disisipkan ke manuskrip atau salindia.
- **SVG** bila Anda ingin menyuntingnya di Illustrator atau Inkscape,
  misalnya memperbaiki posisi label.

Keduanya digambar ulang dari data peta pada resolusi 2000 × 1500 piksel,
jadi hasilnya tidak bergantung pada zoom layar Anda saat itu.

### Berkas jaringan

- **Berkas VOSviewer (.zip)**: berisi berkas map, network, dan warna
  klaster. Cara membukanya ada di dalam berkas `BACA-INI.txt`.
- **GraphML**: untuk Gephi atau Cytoscape.
- **Pajek (.net + .clu)**: jaringan beserta partisi klasternya.
- **CSV node dan tautan**: untuk diolah sendiri di Excel, R, atau Python.

### Data dan laporan

Tersedia di tab **Filter & data**.

- **Laporan Excel** berisi 11 lembar: ringkasan, produksi tahunan, lima
  tabel peringkat, hukum Lotka, hukum Bradford, angka PRISMA, dan seluruh
  rekaman.
- **Rekaman CSV** untuk diolah lebih lanjut.

Centang **Sertakan rekaman tersaring** bila Anda perlu melampirkan daftar
studi yang dikecualikan beserta alasannya.

---

## 8. Diagram PRISMA

Tab **PRISMA** mengisi diagram alir PRISMA 2020 secara otomatis dari impor,
deduplikasi, dan filter Anda. Klik **Unduh SVG** untuk menyimpannya.

Kotak bergaris putus-putus bertanda `n = …` adalah tahap skrining dan
kelayakan yang belum tersedia di versi ini. Isi angkanya sendiri setelah
Anda menyaring judul, abstrak, dan teks lengkap.

Bila masih ada pasangan duplikat yang belum ditinjau, diagram menampilkan
peringatan karena angkanya masih bisa berubah. Selesaikan antrean tinjauan
sebelum mengambil angka untuk manuskrip.

---

## 9. Masalah yang sering terjadi

**"Format file tidak dikenali."**
Berkasnya mungkin kosong, atau diekspor dalam format yang berbeda dari
yang Anda kira. Buka dengan editor teks dan periksa beberapa baris
pertama: ekspor WoS diawali `FN Clarivate`, PubMed diawali `PMID-`, RIS
diawali `TY  - `, dan BibTeX diawali `@article{`.

**Abstrak atau referensi kosong.**
Opsi ekspornya kurang lengkap. Ulangi ekspor dengan "Full Record and Cited
References" di WoS atau "All information" di Scopus.

**Kuota harian OpenAlex habis.**
Tanpa API key, semua pengguna dari satu alamat IP berbagi anggaran gratis
yang kecil. Buat key gratis di <https://openalex.org/settings/api>, lalu
isikan di kolom **API key OpenAlex**. Key itu hanya dipakai untuk
permintaan tersebut dan tidak disimpan.

**Peta terlihat seperti gumpalan padat.**
Naikkan **Minimal kemunculan** agar node berkurang, dan turunkan
**Batas tautan digambar**.

**Satu penulis mendominasi padahal seharusnya tidak.**
Periksa apakah dua orang berbeda tergabung. Bila ekspor Anda hanya memuat
inisial, `Lee S` bisa jadi beberapa orang. Ekspor ulang dengan nama lengkap
penulis bila basis datanya menyediakan.

**Workspace hilang.**
Workspace hanya bisa dibuka lewat tautan `?ws=...`. Periksa riwayat browser
Anda. Tanpa tautan itu, datanya tidak bisa diakses kembali.

---

## 10. Apa yang dilaporkan di bagian Metode

Agar tinjauan Anda dapat diulang orang lain, cantumkan:

1. **Basis data dan tanggal pencarian**, misalnya "Scopus dan Web of
   Science, dicari pada 22 Oktober 2026".
2. **String pencarian lengkap** untuk tiap basis data. Untuk OpenAlex,
   salin URL query yang ditampilkan Bibliomap.
3. **Jumlah rekaman** di tiap tahap, diambil dari diagram PRISMA.
4. **Cara deduplikasi**: "Duplikat digabungkan berdasarkan DOI dan
   pencocokan fuzzy judul, tahun, serta penulis pertama, dengan tinjauan
   manual untuk pasangan yang meragukan."
5. **Parameter peta**: jenis jaringan, unit analisis, ambang minimal
   kemunculan, metode normalisasi, dan resolusi klaster.
6. **Perangkat lunak**: "Bibliomap (versi), menggunakan algoritma Leiden
   untuk klasterisasi dan teknik VOS untuk tata letak."

Rujukan metode yang dipakai Bibliomap: Lotka (1926), Bradford (1934),
Hirsch (2005), Egghe (2006), Van Eck & Waltman (2009), Traag dkk. (2019),
dan Page dkk. (2021) untuk PRISMA 2020.
