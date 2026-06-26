import os
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import get_db_connection, init_db
from search import execute_trace
from audit_ledger import log_audit, verify_audit_ledger
from lineage import create_edge, delete_edge

init_db()

app = FastAPI(title="ScribeLink Demo", description="Hosted ScribeLink with full graph & citation lineage")
BASE_DIR = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.on_event("startup")
def startup(): init_db()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    resp = templates.TemplateResponse(request, "index.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp

@app.get("/api/projects")
async def get_projects():
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id, title, date, lot_id, department FROM meetings;")
    docs = [dict(r) for r in c.fetchall()]
    lots = list({d["lot_id"]: {"id": d["lot_id"], "name": d["lot_id"].replace("-"," "), "date": d["date"]} for d in docs}.values())
    conn.close()
    return {"projects": [{"id":"PRJ_SCL555","name":"SCL-555","description":"SCL-555 High-Speed Controller"}], "lots": lots}

@app.get("/api/audit_logs")
async def get_audits():
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT timestamp, username, department, action_type, details, current_hash FROM audit_logs ORDER BY id DESC LIMIT 50;")
    logs = [dict(r) for r in c.fetchall()]; conn.close()
    return {"logs": logs}

@app.post("/api/audit_logs/verify")
async def verify_ledger(): return verify_audit_ledger()

@app.post("/api/search")
async def search(query: str = Form(...), department: str = Form(None), user: str = Form("Default User"), user_dept: str = Form("Design & TCAD")):
    if not query.strip(): raise HTTPException(400, "Query cannot be empty.")
    log_audit(user, user_dept, "QUERY", f"Searched: '{query}' (Filter: {department})")
    try: return execute_trace(query, department)
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), lot_id: str = Form(...), user: str = Form("Default User"), user_dept: str = Form("Design & TCAD")):
    if not file.filename.endswith((".txt",".pdf")): raise HTTPException(400, "Only .txt/.pdf supported.")
    content = (await file.read()).decode("utf-8", errors="ignore")
    doc_id = f"DOC-{os.urandom(2).hex().upper()}"
    conn = get_db_connection(); c = conn.cursor()
    c.execute("INSERT INTO meetings VALUES (?,?,?,?,?,?,?);", (doc_id, file.filename.replace(".txt",""), "2026-06-14", lot_id, user_dept, f"storage/{file.filename}", content))
    conn.commit(); conn.close()
    log_audit(user, user_dept, "UPLOAD", f"Uploaded: {file.filename}")
    return {"status": "success", "filename": file.filename, "document_id": doc_id}

@app.get("/api/document/{doc_id}")
async def get_document(doc_id: str):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id, title, date, lot_id, department, transcript_text FROM meetings WHERE id=?;", (doc_id,))
    row = c.fetchone(); conn.close()
    if not row: raise HTTPException(404, "Document not found")
    return dict(row)

@app.get("/api/download/{doc_id}")
async def download_document(doc_id: str):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT id, title, transcript_text FROM meetings WHERE id=?;", (doc_id,))
    row = c.fetchone(); conn.close()
    if not row: raise HTTPException(404, "Document not found")
    fname = row["title"].replace(" ","_").replace("/","_") + ".txt"
    return PlainTextResponse(content=row["transcript_text"], headers={"Content-Disposition": f'attachment; filename="{fname}"'})

@app.post("/api/lineage/create")
async def api_create_edge(from_node_id: str = Form(...), to_node_id: str = Form(...), relation_type: str = Form("followed_by"), rationale: str = Form(""), user: str = Form("Default User"), user_dept: str = Form("Design & TCAD")):
    try: return create_edge(from_node_id, to_node_id, relation_type, rationale, user, user_dept)
    except Exception as e: raise HTTPException(400, str(e))

@app.post("/api/lineage/delete")
async def api_delete_edge(from_node_id: str = Form(...), to_node_id: str = Form(...), user: str = Form("Default User"), user_dept: str = Form("Design & TCAD")):
    try: return delete_edge(from_node_id, to_node_id, user, user_dept)
    except Exception as e: raise HTTPException(400, str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
