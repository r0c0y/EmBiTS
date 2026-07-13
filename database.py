import os
from db_adapter import get_db_connection, IS_PG
DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")
_initialized = False

def init_db():
    global _initialized
    if _initialized: return
    conn = get_db_connection(); c = conn.cursor()
    if not IS_PG: c.execute("PRAGMA foreign_keys = ON;")
    tables = [
        "CREATE TABLE IF NOT EXISTS meetings (id TEXT PRIMARY KEY, title TEXT, date TEXT, lot_id TEXT, project_id TEXT DEFAULT 'Unknown', file_path TEXT, file_size_bytes INTEGER DEFAULT 0, transcript_text TEXT, source_type TEXT, content_hash TEXT, created_at TEXT, ocr_quality TEXT DEFAULT 'auto', corrections_count INTEGER DEFAULT 0, ocr_json TEXT, ocr_markdown TEXT, ocr_engine TEXT, page_count INTEGER DEFAULT 0, uploaded_by TEXT DEFAULT 'Anonymous')",
        "CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY, meeting_id TEXT, chunk_index INTEGER, chunk_text TEXT, page_number INTEGER DEFAULT 1, FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE)",
        "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_text, content='chunks', content_rowid='rowid', tokenize='porter unicode61')",
        "CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, meeting_id TEXT, summary TEXT, status TEXT, type TEXT, FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE)",
        "CREATE TABLE IF NOT EXISTS lineage (from_node_id TEXT, to_node_id TEXT, relation_type TEXT, rationale TEXT, PRIMARY KEY (from_node_id, to_node_id))",
        "CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, username TEXT, department TEXT, action_type TEXT, details TEXT, parent_hash TEXT, current_hash TEXT)",
        "CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, name TEXT, password_hash TEXT, salt TEXT, role TEXT DEFAULT 'user')",
        "CREATE TABLE IF NOT EXISTS hierarchical_summaries (id TEXT PRIMARY KEY, project_id TEXT, level INTEGER, summary_text TEXT, source_ids TEXT)",
        "CREATE VIRTUAL TABLE IF NOT EXISTS hierarchical_summaries_fts USING fts5(summary_text, content='hierarchical_summaries', content_rowid='rowid', tokenize='porter unicode61')"
    ]
    for sql in tables: c.execute(sql)
    for trig in ["CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN INSERT INTO chunks_fts(rowid, chunk_text) VALUES (new.rowid, new.chunk_text); END",
                 "CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text) VALUES ('delete', old.rowid, old.chunk_text); END",
                 "CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text) VALUES ('delete', old.rowid, old.chunk_text); INSERT INTO chunks_fts(rowid, chunk_text) VALUES (new.rowid, new.chunk_text); END",
                 "CREATE TRIGGER IF NOT EXISTS h_summaries_ai AFTER INSERT ON hierarchical_summaries BEGIN INSERT INTO hierarchical_summaries_fts(rowid, summary_text) VALUES (new.rowid, new.summary_text); END",
                 "CREATE TRIGGER IF NOT EXISTS h_summaries_ad AFTER DELETE ON hierarchical_summaries BEGIN INSERT INTO hierarchical_summaries_fts(hierarchical_summaries_fts, rowid, summary_text) VALUES ('delete', old.rowid, old.summary_text); END",
                 "CREATE TRIGGER IF NOT EXISTS h_summaries_au AFTER UPDATE ON hierarchical_summaries BEGIN INSERT INTO hierarchical_summaries_fts(hierarchical_summaries_fts, rowid, summary_text) VALUES ('delete', old.rowid, old.summary_text); INSERT INTO hierarchical_summaries_fts(rowid, summary_text) VALUES (new.rowid, new.summary_text); END"]:
        try: c.execute(trig)
        except: pass
    for col in ["project_id TEXT DEFAULT 'Unknown'", "source_type TEXT", "content_hash TEXT", "created_at TEXT", "file_size_bytes INTEGER DEFAULT 0", "ocr_quality TEXT DEFAULT 'auto'", "corrections_count INTEGER DEFAULT 0", "ocr_json TEXT", "ocr_markdown TEXT", "ocr_engine TEXT", "page_count INTEGER DEFAULT 0", "uploaded_by TEXT DEFAULT 'Anonymous'", "status TEXT DEFAULT 'pending'"]:
        try: c.execute(f"ALTER TABLE meetings ADD COLUMN {col};")
        except: pass
    
    # Try adding page_number to chunks table if it is an existing schema
    try: c.execute("ALTER TABLE chunks ADD COLUMN page_number INTEGER DEFAULT 1;")
    except: pass

    # Performance indexes
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_meetings_project ON meetings(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_meetings_status ON meetings(status)",
        "CREATE INDEX IF NOT EXISTS idx_meetings_created ON meetings(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_chunks_meeting ON chunks(meeting_id)",
    ]:
        try: c.execute(idx)
        except: pass

    conn.commit()
    conn.close()

    from vector_store import init_vector_table, build_missing_embeddings
    init_vector_table()
    
    import threading
    threading.Thread(target=build_missing_embeddings, daemon=True).start()
    
    _initialized = True

def get_projects():
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT DISTINCT project_id FROM meetings WHERE project_id IS NOT NULL ORDER BY project_id;")
    return [r[0] for r in c.fetchall()]

def get_lots(project_id=None):
    conn = get_db_connection(); c = conn.cursor()
    sql = "SELECT DISTINCT lot_id FROM meetings WHERE lot_id IS NOT NULL"
    if project_id: sql += " AND project_id = ?"
    c.execute(sql, (project_id,) if project_id else ())
    return [r[0] for r in c.fetchall()]

def get_db_path(): return DB_PATH
