# Bibliomap

Platform analisis bibliometrik dan pemetaan ilmu pengetahuan berbasis web:
statistik bibliometrik ala Biblioshiny dan peta jaringan ala VOSviewer dalam
satu alur.

Status: **Fase 1** (fondasi dan impor). Lihat spesifikasi produk untuk roadmap.

## Yang sudah ada

- Skema rekaman kanonik (`backend/src/bibliomap/schema.py`).
- Parser dengan deteksi format otomatis:

  | Sumber | Format ekspor | Catatan |
  | --- | --- | --- |
  | Web of Science | Plain text (tagged) | Penulis ditautkan ke afiliasi (C1) dan ORCID (OI) |
  | Scopus | CSV | Format penulis lama (`,`) dan baru (`;`) |
  | RIS | `.ris` | EndNote, Zotero, Mendeley, ekspor RIS Scopus/WoS |
  | PubMed | Format PubMed/MEDLINE (`.nbib`) | Afiliasi dan ORCID per penulis, halaman disingkat diperluas |

- API `POST /api/imports/preview` untuk mengunggah file dan melihat hasil parse.
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
    api/imports.py     endpoint impor
    main.py            aplikasi FastAPI
  tests/               tes + fixture sintetis per format
frontend/
  src/
    components/        ImportPanel, RecordTable
    locales/id.json    semua teks antarmuka (Bahasa Indonesia)
```

## Lisensi

[GNU AGPL-3.0-or-later](LICENSE). Algoritma jaringan akan memakai
[CWTS networkanalysis](https://github.com/CWTSLeiden/networkanalysis) (MIT).
Kode VOSviewer tidak digunakan.
