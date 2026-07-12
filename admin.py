from fastapi import APIRouter, Request, Depends, Security, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from database import get_db_connection
import os

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
security = HTTPBearer(auto_error=False)

async def require_auth(creds: HTTPAuthorizationCredentials = Security(security)):
    api_key = os.environ.get("SCL_API_KEY", "")
    if not api_key:
        return
    if not creds or creds.credentials != api_key:
        raise HTTPException(401, "Invalid or missing API key")

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse(request, "admin.html")

@router.get("/admin/dashboard")
async def admin_dashboard_data(auth=Depends(require_auth)):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT COUNT(*) as total_docs FROM meetings")
    total_docs = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT project_id) as total_projects FROM meetings WHERE project_id IS NOT NULL")
    total_projects = c.fetchone()[0]
    c.execute("SELECT COUNT(*) as total_chunks FROM chunks")
    total_chunks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) as total_audits FROM audit_logs")
    total_audits = c.fetchone()[0]
    
    # Timeframe stats
    c.execute("SELECT COUNT(*) FROM meetings WHERE created_at >= datetime('now', '-7 days')")
    w_uploads = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM meetings WHERE created_at >= datetime('now', '-30 days')")
    m_uploads = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM meetings WHERE created_at >= datetime('now', '-365 days')")
    y_uploads = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM audit_logs WHERE timestamp >= datetime('now', '-7 days')")
    w_activity = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM audit_logs WHERE timestamp >= datetime('now', '-30 days')")
    m_activity = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM audit_logs WHERE timestamp >= datetime('now', '-365 days')")
    y_activity = c.fetchone()[0]
    
    c.execute("SELECT action_type, COUNT(*) as cnt FROM audit_logs GROUP BY action_type ORDER BY cnt DESC LIMIT 10")
    action_stats = [dict(r) for r in c.fetchall()]
    c.execute("SELECT project_id, COUNT(*) as cnt, MAX(created_at) as last FROM meetings GROUP BY project_id ORDER BY cnt DESC LIMIT 10")
    project_stats = [dict(r) for r in c.fetchall()]
    c.execute("SELECT source_type, COUNT(*) as cnt FROM meetings GROUP BY source_type ORDER BY cnt DESC")
    source_stats = [dict(r) for r in c.fetchall()]
    conn.close()
    
    return {
        "total_docs": total_docs, 
        "total_projects": total_projects, 
        "total_chunks": total_chunks, 
        "total_audits": total_audits, 
        "timeframe_stats": {
            "uploads": {"weekly": w_uploads, "monthly": m_uploads, "yearly": y_uploads},
            "activity": {"weekly": w_activity, "monthly": m_activity, "yearly": y_activity}
        },
        "action_stats": action_stats, 
        "project_stats": project_stats, 
        "source_stats": source_stats
    }

@router.get("/admin/audits")
async def admin_audits(limit: int = 100, offset: int = 0, auth=Depends(require_auth)):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM audit_logs")
    total = c.fetchone()[0]
    c.execute("SELECT timestamp, username, action_type, details, current_hash FROM audit_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
    logs = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"logs": logs, "total": total, "limit": limit, "offset": offset}

@router.get("/admin/documents")
async def admin_documents(limit: int = 50, offset: int = 0, project: str = None, auth=Depends(require_auth)):
    conn = get_db_connection(); c = conn.cursor()
    sql = "SELECT id, title, date, project_id, source_type, file_size_bytes, created_at FROM meetings"
    params = []
    if project: sql += " WHERE project_id = ?"; params.append(project)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"; params.extend([limit, offset])
    c.execute(sql, params)
    docs = [dict(r) for r in c.fetchall()]
    c.execute("SELECT COUNT(*) FROM meetings" + (" WHERE project_id = ?" if project else ""), params[:1] if project else [])
    total = c.fetchone()[0]
    conn.close()
    return {"documents": docs, "total": total, "limit": limit, "offset": offset}

@router.get("/admin/projects")
async def admin_projects(auth=Depends(require_auth)):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT project_id, COUNT(*) as doc_count, SUM(file_size_bytes) as total_size, MAX(created_at) as last_updated FROM meetings GROUP BY project_id ORDER BY project_id")
    projects = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"projects": projects}

@router.get("/admin/knowledge-map")
async def get_admin_knowledge_map(project: str = None, auth=Depends(require_auth)):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT DISTINCT project_id FROM meetings WHERE project_id != 'Unknown'")
    projects = [r[0] for r in c.fetchall() if r[0]]
    
    sql_docs = "SELECT id, title, project_id, date, lot_id FROM meetings"
    params = []
    if project:
        sql_docs += " WHERE project_id = ?"
        params.append(project)
    c.execute(sql_docs, params)
    docs = [dict(r) for r in c.fetchall()]
    
    doc_ids = [d["id"] for d in docs]
    decisions = []
    lineage = []
    if doc_ids:
        placeholders = ",".join("?" for _ in doc_ids)
        c.execute(f"SELECT id, meeting_id, summary, status, type FROM decisions WHERE meeting_id IN ({placeholders})", doc_ids)
        decisions = [dict(r) for r in c.fetchall()]
        
        c.execute(f"SELECT from_node_id, to_node_id, relation_type, rationale FROM lineage WHERE from_node_id IN ({placeholders}) OR to_node_id IN ({placeholders})", doc_ids + doc_ids)
        lineage = [dict(r) for r in c.fetchall()]
        
    conn.close()
    return {
        "projects": projects,
        "documents": docs,
        "decisions": decisions,
        "lineage": lineage
    }

