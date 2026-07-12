"""Structured OCR storage.

Saves per-page OCR results with layout blocks, bboxes, and metadata
to a sidecar JSON file. Also writes a plain-text and Markdown version
for search and preview.

Layout:
  storage/
    originals/{doc_id}_{filename}      <- raw upload
    ocr/{doc_id}.json                  <- structured OCR blocks per page
    ocr/{doc_id}.md                    <- Markdown preview
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


def _ensure_dirs(base_dir: str):
    os.makedirs(os.path.join(base_dir, "storage", "ocr"), exist_ok=True)


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in text).strip().replace(" ", "_")


def store_ocr_result(
    base_dir: str,
    doc_id: str,
    filename: str,
    ocr_result: Any,  # OCRResult from ocr_engine
    engine_name: str,
    page_count: int,
    detected_date: Optional[str] = None,
) -> Dict[str, str]:
    """Write structured OCR data to disk and return paths + plain text."""
    _ensure_dirs(base_dir)

    pages = []
    for p in ocr_result.pages:
        pages.append({
            "page_num": p.page_num,
            "text": p.text,
            "markdown": p.markdown,
            "blocks": p.blocks,
            "metadata": p.metadata,
        })

    structured = {
        "doc_id": doc_id,
        "filename": filename,
        "engine": engine_name,
        "page_count": page_count,
        "created_at": datetime.now().isoformat(),
        "pages": pages,
    }

    json_path = os.path.join(base_dir, "storage", "ocr", f"{doc_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(structured, f, ensure_ascii=False, indent=2)

    # markdown preview (concatenate page markdowns)
    md = "\n\n".join(p.get("markdown", "") or p.get("text", "") for p in pages)
    md_path = os.path.join(base_dir, "storage", "ocr", f"{doc_id}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    # plain text for search/chunking
    plain = "\n\n".join(p.get("text", "") for p in pages)

    return {
        "text": plain,
        "ocr_json": json_path,
        "ocr_markdown": md_path,
        "ocr_engine": engine_name,
        "ocr_page_count": page_count,
        "ocr_quality": "high" if page_count > 1 else "single_page",
    }


def load_ocr_json(base_dir: str, doc_id: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(base_dir, "storage", "ocr", f"{doc_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
