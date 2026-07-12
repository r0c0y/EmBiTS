import os, re, hashlib, io, tempfile
from datetime import datetime
from PIL import Image
import pdfplumber
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation
from ocr_engine import get_ocr_manager, OCRResult
from ocr_storage import store_ocr_result

EXTS = {".txt",".pdf",".docx",".xlsx",".xls",".pptx",".png",".jpg",".jpeg",".tiff",".bmp",".csv",".md",".json"}

_DATE_PATTERNS = [
    (r"\b(\d{4}-\d{2}-\d{2})\b", "%Y-%m-%d"),
    (r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})\b", None),
    (r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b", "%b %d, %Y"),
    (r"\b\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}\b", "%d %b %Y"),
]

def detect_date(text):
    text = text or ""
    for pat, fmt in _DATE_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            d = m.group(0) if fmt is None else m.group(1)
            for try_fmt in [fmt] if fmt else ["%d-%m-%Y","%m-%d-%Y","%d/%m/%Y","%m/%d/%Y"]:
                try:
                    return datetime.strptime(d, try_fmt).strftime("%Y-%m-%d")
                except: pass
    return None

def chunk_text(text, size=800, overlap=200):
    text = text or ""
    chunks, i = [], 0
    while i < len(text):
        chunks.append(text[i:i+size])
        i += size - overlap
        if i >= len(text): break
    return chunks or [""]

def content_hash(raw):
    return hashlib.sha256(raw).hexdigest()

def _extract_structured(f, ext):
    f.seek(0)
    if ext in (".txt",".csv",".md",".json"):
        return f.read().decode("utf-8", errors="ignore")
    if ext == ".docx":
        import zipfile
        doc = Document(f)
        parts = []
        for p in doc.paragraphs:
            if p.text.strip():
                parts.append(p.text)
        for table in doc.tables:
            if not table.rows:
                continue
            table_lines = []
            col_count = len(table.rows[0].cells)
            for r_idx, row in enumerate(table.rows):
                cells_text = [cell.text.replace("\n", " ").strip() for cell in row.cells]
                row_line = "| " + " | ".join(cells_text) + " |"
                table_lines.append(row_line)
                if r_idx == 0:
                    sep = "|" + "|".join("---" for _ in range(col_count)) + "|"
                    table_lines.append(sep)
            parts.append("\n" + "\n".join(table_lines) + "\n")
        try:
            f.seek(0)
            with zipfile.ZipFile(f) as z:
                media_files = [name for name in z.namelist() if name.startswith("word/media/")]
                if media_files:
                    mgr = get_ocr_manager()
                    for m_file in media_files:
                        img_data = z.read(m_file)
                        img = Image.open(io.BytesIO(img_data))
                        res = mgr.process_image(img)
                        if res.text.strip():
                            parts.append(f"\n[Embedded Image: {m_file.split('/')[-1]}]\n{res.text}")
        except Exception:
            pass
        return "\n".join(parts)
    if ext in (".xlsx",".xls"):
        wb = load_workbook(f, read_only=True, data_only=True)
        t = []
        for s in wb.worksheets:
            for r in s.iter_rows(values_only=True):
                row = " ".join(str(c) for c in r if c is not None)
                if row.strip(): t.append(row)
        return "\n".join(t)
    if ext == ".pptx":
        prs = Presentation(f)
        return "\n".join(sh.text for slide in prs.slides for sh in slide.shapes if hasattr(sh,"text") and sh.text.strip())
    return None

def _save_temp(file_obj, suffix):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        file_obj.seek(0)
        tmp.write(file_obj.read())
        tmp.close()
        return tmp.name
    except Exception:
        try: tmp.close()
        except: pass
        return None

def ingest(file_obj, filename, size=0, base_dir=None):
    base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in EXTS:
        raise ValueError(f"Unsupported format: {ext}")

    structured = _extract_structured(file_obj, ext)
    if structured is not None:
        doc_date = detect_date(structured)
        return {
            "text": structured,
            "detected_date": doc_date,
            "source_type": ext.lstrip("."),
            "meta": {"engine": "native"},
            "ocr_json": None,
            "ocr_markdown": None,
            "ocr_engine": "native",
            "page_count": 1,
        }

    mgr = get_ocr_manager()
    tmp_path = _save_temp(file_obj, ext)
    if not tmp_path:
        raise ValueError("Failed to save temporary file for OCR processing")

    try:
        ocr_result = mgr.process_with_fallback(tmp_path, ext)
    finally:
        try: os.unlink(tmp_path)
        except Exception: pass

    if not ocr_result.text.strip():
        raise ValueError("No text could be extracted by OCR engine")

    doc_date = detect_date(ocr_result.text)
    engine = ocr_result.engine or "unknown"
    page_count = ocr_result.metadata.get("page_count", len(ocr_result.pages))
    quality = "high" if page_count > 1 else "single_page"

    return {
        "text": ocr_result.text,
        "detected_date": doc_date,
        "source_type": ext.lstrip("."),
        "meta": {
            "engine": engine,
            "page_count": page_count,
            "pages": len(ocr_result.pages),
            "metadata": ocr_result.metadata,
        },
        "ocr_result": ocr_result,  # raw result for structured storage after doc_id is known
        "ocr_json": None,
        "ocr_markdown": None,
        "ocr_engine": engine,
        "page_count": page_count,
        "ocr_quality": quality,
    }