@router.delete("/admin/projects/{project_id}")
async def delete_project(project_id: str, auth=Depends(require_auth)):
    conn = get_db_connection(); c = conn.cursor()
    # Select all documents in this project to delete files
    c.execute("SELECT id, file_path FROM meetings WHERE project_id = ?", (project_id,))
    rows = c.fetchall()
    for row in rows:
        doc_id = row["id"]
        filename = row["file_path"]
        # Delete original preview file
        if filename:
            orig_path = os.path.join(os.path.dirname(__file__), "static", "originals", f"{doc_id}_{filename}")
            if os.path.exists(orig_path):
                try: os.unlink(orig_path)
                except: pass
        # Delete ocr sidecars
        ocr_path_json = os.path.join(os.path.dirname(__file__), "storage", "ocr", f"{doc_id}.json")
        ocr_path_md = os.path.join(os.path.dirname(__file__), "storage", "ocr", f"{doc_id}.md")
        for ocr_p in [ocr_path_json, ocr_path_md]:
            if os.path.exists(ocr_p):
                try: os.unlink(ocr_p)
                except: pass
    # Delete chunk embeddings
    c.execute("DELETE FROM chunk_embeddings WHERE chunk_id IN (SELECT id FROM chunks WHERE meeting_id IN (SELECT id FROM meetings WHERE project_id = ?))", (project_id,))
    # Delete meetings row. Cascading foreign keys will delete chunks and decisions!
    c.execute("DELETE FROM meetings WHERE project_id = ?", (project_id,))
    conn.commit(); conn.close()
    return {"status": "success", "message": f"Project '{project_id}' deleted successfully."}

@router.delete("/admin/documents/{doc_id}")
async def delete_document(doc_id: str, auth=Depends(require_auth)):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT file_path, project_id FROM meetings WHERE id = ?", (doc_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Document not found")
    filename = row["file_path"]
    project_id = row["project_id"]
    
    # Delete original preview file
    if filename:
        orig_path = os.path.join(os.path.dirname(__file__), "static", "originals", f"{doc_id}_{filename}")
        if os.path.exists(orig_path):
            try: os.unlink(orig_path)
            except: pass
    # Delete ocr sidecars
    ocr_path_json = os.path.join(os.path.dirname(__file__), "storage", "ocr", f"{doc_id}.json")
    ocr_path_md = os.path.join(os.path.dirname(__file__), "storage", "ocr", f"{doc_id}.md")
    for ocr_p in [ocr_path_json, ocr_path_md]:
        if os.path.exists(ocr_p):
            try: os.unlink(ocr_p)
            except: pass
            
    # Delete chunk embeddings
    c.execute("DELETE FROM chunk_embeddings WHERE chunk_id IN (SELECT id FROM chunks WHERE meeting_id = ?)", (doc_id,))
    # Delete meetings row. Cascading foreign keys will delete chunks and decisions!
    c.execute("DELETE FROM meetings WHERE id = ?", (doc_id,))
    conn.commit(); conn.close()
    return {"status": "success", "message": f"Document '{doc_id}' in project '{project_id}' deleted successfully."}

@router.get("/admin/users")
async def get_admin_users(auth=Depends(require_auth)):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT email, name, role FROM users")
    rows = c.fetchall()
    conn.close()
    return {"users": [dict(r) for r in rows]}

@router.delete("/admin/users/{email}")
async def delete_admin_user(email: str, auth=Depends(require_auth)):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("DELETE FROM users WHERE email = ?", (email,))
    conn.commit(); conn.close()
    return {"status": "success", "message": f"User '{email}' deleted successfully."}

@router.post("/admin/users")
async def add_admin_user(user_data: dict, auth=Depends(require_auth)):
    import secrets, hashlib
    email = user_data.get("email", "").strip().lower()
    name = user_data.get("name", "").strip()
    password = user_data.get("password", "")
    role = user_data.get("role", "user")
    
    if not email or not name or not password:
        raise HTTPException(400, "All fields are required")
    if role not in ["admin", "user"]:
        raise HTTPException(400, "Invalid role")
        
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT email FROM users WHERE email = ?", (email,))
    if c.fetchone():
        conn.close()
        raise HTTPException(400, "User already exists")
        
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    
    c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (email, name, password_hash, salt, role))
    conn.commit(); conn.close()
    return {"status": "success", "message": f"User '{email}' added successfully."}

@router.put("/admin/users/{email}/role")
async def update_admin_user_role(email: str, role_data: dict, auth=Depends(require_auth)):
    role = role_data.get("role")
    if role not in ["admin", "user"]:
        raise HTTPException(400, "Invalid role")
    conn = get_db_connection(); c = conn.cursor()
    c.execute("UPDATE users SET role = ? WHERE email = ?", (role, email))
    conn.commit(); conn.close()
    return {"status": "success", "message": f"User '{email}' role updated to '{role}'."}
