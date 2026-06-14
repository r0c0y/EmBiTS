import os
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import get_db_connection, init_db
from search import execute_trace

app = FastAPI(title="ScribeLink Demo", description="Hosted Monochromatic ScribeLink v1 Demonstration")

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.on_event("startup")
def startup():
    init_db()

def log_audit(user: str, dept: str, action: str, details: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO audit_logs (username, department, action_type, details) VALUES (?, ?, ?, ?)", (user, dept, action, details))
    conn.commit()
    conn.close()

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/api/projects")
async def get_projects():
    return {
        "projects": [{"id": "PRJ_SCL555", "name": "SCL-555", "description": "SCL-555 High-Speed Controller"}],
        "lots": [
            {"id": "LOT-2026-01", "project_id": "PRJ_SCL555", "name": "Lot 1", "date": "2026-01-20"},
            {"id": "LOT-2026-02", "project_id": "PRJ_SCL555", "name": "Lot 2", "date": "2026-05-15"}
        ]
    }

@app.get("/api/audit_logs")
async def get_audits():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, username, department, action_type, details FROM audit_logs ORDER BY id DESC LIMIT 50")
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"logs": logs}

@app.post("/api/search")
async def search(query: str = Form(...), department: str = Form(None), user: str = Form("Default User"), user_dept: str = Form("Design & TCAD")):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    log_audit(user, user_dept, "QUERY", f"Searched: '{query}' (Filter: {department})")
    try:
        return execute_trace(query, department)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), lot_id: str = Form(...), user: str = Form("Default User"), user_dept: str = Form("Design & TCAD")):
    if not file.filename.endswith((".txt", ".pdf")):
        raise HTTPException(status_code=400, detail="Only .txt and .pdf files are supported in this demo.")
    try:
        content = (await file.read()).decode("utf-8", errors="ignore")
        doc_id = f"DOC-{os.urandom(2).hex().upper()}"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO meetings (id, title, date, lot_id, department, file_path, transcript_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc_id, file.filename.replace(".txt", ""), "2026-06-14", lot_id, user_dept, f"storage/{file.filename}", content)
        )
        conn.commit()
        conn.close()
        log_audit(user, user_dept, "UPLOAD", f"Uploaded: {file.filename} (Lot: {lot_id})")
        return {"status": "success", "filename": file.filename, "document_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/api/document/{doc_id}")
async def get_document(doc_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, date, lot_id, department, transcript_text FROM meetings WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return dict(row)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
