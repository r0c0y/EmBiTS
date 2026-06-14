# ScribeLink Minimal Hosted Demo

This directory contains a lightweight, modular, and monochromatic version of the ScribeLink v1 application. It runs completely self-contained, utilizing a zero-dependency local keyword indexer in SQLite. It does not require any external LLM APIs or cloud tokens, making it safe to host publicly.

Every code file in this folder is strictly kept under 100 lines for maximum readability and architectural maintainability.

---

## Technical Stack
* **Backend**: FastAPI (Python 3.12+) & SQLite
* **Frontend**: Vanilla HTML5 (semantic `<details>` disclosures) and modern CSS (custom variables, Outfit typography, responsive grid)

---

## Getting Started

### 1. Prerequisites
Ensure you have Python 3.12+ installed, and install the lightweight server dependencies:
```bash
pip install fastapi uvicorn jinja2
```

### 2. Running the Local Server
From within the `hosted/` directory, run:
```bash
python3 main.py
```
Or run from the project root:
```bash
python3 -m uvicorn hosted.main:app --reload
```
Once started, the application will be accessible at:
👉 **http://127.0.0.1:8000**

---

## Monochromatic UI Features
* **Color System**: Monochromatic dark theme. Pure black background (`#000000`), dark gray card backgrounds (`#0a0a0a`), white text (`#ffffff`), and subtle gray borders (`#222222`).
* **Sliders Accent Exception**: A vibrant neon cyan slider thumb (`#00e5ff`) with glowing highlight shadows on hover.
* **Interactive Disclosures**: Native `<details>` and `<summary>` tags wrap matching citations, allowing text searchability inside closed blocks.

---

## Running Integration Tests
To run the automated endpoint validation tests:
```bash
cd hosted
python3 -m unittest verify_hosted.py
```
This tests server startup, project listing, search keyword matching, and document indexing logs.
