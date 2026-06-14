import sqlite3
import os
import shutil

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")
if os.environ.get("VERCEL"):
    tmp_db = "/tmp/app.db"
    if not os.path.exists(tmp_db) and os.path.exists(DB_PATH):
        shutil.copy(DB_PATH, tmp_db)
    DB_PATH = tmp_db

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meetings (
        id TEXT PRIMARY KEY, title TEXT, date TEXT, lot_id TEXT, department TEXT, file_path TEXT, transcript_text TEXT
    );""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS decisions (
        id TEXT PRIMARY KEY, meeting_id TEXT, summary TEXT, status TEXT, type TEXT,
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
    );""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lineage (
        from_node_id TEXT, to_node_id TEXT, relation_type TEXT, rationale TEXT,
        PRIMARY KEY (from_node_id, to_node_id)
    );""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        username TEXT, department TEXT, action_type TEXT, details TEXT
    );""")
    
    cursor.execute("SELECT COUNT(*) FROM meetings;")
    if cursor.fetchone()[0] == 0:
        base_dir = os.path.dirname(__file__)
        def read_file(rel_path):
            with open(os.path.join(base_dir, rel_path), "r", encoding="utf-8") as f:
                return f.read()
        
        meets = [
            ("SCL-555-DS-001", "Design Specification", "2026-01-20", "LOT-2026-01", "Design & TCAD", "storage/spec.txt"),
            ("SCL-555-MM-001", "Design Review Meeting", "2026-02-10", "LOT-2026-01", "Design & TCAD", "storage/review.txt"),
            ("SCL-555-MM-002", "Shrink Approval Meeting", "2026-05-15", "LOT-2026-02", "Design & TCAD", "storage/shrink.txt"),
            ("SCL-555-FAB-001", "Lot 1 Fab Run Report", "2026-03-05", "LOT-2026-01", "Fabrication Operations", "storage/fab1.txt"),
            ("SCL-555-MM-003", "Yield Excursion Review", "2026-06-01", "LOT-2026-02", "Quality Assurance", "storage/excursion.txt"),
            ("SCL-555-PKG-001", "Lot 1 Packaging Report", "2026-03-12", "LOT-2026-01", "Packaging & Assembly", "storage/pkg1.txt"),
            ("SCL-555-QA-001", "Lot 1 Quality Clearance", "2026-03-20", "LOT-2026-01", "Quality Assurance", "storage/qa1.txt")
        ]
        meetings_data = [(m[0], m[1], m[2], m[3], m[4], m[5], read_file(m[5])) for m in meets]
        cursor.executemany("INSERT INTO meetings VALUES (?, ?, ?, ?, ?, ?, ?);", meetings_data)
        
        decs = [
            ("DEC-1", "SCL-555-DS-001", "Metal Spacing Specified: 0.25 um", "Approved", "Spec_Change"),
            ("DEC-2", "SCL-555-MM-001", "Handoff baseline specifications for Lot 1 release.", "Approved", "Decision"),
            ("DEC-3", "SCL-555-MM-002", "Layout shrink to 0.18 um minimum Metal 1 spacing approved.", "Approved", "Decision"),
            ("DEC-4", "SCL-555-MM-003", "Yield dropped to 45.8% due to bridging shorts on Metal 1.", "Failed", "Excursion"),
            ("DEC-5", "SCL-555-PKG-001", "Gold wire bonding completed with shear force of 12.5g.", "Approved", "Spec_Change"),
            ("DEC-6", "SCL-555-QA-001", "Lot 1 passed operational reliability HTOL tests.", "Approved", "Decision")
        ]
        cursor.executemany("INSERT INTO decisions VALUES (?, ?, ?, ?, ?);", decs)
        
        edges = [
            ("SCL-555-DS-001", "SCL-555-MM-001", "followed_by", "Handoff of specifications"),
            ("SCL-555-MM-001", "SCL-555-FAB-001", "followed_by", "Lot 1 Fabrication"),
            ("SCL-555-MM-001", "SCL-555-MM-002", "followed_by", "Shrink discussion"),
            ("SCL-555-MM-002", "SCL-555-MM-003", "triggered_by", "Layout shrink spacing was approved without recipe updates"),
            ("SCL-555-FAB-001", "SCL-555-PKG-001", "followed_by", "Lot 1 Packaging"),
            ("SCL-555-PKG-001", "SCL-555-QA-001", "followed_by", "Lot 1 Quality Assurance Review")
        ]
        cursor.executemany("INSERT INTO lineage VALUES (?, ?, ?, ?);", edges)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
