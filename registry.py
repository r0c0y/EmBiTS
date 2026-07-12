from fastapi import APIRouter, Form, HTTPException, Query, Security, Depends
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from database import get_db_connection
from audit_ledger import log_audit
import os

router = APIRouter()
ORIGINALS_DIR = os.path.join(os.path.dirname(__file__), "static", "originals")
os.makedirs(ORIGINALS_DIR, exist_ok=True)
security = HTTPBearer(auto_error=False)

async def require_auth(creds: HTTPAuthorizationCredentials = Security(security)):
    api_key = os.environ.get("SCL_API_KEY", "")
    if not api_key:
        return
    if not creds or creds.credentials != api_key:
        raise HTTPException(401, "Invalid or missing API key")

@router.get("/api/registry")
async def get_registry(limit: int = 50, offset: int = 0):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT project_id, COUNT(*) as doc_count, MAX(created_at) as last_updated FROM meetings GROUP BY project_id ORDER BY project_id LIMIT ? OFFSET ?", (limit, offset))
    projects = [dict(r) for r in c.fetchall()]
    c.execute("SELECT COUNT(DISTINCT project_id) FROM meetings WHERE project_id IS NOT NULL")
    total = c.fetchone()[0]
    conn.close()
    return {"projects": projects, "total": total, "limit": limit, "offset": offset}

@router.get("/api/registry/{project_id}/documents")
async def get_project_documents(project_id: str, sort: str = "date", source_type: str = None, title: str = None, date_from: str = None, date_to: str = None, limit: int = 50, offset: int = 0):
    conn = get_db_connection(); c = conn.cursor()
    sql = "SELECT id, title, date, lot_id, project_id, file_path, file_size_bytes, source_type, created_at, ocr_quality, corrections_count, uploaded_by FROM meetings WHERE project_id = ?"
    params = [project_id]
    if source_type == "image":
        placeholders = ",".join("?" * 7)
        sql += f" AND source_type IN ({placeholders})"
        params.extend(["png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp"])
    elif source_type:
        sql += " AND source_type = ?"; params.append(source_type)
    if title: sql += " AND title LIKE ?"; params.append(f"%{title}%")
    if date_from: sql += " AND date >= ?"; params.append(date_from)
    if date_to: sql += " AND date <= ?"; params.append(date_to)
    if sort == "date": sql += " ORDER BY date DESC"
    elif sort == "name": sql += " ORDER BY title ASC"
    elif sort == "size": sql += " ORDER BY file_size_bytes DESC"
    else: sql += " ORDER BY date DESC"
    sql += " LIMIT ? OFFSET ?"; params.extend([limit, offset])
    c.execute(sql, params)
    docs = [dict(r) for r in c.fetchall()]
    c.execute("SELECT COUNT(*) FROM meetings WHERE project_id = ?", (project_id,))
    total = c.fetchone()[0]
    conn.close()
    return {"documents": docs, "project_id": project_id, "total": total, "limit": limit, "offset": offset}

@router.get("/api/registry/{project_id}/activity")
async def get_project_activity(project_id: str):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id, title, date, created_at, source_type, corrections_count FROM meetings WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
    docs = [dict(r) for r in c.fetchall()]
    c.execute("SELECT timestamp, username, action_type, details FROM audit_logs WHERE details LIKE ? ORDER BY id DESC LIMIT 50", (f"%{project_id}%",))
    logs = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"documents": docs, "logs": logs}

@router.get("/api/ocr/{doc_id}")
async def get_ocr(doc_id: str):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id, title, transcript_text, source_type, file_path, file_size_bytes, created_at, ocr_quality, corrections_count FROM meetings WHERE id = ?", (doc_id,))
    row = c.fetchone(); conn.close()
    if not row: raise HTTPException(404, "Document not found")
    d = dict(row)
    original_url = None
    if d.get("file_path"):
        original_url = f"/static/originals/{doc_id}_{d['file_path']}"
    
    from ocr_storage import load_ocr_json
    base_dir = os.path.dirname(__file__)
    ocr_data = load_ocr_json(base_dir, doc_id)
    pages = ocr_data.get("pages", []) if ocr_data else []
    
    return {
        "doc_id": d["id"],
        "title": d["title"],
        "ocr_text": d["transcript_text"],
        "engine": d.get("ocr_quality", "auto"),
        "original_url": original_url,
        "created_at": d["created_at"],
        "file_size_bytes": d.get("file_size_bytes", 0),
        "corrections_count": d.get("corrections_count", 0),
        "pages": pages
    }



@router.get("/api/originals/{filename}")
async def get_original(filename: str):
    path = os.path.join(ORIGINALS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Original file not found")
    return FileResponse(path)
