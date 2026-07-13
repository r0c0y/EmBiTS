# ScribeLink: Local Document Query Engine & Citation Lineage

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

ScribeLink is a **100% offline** document query engine and decision-trail workspace for air-gapped environments. It combines layout-aware OCR text extraction, form-aware chunking, hybrid keyword/semantic search (RRF with title-boost + length normalization), RAPTOR hierarchical summaries, LLM-powered question answering, an interactive knowledge graph, and a tamper-evident SHA-256 audit ledger.

Built for semiconductor fabrication environments where sensitive process documents must never leave the local network.

---

## Table of Contents

1. [Quickstart](#-quickstart)
2. [Architecture Overview](#-architecture-overview)
3. [Document Ingestion Pipeline](#️-document-ingestion-pipeline)
4. [Search & Retrieval Pipeline](#-search--retrieval-pipeline)
5. [OCR Engine](#-ocr-engine)
6. [Frontend Application](#-frontend-application)
7. [Admin Panel & Knowledge Map](#-admin-panel--knowledge-map)
8. [Database Schema](#-database-schema)
9. [Audit Ledger](#-audit-ledger)
10. [API Reference](#-api-reference)
11. [Configuration](#-configuration)
12. [Module Reference](#-module-reference)
13. [Troubleshooting](#-troubleshooting)
14. [Known Limitations](#-known-limitations)

---

## Quickstart

### Prerequisites

- **Python 3.11+**
- **Ollama** — [Install from ollama.com](https://ollama.com)
- System dependencies for OpenCV (Linux only):
  ```bash
  sudo apt install libgl1 libglib2.0-0 libgomp1 libxcb1
  ```

### 1. Clone & setup

```bash
git clone <repo-url> scribelink
cd scribelink/hosted
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Pull local AI models

```bash
ollama pull embeddinggemma:latest   # 768-dim embeddings
ollama pull gemma3:1b               # LLM generation
```

### 3. (Optional) Environment variables

Create `.env` file:

```bash
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=gemma3:1b
EMBEDDING_MODEL=embeddinggemma:latest

# Groq cloud fallback (optional)
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.1-8b-instant
USE_GROQ_FALLBACK=false

# API key for external auth (optional)
SCL_API_KEY=

# Dev mode: enable hot-reload (default: disabled)
SCL_RELOAD=true

# PostgreSQL (optional, default SQLite)
DATABASE_URL=
```

### 4. Run

```bash
python main.py
```

Open **http://localhost:8000** — sign up, first user becomes admin.

### Docker

```bash
docker build -t scribelink .
docker run -p 8000:8000 --network host scribelink
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              CLIENT TIER (Browser SPA)                   │
│  app.js (Auth/Search/Upload) │ admin.js (CRUD/Map)       │
│  utils.js (Viewer/Parser)    │ graph.js (Cytoscape)      │
└──────────────┬──────────────────────────────────────────┘
               │ HTTP
┌──────────────▼──────────────────────────────────────────┐
│            FASTAPI ROUTING TIER                          │
│  main.py (search, upload, auth, preview, translate)      │
│  admin.py (dashboard, users, knowledge-map, CRUD)        │
│  registry.py (document listing, OCR retrieval)           │
└──────┬──────────────────────┬───────────────────────────┘
       │ Upload                │ Query
┌──────▼──────────────┐ ┌─────▼───────────────────────────┐
│  INGESTION TIER      │ │  RETRIEVAL & AI TIER            │
│  ingestion.py        │ │  search_engine.py (RRF)         │
│  ocr_engine.py       │ │  search_helpers.py (token/ctx)  │
│  preprocess.py       │ │  vector_store.py                │
│  ocr_storage.py      │ │  embedder.py                    │
│  summarizer.py       │ │  llm_client.py                  │
│  conflict.py         │ │  rag.py                         │
└──────┬──────────────┘ └─────┬───────────────────────────┘
       │ Store                 │ Read
┌──────▼──────────────────────▼───────────────────────────┐
│              DATA TIER                                    │
│  SQLite (app.db - 10 tables + 2 FTS5 virtual)            │
│  storage/ocr/ (sidecar JSON + MD per document)            │
│  static/originals/ (preserved uploaded files)              │
│  audit_ledger.py (SHA-256 tamper-evident chain)           │
└──────────────────────────────────────────────────────────┘
```

### Core Data Flow

1. **User uploads** a file via the SPA dashboard
2. **FastAPI** receives it, SHA-256 hash + duplicate check, DB entry (`status: pending`), returns immediately
3. **Background task** runs `ingest()` → OCR/extraction → form-aware chunking → FTS5 + vector embeddings → RAPTOR summaries
4. **After completion:** `status: completed` + sidecar OCR storage + vector index + hierarchical summaries
5. **User searches** → meta-query detection OR hybrid RRF search (BM25 + vector cosine) with title-boost + length normalization → per-doc chunk max (3) → query-aware ordering → RAPTOR summaries per-source → LLM generates answer with `[SourceNumber]` citations
6. **Audit log** records every action in a SHA-256 chained ledger

---

## Document Ingestion Pipeline

### Step-by-step flow

```
Upload File
    │
    ├── File extension validated (.txt .pdf .docx .xlsx .xls .pptx .png .jpg .jpeg .tiff .bmp .csv .md .json)
    ├── SHA-256 hash computed; duplicate check by project_id
    ├── DB row created with status = "pending"
    ├── Temp file written to disk
    ├── Original copied to static/originals/{doc_id}_{filename}
    │
    └── Background process starts (returns immediately):
         │
         ├── ingestion.ingest() routes by extension:
         │   ├── .docx → python-docx text + tables (pipe-separated markdown) + embedded image OCR
         │   ├── .xlsx  → openpyxl sheet text extraction (markdown tables)
         │   ├── .pptx  → python-pptx shape text
         │   ├── .txt/.csv/.md/.json → direct UTF-8 read (ignoring errors)
         │   └── .pdf/.png/.jpg/.jpeg → OCR Manager with fallback chain
         │
         ├── OCR Manager process_with_fallback():
         │   ├── LiteParse [priority 110] → layout-aware parsing, multi-column
         │   ├── PyMuPDF [priority 100] → native text extraction (parallel pages)
         │   │   └── per-page garbled detection → fallback to Tesseract
         │   └── Tesseract [priority 90] → PP-OCRv5 ONNX models for scanned images
         │
         ├── Text cleaned (clean_shadow_text for double-rendered chars)
         ├── Form-aware chunking:
         │   ├── ≥3 "Field Name:" patterns AND <2400 chars → single chunk
         │   └── Otherwise: paragraph-boundary split → sentence split → 800-char sliding window, 200 overlap
         ├── Chunks inserted into `chunks` table (page-aware) + FTS5 auto-index
         ├── OCR sidecar saved: storage/ocr/{doc_id}.json + .md
         ├── Auto-edge generation (lineage.py)
         ├── Vector embeddings built (vector_store.py)
         ├── Hierarchical L1 + L2 summaries built (summarizer.py)
         └── status = "completed"
```

### Ingestion Statuses

| Status | Meaning |
|--------|---------|
| `pending` | File uploaded, processing not yet started |
| `completed` | Fully processed and indexed |
| `failed` | Error during processing (reason in `transcript_text`) |

---

## Search & Retrieval Pipeline

### Query flow

```
User Search Query
    │
    ├── Meta-query detection:
    │   └─ "list all documents" → direct SQL listing + LLM summary (bypasses hybrid search)
    │
    └── Hybrid Search (execute_trace):
         │
         ├── FTS5 BM25 Keyword Search
         │   ├── Query tokenized (stopwords removed, porter stemmer via FTS5)
         │   ├── SQLite FTS5 MATCH with bm25 scoring
         │   ├── Project/document/date filters applied
         │   ├── Top 30 results
         │   ├── Title fallback: if zero results, query document titles directly
         │   └── Post-process: title boost (+5/matched term) + length normalization (/ doc_len^0.3)
         │
         ├── Vector Semantic Search
         │   ├── Query embedded via Ollama (embeddinggemma:latest → 768-dim)
         │   ├── All candidate chunk_embeddings BLOBs loaded
         │   ├── Cosine similarity in Python (NumPy)
         │   └── Top 30 results
         │
         └── Reciprocal Rank Fusion (RRF)
              ├── Score = 1/(60 + rank) for each result set
              ├── Scores summed across FTS5 + Vector
              └── Top 15 results by combined score
    │
    ├── Context Building:
    │   ├── Sort chunks by _qscore (score×0.3 + query overlap×0.7)
    │   ├── Group by doc, max 3 chunks per doc
    │   ├── Sort docs by _max_qscore descending (most relevant first)
    │   ├── Fetch L1 hierarchical summaries per document
    │   └── Build prompt: summaries BEFORE chunk excerpts per source
    │
    ├── LLM Generation:
    │   ├── System prompt: [SourceNumber] citations, no HTML/raw IDs, markdown only
    │   ├── Output: <concise> (synthesis) + <elaborate> (deep-dive) XML tags
    │   ├── Primary: Ollama gemma3:1b (120s timeout)
    │   ├── Fallback: Groq llama-3.1-8b-instant (if USE_GROQ_FALLBACK=true)
    │   └── Post-processing: auto-repair missing XML tags
    │
    ├── Parameter Conflict Detection:
    │   ├── Regex patterns: M1/M2 width/spacing/thickness, Gate Oxide, Wafer Sort Yield
    │   └── Flags docs with different values for same parameter
    │
    ├── Graph Generation:
    │   ├── Nodes: documents involved in query
    │   ├── Edges with labels: shared query terms / same project / same lot
    │   └── Decisions: linked decisions (schema only)
    │
    └── Response: {answer, citations, graph, conflicts}
```

### Search Response Structure

```json
{
  "answer": "<concise>Detail here</concise><elaborate>Deep analysis here</elaborate>",
  "citations": [
    {
      "meeting_id": "DOC-XXXXXXXX",
      "meeting_title": "Document Name",
      "date": "2025-03-15",
      "lot_id": "LOT-2025-03-ABCD",
      "department": "project_name",
      "text": "[Document: Title] chunk excerpt...",
      "page_number": 3,
      "confidence": 0.89
    }
  ],
  "graph": {
    "nodes": [{"id": "...", "title": "...", "department": "...", "highlight": true}],
    "edges": [{"source": "...", "target": "...", "type": "query_context", "label": "shared_term", "rationale": "..."}],
    "decisions": []
  },
  "conflicts": [{"parameter": "M1 Min Width", "values": [{"value": "0.18", "doc_id": "...", "title": "...", "snippet": "..."}, {"value": "0.13", ...}]}]
}
```

---

## OCR Engine

### Multi-Engine Fallback Chain

| Engine | Priority | Use Case |
|--------|----------|----------|
| **LiteParse** | 110 | Multi-column layout, tables, reading order; first choice |
| **PyMuPDF** | 100 | Native PDF text layer; parallel page processing (ThreadPoolExecutor, up to 8 workers) |
| **Tesseract** | 90 | Scanned images, final fallback for garbled pages |

The `OCRManager.process_with_fallback()` iterates engines in priority order. Per-page garbled text detection (`is_text_garbled()`) triggers intra-document fallback: a single garbled page in a LiteParse PDF is re-routed to PyMuPDF, then Tesseract, while clean pages stay with the faster engine.

### Garbled Text Detection Heuristics

1. **Empty text**: <10 chars
2. **Unicode replacement**: `\ufffd` present
3. **Short word length**: <200 chars AND avg word length <2.0
4. **Alpha ratio**: <40% alphabetic chars in line
5. **Allowed char ratio**: <75% alphanumeric/whitespace/common symbols in line
6. **Threshold**: >20% of lines garbled → whole page garbled

### Shadow Text Cleaning (`clean_shadow_text()`)

Post-processing function that detects and compresses double-rendered characters (e.g. `GRROOUUPP` → `GROUP`). Applied when ≥75% of a word's characters are consecutively duplicated.

### Preprocessing Pipeline (`preprocess.py`)

1. **Alpha Blending** — RGBA → white background
2. **Grayscale** — single-channel conversion
3. **Deskew** — rotation correction via `cv2.minAreaRect`
4. **Bilateral Filtering** — noise reduction preserving edges
5. **Adaptive Binarization** — Gaussian threshold to high-contrast binary
6. **Median Blur** — salt-and-pepper removal

### Sidecar Storage

After OCR, results are persisted to:
- `storage/ocr/{doc_id}.json` — per-page blocks with bounding boxes, sorted by reading order
- `storage/ocr/{doc_id}.md` — full markdown for preview

---

## Frontend Application

### Files

| File | Lines | Role |
|------|-------|------|
| `static/js/app.js` | ~1150 | Workspace controller: auth, search, upload, registry, viewer |
| `static/js/admin.js` | ~600 | Admin panel: dashboard, CRUD, knowledge map |
| `static/js/utils.js` | ~350 | Shared rendering: markdown parser, viewer, audits, citations |
| `static/js/layout.js` | ~150 | Panel layout, resize, maximize |
| `static/js/graph.js` | ~200 | Cytoscape.js graph rendering with edge labels |
| `static/css/styles.css` | ~200 | Theme styles |

### Key Features

| Feature | Implementation |
|---------|---------------|
| **Auth** | Signup/signin with salted SHA-256, localStorage session, first user = admin |
| **Search** | POST to `/api/search`, renders LLM answer with `[SourceNumber]` citation tooltips and hover preview |
| **Smart Multi-Select** | Cascading project → document checkboxes (OR logic) |
| **Upload** | Drag-drop + parallel XHR with progress rings (CSS conic), polling at 1.5s |
| **Viewer** | Original mode (PDF/DOCX/TXT iframe) | OCR mode (A4 paper pages, markdown) |
| **Translation** | English → Hindi via Ollama, Devanagari script, cached per string |
| **History** | Per-user search history (localStorage, max 5 entries) |
| **Markdown Parser** | Multi-pass: KaTeX → Mermaid → SVG bar charts → `marked.parse()` |
| **Graph Edge Labels** | Cytoscape autorotate labels showing shared query terms/project/lot |

### Sidebar Navigation

| Icon | Tab | Content |
|------|-----|---------|
| Search | Search & Trace | Query form, AI summary, graph, citations, conflicts |
| Upload | Ingest | File upload with progress queue |
| Database | Registry | Project listing with document browser |
| Shield | Audits | Compliance audit trail table |
| Settings | Admin | Admin panel (admin-only) |
| Book | Docs | System documentation (admin-only) |

---

## Admin Panel & Knowledge Map

### Sections

| Section | Purpose |
|---------|---------|
| **Dashboard** | Stats + timeframe trends (weekly/monthly/yearly) with SVG bar charts |
| **Audits** | Paginated tamper-evident audit log (limit/offset) |
| **Documents** | All docs with project filter + cascade delete (sidecars, embeddings, lineage, summaries) |
| **Projects** | Project list with doc count, total size, last updated + cascade delete |
| **Users** | User directory, add/delete, role management (admin/user) |
| **Knowledge Map** | Interactive Cytoscape graph (projects, documents, lineage edges) |

### Knowledge Map

| Node Type | Color | Double-click |
|-----------|-------|-------------|
| Project | Blue border | — |
| Document | Green border | Opens viewer |
| Decision | Amber border | — |

| Edge Type | Color | Meaning |
|-----------|-------|---------|
| `project_to_doc` | Blue | Belongs to project |
| `doc_to_dec` | Amber | Associated decision |
| `lineage` | Red dashed | References another doc |

---

## Database Schema

### Tables

| Table | Rows | Key Details |
|-------|------|-------------|
| `meetings` | 1 per doc | 20 cols. `status`: pending/completed/failed. `content_hash`: SHA-256 dedup. `lot_id`: LOT-{YYYY-MM}-{last4}. |
| `chunks` | ~10 per doc | 800-char windows, 200 overlap. `page_number` tracking. FTS5 auto-sync via 3 triggers. |
| `chunks_fts` | Virtual | FTS5 with `porter unicode61` on `chunk_text`. Content-synced. |
| `chunk_embeddings` | 1 per chunk | `vector` BLOB: 768×float32 = 3072 bytes. |
| `decisions` | Schema only | Roadmap: summary, status, type columns. |
| `lineage` | 1 per edge | Composite PK. Types: reference/derived/supersedes. |
| `hierarchical_summaries` | 1 per doc + 1 per project | L1 (doc-level) + L2 (project-level). FTS5 indexed. |
| `hierarchical_summaries_fts` | Virtual | FTS5 on `summary_text`. 3 auto-sync triggers. |
| `audit_logs` | 1 per action | SHA-256 chained: parent_hash → current_hash chain. |
| `users` | 1 per user | SHA-256 with 32-byte salt. First user = admin. |

### Performance Indexes

```sql
CREATE INDEX idx_meetings_project ON meetings(project_id);
CREATE INDEX idx_meetings_status ON meetings(status);
CREATE INDEX idx_meetings_created ON meetings(created_at);
CREATE INDEX idx_chunks_meeting ON chunks(meeting_id);
```

---

## Audit Ledger

Each audit entry is cryptographically chained:

```
SHA-256(timestamp + username + department + action_type + details + parent_hash)
```

- **Genesis block:** Uses `"GENESIS"` as `parent_hash`
- **Chaining:** Each entry's `parent_hash` = previous entry's `current_hash`
- **Verification:** Iterates all entries → recalculates hashes → confirms chain integrity

Audit triggers: `SIGNUP`, `SIGNIN`, `QUERY`, `UPLOAD`, `OCR_CORRECT`.

---

## API Reference

### Search & Documents

| Method | Path | Auth | Params | Response |
|--------|------|------|--------|----------|
| POST | `/api/search` | — | Form: query, project, document, date_from, date_to, user, user_dept | `{answer, citations, graph, conflicts}` |
| POST | `/api/upload` | — | Form: file, project_id, user, user_dept | `{status, document_id, state}` |
| GET | `/api/document/{id}` | — | — | Document metadata JSON (16 cols) |
| GET | `/api/preview/{id}` | — | — | HTML/FileResponse for inline viewing |
| GET | `/api/download/{id}` | — | — | Attachment download |
| GET | `/api/ocr/{id}` | — | — | `{doc_id, title, engine, pages[{markdown, text, blocks}]}` |
| GET | `/api/originals/{filename}` | — | — | Static file from `static/originals/` |
| GET | `/api/documents` | — | `project` (comma-sep) | `{documents: [{id, title, project_id}]}` |

### Registry

| Method | Path | Params | Response |
|--------|------|--------|----------|
| GET | `/api/registry` | limit, offset | `{projects: [{project_id, doc_count, last_updated}], total}` |
| GET | `/api/registry/{project}/documents` | sort, source_type, title, date_from, date_to, limit, offset | `{documents: [...], total}` |
| GET | `/api/registry/{project}/activity` | — | `{documents: [...], logs: [...]}` |
| GET | `/api/projects` | — | `{projects: [{id, name, description}], lots: [{id, name, date}]}` |

### Auth

| Method | Path | Params | Response |
|--------|------|--------|----------|
| POST | `/api/auth/signup` | Form: email, name, password | `{status, user: {name, email, role}}` |
| POST | `/api/auth/signin` | Form: email, password | `{status, user: {name, email, role}}` |

### Admin

| Method | Path | Params | Response |
|--------|------|--------|----------|
| GET | `/admin/dashboard` | — | Stats + timeframe + action/project/source distribution |
| GET | `/admin/audits` | limit, offset | Paginated audit logs |
| GET | `/admin/documents` | limit, offset, project | Paginated document list |
| GET | `/admin/projects` | — | Project aggregate stats |
| GET | `/admin/knowledge-map` | project | `{projects, documents, decisions, lineage}` |
| DELETE | `/admin/projects/{id}` | — | Cascade delete (docs + sidecars + embeddings + lineage) |
| DELETE | `/admin/documents/{id}` | — | Cascade delete (sidecar + embeddings + lineage + summary) |
| GET | `/admin/users` | — | `{users: [{email, name, role}]}` |
| POST | `/admin/users` | JSON | Add user (email, name, password, role) |
| DELETE | `/admin/users/{email}` | — | Delete user |
| PUT | `/admin/users/{email}/role` | JSON | Update role (admin/user) |

### Lineage

| Method | Path | Params | Response |
|--------|------|--------|----------|
| POST | `/api/lineage/create` | Form: from_node_id, to_node_id, relation_type, rationale, user, user_dept | `{status: "created"}` |
| POST | `/api/lineage/delete` | Form: from_node_id, to_node_id, user, user_dept | `{status: "deleted"}` |

### Translation

| Method | Path | Auth | Params | Response |
|--------|------|------|--------|----------|
| POST | `/api/translate` | — | JSON: {text, target_lang: "Hindi"} | `{status, translated_text}` |

### Health

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | `{status: "ok", documents: N, chunks: N}` |
| GET | `/api/audit_logs` | Last 50 audit entries (newest first) |
| POST | `/api/audit_logs/verify` | Chain integrity check → `{valid, count}` |

---

## Configuration

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | No | Ollama server endpoint |
| `LLM_MODEL` | `gemma3:1b` | No | LLM generation model |
| `EMBEDDING_MODEL` | `embeddinggemma:latest` | No | Embedding model (768-dim) |
| `GROQ_API_KEY` | `""` | If fallback enabled | Groq API key |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | No | Groq model name |
| `USE_GROQ_FALLBACK` | `false` | No | Enable Groq cloud fallback |
| `DATABASE_URL` | `""` | No | PostgreSQL connection string |
| `SCL_API_KEY` | `""` | No | Bearer token for API auth |
| `SCL_RELOAD` | `false` | No | Set `true` for uvicorn hot-reload in dev |

---

## Module Reference

| File | Lines | Responsibility |
|------|-------|----------------|
| `main.py` | 510 | FastAPI app, all core routes |
| `admin.py` | 256 | Admin panel API |
| `registry.py` | 101 | Document registry + OCR retrieval |
| `database.py` | 72 | DB init + schema migration + indexes |
| `db_adapter.py` | 57 | SQLite/PostgreSQL adapter |
| `ingestion.py` | ~200 | File parsing + form-aware chunking |
| `ocr_engine.py` | ~350 | Multi-engine OCR (LiteParse/PyMuPDF/Tesseract) |
| `ocr_storage.py` | 90 | Sidecar JSON+MD persistence |
| `preprocess.py` | 80 | Image preprocessing pipeline |
| `search_engine.py` | ~280 | RRF search + title-boost + query-aware context + fallback |
| `search_helpers.py` | 87 | Tokenizer, context builder, graph with edge labels |
| `vector_store.py` | ~100 | SQLite vector storage + cosine similarity |
| `embedder.py` | ~30 | Ollama embedding client |
| `llm_client.py` | 80 | Ollama + Groq LLM proxy (120s timeout) |
| `ollama_runner.py` | ~50 | Self-healing Ollama process manager |
| `rag.py` | 4 | Prompt templates |
| `summarizer.py` | ~120 | RAPTOR hierarchical L1+L2 summaries |
| `conflict.py` | ~100 | Semiconductor parameter conflict detection |
| `lineage.py` | ~80 | Document relationship edge generation |
| `audit_ledger.py` | ~80 | SHA-256 chained tamper-evident ledger |
| `config.py` | 13 | Environment + model configuration |

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Ollama connection refused | Ollama not running | `ollama serve` or let auto-start via `ollama_runner.py` |
| Server exits immediately | Port 8000 in use | Kill existing process or change port in `main.py` |
| Auto-reload causes constant restart | `SCL_RELOAD=true` in production | Set `SCL_RELOAD=false` (default) |
| OCR returns empty | Missing system libs (Linux) | `sudo apt install libgl1 libglib2.0-0 libgomp1` |
| Upload stays `pending` | File too large or format issue | Check background task logs; serial processing |
| Search returns "No relevant text" | No embeddings built yet | Wait for background processing; check `status` |
| Hindi translation is Hinglish | Small model (`gemma3:1b`) | Upgrade to `gemma3:4b` or `qwen2.5:3b` |
| DB locked errors | Concurrent writes | Serial upload; reduce batch size |
| Groq fallback not working | `GROQ_API_KEY` not set | Set env var or disable `USE_GROQ_FALLBACK` |

---

## Known Limitations

- **CPU-only by default** — no GPU acceleration for OCR or embeddings
- **No tenant isolation** — single-user workspace with basic auth
- **Scalability cap** — RRF computes cosine similarity in Python for all chunks; not suitable for 100k+ documents
- **Decisions table** — schema exists but auto-population is roadmap
- **Language support** — translation is English → Hindi only
- **No HTTPS/TLS** — intended for local network; use a reverse proxy (nginx/caddy) for production
- **Small LLM** — `gemma3:1b` struggles with complex multi-document synthesis and clean Hindi output

---

## Offline / Air-Gapped Deployment

1. On an internet-connected machine, download:
   - Repository zip
   - All Python wheels (`pip download -r requirements.txt -d wheels/`)
   - Ollama models: `embeddinggemma` and `gemma3:1b`
   - ONNX OCR weights (in `models/ocr/`)
2. Transfer via USB to the air-gapped machine
3. Install with offline scripts
4. Run `python main.py`

---

## License

MIT