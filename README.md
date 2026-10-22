# Bibliomap

Platform analisis bibliometrik dan pemetaan ilmu pengetahuan berbasis web:
statistik bibliometrik ala Biblioshiny dan peta jaringan ala VOSviewer dalam
satu alur.

Status: **Fase 3** (statistik dan peta ilmu pengetahuan). Lihat spesifikasi produk untuk roadmap.

## Yang sudah ada

- Skema rekaman kanonik (`backend/src/bibliomap/schema.py`).
- Parser dengan deteksi format otomatis:

  | Sumber | Format ekspor | Catatan |
  | --- | --- | --- |
  | Web of Science | Plain text (tagged) | Penulis ditautkan ke afiliasi (C1) dan ORCID (OI) |
  | Scopus | CSV | Format penulis lama (`,`) dan baru (`;`) |
  | RIS | `.ris` | EndNote, Zotero, Mendeley, EMBASE, ScienceDirect, ekspor RIS Scopus/WoS |
  | PubMed | Format PubMed/MEDLINE (`.nbib`) | Afiliasi dan ORCID per penulis, halaman disingkat diperluas |
  | WoS, Scopus, Zotero, dll. | BibTeX (`.bib`) | Semantik field per eksportir, aksen LaTeX, `@string` |
  | Lens.org | CSV | Referensi sebagai Lens ID, Fields of Study + MeSH |
  | OpenAlex (web) | CSV | Kolom bertitik, nilai ganda dipisah `\|` |

- Pencarian dan impor langsung dari [OpenAlex](https://openalex.org) dengan query
  builder (kata kunci boolean, rentang tahun, jenis dokumen, bahasa, akses terbuka).

- **Workspace** (disimpan di SQLite): gabungkan beberapa impor, tinjau duplikat,
  terapkan filter, dan hasilkan diagram PRISMA 2020.
- **Deduplikasi**: DOI sama digabung otomatis; judul mirip dicocokkan dengan
  fuzzy match (judul, tahun, penulis pertama). Pasangan yang meragukan masuk
  antrean tinjauan manual, dan keputusan Anda selalu mengalahkan aturan otomatis.
- **Filter otomatis**: tahun, jenis dokumen, bahasa, jumlah sitasi, wajib abstrak.
  Rekaman dengan nilai kosong tidak dibuang.
- **PRISMA 2020**: terisi otomatis dari impor, dedup, dan filter; dapat diunduh
  sebagai SVG.
- **Statistik bibliometrik**: ringkasan deskriptif, produksi tahunan, peringkat
  sumber/penulis/afiliasi/negara/kata kunci dengan h-, g-, dan m-index, hukum
  Lotka, dan zona Bradford.
- **Peta ilmu pengetahuan**: lima jenis jaringan (co-authorship, co-occurrence,
  sitasi langsung, bibliographic coupling, co-citation), normalisasi association
  strength, klaster Leiden, tata letak VOS, dirender WebGL.

### Verifikasi terhadap bibliometrix

Metrik dibandingkan langsung dengan bibliometrix 5.5.0 pada file ekspor yang sama
(210 rekaman Scopus). Dokumen, penulis tunggal, rentang tahun, dan total sitasi
cocok persis; rata-rata sitasi, penulis per dokumen, dan indeks kolaborasi cocok
sampai pembulatan dua desimal.

| Metrik | Selisih | Penyebab |
| --- | --- | --- |
| Jumlah sumber | −0,70% | Nama jurnal dinormalisasi, sehingga dua ejaan digabung |
| Jumlah penulis | +0,28% | Nama penulis dinormalisasi lintas basis data |
| Eksponen Lotka | 0% pada input identik | Rumus sama; selisih hanya turunan normalisasi penulis |
| Zona Bradford | 0% pada input identik | bibliometrix menghitung 21 buku tanpa jurnal sebagai satu "sumber" kosong |

Peta 5.000 node dirender pada ~65 fps (dibatasi laju penyegaran layar).

### API

| Endpoint | Fungsi |
| --- | --- |
| `POST /api/imports/preview` | Pratinjau parse tanpa menyimpan |
| `POST /api/openalex/count` dan `/import` | Hitung dan ambil hasil OpenAlex |
| `POST /api/workspaces` | Buat workspace |
| `POST /api/workspaces/{id}/imports/file` dan `/openalex` | Tambah sumber data |
| `GET /api/workspaces/{id}/dedup/pending` | Antrean tinjauan duplikat |
| `POST /api/workspaces/{id}/dedup/decisions` | Simpan keputusan duplikat |
| `PUT /api/workspaces/{id}/filters` | Terapkan filter |
| `GET /api/workspaces/{id}/prisma` | Angka diagram PRISMA |
| `GET /api/workspaces/{id}/analysis/statistics` | Statistik deskriptif dan hukum bibliometrik |
| `POST /api/workspaces/{id}/analysis/map` | Bangun jaringan, klaster, dan tata letak |
- Antarmuka web berbahasa Indonesia untuk pratinjau impor.

## Menjalankan secara lokal

Prasyarat: [uv](https://docs.astral.sh/uv/) dan Node.js 24+.

```bash
cd backend
uv sync
uv run uvicorn bibliomap.main:app --reload --port 8000
```

Di terminal lain:

```bash
cd frontend
npm install
npm run dev
```

Buka http://localhost:5173. Vite meneruskan `/api` ke backend di port 8000.

### Konfigurasi OpenAlex

OpenAlex membebankan biaya per permintaan terhadap anggaran harian. Tanpa API key,
semua permintaan dari satu alamat IP berbagi anggaran gratis yang kecil, jadi
deployment publik wajib memakai key (gratis di https://openalex.org/settings/api).

| Variabel | Fungsi |
| --- | --- |
| `BIBLIOMAP_OPENALEX_API_KEY` | API key server; pengguna tetap bisa memakai key sendiri per permintaan |
| `BIBLIOMAP_OPENALEX_MAILTO` | Email kontak yang dikirim ke OpenAlex |
| `BIBLIOMAP_DB_PATH` | Lokasi basis data SQLite (default `data/bibliomap.sqlite3`) |

## Tes dan pemeriksaan

```bash
cd backend && uv run pytest && uv run ruff check . && uv run mypy src
cd frontend && npm test && npm run lint && npm run build
```

## Struktur

```text
backend/
  src/bibliomap/
    schema.py          skema rekaman kanonik
    parsers/           parser per format + deteksi otomatis
    analysis/          entitas, metrik, jaringan, Leiden + tata letak VOS
    workspace/         dedup, merge, filter, PRISMA, penyimpanan SQLite
    api/               endpoint impor, OpenAlex, workspace
    main.py            aplikasi FastAPI
  tests/               tes + fixture sintetis per format
frontend/
  src/
    components/        ImportPanel, RecordTable
    locales/id.json    semua teks antarmuka (Bahasa Indonesia)
```

## Rujukan metode

Lotka (1926), Bradford (1934), Hirsch (2005), Egghe (2006), Van Eck & Waltman
(2009, association strength dan tata letak VOS), Traag dkk. (2019, algoritma
Leiden). Tata letak ditulis dari fungsi objektif yang dipublikasikan, bukan dari
kode VOSviewer.

## Lisensi

[GNU AGPL-3.0-or-later](LICENSE). Algoritma jaringan akan memakai
[CWTS networkanalysis](https://github.com/CWTSLeiden/networkanalysis) (MIT).
Kode VOSviewer tidak digunakan.
