import sqlite3
import json
import os
import datetime

def seed(c):
    # Seed default admin user if not exists
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        import hashlib, secrets
        salt = secrets.token_hex(16)
        h = hashlib.sha256(("admin123" + salt).encode("utf-8")).hexdigest()
        c.execute("INSERT INTO users (email, name, password_hash, salt, role) VALUES (?,?,?,?,?)", ("admin@scl.gov.in", "Admin Principal", h, salt, "admin"))

    # Seed mock meetings from original_seed_docs.json if not exists
    c.execute("SELECT COUNT(*) FROM meetings")
    if c.fetchone()[0] == 0:
        json_path = os.path.join(os.path.dirname(__file__), "original_seed_docs.json")
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                docs = json.load(f)
            for d in docs:
                mid = d.get("id")
                title = d.get("title")
                date = d.get("date")
                lot_id = d.get("lot_id")
                proj_id = d.get("department") or "Unknown"
                text = d.get("transcript_text")
                file_path = d.get("file_path") or ""
                ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else "txt"
                size = len(text.encode("utf-8"))
                created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                c.execute("INSERT INTO meetings (id, title, date, lot_id, project_id, file_path, file_size_bytes, transcript_text, source_type, content_hash, created_at, ocr_quality, corrections_count, ocr_json, ocr_markdown, ocr_engine, page_count, uploaded_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (mid, title, date, lot_id, proj_id, file_path, size, text, ext, "", created_at, "native", 0, None, None, "native", 1, "seed"))
