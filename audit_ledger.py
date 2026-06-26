import hashlib
from datetime import datetime
from database import get_db_connection

def calculate_hash(timestamp: str, username: str, dept: str, action: str, details: str, parent_hash: str) -> str:
    payload = f"{timestamp}{username}{dept}{action}{details}{parent_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def log_audit(user: str, dept: str, action: str, details: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT current_hash FROM audit_logs ORDER BY id DESC LIMIT 1;")
    row = cursor.fetchone()
    parent = row["current_hash"] if row else "GENESIS"
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    curr_hash = calculate_hash(now_str, user, dept, action, details, parent)
    cursor.execute("""
        INSERT INTO audit_logs (timestamp, username, department, action_type, details, parent_hash, current_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (now_str, user, dept, action, details, parent, curr_hash))
    conn.commit()
    conn.close()

def verify_audit_ledger() -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, timestamp, username, department, action_type, details, parent_hash, current_hash FROM audit_logs ORDER BY id ASC;")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    prev_hash = "GENESIS"
    for r in rows:
        if r["parent_hash"] != prev_hash:
            return {"valid": False, "failed_id": r["id"]}
        recalc = calculate_hash(r["timestamp"], r["username"], r["department"], r["action_type"], r["details"], r["parent_hash"])
        if r["current_hash"] != recalc:
            return {"valid": False, "failed_id": r["id"]}
        prev_hash = r["current_hash"]
        
    return {"valid": True, "count": len(rows)}
