import sqlite3
from database import DB_PATH

def seed(c):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Seed default admin user if not exists
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        import hashlib, secrets
        salt = secrets.token_hex(16)
        h = hashlib.sha256(("admin123" + salt).encode("utf-8")).hexdigest()
        c.execute("INSERT INTO users (email, name, password_hash, salt, role) VALUES (?,?,?,?,?)", ("admin@scl.gov.in", "Admin Principal", h, salt, "admin"))
        
    conn.commit()
    conn.close()
